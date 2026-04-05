import React, { useEffect, useState } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { useApp } from '../../context/AppContext'
import { getDraftStats, getFounderStats } from '../../api'
import { COLORS, DEPT_IDS, DEPT_NAMES } from '../../constants'

const navCls = ({ isActive }) => 'nav-item' + (isActive ? ' active' : '')

export default function Sidebar() {
  const { pendingCount, setPending } = useApp()
  const [founderStats, setFounderStats] = useState({})
  const navigate = useNavigate()

  useEffect(() => {
    const load = () => {
      getDraftStats().then(s => setPending(s.pending_count || 0)).catch(() => {})
      getFounderStats().then(setFounderStats).catch(() => {})
    }
    load()
    const t = setInterval(load, 30000)
    return () => clearInterval(t)
  }, [setPending])

  const founderAlerts = (founderStats.unread_mail || 0)
    + (founderStats.spawn_requests || 0)
    + (founderStats.draft_endeavors || 0)

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <h1>🏛️ Think Tank</h1>
        <p>Central Operations</p>
      </div>

      {/* FOUNDER INBOX — always prominent */}
      <div style={{ padding:'8px 12px 4px' }}>
        <NavLink to="/founder" className={navCls} style={{ background:'rgba(248,81,73,0.08)', borderRadius:7, border:'1px solid rgba(248,81,73,0.2)' }}>
          <span>👑</span> Founder Inbox
          {founderAlerts > 0 && <span className="badge" style={{ background:'var(--red)' }}>{founderAlerts}</span>}
        </NavLink>
      </div>

      <nav className="nav-section">
        <div className="nav-label">Overview</div>
        <NavLink to="/dashboard"  className={navCls}><span>📊</span> Dashboard</NavLink>
        <NavLink to="/drafts"     className={navCls}>
          <span>📋</span> Drafts
          {pendingCount > 0 && <span className="badge">{pendingCount}</span>}
        </NavLink>
        <NavLink to="/mail"       className={navCls}><span>📨</span> Mail Room</NavLink>
        <NavLink to="/ask"        className={navCls}><span>💬</span> Ask</NavLink>
        <NavLink to="/endeavors"  className={navCls}><span>🚀</span> Endeavors</NavLink>
        <NavLink to="/agents"     className={navCls}><span>🤖</span> Agents</NavLink>
      </nav>

      <nav className="nav-section">
        <div className="nav-label">Departments</div>
        {DEPT_IDS.map(id => (
          <NavLink key={id} to={`/dept/${id}`} className={navCls}>
            <span className="dot" style={{ background: COLORS[id] }} />
            {DEPT_NAMES[id].split(' & ')[0]}
          </NavLink>
        ))}
      </nav>

      <button className="btn-nd-sidebar" onClick={() => navigate('/ask')}>＋ New Draft</button>

      <nav className="nav-section">
        <div className="nav-label">Admin</div>
        <NavLink to="/projects" className={navCls}><span>📁</span> Projects</NavLink>
        <NavLink to="/audit"    className={navCls}><span>🔍</span> Audit Log</NavLink>
        <NavLink to="/settings" className={navCls}><span>⚙️</span> Settings</NavLink>
      </nav>
    </aside>
  )
}
