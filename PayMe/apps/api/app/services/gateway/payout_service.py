"""Payout batch creation, mock execution, and reconciliation reporting.

All payout operations are idempotent: passing the same idempotency_key
returns the existing record rather than creating a duplicate.

Mock execution simulates a 90% success / 10% failure rate using a
deterministic hash of each transfer's idempotency_key so results are
reproducible across repeated test runs.
"""

import hashlib
import uuid
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import (
    AttorneyAccount,
    ClaimApproval,
    PayoutBatch,
    PayoutTransfer,
    Settlement,
    SettlementAccount,
    User,
    UserSettlementPreference,
)
from app.services.events.service import emit_event


# ---------------------------------------------------------------------------
# Batch creation
# ---------------------------------------------------------------------------


def create_payout_batch(
    db: Session,
    attorney: AttorneyAccount,
    settlement_id: UUID,
    idempotency_key: str,
) -> PayoutBatch:
    """
    Create a PayoutBatch (status='queued') and one PayoutTransfer per
    approved claimant.

    Idempotency: if a batch with this idempotency_key already exists it is
    returned as-is without any mutations.

    Amount per transfer:
      - Uses ClaimApproval.approved_amount_cents when present.
      - Falls back to Settlement.payout_min_cents if the approval has no
        explicit amount.
      - Defaults to 0 when neither is available.

    Emits payout_batch_created.
    """
    # Idempotency guard
    existing = db.scalar(
        select(PayoutBatch).where(PayoutBatch.idempotency_key == idempotency_key)
    )
    if existing is not None:
        return existing

    settlement = db.get(Settlement, settlement_id)
    fallback_amount = (settlement.payout_min_cents or 0) if settlement else 0

    # All approved claimants for this settlement
    approvals = db.scalars(
        select(ClaimApproval).where(
            ClaimApproval.settlement_id == settlement_id,
            ClaimApproval.status == "approved",
        )
    ).all()

    batch = PayoutBatch(
        id=uuid.uuid4(),
        attorney_id=attorney.id,
        settlement_id=settlement_id,
        status="queued",
        idempotency_key=idempotency_key,
        total_transfers=0,
        successful_transfers=0,
        failed_transfers=0,
        total_amount_cents=0,
    )
    db.add(batch)
    db.flush()  # populate batch.id before creating transfers

    transfers = []
    total_cents = 0
    for approval in approvals:
        amount = (
            approval.approved_amount_cents
            if approval.approved_amount_cents is not None
            else fallback_amount
        )
        transfer_idem_key = f"transfer:{batch.id}:{approval.id}"
        transfer = PayoutTransfer(
            id=uuid.uuid4(),
            batch_id=batch.id,
            approval_id=approval.id,
            user_id=approval.user_id,
            amount_cents=amount,
            status="pending",
            idempotency_key=transfer_idem_key,
        )
        db.add(transfer)
        transfers.append(transfer)
        total_cents += amount

    batch.total_transfers = len(transfers)
    batch.total_amount_cents = total_cents
    db.flush()

    emit_event(
        db,
        "payout_batch_created",
        payload={
            "batch_id": str(batch.id),
            "attorney_id": str(attorney.id),
            "settlement_id": str(settlement_id),
            "total_transfers": batch.total_transfers,
            "total_amount_cents": total_cents,
        },
    )
    return batch


# ---------------------------------------------------------------------------
# Batch processing (mock execution)
# ---------------------------------------------------------------------------


def _mock_transfer_succeeds(idempotency_key: str) -> bool:
    """
    Deterministically decide whether a transfer should succeed.

    Uses the last byte of the SHA-256 hash of the key: if it is >= 26
    (i.e. the key falls in the top ~10% of the byte range) the transfer
    fails; otherwise it succeeds.  This gives a stable ~90% success rate.
    """
    digest = hashlib.sha256(idempotency_key.encode()).digest()
    return digest[-1] < 230  # 230/256 ≈ 89.8%


