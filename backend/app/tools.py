from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from . import rules
from .db import (
    _insert_evidence,
    _insert_external_case,
    _insert_refund,
    connect,
    fixture,
    json_dump,
    json_load,
    payload_row,
    payload_rows,
)
from .models import ToolContext, ToolError, ToolResult


DEMO_NOW = "2026-09-04T15:20:00+08:00"
CONFIRMATION_TOOLS = {
    "submit_cancellation",
    "reserve_mock_alternative",
    "accept_supplier_offer",
    "submit_order_change",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ToolRegistry:
    def execute(self, name: str, arguments: Dict[str, Any], context: ToolContext) -> ToolResult:
        with connect() as connection:
            try:
                contract = self._contract(connection, name)
                self._validate_access(connection, contract, arguments, context)
                cached = self._idempotent_result(connection, contract, arguments)
                if cached:
                    return ToolResult(**cached)
                data = self._dispatch(connection, name, arguments, context)
                result = ToolResult(True, "OK", data, self._source(name), now_iso(), context.trace_id, False)
                if contract["mode"] == "WRITE":
                    self._save_idempotent_result(connection, name, arguments, result)
                self._audit(connection, name, contract["mode"], arguments, context, result.as_dict())
                return result
            except ToolError as exc:
                result = ToolResult(False, exc.code, {"message": exc.message, **exc.details}, "tool-access-gateway", now_iso(), context.trace_id, exc.retryable)
                self._audit(connection, name, "UNKNOWN", arguments, context, result.as_dict())
                return result

    def mint_confirmation(
        self,
        context: ToolContext,
        tool_name: str,
        arguments: Dict[str, Any],
        ttl_minutes: int = 10,
    ) -> str:
        token = f"cfm_{uuid.uuid4().hex}"
        fingerprint = self._action_fingerprint(tool_name, arguments)
        expires_at = (datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)).isoformat()
        with connect() as connection:
            session = connection.execute("SELECT 1 FROM sessions WHERE session_id=?", (context.session_id,)).fetchone()
            if not session:
                raise ToolError("AUTH_REQUIRED", "Session does not exist")
            connection.execute(
                "INSERT INTO confirmation_tokens VALUES (?, ?, ?, ?, ?, ?, ?, NULL)",
                (token, context.session_id, tool_name, arguments.get("order_id"), arguments.get("expected_order_version"), fingerprint, expires_at),
            )
        return token

    def _contract(self, connection: sqlite3.Connection, name: str) -> Dict[str, Any]:
        contract = payload_row(connection, "tool_contracts", "tool_name=?", (name,))
        if not contract:
            raise ToolError("INTERNAL_ERROR", f"Unknown tool: {name}")
        return contract

    def _validate_access(
        self,
        connection: sqlite3.Connection,
        contract: Dict[str, Any],
        arguments: Dict[str, Any],
        context: ToolContext,
    ) -> None:
        specialized_fields = {"confirmation_token", "idempotency_key"}
        missing = [
            key for key in contract.get("input", {}).get("required", [])
            if arguments.get(key) is None and key not in specialized_fields
        ]
        if missing:
            raise ToolError("INTERNAL_ERROR", "Missing required tool arguments", details={"missing": missing})
        if context.conversation_state not in contract.get("allowed_conversation_states", []):
            raise ToolError("ORDER_NOT_CONFIRMED", f"Tool {contract['name']} is not allowed in state {context.conversation_state}")
        identity = connection.execute(
            "SELECT identity_status FROM users WHERE user_id=?", (context.authenticated_user_id,)
        ).fetchone()
        if not identity or identity["identity_status"] != "VERIFIED":
            raise ToolError("AUTH_REQUIRED", "A verified authenticated user is required")
        requested_user = arguments.get("authenticated_user_id")
        if requested_user and requested_user != context.authenticated_user_id:
            raise ToolError("AUTH_REQUIRED", "Authenticated identity does not match the tool request")
        order_id = arguments.get("order_id") or arguments.get("source_order_id")
        if order_id:
            if not context.confirmed_order_id or order_id != context.confirmed_order_id:
                raise ToolError("ORDER_NOT_CONFIRMED", "The requested order was not explicitly confirmed")
            owner = connection.execute("SELECT user_id FROM orders WHERE order_id=?", (order_id,)).fetchone()
            if not owner or owner["user_id"] != context.authenticated_user_id:
                raise ToolError("FORBIDDEN_ORDER", "The authenticated user does not own this order")
        case_id = arguments.get("case_id")
        if case_id and context.case_id and case_id != context.case_id:
            raise ToolError("FORBIDDEN_ORDER", "Case is outside the active session scope")
        if contract["mode"] == "WRITE":
            if not arguments.get("idempotency_key"):
                raise ToolError("IDEMPOTENCY_CONFLICT", "Write tools require an idempotency key")
            if contract["name"] in {"submit_cancellation", "submit_order_change"} and not rules.action_allowed(context.risk_level):
                raise ToolError("RISK_REQUIRES_HUMAN", "Risk level exceeds the automatic transaction limit")
            if contract["name"] in CONFIRMATION_TOOLS:
                replay = connection.execute(
                    "SELECT 1 FROM idempotency_records WHERE idempotency_key=?",
                    (arguments["idempotency_key"],),
                ).fetchone()
                if not replay:
                    self._validate_confirmation(connection, contract["name"], arguments, context)

    def _validate_confirmation(
        self,
        connection: sqlite3.Connection,
        tool_name: str,
        arguments: Dict[str, Any],
        context: ToolContext,
    ) -> None:
        token = arguments.get("confirmation_token")
        if not token:
            raise ToolError("CONFIRMATION_REQUIRED", "This action requires explicit user confirmation")
        row = connection.execute("SELECT * FROM confirmation_tokens WHERE token=?", (token,)).fetchone()
        if not row or row["session_id"] != context.session_id or row["tool_name"] != tool_name:
            raise ToolError("CONFIRMATION_REQUIRED", "Confirmation token is invalid for this action")
        if row["consumed_at"]:
            raise ToolError("CONFIRMATION_REQUIRED", "Confirmation token has already been consumed")
        if datetime.fromisoformat(row["expires_at"]) < datetime.now(timezone.utc):
            raise ToolError("CONFIRMATION_REQUIRED", "Confirmation token has expired")
        if row["order_id"] and row["order_id"] != arguments.get("order_id"):
            raise ToolError("CONFIRMATION_REQUIRED", "Confirmation order does not match")
        if row["expected_version"] is not None and row["expected_version"] != arguments.get("expected_order_version"):
            raise ToolError("VERSION_CONFLICT", "Confirmed order version has changed")
        if row["action_fingerprint"] != self._action_fingerprint(tool_name, arguments):
            raise ToolError("CONFIRMATION_REQUIRED", "Confirmed action details do not match the execution request")
        connection.execute("UPDATE confirmation_tokens SET consumed_at=? WHERE token=?", (now_iso(), token))

    def _idempotent_result(self, connection: sqlite3.Connection, contract: Dict[str, Any], arguments: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if contract["mode"] != "WRITE":
            return None
        key = arguments["idempotency_key"]
        row = connection.execute("SELECT request_hash, result_json FROM idempotency_records WHERE idempotency_key=?", (key,)).fetchone()
        if not row:
            return None
        request_hash = self._request_hash(arguments)
        if row["request_hash"] != request_hash:
            raise ToolError("IDEMPOTENCY_CONFLICT", "The idempotency key was used with different arguments")
        return json_load(row["result_json"])

    def _save_idempotent_result(self, connection: sqlite3.Connection, name: str, arguments: Dict[str, Any], result: ToolResult) -> None:
        connection.execute(
            "INSERT INTO idempotency_records VALUES (?, ?, ?, ?, ?)",
            (arguments["idempotency_key"], name, self._request_hash(arguments), json_dump(result.as_dict()), now_iso()),
        )

    def _audit(self, connection: sqlite3.Connection, name: str, mode: str, arguments: Dict[str, Any], context: ToolContext, response: Dict[str, Any]) -> None:
        connection.execute(
            "INSERT INTO tool_executions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (f"tex_{uuid.uuid4().hex}", name, mode, context.trace_id, context.session_id, context.case_id,
             arguments.get("order_id") or arguments.get("source_order_id"), json_dump(arguments), json_dump(response), now_iso()),
        )

    def _dispatch(self, connection: sqlite3.Connection, name: str, args: Dict[str, Any], context: ToolContext) -> Dict[str, Any]:
        handlers = {
            "list_user_orders": self._list_user_orders,
            "get_order_detail": self._get_order_detail,
            "get_policy_snapshot": self._get_policy_snapshot,
            "list_after_sale_events": self._list_after_sale_events,
            "calculate_refund_quote": self._calculate_refund_quote,
            "validate_action_permission": self._validate_action_permission,
            "submit_cancellation": self._submit_cancellation,
            "get_action_result": self._get_action_result,
            "get_refund_status": self._get_refund_status,
            "get_payment_events": self._get_payment_events,
            "schedule_deadline_action": self._schedule_deadline_action,
            "create_payment_investigation": self._create_payment_investigation,
            "verify_fulfillment_issue": self._verify_fulfillment_issue,
            "get_alternative_hotels": self._get_alternative_hotels,
            "get_guarantee_quote": self._get_fixture_tool,
            "reserve_mock_alternative": self._reserve_mock_alternative,
            "create_human_handoff": self._create_human_handoff,
            "get_handoff_status": self._get_handoff_status,
            "confirm_recovery_outcome": self._confirm_recovery_outcome,
            "build_supplier_case_draft": self._build_supplier_case_draft,
            "create_supplier_case": self._create_supplier_case,
            "get_supplier_case": self._get_supplier_case,
            "accept_supplier_offer": self._accept_supplier_offer,
            "submit_evidence_metadata": self._submit_evidence_metadata,
            "extract_evidence_fields": self._extract_evidence_fields,
            "create_exception_review": self._create_exception_review,
            "create_service_dispute_case": self._create_service_dispute_case,
            "get_change_quote": self._get_fixture_tool,
            "submit_order_change": self._submit_order_change,
            "create_finance_case": self._create_finance_case,
            "get_responsibility_chain": self._get_fixture_tool,
            "get_group_order_breakdown": self._get_fixture_tool,
            "get_partial_cancel_quote": self._get_fixture_tool,
        }
        return handlers[name](connection, name, args, context)

    def _list_user_orders(self, c: sqlite3.Connection, name: str, a: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
        rows = c.execute(
            "SELECT o.payload_json AS order_json, h.payload_json AS hotel_json FROM orders o JOIN hotels h ON h.hotel_id=o.hotel_id WHERE o.user_id=?",
            (a["authenticated_user_id"],),
        ).fetchall()
        items = []
        for row in rows:
            order, hotel = json_load(row["order_json"]), json_load(row["hotel_json"])
            if a.get("status_filter") and order["status"] not in a["status_filter"]:
                continue
            if a.get("city") and hotel["city"] != a["city"]:
                continue
            items.append({
                "order_id": order["order_id"], "hotel_name": hotel["name"], "city": hotel["city"],
                "check_in": order["check_in"], "check_out": order["check_out"], "room_type": order["room_type"],
                "paid_amount": order["amount"]["paid"], "currency": order["amount"]["currency"], "status": order["status"],
            })
        return {"orders": items}

    def _get_order_detail(self, c: sqlite3.Connection, name: str, a: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
        order = self._require_payload(c, "orders", "order_id=?", (a["order_id"],), "Order")
        hotel = self._require_payload(c, "hotels", "hotel_id=?", (order["hotel_id"],), "Hotel")
        return {"order": order, "hotel": hotel, "evidence_refs": [order["order_id"], hotel["hotel_id"]]}

    def _get_policy_snapshot(self, c: sqlite3.Connection, name: str, a: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
        policy = payload_row(c, "policies", "policy_id=?", (a["policy_id"],))
        if not policy:
            raise ToolError("POLICY_SNAPSHOT_MISSING", "Booking policy snapshot is unavailable")
        return {"policy": policy, "evidence_refs": [policy["policy_id"]]}

    def _list_after_sale_events(self, c: sqlite3.Connection, name: str, a: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
        case = c.execute("SELECT case_id FROM cases WHERE order_id=?", (a["order_id"],)).fetchone()
        events = payload_rows(c, "case_events", "case_id=?", (case["case_id"],)) if case else []
        return {"events": events}

    def _calculate_refund_quote(self, c: sqlite3.Connection, name: str, a: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
        order = self._require_payload(c, "orders", "order_id=?", (a["order_id"],), "Order")
        self._check_version(order, a["expected_order_version"])
        policy = self._require_payload(c, "policies", "policy_id=?", (order["policy_id"],), "Policy")
        calculated = rules.refund_quote(order, policy, a["request_time"])
        saved = fixture(c, f"tool:{name}", order["order_id"])
        if saved:
            calculated.update(saved["data"])
        return calculated

    def _validate_action_permission(self, c: sqlite3.Connection, name: str, a: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
        order = self._require_payload(c, "orders", "order_id=?", (a["order_id"],), "Order")
        self._check_version(order, a["expected_order_version"])
        saved = fixture(c, f"tool:{name}", order["order_id"])
        if saved:
            return saved["data"]
        allowed = rules.action_allowed(ctx.risk_level)
        return {"allowed": allowed, "risk_level": ctx.risk_level, "denial_reasons": [] if allowed else ["RISK_REQUIRES_HUMAN"], "confirmation_required": allowed}

    def _submit_cancellation(self, c: sqlite3.Connection, name: str, a: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
        order = self._require_payload(c, "orders", "order_id=?", (a["order_id"],), "Order")
        self._check_version(order, a["expected_order_version"])
        quote_fixture = fixture(c, "tool:calculate_refund_quote", order["order_id"])
        if not quote_fixture or quote_fixture["data"]["quote_id"] != a["quote_id"]:
            raise ToolError("QUOTE_EXPIRED", "Cancellation quote is missing or no longer valid")
        if rules.parse_time(quote_fixture["data"]["expires_at"]) < rules.parse_time(DEMO_NOW):
            raise ToolError("QUOTE_EXPIRED", "Cancellation quote has expired")
        item = self._fixture_for_case(c, "refund", ctx.case_id)
        if not item:
            raise ToolError("INTERNAL_ERROR", "Expected refund fixture is missing")
        _insert_refund(c, item)
        self._update_order(c, order, status="CANCELLED", refund_id=item["refund_id"])
        self._update_case(c, ctx.case_id, "TRACKING_REFUND", "REFUND_INITIATED", "PAYMENT_CHANNEL")
        return {"action_status": "SUCCEEDED", "refund": item, "order_version": order["version"] + 1}

    def _get_action_result(self, c: sqlite3.Connection, name: str, a: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
        row = c.execute("SELECT result_json FROM idempotency_records WHERE idempotency_key=?", (a["idempotency_key"],)).fetchone()
        return {"found": bool(row), "result": json_load(row["result_json"]) if row else None}

    def _get_refund_status(self, c: sqlite3.Connection, name: str, a: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
        refund = self._require_payload(c, "refunds", "refund_id=?", (a["refund_id"],), "Refund")
        return {"refund": refund, "must_not_say": "REFUNDED" if refund["status"] != "REFUNDED" else None}

    def _get_payment_events(self, c: sqlite3.Connection, name: str, a: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
        payment = self._require_payload(c, "payments", "payment_id=?", (a["payment_id"],), "Payment")
        events = payload_rows(c, "payment_events", "payment_id=?", (a["payment_id"],))
        return {"payment": payment, "events": events, "interpretation": rules.payment_interpretation(events)}

    def _schedule_deadline_action(self, c: sqlite3.Connection, name: str, a: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
        action_id = f"SCHED-{ctx.case_id}"
        payload = {"action_id": action_id, "case_id": a["case_id"], "deadline": a["deadline"], "action_type": a["action_type"], "status": "SCHEDULED"}
        c.execute("INSERT OR REPLACE INTO scheduled_actions VALUES (?, ?, ?, ?, ?, ?)", (action_id, a["case_id"], a["deadline"], a["action_type"], "SCHEDULED", json_dump(payload)))
        self._update_case(c, ctx.case_id, "WAITING_EXTERNAL", "AWAITING_PAYMENT", "PAYMENT_CHANNEL")
        return payload

    def _create_payment_investigation(self, c: sqlite3.Connection, name: str, a: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
        item = self._fixture_for_case(c, "external_cases", ctx.case_id, preferred_type="PAYMENT_INVESTIGATION")
        if not item:
            raise ToolError("SLA_NOT_BREACHED", "No payment investigation is needed yet")
        _insert_external_case(c, item)
        return item

    def _verify_fulfillment_issue(self, c: sqlite3.Connection, name: str, a: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
        order = self._require_payload(c, "orders", "order_id=?", (a["order_id"],), "Order")
        alert = order.get("fulfillment_alert")
        return {"verified": bool(alert), "issue": alert, "recovery_first": bool(a["user_on_site"])}

    def _get_alternative_hotels(self, c: sqlite3.Connection, name: str, a: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
        alternatives = payload_rows(c, "alternative_hotels", "source_order_id=? AND available=1", (a["source_order_id"],))
        return {"alternatives": alternatives}

    def _get_fixture_tool(self, c: sqlite3.Connection, name: str, a: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
        order_id = a.get("order_id") or a.get("source_order_id")
        key = order_id
        if a.get("alternative_hotel_id"):
            key = f"{key}:{a['alternative_hotel_id']}"
        item = fixture(c, f"tool:{name}", key)
        if not item:
            raise ToolError("INTERNAL_ERROR", f"No deterministic fixture for {name}")
        return item["data"]

    def _reserve_mock_alternative(self, c: sqlite3.Connection, name: str, a: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
        return {"reservation_id": f"ALT-{ctx.case_id}", "status": "HELD", "alternative_hotel_id": a["alternative_hotel_id"], "hold_minutes": 10}

    def _create_human_handoff(self, c: sqlite3.Connection, name: str, a: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
        candidates = self._fixtures_for_case(c, "external_cases", ctx.case_id)
        item = next((candidate for candidate in candidates if candidate.get("type") == a.get("queue")), None)
        if not item:
            item = {"external_case_id": f"HND-{ctx.case_id}", "case_id": ctx.case_id, "type": a.get("queue", "HUMAN_HANDOFF"), "status": "QUEUED", "waiting_for": "HUMAN_SPECIALIST", "response_due_at": None}
        _insert_external_case(c, item)
        final_status = {"D": "RECOVERY_IN_PROGRESS", "H": "MANUAL_REVIEW", "K": "AWAITING_SPECIALIST", "L": "AWAITING_SPECIALIST"}.get(ctx.case_id.split("-")[1], "MANUAL_REVIEW")
        self._update_case(c, ctx.case_id, "ESCALATED", final_status, item["waiting_for"])
        return {"handoff_id": item["external_case_id"], **item}

    def _get_handoff_status(self, c: sqlite3.Connection, name: str, a: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
        item = self._require_payload(c, "external_cases", "external_case_id=?", (a["handoff_id"],), "Handoff")
        return item

    def _confirm_recovery_outcome(self, c: sqlite3.Connection, name: str, a: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
        if not a["user_confirmation"]:
            raise ToolError("CONFIRMATION_REQUIRED", "User must confirm the recovery outcome")
        self._update_case(c, ctx.case_id, "RESOLVED", "RECOVERED", "NONE")
        return {"recorded": True, "recovery_outcome": a["recovery_outcome"], "case_status": "RECOVERED"}

    def _build_supplier_case_draft(self, c: sqlite3.Connection, name: str, a: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
        return {"draft_id": f"DR-{ctx.case_id}", "summary": {"reason_code": a["reason_code"], "requested_outcome": a["requested_outcome"], "confirmed_facts": a["confirmed_facts"]}, "requires_user_submission_confirmation": True}

    def _create_supplier_case(self, c: sqlite3.Connection, name: str, a: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
        if not a["user_submission_confirmation"]:
            raise ToolError("CONFIRMATION_REQUIRED", "Supplier submission requires user confirmation")
        item = self._fixture_for_case(c, "external_cases", ctx.case_id, preferred_type="SUPPLIER_NEGOTIATION")
        _insert_external_case(c, item)
        self._update_case(c, ctx.case_id, "WAITING_EXTERNAL", "AWAITING_SUPPLIER", "SUPPLIER")
        return {"supplier_case_id": item["external_case_id"], **item}

    def _get_supplier_case(self, c: sqlite3.Connection, name: str, a: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
        return self._require_payload(c, "external_cases", "external_case_id=?", (a["supplier_case_id"],), "Supplier case")

    def _accept_supplier_offer(self, c: sqlite3.Connection, name: str, a: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
        supplier_case = self._require_payload(c, "external_cases", "external_case_id=?", (a["supplier_case_id"],), "Supplier case")
        offer = next((item for item in supplier_case.get("offers", []) if item["offer_id"] == a["offer_id"]), None)
        if not offer:
            raise ToolError("SUPPLIER_OFFER_EXPIRED", "Supplier offer is unavailable")
        if rules.parse_time(offer["valid_until"]) < rules.parse_time(DEMO_NOW):
            raise ToolError("SUPPLIER_OFFER_EXPIRED", "Supplier offer has expired")
        refund = self._fixture_for_case(c, "refund", ctx.case_id)
        _insert_refund(c, refund)
        order = self._require_payload(c, "orders", "order_id=?", (ctx.confirmed_order_id,), "Order")
        self._update_order(c, order, status="CANCELLED", refund_id=refund["refund_id"])
        self._update_case(c, ctx.case_id, "TRACKING_REFUND", "REFUND_INITIATED", "PAYMENT_CHANNEL")
        return {"offer": offer, "refund": refund}

    def _submit_evidence_metadata(self, c: sqlite3.Connection, name: str, a: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
        if not a["consent"]:
            raise ToolError("EVIDENCE_TOO_SENSITIVE", "Evidence metadata requires user consent")
        items = self._fixtures_for_case(c, "evidence_items", ctx.case_id)
        item = next((x for x in items if x["type"] == a["evidence_type"]), None)
        if not item:
            raise ToolError("EVIDENCE_TOO_SENSITIVE", "Only minimum necessary evidence types are accepted")
        _insert_evidence(c, item)
        return item

    def _extract_evidence_fields(self, c: sqlite3.Connection, name: str, a: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
        item = self._require_payload(c, "evidence_items", "evidence_id=?", (a["evidence_id"],), "Evidence")
        return {"evidence_id": item["evidence_id"], "fields": item["fields"], "schema": a["extraction_schema"]}

    def _create_exception_review(self, c: sqlite3.Connection, name: str, a: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
        item = self._fixture_for_case(c, "external_cases", ctx.case_id, preferred_type="SPECIAL_EXCEPTION_REVIEW")
        _insert_external_case(c, item)
        self._update_case(c, ctx.case_id, "ESCALATED", "MANUAL_REVIEW", "HUMAN_SPECIALIST")
        return {"review_case_id": item["external_case_id"], **item}

    def _create_service_dispute_case(self, c: sqlite3.Connection, name: str, a: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
        item = self._fixture_for_case(c, "external_cases", ctx.case_id, preferred_type="SERVICE_DISPUTE")
        _insert_external_case(c, item)
        self._update_case(c, ctx.case_id, "WAITING_EXTERNAL", "MANUAL_REVIEW", "HOTEL")
        return {"dispute_case_id": item["external_case_id"], **item}

    def _submit_order_change(self, c: sqlite3.Connection, name: str, a: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
        order = self._require_payload(c, "orders", "order_id=?", (a["order_id"],), "Order")
        self._check_version(order, a["expected_order_version"])
        quote = fixture(c, "tool:get_change_quote", order["order_id"])["data"]
        if quote["change_quote_id"] != a["change_quote_id"] or rules.parse_time(quote["expires_at"]) < rules.parse_time(DEMO_NOW):
            raise ToolError("QUOTE_EXPIRED", "Change quote is missing or no longer valid")
        new_summary = quote["new_order_summary"]
        order.update(new_summary)
        self._update_order(c, order, status="CONFIRMED")
        self._update_case(c, ctx.case_id, "RESOLVED", "CHANGED", "NONE")
        return {"status": "CHANGED", "new_order_version": order["version"] + 1, "new_order_summary": new_summary, "price_difference": quote["price_difference"]}

    def _create_finance_case(self, c: sqlite3.Connection, name: str, a: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
        item = self._fixture_for_case(c, "external_cases", ctx.case_id, preferred_type="PAYMENT_ANOMALY")
        _insert_external_case(c, item)
        self._update_case(c, ctx.case_id, "ESCALATED", "MANUAL_REVIEW", "FINANCE")
        return {"finance_case_id": item["external_case_id"], **item}

    def _check_version(self, order: Dict[str, Any], expected: int) -> None:
        if order["version"] != expected:
            raise ToolError("VERSION_CONFLICT", "Order version has changed", details={"current_version": order["version"]})

    def _update_order(self, c: sqlite3.Connection, order: Dict[str, Any], **changes: Any) -> None:
        updated = dict(order)
        updated.update(changes)
        updated["version"] = order["version"] + 1
        c.execute(
            "UPDATE orders SET status=?, version=?, refund_id=?, check_in=?, check_out=?, payload_json=? WHERE order_id=?",
            (updated["status"], updated["version"], updated.get("refund_id"), updated["check_in"], updated["check_out"], json_dump(updated), updated["order_id"]),
        )

    def _update_case(self, c: sqlite3.Connection, case_id: str, conversation_state: str, case_status: str, waiting_for: str) -> None:
        case = self._require_payload(c, "cases", "case_id=?", (case_id,), "Case")
        previous_status = case["case_status"]
        case.update({"conversation_state": conversation_state, "case_status": case_status, "waiting_for": waiting_for})
        c.execute(
            "UPDATE cases SET conversation_state=?, case_status=?, waiting_for=?, updated_at=?, payload_json=? WHERE case_id=?",
            (conversation_state, case_status, waiting_for, now_iso(), json_dump(case), case_id),
        )
        event = {
            "event_id": f"evt_{uuid.uuid4().hex}", "case_id": case_id,
            "event_type": "CASE_STATUS_CHANGED", "actor_type": "TOOL", "occurred_at": now_iso(),
            "trace_id": "trace-system", "from_case_status": previous_status, "to_case_status": case_status,
            "public_summary": f"案件状态已更新为 {case_status}。", "internal_reason_codes": [],
            "source_refs": [case["order_id"]], "idempotency_key": None,
        }
        c.execute(
            "INSERT INTO case_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (event["event_id"], case_id, event["event_type"], event["actor_type"], event["occurred_at"],
             event["trace_id"], previous_status, case_status, event["public_summary"], None, json_dump(event)),
        )

    def _fixture_for_case(self, c: sqlite3.Connection, kind: str, case_id: str, preferred_type: Optional[str] = None) -> Optional[Dict[str, Any]]:
        items = self._fixtures_for_case(c, kind, case_id)
        if preferred_type:
            exact = next((item for item in items if item.get("type") == preferred_type), None)
            if exact:
                return exact
        return items[0] if items else None

    def _fixtures_for_case(self, c: sqlite3.Connection, kind: str, case_id: str) -> List[Dict[str, Any]]:
        rows = c.execute("SELECT payload_json FROM fixture_catalog WHERE fixture_type=?", (kind,)).fetchall()
        items = [json_load(row["payload_json"]) for row in rows]
        if kind == "refund":
            case = c.execute("SELECT order_id FROM cases WHERE case_id=?", (case_id,)).fetchone()
            return [item for item in items if case and item.get("order_id") == case["order_id"] and item.get("fixture_phase") != "initial"]
        return [item for item in items if item.get("case_id") == case_id]

    def _require_payload(self, c: sqlite3.Connection, table: str, where: str, values: tuple, label: str) -> Dict[str, Any]:
        item = payload_row(c, table, where, values)
        if not item:
            raise ToolError("INTERNAL_ERROR", f"{label} not found")
        return item

    def _source(self, name: str) -> str:
        if any(token in name for token in ("payment", "refund", "finance")):
            return "mock-payment-service"
        if any(token in name for token in ("supplier", "handoff", "exception", "dispute")):
            return "mock-case-service"
        return "mock-order-service"

    def _request_hash(self, arguments: Dict[str, Any]) -> str:
        comparable = {key: value for key, value in arguments.items() if key != "trace_id"}
        return hashlib.sha256(json_dump(comparable).encode("utf-8")).hexdigest()

    def _action_fingerprint(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        selected = {key: value for key, value in arguments.items() if key not in {"trace_id", "confirmation_token", "idempotency_key"}}
        return hashlib.sha256(f"{tool_name}:{json_dump(selected)}".encode("utf-8")).hexdigest()
