import type { UpsellProposal } from '../types'
import { inr } from '../format'

interface Props {
  proposal: UpsellProposal
  onAdd: (proposal: UpsellProposal) => void
  onDismiss: () => void
}

export function UpsellCard({ proposal, onAdd, onDismiss }: Props) {
  return (
    <div className="glass animate-rise raise-lg rounded-xl border-accent/25 p-4">
      <div className="flex items-center gap-2">
        <span className="rounded-full bg-accent/15 px-2 py-0.5 text-[10px] font-semibold tracking-wide text-accent-soft uppercase">
          Growth co-pilot
        </span>
        {proposal.was_capped && (
          <span className="rounded-full bg-amber/15 px-2 py-0.5 text-[10px] font-semibold tracking-wide text-amber uppercase">
            Discount capped
          </span>
        )}
      </div>

      <p className="mt-2 text-sm font-semibold text-text-hi">{proposal.name}</p>
      <p className="mt-0.5 text-xs text-text-mid">{proposal.rationale}</p>

      <div className="mt-3 flex items-baseline gap-2">
        <span className="text-lg font-semibold text-text-hi">
          {inr(proposal.discounted_price_inr)}
        </span>
        <span className="text-xs text-text-low line-through">
          {inr(proposal.list_price_inr)}
        </span>
        <span className="text-xs font-medium text-mint">
          {proposal.capped_discount_pct}% off
        </span>
      </div>

      {proposal.was_capped && (
        <p className="mt-2 rounded-lg border border-amber/25 bg-amber/10 px-2.5 py-1.5 text-[11px] leading-relaxed text-amber">
          Asked for {proposal.requested_discount_pct}% — policy capped it to{' '}
          {proposal.capped_discount_pct}%.
        </p>
      )}

      <div className="mt-3 flex gap-2">
        <button
          onClick={() => onAdd(proposal)}
          className="glow-accent rounded-lg bg-linear-to-r from-rzp-blue to-accent px-3 py-1.5 text-xs font-medium text-white transition-transform hover:-translate-y-px"
        >
          Add to order
        </button>
        <button
          onClick={onDismiss}
          className="rounded-lg border border-line px-3 py-1.5 text-xs font-medium text-text-mid transition-colors hover:text-text-hi"
        >
          No thanks
        </button>
      </div>
    </div>
  )
}
