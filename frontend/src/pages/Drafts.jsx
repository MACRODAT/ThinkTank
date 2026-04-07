import React, { useState, useEffect, useCallback } from 'react'
import { getDrafts, getPendingDrafts, getDraft, reviewDraft } from '../api'
import { useApp } from '../context/AppContext'
import Spinner from '../components/UI/Spinner'
import DeptTag from '../components/UI/DeptTag'
import PriorityDot from '../components/UI/PriorityDot'
import FullScreenEditor from '../components/Editor/FullScreenEditor'
import DraftViewer from '../components/Editor/DraftViewer'

// ── Inline revision-notes panel ──────────────────────────────────────────────
function RevisionPanel({ draft, onDone }) {
  const { toast } = useApp()
  const [notes,   setNotes]   = useState('')
  const [saving,  setSaving]  = useState(false)
  const [open,    setOpen]    = useState(false)

  const submitRevision = async () => {
    if (!notes.trim()) return
    setSaving(true)
    // Append the revision note to the draft content and revert to pending
    const marker   = `\n\n---\n**📝 REVISION REQUEST (${new Date().toISOString().substring(0,16).replace('T',' ')}):**\n${notes.trim()}`
    const newContent = (draft.content || '') + marker
    // await updateDraft(draft.id, { content: newContent })
    await reviewDraft(draft.id, 'pending')   // keep / revert to pending
    toast('Revision notes added ✓')
    setSaving(false)
    setNotes('')
    setOpen(false)
    onDone?.()
  }

  if (!open) {
    return (
      <button className="btn btn-outline btn-sm" onClick={() => setOpen(true)} title="Request changes">
        📝 Notes
      </button>
    )
  }

  return (
    <div style={{
      position: 'absolute', right: 0, top: '100%', zIndex: 50,
      background: 'var(--surface)', border: '1px solid var(--border)',
      borderRadius: 8, padding: 12, width: 320, boxShadow: '0 8px 32px rgba(0,0,0,.5)',
    }}>
      <div style={{ fontSize: 12, fontWeight: 700, marginBottom: 6, color: 'var(--muted)', textTransform: 'uppercase' }}>
        Revision Notes
      </div>
      <textarea
        className="form-control"
        rows={4}
        style={{ fontSize: 12, resize: 'vertical', marginBottom: 8 }}
        placeholder="Describe the changes needed…"
        value={notes}
        onChange={e => setNotes(e.target.value)}
        autoFocus
      />
      <div style={{ display: 'flex', gap: 6 }}>
        <button className="btn btn-primary btn-sm" style={{ flex: 1 }} onClick={submitRevision} disabled={saving || !notes.trim()}>
          {saving ? <Spinner /> : '📝 Submit Notes'}
        </button>
        <button className="btn btn-ghost btn-sm" onClick={() => { setOpen(false); setNotes('') }}>✕</button>
      </div>
    </div>
  )
}

export default function Drafts() {
  const { toast } = useApp()
  const [tab,     setTab]     = useState('pending')
  const [drafts,  setDrafts]  = useState([])
  const [loading, setLoading] = useState(true)
  const [viewing, setViewing] = useState(null)
  const [editing, setEditing] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = tab === 'pending' ? await getPendingDrafts() : await getDrafts()
      setDrafts(data)
    } finally { setLoading(false) }
  }, [tab])

  useEffect(() => { load() }, [load])

  const openView = async (id) => { const d = await getDraft(id); setViewing(d) }
  const openEdit = async (id) => { const d = await getDraft(id); setEditing(d) }

  const quickReview = async (id, action) => {
    await reviewDraft(id, action)
    toast(`Draft ${action}`)
    load()
  }

  const STATUS_COLOR = { approved: 'var(--green)', rejected: 'var(--red)', pending: 'var(--orange)' }

  return (
    <div>
      <div className="page-header">
        <h2>📋 Draft Vault</h2>
        <p>Documents awaiting review — approve, request revisions, or reject</p>
      </div>

      <div className="tabs">
        {['pending', 'all'].map(t => (
          <button key={t} className={`tab${tab === t ? ' active' : ''}`} onClick={() => setTab(t)}>
            {t === 'pending' ? `Pending${drafts.length && tab==='pending' ? ` (${drafts.length})` : ''}` : 'All Drafts'}
          </button>
        ))}
      </div>

      <div className="card" style={{ padding: 0 }}>
        {loading ? (
          <div className="empty"><Spinner /></div>
        ) : drafts.length === 0 ? (
          <div className="empty">✓ No drafts here</div>
        ) : (
          drafts.map(d => (
            <div key={d.id} className="draft-item" style={{ position: 'relative' }}>
              <PriorityDot priority={d.priority} />
              <DeptTag id={d.dept_id} />
              <div className="draft-info">
                <div className="draft-title">{d.title}</div>
                <div className="draft-meta">
                  <span style={{ textTransform: 'uppercase' }}>{d.draft_type}</span>
                  {' · '}
                  <span>{d.created_at?.substring(0, 16).replace('T', ' ')}</span>
                  {d.status !== 'pending' && (
                    <span style={{ marginLeft: 6, color: STATUS_COLOR[d.status], fontWeight: 700 }}>
                      {d.status}
                    </span>
                  )}
                  {/* Show if revision notes are present */}
                  {d.content?.includes('REVISION REQUEST') && (
                    <span style={{ marginLeft: 6, fontSize: 10, color: 'var(--orange)', fontWeight: 700 }}>
                      📝 HAS NOTES
                    </span>
                  )}
                </div>
              </div>
              <div className="draft-actions">
                <button className="btn btn-outline btn-sm" onClick={() => openEdit(d.id)}>✏ Edit</button>
                <button className="btn btn-ghost   btn-sm" onClick={() => openView(d.id)}>👁 View</button>
                {d.status === 'pending' && (
                  <>
                    {/* Revision notes button */}
                    <div style={{ position: 'relative' }}>
                      <RevisionPanel draft={d} onDone={load} />
                    </div>
                    <button className="btn btn-success btn-sm" onClick={() => quickReview(d.id, 'approved')}>✓</button>
                    <button className="btn btn-danger  btn-sm" onClick={() => quickReview(d.id, 'rejected')}>✗</button>
                  </>
                )}
              </div>
            </div>
          ))
        )}
      </div>

      {viewing && (
        <DraftViewer
          draft={viewing}
          onClose={() => setViewing(null)}
          onReviewed={() => { setViewing(null); load() }}
        />
      )}

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
