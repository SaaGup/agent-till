import { useEffect, useRef, useState } from 'react'
import type { ChatItem, UpsellProposal } from '../types'
import { ToolCallChip } from './ToolCallChip'
import { UpsellCard } from './UpsellCard'
import { CheckoutButton } from './CheckoutButton'

interface PendingCheckout {
  razorpayOrderId: string
  razorpayKeyId: string
  amountInr: number
}

interface Props {
  items: ChatItem[]
  busy: boolean
  upsell: UpsellProposal | null
  checkout: PendingCheckout | null
  onSend: (message: string) => void
  onAddUpsell: (proposal: UpsellProposal) => void
  onDismissUpsell: () => void
  onPaid: () => void
  onFailed: (reason: string) => void
}

const SUGGESTIONS = [
  'I need running shoes under ₹3000',
  'Show me something for trail running',
  'What accessories do you have?',
]

export function ChatPanel({
  items,
  busy,
  upsell,
  checkout,
  onSend,
  onAddUpsell,
  onDismissUpsell,
  onPaid,
  onFailed,
}: Props) {
  const [draft, setDraft] = useState('')
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [items, upsell, checkout, busy])

  const send = (text: string) => {
    const message = text.trim()
    if (!message || busy) return
    setDraft('')
    onSend(message)
  }

  return (
    <div className="flex h-full flex-col bg-white">
      <div className="flex items-center gap-2 border-b border-rzp-border px-4 py-3">
        <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-rzp-blue text-xs font-bold text-white">
          AI
        </div>
        <div>
          <h2 className="text-sm font-semibold text-rzp-navy">Shopping assistant</h2>
          <p className="text-[11px] text-rzp-muted">Browses and checks out via the merchant's tools</p>
        </div>
      </div>

      <div className="scroll-thin flex-1 space-y-3 overflow-auto p-4">
        {items.length === 0 && (
          <div className="pt-6 text-center">
            <p className="text-sm text-rzp-slate">Ask for something to get started.</p>
            <div className="mt-3 flex flex-col items-center gap-2">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  className="rounded-full border border-rzp-border bg-rzp-surface-alt px-3 py-1.5 text-xs text-rzp-slate transition-colors hover:border-rzp-blue hover:text-rzp-blue"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {items.map((item, i) => {
          if (item.kind === 'user') {
            return (
              <div key={i} className="flex justify-end">
                <p className="animate-rise max-w-[85%] rounded-2xl rounded-br-sm bg-rzp-blue px-3.5 py-2 text-sm text-white">
                  {item.text}
                </p>
              </div>
            )
          }
          if (item.kind === 'agent') {
            return (
              <div key={i} className="flex justify-start">
                <p className="animate-rise max-w-[85%] rounded-2xl rounded-bl-sm bg-rzp-surface px-3.5 py-2 text-sm whitespace-pre-wrap text-rzp-navy">
                  {item.text}
                </p>
              </div>
            )
          }
          if (item.kind === 'tool') {
            return (
              <ToolCallChip
                key={i}
                name={item.name}
                input={item.input}
                result={item.result}
                isError={item.isError}
              />
            )
          }
          return (
            <div
              key={i}
              className={`animate-rise rounded-lg border px-3 py-2 text-xs ${
                item.tone === 'circuit'
                  ? 'border-rose-200 bg-rose-50 text-rose-800'
                  : 'border-amber-200 bg-amber-50 text-amber-900'
              }`}
            >
              <span className="font-semibold">
                {item.tone === 'circuit' ? 'Circuit breaker tripped · ' : 'Problem · '}
              </span>
              {item.text}
            </div>
          )
        })}

        {upsell && <UpsellCard proposal={upsell} onAdd={onAddUpsell} onDismiss={onDismissUpsell} />}

        {checkout && (
          <div className="animate-rise rounded-xl border border-rzp-border bg-rzp-surface-alt p-3">
            <p className="mb-2 text-xs text-rzp-slate">
              Approved and ready. Card details go straight to Razorpay — they never reach the agent.
            </p>
            <CheckoutButton
              razorpayOrderId={checkout.razorpayOrderId}
              razorpayKeyId={checkout.razorpayKeyId}
              amountInr={checkout.amountInr}
              onPaid={onPaid}
              onFailed={onFailed}
            />
          </div>
        )}

        {busy && (
          <div className="flex items-center gap-2 text-xs text-rzp-muted">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-rzp-blue" />
            Thinking…
          </div>
        )}

        <div ref={endRef} />
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault()
          send(draft)
        }}
        className="flex gap-2 border-t border-rzp-border p-3"
      >
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Ask for what you need…"
          maxLength={2000}
          className="flex-1 rounded-lg border border-rzp-border bg-rzp-surface-alt px-3 py-2 text-sm text-rzp-navy outline-none transition-colors placeholder:text-rzp-muted focus:border-rzp-blue focus:bg-white"
        />
        <button
          type="submit"
          disabled={busy || !draft.trim()}
          className="rounded-lg bg-rzp-blue px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-rzp-blue-dark disabled:opacity-40"
        >
          Send
        </button>
      </form>
    </div>
  )
}
