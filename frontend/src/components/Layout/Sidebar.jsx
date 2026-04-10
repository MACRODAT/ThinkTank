import React, { useEffect, useState } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { useApp } from '../../context/AppContext'
import { getDraftStats, getFounderStats, getEconomyBalances } from '../../api'
import { COLORS, DEPT_IDS, DEPT_NAMES } from '../../constants'

const navCls = ({ isActive }) => 'nav-item' + (isActive ? ' active' : '')

const THEME_COLORS = {
  dark:'#58a6ff', midnight:'#7c6af7', forest:'#4caf80',
  amber:'#f0a020', rose:'#e060a0', ocean:'#38b0e8', light:'#0969da',
}

export default function Sidebar() {
  const { pendingCount, setPending, theme, setTheme, THEMES, toast,
          fontKey, setFont, FONTS, fontSize, setFontSize, FONT_SIZES } = useApp()
  const [founderStats, setFounderStats] = useState({})
  const [balances,     setBalances]     = useState({})
  const [stopping,     setStopping]     = useState(false)
  const navigate = useNavigate()

  useEffect(() => {
    const load = () => {
      getDraftStats().then(s => setPending(s.pending_count || 0)).catch(() => {})
      getFounderStats().then(setFounderStats).catch(() => {})
      getEconomyBalances().then(setBalances).catch(() => {})
    }
    load()
    const t = setInterval(load, 30000)
    return () => clearInterval(t)
  }, [setPending])

  const founderAlerts = (founderStats.unread_mail || 0)
    + (founderStats.spawn_requests || 0)
    + (founderStats.draft_endeavors || 0)

  // Find top-balance dept for weekly leader
  const topDept = Object.entries(balances).sort((a,b) => b[1]-a[1])[0]

  const stopServer = async () => {
    if (!window.confirm('Stop the Think Tank server?')) return
    setStopping(true)
    try { await fetch('/api/server/stop', { method: 'POST' }) } catch {}
    toast('Server stopping…')
  }

  return (
    <aside className="sidebar" style={{ display:'flex', flexDirection:'column' }}>
      <div className="sidebar-header">
        <h1>🏛️ Think Tank</h1>
        <p>Central Operations</p>
      </div>

      {/* Theme pills */}
      <div style={{ padding:'8px 14px 2px', display:'flex', gap:5, flexWrap:'wrap', alignItems:'center' }}>
        {THEMES.map(t => (
          <button key={t} title={t}
            className={`theme-pill${theme===t?' active':''}`}
            style={{ background: THEME_COLORS[t] }}
            onClick={() => setTheme(t)} />
        ))}
      </div>

      {/* Server status */}
      <div style={{ padding:'2px 14px 6px', display:'flex', alignItems:'center', gap:6, fontSize:10, color:'var(--muted)' }}>
        <span className={`server-dot${stopping?' stopping':''}`} />
        {stopping ? 'Stopping…' : 'Online'}
        {topDept && (
          <span style={{ marginLeft:'auto', fontSize:9, color:'var(--green)', fontWeight:700 }}>
            🏆 {topDept[0]} {topDept[1]}pts
          </span>
        )}
      </div>

      {/* Founder Inbox */}
      <div style={{ padding:'4px 12px' }}>
        <NavLink to="/founder" className={navCls}
          style={{ background:'rgba(248,81,73,0.08)', borderRadius:7, border:'1px solid rgba(248,81,73,0.2)' }}>
          <span>👑</span> Founder Inbox
          {founderAlerts > 0 && <span className="badge" style={{ background:'var(--red)' }}>{founderAlerts}</span>}
        </NavLink>
      </div>

      <nav className="nav-section">
        <div className="nav-label">Overview</div>
        <NavLink to="/dashboard"   className={navCls}><span>📊</span> Dashboard</NavLink>
        <NavLink to="/drafts"      className={navCls}>
          <span>📋</span> Drafts
          {pendingCount > 0 && <span className="badge">{pendingCount}</span>}
        </NavLink>
        <NavLink to="/mail"        className={navCls}><span>📨</span> Mail Room</NavLink>
        <NavLink to="/ask"         className={navCls}><span>💬</span> Ask</NavLink>
        <NavLink to="/endeavors"   className={navCls}><span>🚀</span> Endeavors</NavLink>
        <NavLink to="/agents"      className={navCls}><span>🤖</span> Agents</NavLink>
        <NavLink to="/economy"     className={navCls}><span>💰</span> Economy</NavLink>
        <NavLink to="/marketplace" className={navCls}><span>🏪</span> Marketplace</NavLink>
      </nav>

      <nav className="nav-section">
        <div className="nav-label">Departments</div>
        {DEPT_IDS.map(id => (
          <NavLink key={id} to={`/dept/${id}`} className={navCls}>
            <span className="dot" style={{ background: COLORS[id] }} />
            {DEPT_NAMES[id].split(' & ')[0]}
            {balances[id] !== undefined && (
              <span style={{ marginLeft:'auto', fontSize:9, color: balances[id] < 50 ? 'var(--red)' : 'var(--muted)' }}>
                {balances[id]}
              </span>
            )}
          </NavLink>
        ))}
      </nav>

      <button className="btn-nd-sidebar" onClick={() => navigate('/ask')}>＋ New Draft</button>

      <nav className="nav-section">
        <div className="nav-label">Admin</div>
        <NavLink to="/projects"   className={navCls}><span>📁</span> Projects</NavLink>
        <NavLink to="/audit"      className={navCls}><span>🔍</span> Audit Log</NavLink>
        <NavLink to="/prompts"    className={navCls}><span>🔧</span> Prompts</NavLink>
        <NavLink to="/extensions" className={navCls}><span>🧩</span> Extensions</NavLink>
        <NavLink to="/files"      className={navCls}><span>📁</span> Files</NavLink>
        <NavLink to="/settings"   className={navCls}><span>⚙️</span> Settings</NavLink>
      </nav>

      {/* Font controls */}
      <div style={{ padding:'6px 12px', borderTop:'1px solid var(--border)', marginTop:'auto' }}>
        <div style={{ fontSize:9, color:'var(--muted)', textTransform:'uppercase', letterSpacing:'0.06em', marginBottom:4 }}>Font</div>
        <div style={{ display:'flex', gap:4, flexWrap:'wrap', marginBottom:4 }}>
          {Object.entries(FONTS).map(([k, f]) => (
            <button key={k}
              style={{ fontSize:9, padding:'2px 7px', borderRadius:4, border:'1px solid var(--border)',
                background: fontKey===k ? 'var(--accent)' : 'var(--bg)', color: fontKey===k ? '#000' : 'var(--muted)',
                cursor:'pointer', transition:'all 0.15s', fontFamily: f.value }}
              onClick={() => setFont(k)}>
              {f.label}
            </button>
          ))}
        </div>
        <div style={{ display:'flex', gap:3 }}>
          {Object.keys(FONT_SIZES).map(s => (
            <button key={s}
              style={{ fontSize:9, padding:'2px 6px', borderRadius:4, border:'1px solid var(--border)',
                background: fontSize===s ? 'var(--accent)' : 'var(--bg)', color: fontSize===s ? '#000' : 'var(--muted)',
                cursor:'pointer', transition:'all 0.15s' }}
              onClick={() => setFontSize(s)}>
              {s[0].toUpperCase()}
            </button>
          ))}
        </div>
      </div>

      {/* Stop server */}
      <div style={{ padding:'6px 12px 12px' }}>
        <button onClick={stopServer} disabled={stopping}
          style={{ width:'100%', padding:'7px', borderRadius:7, fontSize:11, fontWeight:700,
            background:'rgba(248,81,73,0.08)', border:'1px solid rgba(248,81,73,0.25)',
            color:'var(--red)', cursor:'pointer', transition:'all 0.15s', opacity: stopping ? 0.5 : 1 }}>
          {stopping ? '⏳ Stopping…' : '⏹ Stop Server'}
        </button>
      </div>
    </aside>
  )
}
