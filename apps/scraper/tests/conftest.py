from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlmodel import Session, SQLModel

from database import Alert, Listing, User, make_engine  # noqa: F401


@pytest.fixture()
def session() -> Iterator[Session]:
    engine = make_engine(":memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session