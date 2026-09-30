import os

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["SEED_DEMO_DATA"] = "false"
os.environ["INITIAL_OWNER_PASSWORD"] = "owner-pass-123"
os.environ["JWT_SECRET"] = "test-secret-with-enough-length-for-hs256"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import ParkingSlot, Role, User  # noqa: E402
from app.security import hash_password  # noqa: E402
from app.seed import seed  # noqa: E402

PASSWORD = "secret-pass-1"


@pytest.fixture()
def client():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed(db)
        db.add_all(
            [
                User(username="manager", role=Role.manager, password_hash=hash_password(PASSWORD)),
                User(username="staff", role=Role.staff, password_hash=hash_password(PASSWORD)),
            ]
            + [ParkingSlot(slot_number=f"P{i:02d}") for i in range(1, 11)]
        )
        db.commit()
    with TestClient(app) as c:
        yield c


def login(client: TestClient, username: str, password: str = PASSWORD) -> dict:
    r = client.post("/api/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture()
def owner(client):
    return login(client, "owner", "owner-pass-123")


@pytest.fixture()
def manager(client):
    return login(client, "manager")


@pytest.fixture()
def staff(client):
    return login(client, "staff")
