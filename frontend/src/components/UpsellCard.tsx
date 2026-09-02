import type { UpsellProposal } from '../types'
import { inr } from '../format'

interface Props {
  proposal: UpsellProposal
  onAdd: (proposal: UpsellProposal) => void
  onDismiss: () => void
}

export function UpsellCard({ proposal, onAdd, onDismiss }: Props) {
  return (
    <div className="animate-rise rounded-xl border border-rzp-border bg-linear-to-br from-white to-rzp-surface-alt p-4 shadow-sm">
      <div className="flex items-center gap-2">
        <span className="rounded-full bg-rzp-blue/10 px-2 py-0.5 text-[10px] font-semibold tracking-wide text-rzp-blue uppercase">
          Growth co-pilot
        </span>
        {proposal.was_capped && (
          <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-semibold tracking-wide text-amber-800 uppercase">
            Discount capped
          </span>
        )}
      </div>

      <p className="mt-2 text-sm font-semibold text-rzp-navy">{proposal.name}</p>
      <p className="mt-0.5 text-xs text-rzp-slate">{proposal.rationale}</p>

      <div className="mt-3 flex items-baseline gap-2">
        <span className="text-lg font-semibold text-rzp-navy">
          {inr(proposal.discounted_price_inr)}
        </span>
        <span className="text-xs text-rzp-muted line-through">
          {inr(proposal.list_price_inr)}
        </span>
        <span className="text-xs font-medium text-emerald-600">
          {proposal.capped_discount_pct}% off
        </span>
      </div>

      {proposal.was_capped && (
        <p className="mt-2 rounded-lg bg-amber-50 px-2.5 py-1.5 text-[11px] leading-relaxed text-amber-900">
          Asked for {proposal.requested_discount_pct}% — policy capped it to{' '}
          {proposal.capped_discount_pct}%.
        </p>
      )}

      <div className="mt-3 flex gap-2">
        <button
          onClick={() => onAdd(proposal)}
          className="rounded-lg bg-rzp-blue px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-rzp-blue-dark"
        >
          Add to order
        </button>
        <button
          onClick={onDismiss}
          className="rounded-lg px-3 py-1.5 text-xs font-medium text-rzp-slate transition-colors hover:bg-rzp-surface"
        >
          No thanks
        </button>
      </div>
    </div>
  )
}
