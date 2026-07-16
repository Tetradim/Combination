from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping
from uuid import uuid4


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class EventEnvelope:
    event_id: str
    event_type: str
    source: str
    occurred_at: datetime
    received_at: datetime
    payload: Mapping[str, Any] = field(default_factory=dict)
    account_id: str | None = None
    instrument_id: str | None = None
    order_id: str | None = None
    bracket_id: str | None = None
    causation_id: str | None = None
    correlation_id: str | None = None
    schema_version: int = 1

    def __post_init__(self) -> None:
        if not self.event_id.strip():
            raise ValueError("event_id is required")
        if not self.event_type.strip():
            raise ValueError("event_type is required")
        if not self.source.strip():
            raise ValueError("source is required")
        if self.occurred_at.tzinfo is None or self.received_at.tzinfo is None:
            raise ValueError("event timestamps must be timezone-aware")
        if self.schema_version <= 0:
            raise ValueError("schema_version must be positive")

    @classmethod
    def create(
        cls,
        *,
        event_type: str,
        source: str,
        payload: Mapping[str, Any] | None = None,
        occurred_at: datetime | None = None,
        account_id: str | None = None,
        instrument_id: str | None = None,
        order_id: str | None = None,
        bracket_id: str | None = None,
        causation_id: str | None = None,
        correlation_id: str | None = None,
    ) -> "EventEnvelope":
        now = utc_now()
        return cls(
            event_id=str(uuid4()),
            event_type=event_type,
            source=source,
            occurred_at=occurred_at or now,
            received_at=now,
            payload=payload or {},
            account_id=account_id,
            instrument_id=instrument_id,
            order_id=order_id,
            bracket_id=bracket_id,
            causation_id=causation_id,
            correlation_id=correlation_id,
        )

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["occurred_at"] = self.occurred_at.isoformat()
        value["received_at"] = self.received_at.isoformat()
        value["payload"] = dict(self.payload)
        return value
