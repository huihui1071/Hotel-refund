# 酒店退款 Agent：技术选型与单 Agent Workflow

> 版本：v0.2  
> 日期：2026-09-04  
> 范围：求职作品集 MVP，全部订单、政策、供应商和支付能力均为 Mock  
> 架构原则：一个面向用户的 Agent，一套显式状态机，多类确定性业务工具

## 1. 技术方案结论

首版采用“单 Agent 编排 + 显式 Workflow + 确定性规则与工具”的架构，不采用多个 Agent 自主协商。

原因：

1. 酒店退款的核心复杂度来自订单状态、政策版本、金额、权限和多方 SLA，不来自需要多个角色自由讨论；
2. 单 Agent 更容易保证上下文连续、金额一致、可观测和可复现；
3. 多 Agent 会增加延迟、成本和结果不确定性，不利于 3 至 5 分钟稳定演示；
4. 面试官更需要看到清楚的业务边界，而不是看到复杂的 Agent 数量。

一句话架构：

> LLM 理解用户并组织表达，Workflow 决定下一步，规则引擎决定能不能做，Tool 负责真实状态读取与写入，人工处理例外和高风险。

## 2. 技术栈选型

### 2.1 推荐栈

| 层 | 选择 | 选择原因 | 暂不选择 |
| --- | --- | --- | --- |
| Web 前端 | React + TypeScript + Vite | 开发快、组件化清晰、适合响应式单页和演示部署 | 重型 SSR 框架，当前没有 SEO 需求 |
| 样式 | 原生 CSS + CSS variables | 无额外运行依赖，便于实现设计 token、响应式与状态样式 | 大型 UI 套件，容易形成模板感 |
| 无障碍基础 | 原生语义组件 | 处理焦点、键盘与交互语义 | 无语义的自造控件 |
| 数据请求 | 轻量 API Adapter | 本地 FastAPI 与 Pages 浏览器 Mock 共用响应结构 | 把请求状态散落在组件中 |
| Agent API | FastAPI + Pydantic | 结构化 schema、自动文档、异步接口和测试友好 | 把 Agent 逻辑直接写在前端 |
| Workflow | Python 显式状态机 | 支持状态、条件路由、检查点和人工中断 | 完全自由的 ReAct 循环 |
| 硬规则 | Python 纯函数 + 版本化规则配置 | 金额和权限可单测、可审计 | 让 LLM 直接计算退款金额 |
| 数据 | SQLite | 本地可运行、支持状态持久化和事务 | 纯前端写死 JSON 结果 |
| 政策检索 | 结构化过滤优先，轻量全文检索补充 | 只有 8 至 12 条模拟政策，不需要向量数据库 | 为展示 RAG 而引入复杂向量设施 |
| LLM | 当前使用确定性 Router，保留可替换 Provider 接口 | 无 Key 可复现，后续可接入结构化输出模型 | 业务代码与单一模型 SDK 深度耦合 |
| Eval | Pytest + JSONL 用例 + 自定义 grader | 可重复验证路由、工具、金额和承诺边界 | 只靠人工试玩 |
| 观测 | 结构化 trace 表 + 前端演示抽屉 | 能向面试官展示每一步依据 | 仅保存最终回答 |
| 部署 | 前后端 Docker 化，单服务或轻量双服务部署 | 易复现、易发链接 | 复杂微服务与消息中间件 |

### 2.2 为什么不做完全自主 ReAct Agent

完全自主 ReAct 适合开放任务，但退款是受约束交易。MVP 将 Agent 的可选动作限制在 Workflow 允许的节点中：

- 模型可以判断“用户可能在问退款进度”；
- 模型不能跳过订单确认直接退款；
- 模型可以生成供应商协商摘要；
- 模型不能决定供应商承担 ¥1,000；
- 模型可以解释支付状态；
- 模型不能把“退款已发起”改写成“已经到账”。

## 3. 系统边界

```text
浏览器
  C 端任务界面
  面试演示解释层
        │
        ▼
FastAPI Application
  会话接口
  Agent Orchestrator
  Workflow / State Machine
  Rule & Risk Engine
  Response Verifier
        │
        ├── Mock Order Service
        ├── Mock Policy Service
        ├── Mock Refund Service
        ├── Mock Supplier Case Service
        ├── Mock Hotel Recovery Service
        └── Mock Human Handoff Service
        │
        ▼
SQLite
  订单、案件、会话状态、退款、工单、trace、eval 结果
```

