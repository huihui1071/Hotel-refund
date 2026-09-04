# 离线 Eval

`agent-eval-cases.json` 包含 36 条中文用户表达，覆盖 A–L 十二类场景，每类 3 条。

当前自动评测：

- 场景路由准确率；
- A–L 覆盖完整性；
- 风险等级标注存在性；
- Workflow 最终状态与 Tool 序列，由 `backend/tests/test_workflows.py` 验证。

运行：

```bash
cd backend
.venv/bin/pytest -q
```

真实 LLM Provider 接入后，可在同一数据集上增加结构化字段准确率、必需事实召回率、承诺失真和该转人工未转等评测。
