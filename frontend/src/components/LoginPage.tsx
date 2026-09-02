import { useEffect, useState } from 'react'
import { ApiError, Unauthorized, api, waitForBackend } from '../api/client'
import { Tilt } from './Tilt'

interface Props {
  onAuthenticated: (token: string, displayName: string) => void
  demoEmail: string
  demoPassword: string
}

const GUARDRAILS = [
  { label: 'Discount cap', value: '20%', note: 'clamped server-side' },
  { label: 'Per-transaction', value: '₹5,000', note: 'blocked outright' },
  { label: 'Session spend', value: '₹8,000', note: 'cumulative ceiling' },
  { label: 'Approval gate', value: '₹3,000', note: 'held for a human' },
]

export function LoginPage({ onAuthenticated, demoEmail, demoPassword }: Props) {
  const [email, setEmail] = useState(demoEmail)
  const [password, setPassword] = useState(demoPassword)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [waking, setWaking] = useState(false)

  // Config arrives after first paint, so the initial useState values are empty. Fill the form
  // once it lands — but never overwrite what the operator has started typing.
  useEffect(() => {
    setEmail((current) => current || demoEmail)
    setPassword((current) => current || demoPassword)
  }, [demoEmail, demoPassword])

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      const { token, user } = await api.login(email, password)
      onAuthenticated(token, user.display_name || user.email)
    } catch (e) {
      if (e instanceof Unauthorized) {
        setError('Incorrect email or password.')
      } else if (e instanceof ApiError && e.status === 429) {
        setError('Too many sign-in attempts. Wait a minute and try again — your details are fine.')
      } else if (e instanceof ApiError) {
        setError(`The server rejected the request (${e.status}). Check the backend is running.`)
      } else {
        // A sleeping free-tier backend and a genuinely dead one look identical from here, so
        // wait for it rather than declaring failure on the first try.
        setWaking(true)
        setError('')
        const awake = await waitForBackend(() => {})
        setWaking(false)
        if (awake) {
          setError('The server was asleep and is awake now — press Enter console again.')
        } else {
          setError("Couldn't reach the server. Check the backend is running and that CORS allows this origin.")
        }
      }
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="relative min-h-screen overflow-hidden bg-ink-900">
      <div className="aurora" />
      <div className="grid-floor" />

      <div className="relative z-10 mx-auto flex min-h-screen max-w-7xl flex-col px-6 py-6">
        <header className="flex items-center gap-3">
          <div className="glow-accent flex h-9 w-9 items-center justify-center rounded-xl bg-linear-to-br from-accent-soft to-rzp-blue text-sm font-bold text-white">
            ₹
          </div>
          <div>
            <p className="text-sm font-semibold tracking-tight text-text-hi">Agent Till</p>
            <p className="text-[11px] text-text-low">Razorpay AI Buildathon · Track 01</p>
          </div>
          <span className="ml-auto rounded-full border border-line bg-ink-800/60 px-3 py-1 text-[10px] font-medium tracking-wide text-text-mid uppercase">
            Test mode
          </span>
        </header>

        <div className="grid flex-1 items-center gap-12 py-10 lg:grid-cols-[1.05fr_minmax(0,420px)]">
          <section>
            <div className="inline-flex items-center gap-2 rounded-full border border-line bg-ink-800/70 px-3 py-1 text-[11px] text-text-mid">
              <span className="pulse-ring h-1.5 w-1.5 rounded-full bg-mint" />
              Agentic commerce, with the money actions bounded
            </div>

            <h1 className="mt-6 text-5xl leading-[1.05] font-semibold tracking-tight text-text-hi lg:text-6xl">
              The merchant till
              <br />
              <span className="bg-linear-to-r from-accent-soft via-white to-mint bg-clip-text text-transparent">
                AI agents can use.
              </span>
            </h1>

            <p className="mt-5 max-w-xl text-[15px] leading-relaxed text-text-mid">
              An AI buyer browses, negotiates and checks out end to end on Razorpay test-mode
              APIs. Every money action is capped, gated and written to an audit trail — enforced
              in the payment path, not asked for in a prompt.
            </p>

            <div className="mt-9 grid max-w-xl grid-cols-2 gap-3 sm:grid-cols-4">
              {GUARDRAILS.map((g, i) => (
                <Tilt key={g.label} max={10}>
                  <div
                    className="glass raise animate-rise animate-float rounded-xl p-3"
                    style={{ animationDelay: `${i * 90}ms, ${i * 400}ms` }}
                  >
                    <p className="text-[10px] tracking-wide text-text-low uppercase">{g.label}</p>
                    <p className="mt-1 text-lg font-semibold text-text-hi">{g.value}</p>
                    <p className="text-[10px] text-text-low">{g.note}</p>
                  </div>
                </Tilt>
              ))}
            </div>

            <div className="mt-9 flex flex-wrap gap-x-6 gap-y-2 text-[11px] text-text-low">
              <span>MCP tool surface</span>
              <span className="text-line">•</span>
              <span>Server-side policy engine</span>
              <span className="text-line">•</span>
              <span>Immutable audit trail</span>
              <span className="text-line">•</span>
              <span>Circuit breaker</span>
            </div>
          </section>

          <Tilt max={5}>
            <form onSubmit={submit} className="glass raise-lg rounded-2xl p-7">
              <h2 className="text-lg font-semibold tracking-tight text-text-hi">
                Merchant sign-in
              </h2>
              <p className="mt-1 text-xs leading-relaxed text-text-low">
                Approving an order releases real money, so the approval gate sits behind a
                session rather than in the open.
              </p>

              <label className="mt-6 block text-[11px] font-medium tracking-wide text-text-mid uppercase">
                Email
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="username"
                required
                className="mt-1.5 w-full rounded-lg border border-line bg-ink-850/80 px-3 py-2.5 text-sm text-text-hi outline-none transition-colors placeholder:text-text-low focus:border-accent"
              />

              <label className="mt-4 block text-[11px] font-medium tracking-wide text-text-mid uppercase">
                Password
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                required
                className="mt-1.5 w-full rounded-lg border border-line bg-ink-850/80 px-3 py-2.5 text-sm text-text-hi outline-none transition-colors placeholder:text-text-low focus:border-accent"
              />

              {error && (
                <p className="animate-rise mt-4 rounded-lg border border-rose/30 bg-rose/10 px-3 py-2 text-xs text-rose">
                  {error}
                </p>
              )}

              <button
                type="submit"
                disabled={busy || waking}
                className="glow-accent mt-6 w-full rounded-lg bg-linear-to-r from-rzp-blue to-accent px-4 py-2.5 text-sm font-semibold text-white transition-transform hover:-translate-y-px disabled:opacity-60"
              >
                {waking ? 'Waking the server…' : busy ? 'Signing in…' : 'Enter console'}
              </button>

              <div className="mt-5 rounded-lg border border-line-soft bg-ink-850/60 px-3 py-2.5">
                <p className="text-[10px] tracking-wide text-text-low uppercase">Demo account</p>
                <p className="mt-1 font-mono text-[11px] text-text-mid">{demoEmail}</p>
                <p className="font-mono text-[11px] text-text-mid">{demoPassword}</p>
                <p className="mt-1.5 text-[10px] leading-relaxed text-text-low">
                  Pre-filled. This is a public demo on Razorpay test mode — no real money moves.
                </p>
              </div>
            </form>
          </Tilt>
        </div>
      </div>
    </div>
  )
}
