from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Iterable, Optional


DEMO_NOW = "2026-09-04T15:20:00+08:00"
RISK_ORDER = {"L0": 0, "L1": 1, "L2": 2, "L3": 3, "L4": 4}


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value)


def refund_quote(order: Dict[str, Any], policy: Dict[str, Any], request_time: str = DEMO_NOW) -> Dict[str, Any]:
    """Deterministically calculate money from the booking policy snapshot."""
    paid = int(order["amount"]["paid"])
    currency = order["amount"]["currency"]
    rule = policy["rule"]
    now = parse_time(request_time)
    fee = paid

    if rule["type"] == "DEADLINE":
        deadline = parse_time(rule["free_cancel_before"])
        fee = 0 if now <= deadline else paid
    elif rule["type"] == "TIERED":
        for tier in rule["tiers"]:
            starts = parse_time(tier["from"]) if tier.get("from") else None
            ends = parse_time(tier["until"]) if tier.get("until") else None
            before = parse_time(tier["before"]) if tier.get("before") else None
            if before:
                if now < before:
                    fee = int(tier["fee"])
                    break
                continue
            if (starts is None or now >= starts) and (ends is None or now < ends):
                fee = int(tier["fee"])
                break
    elif rule["type"] == "NON_REFUNDABLE":
        fee = paid

    return {
        "paid_amount": paid,
        "refund_amount": max(paid - fee, 0),
        "cancellation_fee": fee,
        "currency": currency,
        "policy_id": policy["policy_id"],
        "policy_version": policy["version"],
        "requires_human": bool(policy["requires_human"]),
    }


def route_for(order: Dict[str, Any], policy: Dict[str, Any], refund: Optional[Dict[str, Any]] = None) -> str:
    scenario = order["scenario_id"]
    routes = {
        "A": "DETERMINISTIC_CANCELLATION",
        "B": "DETERMINISTIC_CANCELLATION",
        "C": "REFUND_TRACKING",
        "D": "PREARRIVAL_RECOVERY",
        "E": "ONSITE_URGENT_RECOVERY",
        "F": "SUPPLIER_NEGOTIATION",
        "G": "SPECIAL_EXCEPTION_REVIEW",
        "H": "SERVICE_DISPUTE",
        "I": "ORDER_CHANGE",
        "J": "PAYMENT_ANOMALY",
        "K": "CROSS_BORDER_SPECIALIST",
        "L": "CORPORATE_GROUP_SPECIALIST",
    }
    return routes[scenario]


def risk_for(order: Dict[str, Any], policy: Dict[str, Any]) -> Dict[str, Any]:
    scenario = order["scenario_id"]
    if scenario in {"A", "B", "C", "I"}:
        return {"level": "L1", "reasons": ["DETERMINISTIC_ORDER_SCOPED_ACTION"]}
    if scenario in {"F", "G"}:
        return {"level": "L2", "reasons": ["EXCEPTION_OR_EXTERNAL_DECISION"]}
    return {"level": "L3", "reasons": ["HUMAN_SPECIALIST_REQUIRED"]}


def action_allowed(risk_level: str, maximum_automatic_risk: str = "L1") -> bool:
    return RISK_ORDER[risk_level] <= RISK_ORDER[maximum_automatic_risk]


def payment_interpretation(events: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    events = list(events)
    captures = [e for e in events if e["type"] == "CAPTURE"]
    holds = [e for e in events if e["type"] == "PREAUTHORIZATION_HOLD"]
    return {
        "captured_amount": sum(int(e.get("amount", 0)) for e in captures),
        "preauthorization_hold": sum(int(e.get("amount", 0)) for e in holds),
        "duplicate_capture": len(captures) > 1,
        "hold_is_duplicate_charge": False,
    }


def assert_workflow(expected_tools: Iterable[str], actual_tools: Iterable[str], expected_status: str, actual_status: str) -> Dict[str, bool]:
    expected = list(expected_tools)
    actual = list(actual_tools)
    return {
        "required_tools_called_in_order": _is_subsequence(expected, actual),
        "expected_case_status_reached": expected_status == actual_status,
        "no_unexpected_tool": all(name in expected for name in actual),
    }


def _is_subsequence(expected: list, actual: list) -> bool:
    iterator = iter(actual)
    return all(any(item == candidate for candidate in iterator) for item in expected)
