import type { ReactNode } from 'react'

interface Props {
  children: ReactNode
  tone?: 'neutral' | 'accent' | 'success' | 'warning'
  className?: string
}

export default function Badge({ children, tone = 'neutral', className = '' }: Props) {
  return <span className={`badge badge--${tone} ${className}`.trim()}>{children}</span>
}