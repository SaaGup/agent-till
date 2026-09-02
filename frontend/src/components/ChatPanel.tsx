import { useEffect, useRef, useState } from 'react'
import type { ChatItem, UpsellProposal } from '../types'
import { ToolCallChip } from './ToolCallChip'
import { UpsellCard } from './UpsellCard'
import { CheckoutButton } from './CheckoutButton'
import { AgentText } from './AgentText'

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
  agentEnabled: boolean
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
  agentEnabled,
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
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-2 border-b border-line px-4 py-3">
        <div className="glow-accent flex h-7 w-7 items-center justify-center rounded-lg bg-linear-to-br from-accent-soft to-rzp-blue text-xs font-bold text-white">
          AI
        </div>
        <div>
          <h2 className="text-sm font-semibold tracking-tight text-text-hi">Shopping assistant</h2>
          <p className="text-[11px] text-text-low">Browses and checks out via the merchant's tools</p>
        </div>
      </div>

      <div className="scroll-thin flex-1 space-y-3 overflow-auto p-4">
        {!agentEnabled && (
          <div className="rounded-lg border border-amber/30 bg-amber/10 px-3 py-2 text-xs text-amber">
            No model provider configured — the assistant can't reason until LLM_API_KEY is set.
          </div>
        )}

        {items.length === 0 && (
          <div className="pt-6 text-center">
            <p className="text-sm text-text-mid">Ask for something to get started.</p>
            <div className="mt-3 flex flex-col items-center gap-2">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  className="rounded-full border border-line bg-ink-800/70 px-3 py-1.5 text-xs text-text-mid transition-all hover:-translate-y-px hover:border-accent hover:text-text-hi"
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
                <p className="animate-rise raise max-w-[85%] rounded-2xl rounded-br-sm bg-linear-to-br from-rzp-blue to-accent px-3.5 py-2 text-sm text-white">
                  {item.text}
                </p>
              </div>
            )
          }
          if (item.kind === 'agent') {
            return (
              <div key={i} className="flex justify-start">
                <p className="glass animate-rise raise max-w-[85%] rounded-2xl rounded-bl-sm px-3.5 py-2 text-sm text-text-hi">
                  <AgentText text={item.text} />
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
                  ? 'border-rose/30 bg-rose/10 text-rose'
                  : 'border-amber/30 bg-amber/10 text-amber'
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
          <div className="glass animate-rise raise-lg rounded-xl p-3.5">
            <p className="mb-2.5 text-xs text-text-mid">
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
          <div className="flex items-center gap-2 text-xs text-text-low">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent" />
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
        className="flex gap-2 border-t border-line p-3"
      >
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Ask for what you need…"
          maxLength={2000}
          className="flex-1 rounded-lg border border-line bg-ink-850/80 px-3 py-2 text-sm text-text-hi outline-none transition-colors placeholder:text-text-low focus:border-accent"
        />
        <button
          type="submit"
          disabled={busy || !draft.trim()}
          className="glow-accent rounded-lg bg-linear-to-r from-rzp-blue to-accent px-4 py-2 text-sm font-medium text-white transition-transform hover:-translate-y-px disabled:opacity-40"
        >
          Send
        </button>
      </form>
    </div>
  )
}