前端不能直接修改订单或退款状态。所有写操作必须经过后端 Workflow、规则校验和幂等检查。

## 4. 单 Agent 的职责

### 4.1 Agent 负责

- 理解用户自然语言；
- 判断主意图、次级原因和紧急程度；
- 从候选订单中引导用户确认唯一订单；
- 判断还缺少哪些会改变决策的信息；
- 调用只读工具获取订单、政策、退款和工单事实；
- 把规则引擎返回的方案解释成用户能理解的语言；
- 在获得显式确认后调用被授权的写工具；
- 生成供应商协商或人工转接摘要；
- 管理当前会话节奏和预期。

### 4.2 Agent 不负责

- 自行编造订单、政策或支付状态；
- 自行计算退款、扣款或赔付金额；
- 判断法律争议的最终责任；
- 绕过用户确认执行取消或退款；
- 将历史聊天记忆当作当前订单授权；
- 代表酒店、供应商或支付机构承诺结果；
- 处理真实银行卡、证件或医疗原文数据。

## 5. 统一 Workflow 状态

### 5.1 会话状态与业务状态分离

`conversation_state` 表示 Agent 当前要完成的交互步骤：

```text
START
INTENT_READY
ORDER_SELECTION_REQUIRED
ORDER_CONFIRMED
FACTS_REQUIRED
DECISION_READY
OPTION_PRESENTED
CONFIRMATION_REQUIRED
ACTION_IN_PROGRESS
WAITING_EXTERNAL
TRACKING_REFUND
RESOLVED
ESCALATED
ABANDONED
```

`case_status` 表示退款案件真实进展：

```text
NEW
ASSESSING
AWAITING_USER
AWAITING_SUPPLIER
SUPPLIER_RESPONDED
APPROVED
REJECTED
CANCELLATION_SUBMITTED
REFUND_INITIATED
PAYMENT_PROCESSING
REFUNDED
MANUAL_REVIEW
CLOSED
```

用户关闭页面只能改变会话状态，不能把真实案件标记为关闭。

### 5.2 Agent State schema

```json
{
  "session_id": "sess_xxx",
  "user_id": "usr_demo_01",
  "conversation_state": "ORDER_CONFIRMED",
  "case_id": "case_xxx",
  "confirmed_order_id": "QH-DEMO-001",
  "intent": {
    "primary": "CANCEL_REFUND",
    "reason": "PLAN_CHANGE",
    "urgency": "NORMAL",
    "requested_outcome": "FULL_REFUND",
    "confidence": 0.96
  },
  "slots": {
    "travel_started": false,
    "reason_code": "PLAN_CHANGE",
    "preferred_solution": "FULL_REFUND",
    "evidence_ids": []
  },
  "missing_slots": [],
  "facts": {
    "order_version": 3,
    "policy_id": "POL-HOTEL-CANCEL-003",
    "refund_id": null,
    "supplier_case_id": null
  },
  "risk": {
    "level": "L2",
    "reasons": ["NON_REFUNDABLE_POLICY", "SUPPLIER_CONFIRMATION_REQUIRED"]
  },
  "pending_confirmation": null,
  "last_tool_result_ids": [],
  "response_contract_version": "1.0"
}
```

## 6. 完整节点设计

### Node 0：入口与恢复

输入：用户新消息、登录态、可选 `session_id`。

动作：

- 恢复最近未结束会话；
- 检查是否存在待确认写操作；
- 如果用户切换话题，保留旧案件但创建新的任务上下文；
- 给每次请求生成 `trace_id`。

输出：可继续的 `AgentState`。

### Node 1：安全与越权预检

检查：

- 提示注入与要求绕过规则；
- 是否试图查询他人订单；
- 是否包含完整银行卡号、验证码等敏感信息；
- 是否涉及盗刷、人身安全、诉讼或媒体曝光；
- 是否需要立即人工升级。

决策：

- 安全可继续：进入意图理解；
- 需要脱敏：提示用户删除敏感内容后继续；
- L4 风险：停止自动操作并创建专席转接。