def process_payout_batch(db: Session, batch_id: UUID) -> PayoutBatch:
    """
    Execute all pending transfers in the batch (mock — no real bank API).

    For each pending transfer:
      - Sets status='processing', initiated_at=now()
      - Simulates success or failure deterministically
      - On success: status='completed', provider_transfer_id=mock ref
      - On failure: status='failed', failure_reason='mock_bank_decline'
      - Updates the linked ClaimApproval accordingly

    Updates batch counters and sets a terminal status:
      - 'completed'  — all transfers succeeded
      - 'partial'    — mixed results
      - 'failed'     — all transfers failed (or no transfers)

    Emits payout_transfer_completed / payout_transfer_failed per transfer,
    then payout_batch_completed.
    """
    batch = db.get(PayoutBatch, batch_id)
    if batch is None:
        raise ValueError(f"PayoutBatch {batch_id} not found")

    pending_transfers = db.scalars(
        select(PayoutTransfer).where(
            PayoutTransfer.batch_id == batch_id,
            PayoutTransfer.status == "pending",
        )
    ).all()

    now = datetime.now(timezone.utc)
    success_count = 0
    failure_count = 0

    for transfer in pending_transfers:
        transfer.status = "processing"
        transfer.initiated_at = now
        db.flush()

        if _mock_transfer_succeeds(transfer.idempotency_key):
            transfer.status = "completed"
            transfer.completed_at = now
            transfer.provider_transfer_id = f"mock-{transfer.id}"
            success_count += 1

            # Update linked approval
            approval = db.get(ClaimApproval, transfer.approval_id)
            if approval is not None:
                approval.status = "paid"

            # Sync user-facing claim status to paid_out
            pref = db.scalar(
                select(UserSettlementPreference).where(
                    UserSettlementPreference.user_id == transfer.user_id,
                    UserSettlementPreference.settlement_id == batch.settlement_id,
                )
            )
            if pref is not None:
                pref.claim_status = "paid_out"
                pref.claim_outcome_at = now

            emit_event(
                db,
                "payout_transfer_completed",
                user_id=transfer.user_id,
                payload={
                    "transfer_id": str(transfer.id),
                    "batch_id": str(batch_id),
                    "amount_cents": transfer.amount_cents,
                    "provider_transfer_id": transfer.provider_transfer_id,
                },
            )
        else:
            transfer.status = "failed"
            transfer.completed_at = now
            transfer.failure_reason = "mock_bank_decline"
            failure_count += 1

            approval = db.get(ClaimApproval, transfer.approval_id)
            if approval is not None:
                approval.status = "failed"

            emit_event(
                db,
                "payout_transfer_failed",
                user_id=transfer.user_id,
                payload={
                    "transfer_id": str(transfer.id),
                    "batch_id": str(batch_id),
                    "failure_reason": transfer.failure_reason,
                },
            )

    # Accumulate counters (handles partial re-processing or empty batches)
    batch.successful_transfers = (batch.successful_transfers or 0) + success_count
    batch.failed_transfers = (batch.failed_transfers or 0) + failure_count
    batch.completed_at = now

    total = batch.total_transfers or 0
    completed = batch.successful_transfers
    failed = batch.failed_transfers

    if total == 0 or failed == total:
        batch.status = "failed"
    elif completed == total:
        batch.status = "completed"
    else:
        batch.status = "partial"

    db.flush()
    emit_event(
        db,
        "payout_batch_completed",
        payload={
            "batch_id": str(batch_id),
            "status": batch.status,
            "successful_transfers": batch.successful_transfers,
            "failed_transfers": batch.failed_transfers,
        },
    )
    return batch


# ---------------------------------------------------------------------------
# Reconciliation report
# ---------------------------------------------------------------------------


