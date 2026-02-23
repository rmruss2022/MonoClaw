"""Attorney account management, settlement account linking, and claimant approval.

Covers:
- Attorney registration and API key generation
- Settlement bank-account linking (encrypted at rest)
- Listing submitted claimants for a settlement
- Approving and rejecting individual claimants
"""

import hashlib
import secrets
import uuid
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.crypto import encrypt_token
from app.core.settings import settings
from app.models.entities import (
    AttorneyAccount,
    ClaimApproval,
    Settlement,
    SettlementAccount,
    User,
    UserSettlementPreference,
)
from app.services.events.service import emit_event


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(
        f"{settings.gateway_api_key_salt}:{raw_key}".encode()
    ).hexdigest()


def generate_api_key() -> tuple[str, str]:
    """Return (raw_key, hashed_key). The raw key is shown once to the attorney."""
    raw_key = secrets.token_urlsafe(32)
    hashed_key = _hash_api_key(raw_key)
    return raw_key, hashed_key


# ---------------------------------------------------------------------------
# Attorney lifecycle
# ---------------------------------------------------------------------------


def register_attorney(
    db: Session,
    name: str,
    email: str,
    firm_name: str | None,
) -> tuple[AttorneyAccount, str]:
    """
    Create an AttorneyAccount with a freshly generated API key.

    Returns (account, raw_api_key).  The raw key must be returned to the caller
    once and is never persisted in plaintext.

    Raises ValueError if the email is already registered.
    """
    existing = db.scalar(
        select(AttorneyAccount).where(AttorneyAccount.email == email)
    )
    if existing is not None:
        raise ValueError(f"Attorney email already registered: {email}")

    raw_key, hashed_key = generate_api_key()
    account = AttorneyAccount(
        id=uuid.uuid4(),
        name=name,
        email=email,
        firm_name=firm_name,
        api_key_hash=hashed_key,
        status="active",
    )
    db.add(account)
    db.flush()
    emit_event(
        db,
        "attorney_registered",
        payload={"attorney_id": str(account.id), "email": email},
    )
    return account, raw_key


def get_attorney_by_api_key(db: Session, raw_key: str) -> AttorneyAccount | None:
    """Look up an attorney by their raw API key (hashed for comparison)."""
    hashed = _hash_api_key(raw_key)
    return db.scalar(
        select(AttorneyAccount).where(AttorneyAccount.api_key_hash == hashed)
    )


# ---------------------------------------------------------------------------
# Settlement account linking
# ---------------------------------------------------------------------------


def link_settlement_account(
    db: Session,
    attorney: AttorneyAccount,
    settlement_id: UUID,
    bank_name: str | None,
    account_ref: str,
) -> SettlementAccount:
    """
    Link a bank account to a settlement for the given attorney.

    The account_ref is encrypted before storage.  If a SettlementAccount
    already exists for this settlement it is updated in-place (upsert).
    Emits settlement_account_linked.
    """
    encrypted_ref = encrypt_token(account_ref)

    existing = db.scalar(
        select(SettlementAccount).where(
            SettlementAccount.settlement_id == settlement_id
        )
    )

    if existing is not None:
        existing.attorney_id = attorney.id
        existing.bank_name = bank_name
        existing.account_ref_enc = encrypted_ref
        existing.status = "active"
        existing.linked_at = datetime.now(timezone.utc)
        account = existing
    else:
        account = SettlementAccount(
            id=uuid.uuid4(),
            attorney_id=attorney.id,
            settlement_id=settlement_id,
            bank_name=bank_name,
            account_ref_enc=encrypted_ref,
            status="active",
            linked_at=datetime.now(timezone.utc),
        )
        db.add(account)

    db.flush()
    emit_event(
        db,
        "settlement_account_linked",
        payload={
            "attorney_id": str(attorney.id),
            "settlement_id": str(settlement_id),
            "account_id": str(account.id),
        },
    )
    return account


# ---------------------------------------------------------------------------
# Claimant listing
# ---------------------------------------------------------------------------


def list_submitted_claimants(
    db: Session,
    attorney: AttorneyAccount,
    settlement_id: UUID,
) -> list[dict]:
    """
    Return users whose claim_status is 'submitted' for this settlement.

    Joins UserSettlementPreference with User.  Returns a list of dicts:
      {user_id, email, first_name, last_name, submitted_at}
    """
    rows = (
        db.query(UserSettlementPreference, User)
        .join(User, User.id == UserSettlementPreference.user_id)
        .filter(
            UserSettlementPreference.settlement_id == settlement_id,
            UserSettlementPreference.claim_status == "submitted",
        )
        .all()
    )
    return [
        {
            "user_id": str(pref.user_id),
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "submitted_at": pref.claim_submitted_at,
        }
        for pref, user in rows
    ]


