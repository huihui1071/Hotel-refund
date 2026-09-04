from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional, Tuple

from . import rules
from .db import connect, init_database, json_dump, json_load, payload_row
from .models import ToolContext, WorkflowResult, WorkflowStep
from .tools import DEMO_NOW, ToolRegistry, now_iso


TOOL_STATES = {
    "list_user_orders": "INTENT_READY",
    "get_order_detail": "ORDER_CONFIRMED",
    "get_policy_snapshot": "ORDER_CONFIRMED",
    "list_after_sale_events": "FACTS_REQUIRED",
    "calculate_refund_quote": "DECISION_READY",
    "validate_action_permission": "DECISION_READY",
    "submit_cancellation": "CONFIRMATION_REQUIRED",
    "get_refund_status": "TRACKING_REFUND",
    "get_payment_events": "TRACKING_REFUND",
    "schedule_deadline_action": "TRACKING_REFUND",
    "create_payment_investigation": "WAITING_EXTERNAL",
    "verify_fulfillment_issue": "ORDER_CONFIRMED",
    "get_alternative_hotels": "DECISION_READY",
    "get_guarantee_quote": "DECISION_READY",
    "reserve_mock_alternative": "OPTION_PRESENTED",
    "create_human_handoff": "OPTION_PRESENTED",
    "get_handoff_status": "ESCALATED",
    "confirm_recovery_outcome": "ESCALATED",
    "build_supplier_case_draft": "FACTS_REQUIRED",
    "create_supplier_case": "CONFIRMATION_REQUIRED",
    "get_supplier_case": "WAITING_EXTERNAL",
    "accept_supplier_offer": "OPTION_PRESENTED",
    "submit_evidence_metadata": "FACTS_REQUIRED",
    "extract_evidence_fields": "FACTS_REQUIRED",
    "create_exception_review": "DECISION_READY",
    "create_service_dispute_case": "DECISION_READY",
    "get_change_quote": "DECISION_READY",
    "submit_order_change": "CONFIRMATION_REQUIRED",
    "create_finance_case": "DECISION_READY",
    "get_responsibility_chain": "DECISION_READY",
    "get_group_order_breakdown": "FACTS_REQUIRED",
    "get_partial_cancel_quote": "DECISION_READY",
}