def execute_payouts(
    db: Session,
    attorney: AttorneyAccount,
    items: list[dict],
    idempotency_key: str,
) -> dict:
    """Approve a list of claimants and immediately process payment.

    items: [{"user_id": str, "settlement_id": str, "amount_cents": int | None}]

    Groups by settlement, creates one PayoutBatch per settlement, processes
    each batch immediately (mock simulation).  Fully idempotent via per-batch
    idempotency keys derived from the caller-supplied idempotency_key.

    Returns {"batches": [...reconciliation dicts], "total_items": int, "total_approved": int}
    """
    if not items:
        return {"batches": [], "total_items": 0, "total_approved": 0}

    now = datetime.now(timezone.utc)
    approved_approvals: list[ClaimApproval] = []

    # Step 1: approve every item that has an active settlement account
    for item in items:
        user_id = UUID(str(item["user_id"]))
        settlement_id = UUID(str(item["settlement_id"]))
        amount_cents = item.get("amount_cents")

        sa = db.scalar(
            select(SettlementAccount).where(
                SettlementAccount.settlement_id == settlement_id,
                SettlementAccount.status == "active",
            )
        )
        if sa is None:
            continue  # no bank account — skip silently

        existing = db.scalar(
            select(ClaimApproval).where(
                ClaimApproval.user_id == user_id,
                ClaimApproval.settlement_id == settlement_id,
            )
        )
        if existing is not None:
            existing.attorney_id = attorney.id
            existing.approved_amount_cents = amount_cents
            existing.status = "approved"
            existing.approved_at = now
            existing.rejected_at = None
            approval = existing
        else:
            approval = ClaimApproval(
                id=uuid.uuid4(),
                user_id=user_id,
                settlement_id=settlement_id,
                attorney_id=attorney.id,
                approved_amount_cents=amount_cents,
                status="approved",
                approved_at=now,
            )
            db.add(approval)

        db.flush()
        emit_event(
            db,
            "claimant_approved",
            user_id=user_id,
            payload={
                "approval_id": str(approval.id),
                "attorney_id": str(attorney.id),
                "settlement_id": str(settlement_id),
                "amount_cents": amount_cents,
            },
        )
        approved_approvals.append(approval)

    if not approved_approvals:
        return {"batches": [], "total_items": len(items), "total_approved": 0}

    # Step 2: group approvals by settlement and create+process one batch each
    settlement_approvals: dict[UUID, list[ClaimApproval]] = {}
    for approval in approved_approvals:
        settlement_approvals.setdefault(approval.settlement_id, []).append(approval)

    batch_results = []
    for settlement_id, approvals in settlement_approvals.items():
        batch_idem = f"{idempotency_key}:sid:{settlement_id}"

        existing_batch = db.scalar(
            select(PayoutBatch).where(PayoutBatch.idempotency_key == batch_idem)
        )
        if existing_batch is not None:
            batch_results.append(get_batch_reconciliation(db, existing_batch.id))
            continue

        settlement_obj = db.get(Settlement, settlement_id)
        fallback = (settlement_obj.payout_min_cents or 0) if settlement_obj else 0

        batch = PayoutBatch(
            id=uuid.uuid4(),
            attorney_id=attorney.id,
            settlement_id=settlement_id,
            status="queued",
            idempotency_key=batch_idem,
            total_transfers=0,
            successful_transfers=0,
            failed_transfers=0,
            total_amount_cents=0,
        )
        db.add(batch)
        db.flush()

        total_cents = 0
        for approval in approvals:
            amount = (
                approval.approved_amount_cents
                if approval.approved_amount_cents is not None
                else fallback
            )
            db.add(
                PayoutTransfer(
                    id=uuid.uuid4(),
                    batch_id=batch.id,
                    approval_id=approval.id,
                    user_id=approval.user_id,
                    amount_cents=amount,
                    status="pending",
                    idempotency_key=f"transfer:{batch.id}:{approval.id}",
                )
            )
            total_cents += amount

        batch.total_transfers = len(approvals)
        batch.total_amount_cents = total_cents
        db.flush()

        emit_event(
            db,
            "payout_batch_created",
            payload={
                "batch_id": str(batch.id),
                "attorney_id": str(attorney.id),
                "settlement_id": str(settlement_id),
                "total_transfers": batch.total_transfers,
                "total_amount_cents": total_cents,
            },
        )

        processed = process_payout_batch(db, batch.id)
        batch_results.append(get_batch_reconciliation(db, processed.id))

    return {
        "batches": batch_results,
        "total_items": len(items),
        "total_approved": len(approved_approvals),
    }


