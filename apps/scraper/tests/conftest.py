from collections.abc import Iterator

import pytest
from sqlmodel import Session, SQLModel

from database.db import make_engine
from database.models import Alert, Listing, User  # noqa: E402, F401


@pytest.fixture()
def session() -> Iterator[Session]:
    engine = make_engine(":memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session