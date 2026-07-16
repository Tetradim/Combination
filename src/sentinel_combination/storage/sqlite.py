from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterator

from sentinel_combination.domain.enums import OrderStatus, OrderType, Side
from sentinel_combination.domain.events import EventEnvelope
from sentinel_combination.domain.orders import OrderIntent, OrderLifecycle
from sentinel_combination.domain.positions import Position


def _json_default(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "value"):
        return value.value
    raise TypeError(f"cannot encode {type(value)!r}")


def _dumps(value: Any) -> str:
    return json.dumps(
        value,
        default=_json_default,
        sort_keys=True,
        separators=(",", ":"),
    )


def _parse_datetime(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


class SQLiteTransaction:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def claim_external_event(
        self,
        *,
        source: str,
        external_event_id: str,
    ) -> bool:
        try:
            self.connection.execute(
                """
                INSERT INTO processed_external_events(
                    source,
                    external_event_id,
                    processed_at
                ) VALUES (?, ?, ?)
                """,
                (
                    source,
                    external_event_id,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
        except sqlite3.IntegrityError:
            return False
        return True

    def claim_execution(
        self,
        *,
        source: str,
        execution_id: str,
    ) -> bool:
        try:
            self.connection.execute(
                """
                INSERT INTO processed_executions(
                    source,
                    execution_id,
                    processed_at
                ) VALUES (?, ?, ?)
                """,
                (
                    source,
                    execution_id,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
        except sqlite3.IntegrityError:
            return False
        return True

    def append_event(self, event: EventEnvelope) -> None:
        self.connection.execute(
            """
            INSERT INTO events(
                event_id,
                event_type,
                source,
                occurred_at,
                received_at,
                account_id,
                instrument_id,
                order_id,
                bracket_id,
                causation_id,
                correlation_id,
                schema_version,
                payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.event_id,
                event.event_type,
                event.source,
                event.occurred_at.isoformat(),
                event.received_at.isoformat(),
                event.account_id,
                event.instrument_id,
                event.order_id,
                event.bracket_id,
                event.causation_id,
                event.correlation_id,
                event.schema_version,
                _dumps(dict(event.payload)),
            ),
        )

    def save_order(self, lifecycle: OrderLifecycle) -> None:
        payload = {
            "intent": asdict(lifecycle.intent),
            "status": lifecycle.status.value,
            "filled_quantity": str(lifecycle.filled_quantity),
            "average_fill_price": (
                str(lifecycle.average_fill_price)
                if lifecycle.average_fill_price is not None
                else None
            ),
            "broker_order_id": lifecycle.broker_order_id,
            "reject_reason": lifecycle.reject_reason,
            "last_update_at": (
                lifecycle.last_update_at.isoformat()
                if lifecycle.last_update_at is not None
                else None
            ),
        }
        self.connection.execute(
            """
            INSERT INTO orders(client_order_id, data_json, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(client_order_id) DO UPDATE SET
                data_json = excluded.data_json,
                updated_at = excluded.updated_at
            """,
            (
                lifecycle.intent.client_order_id,
                _dumps(payload),
                datetime.now(timezone.utc).isoformat(),
            ),
        )

    def get_order(self, client_order_id: str) -> OrderLifecycle | None:
        row = self.connection.execute(
            "SELECT data_json FROM orders WHERE client_order_id = ?",
            (client_order_id,),
        ).fetchone()
        if row is None:
            return None
        payload = json.loads(row[0])
        item = payload["intent"]
        intent = OrderIntent(
            client_order_id=item["client_order_id"],
            account_id=item["account_id"],
            instrument_id=item["instrument_id"],
            side=Side(item["side"]),
            quantity=Decimal(item["quantity"]),
            order_type=OrderType(item["order_type"]),
            strategy_id=item["strategy_id"],
            created_at=datetime.fromisoformat(item["created_at"]),
            limit_price=(
                Decimal(item["limit_price"])
                if item["limit_price"] is not None
                else None
            ),
            stop_price=(
                Decimal(item["stop_price"])
                if item["stop_price"] is not None
                else None
            ),
            reduce_only=bool(item["reduce_only"]),
            bracket_id=item["bracket_id"],
            parent_order_id=item["parent_order_id"],
            oca_group_id=item["oca_group_id"],
        )
        return OrderLifecycle(
            intent=intent,
            status=OrderStatus(payload["status"]),
            filled_quantity=Decimal(payload["filled_quantity"]),
            average_fill_price=(
                Decimal(payload["average_fill_price"])
                if payload["average_fill_price"] is not None
                else None
            ),
            broker_order_id=payload["broker_order_id"],
            reject_reason=payload["reject_reason"],
            last_update_at=_parse_datetime(payload["last_update_at"]),
        )

    def save_position(self, position: Position) -> None:
        payload = {
            "account_id": position.account_id,
            "instrument_id": position.instrument_id,
            "quantity": str(position.quantity),
            "average_entry_price": str(position.average_entry_price),
            "realized_pnl": str(position.realized_pnl),
            "fees_paid": str(position.fees_paid),
            "updated_at": (
                position.updated_at.isoformat()
                if position.updated_at is not None
                else None
            ),
        }
        self.connection.execute(
            """
            INSERT INTO positions(
                account_id,
                instrument_id,
                data_json,
                updated_at
            ) VALUES (?, ?, ?, ?)
            ON CONFLICT(account_id, instrument_id) DO UPDATE SET
                data_json = excluded.data_json,
                updated_at = excluded.updated_at
            """,
            (
                position.account_id,
                position.instrument_id,
                _dumps(payload),
                datetime.now(timezone.utc).isoformat(),
            ),
        )

    def get_position(
        self,
        *,
        account_id: str,
        instrument_id: str,
    ) -> Position | None:
        row = self.connection.execute(
            """
            SELECT data_json
            FROM positions
            WHERE account_id = ? AND instrument_id = ?
            """,
            (account_id, instrument_id),
        ).fetchone()
        if row is None:
            return None
        payload = json.loads(row[0])
        return Position(
            account_id=payload["account_id"],
            instrument_id=payload["instrument_id"],
            quantity=Decimal(payload["quantity"]),
            average_entry_price=Decimal(payload["average_entry_price"]),
            realized_pnl=Decimal(payload["realized_pnl"]),
            fees_paid=Decimal(payload["fees_paid"]),
            updated_at=_parse_datetime(payload["updated_at"]),
        )


class SQLiteStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = FULL")
        return connection

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS metadata(
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS processed_external_events(
                    source TEXT NOT NULL,
                    external_event_id TEXT NOT NULL,
                    processed_at TEXT NOT NULL,
                    PRIMARY KEY(source, external_event_id)
                );

                CREATE TABLE IF NOT EXISTS processed_executions(
                    source TEXT NOT NULL,
                    execution_id TEXT NOT NULL,
                    processed_at TEXT NOT NULL,
                    PRIMARY KEY(source, execution_id)
                );

                CREATE TABLE IF NOT EXISTS events(
                    event_id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    source TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    received_at TEXT NOT NULL,
                    account_id TEXT,
                    instrument_id TEXT,
                    order_id TEXT,
                    bracket_id TEXT,
                    causation_id TEXT,
                    correlation_id TEXT,
                    schema_version INTEGER NOT NULL,
                    payload_json TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_events_order
                    ON events(order_id, occurred_at);

                CREATE INDEX IF NOT EXISTS idx_events_account
                    ON events(account_id, occurred_at);

                CREATE TABLE IF NOT EXISTS orders(
                    client_order_id TEXT PRIMARY KEY,
                    data_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS positions(
                    account_id TEXT NOT NULL,
                    instrument_id TEXT NOT NULL,
                    data_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(account_id, instrument_id)
                );

                CREATE TABLE IF NOT EXISTS kill_switch(
                    singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
                    level TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                INSERT INTO metadata(key, value)
                VALUES ('schema_version', '1')
                ON CONFLICT(key) DO NOTHING;

                INSERT INTO kill_switch(
                    singleton,
                    level,
                    reason,
                    updated_at
                )
                VALUES (1, 'clear', '', CURRENT_TIMESTAMP)
                ON CONFLICT(singleton) DO NOTHING;
                """
            )

    @contextmanager
    def transaction(self) -> Iterator[SQLiteTransaction]:
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            transaction = SQLiteTransaction(connection)
            yield transaction
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def healthcheck(self) -> bool:
        try:
            with self._connect() as connection:
                row = connection.execute(
                    """
                    SELECT value
                    FROM metadata
                    WHERE key = 'schema_version'
                    """
                ).fetchone()
                return row is not None and row[0] == "1"
        except sqlite3.Error:
            return False
