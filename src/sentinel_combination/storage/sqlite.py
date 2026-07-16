from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

from sentinel_combination.domain.enums import KillSwitchLevel, OrderStatus, OrderType, Side
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
    return json.dumps(value, default=_json_default, sort_keys=True, separators=(",", ":"))


def _parse_datetime(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _order_from_payload(payload: Mapping[str, Any]) -> OrderLifecycle:
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
        limit_price=Decimal(item["limit_price"]) if item.get("limit_price") is not None else None,
        stop_price=Decimal(item["stop_price"]) if item.get("stop_price") is not None else None,
        reduce_only=bool(item.get("reduce_only", False)),
        bracket_id=item.get("bracket_id"),
        parent_order_id=item.get("parent_order_id"),
        oca_group_id=item.get("oca_group_id"),
        time_in_force=item.get("time_in_force", "GTC"),
        metadata=dict(item.get("metadata") or {}),
    )
    return OrderLifecycle(
        intent=intent,
        status=OrderStatus(payload["status"]),
        filled_quantity=Decimal(payload["filled_quantity"]),
        average_fill_price=(
            Decimal(payload["average_fill_price"])
            if payload.get("average_fill_price") is not None
            else None
        ),
        broker_order_id=payload.get("broker_order_id"),
        reject_reason=payload.get("reject_reason"),
        last_update_at=_parse_datetime(payload.get("last_update_at")),
    )


