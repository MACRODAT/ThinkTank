import React, { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getDepartment, getProjects, getPendingDrafts, getDeptMail,
         getDeptPrompt, saveDeptPrompt, runDepartment, reviewDraft } from '../../api'
import { useApp } from '../../context/AppContext'
import { ICONS, PRIO_COLORS } from '../../constants'
import Spinner from '../../components/UI/Spinner'
import DeptTag from '../../components/UI/DeptTag'
import PriorityDot from '../../components/UI/PriorityDot'
import Modal from '../../components/UI/Modal'
import ProjectModal from '../Projects/ProjectModal'
import FullScreenEditor from '../../components/Editor/FullScreenEditor'
import DraftViewer from '../../components/Editor/DraftViewer'

export default function Department() {
  const { id } = useParams()
  const { toast } = useApp()
  const navigate  = useNavigate()

  const [dept,       setDept]      = useState(null)
  const [projects,   setProjects]  = useState([])
  const [drafts,     setDrafts]    = useState([])
  const [mail,       setMail]      = useState([])
  const [loading,    setLoading]   = useState(true)
  const [running,    setRunning]   = useState(false)
  const [promptOpen, setPromptOpen]= useState(false)
  const [promptTxt,  setPromptTxt] = useState('')
  const [schedule,   setSchedule]  = useState('')
  const [savingP,    setSavingP]   = useState(false)
  const [projModal,  setProjModal] = useState(false)
  const [editProj,   setEditProj]  = useState(null)
  const [editorDraft,setEditorDraft] = useState(null)
  const [viewerDraft,setViewerDraft] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    const [d, p, dr, m] = await Promise.all([
      getDepartment(id),
      getProjects({ dept_id: id }),
      getPendingDrafts(id),
      getDeptMail(id),
    ])
    setDept(d); setDrafts(dr); setMail(m)
    const seen = new Set()
    setProjects(p.filter(x => { if(seen.has(x.id)) return false; seen.add(x.id); return true }))
    setLoading(false)
  }, [id])

  useEffect(() => { load() }, [load])

  const run = async () => {
    setRunning(true)
    try { await runDepartment(id); toast(`${id} cycle started`) }
    catch(e) { toast(e.message, 'error') }
    setRunning(false)
  }

  const openPrompt = async () => {
    const d = await getDeptPrompt(id)
    setPromptTxt(d.system_prompt || '')
    setSchedule(d.schedule || '')
    setPromptOpen(true)
  }

  const savePrompt = async () => {
    setSavingP(true)
    try { await saveDeptPrompt(id, { system_prompt: promptTxt, schedule: schedule || null }); toast('Prompt saved ✓') }
    catch(e) { toast(e.message, 'error') }
    setSavingP(false)
  }

  if (loading) return <div className="empty"><Spinner lg /></div>

  const activeProj  = projects.filter(p => p.status === 'active')
  const unreadCount = mail.filter(m => m.status==='unread' && m.to_dept===id).length

  return (
    <div>
      <div className="page-header" style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start' }}>
        <div style={{ display:'flex', alignItems:'center', gap:14 }}>
          <span style={{ fontSize:36 }}>{ICONS[id]||'🏛️'}</span>
          <div><h2>{dept?.name}</h2><p>{dept?.description || ''}</p></div>
        </div>
        <div style={{ display:'flex', gap:8 }}>
          <button className="btn btn-outline btn-sm" onClick={openPrompt}>✏ Edit Prompt</button>
          <button className="btn btn-primary" onClick={run} disabled={running}>
            {running ? <><Spinner/> Running…</> : '▶ Run Cycle'}
          </button>
        </div>
      </div>

      <div className="grid grid-3" style={{ marginBottom:24 }}>
        <div className="card stat"><div className="stat-value" style={{ color:'var(--orange)' }}>{drafts.length}</div><div className="stat-label">Pending Drafts</div></div>
        <div className="card stat"><div className="stat-value" style={{ color:'var(--accent)' }}>{unreadCount}</div><div className="stat-label">Unread Mail</div></div>
        <div className="card stat"><div className="stat-value" style={{ color:'var(--green)' }}>{activeProj.length}</div><div className="stat-label">Active Projects</div></div>
      </div>

      <div className="grid grid-2">
        <div className="card">
          <div className="card-header">
            <span className="card-title">Projects ({projects.length})</span>
            <button className="btn btn-success btn-sm" onClick={() => { setEditProj(null); setProjModal(true) }}>＋ Add</button>
          </div>
          {projects.length === 0 ? <div className="empty">No projects</div> : projects.map(p => (
            <div key={p.id} style={{ display:'flex', gap:8, alignItems:'flex-start', padding:'10px 0', borderBottom:'1px solid var(--border)' }}>
              <PriorityDot priority={p.priority} />
              <div style={{ flex:1, minWidth:0 }}>
                <div style={{ fontSize:13, fontWeight:600 }}>{p.name}</div>
                <div style={{ fontSize:11, color:'var(--muted)', marginTop:2 }}>{p.description}</div>
                <div style={{ display:'flex', gap:8, marginTop:4 }}>
                  <span style={{ fontSize:10, fontWeight:700, textTransform:'uppercase',
                    color: {active:'var(--green)',paused:'var(--orange)',completed:'var(--muted)',cancelled:'var(--red)'}[p.status]||'var(--muted)' }}>
                    {p.status}
                  </span>
                  <span style={{ fontSize:10, fontWeight:600, color:PRIO_COLORS[p.priority], textTransform:'uppercase' }}>{p.priority}</span>
                </div>
              </div>
              <div style={{ display:'flex', gap:4 }}>
                <button className="btn btn-outline btn-sm" onClick={() => { setEditProj(p); setProjModal(true) }}>✏</button>
              </div>
            </div>
          ))}
        </div>

        <div className="card" style={{ padding:0 }}>
          <div style={{ padding:'14px 18px', borderBottom:'1px solid var(--border)' }}>
            <span className="card-title">Pending Drafts</span>
          </div>
          {drafts.length === 0 ? <div className="empty">No pending drafts</div> : drafts.map(d => (
            <div key={d.id} className="draft-item">
              <PriorityDot priority={d.priority} />
              <div className="draft-info">
                <div className="draft-title">{d.title}</div>
                <div className="draft-meta">{d.draft_type?.toUpperCase()} · {d.created_at?.substring(0,10)}</div>
              </div>
              <div className="draft-actions">
                <button className="btn btn-outline btn-sm" onClick={() => setEditorDraft(d)}>✏ Edit</button>
                <button className="btn btn-ghost   btn-sm" onClick={() => setViewerDraft(d)}>👁 View</button>
                <button className="btn btn-success  btn-sm" onClick={async () => { await reviewDraft(d.id,'approved'); toast('Approved'); load() }}>✓</button>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="card" style={{ marginTop:16, padding:0 }}>
        <div style={{ padding:'14px 18px', borderBottom:'1px solid var(--border)' }}><span className="card-title">Recent Mail</span></div>
        {mail.length === 0 ? <div className="empty">No mail</div> : mail.slice(0,8).map(m => (
          <div key={m.id} className="mail-item" onClick={() => navigate(`/mail/${m.thread_id}`)}>
            <span className="arrow-badge" style={{ background:'#607D8B' }}>{m.from_dept}</span>
            <span style={{ color:'var(--muted)', fontSize:11, margin:'0 4px' }}>→</span>
            <span className="arrow-badge" style={{ background:'#607D8B' }}>{m.to_dept}</span>
            <div style={{ flex:1, padding:'0 10px', minWidth:0 }}>
              <div style={{ fontSize:13 }}>{m.subject}</div>
            </div>
            <div className="mail-time">{m.created_at?.substring(0,10)}</div>
          </div>
        ))}
      </div>

      <Modal open={promptOpen} onClose={() => setPromptOpen(false)} fullish>
        <div className="modal-header">
          <DeptTag id={id} />
          <div style={{ flex:1 }}>
            <div style={{ fontWeight:700, fontSize:15 }}>{dept?.name} — System Prompt</div>
            <div style={{ fontSize:11, color:'var(--muted)' }}>Identity, ethics, tone, scheduling, output format</div>
          </div>
          <div style={{ display:'flex', gap:8, alignItems:'center' }}>
            <div>
              <label style={{ fontSize:10, color:'var(--muted)', display:'block', textTransform:'uppercase', letterSpacing:'.05em' }}>Schedule (cron)</label>
              <input className="form-control" value={schedule} onChange={e => setSchedule(e.target.value)}
                style={{ width:160, padding:'4px 8px', fontSize:12 }} placeholder="0 8 * * *" />
            </div>
            <button className="btn btn-success" onClick={savePrompt} disabled={savingP}>
              {savingP ? <><Spinner/> Saving…</> : '💾 Save'}
            </button>
            <button className="btn btn-ghost" onClick={() => setPromptOpen(false)}>✕</button>
          </div>
        </div>
        <div style={{ padding:'8px 24px', background:'var(--bg)', borderBottom:'1px solid var(--border)', fontSize:11, color:'var(--muted)' }}>
          Markdown supported. Sections: MANDATE · CORE RESPONSIBILITIES · COMMUNICATION STYLE · OUTPUT FORMATS
        </div>
        <div style={{ flex:1, overflow:'hidden' }}>
          <textarea className="prompt-editor" style={{ border:'none', borderRadius:0, minHeight:500 }}
            value={promptTxt} onChange={e => setPromptTxt(e.target.value)} />
        </div>
      </Modal>

      {projModal && (
        <ProjectModal
          initial={editProj}
          defaultDept={id}
          onClose={() => { setProjModal(false); setEditProj(null) }}
          onSaved={() => { setProjModal(false); setEditProj(null); load() }}
        />
      )}

      {editorDraft && (
        <FullScreenEditor
          draft={editorDraft}
          onClose={() => setEditorDraft(null)}
          onSaved={() => { setEditorDraft(null); load() }}
        />
      )}

      {viewerDraft && (
        <DraftViewer
          draft={viewerDraft}
          onClose={() => setViewerDraft(null)}
          onReviewed={() => { setViewerDraft(null); load() }}
        />
      )}
    </div>
  )
}
