import React, { useState, useEffect, useCallback } from 'react'
import { getDrafts, getPendingDrafts, getDraft, reviewDraft, updateDraft, getAgents } from '../api'
import { useApp } from '../context/AppContext'
import Spinner from '../components/UI/Spinner'
import DeptTag from '../components/UI/DeptTag'
import PriorityDot from '../components/UI/PriorityDot'
import FullScreenEditor from '../components/Editor/FullScreenEditor'
import DraftViewer from '../components/Editor/DraftViewer'
import { DEPT_IDS } from '../constants'

const STATUS_STYLE = {
  pending:  { color:'var(--orange)', bg:'rgba(210,153,34,.12)',  label:'Pending'   },
  revised:  { color:'var(--red)',    bg:'rgba(248,81,73,.12)',   label:'📝 Revised' },
  approved: { color:'var(--green)',  bg:'rgba(63,185,80,.12)',   label:'✓ Approved' },
  rejected: { color:'var(--muted)', bg:'rgba(139,148,158,.1)',  label:'✗ Rejected' },
  archived: { color:'var(--muted)', bg:'transparent',           label:'Archived'  },
}

const DRAFT_TYPES = ['strategy','memo','report','weekly_report','policy','other']

function RevisionPanel({ draft, onDone }) {
  const { toast } = useApp()
  const [notes,  setNotes]  = useState('')
  const [saving, setSaving] = useState(false)
  const [open,   setOpen]   = useState(false)
  const submit = async () => {
    if (!notes.trim()) return
    setSaving(true)
    await reviewDraft(draft.id, 'revised', notes, 'founder')
    toast('Revision notes added ✓')
    setSaving(false); setNotes(''); setOpen(false); onDone?.()
  }
  if (!open) return (
    <button className="btn btn-outline btn-sm" onClick={() => setOpen(true)}>📝 Notes</button>
  )
  return (
    <div style={{ position:'absolute', right:0, top:'100%', zIndex:50,
      background:'var(--surface)', border:'1px solid var(--accent)',
      borderRadius:8, padding:12, width:340, boxShadow:'0 8px 32px rgba(0,0,0,.6)' }}>
      <div style={{ fontSize:12, fontWeight:700, marginBottom:6, color:'var(--orange)' }}>📝 Request Revision</div>
      <textarea className="form-control" rows={4} style={{ fontSize:12, resize:'vertical', marginBottom:8 }}
        placeholder="Describe what needs to change…"
        value={notes} onChange={e => setNotes(e.target.value)} autoFocus />
      <div style={{ display:'flex', gap:6 }}>
        <button className="btn btn-danger btn-sm" style={{ flex:1 }} onClick={submit} disabled={saving || !notes.trim()}>
          {saving ? <Spinner /> : '📝 Submit'}
        </button>
        <button className="btn btn-ghost btn-sm" onClick={() => { setOpen(false); setNotes('') }}>✕</button>
      </div>
    </div>
  )
}

