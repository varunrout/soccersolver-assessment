import type { ReactNode } from 'react'
import { BarChart3, GitCompareArrows, MessageSquareText, Search, ShieldCheck } from 'lucide-react'
import { NavLink } from 'react-router-dom'

interface Props {
  children: ReactNode
}

const navigation = [
  { to: '/', label: 'Search', icon: Search, end: true },
  { to: '/compare', label: 'Compare', icon: GitCompareArrows, end: false },
  { to: '/chat', label: 'Ask SoccerSolver', icon: MessageSquareText, end: false },
]

export default function AppShell({ children }: Props) {
  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="app-header__inner">
          <NavLink className="brand" to="/" aria-label="SoccerSolver home">
            <span className="brand__mark" aria-hidden="true"><BarChart3 size={20} /></span>
            <span className="brand__wordmark">Soccer<span>Solver</span></span>
            <span className="brand__descriptor">Player intelligence</span>
          </NavLink>
          <nav className="nav" aria-label="Primary navigation">
            {navigation.map(({ to, label, icon: Icon, end }) => (
              <NavLink key={to} to={to} end={end}>
                <Icon size={17} aria-hidden="true" />
                <span>{label}</span>
              </NavLink>
            ))}
          </nav>
          <div className="app-header__status" aria-label="Deterministic analytics">
            <ShieldCheck size={16} aria-hidden="true" />
            <span>Verified data layer</span>
          </div>
        </div>
      </header>
      <main className="main-content">{children}</main>
    </div>
  )
}