import { useState } from 'react'
import type { AuditEntry } from '../types'
import { inr } from '../format'

const DECISION_STYLES: Record<string, string> = {
  allowed: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  capped: 'bg-amber-50 text-amber-800 border-amber-200',
  blocked: 'bg-rose-50 text-rose-700 border-rose-200',
  pending_approval: 'bg-blue-50 text-rzp-blue border-blue-200',
  approved: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  denied: 'bg-rose-50 text-rose-700 border-rose-200',
}

const ACTOR_LABELS: Record<string, string> = {
  ai_buyer_agent: 'AI buyer',
  growth_copilot_agent: 'Growth co-pilot',
  merchant_human: 'Merchant',
  system: 'System',
}

function shortId(id: string) {
  return id.slice(0, 8)
}

export function AuditTrailView({ entries }: { entries: AuditEntry[] }) {
  const [moneyOnly, setMoneyOnly] = useState(false)
  const rows = moneyOnly ? entries.filter((e) => e.money_affecting) : entries

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-rzp-border px-4 py-3">
        <div>
          <h2 className="text-sm font-semibold text-rzp-navy">Audit trail</h2>
          <p className="text-xs text-rzp-muted">
            Every decision, with the reason and the policy in force at the time.
          </p>
        </div>
        <label className="flex cursor-pointer items-center gap-2 text-xs text-rzp-slate">
          <input
            type="checkbox"
            checked={moneyOnly}
            onChange={(e) => setMoneyOnly(e.target.checked)}
            className="accent-rzp-blue"
          />
          Money actions only
        </label>
      </div>

      <div className="scroll-thin flex-1 overflow-auto">
        {rows.length === 0 && (
          <p className="px-4 py-8 text-center text-xs text-rzp-muted">
            No entries yet — talk to the assistant to generate activity.
          </p>
        )}

        <ul className="divide-y divide-rzp-border">
          {rows.map((entry) => (
            <li key={entry.id} className="px-4 py-3 transition-colors hover:bg-rzp-surface-alt">
              <div className="flex flex-wrap items-center gap-2">
                <span
                  className={`rounded-md border px-1.5 py-0.5 text-[10px] font-semibold uppercase ${
                    DECISION_STYLES[entry.decision] ?? 'border-rzp-border bg-rzp-surface text-rzp-slate'
                  }`}
                >
                  {entry.decision.replace('_', ' ')}
                </span>
                <code className="font-mono text-[11px] font-medium text-rzp-navy">
                  {entry.action_type}
                </code>
                <span className="text-[11px] text-rzp-muted">
                  {ACTOR_LABELS[entry.actor] ?? entry.actor}
                </span>
                {entry.money_affecting && (
                  <span className="rounded bg-rzp-blue/10 px-1.5 py-0.5 text-[10px] font-medium text-rzp-blue">
                    money
                  </span>
                )}
                {entry.amount_inr != null && (
                  <span className="text-[11px] font-semibold text-rzp-navy">
                    {inr(entry.amount_inr)}
                  </span>
                )}
                <span className="ml-auto font-mono text-[10px] text-rzp-muted">
                  {entry.ts ? new Date(entry.ts).toLocaleTimeString() : ''}
                </span>
              </div>

              <p className="mt-1.5 text-xs leading-relaxed text-rzp-slate">{entry.explanation}</p>

              <div className="mt-1 flex gap-3 font-mono text-[10px] text-rzp-muted">
                <span title="Correlation id — ties a failure to its recovery">
                  corr {shortId(entry.correlation_id)}
                </span>
                {entry.order_id && <span>order {shortId(entry.order_id)}</span>}
              </div>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
