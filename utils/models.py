from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Alert:
    user_id: int
    created_at: datetime
    id: Optional[int] = None
    alert_name: Optional[str] = None
    min_price: Optional[int] = None
    max_price: Optional[int] = None
    neighbourhoods: list[str] = field(default_factory=list)
    active: bool = True
