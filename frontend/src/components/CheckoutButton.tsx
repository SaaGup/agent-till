import { useState } from 'react'
import { api } from '../api/client'
import { inr } from '../format'

declare global {
  interface Window {
    Razorpay?: new (options: Record<string, unknown>) => { open: () => void; on: (e: string, cb: (r: unknown) => void) => void }
  }
}

interface Props {
  razorpayOrderId: string
  razorpayKeyId: string
  amountInr: number
  onPaid: () => void
  onFailed: (reason: string) => void
}

export function CheckoutButton({ razorpayOrderId, razorpayKeyId, amountInr, onPaid, onFailed }: Props) {
  const [busy, setBusy] = useState(false)

  const openCheckout = () => {
    if (!window.Razorpay) {
      onFailed('Razorpay Checkout did not load.')
      return
    }
    setBusy(true)

    const rzp = new window.Razorpay({
      key: razorpayKeyId,
      order_id: razorpayOrderId,
      amount: Math.round(amountInr * 100),
      currency: 'INR',
      name: 'Agent-Ready Storefront',
      description: 'Test-mode payment',
      theme: { color: '#2950da' },
      // Card details go straight to Razorpay from this modal — they never touch the agent
      // or the merchant backend, which is why a human completes this step.
      handler: async (response: {
        razorpay_order_id: string
        razorpay_payment_id: string
        razorpay_signature: string
      }) => {
        try {
          await api.verifyPayment(response)
          onPaid()
        } catch {
          onFailed('Payment verification failed.')
        } finally {
          setBusy(false)
        }
      },
      modal: { ondismiss: () => setBusy(false) },
    })

    rzp.on('payment.failed', (resp: unknown) => {
      const error = (resp as { error?: { description?: string } })?.error
      const reason = error?.description ?? 'Payment declined at the gateway.'
      api.reportFailed(razorpayOrderId, reason).catch(() => {})
      onFailed(reason)
      setBusy(false)
    })

    rzp.open()
  }

  return (
    <button
      onClick={openCheckout}
      disabled={busy}
      className="glow-accent sheen w-full rounded-lg bg-linear-to-r from-rzp-blue to-accent px-4 py-2.5 text-sm font-semibold text-white transition-transform hover:-translate-y-px disabled:opacity-60"
    >
      {busy ? 'Opening checkout…' : `Pay ${inr(amountInr)}`}
    </button>
  )
}
