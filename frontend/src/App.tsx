import { FormEvent, useEffect, useRef, useState } from 'react'
import { checkApi, runMessage, runScenario } from './api'
import { badcases, funnel, metrics, scenarioGroups, scenarios, workflowBranches, workflowStages } from './data'
import type { Metric, PageKey, RunResponse, Scenario, WorkflowStep } from './types'

const navItems: { id: PageKey; label: string }[] = [
  { id:'design', label:'Agent 设计' },
  { id:'simulation', label:'场景模拟' },
  { id:'dashboard', label:'运营看板' },
]

function AgentDesign({ onStart }: { onStart: () => void }) {
  return (
    <section className="workflow-shell" aria-label="Agent 完整工作流程">
      <div className="workflow-toolbar">
        <div><strong>完整 Workflow</strong><p>从用户问题到可验证结果</p></div>
        <div className="legend" aria-label="技术角色图例">
          <span data-tone="agent">LLM / 规则</span><span data-tone="tool">Tool</span>
          <span data-tone="guard">权限 / 人工</span><span data-tone="memory">Memory / Trace</span>
        </div>
      </div>
      <div className="workflow-canvas">
        <div className="workflow-main">
          {workflowStages.map((stage, index) => (
            <div className="flow-step" key={stage.title}>
              <article className="flow-node" data-tone={stage.tone}>
                <div className="node-meta"><span>{String(index + 1).padStart(2, '0')}</span><b>{stage.type}</b></div>
                <h2>{stage.title}</h2><p>{stage.copy}</p>
              </article>
              {index < workflowStages.length - 1 && <span className="flow-arrow" aria-hidden="true">→</span>}
            </div>
          ))}
        </div>
        <div className="route-label"><span>规则命中后进入一条处理路径</span></div>
        <div className="branch-grid">
          {workflowBranches.map((branch) => (
            <article className="branch" key={branch.title}>
              <div><span className="mode-badge">{branch.mode}</span><h2>{branch.title}</h2></div>
              <p>{branch.copy}</p><strong>{branch.steps}</strong>
            </article>
          ))}
        </div>
        <div className="closure-row">
          <div><span>Verifier + LLM</span><strong>校验金额、状态、动作词与 SLA</strong></div>
          <span aria-hidden="true">→</span>
          <div><span>Case Memory + Trace Log</span><strong>保存状态、依据和工具审计</strong></div>
        </div>
      </div>
      <div className="page-action"><button className="primary" type="button" onClick={onStart}>开始场景模拟</button></div>
    </section>
  )
}

function stepSummary(step: WorkflowStep) {
  const data = step.result as Record<string, unknown> | undefined
  if (typeof data?.summary === 'string') return data.summary
  if (step.tool_name) return `已执行 ${step.tool_name}，回执已记录`
  return `${step.state_before} → ${step.state_after}`
}

