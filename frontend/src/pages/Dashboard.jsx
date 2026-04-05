import React, { useState, useEffect } from 'react'
import { getDepartments, getDraftStats, runDepartment, runAllDepts } from '../api'
import { useApp } from '../context/AppContext'
import { COLORS, ICONS } from '../constants'
import Spinner from '../components/UI/Spinner'

export default function Dashboard() {
  const { toast } = useApp()
  const [depts, setDepts] = useState([])
  const [stats, setStats] = useState({})
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState('')

  useEffect(() => {
    Promise.all([getDepartments(), getDraftStats()])
      .then(([d, s]) => { setDepts(d); setStats(s) })
      .finally(() => setLoading(false))
  }, [])

  const runAll = async () => {
    setRunning('all')
    try { await runAllDepts(); toast('All cycles started') }
    catch(e) { toast('Failed: ' + e.message, 'error') }
    setRunning('')
  }

  const runOne = async (id) => {
    setRunning(id)
    try { await runDepartment(id); toast(`${id} cycle started`) }
    catch(e) { toast('Failed: ' + e.message, 'error') }
    setRunning('')
  }

  const totalMail = depts.reduce((s,d) => s + (d.unread_mail||0), 0)

  if (loading) return <div className="empty"><Spinner lg /></div>

  return (
    <div>
      <div className="page-header">
        <h2>🏛️ Central Think Tank</h2>
        <p>Live overview of all departments and pending work</p>
      </div>

      <div style={{ display:'flex', gap:12, alignItems:'center', marginBottom:24 }}>
        <button className="btn btn-primary" onClick={runAll} disabled={running==='all'}>
          {running==='all' ? <><Spinner/> Starting…</> : '▶ Run All Departments'}
        </button>
      </div>

      <div className="grid grid-3" style={{ marginBottom:24 }}>
        <div className="card stat"><div className="stat-value">{depts.length}</div><div className="stat-label">Departments</div></div>
        <div className="card stat"><div className="stat-value" style={{ color:'var(--orange)' }}>{stats.pending_count||0}</div><div className="stat-label">Pending Drafts</div></div>
        <div className="card stat"><div className="stat-value" style={{ color:'var(--accent)' }}>{totalMail}</div><div className="stat-label">Unread Mail</div></div>
      </div>

      <div className="grid grid-2">
        {depts.map(d => (
          <div key={d.id} className="card dept-card" style={{ borderLeftColor: COLORS[d.id]||'#607D8B' }}>
            <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start' }}>
              <div>
                <div className="dept-name">{d.name}</div>
                <div className="dept-code" style={{ fontSize:11, color:'var(--muted)' }}>{d.code}</div>
              </div>
              <span style={{ fontSize:22 }}>{ICONS[d.id]||'🏛️'}</span>
            </div>
            <div className="dept-stats">
              <div className="dept-stat">
                <div className="dept-stat-val" style={{ color:'var(--orange)' }}>{d.pending_drafts||0}</div>
                <div className="dept-stat-lbl">Drafts</div>
              </div>
              <div className="dept-stat">
                <div className="dept-stat-val" style={{ color:'var(--accent)' }}>{d.unread_mail||0}</div>
                <div className="dept-stat-lbl">Mail</div>
              </div>
            </div>
            <button className="run-btn" onClick={() => runOne(d.id)} disabled={running===d.id}
              style={{ marginTop:14,width:'100%',padding:8,borderRadius:6,border:'1px solid var(--border)',
                background:'transparent',color:'var(--text)',cursor:'pointer',fontSize:12,transition:'all .15s' }}>
              {running===d.id ? <><Spinner/> Running…</> : '▶ Run Cycle'}
            </button>
            <div style={{ fontSize:11, color:'var(--muted)', marginTop:8 }}>
              Last: {d.last_run ? d.last_run.replace('T',' ').substring(0,16) : 'Never'}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
