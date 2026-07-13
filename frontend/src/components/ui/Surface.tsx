import type { ElementType, ReactNode } from 'react'

interface Props {
  as?: ElementType
  children: ReactNode
  className?: string
  elevated?: boolean
}

export default function Surface({ as: Component = 'section', children, className = '', elevated = false }: Props) {
  return (
    <Component className={`surface${elevated ? ' surface--elevated' : ''} ${className}`.trim()}>
      {children}
    </Component>
  )
}