function Simulation({ apiMode }: { apiMode: 'api' | 'browser-mock' }) {
  const [selected, setSelected] = useState<Scenario>(scenarios.find((item) => item.id === 'F') ?? scenarios[0])
  const [run, setRun] = useState<RunResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [complete, setComplete] = useState(false)
  const [message, setMessage] = useState('临时有事去不了了，酒店说不能退，能帮我争取吗？')
  const [notice, setNotice] = useState('')
  const initialized = useRef(false)

  async function executeScenario(scenario: Scenario) {
    setSelected(scenario); setLoading(true); setComplete(false); setNotice('')
    const response = await runScenario(scenario)
    setRun(response); setNotice(response.notice ?? ''); setLoading(false)
  }

  useEffect(() => {
    if (initialized.current) return
    initialized.current = true
    void executeScenario(selected)
  }, [])

  async function submitMessage(event: FormEvent) {
    event.preventDefault()
    if (message.trim().length < 2) return
    setLoading(true); setComplete(false); setNotice('')
    const response = await runMessage(message.trim())
    setSelected(response.scenario); setRun(response.run); setNotice(response.run.notice ?? ''); setLoading(false)
  }

  const shownMode = run?.mode ?? apiMode
  return (
    <>
      <form className="message-bar" onSubmit={submitMessage}>
        <label htmlFor="agent-message">模拟用户问题</label>
        <div><input id="agent-message" value={message} onChange={(event) => setMessage(event.target.value)} maxLength={500} /><button className="primary" disabled={loading}>{loading ? '处理中' : '发送'}</button></div>
        <span className="mode-note" data-mode={shownMode}>{shownMode === 'api' ? 'FastAPI Workflow' : 'GitHub Pages 浏览器 Mock'}</span>
      </form>
      {notice && <div className="inline-notice" role="status">{notice}</div>}
      <select className="mobile-scenario" aria-label="选择演示场景" value={selected.id} onChange={(event) => void executeScenario(scenarios.find((item) => item.id === event.target.value) ?? selected)}>
        {scenarios.map((item) => <option key={item.id} value={item.id}>{item.id} · {item.name}</option>)}
      </select>
      <section className="simulation-layout">
        <aside className="scenario-rail" aria-label="A 到 L 场景">
          {scenarioGroups.map((group) => <section key={group}><h2>{group}</h2>{scenarios.filter((item) => item.group === group).map((item) => (
            <button type="button" key={item.id} aria-current={selected.id === item.id} onClick={() => void executeScenario(item)}><span>{item.id}</span><strong>{item.name}</strong><small>{item.risk}</small></button>
          ))}</section>)}
        </aside>
        <section className="customer-panel" aria-label="C 端用户界面">
          <div className="panel-bar"><strong>用户体验</strong><span className="pill">{selected.goal}</span></div>
          <div className="customer-body" aria-live="polite">
            <div className="user-query">{selected.query}</div>
            {loading ? <div className="loading-block"><i/><i/><i/></div> : <>
              <article className="answer">
                <div className="answer-kicker"><span/><b>酒店售后 Agent</b><em>{complete ? '处理结果' : '已生成方案'}</em></div>
                <h2>{complete ? selected.resultTitle : selected.conclusion}</h2>
                <section className="solution-card" data-complete={complete}>
                  <div className="solution-head"><div><span>✓ {complete ? '处理结果' : '推荐方案'}</span><h3>{complete ? selected.afterTitle : selected.planTitle}</h3><p>{complete ? selected.resultCopy : selected.planCopy}</p></div><em>{complete ? '已提交' : selected.status}</em></div>
                  <div className="solution-facts">
                    <div><span>{selected.money[0]}</span><strong>{selected.money[1]}</strong></div>
                    <div><span>{selected.fee[0]}</span><strong>{selected.fee[1]}</strong></div>
                    <div><span>{complete ? '下次更新' : '方案影响'}</span><strong>{complete ? selected.update : selected.impact}</strong></div>
                  </div>
                  <p className="solution-note">ⓘ {complete ? '系统已记录本次操作，无需重复提交。' : selected.riskNote}</p>
                </section>
              </article>
              <div className="task-action"><button className="primary" type="button" disabled={complete} onClick={() => setComplete(true)}>{complete ? '已提交' : selected.action}</button></div>
            </>}
          </div>
        </section>
        <aside className="trace-panel" aria-label="Agent 决策轨迹">
          <div className="panel-bar"><strong>Agent 决策轨迹</strong><span className="pill">用户不可见</span></div>
          <div className="trace-list">
            {(run?.result.steps ?? []).map((step) => <article key={`${step.sequence_no}-${step.tool_name ?? step.workflow_node}`}>
              <span>{step.sequence_no}</span><div><strong>{step.tool_name || step.workflow_node}</strong><p>{stepSummary(step)}</p><em>{step.actor}</em></div>
            </article>)}
          </div>
        </aside>
      </section>
    </>
  )
}

function MetricTable() {
  const groups = ['全部', ...new Set(metrics.map((item) => item.group))]
  const [group, setGroup] = useState('全部')
  const visible = group === '全部' ? metrics : metrics.filter((item) => item.group === group)
  return <section className="dashboard-section"><div className="section-head"><h2>核心指标矩阵</h2><div className="metric-tabs">{groups.map((item) => <button key={item} aria-pressed={group === item} onClick={() => setGroup(item)}>{item}</button>)}</div></div><div className="table-scroll"><table><thead><tr><th>维度</th><th>指标</th><th>当前值</th><th>目标</th><th>环比</th><th>状态</th><th>诊断</th></tr></thead><tbody>{visible.map((metric: Metric) => <tr key={metric.name}><td>{metric.group}</td><td><strong>{metric.name}</strong></td><td>{metric.value}</td><td>{metric.target}</td><td>{metric.trend}</td><td><span className="status" data-status={metric.status}>{metric.status}</span></td><td>{metric.note}</td></tr>)}</tbody></table></div></section>
}

