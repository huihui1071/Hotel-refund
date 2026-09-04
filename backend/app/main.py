from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .db import connect, database_path, init_database, json_load, payload_row, payload_rows
from .models import ToolContext, ToolError
from .tools import ToolRegistry
from .workflow import ScenarioWorkflow


class ToolContextRequest(BaseModel):
    session_id: str
    authenticated_user_id: str
    conversation_state: str
    trace_id: str
    case_id: Optional[str] = None
    confirmed_order_id: Optional[str] = None
    risk_level: str = "L0"


class ToolCallRequest(BaseModel):
    context: ToolContextRequest
    arguments: Dict[str, Any] = Field(default_factory=dict)


class ConfirmationRequest(BaseModel):
    context: ToolContextRequest
    tool_name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    ttl_minutes: int = 10


class WorkflowRunRequest(BaseModel):
    reset_database: bool = False


class AgentMessageRequest(BaseModel):
    message: str = Field(min_length=2, max_length=500)
    reset_database: bool = True


SCENARIO_SIGNALS = {
    "A": ("免费取消", "明天", "取消酒店"),
    "B": ("扣多少", "扣费", "取消费", "退多少", "首晚", "今天不去"),
    "C": ("没到账", "没有到账", "还没收到", "退款进度", "退款已经提交", "退了"),
    "D": ("通知没房", "临时加价", "加价换房", "入住前"),
    "E": ("前台", "已经到店", "到店无房", "没有房间"),
    "F": ("不能退", "不可取消", "争取", "协商", "临时有事"),
    "G": ("航班取消", "疾病", "灾害", "证明", "特殊情况"),
    "H": ("很脏", "图片不一样", "描述不符", "服务问题"),
    "I": ("日期订错", "房型订错", "改日期", "改房型", "改名"),
    "J": ("扣了两次", "重复扣款", "押金", "预授权"),
    "K": ("海外酒店", "代理", "跨境", "谁负责"),
    "L": ("公司订", "间房", "部分取消", "发票", "团体"),
}


def route_agent_message(message: str) -> Dict[str, Any]:
    normalized = "".join(message.lower().split())
    ranked = []
    for scenario_id, signals in SCENARIO_SIGNALS.items():
        hits = [signal for signal in signals if "".join(signal.lower().split()) in normalized]
        ranked.append((len(hits), scenario_id, hits))
    score, scenario_id, hits = max(ranked, key=lambda item: item[0])
    if score == 0:
        scenario_id, hits = "F", []
    return {
        "scenario_id": scenario_id,
        "confidence": 0.94 if score >= 2 else 0.78 if score == 1 else 0.52,
        "matched_signals": hits,
        "fallback_used": score == 0,
        "router": "DETERMINISTIC_MVP_ROUTER",
    }


app = FastAPI(
    title="去哪儿酒店退款智能客服 Mock API",
    version="0.1.0",
    description="求职作品演示接口。全部订单、政策、金额和处理结果均为 Mock。",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

registry = ToolRegistry()
workflow = ScenarioWorkflow(registry)
init_database()


def _context(value: ToolContextRequest) -> ToolContext:
    data = value.model_dump() if hasattr(value, "model_dump") else value.dict()
    return ToolContext(**data)


@app.get("/health")
def health() -> Dict[str, Any]:
    with connect() as connection:
        counts = {
            "scenarios": connection.execute("SELECT COUNT(*) FROM scenario_fixtures").fetchone()[0],
            "tools": connection.execute("SELECT COUNT(*) FROM tool_contracts").fetchone()[0],
        }
    return {"ok": True, "mock": True, "database": str(database_path()), **counts}


@app.post("/api/admin/reset")
def reset_database() -> Dict[str, Any]:
    path = init_database(reset=True)
    return {"ok": True, "mock": True, "database": str(path)}


@app.get("/api/scenarios")
def list_scenarios() -> Dict[str, Any]:
    with connect() as connection:
        scenarios = payload_rows(connection, "scenario_fixtures")
    return {"mock": True, "scenarios": scenarios}


@app.get("/api/scenarios/{scenario_id}")
def get_scenario(scenario_id: str) -> Dict[str, Any]:
    with connect() as connection:
        scenario = payload_row(connection, "scenario_fixtures", "scenario_id=?", (scenario_id.upper(),))
    if not scenario:
        raise HTTPException(status_code=404, detail="Unknown scenario")
    return {"mock": True, "scenario": scenario}


@app.post("/api/agent/message")
def handle_agent_message(request: AgentMessageRequest) -> Dict[str, Any]:
    routing = route_agent_message(request.message)
    if request.reset_database:
        init_database(reset=True)
    try:
        result = workflow.run(routing["scenario_id"])
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        "mock": True,
        "message": request.message,
        "routing": routing,
        "result": result.as_dict(),
    }


