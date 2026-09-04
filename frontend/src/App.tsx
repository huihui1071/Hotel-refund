import { useEffect, useRef, useState, type ReactNode } from 'react'
import { runScenario } from './api'
import { badcases, funnel, metrics, scenarioGroups, scenarios } from './data'
import type { Metric, PageKey, RunResponse, Scenario, WorkflowStep } from './types'

const navItems: { id: PageKey; label: string }[] = [
  { id:'design', label:'Agent 设计' },
  { id:'simulation', label:'场景模拟' },
  { id:'dashboard', label:'运营看板' },
]

type FlowTone = 'agent' | 'tool' | 'guard' | 'memory'

function DiagramNode({
  left, top, role, type, title, children, tone, decision = false,
}: {
  left: number
  top: number
  role?: string
  type: string
  title: string
  children: ReactNode
  tone?: FlowTone
  decision?: boolean
}) {
  const content = (
    <>
      <div className="dnode-kicker">{role && <span>{role}</span>}<b>{type}</b></div>
      <h2>{title}</h2><p>{children}</p>
    </>
  )
  return (
    <article className={`dnode${decision ? ' decision' : ''}`} data-tone={tone} style={{ left, top }}>
      {decision ? <div className="dnode-content">{content}</div> : content}
    </article>
  )
}

function AgentDesign({ onStart }: { onStart: () => void }) {
  return (
    <>
      <section className="dflow-shell" aria-label="Agent 完整工作流程">
        <div className="dflow-toolbar">
          <div><strong>完整 Workflow</strong><p>从接收问题到业务闭环，包含权限门、判断、回环和三条执行路径</p></div>
          <div className="dflow-legend" aria-label="技术角色图例">
            <span className="dflow-key">LLM / 规则</span><span className="dflow-key" data-tone="tool">Tool</span>
            <span className="dflow-key" data-tone="guard">权限 / 人工</span><span className="dflow-key" data-tone="memory">Memory / Trace</span>
          </div>
        </div>
        <div className="dflow-viewport" tabIndex={0} aria-label="可滚动查看完整流程图">
          <div className="dflow-canvas">
            <div className="dflow-phase" style={{ top: 410 }}><span>02 · 核实订单与事实</span></div>
            <div className="dflow-phase" style={{ top: 990 }}><span>03 · 决策与路由</span></div>
            <div className="dflow-phase" style={{ top: 2160 }}><span>04 · 结果闭环</span></div>
            <svg className="dflow-lines" viewBox="0 0 1180 2460" aria-hidden="true">
              <defs><marker id="flow-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="context-stroke" /></marker></defs>
              <path data-tone="main" d="M590 122 V150"/><path data-tone="main" d="M590 242 V280"/><path data-tone="main" d="M590 372 V393"/>
              <path data-tone="main" d="M717 520 H770 V496 H810"/><text x="748" y="506">允许</text>
              <path data-tone="guard" d="M463 520 H28 V1756 H70"/><text x="34" y="540">拒绝</text>
              <path data-tone="main" d="M960 542 V580"/><path data-tone="main" d="M960 672 V698"/>
              <path data-tone="loop" d="M843 825 H380"/><text x="602" y="813">否</text>
              <path data-tone="loop" d="M80 806 H28 V520 H463"/>
              <path data-tone="main" d="M970 952 V975 H590 V973"/><text x="944" y="970">是</text>
              <path d="M463 1100 H190 V1230"/><text x="292" y="1088">只需查询</text>
              <path data-tone="main" d="M590 1227 V1240"/><text x="604" y="1233">可生成确定方案</text>
              <path data-tone="guard" d="M717 1100 H780 V1740 H717"/><text x="790" y="1120">需协同或高风险</text>
              <path d="M190 1322 V2236 H440"/>
              <path data-tone="main" d="M590 1332 V1370"/><path data-tone="main" d="M590 1462 V1500"/><path data-tone="main" d="M590 1592 V1623"/>
              <path data-tone="guard" d="M463 1740 H370"/><text x="395" y="1728">拒绝</text>
              <path data-tone="main" d="M590 1867 V1880"/><text x="604" y="1875">交易写入</text>
              <path data-tone="guard" d="M717 1740 H970 V1880"/><text x="825" y="1728">流程写入</text>
              <path data-tone="main" d="M590 1972 V2010"/><path data-tone="main" d="M590 2102 V2190"/>
              <path d="M970 1972 V2010"/><path d="M970 2102 V2140 H740 V2236"/>
              <path data-tone="main" d="M590 2282 V2320"/>
            </svg>

            <DiagramNode left={440} top={30} role="会话入口" type="Session Memory" title="接收用户问题">创建 <code>session_id</code> 与 <code>trace_id</code></DiagramNode>
            <DiagramNode left={440} top={150} role="理解层" type="LLM + 安全分类器" title="理解诉求与紧急度" tone="agent">意图、原因、风险、订单线索</DiagramNode>
            <DiagramNode left={440} top={280} role="订单选择组件" type="UI" title="用户确认唯一订单"><code>confirmed_order_id</code> 写入状态</DiagramNode>
            <DiagramNode left={500} top={430} type="READ Gate" title="是否允许读取？" tone="guard" decision>身份、归属、状态白名单、脱敏</DiagramNode>
            <DiagramNode left={810} top={450} role="查询类 Tool" type="READ" title="读取可信业务事实" tone="tool">订单、政策、退款、支付、工单、责任链</DiagramNode>
            <DiagramNode left={810} top={580} role="结构化过滤" type="RAG" title="匹配政策并辅助解释" tone="agent">RAG 不决定金额与权限</DiagramNode>
            <DiagramNode left={880} top={735} type="LLM + 必填规则" title="信息是否足够？" tone="agent" decision>只检查会改变结论的信息</DiagramNode>
            <DiagramNode left={80} top={760} role="对话补全" type="LLM + Session Memory" title="最少追问" tone="memory">只问会改变处理结论的信息，再回到读取权限门</DiagramNode>
            <DiagramNode left={500} top={1010} type="Rules + Workflow" title="选择处理路径" tone="agent" decision>规则决定金额、权限、风险和路由</DiagramNode>
            <DiagramNode left={40} top={1230} role="查询类 Tool" type="READ" title="查询当前业务状态" tone="tool">退款进度、支付事件、工单进度</DiagramNode>
            <DiagramNode left={440} top={1240} role="计算 / 决策 Tool" type="READ" title="生成可执行方案" tone="tool">退款报价、变更报价、保障预览、权限校验</DiagramNode>
            <DiagramNode left={440} top={1370} role="结构化组件" type="LLM" title="展示方案与预期" tone="agent">金额沿用 Tool 回执，LLM 只负责解释</DiagramNode>
            <DiagramNode left={440} top={1500} role="前端确认组件" type="安全机制" title="用户二次确认" tone="guard">明确金额、后果和操作对象</DiagramNode>
            <DiagramNode left={500} top={1650} type="WRITE Gate" title="允许改变业务状态？" tone="guard" decision>鉴权、状态、风险、确认、版本、幂等</DiagramNode>
            <DiagramNode left={70} top={1710} role="安全机制" type="Human-in-the-loop" title="阻断或转人工核验" tone="guard">不暴露订单，不把失败改写成成功</DiagramNode>
            <DiagramNode left={440} top={1880} role="交易写权限" type="WRITE Auth" title="校验确认、版本和风险" tone="guard"><code>confirmation_token</code> + <code>expected_version</code></DiagramNode>
            <DiagramNode left={440} top={2010} role="交易类 Tool" type="WRITE" title="执行取消或订单变更" tone="tool"><code>submit_cancellation</code> / <code>submit_order_change</code></DiagramNode>
            <DiagramNode left={820} top={1880} role="协同写权限" type="L3 / L4 硬转人工" title="允许创建协作任务" tone="guard">只能创建工单，不得裁决退款金额</DiagramNode>
            <DiagramNode left={820} top={2010} role="协同类 Tool" type="WRITE" title="创建并跟踪协作任务" tone="tool">供应商、支付调查、材料、人工专席</DiagramNode>
            <DiagramNode left={440} top={2190} role="事实校验器" type="Verifier + LLM" title="返回结果与下一步" tone="agent">校验金额、动作词、状态、SLA 与允许按钮</DiagramNode>
            <DiagramNode left={440} top={2320} role="案件持久化" type="Case Memory + Trace Log" title="保存案件状态" tone="memory">支持后续查询、恢复会话、审计和 Badcase 回放</DiagramNode>
          </div>
        </div>
        <div className="dflow-summary" aria-label="四层流程摘要">
          <div><span>01 理解</span><strong>识别诉求、原因和紧急度</strong></div>
          <div><span>02 核实</span><strong>确认订单并读取可信事实</strong></div>
          <div><span>03 决策</span><strong>规则选择查询、交易或协同</strong></div>
          <div><span>04 闭环</span><strong>校验结果并持久化案件</strong></div>
        </div>
      </section>
      <div className="page-action"><button className="primary" type="button" onClick={onStart}>开始场景模拟</button></div>
    </>
  )
}

