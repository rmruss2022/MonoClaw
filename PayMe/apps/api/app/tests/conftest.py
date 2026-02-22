import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy import event, text
from sqlalchemy.orm import sessionmaker

from app.core.db import Base, get_db
from app.main import app
from app.models.entities import Settlement, SettlementFeatureIndex

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL", os.getenv("DATABASE_URL", "postgresql+psycopg://payme:payme@localhost:5432/payme")
)
TEST_DB_SCHEMA = os.getenv("TEST_DB_SCHEMA", "payme_test")

engine = create_engine(TEST_DATABASE_URL, future=True)
TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


if TEST_DB_SCHEMA in {"public", "pg_catalog", "information_schema"}:
    raise RuntimeError("Unsafe TEST_DB_SCHEMA value. Refusing to run tests against a system/public schema.")


@event.listens_for(engine, "checkout")
def _set_test_search_path(dbapi_connection, _connection_record, _connection_proxy):
    cursor = dbapi_connection.cursor()
    cursor.execute(f'SET search_path TO "{TEST_DB_SCHEMA}"')
    cursor.close()


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_schema_on_exit():
    yield
    with engine.begin() as conn:
        conn.execute(text(f'DROP SCHEMA IF EXISTS "{TEST_DB_SCHEMA}" CASCADE'))


@pytest.fixture
def db_setup():
    try:
        with engine.begin() as conn:
            conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{TEST_DB_SCHEMA}"'))
            conn.execute(text(f'SET search_path TO "{TEST_DB_SCHEMA}"'))
            Base.metadata.drop_all(bind=conn)
            Base.metadata.create_all(bind=conn)
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
