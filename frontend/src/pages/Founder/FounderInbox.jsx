import React, { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  getFounderInbox, markFounderRead, replyFounderMail,
  getSpawnRequests, approveSpawn, rejectSpawn,
  getDraftEndeavors, approveDraftEndeavor, rejectDraftEndeavor, editDraftEndeavor,
  getFounderStats,
} from '../../api'
import { useApp } from '../../context/AppContext'
import { COLORS } from '../../constants'
import Spinner from '../../components/UI/Spinner'
import Modal from '../../components/UI/Modal'
import MarkdownPreview from '../../components/Editor/MarkdownPreview'

const PRIORITY_COLOR = { critical:'var(--red)', high:'var(--orange)', normal:'var(--muted)' }

export default function FounderInbox() {
  const { toast } = useApp()
  const navigate  = useNavigate()

  const [stats,      setStats]      = useState({})
  const [mail,       setMail]       = useState([])
  const [spawns,     setSpawns]     = useState([])
  const [draftEndv,  setDraftEndv]  = useState([])
  const [loading,    setLoading]    = useState(true)
  const [tab,        setTab]        = useState('mail')

  // Reply state
  const [replyTarget,setReplyTarget]= useState(null)
  const [replyBody,  setReplyBody]  = useState('')
  const [sending,    setSending]    = useState(false)

  // Viewing a mail
  const [viewing,    setViewing]    = useState(null)

  // Editing a draft endeavor
  const [editDE,     setEditDE]     = useState(null)
  const [editName,   setEditName]   = useState('')
  const [editDesc,   setEditDesc]   = useState('')
  const [editPhases, setEditPhases] = useState('')
  const [editNotes,  setEditNotes]  = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    const [s, m, sp, de] = await Promise.all([
      getFounderStats().catch(()=>({})),
      getFounderInbox().catch(()=>[]),
      getSpawnRequests({ status:'pending' }).catch(()=>[]),
      getDraftEndeavors({ status:'pending' }).catch(()=>[]),
    ])
    setStats(s); setMail(m); setSpawns(sp); setDraftEndv(de)
    setLoading(false)
  }, [])

  useEffect(() => { load() }, [load])

  const openMail = async (m) => {
    if (m.status === 'unread') await markFounderRead(m.id)
    setViewing(m); load()
  }

  const sendReply = async () => {
    if (!replyBody.trim()) return
    setSending(true)
    await replyFounderMail(replyTarget.id, { reply_body: replyBody })
    toast('Reply sent ✓')
    setSending(false); setReplyTarget(null); setReplyBody('')
    setViewing(null); load()
  }

  const approveDE = async (id) => {
    await approveDraftEndeavor(id, { reviewed_by:'founder', review_notes: editNotes })
    toast('Endeavor approved & activated ✓'); setEditDE(null); load()
  }

  const rejectDE = async (id) => {
    await rejectDraftEndeavor(id, { reviewed_by:'founder', review_notes: editNotes })
    toast('Endeavor rejected'); setEditDE(null); load()
  }

  const saveEditDE = async () => {
    if (!editDE) return
    await editDraftEndeavor(editDE.id, {
      name: editName, description: editDesc,
      phases_json: editPhases || editDE.phases_json,
    })
    toast('Draft updated ✓'); setEditDE(null); load()
  }

  const openEditDE = (de) => {
    setEditDE(de); setEditName(de.name); setEditDesc(de.description)
    setEditPhases(de.phases_json||'[]'); setEditNotes('')
  }

  const unreadCount = mail.filter(m => m.status === 'unread').length

  return (
    <div>
      {/* Header */}
      <div className="page-header" style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start' }}>
        <div>
          <h2>👑 Founder Inbox</h2>
          <p>Direct escalations from department CEOs and pending approvals</p>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-3" style={{ marginBottom:24 }}>
        <div className="card stat">
          <div className="stat-value" style={{ color:'var(--red)' }}>{stats.unread_mail||0}</div>
          <div className="stat-label">Unread Mail</div>
        </div>
        <div className="card stat">
          <div className="stat-value" style={{ color:'var(--orange)' }}>{stats.spawn_requests||0}</div>
          <div className="stat-label">Spawn Requests</div>
        </div>
        <div className="card stat">
          <div className="stat-value" style={{ color:'var(--accent)' }}>{stats.draft_endeavors||0}</div>
          <div className="stat-label">Draft Endeavors</div>
        </div>
      </div>

      {/* Tabs */}
      <div className="tabs">
        <button className={`tab${tab==='mail'?' active':''}`} onClick={()=>setTab('mail')}>
          📨 Mail {unreadCount>0&&<span className="badge" style={{ marginLeft:4 }}>{unreadCount}</span>}
        </button>
        <button className={`tab${tab==='spawns'?' active':''}`} onClick={()=>setTab('spawns')}>
          🧬 Spawn Requests {spawns.length>0&&<span className="badge" style={{ marginLeft:4 }}>{spawns.length}</span>}
        </button>
        <button className={`tab${tab==='endeavors'?' active':''}`} onClick={()=>setTab('endeavors')}>
          🚀 Draft Endeavors {draftEndv.length>0&&<span className="badge" style={{ marginLeft:4 }}>{draftEndv.length}</span>}
        </button>
      </div>

      {loading ? <div className="empty"><Spinner/></div> : (

        /* ── MAIL ── */
        tab === 'mail' ? (
          <div className="card" style={{ padding:0 }}>
            {mail.length === 0 ? <div className="empty">No mail from CEOs yet.</div> : mail.map(m => (
              <div key={m.id}
                className={`founder-mail-item${m.status==='unread'?' unread':''}`}
                onClick={()=>openMail(m)}>
                <div style={{ display:'flex', gap:10, alignItems:'flex-start', flex:1, minWidth:0 }}>
                  {/* Agent avatar */}
                  <div style={{ width:36, height:36, borderRadius:'50%', background:COLORS[m.from_dept_id]||'#607D8B',
                    display:'flex', alignItems:'center', justifyContent:'center',
                    fontSize:14, fontWeight:800, color:'#fff', flexShrink:0 }}>
                    {(m.agent_name||'?')[0]}
                  </div>
                  <div style={{ flex:1, minWidth:0 }}>
                    <div style={{ display:'flex', gap:8, alignItems:'center' }}>
                      <span style={{ fontSize:13, fontWeight: m.status==='unread'?700:500 }}>{m.subject}</span>
                      {m.requires_decision===1 && (
                        <span style={{ fontSize:10, background:'rgba(248,81,73,.15)', color:'var(--red)',
                          padding:'2px 6px', borderRadius:4, fontWeight:700, flexShrink:0 }}>DECISION NEEDED</span>
                      )}
                    </div>
                    <div style={{ fontSize:11, color:'var(--muted)', marginTop:2 }}>
                      {m.agent_name} · {m.agent_title} ·
                      <span className="dept-tag" style={{ background:COLORS[m.from_dept_id]||'#607D8B', fontSize:9, marginLeft:4 }}>{m.from_dept_id}</span>
                    </div>
                    <div style={{ fontSize:12, color:'var(--muted)', marginTop:3, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>
                      {m.body.substring(0,120)}
                    </div>
                  </div>
                </div>
                <div style={{ display:'flex', flexDirection:'column', alignItems:'flex-end', gap:4, flexShrink:0 }}>
                  <span style={{ fontSize:10, fontWeight:700, color:PRIORITY_COLOR[m.priority]||'var(--muted)', textTransform:'uppercase' }}>{m.priority}</span>
                  <span style={{ fontSize:10, color:'var(--muted)' }}>{m.created_at?.substring(0,16).replace('T',' ')}</span>
                  {m.status==='replied' && <span style={{ fontSize:9, color:'var(--green)' }}>✓ Replied</span>}
                </div>
              </div>
            ))}
          </div>
        )

        /* ── SPAWN REQUESTS ── */
        : tab === 'spawns' ? (
          <div className="card" style={{ padding:0 }}>
            {spawns.length === 0 ? <div className="empty">No pending spawn requests.</div> : spawns.map(s=>(
              <div key={s.id} style={{ display:'flex', gap:12, alignItems:'center', padding:'14px 16px', borderBottom:'1px solid var(--border)' }}>
                <span className="dept-tag" style={{ background:COLORS[s.dept_id]||'#607D8B' }}>{s.dept_id}</span>
                <div style={{ flex:1 }}>
                  <div style={{ fontSize:14, fontWeight:700 }}>{s.proposed_name}</div>
                  <div style={{ fontSize:12, color:'var(--muted)' }}>{s.proposed_role} · requested by {s.requester_name}</div>
                  {s.proposed_personality && <div style={{ fontSize:11, color:'var(--muted)', marginTop:3 }}>{s.proposed_personality.substring(0,100)}</div>}
                </div>
                <div style={{ display:'flex', gap:6 }}>
                  <button className="btn btn-success btn-sm" onClick={()=>approveSpawn(s.id,{approved_by:'founder'}).then(()=>{toast('Approved ✓');load()})}>✓ Approve</button>
                  <button className="btn btn-danger  btn-sm" onClick={()=>rejectSpawn(s.id,{reason:'Rejected by Founder'}).then(()=>{toast('Rejected');load()})}>✗ Reject</button>
                </div>
              </div>
            ))}
          </div>
        )

        /* ── DRAFT ENDEAVORS ── */
        : (
          <div className="card" style={{ padding:0 }}>
            {draftEndv.length === 0 ? <div className="empty">No draft endeavors awaiting review.</div> : draftEndv.map(de=>(
              <div key={de.id} style={{ padding:'16px', borderBottom:'1px solid var(--border)' }}>
                <div style={{ display:'flex', gap:10, alignItems:'flex-start', marginBottom:8 }}>
                  <span className="dept-tag" style={{ background:COLORS[de.dept_id]||'#607D8B' }}>{de.dept_id}</span>
                  <div style={{ flex:1 }}>
                    <div style={{ fontSize:15, fontWeight:700 }}>{de.name}</div>
                    <div style={{ fontSize:12, color:'var(--muted)' }}>by {de.agent_name}{de.is_ceo?' (CEO)':''} · {de.created_at?.substring(0,10)}</div>
                    <div style={{ fontSize:13, color:'var(--muted)', marginTop:4, lineHeight:1.5 }}>{de.description}</div>
                  </div>
                </div>
                {(de.phases||[]).length > 0 && (
                  <div style={{ marginBottom:8, fontSize:12, color:'var(--muted)' }}>
                    {de.phases.length} phase{de.phases.length>1?'s':''}: {de.phases.map(p=>p.name||'Phase').join(' → ')}
                  </div>
                )}
                <div style={{ display:'flex', gap:6 }}>
                  <button className="btn btn-success btn-sm" onClick={()=>approveDE(de.id)}>✓ Approve & Launch</button>
                  <button className="btn btn-outline btn-sm" onClick={()=>openEditDE(de)}>✏ Edit</button>
                  <button className="btn btn-danger  btn-sm" onClick={()=>rejectDE(de.id)}>✗ Reject</button>
                </div>
              </div>
            ))}
          </div>
        )
      )}

      {/* View mail modal */}
      <Modal open={!!viewing} onClose={()=>setViewing(null)} wide>
        {viewing && (
          <>
            <div style={{ display:'flex', gap:10, alignItems:'center', marginBottom:14 }}>
              <div style={{ width:40, height:40, borderRadius:'50%', background:COLORS[viewing.from_dept_id]||'#607D8B',
                display:'flex', alignItems:'center', justifyContent:'center', fontSize:16, fontWeight:800, color:'#fff' }}>
                {(viewing.agent_name||'?')[0]}
              </div>
              <div>
                <div style={{ fontWeight:700 }}>{viewing.agent_name}</div>
                <div style={{ fontSize:12, color:'var(--muted)' }}>{viewing.agent_title} · {viewing.from_dept_id}</div>
              </div>
              <span style={{ marginLeft:'auto', fontSize:11, fontWeight:700, textTransform:'uppercase', color:PRIORITY_COLOR[viewing.priority] }}>{viewing.priority}</span>
            </div>
            <h3 style={{ marginBottom:12 }}>{viewing.subject}</h3>
            <div style={{ background:'var(--bg)', border:'1px solid var(--border)', borderRadius:8, padding:16, marginBottom:14 }}>
              <MarkdownPreview content={viewing.body} />
            </div>
            {viewing.replied_at && (
              <div style={{ background:'rgba(88,166,255,.05)', border:'1px solid rgba(88,166,255,.2)', borderRadius:8, padding:14, marginBottom:14 }}>
                <div style={{ fontSize:11, color:'var(--accent)', fontWeight:700, marginBottom:6 }}>YOUR REPLY · {viewing.replied_at?.substring(0,16).replace('T',' ')}</div>
                <div style={{ fontSize:13, lineHeight:1.6 }}>{viewing.reply_body}</div>
              </div>
            )}
            {viewing.status !== 'replied' && (
              replyTarget?.id === viewing.id ? (
                <div>
                  <textarea className="form-control" rows={5} style={{ resize:'vertical', marginBottom:8 }}
                    placeholder="Your reply to the CEO…"
                    value={replyBody} onChange={e=>setReplyBody(e.target.value)} />
                  <div style={{ display:'flex', gap:8 }}>
                    <button className="btn btn-primary" onClick={sendReply} disabled={sending}>{sending?<Spinner/>:'📨 Send Reply'}</button>
                    <button className="btn btn-ghost" onClick={()=>setReplyTarget(null)}>Cancel</button>
                  </div>
                </div>
              ) : (
                <button className="btn btn-primary" onClick={()=>setReplyTarget(viewing)}>📨 Reply to CEO</button>
              )
            )}
          </>
        )}
      </Modal>

      {/* Edit draft endeavor modal */}
      <Modal open={!!editDE} onClose={()=>setEditDE(null)} wide>
        {editDE && (
          <>
            <h3 style={{ marginBottom:14 }}>✏ Edit Draft Endeavor</h3>
            <div className="form-group">
              <label className="form-label">Name</label>
              <input className="form-control" value={editName} onChange={e=>setEditName(e.target.value)} />
            </div>
            <div className="form-group">
              <label className="form-label">Description</label>
              <textarea className="form-control" rows={3} value={editDesc} onChange={e=>setEditDesc(e.target.value)} />
            </div>
            <div className="form-group">
              <label className="form-label">Phases (JSON)</label>
              <textarea className="form-control" rows={5} style={{ fontFamily:'monospace', fontSize:12 }}
                value={editPhases} onChange={e=>setEditPhases(e.target.value)} />
            </div>
            <div className="form-group">
              <label className="form-label">Review Notes</label>
              <textarea className="form-control" rows={2} value={editNotes} onChange={e=>setEditNotes(e.target.value)} placeholder="Optional notes…" />
            </div>
            <div style={{ display:'flex', gap:8 }}>
              <button className="btn btn-success" onClick={saveEditDE}>💾 Save Changes</button>
              <button className="btn btn-primary" onClick={()=>approveDE(editDE.id)}>✓ Approve & Launch</button>
              <button className="btn btn-danger"  onClick={()=>rejectDE(editDE.id)}>✗ Reject</button>
              <button className="btn btn-ghost"   onClick={()=>setEditDE(null)}>Cancel</button>
            </div>
          </>
        )}
      </Modal>
    </div>
  )
}
