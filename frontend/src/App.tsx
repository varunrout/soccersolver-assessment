import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import SearchPage from './pages/SearchPage'
import ProfilePage from './pages/ProfilePage'
import ComparePage from './pages/ComparePage'
import ChatPage from './pages/ChatPage'

function Nav() {
  return (
    <nav className="nav">
      <span className="nav-brand">{'\u26bd'} SoccerSolver</span>
      <div className="nav-links">
        <NavLink to="/" end>Search</NavLink>
        <NavLink to="/compare">Compare</NavLink>
        <NavLink to="/chat">Ask AI</NavLink>
      </div>
    </nav>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <Nav />
      <main className="main-content">
        <Routes>
          <Route path="/" element={<SearchPage />} />
          <Route path="/player/:id" element={<ProfilePage />} />
          <Route path="/compare" element={<ComparePage />} />
          <Route path="/chat" element={<ChatPage />} />
        </Routes>
      </main>
    </BrowserRouter>
  )
}
