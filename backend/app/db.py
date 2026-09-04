from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"
MOCK_ROOT = PROJECT_ROOT / "mock"
CONTRACT_ROOT = PROJECT_ROOT / "contracts"
SCHEMA_PATH = BACKEND_ROOT / "db" / "schema.sql"
DEFAULT_DB_PATH = BACKEND_ROOT / "data" / "qunar_mock.db"


def database_path() -> Path:
    return Path(os.environ.get("QUNAR_MOCK_DB", str(DEFAULT_DB_PATH))).resolve()


def _load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def json_dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def json_load(value: str) -> Any:
    return json.loads(value)


@contextmanager
def connect(path: Optional[Path] = None) -> Iterator[sqlite3.Connection]:
    target = path or database_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(target))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def init_database(path: Optional[Path] = None, reset: bool = False) -> Path:
    target = path or database_path()
    if reset and target.exists():
        target.unlink()
    with connect(target) as connection:
        connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        if connection.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
            _seed(connection)
    return target


def _insert_payload(
    connection: sqlite3.Connection,
    table: str,
    fields: Dict[str, Any],
    payload: Dict[str, Any],
) -> None:
    row = dict(fields)
    row["payload_json"] = json_dump(payload)
    columns = ", ".join(row)
    placeholders = ", ".join("?" for _ in row)
    connection.execute(
        f"INSERT OR REPLACE INTO {table} ({columns}) VALUES ({placeholders})",
        tuple(row.values()),
    )


def _seed(connection: sqlite3.Connection) -> None:
    users = _load_json(MOCK_ROOT / "users.json")["users"]
    for item in users:
        _insert_payload(connection, "users", {
            "user_id": item["user_id"], "display_name": item["display_name"],
            "mobile_masked": item["mobile_masked"], "identity_status": item["identity_status"],
        }, item)

    for item in _load_json(MOCK_ROOT / "hotels.json")["hotels"]:
        _insert_payload(connection, "hotels", {
            "hotel_id": item["hotel_id"], "name": item["name"], "city": item["city"],
            "country": item["country"], "star_level": item.get("star_level"),
        }, item)

    for item in _load_json(MOCK_ROOT / "suppliers.json")["suppliers"]:
        _insert_payload(connection, "suppliers", {
            "supplier_id": item["supplier_id"], "name": item["name"], "type": item["type"],
        }, item)

    for item in _load_json(MOCK_ROOT / "policies.json")["policies"]:
        _insert_payload(connection, "policies", {
            "policy_id": item["policy_id"], "version": item["version"],
            "scenario": item["scenario"], "requires_human": int(item["requires_human"]),
        }, item)

    orders = _load_json(MOCK_ROOT / "orders.json")["orders"]
    for item in orders:
        _insert_payload(connection, "orders", {
            "order_id": item["order_id"], "scenario_id": item["scenario_id"],
            "user_id": item["user_id"], "hotel_id": item["hotel_id"],
            "supplier_id": item["supplier_id"], "policy_id": item["policy_id"],
            "payment_id": item["payment_id"], "refund_id": item.get("refund_id"),
            "status": item["status"], "version": item["version"],
            "check_in": item["check_in"], "check_out": item["check_out"],
            "timezone": item["timezone"], "paid_amount": item["amount"]["paid"],
            "currency": item["amount"]["currency"],
        }, item)

    payment_data = _load_json(MOCK_ROOT / "payments.json")
    for item in payment_data["payments"]:
        _insert_payload(connection, "payments", {
            "payment_id": item["payment_id"], "order_id": item["order_id"],
            "channel": item["channel"], "status": item["status"],
            "amount": item["amount"], "currency": item["currency"],
        }, item)
    for item in payment_data["payment_events"]:
        _insert_payload(connection, "payment_events", {
            "event_id": item["event_id"], "payment_id": item["payment_id"],
            "event_type": item["type"], "occurred_at": item["occurred_at"],
        }, item)

    refund_items = _load_json(MOCK_ROOT / "refunds.json")["refunds"]
    for item in refund_items:
        _catalog_fixture(connection, "refund", item["refund_id"], item.get("fixture_phase", "initial"), item)
        if item.get("fixture_phase", "initial") == "initial":
            _insert_refund(connection, item)

    for item in _load_json(MOCK_ROOT / "cases.json")["cases"]:
        _insert_payload(connection, "cases", {
            "case_id": item["case_id"], "scenario_id": item["scenario_id"],
            "user_id": item["user_id"], "order_id": item["order_id"],
            "conversation_state": item["conversation_state"], "case_status": item["case_status"],
            "risk_level": item["risk_level"], "waiting_for": item["waiting_for"],
        }, item)

    for item in _load_json(MOCK_ROOT / "case-events.json")["events"]:
        _insert_payload(connection, "case_events", {
            "event_id": item["event_id"], "case_id": item["case_id"],
            "event_type": item["event_type"], "actor_type": item["actor_type"],
            "occurred_at": item["occurred_at"], "trace_id": item["trace_id"],
            "from_case_status": item.get("from_case_status"), "to_case_status": item.get("to_case_status"),
            "public_summary": item["public_summary"], "idempotency_key": item.get("idempotency_key"),
        }, item)

    _seed_phased_items(connection, "external-cases.json", "external_cases", "external_case_id")
    _seed_phased_items(connection, "evidence.json", "evidence_items", "evidence_id")

    for item in _load_json(MOCK_ROOT / "alternative-hotels.json")["alternatives"]:
        _insert_payload(connection, "alternative_hotels", {
            "source_order_id": item["source_order_id"], "hotel_id": item["hotel_id"],
            "available": int(item["available"]), "price_difference": item["price_difference"],
        }, item)

    for item in _load_json(MOCK_ROOT / "scenario-fixtures.json")["scenarios"]:
        _insert_payload(connection, "scenario_fixtures", {
            "scenario_id": item["scenario_id"], "title": item["title"],
            "expected_route": item["expected_route"], "expected_case_status": item["expected_case_status"],
        }, item)

    contracts = _load_json(CONTRACT_ROOT / "tool-contracts.json")["tools"]
    for item in contracts:
        _insert_payload(connection, "tool_contracts", {
            "tool_name": item["name"], "mode": item["mode"],
        }, item)

    responses = _load_json(MOCK_ROOT / "tool-response-fixtures.json")["responses"]
    for tool_name, items in responses.items():
        for item in items:
            key = item.get("order_id") or item["fixture_id"]
            if item.get("alternative_hotel_id"):
                key = f"{key}:{item['alternative_hotel_id']}"
            _catalog_fixture(connection, f"tool:{tool_name}", key, "initial", item)


