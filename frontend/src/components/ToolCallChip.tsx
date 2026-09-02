import { useState } from 'react'

const LABELS: Record<string, string> = {
  search_catalog: 'Searching catalog',
  get_product: 'Reading product',
  create_payment_intent_tool: 'Creating payment intent',
  confirm_payment: 'Checking payment',
  get_order_status_tool: 'Checking order',
}

interface Props {
  name: string
  input: Record<string, unknown>
  result?: string
  isError?: boolean
}

export function ToolCallChip({ name, input, result, isError }: Props) {
  const [open, setOpen] = useState(false)
  const label = LABELS[name] ?? name
  const pending = result === undefined

  return (
    <div className="animate-rise">
      <button
        onClick={() => setOpen((v) => !v)}
        className={`flex w-full items-center gap-2 rounded-lg border px-3 py-2 text-left text-xs transition-colors ${
          isError
            ? 'border-amber-300 bg-amber-50 text-amber-900 hover:bg-amber-100'
            : 'border-rzp-border bg-white text-rzp-slate hover:bg-rzp-surface-alt'
        }`}
      >
        <span
          className={`h-1.5 w-1.5 shrink-0 rounded-full ${
            pending ? 'animate-pulse bg-rzp-blue' : isError ? 'bg-amber-500' : 'bg-emerald-500'
          }`}
        />
        <span className="font-medium">{label}</span>
        <code className="truncate font-mono text-[11px] text-rzp-muted">{name}</code>
        <span className="ml-auto shrink-0 text-rzp-muted">{open ? '−' : '+'}</span>
      </button>

      {open && (
        <div className="scroll-thin mt-1 max-h-56 overflow-auto rounded-lg bg-rzp-navy p-3 font-mono text-[11px] leading-relaxed text-slate-200">
          <div className="text-rzp-muted">input</div>
          <pre className="whitespace-pre-wrap break-all">{JSON.stringify(input, null, 2)}</pre>
          {result !== undefined && (
            <>
              <div className="mt-2 text-rzp-muted">result</div>
              <pre className="whitespace-pre-wrap break-all">{result}</pre>
            </>
          )}
        </div>
      )}
    </div>
  )
}
