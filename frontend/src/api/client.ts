import type { AgentEvent, Approval, AuditEntry, Metrics, Order, Product, UpsellProposal } from '../types'

const BASE = import.meta.env.VITE_API_BASE ?? ''

async function json<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
  })
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`)
  return res.json() as Promise<T>
}

export const api = {
  config: () =>
    json<{ razorpay_key_id: string; payments_live: boolean; agent_enabled: boolean }>('/api/config'),
  catalog: () => json<Product[]>('/api/catalog'),
  orders: () => json<Order[]>('/api/orders'),
  auditLog: () => json<AuditEntry[]>('/api/audit-log'),
  approvals: () => json<Approval[]>('/api/approvals'),
  metrics: () => json<Metrics>('/api/metrics'),

  decideApproval: (id: string, approve: boolean) =>
    json<{ status: string; razorpay_order_id: string | null; intent_id: string; amount_inr: number }>(
      `/api/approvals/${id}/decision`,
      { method: 'POST', body: JSON.stringify({ approve }) },
    ),

  upsell: (sessionId: string, cartProductIds: string[], intent: string) =>
    json<{ proposal: UpsellProposal | null }>('/api/upsell', {
      method: 'POST',
      body: JSON.stringify({
        session_id: sessionId,
        cart_product_ids: cartProductIds,
        buyer_intent_summary: intent,
      }),
    }),

  verifyPayment: (payload: {
    razorpay_order_id: string
    razorpay_payment_id: string
    razorpay_signature: string
  }) => json('/api/payments/verify', { method: 'POST', body: JSON.stringify(payload) }),

  reportFailed: (razorpayOrderId: string, reason: string) =>
    json('/api/payments/failed', {
      method: 'POST',
      body: JSON.stringify({ razorpay_order_id: razorpayOrderId, reason }),
    }),

  forceOutOfStock: (productId: string, demoKey: string) =>
    json(`/api/demo/force-out-of-stock/${productId}`, {
      method: 'POST',
      headers: { 'X-Demo-Key': demoKey },
    }),
}

/** Streams the agent's turn. Server-sent events are read off a POST body, which EventSource
 *  can't do (it's GET-only), so the stream is parsed manually. */
export async function streamChat(
  sessionId: string,
  message: string,
  onEvent: (event: AgentEvent) => void,
): Promise<void> {
  const res = await fetch(`${BASE}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, message }),
  })
  if (!res.ok || !res.body) throw new Error(`chat failed: ${res.status}`)

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    const chunks = buffer.split('\n\n')
    buffer = chunks.pop() ?? ''
    for (const chunk of chunks) {
      const line = chunk.split('\n').find((l) => l.startsWith('data: '))
      if (!line) continue
      try {
        onEvent(JSON.parse(line.slice(6)) as AgentEvent)
      } catch {
        // A partial frame can arrive mid-chunk; the next read completes it.
      }
    }
  }
}
