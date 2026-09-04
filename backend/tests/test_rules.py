from app.db import connect, payload_row
from app.rules import payment_interpretation, refund_quote


def _order_and_policy(order_id):
    with connect() as connection:
        order = payload_row(connection, "orders", "order_id=?", (order_id,))
        policy = payload_row(connection, "policies", "policy_id=?", (order["policy_id"],))
    return order, policy


def test_free_cancel_quote_is_full_refund():
    order, policy = _order_and_policy("ORD-A-001")
    quote = refund_quote(order, policy)
    assert quote["refund_amount"] == 688
    assert quote["cancellation_fee"] == 0


def test_tiered_cancel_quote_uses_booking_policy_time_window():
    order, policy = _order_and_policy("ORD-B-001")
    quote = refund_quote(order, policy)
    assert quote["refund_amount"] == 600
    assert quote["cancellation_fee"] == 600


def test_preauthorization_hold_is_not_duplicate_capture():
    result = payment_interpretation([
        {"type": "CAPTURE", "amount": 1600},
        {"type": "PREAUTHORIZATION_HOLD", "amount": 500},
    ])
    assert result == {
        "captured_amount": 1600,
        "preauthorization_hold": 500,
        "duplicate_capture": False,
        "hold_is_duplicate_charge": False,
    }

