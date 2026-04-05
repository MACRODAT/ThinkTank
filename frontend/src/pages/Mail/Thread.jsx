import React, { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getThread } from '../../api'
import Spinner from '../../components/UI/Spinner'
import DeptTag from '../../components/UI/DeptTag'

export default function Thread() {
  const { tid }   = useParams()
  const navigate  = useNavigate()
  const [thread,  setThread]  = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getThread(tid).then(setThread).finally(() => setLoading(false))
  }, [tid])

  const first = thread[0] || {}

  return (
    <div>
      <div style={{ marginBottom:16 }}>
        <button className="btn btn-ghost btn-sm" onClick={() => navigate('/mail')}>← Back to Mail</button>
      </div>
      <div className="page-header">
        <h2>{first.subject || 'Thread'}</h2>
        <p>{thread.length} message(s)</p>
      </div>
      {loading ? <div className="empty"><Spinner/></div> : (
        <div style={{ display:'flex', flexDirection:'column', gap:12 }}>
          {thread.map(m => (
            <div key={m.id} className="card">
              <div style={{ display:'flex', gap:10, alignItems:'center', marginBottom:12 }}>
                <DeptTag id={m.from_dept} />
                <span style={{ color:'var(--muted)', fontSize:12 }}>→</span>
                <DeptTag id={m.to_dept} />
                <span style={{ marginLeft:'auto', fontSize:11, color:'var(--muted)' }}>
                  {m.created_at?.substring(0,16).replace('T',' ')}
                </span>
              </div>
              <div style={{ fontSize:13, lineHeight:1.7, whiteSpace:'pre-wrap' }}>{m.body}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
