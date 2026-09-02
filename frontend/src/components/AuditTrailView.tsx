import { useState } from 'react'
import type { AuditEntry } from '../types'
import { inr } from '../format'

const DECISION_STYLES: Record<string, string> = {
  allowed: 'bg-mint/10 text-mint border-mint/30',
  capped: 'bg-amber/10 text-amber border-amber/30',
  blocked: 'bg-rose/10 text-rose border-rose/30',
  pending_approval: 'bg-accent/10 text-accent-soft border-accent/30',
  approved: 'bg-mint/10 text-mint border-mint/30',
  denied: 'bg-rose/10 text-rose border-rose/30',
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
      <div className="flex items-center justify-between border-b border-line px-4 py-3">
        <div>
          <h2 className="text-sm font-semibold tracking-tight text-text-hi">Audit trail</h2>
          <p className="text-[11px] text-text-low">
            Every decision, with the reason and the policy in force at the time.
          </p>
        </div>
        <label className="flex cursor-pointer items-center gap-2 text-[11px] text-text-mid">
          <input
            type="checkbox"
            checked={moneyOnly}
            onChange={(e) => setMoneyOnly(e.target.checked)}
            className="accent-accent"
          />
          Money actions only
        </label>
      </div>

      <div className="scroll-thin flex-1 overflow-auto">
        {rows.length === 0 && (
          <p className="px-4 py-10 text-center text-xs text-text-low">
            No entries yet — talk to the assistant to generate activity.
          </p>
        )}

        <ul className="divide-y divide-line-soft">
          {rows.map((entry) => (
            <li
              key={entry.id}
              className="animate-rise border-l-2 border-transparent px-4 py-3 transition-colors hover:border-l-accent hover:bg-ink-800/50"
            >
              <div className="flex flex-wrap items-center gap-2">
                <span
                  className={`rounded-md border px-1.5 py-0.5 text-[10px] font-semibold uppercase ${
                    DECISION_STYLES[entry.decision] ?? 'border-line bg-ink-700 text-text-mid'
                  }`}
                >
                  {entry.decision.replace('_', ' ')}
                </span>
                <code className="font-mono text-[11px] font-medium text-text-hi">
                  {entry.action_type}
                </code>
                <span className="text-[11px] text-text-low">
                  {ACTOR_LABELS[entry.actor] ?? entry.actor}
                </span>
                {entry.money_affecting && (
                  <span className="rounded bg-accent/15 px-1.5 py-0.5 text-[10px] font-medium text-accent-soft">
                    money
                  </span>
                )}
                {entry.amount_inr != null && (
                  <span className="text-[11px] font-semibold text-text-hi">
                    {inr(entry.amount_inr)}
                  </span>
                )}
                <span className="ml-auto font-mono text-[10px] text-text-low">
                  {entry.ts ? new Date(entry.ts).toLocaleTimeString() : ''}
                </span>
              </div>

              <p className="mt-1.5 text-xs leading-relaxed text-text-mid">{entry.explanation}</p>

              <div className="mt-1 flex gap-3 font-mono text-[10px] text-text-low">
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