export default function Drafts() {
  const { toast } = useApp()
  const [tab,       setTab]       = useState('pending')
  const [allDrafts, setAllDrafts] = useState([])
  const [loading,   setLoading]   = useState(true)
  const [viewing,   setViewing]   = useState(null)
  const [editing,   setEditing]   = useState(null)

  // Filters
  const [fType,   setFType]   = useState('')
  const [fDept,   setFDept]   = useState('')
  const [fStatus, setFStatus] = useState('')
  const [fFrom,   setFFrom]   = useState('')
  const [fTo,     setFTo]     = useState('')
  const [fSearch, setFSearch] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const params = tab === 'pending'
        ? {}
        : { limit: 200, ...(fDept && { dept_id: fDept }) }
      const data = tab === 'pending'
        ? await getPendingDrafts(fDept || undefined)
        : await getDrafts(params)
      setAllDrafts(data)
    } finally { setLoading(false) }
  }, [tab, fDept])

  useEffect(() => { load() }, [load])

  const drafts = allDrafts.filter(d => {
    if (fType   && d.draft_type !== fType)                        return false
    if (fStatus && d.status     !== fStatus)                      return false
    if (fFrom   && d.created_at?.substring(0,10) < fFrom)         return false
    if (fTo     && d.created_at?.substring(0,10) > fTo)           return false
    if (fSearch && !d.title?.toLowerCase().includes(fSearch.toLowerCase()) &&
                   !d.content?.toLowerCase().includes(fSearch.toLowerCase())) return false
    return true
  })

  const openView = async (id) => { const d = await getDraft(id); setViewing(d) }
  const openEdit = async (id) => { const d = await getDraft(id); setEditing(d) }

  const quickReview = async (id, action) => {
    const d = allDrafts.find(x => x.id === id)
    if (action === 'approved' && d?.status === 'revised') {
      toast('Cannot approve — revision notes pending.', 'error'); return
    }
    await reviewDraft(id, action, undefined, 'founder')
    toast(`Draft ${action}`)
    load()
  }

  return (
    <div>
      <div className="page-header">
        <h2>📋 Draft Vault</h2>
        <p>Review, approve, and manage all AI-generated documents</p>
      </div>

      <div className="tabs">
        <button className={`tab${tab==='pending'?' active':''}`} onClick={() => setTab('pending')}>
          ⏳ Pending {tab==='pending' && drafts.length > 0 && <span className="badge" style={{ marginLeft:4 }}>{drafts.length}</span>}
        </button>
        <button className={`tab${tab==='all'?' active':''}`} onClick={() => setTab('all')}>📚 All Drafts</button>
      </div>

      {/* Filter bar */}
      <div style={{ display:'flex', gap:8, marginBottom:14, flexWrap:'wrap', alignItems:'center',
        padding:'10px 14px', background:'var(--surface)', borderRadius:8, border:'1px solid var(--border)' }}>
        <input className="form-control" style={{ maxWidth:180, marginBottom:0 }}
          placeholder="🔍 Search title/content…" value={fSearch} onChange={e => setFSearch(e.target.value)} />
        <select className="form-control" style={{ maxWidth:130 }} value={fType} onChange={e => setFType(e.target.value)}>
          <option value="">All Types</option>
          {DRAFT_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
        </select>
        <select className="form-control" style={{ maxWidth:100 }} value={fDept} onChange={e => setFDept(e.target.value)}>
          <option value="">All Depts</option>
          {DEPT_IDS.map(d => <option key={d} value={d}>{d}</option>)}
        </select>
        {tab === 'all' && (
          <select className="form-control" style={{ maxWidth:120 }} value={fStatus} onChange={e => setFStatus(e.target.value)}>
            <option value="">All Statuses</option>
            {Object.keys(STATUS_STYLE).map(s => <option key={s} value={s}>{s}</option>)}
          </select>
        )}
        <input type="date" className="form-control" style={{ maxWidth:140 }} value={fFrom} onChange={e => setFFrom(e.target.value)} title="From date" />
        <input type="date" className="form-control" style={{ maxWidth:140 }} value={fTo}   onChange={e => setFTo(e.target.value)}   title="To date" />
        {(fType || fDept || fStatus || fFrom || fTo || fSearch) && (
          <button className="btn btn-ghost btn-sm" onClick={() => { setFType(''); setFDept(''); setFStatus(''); setFFrom(''); setFTo(''); setFSearch('') }}>
            ✕ Clear
          </button>
        )}
        <span style={{ fontSize:11, color:'var(--muted)', marginLeft:'auto' }}>{drafts.length} shown</span>
      </div>

      <div className="card" style={{ padding:0 }}>
        {loading ? (
          <div className="empty"><Spinner /></div>
        ) : drafts.length === 0 ? (
          <div className="empty">✓ No drafts match your filters</div>
        ) : drafts.map(d => {
          const ss        = STATUS_STYLE[d.status] || STATUS_STYLE.pending
          const isRevised = d.status === 'revised'
          return (
            <div key={d.id} className="draft-item" style={{
              position:'relative',
              borderLeft: isRevised ? '3px solid var(--red)' : undefined,
              background: isRevised ? 'rgba(248,81,73,.03)' : undefined,
            }}>
              <PriorityDot priority={d.priority} />
              <DeptTag id={d.dept_id} />
              <div className="draft-info">
                <div className="draft-title">{d.title}</div>
                <div className="draft-meta" style={{ display:'flex', gap:8, flexWrap:'wrap', alignItems:'center' }}>
                  <span style={{ textTransform:'uppercase', fontSize:10, color:'var(--accent)' }}>{d.draft_type}</span>
                  <span style={{ color:'var(--muted)' }}>·</span>
                  <span>{d.created_at?.substring(0,10)}</span>
                  {d.created_by_agent && <span style={{ fontSize:10, color:'var(--muted)' }}>by {d.created_by_agent.substring(0,8)}</span>}
                  <span style={{ fontSize:10, fontWeight:700, color:ss.color, background:ss.bg, padding:'1px 7px', borderRadius:4 }}>
                    {ss.label}
                  </span>
                  {d.reviewed_by && (
                    <span style={{ fontSize:10, color:'var(--muted)' }}>
                      reviewed by {d.reviewed_by}
                    </span>
                  )}
                </div>
                {isRevised && d.review_notes && (
                  <div style={{ fontSize:11, color:'var(--orange)', marginTop:4, lineHeight:1.5,
                    borderLeft:'2px solid var(--orange)', paddingLeft:8 }}>
                    📝 {d.review_notes.substring(0,120)}{d.review_notes.length > 120 ? '…' : ''}
                  </div>
                )}
              </div>
              <div className="draft-actions">
                <button className="btn btn-outline btn-sm" onClick={() => openEdit(d.id)}>✏</button>
                <button className="btn btn-ghost btn-sm"   onClick={() => openView(d.id)}>👁</button>
                {d.status === 'pending' && (
                  <>
                    <div style={{ position:'relative' }}><RevisionPanel draft={d} onDone={load} /></div>
                    <button className="btn btn-success btn-sm" onClick={() => quickReview(d.id,'approved')}>✓</button>
                  </>
                )}
                {(d.status === 'pending' || d.status === 'revised') && (
                  <button className="btn btn-danger btn-sm" onClick={() => quickReview(d.id,'rejected')}>✗</button>
                )}
                {d.status === 'revised' && (
                  <button className="btn btn-outline btn-sm" title="Reset to pending"
                    onClick={() => reviewDraft(d.id,'pending',null,'founder').then(() => { toast('Reset to pending'); load() })}>
                    ↩
                  </button>
                )}
              </div>
            </div>
          )
        })}
      </div>

      {viewing && <DraftViewer draft={viewing} onClose={() => setViewing(null)} onReviewed={() => { setViewing(null); load() }} />}
      {editing  && <FullScreenEditor draft={editing} onClose={() => setEditing(null)} onSaved={() => { load(); setEditing(null) }} />}
    </div>
  )
}
