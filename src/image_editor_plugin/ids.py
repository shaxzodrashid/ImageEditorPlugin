from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

IdProvider = Callable[[str], str]
TimeProvider = Callable[[], datetime]


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4()}"


def utc_now() -> datetime:
    return datetime.now(UTC)