# ---------------------------------------------------------------------------
# Approval and rejection
# ---------------------------------------------------------------------------


def approve_claimant(
    db: Session,
    attorney: AttorneyAccount,
    user_id: UUID,
    settlement_id: UUID,
    amount_cents: int | None,
    note: str | None,
) -> ClaimApproval:
    """
    Upsert a ClaimApproval record with status='approved'.

    Raises ValueError if the settlement has no linked SettlementAccount.
    Emits claimant_approved.
    """
    # Guard: settlement must have a bank account before approving payouts
    account = db.scalar(
        select(SettlementAccount).where(
            SettlementAccount.settlement_id == settlement_id,
            SettlementAccount.status == "active",
        )
    )
    if account is None:
        raise ValueError(
            f"Settlement {settlement_id} has no active bank account linked. "
            "Link a settlement account before approving claimants."
        )

    existing = db.scalar(
        select(ClaimApproval).where(
            ClaimApproval.user_id == user_id,
            ClaimApproval.settlement_id == settlement_id,
        )
    )

    now = datetime.now(timezone.utc)
    if existing is not None:
        existing.attorney_id = attorney.id
        existing.approved_amount_cents = amount_cents
        existing.status = "approved"
        existing.review_note = note
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
            review_note=note,
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
    return approval


def list_all_submitted_claimants(
    db: Session,
    attorney: AttorneyAccount,
) -> list[dict]:
    """Return all submitted claimants across every settlement the attorney has an active account for.

    Joins UserSettlementPreference + User + Settlement + optional ClaimApproval.
    Includes settlement payout_min_cents so the frontend can pre-fill amounts.
    """
    managed_sids = db.scalars(
        select(SettlementAccount.settlement_id).where(
            SettlementAccount.attorney_id == attorney.id,
            SettlementAccount.status == "active",
        )
    ).all()

    if not managed_sids:
        return []

    rows = (
        db.query(UserSettlementPreference, User, Settlement)
        .join(User, User.id == UserSettlementPreference.user_id)
        .join(Settlement, Settlement.id == UserSettlementPreference.settlement_id)
        .filter(
            UserSettlementPreference.settlement_id.in_(managed_sids),
            UserSettlementPreference.claim_status == "submitted",
        )
        .order_by(UserSettlementPreference.claim_submitted_at.desc())
        .all()
    )

    result = []
    for pref, user, settlement in rows:
        approval = db.scalar(
            select(ClaimApproval).where(
                ClaimApproval.user_id == user.id,
                ClaimApproval.settlement_id == settlement.id,
            )
        )
        result.append(
            {
                "user_id": str(user.id),
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "settlement_id": str(settlement.id),
                "settlement_title": settlement.title,
                "settlement_payout_min_cents": settlement.payout_min_cents,
                "submitted_at": pref.claim_submitted_at,
                "approval_id": str(approval.id) if approval else None,
                "approval_status": approval.status if approval else "pending",
                "approved_amount_cents": approval.approved_amount_cents if approval else None,
            }
        )
    return result


def reject_claimant(
    db: Session,
    attorney: AttorneyAccount,
    user_id: UUID,
    settlement_id: UUID,
    note: str | None,
) -> ClaimApproval:
    """
    Upsert a ClaimApproval record with status='rejected'.
    Emits claimant_rejected.
    """
    existing = db.scalar(
        select(ClaimApproval).where(
            ClaimApproval.user_id == user_id,
            ClaimApproval.settlement_id == settlement_id,
        )
    )

    now = datetime.now(timezone.utc)
    if existing is not None:
        existing.attorney_id = attorney.id
        existing.status = "rejected"
        existing.review_note = note
        existing.rejected_at = now
        existing.approved_at = None
        approval = existing
    else:
        approval = ClaimApproval(
            id=uuid.uuid4(),
            user_id=user_id,
            settlement_id=settlement_id,
            attorney_id=attorney.id,
            status="rejected",
            review_note=note,
            rejected_at=now,
        )
        db.add(approval)

    db.flush()
    emit_event(
        db,
        "claimant_rejected",
        user_id=user_id,
        payload={
            "approval_id": str(approval.id),
            "attorney_id": str(attorney.id),
            "settlement_id": str(settlement_id),
        },
    )
    return approval