def _order_payload(lifecycle: OrderLifecycle) -> dict[str, Any]:
    return {
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


class SQLiteTransaction:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def claim_external_event(self, *, source: str, external_event_id: str) -> bool:
        try:
            self.connection.execute(
                "INSERT INTO processed_external_events(source, external_event_id, processed_at) VALUES (?, ?, ?)",
                (source, external_event_id, datetime.now(timezone.utc).isoformat()),
            )
        except sqlite3.IntegrityError:
            return False
        return True

    def claim_execution(self, *, source: str, execution_id: str) -> bool:
        try:
            self.connection.execute(
                "INSERT INTO processed_executions(source, execution_id, processed_at) VALUES (?, ?, ?)",
                (source, execution_id, datetime.now(timezone.utc).isoformat()),
            )
        except sqlite3.IntegrityError:
            return False
        return True

    def append_event(self, event: EventEnvelope) -> None:
        previous = self.connection.execute(
            "SELECT event_hash FROM events ORDER BY sequence DESC LIMIT 1"
        ).fetchone()
        previous_hash = previous[0] if previous else "0" * 64
        payload_json = _dumps(dict(event.payload))
        canonical = _dumps(
            {
                "event_id": event.event_id,
                "event_type": event.event_type,
                "source": event.source,
                "occurred_at": event.occurred_at.isoformat(),
                "received_at": event.received_at.isoformat(),
                "account_id": event.account_id,
                "instrument_id": event.instrument_id,
                "order_id": event.order_id,
                "bracket_id": event.bracket_id,
                "causation_id": event.causation_id,
                "correlation_id": event.correlation_id,
                "schema_version": event.schema_version,
                "payload_json": payload_json,
                "previous_hash": previous_hash,
            }
        )
        event_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        self.connection.execute(
            """
            INSERT INTO events(
                event_id, event_type, source, occurred_at, received_at,
                account_id, instrument_id, order_id, bracket_id,
                causation_id, correlation_id, schema_version, payload_json,
                previous_hash, event_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                payload_json,
                previous_hash,
                event_hash,
            ),
        )

    def save_order(self, lifecycle: OrderLifecycle, *, broker_name: str | None = None) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self.connection.execute(
            """
            INSERT INTO orders(client_order_id, broker_name, data_json, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(client_order_id) DO UPDATE SET
                broker_name = COALESCE(excluded.broker_name, orders.broker_name),
                data_json = excluded.data_json,
                updated_at = excluded.updated_at
            """,
            (lifecycle.intent.client_order_id, broker_name, _dumps(_order_payload(lifecycle)), now),
        )

    def get_order(self, client_order_id: str) -> OrderLifecycle | None:
        row = self.connection.execute(
            "SELECT data_json FROM orders WHERE client_order_id = ?", (client_order_id,)
        ).fetchone()
        return _order_from_payload(json.loads(row[0])) if row else None

    def list_orders(
        self,
        *,
        account_id: str | None = None,
        broker_name: str | None = None,
        include_terminal: bool = True,
    ) -> list[OrderLifecycle]:
        rows = self.connection.execute(
            "SELECT broker_name, data_json FROM orders ORDER BY updated_at"
        ).fetchall()
        result: list[OrderLifecycle] = []
        for row in rows:
            lifecycle = _order_from_payload(json.loads(row[1]))
            if account_id and lifecycle.intent.account_id != account_id:
                continue
            if broker_name and row[0] != broker_name:
                continue
            if not include_terminal and lifecycle.status.terminal:
                continue
            result.append(lifecycle)
        return result

    def broker_for_order(self, client_order_id: str) -> str | None:
        row = self.connection.execute(
            "SELECT broker_name FROM orders WHERE client_order_id = ?", (client_order_id,)
        ).fetchone()
        return row[0] if row else None

    def save_position(self, position: Position) -> None:
        payload = {
            "account_id": position.account_id,
            "instrument_id": position.instrument_id,
            "quantity": str(position.quantity),
            "average_entry_price": str(position.average_entry_price),
            "realized_pnl": str(position.realized_pnl),
            "fees_paid": str(position.fees_paid),
            "updated_at": position.updated_at.isoformat() if position.updated_at else None,
        }
        self.connection.execute(
            """
            INSERT INTO positions(account_id, instrument_id, data_json, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(account_id, instrument_id) DO UPDATE SET
                data_json = excluded.data_json, updated_at = excluded.updated_at
            """,
            (
                position.account_id,
                position.instrument_id,
                _dumps(payload),
                datetime.now(timezone.utc).isoformat(),
            ),
        )

    def get_position(self, *, account_id: str, instrument_id: str) -> Position | None:
        row = self.connection.execute(
            "SELECT data_json FROM positions WHERE account_id = ? AND instrument_id = ?",
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
            updated_at=_parse_datetime(payload.get("updated_at")),
        )

    def list_positions(self, *, account_id: str | None = None) -> list[Position]:
        rows = self.connection.execute("SELECT data_json FROM positions ORDER BY account_id, instrument_id").fetchall()
        result = []
        for row in rows:
            payload = json.loads(row[0])
            if account_id and payload["account_id"] != account_id:
                continue
            result.append(
                Position(
                    account_id=payload["account_id"],
                    instrument_id=payload["instrument_id"],
                    quantity=Decimal(payload["quantity"]),
                    average_entry_price=Decimal(payload["average_entry_price"]),
                    realized_pnl=Decimal(payload["realized_pnl"]),
                    fees_paid=Decimal(payload["fees_paid"]),
                    updated_at=_parse_datetime(payload.get("updated_at")),
                )
            )
        return result

    def save_bracket(self, bracket_id: str, payload: Mapping[str, Any], status: str) -> None:
        self.connection.execute(
            """
            INSERT INTO brackets(bracket_id, status, data_json, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(bracket_id) DO UPDATE SET
                status = excluded.status, data_json = excluded.data_json,
                updated_at = excluded.updated_at
            """,
            (bracket_id, status, _dumps(dict(payload)), datetime.now(timezone.utc).isoformat()),
        )

    def get_bracket(self, bracket_id: str) -> dict[str, Any] | None:
        row = self.connection.execute(
            "SELECT status, data_json FROM brackets WHERE bracket_id = ?", (bracket_id,)
        ).fetchone()
        if not row:
            return None
        payload = json.loads(row[1])
        payload["status"] = row[0]
        return payload

    def list_brackets(self, *, status: str | None = None) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT bracket_id, status, data_json FROM brackets ORDER BY updated_at"
        ).fetchall()
        result = []
        for bracket_id, bracket_status, data_json in rows:
            if status and status != bracket_status:
                continue
            payload = json.loads(data_json)
            payload["bracket_id"] = bracket_id
            payload["status"] = bracket_status
            result.append(payload)
        return result

    def set_kill_switch(self, level: KillSwitchLevel, reason: str) -> None:
        if level is not KillSwitchLevel.CLEAR and not reason.strip():
            raise ValueError("kill-switch reason is required")
        self.connection.execute(
            "UPDATE kill_switch SET level = ?, reason = ?, updated_at = ? WHERE singleton = 1",
            (level.value, reason, datetime.now(timezone.utc).isoformat()),
        )

    def get_kill_switch(self) -> tuple[KillSwitchLevel, str, datetime]:
        row = self.connection.execute(
            "SELECT level, reason, updated_at FROM kill_switch WHERE singleton = 1"
        ).fetchone()
        if not row:
            raise RuntimeError("kill switch row is missing")
        return KillSwitchLevel(row[0]), str(row[1]), datetime.fromisoformat(row[2])

    def save_reconciliation(
        self,
        *,
        broker_name: str,
        account_id: str,
        positions_match: bool,
        orders_match: bool,
        details: Mapping[str, Any],
    ) -> None:
        self.connection.execute(
            """
            INSERT INTO reconciliations(
                broker_name, account_id, positions_match, orders_match,
                details_json, checked_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(broker_name, account_id) DO UPDATE SET
                positions_match = excluded.positions_match,
                orders_match = excluded.orders_match,
                details_json = excluded.details_json,
                checked_at = excluded.checked_at
            """,
            (
                broker_name,
                account_id,
                int(positions_match),
                int(orders_match),
                _dumps(dict(details)),
                datetime.now(timezone.utc).isoformat(),
            ),
        )

    def get_reconciliation(self, broker_name: str, account_id: str) -> dict[str, Any] | None:
        row = self.connection.execute(
            "SELECT positions_match, orders_match, details_json, checked_at FROM reconciliations WHERE broker_name = ? AND account_id = ?",
            (broker_name, account_id),
        ).fetchone()
        if not row:
            return None
        return {
            "positions_match": bool(row[0]),
            "orders_match": bool(row[1]),
            "details": json.loads(row[2]),
            "checked_at": row[3],
        }


class SQLiteStore:
    SCHEMA_VERSION = "3"

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
                CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS processed_external_events(
                    source TEXT NOT NULL, external_event_id TEXT NOT NULL,
                    processed_at TEXT NOT NULL, PRIMARY KEY(source, external_event_id)
                );
                CREATE TABLE IF NOT EXISTS processed_executions(
                    source TEXT NOT NULL, execution_id TEXT NOT NULL,
                    processed_at TEXT NOT NULL, PRIMARY KEY(source, execution_id)
                );
                CREATE TABLE IF NOT EXISTS events(
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT UNIQUE NOT NULL, event_type TEXT NOT NULL,
                    source TEXT NOT NULL, occurred_at TEXT NOT NULL,
                    received_at TEXT NOT NULL, account_id TEXT,
                    instrument_id TEXT, order_id TEXT, bracket_id TEXT,
                    causation_id TEXT, correlation_id TEXT,
                    schema_version INTEGER NOT NULL, payload_json TEXT NOT NULL,
                    previous_hash TEXT NOT NULL, event_hash TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_events_order ON events(order_id, occurred_at);
                CREATE INDEX IF NOT EXISTS idx_events_account ON events(account_id, occurred_at);
                CREATE TABLE IF NOT EXISTS orders(
                    client_order_id TEXT PRIMARY KEY, broker_name TEXT,
                    data_json TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS positions(
                    account_id TEXT NOT NULL, instrument_id TEXT NOT NULL,
                    data_json TEXT NOT NULL, updated_at TEXT NOT NULL,
                    PRIMARY KEY(account_id, instrument_id)
                );
                CREATE TABLE IF NOT EXISTS brackets(
                    bracket_id TEXT PRIMARY KEY, status TEXT NOT NULL,
                    data_json TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS reconciliations(
                    broker_name TEXT NOT NULL, account_id TEXT NOT NULL,
                    positions_match INTEGER NOT NULL, orders_match INTEGER NOT NULL,
                    details_json TEXT NOT NULL, checked_at TEXT NOT NULL,
                    PRIMARY KEY(broker_name, account_id)
                );
                CREATE TABLE IF NOT EXISTS kill_switch(
                    singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
                    level TEXT NOT NULL, reason TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                INSERT INTO kill_switch(singleton, level, reason, updated_at)
                VALUES (1, 'clear', '', CURRENT_TIMESTAMP)
                ON CONFLICT(singleton) DO NOTHING;
                """
            )
            columns = {row[1] for row in connection.execute("PRAGMA table_info(orders)")}
            if "broker_name" not in columns:
                connection.execute("ALTER TABLE orders ADD COLUMN broker_name TEXT")
            connection.execute(
                "INSERT INTO metadata(key, value) VALUES ('schema_version', ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (self.SCHEMA_VERSION,),
            )

    @contextmanager
    def transaction(self) -> Iterator[SQLiteTransaction]:
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield SQLiteTransaction(connection)
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
                    "SELECT value FROM metadata WHERE key = 'schema_version'"
                ).fetchone()
                return bool(row and row[0] == self.SCHEMA_VERSION and connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok")
        except sqlite3.Error:
            return False

    def verify_audit_chain(self) -> bool:
        try:
            with self._connect() as connection:
                rows = connection.execute(
                    """
                    SELECT event_id, event_type, source, occurred_at, received_at,
                           account_id, instrument_id, order_id, bracket_id,
                           causation_id, correlation_id, schema_version,
                           payload_json, previous_hash, event_hash
                    FROM events ORDER BY sequence
                    """
                ).fetchall()
        except sqlite3.Error:
            return False
        previous = "0" * 64
        for row in rows:
            if row[13] != previous:
                return False
            canonical = _dumps(
                {
                    "event_id": row[0],
                    "event_type": row[1],
                    "source": row[2],
                    "occurred_at": row[3],
                    "received_at": row[4],
                    "account_id": row[5],
                    "instrument_id": row[6],
                    "order_id": row[7],
                    "bracket_id": row[8],
                    "causation_id": row[9],
                    "correlation_id": row[10],
                    "schema_version": row[11],
                    "payload_json": row[12],
                    "previous_hash": row[13],
                }
            )
            expected = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
            if expected != row[14]:
                return False
            previous = row[14]
        return True

    def list_events(self, *, limit: int = 200) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT sequence, event_id, event_type, source, occurred_at, account_id, instrument_id, order_id, bracket_id, payload_json, event_hash FROM events ORDER BY sequence DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {
                "sequence": row[0],
                "event_id": row[1],
                "event_type": row[2],
                "source": row[3],
                "occurred_at": row[4],
                "account_id": row[5],
                "instrument_id": row[6],
                "order_id": row[7],
                "bracket_id": row[8],
                "payload": json.loads(row[9]),
                "event_hash": row[10],
            }
            for row in rows
        ]
