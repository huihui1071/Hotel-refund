# A–L Mock 数据说明

本目录中的全部内容均为求职作品演示数据，不代表去哪儿真实订单、政策、接口、供应商、酒店或经营指标。

## 文件关系

```text
scenario-fixtures.json
  └─ scenario_id A–L
      ├─ users.json / user_id
      ├─ orders.json / order_id
      │   ├─ hotels.json / hotel_id
      │   ├─ suppliers.json / supplier_id
      │   ├─ policies.json / policy_id
      │   └─ payments.json / payment_id
      ├─ cases.json / case_id
      ├─ case-events.json（追加式事件和状态恢复起点）
      ├─ refunds.json / refund_id（存在或预期创建）
      ├─ external-cases.json（供应商、支付、人工专席）
      ├─ evidence.json（仅 G/H 场景）
      ├─ alternative-hotels.json（仅 D/E 场景）
      └─ tool-response-fixtures.json（确定性 Tool 返回）
```

## 初始数据与预期数据

- 没有 `fixture_phase` 的记录是场景开始前即可读取的初始数据。
- `expected_after_action` 表示执行写 Tool 后应创建的结果。
- `expected_after_submit`、`expected_after_supplier_offer`、`expected_on_sla_breach` 等用于演示指定分支或端到端断言，初始化数据库时不应全部直接写入当前态。

## 统一时间

- 默认演示基准时间：`2026-09-04T15:20:00+08:00`。
- D、E 等紧急场景可以使用各自脚本中的场景时间。
- 政策时点必须在订单的 `timezone` 中比较，然后再转为统一存储时间。

## 金额约束

- 金额均使用整数元以方便演示，实际实现建议使用最小货币单位整数。
- A：¥688 全退。
- B：¥1,200 中扣 ¥600、退 ¥600。
- F：供应商例外方案为退 ¥1,000，不能由 LLM 修改。
- I：改期补 ¥80；取消对比扣 ¥300。
- K：原交易币种为 USD，不在 LLM 中自行换算最终人民币退款。
- L：部分取消结果必须经过团体专席确认，响应 fixture 仅为预览。

## 隐私约束

- 不保存完整手机号、银行卡、证件号或验证码。
- 证据文件使用 Mock 引用或结构化元数据；原始敏感材料不进入 LLM 上下文。
- 订单历史和会话记忆不能替代当前身份及操作授权。

## 使用建议

1. 先加载没有 `fixture_phase` 的初始记录。
2. 根据 `scenario-fixtures.json` 选择场景和预期 Tool 顺序。
3. 写 Tool 成功后，从对应的预期 fixture 生成新记录并追加业务事件。
4. 对比 `success_assertions` 判断场景是否正确闭环。
5. 每个场景另设至少一条 Tool 失败、超时、越权或版本冲突用例。
