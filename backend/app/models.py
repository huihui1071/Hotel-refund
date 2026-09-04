from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ToolContext:
    session_id: str
    authenticated_user_id: str
    conversation_state: str
    trace_id: str
    case_id: Optional[str] = None
    confirmed_order_id: Optional[str] = None
    risk_level: str = "L0"


@dataclass
class ToolResult:
    ok: bool
    code: str
    data: Dict[str, Any]
    source: str
    occurred_at: str
    trace_id: str
    retryable: bool = False

    def as_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "code": self.code,
            "data": self.data,
            "source": self.source,
            "occurred_at": self.occurred_at,
            "trace_id": self.trace_id,
            "retryable": self.retryable,
        }


@dataclass
class WorkflowStep:
    sequence_no: int
    workflow_node: str
    actor: str
    state_before: str
    state_after: str
    result: Dict[str, Any] = field(default_factory=dict)
    tool_name: Optional[str] = None


@dataclass
class WorkflowResult:
    run_id: str
    scenario_id: str
    route: str
    session_id: str
    case_id: str
    conversation_state: str
    case_status: str
    waiting_for: str
    tool_calls: List[str]
    steps: List[WorkflowStep]
    assertions: Dict[str, bool]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "scenario_id": self.scenario_id,
            "route": self.route,
            "session_id": self.session_id,
            "case_id": self.case_id,
            "conversation_state": self.conversation_state,
            "case_status": self.case_status,
            "waiting_for": self.waiting_for,
            "tool_calls": self.tool_calls,
            "steps": [step.__dict__ for step in self.steps],
            "assertions": self.assertions,
        }


class ToolError(Exception):
    def __init__(self, code: str, message: str, *, retryable: bool = False, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable
        self.details = details or {}