@app.post("/api/workflows/{scenario_id}/run")
def run_workflow(scenario_id: str, request: WorkflowRunRequest) -> Dict[str, Any]:
    if request.reset_database:
        init_database(reset=True)
    try:
        result = workflow.run(scenario_id.upper())
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"mock": True, "result": result.as_dict()}


@app.post("/api/tools/{tool_name}")
def call_tool(tool_name: str, request: ToolCallRequest) -> Dict[str, Any]:
    result = registry.execute(tool_name, request.arguments, _context(request.context))
    return result.as_dict()


@app.post("/api/confirmations")
def create_confirmation(request: ConfirmationRequest) -> Dict[str, Any]:
    try:
        token = registry.mint_confirmation(
            _context(request.context), request.tool_name, request.arguments, request.ttl_minutes
        )
    except ToolError as exc:
        raise HTTPException(status_code=412, detail={"code": exc.code, "message": exc.message}) from exc
    return {"ok": True, "confirmation_token": token, "expires_in_minutes": request.ttl_minutes}


@app.get("/api/cases/{case_id}")
def get_case(case_id: str) -> Dict[str, Any]:
    with connect() as connection:
        case = payload_row(connection, "cases", "case_id=?", (case_id,))
        events = payload_rows(connection, "case_events", "case_id=?", (case_id,)) if case else []
        external = payload_rows(connection, "external_cases", "case_id=?", (case_id,)) if case else []
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return {"mock": True, "case": case, "events": events, "external_cases": external}


@app.get("/api/traces/{trace_id}")
def get_trace(trace_id: str) -> Dict[str, Any]:
    with connect() as connection:
        rows = connection.execute(
            "SELECT request_json, response_json, tool_name, mode, occurred_at FROM tool_executions WHERE trace_id=? ORDER BY occurred_at",
            (trace_id,),
        ).fetchall()
    return {"mock": True, "trace_id": trace_id, "tool_executions": [
        {"tool_name": row["tool_name"], "mode": row["mode"], "request": json_load(row["request_json"]),
         "response": json_load(row["response_json"]), "occurred_at": row["occurred_at"]}
        for row in rows
    ]}


@app.get("/api/workflow-runs/{run_id}")
def get_workflow_run(run_id: str) -> Dict[str, Any]:
    with connect() as connection:
        run = connection.execute("SELECT * FROM workflow_runs WHERE run_id=?", (run_id,)).fetchone()
        steps = connection.execute("SELECT * FROM workflow_steps WHERE run_id=? ORDER BY sequence_no", (run_id,)).fetchall()
    if not run:
        raise HTTPException(status_code=404, detail="Workflow run not found")
    return {
        "mock": True,
        "run": {key: run[key] for key in run.keys() if key != "result_json"},
        "result": json_load(run["result_json"]) if run["result_json"] else None,
        "steps": [{
            "sequence_no": row["sequence_no"], "workflow_node": row["workflow_node"],
            "actor": row["actor"], "tool_name": row["tool_name"], "state_before": row["state_before"],
            "state_after": row["state_after"], "result": json_load(row["result_json"]),
            "occurred_at": row["occurred_at"],
        } for row in steps],
    }
