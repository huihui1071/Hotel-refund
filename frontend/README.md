# 酒店退款 Agent 前端

React + TypeScript + Vite 实现的三模块前端：Agent 设计、A–L 场景模拟、运营看板。

## 两种运行模式

- 本地联调：默认请求 `http://127.0.0.1:8000` 的 FastAPI Mock 后端，运行真实 SQLite、规则引擎、Tool 和 Workflow。
- GitHub Pages：静态环境自动使用同结构的浏览器 Mock Adapter，便于直接分享。界面持续显示 Mock 标识。

如需使用其他后端地址：

```bash
VITE_API_BASE_URL=http://127.0.0.1:8010 npm run dev
```

## 开发

```bash
npm install
npm run dev
```

## 验证

```bash
npm test
npm run build
```
