import React, { useState, useEffect } from 'react'
import { getDrafts, getPendingDrafts, getDraft, reviewDraft } from '../api'
import { useApp } from '../context/AppContext'
import Spinner from '../components/UI/Spinner'
import DeptTag from '../components/UI/DeptTag'
import PriorityDot from '../components/UI/PriorityDot'
import FullScreenEditor from '../components/Editor/FullScreenEditor'
import DraftViewer from '../components/Editor/DraftViewer'

export default function Drafts() {
  const { toast } = useApp()
  const [tab,     setTab]     = useState('pending')
  const [drafts,  setDrafts]  = useState([])
  const [loading, setLoading] = useState(true)
  const [viewing, setViewing] = useState(null)  // draft object for viewer
  const [editing, setEditing] = useState(null)  // draft object for editor

  const load = async () => {
    setLoading(true)
    try {
      const data = tab === 'pending' ? await getPendingDrafts() : await getDrafts()
      setDrafts(data)
    } finally { setLoading(false) }
  }

  useEffect(() => { load() }, [tab])

  const openView = async (id) => { const d = await getDraft(id); setViewing(d) }
  const openEdit = async (id) => { const d = await getDraft(id); setEditing(d) }

  const quickReview = async (id, action) => {
    await reviewDraft(id, action)
    toast(`Draft ${action}`)
    load()
  }

  return (
    <div>
      <div className="page-header">
        <h2>📋 Draft Vault</h2>
        <p>AI-generated documents awaiting your review</p>
      </div>

      <div className="tabs">
        {['pending','all'].map(t => (
          <button key={t} className={`tab${tab===t?' active':''}`} onClick={() => setTab(t)}>
            {t === 'pending' ? 'Pending' : 'All Drafts'}
          </button>
        ))}
      </div>

      <div className="card" style={{ padding:0 }}>
        {loading
          ? <div className="empty"><Spinner/></div>
          : drafts.length === 0
            ? <div className="empty">✓ No drafts here</div>
            : drafts.map(d => (
              <div key={d.id} className="draft-item">
                <PriorityDot priority={d.priority} />
                <DeptTag id={d.dept_id} />
                <div className="draft-info">
                  <div className="draft-title">{d.title}</div>
                  <div className="draft-meta">
                    {d.draft_type?.toUpperCase()} · {d.created_at?.substring(0,16).replace('T',' ')}
                    {d.status !== 'pending' && (
                      <span style={{ marginLeft:6, color: d.status==='approved'?'var(--green)':'var(--red)', fontWeight:600 }}>
                        {d.status}
                      </span>
                    )}
                  </div>
                </div>
                <div className="draft-actions">
                  <button className="btn btn-outline btn-sm" onClick={() => openEdit(d.id)}>✏ Edit</button>
                  <button className="btn btn-ghost   btn-sm" onClick={() => openView(d.id)}>👁 View</button>
                  {d.status === 'pending' && <>
                    <button className="btn btn-success btn-sm" onClick={() => quickReview(d.id,'approved')}>✓</button>
                    <button className="btn btn-danger  btn-sm" onClick={() => quickReview(d.id,'rejected')}>✗</button>
                  </>}
                </div>
              </div>
          ))
        }
      </div>

      {/* Split-pane viewer with markdown rendering */}
      {viewing && (
        <DraftViewer
          draft={viewing}
          onClose={() => setViewing(null)}
          onReviewed={() => { setViewing(null); load() }}
        />
      )}

      {/* Split-pane editor with live preview */}
      {editing && (
        <FullScreenEditor
          draft={editing}
          onClose={() => setEditing(null)}
          onSaved={() => { load(); setEditing(null) }}
        />
      )}
    </div>
  )
}