### Node 2：意图、原因与紧急度识别

LLM 按固定 schema 输出：

```json
{
  "primary_intent": "CANCEL_REFUND",
  "secondary_reason": "ILLNESS",
  "urgency": "HIGH",
  "requested_outcome": "FULL_REFUND",
  "order_clues": {
    "city": "杭州",
    "check_in_date": "2026-09-05"
  },
  "confidence": 0.91
}
```

路由规则：

- `FULFILLMENT_FAILURE + user_on_site=true`：直接进入紧急恢复分支；
- 置信度低于阈值：只澄清主任务，不查询全部系统；
- 同时包含多个诉求：确定一个主任务，其余存入 `secondary_tasks`。

### Node 3：订单解析与显式确认

1. 调用 `list_user_orders`；
2. 根据日期、城市和订单状态筛选候选；
3. 只有一个强匹配订单，也要向用户显示订单摘要并确认；
4. 多个候选订单时展示最多 3 个；
5. 用户确认后写入 `confirmed_order_id`；
6. 后续不允许 LLM 自行切换订单。

### Node 4：事实并行读取

确认订单后，并行调用：

- `get_order_detail`；
- `get_policy_snapshot`；
- `list_after_sale_events`；
- 若存在退款单，调用 `get_refund_status`；
- 若存在供应商工单，调用 `get_supplier_case`。

所有返回值进入 `facts`，LLM 只消费标准化摘要，不直接读取数据库。

### Node 5：信息完整度判断

以规则表而不是模型感觉决定必填项：

| 主意图 | 必填信息 |
| --- | --- |
| 条款内取消 | 已确认订单、当前时间、成交政策、支付状态 |
| 例外协商 | 上述信息 + 原因 + 用户期望方案 |
| 退款进度 | 已确认订单、退款单、退款发起时间、支付渠道 |
| 到店无房 | 已确认订单、是否已到店、酒店反馈、可联系号码 |

A–L 全场景的必填信息、逐步状态和 Tool 顺序见 `11-A-L场景端到端演示脚本与状态流转.md`。

一次最多追问两个问题。系统已有的信息禁止再次询问。

### Node 6：业务路由

```text
IF urgent fulfillment failure
  → D/E：紧急履约恢复
ELSE IF primary intent = REFUND_STATUS
  → C：退款进度
ELSE IF payment anomaly
  → J：支付/财务调查
ELSE IF primary intent = ORDER_CHANGE
  → I：变更与取消方案比较
ELSE IF special event or service dispute
  → G/H：必要材料 + 人工审核/酒店核实
ELSE IF cross-border, multi-supplier, corporate or group order
  → K/L：责任链/授权核对 + 专席
ELSE IF policy allows deterministic cancellation
  → A/B：确定性取消报价
ELSE IF cancellation requires supplier or manual exception
  → F：供应商例外协商
ELSE
  → Branch E：人工兜底
```

### Branch A：条款内取消

1. 调用 `calculate_refund_quote`；
2. 调用 `validate_action_permission`；
3. 输出金额、扣费、路径、到账时间和政策依据；
4. 创建带过期时间的 `pending_confirmation`；
5. 用户点击“确认取消”后再次校验订单版本和报价；
6. 调用 `submit_cancellation`；
7. 成功后创建退款单并进入进度页；
8. 超时或冲突时不重试写操作，先查询幂等结果。

### Branch B：不可取消订单例外协商

1. 明确告知“当前不能直接自动退款，可发起协商”；
2. 收集最少必要的原因和期望方案；
3. 调用 `build_supplier_case_draft` 生成结构化草稿；
4. 用户确认提交协商；
5. 调用 `create_supplier_case`；
6. 显示供应商 SLA、当前等待方和下一更新时间；
7. Mock 供应商返回后，调用 `get_supplier_case`；
8. 如果提供部分退款或改期，展示并列方案；
9. 用户确认选项后进入对应写操作；
10. 供应商拒绝或超时则创建人工复核。

### Branch C：退款进度

1. 调用 `get_refund_status`；
2. 将支付状态映射为用户语言；
3. 计算是否超出渠道 SLA；
4. SLA 内：显示当前阶段、预计最晚时间和通知选项；
5. SLA 外：调用 `create_payment_investigation`；
6. 不允许把 `REFUND_INITIATED` 表述为 `REFUNDED`。

