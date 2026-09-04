from app.db import connect, json_dump
from app.models import ToolContext
from app.tools import ToolRegistry, now_iso


def _session(user_id="USR-A", order_id="ORD-A-001", case_id="CASE-A-001", state="ORDER_CONFIRMED"):
    session_id = "sess-test"
    with connect() as connection:
        connection.execute(
            "INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (session_id, user_id, case_id, order_id, state, json_dump({}), now_iso(), now_iso()),
        )
    return ToolContext(session_id, user_id, state, "trace-test", case_id, order_id, "L1")


def test_read_gateway_blocks_order_outside_authenticated_user():
    context = _session(order_id="ORD-B-001")
    result = ToolRegistry().execute("get_order_detail", {
        "authenticated_user_id": "USR-A", "order_id": "ORD-B-001", "trace_id": "trace-test"
    }, context)
    assert result.ok is False
    assert result.code == "FORBIDDEN_ORDER"


def test_transaction_write_requires_confirmation():
    context = _session(state="CONFIRMATION_REQUIRED")
    result = ToolRegistry().execute("submit_cancellation", {
        "authenticated_user_id": "USR-A", "case_id": "CASE-A-001", "order_id": "ORD-A-001",
        "expected_order_version": 2, "quote_id": "QT-A-001", "confirmation_token": None,
        "idempotency_key": "idem-missing-confirmation", "trace_id": "trace-test",
    }, context)
    assert result.ok is False
    assert result.code == "CONFIRMATION_REQUIRED"


def test_write_idempotency_returns_original_result():
    context = _session(user_id="USR-C", order_id="ORD-C-001", case_id="CASE-C-001", state="TRACKING_REFUND")
    arguments = {
        "case_id": "CASE-C-001", "deadline": "2026-09-07T18:00:00+08:00",
        "action_type": "CHECK_REFUND_SLA", "idempotency_key": "idem-replay", "trace_id": "trace-test",
    }
    registry = ToolRegistry()
    first = registry.execute("schedule_deadline_action", arguments, context)
    second = registry.execute("schedule_deadline_action", arguments, context)
    assert first.ok and second.ok
    assert first.data == second.data
    with connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM scheduled_actions").fetchone()[0] == 1

