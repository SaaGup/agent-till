import type { Approval, Metrics, Order } from '../types'
import { inr } from '../format'
import { Tilt } from './Tilt'

const STATUS_STYLES: Record<string, string> = {
  paid: 'bg-mint/10 text-mint border-mint/30',
  pending_payment: 'bg-accent/10 text-accent-soft border-accent/30',
  pending_approval: 'bg-amber/10 text-amber border-amber/30',
  failed: 'bg-rose/10 text-rose border-rose/30',
  created: 'bg-ink-700 text-text-mid border-line',
}

interface Props {
  metrics: Metrics | null
  orders: Order[]
  approvals: Approval[]
  onDecide: (approvalId: string, approve: boolean) => void
  deciding: string | null
}

function Stat({ label, value, accent }: { label: string; value: string | number; accent?: boolean }) {
  return (
    <Tilt max={9}>
      <div className="glass raise rounded-xl p-3.5">
        <p className="text-[10px] font-medium tracking-wide text-text-low uppercase">{label}</p>
        <p
          className={`mt-1 text-2xl font-semibold tracking-tight ${
            accent
              ? 'bg-linear-to-r from-mint to-accent-soft bg-clip-text text-transparent'
              : 'text-text-hi'
          }`}
        >
          {value}
        </p>
      </div>
    </Tilt>
  )
}

export function MerchantDashboard({ metrics, orders, approvals, onDecide, deciding }: Props) {
  return (
    <div className="scroll-thin h-full overflow-auto p-4">
      <div className="grid grid-cols-3 gap-3">
        <Stat label="Revenue" value={inr(metrics?.revenue_inr ?? 0)} accent />
        <Stat label="Orders paid" value={metrics?.orders_paid ?? 0} />
        <Stat label="Audit entries" value={metrics?.audit_entries ?? 0} />
      </div>

      <section className="mt-6">
        <h3 className="flex items-center gap-2 text-[11px] font-semibold tracking-wide text-text-mid uppercase">
          Pending approvals
          {approvals.length > 0 && (
            <span className="pulse-ring rounded-full bg-amber/20 px-2 py-0.5 text-[10px] text-amber">
              {approvals.length}
            </span>
          )}
        </h3>

        {approvals.length === 0 ? (
          <p className="mt-2 rounded-xl border border-dashed border-line px-3 py-5 text-center text-xs text-text-low">
            Nothing waiting on you.
          </p>
        ) : (
          <ul className="mt-2 space-y-2">
            {approvals.map((a) => (
              <li
                key={a.id}
                className="animate-rise raise rounded-xl border border-amber/25 bg-linear-to-br from-amber/10 to-transparent p-3.5"
              >
                <div className="flex items-center justify-between">
                  <span className="text-base font-semibold text-text-hi">{inr(a.amount_inr)}</span>
                  <span className="font-mono text-[10px] text-text-low">
                    {a.session_id.slice(0, 14)}
                  </span>
                </div>
                <p className="mt-1.5 text-xs leading-relaxed text-text-mid">{a.reason}</p>
                <div className="mt-3 flex gap-2">
                  <button
                    disabled={deciding === a.id}
                    onClick={() => onDecide(a.id, true)}
                    className="glow-accent rounded-lg bg-linear-to-r from-rzp-blue to-accent px-3.5 py-1.5 text-xs font-semibold text-white transition-transform hover:-translate-y-px disabled:opacity-50"
                  >
                    Approve
                  </button>
                  <button
                    disabled={deciding === a.id}
                    onClick={() => onDecide(a.id, false)}
                    className="rounded-lg border border-line bg-ink-800/70 px-3.5 py-1.5 text-xs font-medium text-text-mid transition-colors hover:border-rose/40 hover:text-rose disabled:opacity-50"
                  >
                    Deny
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="mt-6">
        <h3 className="text-[11px] font-semibold tracking-wide text-text-mid uppercase">Orders</h3>
        {orders.length === 0 ? (
          <p className="mt-2 rounded-xl border border-dashed border-line px-3 py-5 text-center text-xs text-text-low">
            No orders yet.
          </p>
        ) : (
          <ul className="mt-2 space-y-2">
            {orders.map((o) => (
              <li key={o.id} className="glass raise rounded-xl p-3.5">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-semibold text-text-hi">{inr(o.amount_inr)}</span>
                  <span
                    className={`rounded-md border px-2 py-0.5 text-[10px] font-semibold uppercase ${
                      STATUS_STYLES[o.status] ?? 'border-line bg-ink-700 text-text-mid'
                    }`}
                  >
                    {o.status.replace('_', ' ')}
                  </span>
                </div>
                <p className="mt-1 text-xs text-text-mid">
                  {o.items.map((i) => `${i.qty}× ${i.name}`).join(', ') || '—'}
                </p>
                {o.discount_pct > 0 && (
                  <p className="mt-0.5 text-[11px] text-mint">{o.discount_pct}% discount applied</p>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}
