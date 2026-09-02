import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api, auth, streamChat, Unauthorized } from './api/client'
import { ChatPanel } from './components/ChatPanel'
import { MerchantDashboard } from './components/MerchantDashboard'
import { AuditTrailView } from './components/AuditTrailView'
import { LoginPage } from './components/LoginPage'
import type { Approval, AuditEntry, ChatItem, Metrics, Order, UpsellProposal } from './types'

function sessionId(): string {
  const key = 'agent-till-session'
  let id = localStorage.getItem(key)
  if (!id) {
    id = `sess-${crypto.randomUUID().slice(0, 12)}`
    localStorage.setItem(key, id)
  }
  return id
}

type Tab = 'dashboard' | 'audit'

export default function App() {
  const session = useMemo(sessionId, [])
  const [token, setToken] = useState<string | null>(auth.token)
  const [merchant, setMerchant] = useState('')
  const [config, setConfig] = useState<{
    razorpay_key_id: string
    demo_merchant_email: string
    demo_merchant_password: string
    agent_enabled: boolean
  } | null>(null)

  const [items, setItems] = useState<ChatItem[]>([])
  const [busy, setBusy] = useState(false)
  const [tab, setTab] = useState<Tab>('dashboard')

  const [orders, setOrders] = useState<Order[]>([])
  const [audit, setAudit] = useState<AuditEntry[]>([])
  const [approvals, setApprovals] = useState<Approval[]>([])
  const [metrics, setMetrics] = useState<Metrics | null>(null)
  const [deciding, setDeciding] = useState<string | null>(null)

  const [upsell, setUpsell] = useState<UpsellProposal | null>(null)
  const [checkout, setCheckout] = useState<
    { razorpayOrderId: string; razorpayKeyId: string; amountInr: number } | null
  >(null)

  const cartRef = useRef<string[]>([])
  const lastIntentRef = useRef('')

  useEffect(() => {
    api.config().then(setConfig).catch(() => {})
  }, [])

  const signOut = useCallback(() => {
    auth.clear()
    setToken(null)
    setMerchant('')
  }, [])

  const refresh = useCallback(async () => {
    if (!token) return
    try {
      const [o, a, ap, m] = await Promise.all([
        api.orders(),
        api.auditLog(),
        api.approvals(),
        api.metrics(),
      ])
      setOrders(o)
      setAudit(a)
      setApprovals(ap)
      setMetrics(m)
    } catch (e) {
      // An expired session should return the operator to sign-in, not leave a dashboard that
      // silently stops updating.
      if (e instanceof Unauthorized) signOut()
    }
  }, [token, signOut])

  useEffect(() => {
    refresh()
    const t = setInterval(refresh, 3000)
    return () => clearInterval(t)
  }, [refresh])

  const maybeProposeUpsell = useCallback(async () => {
    if (cartRef.current.length === 0 || upsell) return
    try {
      const { proposal } = await api.upsell(session, cartRef.current, lastIntentRef.current)
      if (proposal) setUpsell(proposal)
    } catch {
      // An upsell is an enhancement, never a blocker on the purchase path.
    }
  }, [session, upsell])

  const send = useCallback(
    async (message: string) => {
      setBusy(true)
      lastIntentRef.current = message
      setItems((prev) => [...prev, { kind: 'user', text: message }])

      try {
        await streamChat(session, message, (event) => {
          if (event.type === 'text') {
            setItems((prev) => [...prev, { kind: 'agent', text: event.text }])
          } else if (event.type === 'tool_call') {
            setItems((prev) => [...prev, { kind: 'tool', name: event.name, input: event.input }])
          } else if (event.type === 'tool_result') {
            setItems((prev) => {
              const next = [...prev]
              for (let i = next.length - 1; i >= 0; i--) {
                const item = next[i]
                if (item.kind === 'tool' && item.name === event.name && item.result === undefined) {
                  next[i] = { ...item, result: event.result, isError: event.is_error }
                  break
                }
              }
              return next
            })

            if (event.name === 'create_payment_intent_tool' && !event.is_error) {
              try {
                const parsed = JSON.parse(event.result) as {
                  razorpay_order_id: string | null
                  razorpay_key_id: string
                  amount_inr: number
                }
                if (parsed.razorpay_order_id) {
                  setCheckout({
                    razorpayOrderId: parsed.razorpay_order_id,
                    razorpayKeyId: parsed.razorpay_key_id,
                    amountInr: parsed.amount_inr,
                  })
                }
              } catch {
                // Approval-gated intents have no payable order yet.
              }
            }

            if (event.name === 'get_product') {
              try {
                const parsed = JSON.parse(event.result) as { id?: string }
                if (parsed.id) cartRef.current = [...new Set([...cartRef.current, parsed.id])]
              } catch {
                /* not a single product */
              }
            }
          } else if (event.type === 'error') {
            setItems((prev) => [...prev, { kind: 'notice', text: event.message, tone: 'error' }])
          } else if (event.type === 'circuit_open') {
            setItems((prev) => [...prev, { kind: 'notice', text: event.message, tone: 'circuit' }])
          }
        })
      } catch {
        setItems((prev) => [
          ...prev,
          { kind: 'notice', text: 'Could not reach the assistant.', tone: 'error' },
        ])
      } finally {
        setBusy(false)
        refresh()
        maybeProposeUpsell()
      }
    },
    [session, refresh, maybeProposeUpsell],
  )

  const decide = async (approvalId: string, approve: boolean) => {
    setDeciding(approvalId)
    try {
      const result = await api.decideApproval(approvalId, approve)
      if (approve && result.razorpay_order_id) {
        setCheckout({
          razorpayOrderId: result.razorpay_order_id,
          razorpayKeyId: config?.razorpay_key_id ?? '',
          amountInr: result.amount_inr,
        })
      }
      setItems((prev) => [
        ...prev,
        approve
          ? { kind: 'agent', text: 'The merchant approved your order — you can pay below.' }
          : { kind: 'notice', text: 'The merchant denied this order.', tone: 'error' },
      ])
    } catch (e) {
      if (e instanceof Unauthorized) signOut()
    } finally {
      setDeciding(null)
      refresh()
    }
  }

  if (!token) {
    return (
      <LoginPage
        demoEmail={config?.demo_merchant_email ?? ''}
        demoPassword={config?.demo_merchant_password ?? ''}
        onAuthenticated={(t, name) => {
          auth.set(t)
          setToken(t)
          setMerchant(name)
        }}
      />
    )
  }

  return (
    <div className="relative flex h-screen flex-col bg-ink-900">
      <div className="aurora" />

      <header className="relative z-10 flex items-center gap-3 border-b border-line bg-ink-850/70 px-5 py-3 backdrop-blur-xl">
        <div className="glow-accent flex h-8 w-8 items-center justify-center rounded-lg bg-linear-to-br from-accent-soft to-rzp-blue text-sm font-bold text-white">
          ₹
        </div>
        <div>
          <h1 className="text-sm font-semibold tracking-tight text-text-hi">Agent Till</h1>
          <p className="text-[11px] text-text-low">
            The merchant till AI agents can use — and never overspend
          </p>
        </div>

        <div className="ml-auto flex items-center gap-2">
          <span className="hidden rounded-full border border-line bg-ink-800/70 px-2.5 py-1 font-mono text-[10px] text-text-mid sm:inline">
            {session}
          </span>
          <span className="rounded-full border border-mint/30 bg-mint/10 px-2.5 py-1 text-[10px] font-medium text-mint">
            {merchant || 'merchant'}
          </span>
          <button
            onClick={signOut}
            className="rounded-lg border border-line px-2.5 py-1 text-[11px] text-text-mid transition-colors hover:border-accent hover:text-text-hi"
          >
            Sign out
          </button>
        </div>
      </header>

      <main className="relative z-10 grid min-h-0 flex-1 grid-cols-1 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <section className="min-h-0 border-r border-line">
          <ChatPanel
            items={items}
            busy={busy}
            upsell={upsell}
            checkout={checkout}
            agentEnabled={config?.agent_enabled ?? true}
            onSend={send}
            onAddUpsell={(p) => {
              setUpsell(null)
              send(`Add the ${p.name} at the ${p.capped_discount_pct}% discount and check me out.`)
            }}
            onDismissUpsell={() => setUpsell(null)}
            onPaid={() => {
              setCheckout(null)
              setItems((prev) => [...prev, { kind: 'agent', text: 'Payment confirmed — thank you!' }])
              refresh()
            }}
            onFailed={(reason) => {
              setItems((prev) => [...prev, { kind: 'notice', text: reason, tone: 'error' }])
              refresh()
            }}
          />
        </section>

        <section className="flex min-h-0 flex-col bg-ink-850/40">
          <div className="flex gap-1 border-b border-line px-3 pt-2">
            {(['dashboard', 'audit'] as Tab[]).map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`rounded-t-lg px-3 py-2 text-xs font-medium transition-colors ${
                  tab === t
                    ? 'border-b-2 border-accent text-text-hi'
                    : 'text-text-low hover:text-text-mid'
                }`}
              >
                {t === 'dashboard' ? 'Merchant dashboard' : `Audit trail (${audit.length})`}
              </button>
            ))}
          </div>

          <div className="min-h-0 flex-1">
            {tab === 'dashboard' ? (
              <MerchantDashboard
                metrics={metrics}
                orders={orders}
                approvals={approvals}
                onDecide={decide}
                deciding={deciding}
              />
            ) : (
              <AuditTrailView entries={audit} />
            )}
          </div>
        </section>
      </main>
    </div>
  )
}
