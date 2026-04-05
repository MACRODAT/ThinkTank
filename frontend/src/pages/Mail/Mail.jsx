import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { getAllMail, markRead } from '../../api'
import { COLORS, DEPT_IDS } from '../../constants'
import Spinner from '../../components/UI/Spinner'

export default function Mail() {
  const [mails,   setMails]   = useState([])
  const [filter,  setFilter]  = useState('all')
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    getAllMail().then(setMails).finally(() => setLoading(false))
  }, [])

  const filtered = filter === 'all' ? mails
    : mails.filter(m => m.from_dept === filter || m.to_dept === filter)

  const open = async (m) => {
    if (m.status === 'unread') await markRead(m.id).catch(() => {})
    navigate(`/mail/${m.thread_id}`)
  }

  return (
    <div>
      <div className="page-header">
        <h2>📨 Mail Room</h2>
        <p>Inter-department communications</p>
      </div>

      <div style={{ marginBottom:16 }}>
        <select className="form-control" style={{ maxWidth:220 }}
          value={filter} onChange={e => setFilter(e.target.value)}>
          <option value="all">All Departments</option>
          {DEPT_IDS.map(id => <option key={id} value={id}>{id}</option>)}
        </select>
      </div>

      <div className="card" style={{ padding:0 }}>
        {loading ? <div className="empty"><Spinner/></div>
          : filtered.length === 0 ? <div className="empty">No mail found</div>
          : filtered.map(m => {
            const u = m.status === 'unread'
            return (
              <div key={m.id} className={`mail-item${u?' unread':''}`} onClick={() => open(m)}>
                <span className="arrow-badge" style={{ background: COLORS[m.from_dept]||'#607D8B' }}>{m.from_dept}</span>
                <span style={{ color:'var(--muted)', fontSize:12 }}>→</span>
                <span className="arrow-badge" style={{ background: COLORS[m.to_dept]||'#607D8B' }}>{m.to_dept}</span>
                <div style={{ flex:1, minWidth:0, padding:'0 10px' }}>
                  <div className="mail-subject">{u && '● '}<strong>{m.subject}</strong></div>
                  <div style={{ fontSize:11, color:'var(--muted)', overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>
                    {m.body?.substring(0,80)}…
                  </div>
                </div>
                <div style={{ textAlign:'right', flexShrink:0 }}>
                  <div className="mail-time">{m.created_at?.substring(0,16).replace('T',' ')}</div>
                  <div style={{ fontSize:10, color: m.priority==='urgent'?'var(--red)':m.priority==='high'?'var(--orange)':'var(--muted)' }}>
                    {m.priority}
                  </div>
                </div>
              </div>
            )
          })
        }
      </div>
    </div>
  )
}