class ScenarioWorkflow:
    def __init__(self, registry: Optional[ToolRegistry] = None):
        self.registry = registry or ToolRegistry()

    def run(self, scenario_id: str) -> WorkflowResult:
        init_database()
        scenario, order, case = self._load_scenario(scenario_id.upper())
        route = scenario["expected_route"]
        run_id = f"run_{uuid.uuid4().hex}"
        session_id = f"sess_{uuid.uuid4().hex}"
        trace_id = f"trace_{uuid.uuid4().hex}"
        timestamp = now_iso()
        state = "START"
        facts: Dict[str, Any] = {}
        steps: List[WorkflowStep] = []
        tool_calls: List[str] = []

        with connect() as connection:
            connection.execute(
                "INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (session_id, case["user_id"], case["case_id"], order["order_id"], state,
                 json_dump({"scenario_id": scenario_id, "route": route}), timestamp, timestamp),
            )
            connection.execute(
                "INSERT INTO workflow_runs VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL)",
                (run_id, scenario_id, session_id, case["case_id"], route, "RUNNING", timestamp),
            )

        state = self._record_node(run_id, steps, "INTENT_AND_ROUTE", "RULE_ENGINE", state, "INTENT_READY", {
            "entry_message": scenario["entry_message"], "route": route, "risk_level": scenario["risk_level"]
        })
        context = ToolContext(session_id, case["user_id"], state, trace_id, case["case_id"], order["order_id"], scenario["risk_level"])

        sequence = list(scenario["required_tools"])
        if scenario_id == "H":
            index = sequence.index("submit_evidence_metadata")
            sequence.insert(index + 1, "submit_evidence_metadata")

        for occurrence, tool_name in enumerate(sequence):
            desired_state = self._state_for(scenario_id, tool_name)
            if state != desired_state:
                state = self._record_node(run_id, steps, "WORKFLOW_ROUTE", "STATE_MACHINE", state, desired_state, {"next_tool": tool_name})
            context.conversation_state = state
            self._update_session(session_id, state, facts)
            arguments = self._arguments(tool_name, scenario_id, scenario, order, case, facts, trace_id, occurrence)
            if tool_name in {"submit_cancellation", "reserve_mock_alternative", "accept_supplier_offer", "submit_order_change"}:
                token = self.registry.mint_confirmation(context, tool_name, arguments)
                arguments["confirmation_token"] = token
            result = self.registry.execute(tool_name, arguments, context)
            tool_calls.append(tool_name)
            if not result.ok:
                self._finish_failed(run_id, result.as_dict())
                raise RuntimeError(f"{tool_name} failed: {result.code} {result.data}")
            facts[tool_name] = result.data
            state_after = self._next_state_after(scenario_id, tool_name, state)
            self._record_tool_step(run_id, steps, tool_name, state, state_after, result.as_dict())
            state = state_after

        final = self._load_case(case["case_id"])
        state = final["conversation_state"]
        self._update_session(session_id, state, facts)
        assertions = rules.assert_workflow(
            scenario["required_tools"], tool_calls, scenario["expected_case_status"], final["case_status"]
        )
        result = WorkflowResult(
            run_id, scenario_id, route, session_id, case["case_id"], state,
            final["case_status"], final["waiting_for"], tool_calls, steps, assertions,
        )
        with connect() as connection:
            connection.execute(
                "UPDATE workflow_runs SET status=?, completed_at=?, result_json=? WHERE run_id=?",
                ("SUCCEEDED" if all(assertions.values()) else "ASSERTION_FAILED", now_iso(), json_dump(result.as_dict()), run_id),
            )
        return result

    def _load_scenario(self, scenario_id: str) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
        with connect() as connection:
            scenario = payload_row(connection, "scenario_fixtures", "scenario_id=?", (scenario_id,))
            if not scenario:
                raise ValueError(f"Unknown scenario: {scenario_id}")
            order = payload_row(connection, "orders", "order_id=?", (scenario["order_id"],))
            case = payload_row(connection, "cases", "case_id=?", (scenario["case_id"],))
        return scenario, order, case

    def _load_case(self, case_id: str) -> Dict[str, Any]:
        with connect() as connection:
            return payload_row(connection, "cases", "case_id=?", (case_id,))

    def _state_for(self, scenario_id: str, tool_name: str) -> str:
        overrides = {
            ("C", "get_payment_events"): "TRACKING_REFUND",
            ("H", "create_human_handoff"): "WAITING_EXTERNAL",
            ("K", "create_human_handoff"): "DECISION_READY",
            ("E", "create_human_handoff"): "OPTION_PRESENTED",
            ("L", "create_human_handoff"): "OPTION_PRESENTED",
        }
        return overrides.get((scenario_id, tool_name), TOOL_STATES[tool_name])

    def _next_state_after(self, scenario_id: str, tool_name: str, current: str) -> str:
        next_states = {
            "submit_cancellation": "TRACKING_REFUND",
            "schedule_deadline_action": "WAITING_EXTERNAL",
            "create_human_handoff": "ESCALATED",
            "confirm_recovery_outcome": "RESOLVED",
            "create_supplier_case": "WAITING_EXTERNAL",
            "get_supplier_case": "OPTION_PRESENTED",
            "accept_supplier_offer": "TRACKING_REFUND",
            "create_exception_review": "ESCALATED",
            "create_service_dispute_case": "WAITING_EXTERNAL",
            "submit_order_change": "RESOLVED",
            "create_finance_case": "ESCALATED",
        }
        return next_states.get(tool_name, current)

    def _arguments(
        self,
        name: str,
        scenario_id: str,
        scenario: Dict[str, Any],
        order: Dict[str, Any],
        case: Dict[str, Any],
        facts: Dict[str, Any],
        trace_id: str,
        occurrence: int,
    ) -> Dict[str, Any]:
        user_id, order_id, case_id = case["user_id"], order["order_id"], case["case_id"]
        idem = f"idem-{scenario_id}-{name}-{occurrence}"
        common = {"trace_id": trace_id}
        mapping: Dict[str, Dict[str, Any]] = {
            "list_user_orders": {"authenticated_user_id": user_id, "status_filter": ["CONFIRMED", "CHECKED_IN"]},
            "get_order_detail": {"authenticated_user_id": user_id, "order_id": order_id},
            "get_policy_snapshot": {"order_id": order_id, "policy_id": order["policy_id"]},
            "list_after_sale_events": {"order_id": order_id},
            "calculate_refund_quote": {"order_id": order_id, "expected_order_version": order["version"], "request_time": DEMO_NOW, "reason_code": "PLAN_CHANGE"},
            "validate_action_permission": {"authenticated_user_id": user_id, "case_id": case_id, "order_id": order_id, "action": "CANCEL", "expected_order_version": order["version"]},
            "submit_cancellation": {"authenticated_user_id": user_id, "case_id": case_id, "order_id": order_id, "expected_order_version": order["version"], "quote_id": facts.get("calculate_refund_quote", {}).get("quote_id"), "idempotency_key": idem},
            "get_refund_status": {"refund_id": order.get("refund_id") or facts.get("submit_cancellation", {}).get("refund", {}).get("refund_id")},
            "get_payment_events": {"authenticated_user_id": user_id, "payment_id": order["payment_id"]},
            "schedule_deadline_action": {"case_id": case_id, "deadline": facts.get("get_refund_status", {}).get("refund", {}).get("sla_due_at", "2026-09-07T18:00:00+08:00"), "action_type": "CHECK_REFUND_SLA", "idempotency_key": idem},
            "create_payment_investigation": {"case_id": case_id, "order_id": order_id, "refund_id": order.get("refund_id"), "trigger_reason": "SLA_BREACH", "idempotency_key": idem},
            "verify_fulfillment_issue": {"case_id": case_id, "order_id": order_id, "reported_issue": order.get("fulfillment_alert", {}).get("type", "NO_ROOM"), "user_on_site": scenario_id == "E"},
            "get_alternative_hotels": {"source_order_id": order_id, "location": "HOTEL_AREA", "check_in": order["check_in"], "check_out": order["check_out"], "minimum_star_level": 4},
            "get_guarantee_quote": {"order_id": order_id, "issue_type": order.get("fulfillment_alert", {}).get("type", "NO_ROOM"), "alternative_hotel_id": "HTL-D-ALT-1" if scenario_id == "D" else "HTL-E-ALT-1"},
            "reserve_mock_alternative": {"authenticated_user_id": user_id, "case_id": case_id, "alternative_hotel_id": "HTL-D-ALT-1", "idempotency_key": idem},
            "create_human_handoff": {"case_id": case_id, "order_id": order_id, "user_goal": scenario["title"], "confirmed_facts": [order_id], "unknown_facts": [], "policy_refs": [order["policy_id"]], "tool_results": list(facts), "risk_level": scenario["risk_level"], "risk_reasons": ["SPECIALIST_REQUIRED"], "recommended_next_step": "SPECIALIST_REVIEW", "queue": self._handoff_queue(scenario_id), "idempotency_key": idem},
            "get_handoff_status": {"handoff_id": facts.get("create_human_handoff", {}).get("handoff_id")},
            "confirm_recovery_outcome": {"case_id": case_id, "recovery_outcome": "ALTERNATIVE_HOTEL_CONFIRMED", "user_confirmation": True, "idempotency_key": idem},
            "build_supplier_case_draft": {"case_id": case_id, "order_id": order_id, "reason_code": "PLAN_CHANGE", "requested_outcome": "EXCEPTION_REFUND", "confirmed_facts": ["NON_REFUNDABLE_POLICY"], "evidence_ids": []},
            "create_supplier_case": {"authenticated_user_id": user_id, "case_id": case_id, "order_id": order_id, "draft_id": facts.get("build_supplier_case_draft", {}).get("draft_id"), "user_submission_confirmation": True, "idempotency_key": idem},
            "get_supplier_case": {"supplier_case_id": facts.get("create_supplier_case", {}).get("supplier_case_id")},
            "accept_supplier_offer": {"authenticated_user_id": user_id, "case_id": case_id, "supplier_case_id": facts.get("create_supplier_case", {}).get("supplier_case_id"), "offer_id": "OFF-F-REFUND", "idempotency_key": idem},
            "extract_evidence_fields": {"evidence_id": facts.get("submit_evidence_metadata", {}).get("evidence_id"), "extraction_schema": "MINIMUM_NECESSARY_V1"},
            "create_exception_review": {"case_id": case_id, "order_id": order_id, "reason_code": "TRANSPORT_CANCELLATION", "evidence_ids": ["EVD-G-001"], "requested_outcome": "FULL_REFUND_REVIEW", "idempotency_key": idem},
            "create_service_dispute_case": {"case_id": case_id, "order_id": order_id, "issue_categories": ["DESCRIPTION_MISMATCH", "CLEANLINESS"], "user_on_site": True, "evidence_ids": ["EVD-H-001", "EVD-H-002"], "requested_outcome": "REFUND", "idempotency_key": idem},
            "get_change_quote": {"order_id": order_id, "expected_order_version": order["version"], "change_type": "DATE", "target_value": {"check_in": "2026-09-13", "check_out": "2026-09-14"}},
            "submit_order_change": {"authenticated_user_id": user_id, "case_id": case_id, "order_id": order_id, "expected_order_version": order["version"], "change_quote_id": facts.get("get_change_quote", {}).get("change_quote_id"), "idempotency_key": idem},
            "create_finance_case": {"case_id": case_id, "order_id": order_id, "payment_id": order["payment_id"], "event_ids": ["PEV-J-CAPTURE", "PEV-J-AUTH-HOLD"], "anomaly_type": "PREAUTHORIZATION_HOLD", "idempotency_key": idem},
            "get_responsibility_chain": {"order_id": order_id},
            "get_group_order_breakdown": {"authenticated_user_id": user_id, "order_id": order_id},
            "get_partial_cancel_quote": {"order_id": order_id, "expected_order_version": order["version"], "room_item_ids": ["L-R1", "L-R2", "L-R3"]},
        }
        if name == "submit_evidence_metadata":
            if scenario_id == "G":
                data = {"authenticated_user_id": user_id, "case_id": case_id, "evidence_type": "TRANSPORT_CANCELLATION_NOTICE", "storage_reference": "mock://evidence/G/transport", "consent": True, "idempotency_key": idem}
            else:
                evidence_type = "ISSUE_PHOTO" if occurrence == 2 else "HOTEL_CONTACT_RESULT"
                data = {"authenticated_user_id": user_id, "case_id": case_id, "evidence_type": evidence_type, "storage_reference": f"mock://evidence/H/{occurrence}", "consent": True, "idempotency_key": idem}
        else:
            data = mapping[name]
        return {**data, **common}

    def _handoff_queue(self, scenario_id: str) -> str:
        return {
            "D": "URGENT_HUMAN_HANDOFF", "E": "URGENT_HUMAN_HANDOFF",
            "H": "SERVICE_RECOVERY_SPECIALIST", "K": "CROSS_BORDER_SPECIALIST",
            "L": "CORPORATE_GROUP_SPECIALIST",
        }.get(scenario_id, "HUMAN_SPECIALIST")

    def _record_node(self, run_id: str, steps: List[WorkflowStep], node: str, actor: str, before: str, after: str, result: Dict[str, Any]) -> str:
        step = WorkflowStep(len(steps) + 1, node, actor, before, after, result)
        steps.append(step)
        self._persist_step(run_id, step)
        return after

    def _record_tool_step(self, run_id: str, steps: List[WorkflowStep], tool_name: str, before: str, after: str, result: Dict[str, Any]) -> None:
        step = WorkflowStep(len(steps) + 1, "TOOL_EXECUTION", "TOOL", before, after, result, tool_name)
        steps.append(step)
        self._persist_step(run_id, step)

    def _persist_step(self, run_id: str, step: WorkflowStep) -> None:
        with connect() as connection:
            connection.execute(
                "INSERT INTO workflow_steps VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (f"wst_{uuid.uuid4().hex}", run_id, step.sequence_no, step.workflow_node, step.actor,
                 step.tool_name, step.state_before, step.state_after, json_dump(step.result), now_iso()),
            )

    def _update_session(self, session_id: str, state: str, facts: Dict[str, Any]) -> None:
        with connect() as connection:
            connection.execute(
                "UPDATE sessions SET conversation_state=?, state_json=?, updated_at=? WHERE session_id=?",
                (state, json_dump({"facts": list(facts)}), now_iso(), session_id),
            )

    def _finish_failed(self, run_id: str, error: Dict[str, Any]) -> None:
        with connect() as connection:
            connection.execute(
                "UPDATE workflow_runs SET status='FAILED', completed_at=?, result_json=? WHERE run_id=?",
                (now_iso(), json_dump(error), run_id),
            )