### Branch D：到店无房或临时加价

1. 立即将风险设为 L3；
2. 创建加急案件，不等待普通多轮澄清完成；
3. 调用 `verify_fulfillment_issue`；
4. 并行调用 `get_alternative_hotels` 和 `create_human_handoff`；
5. 页面主目标变为“今晚先住下”；
6. 给出协调原酒店、替代住宿、取消并申请保障三类动作；
7. 退款与责任结算作为后续案件处理，不阻塞住宿恢复。

### Branch E：人工兜底

触发：身份冲突、政策缺失、高金额、服务事实冲突、欺诈、安全、法律争议、连续工具失败。

动作：

1. 生成结构化案件摘要；
2. 标注已确认事实、未知项、已调用工具和失败原因；
3. 创建人工工单；
4. 向用户显示为什么转人工、预计响应和下一更新时间；
5. 人工端可继续使用同一 `case_id`。

### Node 7：响应事实校验

在回复发送前检查：

- 回复中的金额是否全部来自最新 tool result；
- “已取消、已提交、已退款、已到账”等动作词是否有对应事件；
- 时间是否来自 SLA 规则；
- 政策引用是否属于当前订单版本；
- 下一步按钮是否与当前状态允许动作一致；
- 是否泄露内部 prompt、风险规则或其他用户信息。

失败则使用安全模板重新生成，不把未校验回答发送给用户。

### Node 8：状态持久化与观测

每轮保存：

- 状态进入和离开时间；
- 意图与置信度；
- 订单确认事件；
- 工具调用参数摘要、状态码和耗时；
- 使用的政策版本；
- 风险决策与原因；
- 用户确认事件；
- 最终响应中的事实引用；
- 是否转人工及转人工原因。

## 7. Tool 设计

A–L 场景共用的完整 Tool 机器可读契约、错误码和前端响应 schema 位于 `contracts/`；本节保留核心工具的说明性摘要。

### 7.1 设计规范

- 一工具一职责；
- 工具名表达业务动作，不表达页面动作；
- 读写工具分离；
- 写工具必须有鉴权、幂等键、预期版本和确认 token；
- Tool 只返回结构化结果，不返回可直接展示的长文案；
- 错误码区分“不可重试”“可重试”“结果未知”；
- LLM 不能直接访问数据库。

### 7.2 统一返回 envelope

```json
{
  "ok": true,
  "code": "OK",
  "data": {},
  "source": "mock-refund-service",
  "occurred_at": "2026-09-04T15:20:00+08:00",
  "trace_id": "tr_xxx",
  "retryable": false
}
```

### 7.3 只读工具

#### `list_user_orders`

```json
{
  "user_id": "usr_demo_01",
  "status_filter": ["CONFIRMED", "CANCELLED", "REFUND_PROCESSING"],
  "city": "杭州",
  "check_in_from": "2026-09-01",
  "check_in_to": "2026-09-30"
}
```

只返回用户有权查看的脱敏订单摘要。

#### `get_order_detail`

输入：`order_id`, `user_id`。  
输出：订单状态、房型、日期、渠道、供应商、金额、支付概要和版本号。

#### `get_policy_snapshot`

输入：`order_id`。  
输出：成交时政策 ID、版本、截止时间、扣费表达式、提示证据和用户展示文本。

#### `calculate_refund_quote`

输入：

```json
{
  "order_id": "QH-DEMO-002",
  "order_version": 2,
  "request_time": "2026-09-04T15:20:00+08:00",
  "reason_code": "PLAN_CHANGE"
}
```

输出：

```json
{
  "quote_id": "qt_001",
  "expires_at": "2026-09-04T15:30:00+08:00",
  "paid_amount": 688,
  "refund_amount": 688,
  "cancellation_fee": 0,
  "currency": "CNY",
  "refund_route": "WECHAT_ORIGINAL_ROUTE",
  "estimated_arrival": "1-3 business days",
  "policy_id": "POL-HOTEL-CANCEL-001",
  "requires_human": false
}
```

#### `get_refund_status`

输出状态限定为：

```text
NOT_CREATED
PENDING_APPROVAL
REFUND_INITIATED
CHANNEL_PROCESSING
REFUNDED
FAILED
STATUS_UNKNOWN
```

