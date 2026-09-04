from fastapi.testclient import TestClient

from app.main import app


def test_health_exposes_mock_scope():
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json()["mock"] is True
    assert response.json()["scenarios"] == 12
    assert response.json()["tools"] == 33


def test_workflow_endpoint_returns_traceable_result():
    response = TestClient(app).post("/api/workflows/A/run", json={"reset_database": True})
    assert response.status_code == 200
    result = response.json()["result"]
    assert result["case_status"] == "REFUND_INITIATED"
    assert "submit_cancellation" in result["tool_calls"]
    detail = TestClient(app).get(f"/api/workflow-runs/{result['run_id']}")
    assert detail.status_code == 200
    assert len(detail.json()["steps"]) > 0


def test_agent_message_routes_and_runs_workflow():
    response = TestClient(app).post(
        "/api/agent/message",
        json={"message": "酒店说这个订单不能退，可以帮我协商吗？", "reset_database": True},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["routing"]["scenario_id"] == "F"
    assert payload["routing"]["router"] == "DETERMINISTIC_MVP_ROUTER"
    assert payload["result"]["case_status"] == "REFUND_INITIATED"


def test_agent_message_understands_refund_not_received_variant():
    response = TestClient(app).post(
        "/api/agent/message",
        json={"message": "退款已经提交三天了，怎么还没有到账？", "reset_database": True},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["routing"]["scenario_id"] == "C"
    assert payload["result"]["case_status"] == "AWAITING_PAYMENT"
