import json
from pathlib import Path

import pytest

from app.main import route_agent_message


EVAL_PATH = Path(__file__).resolve().parents[2] / "eval" / "agent-eval-cases.json"
EVAL_CASES = json.loads(EVAL_PATH.read_text(encoding="utf-8"))["cases"]


def test_eval_dataset_has_three_cases_for_every_scenario():
    counts = {scenario_id: 0 for scenario_id in "ABCDEFGHIJKL"}
    for item in EVAL_CASES:
        counts[item["expected_scenario"]] += 1
        assert item["risk_level"].startswith("L")
    assert len(EVAL_CASES) == 36
    assert set(counts.values()) == {3}


@pytest.mark.parametrize("item", EVAL_CASES, ids=[item["id"] for item in EVAL_CASES])
def test_mvp_router_matches_eval_case(item):
    result = route_agent_message(item["message"])
    assert result["scenario_id"] == item["expected_scenario"]
