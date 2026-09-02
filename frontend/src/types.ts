export type AgentEvent =
  | { type: 'text'; text: string }
  | { type: 'tool_call'; name: string; input: Record<string, unknown> }
  | { type: 'tool_result'; name: string; is_error: boolean; result: string }
  | { type: 'error'; message: string }
  | { type: 'circuit_open'; message: string }
  | { type: 'done' }

export type ChatItem =
  | { kind: 'user'; text: string }
  | { kind: 'agent'; text: string }
  | { kind: 'tool'; name: string; input: Record<string, unknown>; result?: string; isError?: boolean }
  | { kind: 'notice'; text: string; tone: 'error' | 'circuit' }

export interface Product {
  id: string
  name: string
  description: string
  price_inr: number
  category: string
  stock_qty: number
  tags: string[]
}

export interface OrderItem {
  name: string
  qty: number
  unit_price_inr: number
}

export interface Order {
  id: string
  session_id: string
  amount_inr: number
  discount_pct: number
  status: string
  created_at: string | null
  paid_at: string | null
  items: OrderItem[]
}

export interface AuditEntry {
  id: string
  ts: string | null
  correlation_id: string
  session_id: string
  actor: string
  action_type: string
  money_affecting: boolean
  decision: string
  explanation: string
  amount_inr: number | null
  order_id: string | null
  policy_snapshot: Record<string, unknown>
}

export interface Approval {
  id: string
  order_id: string
  session_id: string
  amount_inr: number
  reason: string
  created_at: string | null
}

export interface Metrics {
  orders_total: number
  orders_paid: number
  revenue_inr: number
  pending_approvals: number
  audit_entries: number
}

export interface UpsellProposal {
  product_id: string
  name: string
  list_price_inr: number
  discounted_price_inr: number
  requested_discount_pct: number
  capped_discount_pct: number
  was_capped: boolean
  rationale: string
  explanation: string
}
