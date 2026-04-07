import React, { useState, useEffect, useCallback } from 'react'
import { getDrafts, getPendingDrafts, getDraft, reviewDraft, updateDraft } from '../api'
import { useApp } from '../context/AppContext'
import Spinner from '../components/UI/Spinner'
import DeptTag from '../components/UI/DeptTag'
import PriorityDot from '../components/UI/PriorityDot'
import FullScreenEditor from '../components/Editor/FullScreenEditor'
import DraftViewer from '../components/Editor/DraftViewer'

// Status colors and labels
const STATUS_STYLE = {
  pending:  { color: 'var(--orange)',  bg: 'rgba(210,153,34,.12)',  label: 'Pending'  },
  revised:  { color: 'var(--red)',     bg: 'rgba(248,81,73,.12)',   label: '📝 Revised' },
  approved: { color: 'var(--green)',   bg: 'rgba(63,185,80,.12)',   label: '✓ Approved' },
  rejected: { color: 'var(--muted)',   bg: 'rgba(139,148,158,.1)',  label: '✗ Rejected' },
  archived: { color: 'var(--muted)',   bg: 'transparent',           label: 'Archived' },
}

// ── Revision notes panel ─────────────────────────────────────────────────────
function RevisionPanel({ draft, onDone }) {
  const { toast } = useApp()
  const [notes,  setNotes]  = useState('')
  const [saving, setSaving] = useState(false)
  const [open,   setOpen]   = useState(false)

  const submit = async () => {
    if (!notes.trim()) return
    setSaving(true)
    // Mark as 'revised' with notes — blocks approval until creator re-reviews
    await reviewDraft(draft.id, 'revised', notes, 'founder')
    toast('Revision notes added — draft marked as Revised ✓')
    setSaving(false); setNotes(''); setOpen(false); onDone?.()
  }

  if (!open) return (
    <button className="btn btn-outline btn-sm" onClick={() => setOpen(true)} title="Request changes">
      📝 Notes
    </button>
  )

  return (
    <div style={{
      position: 'absolute', right: 0, top: '100%', zIndex: 50,
      background: 'var(--surface)', border: '1px solid var(--accent)',
      borderRadius: 8, padding: 12, width: 340,
      boxShadow: '0 8px 32px rgba(0,0,0,.6)',
    }}>
      <div style={{ fontSize: 12, fontWeight: 700, marginBottom: 6, color: 'var(--orange)' }}>
        📝 Request Revision
      </div>
      <p style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 8, lineHeight: 1.5 }}>
        This will mark the draft as <strong>Revised</strong> — it cannot be approved until the
        original author reviews your notes.
      </p>
      <textarea className="form-control" rows={4}
        style={{ fontSize: 12, resize: 'vertical', marginBottom: 8 }}
        placeholder="Describe what needs to change…"
        value={notes} onChange={e => setNotes(e.target.value)} autoFocus />
      <div style={{ display: 'flex', gap: 6 }}>
        <button className="btn btn-danger btn-sm" style={{ flex: 1 }}
          onClick={submit} disabled={saving || !notes.trim()}>
          {saving ? <Spinner /> : '📝 Submit & Mark Revised'}
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
    const d = drafts.find(x => x.id === id)
    // Block approving a revised draft
    if (action === 'approved' && d?.status === 'revised') {
      toast('Cannot approve — draft has revision notes. Creator must review first.', 'error')
      return
    }
    await reviewDraft(id, action, undefined, 'founder')
    toast(`Draft ${action}`)
    load()
  }

  const pendingCount = drafts.length

  return (
    <div>
      <div className="page-header">
        <h2>📋 Draft Vault</h2>
        <p>Documents awaiting review — approve, request revisions, or reject</p>
      </div>

      <div className="tabs">
        {[
          { key: 'pending', label: `Pending${tab==='pending' && pendingCount ? ` (${pendingCount})` : ''}` },
          { key: 'all',     label: 'All Drafts' },
        ].map(t => (
          <button key={t.key} className={`tab${tab===t.key?' active':''}`} onClick={() => setTab(t.key)}>
            {t.label}
          </button>
        ))}
      </div>

      <div className="card" style={{ padding: 0 }}>
        {loading ? (
          <div className="empty"><Spinner /></div>
        ) : drafts.length === 0 ? (
          <div className="empty">✓ No drafts here</div>
        ) : (
          drafts.map(d => {
            const ss = STATUS_STYLE[d.status] || STATUS_STYLE.pending
            const isRevised = d.status === 'revised'

            return (
              <div key={d.id} className="draft-item" style={{
                position: 'relative',
                borderLeft: isRevised ? '3px solid var(--red)' : undefined,
                background: isRevised ? 'rgba(248,81,73,.03)' : undefined,
              }}>
                <PriorityDot priority={d.priority} />
                <DeptTag id={d.dept_id} />
                <div className="draft-info">
                  <div className="draft-title">{d.title}</div>
                  <div className="draft-meta" style={{ display:'flex', gap:8, flexWrap:'wrap', alignItems:'center' }}>
                    <span style={{ textTransform:'uppercase', fontSize:10 }}>{d.draft_type}</span>
                    <span style={{ color:'var(--muted)' }}>·</span>
                    <span>{d.created_at?.substring(0,10)}</span>

                    {/* Status badge */}
                    <span style={{ fontSize:10, fontWeight:700, color:ss.color,
                      background:ss.bg, padding:'1px 7px', borderRadius:4 }}>
                      {ss.label}
                    </span>

                    {/* Reviewer info */}
                    {d.reviewed_by && d.reviewed_at && (
                      <span style={{ fontSize:10, color:'var(--muted)' }}>
                        by {d.reviewed_by} @ {d.reviewed_at?.substring(0,10)}
                      </span>
                    )}
                    {d.revised_by && d.revised_at && (
                      <span style={{ fontSize:10, color:'var(--orange)' }}>
                        · revised by {d.revised_by} @ {d.revised_at?.substring(0,10)}
                      </span>
                    )}
                  </div>

                  {/* Show revision note preview */}
                  {isRevised && d.review_notes && (
                    <div style={{ fontSize:11, color:'var(--orange)', marginTop:4, lineHeight:1.5,
                      borderLeft:'2px solid var(--orange)', paddingLeft:8 }}>
                      📝 {d.review_notes.substring(0, 120)}{d.review_notes.length > 120 ? '…' : ''}
                    </div>
                  )}
                </div>

                <div className="draft-actions">
                  <button className="btn btn-outline btn-sm" onClick={() => openEdit(d.id)}>✏ Edit</button>
                  <button className="btn btn-ghost   btn-sm" onClick={() => openView(d.id)}>👁 View</button>
                  {(d.status === 'pending' || d.status === 'revised') && (
                    <>
                      {/* Revision notes — only for pending (can't add more notes to already-revised) */}
                      {d.status === 'pending' && (
                        <div style={{ position: 'relative' }}>
                          <RevisionPanel draft={d} onDone={load} />
                        </div>
                      )}
                      {/* Can only approve if NOT in revised state */}
                      {d.status === 'pending' && (
                        <button className="btn btn-success btn-sm" onClick={() => quickReview(d.id, 'approved')}>✓</button>
                      )}
                      {/* Can always reject */}
                      <button className="btn btn-danger btn-sm" onClick={() => quickReview(d.id, 'rejected')}>✗</button>
                      {/* If revised, allow reverting to pending after creator has reviewed */}
                      {d.status === 'revised' && (
                        <button className="btn btn-outline btn-sm" title="Mark as reviewed by creator — allow approval"
                          onClick={() => { reviewDraft(d.id, 'pending', null, 'founder').then(() => { toast('Reset to pending'); load() }) }}>
                          ↩ Reset
                        </button>
                      )}
                    </>
                  )}
                </div>
              </div>
            )
          })
        )}
      </div>

      {viewing && (
        <DraftViewer draft={viewing} onClose={() => setViewing(null)}
          onReviewed={() => { setViewing(null); load() }} />
      )}
      {editing && (
        <FullScreenEditor draft={editing} onClose={() => setEditing(null)}
          onSaved={() => { load(); setEditing(null) }} />
      )}
    </div>
  )
}