def _seed_phased_items(
    connection: sqlite3.Connection, file_name: str, table: str, key_name: str
) -> None:
    document = _load_json(MOCK_ROOT / file_name)
    list_value = next(value for value in document.values() if isinstance(value, list))
    for item in list_value:
        phase = item.get("fixture_phase", "initial")
        _catalog_fixture(connection, table, item[key_name], phase, item)
        if phase != "initial":
            continue
        if table == "external_cases":
            _insert_external_case(connection, item)
        else:
            _insert_evidence(connection, item)


def _catalog_fixture(connection: sqlite3.Connection, kind: str, key: str, phase: str, item: Dict[str, Any]) -> None:
    connection.execute(
        "INSERT OR REPLACE INTO fixture_catalog VALUES (?, ?, ?, ?)",
        (kind, key, phase, json_dump(item)),
    )


def _insert_refund(connection: sqlite3.Connection, item: Dict[str, Any]) -> None:
    _insert_payload(connection, "refunds", {
        "refund_id": item["refund_id"], "order_id": item["order_id"],
        "payment_id": item["payment_id"], "status": item["status"],
        "amount": item["amount"], "currency": item["currency"],
        "waiting_for": item.get("waiting_for"),
    }, item)


def _insert_external_case(connection: sqlite3.Connection, item: Dict[str, Any]) -> None:
    _insert_payload(connection, "external_cases", {
        "external_case_id": item["external_case_id"], "case_id": item["case_id"],
        "type": item["type"], "status": item["status"], "waiting_for": item["waiting_for"],
        "response_due_at": item.get("response_due_at"),
    }, item)


def _insert_evidence(connection: sqlite3.Connection, item: Dict[str, Any]) -> None:
    _insert_payload(connection, "evidence_items", {
        "evidence_id": item["evidence_id"], "case_id": item["case_id"],
        "type": item["type"], "storage": item["storage"],
        "user_confirmed": int(item["user_confirmed"]),
    }, item)


def payload_row(connection: sqlite3.Connection, table: str, where: str, values: tuple) -> Optional[Dict[str, Any]]:
    row = connection.execute(f"SELECT payload_json FROM {table} WHERE {where}", values).fetchone()
    return json_load(row["payload_json"]) if row else None


def payload_rows(connection: sqlite3.Connection, table: str, where: str = "1=1", values: tuple = ()) -> List[Dict[str, Any]]:
    rows = connection.execute(f"SELECT payload_json FROM {table} WHERE {where}", values).fetchall()
    return [json_load(row["payload_json"]) for row in rows]


def fixture(connection: sqlite3.Connection, kind: str, key: str, phase: Optional[str] = None) -> Optional[Dict[str, Any]]:
    if phase:
        row = connection.execute(
            "SELECT payload_json FROM fixture_catalog WHERE fixture_type=? AND fixture_key=? AND phase=?",
            (kind, key, phase),
        ).fetchone()
    else:
        row = connection.execute(
            "SELECT payload_json FROM fixture_catalog WHERE fixture_type=? AND fixture_key=? ORDER BY phase LIMIT 1",
            (kind, key),
        ).fetchone()
    return json_load(row["payload_json"]) if row else None
