import { useRef, type ReactNode } from 'react'

/** Pointer-reactive tilt. Real depth needs the surface to respond to where you are, not just
 *  sit under a drop shadow — but it stays subtle (a few degrees) so text never distorts, and
 *  it disables itself for coarse pointers where there is no hover to react to. */
export function Tilt({
  children,
  className = '',
  max = 7,
}: {
  children: ReactNode
  className?: string
  max?: number
}) {
  const ref = useRef<HTMLDivElement>(null)

  const move = (e: React.MouseEvent) => {
    const el = ref.current
    if (!el || window.matchMedia('(pointer: coarse)').matches) return
    const r = el.getBoundingClientRect()
    const px = (e.clientX - r.left) / r.width - 0.5
    const py = (e.clientY - r.top) / r.height - 0.5
    el.style.transform = `perspective(1100px) rotateY(${px * max}deg) rotateX(${-py * max}deg) translateZ(0)`
  }

  const reset = () => {
    if (ref.current) ref.current.style.transform = ''
  }

  return (
    <div ref={ref} onMouseMove={move} onMouseLeave={reset} className={`tilt ${className}`}>
      {children}
    </div>
  )
}