def list_payout_history(
    db: Session,
    attorney: AttorneyAccount,
) -> list[dict]:
    """Return all payout transfers for batches owned by this attorney."""
    rows = (
        db.query(PayoutTransfer, PayoutBatch, User, Settlement)
        .join(PayoutBatch, PayoutBatch.id == PayoutTransfer.batch_id)
        .join(User, User.id == PayoutTransfer.user_id)
        .join(Settlement, Settlement.id == PayoutBatch.settlement_id)
        .filter(PayoutBatch.attorney_id == attorney.id)
        .order_by(PayoutTransfer.created_at.desc())
        .all()
    )
    return [
        {
            "transfer_id": str(transfer.id),
            "batch_id": str(batch.id),
            "user_id": str(transfer.user_id),
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "settlement_id": str(batch.settlement_id),
            "settlement_title": settlement.title,
            "amount_cents": transfer.amount_cents,
            "status": transfer.status,
            "provider_transfer_id": transfer.provider_transfer_id,
            "failure_reason": transfer.failure_reason,
            "initiated_at": transfer.initiated_at,
            "completed_at": transfer.completed_at,
        }
        for transfer, batch, user, settlement in rows
    ]


def get_account_balance(db: Session, attorney: AttorneyAccount) -> dict:
    """Return a sandbox balance summary for this attorney's settlement fund.

    The sandbox starts with a fixed $100,000 balance.  Disbursed = sum of
    completed transfers; pending = sum of approved-but-not-yet-paid amounts;
    available = sandbox balance - disbursed.
    """
    SANDBOX_BALANCE_CENTS = 10_000_000  # $100,000.00

    disbursed = db.scalar(
        select(func.coalesce(func.sum(PayoutTransfer.amount_cents), 0))
        .join(PayoutBatch, PayoutBatch.id == PayoutTransfer.batch_id)
        .where(
            PayoutBatch.attorney_id == attorney.id,
            PayoutTransfer.status == "completed",
        )
    ) or 0

    pending = db.scalar(
        select(func.coalesce(func.sum(ClaimApproval.approved_amount_cents), 0))
        .where(
            ClaimApproval.attorney_id == attorney.id,
            ClaimApproval.status == "approved",
        )
    ) or 0

    sa = db.scalar(
        select(SettlementAccount).where(
            SettlementAccount.attorney_id == attorney.id,
            SettlementAccount.status == "active",
        )
    )
    bank_name = sa.bank_name if sa else "Sandbox Bank"

    return {
        "bank_name": bank_name,
        "sandbox_balance_cents": SANDBOX_BALANCE_CENTS,
        "disbursed_cents": int(disbursed),
        "pending_approval_cents": int(pending),
        "available_cents": SANDBOX_BALANCE_CENTS - int(disbursed),
    }


def get_batch_reconciliation(db: Session, batch_id: UUID) -> dict:
    """
    Return a full reconciliation report for a payout batch.

    Shape:
    {
        batch_id, settlement_id, status, total, successful, failed,
        total_amount_cents,
        transfers: [
            {user_id, amount_cents, status, provider_transfer_id, failure_reason}
        ]
    }
    """
    batch = db.get(PayoutBatch, batch_id)
    if batch is None:
        raise ValueError(f"PayoutBatch {batch_id} not found")

    transfers = db.scalars(
        select(PayoutTransfer).where(PayoutTransfer.batch_id == batch_id)
    ).all()

    return {
        "batch_id": str(batch.id),
        "settlement_id": str(batch.settlement_id),
        "status": batch.status,
        "total": batch.total_transfers,
        "successful": batch.successful_transfers,
        "failed": batch.failed_transfers,
        "total_amount_cents": batch.total_amount_cents,
        "transfers": [
            {
                "user_id": str(t.user_id),
                "amount_cents": t.amount_cents,
                "status": t.status,
                "provider_transfer_id": t.provider_transfer_id,
                "failure_reason": t.failure_reason,
            }
            for t in transfers
        ],
    }