#### `get_supplier_case`

返回协商状态、等待方、SLA、回复方案和有效期。

#### `get_alternative_hotels`

返回同日期、附近、同等级的模拟替代酒店。MVP 不完成真实预订。

### 7.4 写工具

#### `submit_cancellation`

必填：`order_id`, `expected_order_version`, `quote_id`, `confirmation_token`, `idempotency_key`。

拒绝条件：报价过期、订单版本变化、用户未确认、身份不匹配、风险等级高于 L1、重复退款处理中。

#### `create_supplier_case`

必填：订单、原因代码、用户期望、事实摘要、材料 ID、用户提交确认。

输出：`supplier_case_id`, `status`, `response_due_at`, `waiting_for`。

#### `create_payment_investigation`

只在超过支付 SLA、渠道失败或状态未知时可调用。

#### `create_human_handoff`

输入必须包含：

- 订单与案件；
- 用户目标；
- 已确认事实；
- 未确认事实；
- 命中政策；
- 已执行动作；
- 风险级别与原因；
- 推荐下一步。

## 8. 记忆设计

### 8.1 四类“记忆”必须分开

| 类型 | 内容 | 存储 | 生命周期 | 可否影响退款决定 |
| --- | --- | --- | --- | --- |
| 当前轮上下文 | 最近消息、当前问题 | 请求内存 | 单次请求 | 仅用于理解语言 |
| 会话工作记忆 | 已确认订单、意图、槽位、待确认动作 | `conversation_state` | 会话结束后短期保留 | 可以，但必须来自显式确认或工具 |
| 案件业务记忆 | 工单、退款、供应商回复、状态事件 | 业务表 | 跟随案件审计周期 | 可以，是事实来源 |
| 用户偏好记忆 | 常用语言、是否希望短信通知 | 用户设置表 | 用户可查看和删除 | 不能决定金额、权限或目标订单 |

政策库不是记忆，订单历史也不是模型长期记忆。它们属于按权限查询的业务数据。

### 8.2 不做向量化长期聊天记忆

MVP 不把所有历史对话嵌入向量库，原因：

- 退款判断依赖当前订单事实，不依赖“模型记得用户以前说过什么”；
- 历史摘要可能过期或属于另一笔订单；
- 长期语义记忆增加隐私与错误关联风险；
- 作品集需要证明边界意识，而非展示所有技术组件。

### 8.3 记忆写入规则

只有以下内容可以写入结构化记忆：

- 用户显式确认的订单；
- Tool 返回的订单、政策、退款与工单事实；
- 用户明确表达的退款原因和期望方案；
- 已完成的确认、提交和转人工事件；
- 可撤销的通知偏好。

不得把模型推断的身份、责任或退款金额写成事实。

### 8.4 记忆冲突处理

优先级：

```text
最新业务 Tool 结果
> 用户在当前会话中的显式确认
> 当前案件历史事件
> 会话摘要
> 用户偏好
```

如果订单版本变化、用户说法与系统状态冲突或供应商返回更新，必须重新进入事实读取节点。

### 8.5 会话恢复

重新进入时只恢复：

- 当前案件一句话摘要；
- 已确认订单；
- 当前真实状态；
- 等待对象与下一更新时间；
- 尚未完成的用户动作。

不会自动恢复一个已过期的“确认取消”按钮；写操作 confirmation token 必须失效并重新生成。

## 9. RAG 与政策设计

### 9.1 采用结构化过滤优先

检索顺序：

1. 用 `order_id` 找到成交时 `policy_id`；
2. 按 `policy_id + version` 获取结构化规则；
3. 需要解释时才检索对应用户展示片段；
4. 找不到精确版本时禁止回退到“相似政策”做自动决策；
5. 政策缺失直接转人工。

### 9.2 RAG 只负责解释

RAG 可以回答：为什么会扣首晚、退款预计多久到账、到店无房需要哪些信息。

RAG 不可以决定：这笔订单退 ¥688、用户是否有操作权限、供应商是否已经同意、资金是否到账。

## 10. Prompt 结构

系统 prompt 建议分为五段：

