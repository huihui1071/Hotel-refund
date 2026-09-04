# Mock 后端运行说明

本目录是去哪儿酒店退款智能客服作品集 MVP 的可执行后端。全部订单、政策、金额、供应商回复和处理结果均为 Mock，不代表去哪儿真实业务。

## 已实现

- SQLite Schema：订单、政策、支付、退款、案件、证据、外部工单、Session、确认令牌、幂等记录、Workflow Run、Step Trace 和 Tool 审计。
- 33 个 Tool 的统一 Registry 与契约校验。
- 读取权限：登录身份、显式订单确认、订单归属、Workflow 状态白名单。
- 写入权限：风险边界、用户确认令牌、订单版本和幂等键。
- 确定性规则：免费取消、阶梯扣费、支付预授权解释、风险与场景路由。
- A–L 十二条可执行 Workflow。
- FastAPI Mock API 与 OpenAPI 文档。
- 61 项数据库、规则、权限、API、Workflow 与离线 Eval 自动化测试。
- 自然语言 MVP Router：将用户问题映射到 A–L 场景并执行同一套 Workflow。

## 启动

```bash
cd /Users/huihuibuhui/Documents/my求职/去哪儿/backend
UV_CACHE_DIR=/tmp/qunar-uv-cache /Users/huihuibuhui/.local/bin/uv sync --extra dev
.venv/bin/python -m app.cli init-db --reset
.venv/bin/uvicorn app.main:app --reload --port 8000
```

打开：

- API 文档：`http://127.0.0.1:8000/docs`
- 健康检查：`http://127.0.0.1:8000/health`

## 运行场景

运行单个场景：

```bash
.venv/bin/python -m app.cli run-scenario A --reset
```

运行 A–L 全部场景：

```bash
.venv/bin/python -m app.cli run-all --reset
```

通过 API 运行：

```bash
curl -X POST http://127.0.0.1:8000/api/workflows/A/run \
  -H 'Content-Type: application/json' \
  -d '{"reset_database":true}'
```

## 主要接口

| 方法 | 路径 | 作用 |
| --- | --- | --- |
| `GET` | `/health` | 查看数据库、场景数和 Tool 数 |
| `GET` | `/api/scenarios` | 获取 A–L 演示场景 |
| `POST` | `/api/agent/message` | 接收自然语言问题、路由场景并执行 Workflow |
| `POST` | `/api/workflows/{scenario_id}/run` | 执行一条完整 Workflow |
| `GET` | `/api/workflow-runs/{run_id}` | 获取节点级 Trace |
| `POST` | `/api/tools/{tool_name}` | 经权限网关调用单个 Tool |
| `POST` | `/api/confirmations` | 为高影响动作签发短时确认令牌 |
| `GET` | `/api/cases/{case_id}` | 查询案件、事件和外部协同状态 |
| `GET` | `/api/traces/{trace_id}` | 查询 Tool 执行审计 |
| `POST` | `/api/admin/reset` | 恢复完整演示初始数据 |

## 测试

```bash
.venv/bin/pytest -q
```

预期结果：`61 passed`。

## 实现边界

- `app/workflow.py` 是显式状态机和 A–L 演示编排，不是自由 ReAct 循环。
- `app/rules.py` 负责金额、风险和支付语义等确定性判断。
- `app/tools.py` 是 Tool Access Gateway、33 个 Tool Handler、写入事务和审计入口。
- `app/db.py` 负责 Schema 初始化，并严格区分初始数据与 `expected_after_*` 预期 fixture。
- 前端只能展示 Tool 回执中的金额和状态，并只能提交后端允许的动作。
