import { BrowserRouter, Routes, Route } from 'react-router-dom'
import SearchPage from './pages/SearchPage'
import ProfilePage from './pages/ProfilePage'
import ComparePage from './pages/ComparePage'
import ChatPage from './pages/ChatPage'
import AppShell from './components/ui/AppShell'

export default function App() {
  return (
    <BrowserRouter>
      <AppShell>
        <Routes>
          <Route path="/" element={<SearchPage />} />
          <Route path="/player/:id" element={<ProfilePage />} />
          <Route path="/compare" element={<ComparePage />} />
          <Route path="/chat" element={<ChatPage />} />
        </Routes>
      </AppShell>
    </BrowserRouter>
  )
}
