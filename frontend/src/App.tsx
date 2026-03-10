import { Navigate, Route, Routes } from 'react-router-dom'

import { LayoutShell } from './components/LayoutShell'
import { LitePage } from './pages/LitePage'
import { SettingsPage } from './pages/SettingsPage'

function App() {
  return (
    <LayoutShell>
      <Routes>
        <Route path="/" element={<Navigate to="/lite" replace />} />
        <Route path="/lite" element={<LitePage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="*" element={<Navigate to="/lite" replace />} />
      </Routes>
    </LayoutShell>
  )
}

export default App