function Dashboard() {
  return <>
    <div className="dashboard-toolbar"><div className="filters">
      <label><span>时间</span><select><option>近 8 周</option><option>近 30 天</option><option>本周</option></select></label>
      <label><span>退款类型</span><select><option>全部 A–L 场景</option><option>取消与变更</option><option>退款与支付</option><option>履约与住宿</option><option>特殊审核</option></select></label>
      <label><span>供应商</span><select><option>全部供应商</option><option>平台直连</option><option>国内代理</option><option>海外供应商</option></select></label>
      <label><span>风险等级</span><select><option>全部风险等级</option><option>L0–L1</option><option>L2</option><option>L3–L4</option></select></label>
    </div><span className="data-note">模拟运营数据，不代表真实表现</span></div>
    <section className="overview"><div className="north-star"><span>北极星指标 · 近 8 周 · 环比 +2.8pp</span><strong>62.4%</strong><h2>正确退款任务闭环率</h2><p>结果、金额、权限和流程均正确，且取消、退款或明确替代方案得到系统或用户确认。</p><small>正确闭环 6,240　有效案件 10,000　目标 ≥65%</small></div><div className="health"><h2>本期健康结论</h2><p>整体闭环持续改善，但“业务状态完成 → 到账或结果确认”仍损失 530 件；一次解决率和人工改判率未达目标。</p><div><span>闭环率趋势<strong>连续 4 周改善</strong></span><span>最大环节流失<strong>协同未完成 1,310</strong></span><span>风险预警<strong>3 项超出目标</strong></span></div></div></section>
    <section className="dashboard-section"><div className="section-head"><h2>退款处理链路漏斗</h2><span>分母：10,000 个有效退款案件</span></div><div className="funnel">{funnel.map(([name,count,rate,loss]) => <div className="funnel-row" key={name}><strong>{name}</strong><div><i style={{width:rate}}/></div><b>{count}</b><span>{rate}</span><em>{loss}</em></div>)}</div></section>
    <MetricTable />
    <section className="dashboard-section"><div className="section-head"><h2>Badcase 闭环工作台</h2></div><div className="badcase-summary"><div><span>Badcase 闭环率</span><strong>78.6%</strong></div><div><span>逾期未修复问题</span><strong>7 个</strong></div><div><span>关闭后 14 天复发率</span><strong>4.1%</strong></div></div><div className="lifecycle">{['发现','归因','修复','回归验证','上线观察','关闭'].map((item,index) => <span key={item}>{String(index + 1).padStart(2,'0')}<strong>{item}</strong></span>)}</div><div className="table-scroll"><table><thead><tr><th>Badcase 类型</th><th>影响案件</th><th>风险</th><th>当前阶段</th><th>Owner</th><th>SLA</th></tr></thead><tbody>{badcases.map((item) => <tr key={item.type}><td><strong>{item.type}</strong></td><td>{item.count}</td><td>{item.risk}</td><td>{item.stage}</td><td>{item.owner}</td><td>{item.sla}</td></tr>)}</tbody></table></div></section>
  </>
}

export default function App() {
  const [page, setPage] = useState<PageKey>('design')
  const [apiMode, setApiMode] = useState<'api' | 'browser-mock'>('browser-mock')
  useEffect(() => { void checkApi().then(setApiMode) }, [])
  return <>
    <header className="app-header"><div className="brand"><span>旅</span><strong>酒店退款 Agent</strong></div><nav aria-label="主要页面">{navItems.map((item) => <button key={item.id} aria-current={page === item.id} onClick={() => setPage(item.id)}>{item.label}</button>)}</nav><div className="mock-badge">Mock 数据</div></header>
    <main>{page === 'design' && <AgentDesign onStart={() => setPage('simulation')} />}{page === 'simulation' && <Simulation apiMode={apiMode} />}{page === 'dashboard' && <Dashboard />}</main>
  </>
}
