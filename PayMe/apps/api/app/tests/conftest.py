import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

from app.core.db import Base, get_db
from app.main import app
from app.models.entities import Settlement, SettlementFeatureIndex

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL", os.getenv("DATABASE_URL", "postgresql+psycopg://payme:payme@localhost:5432/payme")
)

engine = create_engine(TEST_DATABASE_URL, future=True)
TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


@pytest.fixture
def db_setup():
    try:
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
    except OperationalError:
        pytest.skip("Postgres test database is unavailable. Start docker compose db or set TEST_DATABASE_URL.")
    db = TestingSessionLocal()
    try:
        settlement = Settlement(
            id=uuid.uuid4(),
            title="Amazon Prime Settlement",
            status="open",
            eligibility_predicates={"required_features": ["merchant:amazon"], "states": ["NY", "CA"]},
            summary_text="Prime settlement",
            eligibility_text="Amazon purchases in supported states",
            covered_brands=["amazon"],
            tags=["consumer"],
        )
        db.add(settlement)
        db.flush()
        db.add(
            SettlementFeatureIndex(
                settlement_id=settlement.id,
                feature_key="merchant:amazon",
                feature_kind="required",
            )
        )
        db.commit()
    finally:
        db.close()
    yield


@pytest.fixture
def client(db_setup):
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
