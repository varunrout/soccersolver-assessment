import type { ReactNode } from 'react'

interface Props {
  eyebrow?: string
  title: string
  description: string
  actions?: ReactNode
  className?: string
}

export default function PageHeader({ eyebrow, title, description, actions, className = '' }: Props) {
  return (
    <header className={`page-header ${className}`.trim()}>
      <div className="page-header__copy">
        {eyebrow ? <span className="page-header__eyebrow">{eyebrow}</span> : null}
        <h1 className="page-title">{title}</h1>
        <p>{description}</p>
      </div>
      {actions ? <div className="page-header__actions">{actions}</div> : null}
    </header>
  )
}