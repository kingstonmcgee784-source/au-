"""Test configuration.

The database URL must point at a throwaway file before any `app` module is
imported, because the engine is created at import time.
"""

import os
import tempfile
from collections.abc import Iterator
from pathlib import Path

_TEST_DIR = Path(tempfile.mkdtemp(prefix="alpha_research_tests_"))
os.environ["DATABASE_URL"] = f"sqlite:///{(_TEST_DIR / 'test.db').as_posix()}"
os.environ["ENVIRONMENT"] = "test"
os.environ["MARKET_DATA_PROVIDER"] = "none"
os.environ["SEC_USER_AGENT"] = ""
os.environ["AI_PROVIDER"] = "none"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.db.session import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402


@pytest.fixture(scope="session")
def client() -> Iterator[TestClient]:
    # Entering the client runs the lifespan, which applies migrations.
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db(client: TestClient) -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(autouse=True)
def _clean_tables(client: TestClient) -> Iterator[None]:
    yield
    with SessionLocal() as session:
        for table in reversed(Base.metadata.sorted_tables):
            session.execute(table.delete())
        session.commit()


@pytest.fixture
def scratch_dir() -> Path:
    return Path(tempfile.mkdtemp(dir=_TEST_DIR))
