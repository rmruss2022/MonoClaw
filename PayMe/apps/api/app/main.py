import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.admin import router as admin_router
from app.api.routes.auth import router as auth_router
from app.api.routes.autofill import router as autofill_router
from app.api.routes.gateway import router as gateway_router
from app.api.routes.integrations import router as integrations_router
from app.api.routes.matching import claims_router
from app.api.routes.matching import router as matching_router
from app.api.routes.matching import settlement_router
from app.api.routes.me import router as me_router
from app.api.routes.onboarding import router as onboarding_router
from app.core.logging import RequestIDMiddleware, app_logger
from app.core.settings import settings


def _provision_demo_users() -> None:
    """Ensure demo/test accounts exist with correct roles on every startup.

    Creates accounts if they don't exist; updates role if they do.
    All demo accounts share `settings.mock_provision_password`.

    Accounts created:
    - large_test_user  → role: super_user
    - admin_test       → role: admin
    - attorney_test    → role: attorney  + linked AttorneyAccount
    - attorney_user    → role: attorney  + linked AttorneyAccount
    """
    from sqlalchemy import select  # noqa: PLC0415

    from app.core.db import SessionLocal  # noqa: PLC0415
    from app.core.security import hash_password  # noqa: PLC0415
    from app.models.entities import AttorneyAccount, User  # noqa: PLC0415
    from app.services.gateway.attorney_service import generate_api_key  # noqa: PLC0415

    db = SessionLocal()
    try:
        pw_hash = hash_password(settings.mock_provision_password)

        demo_users = [
            ("large_test_user", "large_test_user@example.com", "super_user"),
            ("admin_test", "admin_test@example.com", "admin"),
            ("attorney_test", "attorney_test@example.com", "attorney"),
            ("attorney_user", "attorney_user@example.com", "attorney"),
        ]

        created_users: dict[str, User] = {}
        for username, email, role in demo_users:
            user = db.scalar(select(User).where(User.username == username))
            if user is None:
                user = User(
                    username=username,
                    email=email,
                    password_hash=pw_hash,
                    role=role,
                )
                db.add(user)
            else:
                # Always sync role and password so env changes take effect
                user.role = role
                user.password_hash = pw_hash
            db.flush()
            created_users[username] = user

        # Ensure each attorney demo user has a linked AttorneyAccount
        attorney_meta = {
            "attorney_test": ("Test Attorney", "Test Law Firm LLC"),
            "attorney_user": ("Attorney User", "Test Law Firm LLC"),
        }
        atty_accts: dict[str, AttorneyAccount] = {}
        for username, (name, firm) in attorney_meta.items():
            atty_user = created_users[username]
            acct = db.scalar(select(AttorneyAccount).where(AttorneyAccount.user_id == atty_user.id))
            if acct is None:
                _, hashed_key = generate_api_key()
                acct = AttorneyAccount(
                    id=uuid.uuid4(),
                    user_id=atty_user.id,
                    name=name,
                    email=atty_user.email,
                    firm_name=firm,
                    api_key_hash=hashed_key,
                    status="active",
                )
                db.add(acct)
            atty_accts[username] = acct
        db.flush()

        # Use attorney_test as the primary account for settlement linking
        atty_acct = atty_accts["attorney_test"]

        # Link every settlement to attorney_test with a sandbox bank account.
        # Uses upsert: if the settlement already has a different attorney's account,
        # reassign it to attorney_test.
        from app.core.crypto import encrypt_token  # noqa: PLC0415
        from app.models.entities import Settlement, SettlementAccount  # noqa: PLC0415

        settlements = db.scalars(select(Settlement)).all()
        for settlement in settlements:
            existing_sa = db.scalar(
                select(SettlementAccount).where(
                    SettlementAccount.settlement_id == settlement.id
                )
            )
            if existing_sa is None:
                db.add(
                    SettlementAccount(
                        id=uuid.uuid4(),
                        attorney_id=atty_acct.id,
                        settlement_id=settlement.id,
                        bank_name="Sandbox Bank",
                        account_ref_enc=encrypt_token(
                            "sandbox-routing:021000021:sandbox-acct:000111222"
                        ),
                        status="active",
                    )
                )
            elif existing_sa.attorney_id != atty_acct.id:
                existing_sa.attorney_id = atty_acct.id
                existing_sa.status = "active"

        db.flush()

        # Seed default questions on ALL managed settlements (idempotent)
        from app.services.settlements.questions_service import seed_default_questions  # noqa: PLC0415
        from app.models.entities import SettlementQuestion  # noqa: PLC0415

        managed_sas = db.scalars(
            select(SettlementAccount).where(SettlementAccount.attorney_id == atty_acct.id)
        ).all()
        for sa in managed_sas:
            has_q = db.scalar(
                select(SettlementQuestion).where(SettlementQuestion.settlement_id == sa.settlement_id)
            )
            if has_q is None:
                seed_default_questions(db, atty_acct, sa.settlement_id)

        # Seed mock balance into large_test_user's PlaidItem if not already set
        from app.models.entities import PlaidItem  # noqa: PLC0415

        test_user = created_users.get("large_test_user")
        if test_user is not None:
            plaid_item = db.scalar(
                select(PlaidItem).where(
                    PlaidItem.user_id == test_user.id,
                    PlaidItem.status == "active",
                )
            )
            if plaid_item is not None and plaid_item.balance_available_cents is None:
                plaid_item.balance_available_cents = 24783  # $247.83
                plaid_item.balance_current_cents = 31247   # $312.47

        db.commit()
        app_logger.info(
            "demo_users_provisioned",
            extra={"request_id": "", "path": "", "method": "", "status_code": 0},
        )
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        app_logger.warning(
            f"demo_user_provisioning_failed: {exc}",
            extra={"request_id": "", "path": "", "method": "", "status_code": 0},
        )
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    _provision_demo_users()
    yield


app = FastAPI(title="PayMe Lite API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:15173",
        "http://127.0.0.1:15173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestIDMiddleware)

app.include_router(auth_router)
app.include_router(me_router)
app.include_router(onboarding_router)
app.include_router(matching_router)
app.include_router(settlement_router)
app.include_router(claims_router)
app.include_router(integrations_router)
app.include_router(admin_router)
app.include_router(autofill_router)
app.include_router(gateway_router)


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.middleware("http")
async def log_requests(request: Request, call_next):
    response = await call_next(request)
    app_logger.info(
        "request_completed",
        extra={
            "request_id": getattr(request.state, "request_id", ""),
            "path": request.url.path,
            "method": request.method,
            "status_code": response.status_code,
        },
    )
    return response
