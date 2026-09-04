# 去哪儿酒店退款智能客服 Agent MVP

一个面向酒店售后退款场景的非官方、全链路 Mock MVP：Agent 代表模拟的酒店售后团队，在订单事实、成交政策、责任主体和权限边界明确后，用尽可能少的交互给出结论与可执行方案，并把任务推进到可验证结果。

[在线体验](https://huihui1071.github.io/Hotel-refund/) · [查看 Agent Workflow](./docs/02-Agent-Workflow与Tool权限.md) · [查看模拟场景与 Eval](./docs/03-A-L场景与Eval.md)

> 免责声明：本项目是个人产品设计与工程验证作品，不是去哪儿官方产品。订单、政策、供应商、接口、金额和运营指标均为 Mock，不代表任何真实用户或企业内部数据。

## 为什么做

酒店退款的难点通常不是“解释一条规则”，而是同时处理订单事实、成交时政策、供应商协作、支付状态和操作授权。这个 MVP 验证一套可控的 Agent 方案：让 LLM 负责理解与表达，让规则引擎决定金额和路径，让 Tool 在权限网关内读取或执行，并用状态机、记忆和审计保证结果可恢复、可验证。

## 三个核心能力

1. **结论与行动优先**：用户侧只展示能否处理、金额影响、下一步与预计时间，不暴露内部推理和审计过程。
2. **受控 Agent Workflow**：单 Agent 编排 LLM、规则引擎、33 个 Tool、权限门、Session/Case Memory 与 Trace；金额、状态和权限不由模型自由生成。
3. **从场景到运营闭环**：覆盖十二类模拟退款及履约异常，使用 36 条离线 Eval、链路漏斗、核心指标和 Badcase 生命周期验证质量。

## 3 分钟浏览路线

1. **第 0–1 分钟：**打开[在线体验](https://huihui1071.github.io/Hotel-refund/)，先看 Agent 整体链路与职责边界。
2. **第 1–2 分钟：**进入“场景模拟”，建议选择 F「不可取消例外协商」、A「免费取消」或 E「到店无房」，观察结论、方案、确认和状态变化。
3. **第 2–3 分钟：**进入“运营看板”，检查北极星指标、处理漏斗、核心指标和 Badcase 闭环是否形成完整运营机制。

继续深入时，推荐按以下四份终稿阅读：

| 主题 | 重点 |
| --- | --- |
| [产品与需求分析](./docs/01-产品与需求分析.md) | 问题定义、用户场景、MVP 边界与产品决策 |
| [Agent Workflow 与 Tool 权限](./docs/02-Agent-Workflow与Tool权限.md) | 节点、技术角色、Tool 契约、权限和记忆设计 |
| [模拟场景与 Eval](./docs/03-A-L场景与Eval.md) | 十二类端到端场景、风险分层和验证方式 |
| [运营指标与 Badcase 闭环](./docs/04-运营指标与Badcase闭环.md) | 北极星、过程漏斗、风险指标与问题修复机制 |

## 当前可验证实现

- `frontend/`：React + TypeScript + Vite 三模块界面；GitHub Pages 使用同结构的浏览器端确定性 Mock Adapter。
- `backend/`：FastAPI、SQLite、规则引擎、显式 Workflow、Tool 权限网关与审计。
- `contracts/`：33 个 Tool 契约、统一错误码、Agent 响应和案件事件 Schema。
- `mock/`：模拟场景所需的订单、政策、支付、退款、供应商和预期结果。
- `eval/`：36 条中文路由评测，每个场景 3 条；后端共 61 项自动化测试。
- `.github/workflows/`：每次推送自动执行前后端测试、构建并发布 GitHub Pages。

在线版用于免安装体验；本地版会真实执行仓库内的 SQLite、规则、Tool 与 Workflow。两种模式都只处理 Mock 数据。

## 本地运行

后端：

```bash
cd backend
UV_CACHE_DIR=/tmp/hotel-refund-uv-cache uv sync --extra dev
.venv/bin/python -m app.cli init-db --reset
.venv/bin/uvicorn app.main:app --reload --port 8000
```

前端：

```bash
cd frontend
npm install
npm run dev
```

验证：

```bash
cd backend && .venv/bin/pytest -q
cd ../frontend && npm test && npm run build
```

## 设计边界

- 这是确定性业务 Workflow，不是让模型自主决定金额和操作的自由 ReAct Agent。
- LLM 只负责意图理解、信息抽取和用户表达；金额、政策、权限、状态与 SLA 来自规则或 Tool。
- 高影响写操作需要显式确认、幂等键和版本校验；高风险、证据争议及跨境/团体订单升级人工。
- 用户界面只展示结论与可执行方案；证据引用和 Trace 仅用于演示验证、质检和审计。
