import React, { useState, useEffect } from 'react'
import { getAuditLog } from '../api'
import { COLORS } from '../constants'
import Spinner from '../components/UI/Spinner'

const EVT_ICON = {
  cycle_start:'🔄', cycle_error:'❌', mail_sent:'📨',
  draft_created:'📝', draft_reviewed:'✅', orchestrator_run:'🏛️', ai_thinking:'🧠'
}

export default function Audit() {
  const [events, setEvents] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getAuditLog(100).then(setEvents).finally(() => setLoading(false))
  }, [])

  return (
    <div>
      <div className="page-header"><h2>🔍 Audit Log</h2><p>Full activity history</p></div>
      <div className="card" style={{ padding:0 }}>
        {loading ? <div className="empty"><Spinner/></div>
          : events.length === 0 ? <div className="empty">No events yet</div>
          : events.map(e => (
            <div key={e.id} style={{ display:'flex', gap:12, padding:'10px 16px', borderBottom:'1px solid var(--border)', alignItems:'flex-start' }}>
              <span style={{ fontSize:16, flexShrink:0 }}>{EVT_ICON[e.event_type]||'📌'}</span>
              <div style={{ flex:1, minWidth:0 }}>
                <div style={{ fontSize:13, fontWeight:600 }}>
                  {e.dept_id && <span style={{ color:COLORS[e.dept_id]||'#607D8B', marginRight:4 }}>[{e.dept_id}]</span>}
                  {e.description}
                </div>
                <div style={{ fontSize:11, color:'var(--muted)', marginTop:2 }}>{e.event_type}</div>
              </div>
              <div style={{ fontSize:11, color:'var(--muted)', whiteSpace:'nowrap', flexShrink:0 }}>
                {e.created_at?.substring(0,16).replace('T',' ')}
              </div>
            </div>
          ))
        }
      </div>
    </div>
  )
}
