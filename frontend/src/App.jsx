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
import DeptFiles from './pages/Department/DeptFiles'
import Projects from './pages/Projects/Projects'
import Audit from './pages/Audit'
import Settings from './pages/Settings/Settings'
import Endeavors from './pages/Endeavors/Endeavors'
import EndeavorDetail from './pages/Endeavors/EndeavorDetail'
import KanbanBoard from './pages/Endeavors/KanbanBoard'
import AgentsPage from './pages/Agents/AgentsPage'
import AgentProfile from './pages/Agents/AgentProfile'
import FounderInbox from './pages/Founder/FounderInbox'
import PromptsPage from './pages/Settings/PromptsPage'
import ExtensionsPage from './pages/Extensions/ExtensionsPage'
import EconomyPage from './pages/Economy/EconomyPage'
import MarketplacePage from './pages/Marketplace/MarketplacePage'
import FilesPage from './pages/Files/FilesPage'

export default function App() {
  return (
    <AppProvider>
      <BrowserRouter>
        <div className="layout">
          <Sidebar />
          <main className="main-area">
            <Routes>
              <Route path="/"                         element={<Navigate to="/dashboard" replace />} />
              <Route path="/dashboard"                element={<Dashboard />} />
              <Route path="/drafts"                   element={<Drafts />} />
              <Route path="/ask"                      element={<Ask />} />
              <Route path="/mail"                     element={<Mail />} />
              <Route path="/mail/:tid"                element={<Thread />} />
              <Route path="/dept/:id"                 element={<Department />} />
              <Route path="/dept/:id/files"           element={<DeptFiles />} />
              <Route path="/dept/:id/agents"          element={<AgentsPage />} />
              <Route path="/projects"                 element={<Projects />} />
              <Route path="/audit"                    element={<Audit />} />
              <Route path="/settings"                 element={<Settings />} />
              <Route path="/endeavors"                element={<Endeavors />} />
              <Route path="/endeavors/:id"            element={<EndeavorDetail />} />
              <Route path="/endeavors/:id/kanban"     element={<KanbanBoard />} />
              <Route path="/agents"                   element={<AgentsPage />} />
              <Route path="/agents/:id"               element={<AgentProfile />} />
              <Route path="/founder"                  element={<FounderInbox />} />
              <Route path="/prompts"                  element={<PromptsPage />} />
              <Route path="/extensions"               element={<ExtensionsPage />} />
              <Route path="/economy"                  element={<EconomyPage />} />
              <Route path="/marketplace"              element={<MarketplacePage />} />
              <Route path="/files"                     element={<FilesPage />} />
            </Routes>
          </main>
        </div>
        <Toast />
      </BrowserRouter>
    </AppProvider>
  )
}
