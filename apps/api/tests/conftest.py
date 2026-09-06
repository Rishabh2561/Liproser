import os

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["PRIVATE_STORAGE_ROOT"] = "data/private/test"
os.environ["AI_PROVIDER"] = "unconfigured"

import pytest
from fastapi.testclient import TestClient
from liproser.config import get_settings
from liproser.database import Base, engine
from liproser.main import app


@pytest.fixture(autouse=True)
def clean_database():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    get_settings.cache_clear()
    yield


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client
