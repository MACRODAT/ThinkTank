import React, { useState, useRef, useCallback, useEffect } from 'react'
import DeptTag from '../UI/DeptTag'
import MarkdownPreview from './MarkdownPreview'
import SlashPalette from './SlashPalette'
import { updateDraft, reviewDraft } from '../../api'
import { useApp } from '../../context/AppContext'
import { DRAFT_TYPES, PRIORITIES } from '../../constants'

// Panel display updateDraft
const MODE = { SPLIT: 'split', FULL: 'full', PREVIEW: 'preview', MINI: 'mini' }

export default function FullScreenEditor({ draft, onClose, onSaved }) {
  const { toast } = useApp()

  const [title,     setTitle]     = useState(draft?.title      || '')
  const [content,   setContent]   = useState(draft?.content    || '')
  const [draftType, setDraftType] = useState(draft?.draft_type || 'strategy')
  const [priority,  setPriority]  = useState(draft?.priority   || 'normal')
  const [saving,    setSaving]    = useState(false)
  const [mode,      setMode]      = useState(MODE.SPLIT)
  const [slash,     setSlash]     = useState(null)
  const [slashStart,setSlashStart]= useState(-1)
  const [prevMode,  setPrevMode]  = useState(MODE.SPLIT)

  const undos = useRef([])
  const redos = useRef([])
  const taRef = useRef(null)

  const wordCount = content.trim().split(/\s+/).filter(Boolean).length

  // Undo snapshot
  const snap = useCallback(() => {
    const v = taRef.current?.value ?? content
    if (!undos.current.length || undos.current[undos.current.length - 1] !== v) {
      undos.current.push(v); redos.current = []
      if (undos.current.length > 100) undos.current.shift()
    }
  }, [content])

  const patch = async (action) => {
    setSaving(true)
    try {
      await updateDraft(draft.id, { title, content, draft_type: draftType, priority })
      if (action) await reviewDraft(draft.id, action)
      toast(action ? `Saved & ${action}` : 'Saved ✓')
      onSaved?.()
      if (action) onClose()
    } catch(e) { toast('Save failed: ' + e.message, 'error') }
    setSaving(false)
  }

  // Minimize / restore
  const minimize = () => { setPrevMode(mode); setMode(MODE.MINI) }
  const restore  = () => setMode(prevMode)

  // ── Toolbar helpers ──────────────────────────────────────────────────
  const wrap = (pre, post, linePrefix) => {
    const ta = taRef.current; if (!ta) return
    const s = ta.selectionStart, e = ta.selectionEnd, sel = content.substring(s, e)
    snap()
    const rep = linePrefix
      ? (sel || 'text').split('\n').map(l => pre + l).join('\n')
      : pre + (sel || 'text') + post
    const next = content.substring(0, s) + rep + content.substring(e)
    setContent(next)
    setTimeout(() => { ta.selectionStart = s; ta.selectionEnd = s + rep.length }, 0)
  }

  const ins = (txt) => {
    const ta = taRef.current; if (!ta) return
    const s = ta.selectionStart; snap()
    setContent(content.substring(0, s) + txt + content.substring(s))
    setTimeout(() => { ta.selectionStart = ta.selectionEnd = s + txt.length }, 0)
  }

  // ── Keyboard shortcuts ───────────────────────────────────────────────
  const handleKD = (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 's') { e.preventDefault(); patch(null); return }
    if ((e.ctrlKey || e.metaKey) && !e.shiftKey && e.key === 'z') {
      e.preventDefault()
      if (undos.current.length < 2) return
      redos.current.push(undos.current.pop())
      setContent(undos.current[undos.current.length - 1])
      return
    }
    if ((e.ctrlKey || e.metaKey) && (e.key === 'y' || (e.shiftKey && e.key === 'z'))) {
      e.preventDefault()
      if (!redos.current.length) return
      const v = redos.current.pop(); undos.current.push(v); setContent(v)
      return
    }
    if (e.key === 'Tab')    { e.preventDefault(); ins('    '); return }
    if (e.key === 'Escape') { setSlash(null); return }
  }

  const handleKU = (e) => {
    const ta = taRef.current; if (!ta) return
    const pos = ta.selectionStart
    if (e.key === '/') {
      setSlashStart(pos - 1)
      const rect = ta.getBoundingClientRect()
      const lines = content.substring(0, pos).split('\n')
      const ln = lines.length
      setSlash({
        top:  Math.min(rect.top  + ln * 27 - ta.scrollTop + 10, window.innerHeight - 380),
        left: Math.min(rect.left + Math.min(lines[ln-1].length * 8, 300), window.innerWidth - 320),
      })
      return
    }
    if (!slash) return
    if (slashStart >= 0 && pos > slashStart) {
      if (/\n/.test(content.substring(slashStart + 1, pos))) setSlash(null)
    } else { setSlash(null) }
  }

  const handleSlashSelect = (block) => {
    const ta = taRef.current; if (!ta) return
    const pos = ta.selectionStart
    const before = content.substring(0, slashStart)
    const after  = content.substring(pos)
    snap()
    setContent(before + block.ins + after)
    setTimeout(() => { ta.selectionStart = ta.selectionEnd = before.length + block.ins.length }, 0)
    setSlash(null)
  }

  // status pill colours
  const statusBg    = draft?.status === 'approved' ? 'rgba(63,185,80,.18)'   : draft?.status === 'rejected' ? 'rgba(248,81,73,.18)'   : 'rgba(210,153,34,.18)'
  const statusColor = draft?.status === 'approved' ? 'var(--green)'           : draft?.status === 'rejected' ? 'var(--red)'             : 'var(--orange)'

  // ── MINIMIZED CHIP ───────────────────────────────────────────────────
  if (mode === MODE.MINI) {
    return (
      <div className="sp-mini" onClick={restore}>
        <span style={{ fontSize: 14 }}>✏️</span>
        <DeptTag id={draft?.dept_id} />
        <span style={{ fontSize: 12, color: 'var(--text)', maxWidth: 260, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {title || 'Untitled'}
        </span>
        <span style={{ fontSize: 11, background: statusBg, color: statusColor, padding: '2px 8px', borderRadius: 4, fontWeight: 700, textTransform: 'uppercase', flexShrink: 0 }}>
          {draft?.status}
        </span>
        <button className="btn btn-primary btn-sm" onClick={e => { e.stopPropagation(); restore() }}>
          ⊞ Open
        </button>
        <button className="btn btn-ghost btn-sm" onClick={e => { e.stopPropagation(); onClose() }}>✕</button>
      </div>
    )
  }

  // ── FULL OVERLAY (split / full / preview) ────────────────────────────
  return (
    <div className="sp-overlay" data-mode={mode}>
      {/* ── Top bar ── */}
      <div className="sp-topbar">
        <div className="sp-topbar-left">
          <DeptTag id={draft?.dept_id} />
          <span style={{ fontSize: 13, color: 'var(--muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 320 }}>
            {title || 'Untitled'}
          </span>
          <span style={{ fontSize: 11, background: statusBg, color: statusColor, padding: '3px 9px', borderRadius: 4, fontWeight: 700, textTransform: 'uppercase', flexShrink: 0 }}>
            {draft?.status}
          </span>
        </div>

        <div className="sp-topbar-right">
          {/* Mode switcher */}
          <div className="sp-mode-group">
            <button className={`sp-mode-btn${mode===MODE.FULL?    ' active':''}`} onClick={() => setMode(MODE.FULL)}    title="Editor full width">✎ Edit</button>
            <button className={`sp-mode-btn${mode===MODE.SPLIT?   ' active':''}`} onClick={() => setMode(MODE.SPLIT)}   title="50 / 50 split">⊟ Split</button>
            <button className={`sp-mode-btn${mode===MODE.PREVIEW?' active':''}`} onClick={() => setMode(MODE.PREVIEW)} title="Preview full width">👁 Preview</button>
          </div>

          {/* Type + priority */}
          <select className="fs-sel" value={draftType} onChange={e => setDraftType(e.target.value)}>
            {DRAFT_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
          </select>
          <select className="fs-sel" value={priority} onChange={e => setPriority(e.target.value)}>
            {PRIORITIES.map(p => <option key={p} value={p}>{p.charAt(0).toUpperCase() + p.slice(1)}</option>)}
          </select>

          {/* Actions */}
          <button className="btn btn-success btn-sm" onClick={() => patch(null)} disabled={saving}>
            {saving ? '⏳' : '💾 Save'}
          </button>
          <button className="btn btn-primary btn-sm" onClick={() => patch('approved')}>✓ Approve</button>
          <button className="btn btn-danger  btn-sm" onClick={() => patch('rejected')}>✗ Reject</button>
          <button className="btn btn-ghost   btn-sm" onClick={minimize} title="Minimize to chip">⊟</button>
          <button className="btn btn-ghost   btn-sm" onClick={onClose}  title="Close editor">✕</button>
        </div>
      </div>

      {/* ── Markdown toolbar (hidden in preview-only mode) ── */}
      {mode !== MODE.PREVIEW && (
        <div className="sp-toolbar">
          {[['H1','# '],['H2','## '],['H3','### '],['H4','#### ']].map(([l,p]) => (
            <button key={l} className="tbtn" onClick={() => wrap(p,'',true)}>{l}</button>
          ))}
          <div className="tsep"/>
          <button className="tbtn" onClick={() => wrap('**','**')}><b>B</b></button>
          <button className="tbtn" onClick={() => wrap('*','*')}><i>I</i></button>
          <button className="tbtn" onClick={() => wrap('~~','~~')}><s>S</s></button>
          <button className="tbtn" onClick={() => wrap('`','`')}>{'`c`'}</button>
          <div className="tsep"/>
          <button className="tbtn" onClick={() => wrap('- ','',true)}>• List</button>
          <button className="tbtn" onClick={() => {
            const sel = content.substring(taRef.current?.selectionStart||0, taRef.current?.selectionEnd||0) || 'Item'
            ins(sel.split('\n').map((l,i) => `${i+1}. ${l}`).join('\n'))
          }}>1. List</button>
          <button className="tbtn" onClick={() => wrap('> ','',true)}>❝ Quote</button>
          <button className="tbtn" onClick={() => ins('\n---\n')}>─ Divider</button>
          <button className="tbtn" onClick={() => ins('\n| Col 1 | Col 2 |\n|-------|-------|\n| Cell  | Cell  |\n')}>⊞ Table</button>
          <button className="tbtn" onClick={() => ins('\n```\ncode\n```\n')}>{'{ } Code'}</button>
          <button className="tbtn" onClick={() => ins(new Date().toISOString().split('T')[0])}>📅</button>
          <div className="tsep"/>
          <button className="tbtn" onClick={() => { if(undos.current.length>=2){redos.current.push(undos.current.pop());setContent(undos.current[undos.current.length-1])} }}>↩</button>
          <button className="tbtn" onClick={() => { if(redos.current.length){const v=redos.current.pop();undos.current.push(v);setContent(v)} }}>↪</button>
          <div className="tsep"/>
          <span style={{ fontSize:11, color:'var(--muted)', padding:'0 4px' }}>Type <kbd>/</kbd> for blocks</span>
        </div>
      )}

      {/* ── Body ── */}
      <div className="sp-body">
        {/* LEFT PANE: editor */}
        {mode !== MODE.PREVIEW && (
          <div className="sp-left">
            <div className="sp-pane-header">
              <span style={{ fontSize:11, fontWeight:700, textTransform:'uppercase', color:'var(--muted)', letterSpacing:'.06em' }}>Editor</span>
              <span style={{ fontSize:11, color:'var(--muted)', marginLeft:'auto' }}>
                {wordCount.toLocaleString()} words · {content.length.toLocaleString()} chars
              </span>
            </div>
            <div style={{ flex:1, overflow:'hidden', display:'flex', flexDirection:'column', padding:'0 0 12px 0' }}>
              <textarea
                className="sp-title-inp"
                placeholder="Untitled Document"
                rows={1}
                value={title}
                onChange={e => setTitle(e.target.value)}
                onInput={e => { e.target.style.height='auto'; e.target.style.height=e.target.scrollHeight+'px' }}
              />
              <textarea
                ref={taRef}
                className="sp-content-inp"
                placeholder="Start writing… or type / to insert a block"
                value={content}
                onChange={e => setContent(e.target.value)}
                onKeyDown={handleKD}
                onKeyUp={handleKU}
              />
            </div>
            <div className="sp-pane-footer">
              <span style={{ fontSize:11, color:'var(--muted)' }}>
                <kbd>Ctrl+S</kbd> Save &nbsp;<kbd>/</kbd> Blocks &nbsp;<kbd>Tab</kbd> Indent
              </span>
            </div>
          </div>
        )}

        {/* RIGHT PANE: live preview */}
        {mode !== MODE.FULL && (
          <div className="sp-right">
            <div className="sp-pane-header">
              <span style={{ fontSize:11, fontWeight:700, textTransform:'uppercase', color:'var(--muted)', letterSpacing:'.06em' }}>Live Preview</span>
            </div>
            <MarkdownPreview content={content} />
          </div>
        )}
      </div>

      {slash && (
        <SlashPalette pos={slash} onSelect={handleSlashSelect} onClose={() => setSlash(null)} />
      )}
    </div>
  )
}
