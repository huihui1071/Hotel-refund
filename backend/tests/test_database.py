from app.db import connect


def test_seeded_schema_has_all_scenarios_and_tools():
    with connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM scenario_fixtures").fetchone()[0] == 12
        assert connection.execute("SELECT COUNT(*) FROM tool_contracts").fetchone()[0] == 33
        assert connection.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 12
        assert connection.execute("SELECT COUNT(*) FROM refunds").fetchone()[0] == 1


def test_expected_write_results_are_not_seeded_as_current_state():
    with connect() as connection:
        refund_ids = {row[0] for row in connection.execute("SELECT refund_id FROM refunds")}
        external_count = connection.execute("SELECT COUNT(*) FROM external_cases").fetchone()[0]
        evidence_count = connection.execute("SELECT COUNT(*) FROM evidence_items").fetchone()[0]
    assert refund_ids == {"RFD-C-001"}
    assert external_count == 0
    assert evidence_count == 0

