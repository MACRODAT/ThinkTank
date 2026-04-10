import React, { useState } from 'react'
import DeptTag from '../UI/DeptTag'
import MarkdownPreview from './MarkdownPreview'
import { reviewDraft } from '../../api'
import { useApp } from '../../context/AppContext'
import { PRIO_COLORS } from '../../constants'

const MODE = { SPLIT: 'split', INFO: 'info', PREVIEW: 'preview', MINI: 'mini' }

export default function DraftViewer({ draft, onClose, onReviewed }) {
  const { toast } = useApp()
  const [mode,     setMode]    = useState(MODE.SPLIT)
  const [prevMode, setPrevMode]= useState(MODE.SPLIT)
  const [acting,   setActing]  = useState(false)

  const doReview = async (action) => {
    setActing(true)
    try {
      await reviewDraft(draft.id, action)
      toast(`Draft ${action}`)
      onReviewed?.()
      onClose()
    } catch(e) { toast(e.message, 'error') }
    setActing(false)
  }

  const minimize = () => { setPrevMode(mode); setMode(MODE.MINI) }
  const restore  = () => setMode(prevMode)

  const statusBg    = draft?.status === 'approved' ? 'rgba(63,185,80,.18)'  : draft?.status === 'rejected' ? 'rgba(248,81,73,.18)'  : 'rgba(210,153,34,.18)'
  const statusColor = draft?.status === 'approved' ? 'var(--green)'          : draft?.status === 'rejected' ? 'var(--red)'            : 'var(--orange)'

  // ── MINIMIZED CHIP ───────────────────────────────────────────────────
  if (mode === MODE.MINI) {
    return (
      <div className="sp-mini" onClick={restore}>
        <span style={{ fontSize:14 }}>📄</span>
        <DeptTag id={draft?.dept_id} />
        <span style={{ fontSize:12, color:'var(--text)', maxWidth:260, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>
          {draft?.title || 'Untitled'}
        </span>
        <span style={{ fontSize:11, background:statusBg, color:statusColor, padding:'2px 8px', borderRadius:4, fontWeight:700, textTransform:'uppercase', flexShrink:0 }}>
          {draft?.status}
        </span>
        <button className="btn btn-primary btn-sm" onClick={e => { e.stopPropagation(); restore() }}>⊞ Open</button>
        <button className="btn btn-ghost   btn-sm" onClick={e => { e.stopPropagation(); onClose() }}>✕</button>
      </div>
    )
  }

  // ── FULL OVERLAY ─────────────────────────────────────────────────────
  return (
    <div className="sp-overlay" data-mode={mode === MODE.INFO ? 'full' : mode === MODE.PREVIEW ? 'preview' : 'split'} style={{'height': '80vh'}}>

      {/* ── Top bar ── */}
      <div className="sp-topbar">
        <div className="sp-topbar-left">
          <DeptTag id={draft?.dept_id} />
          <span style={{ fontSize:13, color:'var(--muted)', overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap', maxWidth:320 }}>
            {draft?.title}
          </span>
          <span style={{ fontSize:11, background:statusBg, color:statusColor, padding:'3px 9px', borderRadius:4, fontWeight:700, textTransform:'uppercase', flexShrink:0 }}>
            {draft?.status}
          </span>
        </div>

        <div className="sp-topbar-right">
          {/* Mode switcher */}
          <div className="sp-mode-group">
            <button className={`sp-mode-btn${mode===MODE.INFO?    ' active':''}`} onClick={() => setMode(MODE.INFO)}    title="Info panel full width">ℹ Info</button>
            <button className={`sp-mode-btn${mode===MODE.SPLIT?   ' active':''}`} onClick={() => setMode(MODE.SPLIT)}   title="50 / 50 split">⊟ Split</button>
            <button className={`sp-mode-btn${mode===MODE.PREVIEW?' active':''}`} onClick={() => setMode(MODE.PREVIEW)} title="Preview full width">👁 Preview</button>
          </div>

          {draft?.status === 'pending' && <>
            <button className="btn btn-success btn-sm" onClick={() => doReview('approved')} disabled={acting}>✓ Approve</button>
            <button className="btn btn-danger  btn-sm" onClick={() => doReview('rejected')} disabled={acting}>✗ Reject</button>
          </>}
          <button className="btn btn-ghost btn-sm" onClick={minimize} title="Minimize to chip">⊟</button>
          <button className="btn btn-ghost btn-sm" onClick={onClose}  title="Close">✕</button>
        </div>
      </div>

      {/* ── Body ── */}
      <div className="sp-body">
        {/* LEFT PANE: info */}
        {mode !== MODE.PREVIEW && (
          <div className="sp-left">
            <div className="sp-pane-header">
              <span style={{ fontSize:11, fontWeight:700, textTransform:'uppercase', color:'var(--muted)', letterSpacing:'.06em' }}>Document Info</span>
            </div>
            <div style={{ flex:1, overflowY:'auto', padding:'24px 28px' }}>
              <h2 style={{ fontSize:22, fontWeight:800, marginBottom:16, lineHeight:1.3 }}>{draft?.title}</h2>

              <div style={{ display:'flex', flexDirection:'column', gap:12 }}>
                {[
                  ['Department', <DeptTag id={draft?.dept_id} />],
                  ['Type',       <span style={{ fontSize:13, textTransform:'uppercase', color:'var(--muted)' }}>{draft?.draft_type?.replace(/_/g,' ')}</span>],
                  ['Priority',   <span style={{ fontSize:13, fontWeight:700, color:PRIO_COLORS[draft?.priority], textTransform:'uppercase' }}>{draft?.priority}</span>],
                  ['Status',     <span style={{ fontSize:13, fontWeight:700, background:statusBg, color:statusColor, padding:'2px 10px', borderRadius:4, textTransform:'uppercase' }}>{draft?.status}</span>],
                  ['Created',    <span style={{ fontSize:13, color:'var(--muted)' }}>{draft?.created_at?.substring(0,16).replace('T',' ')}</span>],
                ].map(([label, value]) => (
                  <div key={label} style={{ display:'flex', alignItems:'center', gap:12, padding:'8px 0', borderBottom:'1px solid var(--border)' }}>
                    <span style={{ fontSize:11, fontWeight:700, color:'var(--muted)', textTransform:'uppercase', width:90, flexShrink:0 }}>{label}</span>
                    {value}
                  </div>
                ))}
              </div>

              {draft?.status === 'pending' && (
                <div style={{ display:'flex', flexDirection:'column', gap:10, marginTop:28 }}>
                  <p style={{ fontSize:12, color:'var(--muted)', marginBottom:4 }}>Review Actions</p>
                  <button className="btn btn-success" style={{ justifyContent:'center', padding:'10px' }}
                    onClick={() => doReview('approved')} disabled={acting}>
                    ✓ Approve Document
                  </button>
                  <button className="btn btn-danger" style={{ justifyContent:'center', padding:'10px' }}
                    onClick={() => doReview('rejected')} disabled={acting}>
                    ✗ Reject Document
                  </button>
                </div>
              )}

              {/* Word count */}
              <div style={{ marginTop:28, padding:'14px', background:'var(--bg)', borderRadius:8, border:'1px solid var(--border)' }}>
                <div style={{ fontSize:11, color:'var(--muted)', marginBottom:8, fontWeight:700, textTransform:'uppercase' }}>Statistics</div>
                <div style={{ display:'flex', gap:20 }}>
                  {[
                    ['Words',   draft?.content?.trim().split(/\s+/).filter(Boolean).length ?? 0],
                    ['Chars',   draft?.content?.length ?? 0],
                    ['Lines',   draft?.content?.split('\n').length ?? 0],
                  ].map(([l,v]) => (
                    <div key={l} style={{ textAlign:'center' }}>
                      <div style={{ fontSize:20, fontWeight:800 }}>{v.toLocaleString()}</div>
                      <div style={{ fontSize:11, color:'var(--muted)' }}>{l}</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* RIGHT PANE: rendered markdown */}
        {mode !== MODE.INFO && (
          <div className="sp-right">
            <div className="sp-pane-header">
              <span style={{ fontSize:11, fontWeight:700, textTransform:'uppercase', color:'var(--muted)', letterSpacing:'.06em' }}>Rendered Document</span>
            </div>
            <MarkdownPreview content={draft?.content} />
          </div>
        )}
      </div>
    </div>
  )
}
