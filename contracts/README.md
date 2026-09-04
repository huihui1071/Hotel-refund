# Tool 与响应契约说明

## 文件

- `tool-contracts.json`：A–L 场景使用的 Tool 名称、读写属性、允许状态、输入、输出和拒绝条件。
- `tool-errors.json`：统一错误码，以及 Agent 面对每类错误时必须采取的动作。
- `agent-response.schema.json`：Agent 返回给前端的结构化协议。
- `case-event.schema.json`：案件追加事件协议，用于状态恢复、Trace 和后续指标计算。

## 边界

1. LLM 不直接读数据库，只能消费 Tool 返回的标准化结果。
2. 金额、政策、权限、业务状态和 SLA 由 Tool 或规则引擎返回。
3. 用户可见回复中的事实必须通过 `evidence_refs` 指回订单、政策、Tool 回执或案件事件。
4. `demo_trace` 只显示可审计决策依据，不输出模型隐性推理过程。
5. 所有写 Tool 均使用幂等键；结果未知时先查询 `get_action_result`。
6. 前端只能渲染 `allowed_actions` 中的操作，不能自行拼出退款或取消请求。

## 实现顺序

1. 先实现只读 Tool：订单、政策、退款、支付、责任链和拆分查询。
2. 再实现纯函数规则：退款报价、风险、SLA、变更和保障预览。
3. 然后实现写 Tool：取消、改期、工单、材料和人工移交。
4. 最后接入 Workflow、响应事实校验与前端组件渲染。
