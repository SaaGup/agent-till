import type { Approval, Metrics, Order } from '../types'
import { inr } from '../format'

const STATUS_STYLES: Record<string, string> = {
  paid: 'bg-emerald-50 text-emerald-700',
  pending_payment: 'bg-blue-50 text-rzp-blue',
  pending_approval: 'bg-amber-50 text-amber-800',
  failed: 'bg-rose-50 text-rose-700',
  created: 'bg-rzp-surface text-rzp-slate',
}

interface Props {
  metrics: Metrics | null
  orders: Order[]
  approvals: Approval[]
  onDecide: (approvalId: string, approve: boolean) => void
  deciding: string | null
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-xl border border-rzp-border bg-white p-3">
      <p className="text-[11px] font-medium tracking-wide text-rzp-muted uppercase">{label}</p>
      <p className="mt-1 text-xl font-semibold text-rzp-navy">{value}</p>
    </div>
  )
}

export function MerchantDashboard({ metrics, orders, approvals, onDecide, deciding }: Props) {
  return (
    <div className="scroll-thin h-full overflow-auto p-4">
      <div className="grid grid-cols-3 gap-3">
        <Stat label="Revenue" value={inr(metrics?.revenue_inr ?? 0)} />
        <Stat label="Orders paid" value={metrics?.orders_paid ?? 0} />
        <Stat label="Audit entries" value={metrics?.audit_entries ?? 0} />
      </div>

      <section className="mt-5">
        <h3 className="flex items-center gap-2 text-xs font-semibold tracking-wide text-rzp-slate uppercase">
          Pending approvals
          {approvals.length > 0 && (
            <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[10px] text-amber-800">
              {approvals.length}
            </span>
          )}
        </h3>

        {approvals.length === 0 ? (
          <p className="mt-2 rounded-xl border border-dashed border-rzp-border px-3 py-4 text-center text-xs text-rzp-muted">
            Nothing waiting on you.
          </p>
        ) : (
          <ul className="mt-2 space-y-2">
            {approvals.map((a) => (
              <li
                key={a.id}
                className="animate-rise rounded-xl border border-amber-200 bg-amber-50/60 p-3"
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-semibold text-rzp-navy">
                    {inr(a.amount_inr)}
                  </span>
                  <span className="font-mono text-[10px] text-rzp-muted">
                    {a.session_id.slice(0, 12)}
                  </span>
                </div>
                <p className="mt-1 text-xs leading-relaxed text-rzp-slate">{a.reason}</p>
                <div className="mt-2.5 flex gap-2">
                  <button
                    disabled={deciding === a.id}
                    onClick={() => onDecide(a.id, true)}
                    className="rounded-lg bg-rzp-blue px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-rzp-blue-dark disabled:opacity-50"
                  >
                    Approve
                  </button>
                  <button
                    disabled={deciding === a.id}
                    onClick={() => onDecide(a.id, false)}
                    className="rounded-lg border border-rzp-border bg-white px-3 py-1.5 text-xs font-medium text-rzp-slate transition-colors hover:bg-rzp-surface disabled:opacity-50"
                  >
                    Deny
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="mt-5">
        <h3 className="text-xs font-semibold tracking-wide text-rzp-slate uppercase">Orders</h3>
        {orders.length === 0 ? (
          <p className="mt-2 rounded-xl border border-dashed border-rzp-border px-3 py-4 text-center text-xs text-rzp-muted">
            No orders yet.
          </p>
        ) : (
          <ul className="mt-2 space-y-2">
            {orders.map((o) => (
              <li key={o.id} className="rounded-xl border border-rzp-border bg-white p-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-semibold text-rzp-navy">
                    {inr(o.amount_inr)}
                  </span>
                  <span
                    className={`rounded-md px-2 py-0.5 text-[10px] font-semibold uppercase ${
                      STATUS_STYLES[o.status] ?? 'bg-rzp-surface text-rzp-slate'
                    }`}
                  >
                    {o.status.replace('_', ' ')}
                  </span>
                </div>
                <p className="mt-1 text-xs text-rzp-slate">
                  {o.items.map((i) => `${i.qty}× ${i.name}`).join(', ') || '—'}
                </p>
                {o.discount_pct > 0 && (
                  <p className="mt-0.5 text-[11px] text-emerald-600">{o.discount_pct}% discount applied</p>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}
