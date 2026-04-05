import React from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AppProvider } from './context/AppContext'
import Sidebar from './components/Layout/Sidebar'
import Toast from './components/UI/Toast'
import Dashboard from './pages/Dashboard'
import Drafts from './pages/Drafts'
import Ask from './pages/Ask'
import Mail from './pages/Mail/Mail'
import Thread from './pages/Mail/Thread'
import Department from './pages/Department/Department'
import Projects from './pages/Projects/Projects'
import Audit from './pages/Audit'
import Settings from './pages/Settings/Settings'

export default function App() {
  return (
    <AppProvider>
      <BrowserRouter>
        <div className="layout">
          <Sidebar />
          <main className="main-area">
            <Routes>
              <Route path="/"          element={<Navigate to="/dashboard" replace />} />
              <Route path="/dashboard" element={<Dashboard />} />
              <Route path="/drafts"    element={<Drafts />} />
              <Route path="/ask"       element={<Ask />} />
              <Route path="/mail"      element={<Mail />} />
              <Route path="/mail/:tid" element={<Thread />} />
              <Route path="/dept/:id"  element={<Department />} />
              <Route path="/projects"  element={<Projects />} />
              <Route path="/audit"     element={<Audit />} />
              <Route path="/settings"  element={<Settings />} />
            </Routes>
          </main>
        </div>
        <Toast />
      </BrowserRouter>
    </AppProvider>
  )
}
