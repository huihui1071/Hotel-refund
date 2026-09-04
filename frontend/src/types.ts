export type PageKey = 'design' | 'simulation' | 'dashboard'

export type Scenario = {
  id: string
  group: string
  name: string
  goal: string
  query: string
  conclusion: string
  money: [string, string]
  fee: [string, string]
  status: string
  update: string
  action: string
  route: string
  risk: string
  planTitle: string
  planCopy: string
  impact: string
  riskNote: string
  resultTitle: string
  afterTitle: string
  resultCopy: string
  trace: [string, string][]
}

export type WorkflowStep = {
  sequence_no: number
  workflow_node: string
  actor: string
  tool_name?: string | null
  state_before: string
  state_after: string
  result?: Record<string, unknown>
}

export type WorkflowResult = {
  run_id: string
  scenario_id: string
  route: string
  case_status: string
  waiting_for: string
  steps: WorkflowStep[]
  assertions: Record<string, boolean>
}

export type RunResponse = {
  result: WorkflowResult
  mode: 'api' | 'browser-mock'
  notice?: string
}

export type Metric = {
  group: string
  name: string
  value: string
  target: string
  trend: string
  status: '正常' | '关注' | '风险'
  note: string
}
