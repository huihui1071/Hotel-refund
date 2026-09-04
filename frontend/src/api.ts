import { matchScenario, scenarios } from './data'
import type { RunResponse, Scenario, WorkflowResult, WorkflowStep } from './types'

const configuredBase = import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, '')
const apiBase = configuredBase || (import.meta.env.DEV ? 'http://127.0.0.1:8000' : '')

const caseStatus: Record<string, string> = {
  A:'REFUND_INITIATED', B:'REFUND_INITIATED', C:'AWAITING_PAYMENT', D:'RECOVERY_IN_PROGRESS',
  E:'RECOVERED', F:'REFUND_INITIATED', G:'MANUAL_REVIEW', H:'MANUAL_REVIEW', I:'CHANGED',
  J:'MANUAL_REVIEW', K:'AWAITING_SPECIALIST', L:'AWAITING_SPECIALIST',
}

const waitingFor: Record<string, string> = {
  A:'PAYMENT_CHANNEL', B:'PAYMENT_CHANNEL', C:'PAYMENT_CHANNEL', D:'URGENT_SPECIALIST',
  E:'NONE', F:'PAYMENT_CHANNEL', G:'EXCEPTION_REVIEWER', H:'SERVICE_SPECIALIST', I:'NONE',
  J:'FINANCE_SPECIALIST', K:'CROSS_BORDER_SPECIALIST', L:'CORPORATE_SPECIALIST',
}

function mockWorkflow(scenario: Scenario): WorkflowResult {
  const steps: WorkflowStep[] = scenario.trace.map(([actor, copy], index) => ({
    sequence_no: index + 1,
    workflow_node: index === 0 ? 'INTENT_AND_ROUTE' : actor.includes('Tool') ? 'TOOL_EXECUTION' : 'WORKFLOW_ROUTE',
    actor,
    tool_name: actor.includes('Tool') ? actor.replace(' Tool', '').toLowerCase().replaceAll(' ', '_') : null,
    state_before: index === 0 ? 'START' : `STEP_${index}`,
    state_after: index === scenario.trace.length - 1 ? caseStatus[scenario.id] : `STEP_${index + 1}`,
    result: { summary: copy, mock: true },
  }))
  return {
    run_id: `browser_${crypto.randomUUID()}`,
    scenario_id: scenario.id,
    route: scenario.route,
    case_status: caseStatus[scenario.id],
    waiting_for: waitingFor[scenario.id],
    steps,
    assertions: { expected_route: true, expected_case_status: true, tool_sequence: true },
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBase}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  })
  if (!response.ok) throw new Error(`API ${response.status}`)
  return response.json() as Promise<T>
}

export async function runScenario(scenario: Scenario): Promise<RunResponse> {
  if (!apiBase) {
    await new Promise((resolve) => setTimeout(resolve, 420))
    return { result: mockWorkflow(scenario), mode: 'browser-mock' }
  }
  try {
    const payload = await request<{ result: WorkflowResult }>(`/api/workflows/${scenario.id}/run`, {
      method: 'POST',
      body: JSON.stringify({ reset_database: true }),
    })
    return { result: payload.result, mode: 'api' }
  } catch {
    return {
      result: mockWorkflow(scenario),
      mode: 'browser-mock',
      notice: 'FastAPI 未启动，已切换为同结构浏览器 Mock。',
    }
  }
}

export async function runMessage(message: string): Promise<{ scenario: Scenario; run: RunResponse }> {
  const localMatch = matchScenario(message)
  if (!apiBase) return { scenario: localMatch, run: await runScenario(localMatch) }
  try {
    const payload = await request<{ routing: { scenario_id: string }; result: WorkflowResult }>('/api/agent/message', {
      method: 'POST',
      body: JSON.stringify({ message, reset_database: true }),
    })
    const scenario = scenarios.find((item) => item.id === payload.routing.scenario_id) ?? localMatch
    return { scenario, run: { result: payload.result, mode: 'api' } }
  } catch {
    return {
      scenario: localMatch,
      run: {
        result: mockWorkflow(localMatch),
        mode: 'browser-mock',
        notice: 'FastAPI 未启动，已使用浏览器端确定性路由完成演示。',
      },
    }
  }
}

export async function checkApi(): Promise<'api' | 'browser-mock'> {
  if (!apiBase) return 'browser-mock'
  try {
    await request('/health')
    return 'api'
  } catch {
    return 'browser-mock'
  }
}
