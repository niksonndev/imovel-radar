from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlmodel import Session, SQLModel

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database import Alert, Listing, User, make_engine  # noqa: E402, F401


@pytest.fixture()
def session() -> Iterator[Session]:
    engine = make_engine(":memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session