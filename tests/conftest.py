import os

os.environ["DATABASE_URL"] = "sqlite:///./test_paper_trading.db"
os.environ["INITIAL_CASH"] = "100000"

import pytest
from fastapi.testclient import TestClient

from quant_trader.api import app
from quant_trader.db import Base, engine


@pytest.fixture(autouse=True)
def clean_database():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client

