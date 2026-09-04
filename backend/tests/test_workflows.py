import pytest

from app.workflow import ScenarioWorkflow


EXPECTED = {
    "A": "REFUND_INITIATED", "B": "REFUND_INITIATED", "C": "AWAITING_PAYMENT",
    "D": "RECOVERY_IN_PROGRESS", "E": "RECOVERED", "F": "REFUND_INITIATED",
    "G": "MANUAL_REVIEW", "H": "MANUAL_REVIEW", "I": "CHANGED",
    "J": "MANUAL_REVIEW", "K": "AWAITING_SPECIALIST", "L": "AWAITING_SPECIALIST",
}


@pytest.mark.parametrize("scenario_id", list("ABCDEFGHIJKL"))
def test_scenario_reaches_contract_status(scenario_id):
    result = ScenarioWorkflow().run(scenario_id)
    assert result.case_status == EXPECTED[scenario_id]
    assert all(result.assertions.values())
    assert len(result.steps) >= len(result.tool_calls)

