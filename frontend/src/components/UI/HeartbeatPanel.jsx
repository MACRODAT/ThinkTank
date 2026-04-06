import React, { useState, useEffect, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { getHeartbeatStatus, triggerHeartbeat } from '../../api'
import { COLORS } from '../../constants'
import Spinner from '../UI/Spinner'

function fmtAgo(iso) {
  if (!iso) return 'never'
  const s = Math.floor((Date.now() - new Date(iso).getTime()) / 1000)
  if (s < 60)    return `${s}s ago`
  if (s < 3600)  return `${Math.floor(s/60)}m ago`
  return `${Math.floor(s/3600)}h ago`
}

export default function HeartbeatPanel() {
  const navigate   = useNavigate()
  const [data,     setData]     = useState(null)
  const [running,  setRunning]  = useState(null)
  const [expanded, setExpanded] = useState(false)
  const pollRef = useRef(null)

  const load = useCallback(async () => {
    const d = await getHeartbeatStatus().catch(() => null)
    if (d) setData(d)
  }, [])

  useEffect(() => {
    load()
    pollRef.current = setInterval(load, 15000)
    return () => clearInterval(pollRef.current)
  }, [load])

  const handleRun = async (e, id) => {
    e.stopPropagation()
    setRunning(id)
    await triggerHeartbeat(id).catch(() => {})
    setRunning(null)
    await load()
  }

  if (!data || !data.agents?.length) return null

  const agents   = data.agents
  const next2    = agents.slice(0, 2)
  const rest     = agents.slice(2)

  // Compute "time since last beat" to figure out who's most overdue (= next)
  const withDue = agents.map(a => {
    const last    = a.last_heartbeat ? new Date(a.last_heartbeat).getTime() : 0
    const dueAt   = last + (a.heartbeat_interval || 5) * 60 * 1000
    const overdue = dueAt - Date.now()
    return { ...a, dueAt, overdue }
  }).sort((a, b) => a.overdue - b.overdue)

  const nextUp = withDue[0]
  const comingUp = withDue.slice(1, 4)

  return (
    <div className="hb-panel">
      <div className="hb-panel-title" style={{ cursor:'pointer' }} onClick={() => setExpanded(v => !v)}>
        <span style={{ animation: 'pulse 2s infinite', display:'inline-block', width:8, height:8, borderRadius:'50%', background:'var(--green)' }} />
        Agent Heartbeat Queue · {data.queue_length} active
        <span style={{ marginLeft:'auto', color:'var(--muted)', fontWeight:400 }}>{expanded ? '▲ collapse' : '▼ expand'}</span>
      </div>

      {/* Next up — always visible */}
      {nextUp && (
        <div className="hb-row" style={{ background:`${COLORS[nextUp.dept_id]||'#607D8B'}0a`, borderRadius:6, padding:'8px 10px', marginBottom:4 }}>
          <div className="hb-dot hb-dot-next" />
          <span style={{ fontSize:13, fontWeight:700, flex:1 }}>
            {nextUp.name}
            {nextUp.is_ceo && <span style={{ marginLeft:5, fontSize:10, color:'gold' }}>👑</span>}
          </span>
          <span className="dept-tag" style={{ background: COLORS[nextUp.dept_id]||'#607D8B', fontSize:9 }}>{nextUp.dept_id}</span>
          <span style={{ fontSize:11, color:'var(--orange)', minWidth:60, textAlign:'right' }}>
            {nextUp.overdue < 0 ? `in ${Math.ceil(Math.abs(nextUp.overdue)/60000)}m` : 'overdue'}
          </span>
          <button className="btn btn-outline btn-sm" style={{ padding:'2px 8px', fontSize:11 }}
            onClick={e => handleRun(e, nextUp.id)} disabled={running===nextUp.id}>
            {running===nextUp.id ? <Spinner/> : '❤ Run'}
          </button>
          <button className="btn btn-ghost btn-sm" style={{ padding:'2px 6px', fontSize:11 }}
            onClick={e => { e.stopPropagation(); navigate(`/agents/${nextUp.id}`) }}>→</button>
        </div>
      )}

      {/* Queue preview */}
      {comingUp.map((a, i) => (
        <div key={a.id} className="hb-row">
          <div className="hb-dot hb-dot-idle" />
          <span style={{ fontSize:12, flex:1, color:'var(--muted)' }}>
            <span style={{ color:'var(--text)', fontWeight:600 }}>{a.name}</span>
            {a.is_ceo && <span style={{ marginLeft:4, fontSize:10, color:'gold' }}>👑</span>}
          </span>
          <span className="dept-tag" style={{ background: COLORS[a.dept_id]||'#607D8B', fontSize:9 }}>{a.dept_id}</span>
          <span style={{ fontSize:11, color:'var(--muted)', minWidth:60, textAlign:'right' }}>
            {a.overdue < 0 ? `in ${Math.ceil(Math.abs(a.overdue)/60000)}m` : 'overdue'}
          </span>
          <span style={{ fontSize:10, color:'var(--muted)', minWidth:70, textAlign:'right' }}>
            last: {fmtAgo(a.last_heartbeat)}
          </span>
        </div>
      ))}

      {/* Expanded view: all agents + last summary */}
      {expanded && (
        <div style={{ marginTop:10, borderTop:'1px solid var(--border)', paddingTop:10 }}>
          {withDue.map(a => (
            <div key={a.id} className="hb-row" style={{ alignItems:'flex-start' }}>
              <div className="hb-dot" style={{ marginTop:4,
                background: a.last_result === 'error' ? 'var(--red)' : a.last_heartbeat ? 'var(--green)' : 'var(--border)' }} />
              <div style={{ flex:1, minWidth:0 }}>
                <div style={{ display:'flex', alignItems:'center', gap:6 }}>
                  <span style={{ fontSize:12, fontWeight:600, cursor:'pointer', color:'var(--text)' }}
                    onClick={() => navigate(`/agents/${a.id}`)}>
                    {a.name}
                  </span>
                  {a.is_ceo && <span style={{ fontSize:10, color:'gold' }}>👑</span>}
                  <span className="dept-tag" style={{ background: COLORS[a.dept_id]||'#607D8B', fontSize:9 }}>{a.dept_id}</span>
                  <span style={{ fontSize:10, color:'var(--muted)' }}>{a.title || a.role}</span>
                </div>
                {a.last_summary && (
                  <div style={{ fontSize:11, color:'var(--muted)', marginTop:2, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>
                    {a.last_summary}
                  </div>
                )}
              </div>
              <div style={{ textAlign:'right', flexShrink:0 }}>
                <div style={{ fontSize:10, color:'var(--muted)' }}>last: {fmtAgo(a.last_heartbeat)}</div>
                <div style={{ fontSize:10, color: a.overdue > 0 ? 'var(--orange)' : 'var(--muted)' }}>
                  next: {a.overdue < 0 ? `in ${Math.ceil(Math.abs(a.overdue)/60000)}m` : 'overdue'}
                </div>
              </div>
              <button className="btn btn-ghost btn-sm" style={{ padding:'2px 8px', fontSize:11, flexShrink:0 }}
                onClick={e => handleRun(e, a.id)} disabled={running===a.id}>
                {running===a.id ? <Spinner/> : '❤'}
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
