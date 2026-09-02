const WHOLE = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 })
const PAISE = new Intl.NumberFormat('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })

/** Discounts produce fractional rupees (₹2399.2), which reads as a bug rather than a price.
 *  Show paise only when there are any. */
export function inr(amount: number): string {
  const fmt = Number.isInteger(amount) ? WHOLE : PAISE
  return `₹${fmt.format(amount)}`
}
