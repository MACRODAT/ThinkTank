import React, { useState, useEffect } from 'react'
import { getDepartments, createDraft, runDepartment } from '../api'
import { useApp } from '../context/AppContext'
import { ICONS, DRAFT_TYPES, PRIORITIES } from '../constants'
import Spinner from '../components/UI/Spinner'

export default function Ask() {
  const { toast } = useApp()
  const [depts,   setDepts]   = useState([])
  const [deptId,  setDeptId]  = useState('HF')
  const [type,    setType]    = useState('memo')
  const [prio,    setPrio]    = useState('normal')
  const [prompt,  setPrompt]  = useState('')
  const [title,   setTitle]   = useState('')
  const [sending, setSending] = useState(false)
  const [status,  setStatus]  = useState(null)

  useEffect(() => { getDepartments().then(setDepts) }, [])

  const submit = async () => {
    if (!prompt.trim()) { setStatus({ ok:false, msg:'Prompt is required.' }); return }
    setSending(true); setStatus(null)
    try {
      const t = title.trim() || prompt.substring(0,60) + (prompt.length>60?'…':'')
      const res = await createDraft({ dept_id:deptId, draft_type:type, title:t, content:prompt, priority:prio })
      if (res.draft_id) {
        await runDepartment(deptId)
        setStatus({ ok:true, msg:`✓ Draft created & ${deptId} cycle triggered. Check Drafts when complete.` })
        setPrompt(''); setTitle('')
        toast('Prompt sent ✓')
      } else { setStatus({ ok:false, msg:'Server error.' }) }
    } catch(e) { setStatus({ ok:false, msg:e.message }) }
    setSending(false)
  }

  return (
    <div>
      <div className="page-header">
        <h2>💬 Ask</h2>
        <p>Send a one-off prompt to any department — result saved as a draft</p>
      </div>
      <div className="card">
        <div className="form-row form-row-3" style={{ marginBottom:14 }}>
          <div className="form-group">
            <label className="form-label">Department</label>
            <select className="form-control" value={deptId} onChange={e => setDeptId(e.target.value)}>
              {depts.map(d => <option key={d.id} value={d.id}>{ICONS[d.id]} {d.id} — {d.name}</option>)}
            </select>
          </div>
          <div className="form-group">
            <label className="form-label">Task Type</label>
            <select className="form-control" value={type} onChange={e => setType(e.target.value)}>
              {DRAFT_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
            </select>
          </div>
          <div className="form-group">
            <label className="form-label">Priority</label>
            <select className="form-control" value={prio} onChange={e => setPrio(e.target.value)}>
              {PRIORITIES.map(p => <option key={p} value={p}>{p}</option>)}
            </select>
          </div>
        </div>

        <div className="form-group">
          <label className="form-label">Your Prompt *</label>
          <textarea className="form-control" rows={8}
            style={{ resize:'vertical', lineHeight:1.7 }}
            placeholder={'Describe what you want the department to produce.\n\nExamples:\n• Analyze my cancer prevention habits and suggest a 12-week action plan\n• Draft a Q2 budget review highlighting risks and opportunities\n• Survey AI-assisted CAD tools and rank top 5 for mechanical design'}
            value={prompt} onChange={e => setPrompt(e.target.value)} />
        </div>

        <div className="form-group">
          <label className="form-label">Draft Title <span style={{ textTransform:'none', fontWeight:400, color:'var(--muted)' }}>(optional)</span></label>
          <input className="form-control" style={{ maxWidth:500 }}
            placeholder="Leave blank to auto-generate from prompt"
            value={title} onChange={e => setTitle(e.target.value)} />
        </div>

        <div style={{ display:'flex', gap:12, alignItems:'center', marginTop:4 }}>
          <button className="btn btn-primary" onClick={submit} disabled={sending}>
            {sending ? <><Spinner/> Running…</> : '🚀 Send to Department'}
          </button>
          {status && (
            <span style={{ fontSize:13, color: status.ok ? 'var(--green)' : 'var(--red)' }}>
              {status.msg}
            </span>
          )}
        </div>
      </div>
    </div>
  )
}
