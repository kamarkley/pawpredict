from datetime import date, timedelta

from sqlalchemy.dialects.postgresql import ENUM

import app.routes.dogs as dog_routes
from app.models.dog import Dog
from app.schemas.dog import DogCreate
from app.security import AuthUser


class StubSession:
    def __init__(self):
        self.calls = []

    def add(self, value):
        self.calls.append(("add", value))

    def flush(self):
        self.calls.append(("flush", None))

    def commit(self):
        self.calls.append(("commit", None))

    def refresh(self, value):
        self.calls.append(("refresh", value))


def test_create_dog_flushes_parent_before_seeding(monkeypatch):
    db = StubSession()

    user = AuthUser(
        id=__import__("uuid").uuid4(),
        email="owner@example.com",
    )

    payload = DogCreate(
        name="Test Dog",
        birth_date=date.today() - timedelta(days=100),
        sex="MALE",
        neutered=False,
    )

    def fake_seed_new_dog(session, dog, now):
        session.calls.append(("seed", dog))

    monkeypatch.setattr(
        dog_routes,
        "seed_new_dog",
        fake_seed_new_dog,
    )

    dog = dog_routes.create_dog(
        data=payload,
        db=db,
        user=user,
    )

    operation_order = [
        call[0]
        for call in db.calls
    ]

    assert operation_order == [
        "add",
        "flush",
        "seed",
        "commit",
        "refresh",
    ]

    assert dog.owner_user_id == user.id
    assert dog.name == "Test Dog"
    assert dog.sex == "MALE"


def test_dog_sex_uses_existing_postgres_enum():
    sex_type = Dog.__table__.c.sex.type

    assert isinstance(sex_type, ENUM)
    assert sex_type.name == "dog_sex"
    assert sex_type.enums == [
        "MALE",
        "FEMALE",
        "UNKNOWN",
    ]