function stepSummary(step: WorkflowStep) {
  const data = step.result as Record<string, unknown> | undefined
  if (typeof data?.summary === 'string') return data.summary
  if (step.tool_name) return `已执行 ${step.tool_name}，回执已记录`
  return `${step.state_before} → ${step.state_after}`
}

function Simulation() {
  const [selected, setSelected] = useState<Scenario>(scenarios.find((item) => item.id === 'F') ?? scenarios[0])
  const [run, setRun] = useState<RunResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [complete, setComplete] = useState(false)
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

  return (
    <>
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
      <label><span>退款类型</span><select><option>全部类型</option><option>取消与变更</option><option>退款与支付</option><option>履约与住宿</option><option>特殊审核</option></select></label>
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
  return <>
    <header className="app-header"><div className="brand"><span>旅</span><strong>酒店退款 Agent</strong></div><nav aria-label="主要页面">{navItems.map((item) => <button key={item.id} aria-current={page === item.id} onClick={() => setPage(item.id)}>{item.label}</button>)}</nav><div className="mock-badge">Mock 数据</div></header>
    <main>{page === 'design' && <AgentDesign onStart={() => setPage('simulation')} />}{page === 'simulation' && <Simulation />}{page === 'dashboard' && <Dashboard />}</main>
  </>
}
