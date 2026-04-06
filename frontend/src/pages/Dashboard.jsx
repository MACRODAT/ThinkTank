import React, { useState, useEffect, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  getDepartments, getDraftStats, runDepartment, runAllDepts,
  getTodayTasks, getCalendarEvents, toggleObjective,
} from '../api'
import { useApp } from '../context/AppContext'
import { COLORS, ICONS } from '../constants'
import Spinner from '../components/UI/Spinner'
import HeartbeatPanel from '../components/UI/HeartbeatPanel'
import HeartbeatMonitor from '../components/UI/HeartbeatMonitor'
// ── Mini Calendar ─────────────────────────────────────────────────────────────

function MiniCalendar({ events = {} }) {
  const today = new Date()
  const [viewDate, setViewDate] = useState(new Date(today.getFullYear(), today.getMonth(), 1))
  const [selected, setSelected] = useState(today.toISOString().split('T')[0])

  const year  = viewDate.getFullYear()
  const month = viewDate.getMonth()   // 0-indexed

  const firstDayOfWeek = new Date(year, month, 1).getDay()
  const daysInMonth    = new Date(year, month + 1, 0).getDate()
  const todayStr       = today.toISOString().split('T')[0]

  const prevMonth = () => setViewDate(new Date(year, month - 1, 1))
  const nextMonth = () => setViewDate(new Date(year, month + 1, 1))

  const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
  const DAYS   = ['Su','Mo','Tu','We','Th','Fr','Sa']

  const cells = []
  for (let i = 0; i < firstDayOfWeek; i++) cells.push(null)
  for (let d = 1; d <= daysInMonth; d++) cells.push(d)

  return (
    <div className="mini-cal">
      <div className="mini-cal-header">
        <button className="mini-cal-nav" onClick={prevMonth}>‹</button>
        <span style={{ fontWeight:700, fontSize:13 }}>{MONTHS[month]} {year}</span>
        <button className="mini-cal-nav" onClick={nextMonth}>›</button>
      </div>
      <div className="mini-cal-grid">
        {DAYS.map(d => <div key={d} className="mini-cal-dow">{d}</div>)}
        {cells.map((day, i) => {
          if (!day) return <div key={`e${i}`} />
          const iso = `${year}-${String(month+1).padStart(2,'0')}-${String(day).padStart(2,'0')}`
          const evts = events[iso] || []
          const isToday    = iso === todayStr
          const isSelected = iso === selected

          return (
            <div key={iso}
              className={`mini-cal-day${isToday?' today':''}${isSelected?' selected':''}`}
              onClick={() => setSelected(iso)}
            >
              <span>{day}</span>
              {evts.length > 0 && (
                <div className="mini-cal-dots">
                  {evts.slice(0,3).map((e,i) => (
                    <span key={i} className="mini-cal-dot" style={{ background: e.color || 'var(--accent)' }}
                      title={`${e.type === 'phase_start' ? '▶ Start' : '⏹ End'}: ${e.name} (${e.endeavor})`} />
                  ))}
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* Selected day events */}
      {events[selected] && events[selected].length > 0 && (
        <div className="mini-cal-events">
          {events[selected].map((e,i) => (
            <div key={i} style={{ display:'flex', alignItems:'center', gap:6, fontSize:12, padding:'4px 0' }}>
              <span style={{ width:8, height:8, borderRadius:'50%', background:e.color, flexShrink:0, display:'inline-block' }} />
              <span style={{ color:'var(--muted)' }}>{e.type === 'phase_start' ? '▶' : '⏹'}</span>
              <span><strong>{e.name}</strong> · {e.endeavor}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Today task item ───────────────────────────────────────────────────────────

function TodayTask({ task, onToggle, overdue }) {
  const navigate = useNavigate()
  return (
    <div className={`today-task${overdue?' overdue':''}${task.is_done?' done':''}`}>
      <button className="obj-check" onClick={() => onToggle(task.id)}>
        {task.is_done ? '✓' : ''}
      </button>
      <div style={{ flex:1, minWidth:0 }}>
        <div style={{ fontSize:13, fontWeight:600, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>
          {task.title}
        </div>
        <div style={{ fontSize:11, color:'var(--muted)', marginTop:1, display:'flex', gap:6, alignItems:'center' }}>
          <span style={{ width:8, height:8, borderRadius:'50%', background: task.endeavor_color||'var(--accent)', display:'inline-block', flexShrink:0 }} />
          <span>{task.endeavor_name}</span>
          <span>·</span>
          <span>{task.phase_name}</span>
          {overdue && task.effective_end && (
            <span style={{ color:'var(--red)', fontWeight:600 }}>· due {task.effective_end}</span>
          )}
        </div>
      </div>
      <button className="btn btn-ghost btn-sm" onClick={() => navigate(`/endeavors/${task.endeavor_id}`)}>→</button>
    </div>
  )
}

// ── Dashboard ─────────────────────────────────────────────────────────────────

export default function Dashboard() {
  const { toast } = useApp()
  const navigate  = useNavigate()

  const [depts,        setDepts]       = useState([])
  const [stats,        setStats]       = useState({})
  const [todayTasks,   setTodayTasks]  = useState({ today: [], overdue: [] })
  const [calEvents,    setCalEvents]   = useState({})
  const [loading,      setLoading]     = useState(true)
  const [loadingTasks, setLoadingTasks]= useState(true)
  const [running,      setRunning]     = useState('')

  const today = new Date()

  const load = useCallback(async () => {
    setLoading(true)
    const [d, s] = await Promise.all([getDepartments(), getDraftStats()])
    setDepts(d); setStats(s)
    setLoading(false)
  }, [])

  const loadTasks = useCallback(async () => {
    setLoadingTasks(true)
    const [tasks, cal] = await Promise.all([
      getTodayTasks().catch(() => ({ today:[], overdue:[] })),
      getCalendarEvents(today.getFullYear(), today.getMonth()+1).catch(() => ({ events:{} })),
    ])
    setTodayTasks(tasks)
    setCalEvents(cal.events || {})
    setLoadingTasks(false)
  }, [])

  useEffect(() => { load(); loadTasks() }, [])

  const runAll = async () => {
    setRunning('all')
    try { await runAllDepts(); toast('All cycles started') }
    catch(e) { toast('Failed: ' + e.message, 'error') }
    setRunning('')
  }

  const runOne = async (id) => {
    setRunning(id)
    try { await runDepartment(id); toast(`${id} cycle started`) }
    catch(e) { toast('Failed', 'error') }
    setRunning('')
  }

  const handleToggle = async (id) => {
    await toggleObjective(id)
    loadTasks()
  }

  const totalMail = depts.reduce((s,d) => s + (d.unread_mail||0), 0)
  const pendingToday  = todayTasks.today?.filter(t => !t.is_done) || []
  const overdueItems  = todayTasks.overdue?.filter(t => !t.is_done) || []

  return (
    <div>
      <div className="page-header">
        <h2>🏛️ Central Think Tank</h2>
        <p>Live overview · {today.toLocaleDateString('en-GB', { weekday:'long', year:'numeric', month:'long', day:'numeric' })}</p>
      </div>

      <div style={{ display:'flex', gap:12, alignItems:'center', marginBottom:24 }}>
        <button className="btn btn-primary" onClick={runAll} disabled={running==='all'}>
          {running==='all' ? <><Spinner/> Starting…</> : '▶ Run All Departments'}
        </button>
        <button className="btn btn-outline" onClick={() => navigate('/endeavors')}>
          🚀 Endeavors
        </button>
      </div>

      {/* Stats */}
      <HeartbeatPanel />
      <div className="grid grid-3" style={{ marginBottom:24 }}>
        <div className="card stat"><div className="stat-value">{depts.length}</div><div className="stat-label">Departments</div></div>
        <div className="card stat"><div className="stat-value" style={{ color:'var(--orange)' }}>{stats.pending_count||0}</div><div className="stat-label">Pending Drafts</div></div>
        <div className="card stat"><div className="stat-value" style={{ color:'var(--accent)' }}>{totalMail}</div><div className="stat-label">Unread Mail</div></div>
      </div>

      {/* Main two-column layout */}
      <div style={{ display:'grid', gridTemplateColumns:'1fr 320px', gap:20, alignItems:'start' }}>

        {/* LEFT: Department cards */}
        <div>
          {loading ? <div className="empty"><Spinner lg /></div> : (
            <div className="grid grid-2">
              {depts.map(d => (
                <div key={d.id} className="card dept-card" style={{ borderLeftColor: COLORS[d.id]||'#607D8B', cursor:'pointer' }}
                  onClick={() => navigate(`/dept/${d.id}`)}>
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
                  <button className="run-btn" onClick={e => { e.stopPropagation(); runOne(d.id) }} disabled={running===d.id}>
                    {running===d.id ? <><Spinner/> Running…</> : '▶ Run Cycle'}
                  </button>
                  <div style={{ fontSize:11, color:'var(--muted)', marginTop:8 }}>
                    Last: {d.last_run ? d.last_run.replace('T',' ').substring(0,16) : 'Never'}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* RIGHT: Calendar + Today's Tasks */}
        <div style={{ display:'flex', flexDirection:'column', gap:16 }}>

          {/* Mini Calendar */}
          <div className="card" style={{ padding:0 }}>
            <div style={{ padding:'12px 16px', borderBottom:'1px solid var(--border)' }}>
              <span className="card-title">📅 Endeavor Calendar</span>
            </div>
            <MiniCalendar events={calEvents} />
          </div>

          {/* Heartbeat Monitor */}
          <HeartbeatMonitor />

          {/* Today's Tasks */}
          <div className="card" style={{ padding:0 }}>
            <div style={{ padding:'12px 16px', borderBottom:'1px solid var(--border)', display:'flex', alignItems:'center', gap:8 }}>
              <span className="card-title">🎯 Today's Tasks</span>
              {pendingToday.length > 0 && (
                <span style={{ background:'var(--orange)', color:'#000', fontSize:10, fontWeight:700, padding:'1px 6px', borderRadius:10, marginLeft:'auto' }}>
                  {pendingToday.length}
                </span>
              )}
            </div>
            {loadingTasks ? <div className="empty" style={{ padding:20 }}><Spinner/></div> : (
              pendingToday.length === 0 ? (
                <div className="empty" style={{ padding:'20px 16px', fontSize:12 }}>
                  ✓ No active tasks from current phases
                </div>
              ) : (
                <div>
                  {pendingToday.map(t => <TodayTask key={t.id} task={t} onToggle={handleToggle} />)}
                </div>
              )
            )}
          </div>

          {/* Overdue Tasks */}
          {overdueItems.length > 0 && (
            <div className="card" style={{ padding:0, border:'1px solid rgba(248,81,73,.3)' }}>
              <div style={{ padding:'12px 16px', borderBottom:'1px solid rgba(248,81,73,.3)', display:'flex', alignItems:'center', gap:8 }}>
                <span className="card-title" style={{ color:'var(--red)' }}>⚠ Overdue</span>
                <span style={{ background:'var(--red)', color:'#fff', fontSize:10, fontWeight:700, padding:'1px 6px', borderRadius:10, marginLeft:'auto' }}>
                  {overdueItems.length}
                </span>
              </div>
              {overdueItems.map(t => <TodayTask key={t.id} task={t} onToggle={handleToggle} overdue />)}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