1. 角色：代表模拟平台售后，目标是推进任务；
2. 事实原则：只使用 state 和 tool result；
3. Workflow 原则：遵守当前允许节点和动作；
4. 风险规则：资金、权限、高风险和转人工；
5. 输出契约：结构化 `message + ui_blocks + next_actions + citations`。

推荐响应 schema：

```json
{
  "message": "这笔订单仍在免费取消期内，可以退回 ¥688。",
  "ui_blocks": [
    {
      "type": "REFUND_QUOTE",
      "source_result_id": "tool_result_qt_001"
    }
  ],
  "next_actions": [
    {
      "action": "REQUEST_CANCELLATION_CONFIRMATION",
      "label": "确认取消并退款"
    },
    {
      "action": "KEEP_ORDER",
      "label": "保留订单"
    }
  ],
  "expectation": {
    "waiting_for": "USER",
    "next_update_at": null
  }
}
```

卡片中的金额和状态由前端通过 `source_result_id` 读取工具结果渲染，不从自由文本解析。

## 11. 预期管理的技术契约

每次状态回复必须包含：

```json
{
  "confirmed_fact": "平台已于 9 月 2 日 14:30 发起退款",
  "current_state": "CHANNEL_PROCESSING",
  "waiting_for": "微信支付渠道",
  "next_update_at": "2026-09-05T18:00:00+08:00",
  "user_action_required": false,
  "fallback_after_deadline": "自动创建支付调查工单"
}
```

如果任一字段未知，显式返回 `null + unknown_reason`，禁止用模糊文案掩盖。

## 12. 错误与降级

| 错误 | Agent 行为 | 用户表达 |
| --- | --- | --- |
| 订单服务超时 | 自动重试一次，只读失败后转人工 | 当前无法读取订单，不会替你执行取消 |
| 政策版本缺失 | 禁止计算和写操作 | 暂时无法确认这笔订单成交时的规则，已转人工核实 |
| 金额工具失败 | 不展示模型估算金额 | 当前无法给出可靠退款金额 |
| 写操作超时 | 先查幂等结果，不直接重试 | 提交结果仍在确认，不会重复扣款或退款 |
| 支付状态未知 | 创建支付调查或人工工单 | 当前无法确认资金状态，已升级查询 |
| LLM 不可用 | 预置场景走规则模板 | 仍可完成订单选择、报价、确认和进度查询 |

## 13. 数据表建议

```text
users
orders
order_policy_snapshots
payments
refunds
cases
case_events
supplier_cases
conversations
conversation_states
tool_executions
agent_traces
human_handoffs
eval_cases
eval_runs
```

所有重要状态变化采用追加事件，当前状态可以物化，但不可只保存最终值。

## 14. Eval 与验收

### 14.1 分层评测

| 层 | 评测内容 | 方法 |
| --- | --- | --- |
| 单元测试 | 退款金额、时点、SLA、权限、幂等 | Python 规则测试 |
| Tool 契约 | schema、错误码、鉴权、版本冲突 | API 测试 |
| Workflow | 节点和分支是否正确 | 固定状态轨迹断言 |
| LLM | 意图、槽位、摘要、解释 | JSONL 回归集 + 人工抽检 |
| 安全 | 越权、提示注入、敏感信息、错误承诺 | 对抗用例 |
| 端到端 | A–L 十二个演示场景 | 浏览器自动化与人工验收 |

### 14.2 发布阻断项

以下任一出现即阻断演示版本：

- 未确认订单就执行写操作；
- 退款金额与规则工具返回不一致；
- 重复点击产生两笔退款；
- 将“已发起”显示为“已到账”；
- L3/L4 场景未转人工；
- 工具失败后声称操作成功；
- 未标注 Mock 或暗示真实去哪儿系统连接。

## 15. 面试展示时如何讲技术选型

建议用 40 秒表达：

> 我没有把它设计成一个完全自主的聊天机器人，而是单 Agent 加显式状态机。模型负责理解用户和解释结果，退款金额、权限、状态流转都由可测试的规则和 Tool 决定。记忆也只保存已确认订单、结构化槽位和业务事件，不让历史聊天替代当前授权。这样既能完成低风险退款，又能在不可取消协商、到店无房或支付异常时稳定转人工，同时每一步都有 trace 可回放。

这段表达能够同时体现 Agent 能力、工程可行性和产品风险意识。
