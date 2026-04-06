import React, { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  getAgents, createAgent, fireAgent, triggerHeartbeat,
  getSpawnRequests, approveSpawn, rejectSpawn,
} from '../../api'
import { useApp } from '../../context/AppContext'
import { COLORS, DEPT_IDS, DEPT_NAMES } from '../../constants'
import Spinner from '../../components/UI/Spinner'
import Modal from '../../components/UI/Modal'
import MarkdownPreview from '../../components/Editor/MarkdownPreview'
import HeartbeatMonitor from '../../components/UI/HeartbeatMonitor'
import AgentChat from '../../components/UI/AgentChat'

const ROLE_COLORS = { ceo:'#f85149', senior:'#d29922', analyst:'#3fb950', junior:'#8b949e' }
const STATUS_COLORS = { active:'var(--green)', fired:'var(--red)', pending:'var(--orange)' }

function AgentAvatar({ agent, size = 48 }) {
  if (agent.profile_image_url) {
    return <img src={agent.profile_image_url} alt={agent.name}
      style={{ width:size, height:size, borderRadius:'50%', objectFit:'cover', border:'2px solid var(--border)' }} />
  }
  const initials = agent.name.split(' ').map(w=>w[0]).join('').toUpperCase().slice(0,2)
  const bg = COLORS[agent.dept_id] || '#607D8B'
  return (
    <div style={{ width:size, height:size, borderRadius:'50%', background:bg,
      display:'flex', alignItems:'center', justifyContent:'center',
      fontSize: size * 0.35, fontWeight:800, color:'#fff', flexShrink:0,
      border: agent.is_ceo ? `3px solid gold` : '2px solid var(--border)' }}>
      {initials}
    </div>
  )
}

function AgentCard({ agent, onHeartbeat, onFire, onClick }) {
  const [running, setRunning] = useState(false)
  const handleHB = async (e) => {
    e.stopPropagation()
    setRunning(true)
    await onHeartbeat(agent.id)
    setRunning(false)
  }
  return (
    <div className="agent-card" style={{ borderLeft:`3px solid ${COLORS[agent.dept_id]||'#607D8B'}`, opacity: agent.status==='fired' ? 0.5 : 1 }}
      onClick={onClick}>
      <div style={{ display:'flex', gap:12, alignItems:'flex-start', marginBottom:10 }}>
        <AgentAvatar agent={agent} />
        <div style={{ flex:1, minWidth:0 }}>
          <div style={{ display:'flex', alignItems:'center', gap:6, flexWrap:'wrap' }}>
            <span style={{ fontSize:14, fontWeight:700 }}>{agent.name}</span>
            {agent.is_ceo && <span className="agent-badge ceo">CEO</span>}
            <span className="agent-badge" style={{ background:`${STATUS_COLORS[agent.status]}22`, color:STATUS_COLORS[agent.status] }}>
              {agent.status}
            </span>
          </div>
          <div style={{ fontSize:12, color:'var(--muted)', marginTop:2 }}>{agent.title || agent.role}</div>
          <div style={{ fontSize:11, color:'var(--muted)', marginTop:1 }}>
            <span className="dept-tag" style={{ background:COLORS[agent.dept_id]||'#607D8B', fontSize:10 }}>{agent.dept_id}</span>
            <span style={{ marginLeft:6 }}>⬇ L{agent.hierarchy_level}</span>
            {agent.subordinate_count > 0 && <span style={{ marginLeft:6 }}>👥 {agent.subordinate_count}</span>}
          </div>
        </div>
      </div>
      {agent.personality && (
        <div style={{ fontSize:11, color:'var(--muted)', marginBottom:8, lineHeight:1.4,
          overflow:'hidden', textOverflow:'ellipsis', display:'-webkit-box',
          WebkitLineClamp:2, WebkitBoxOrient:'vertical' }}>
          {agent.personality.substring(0,120)}
        </div>
      )}
      <div style={{ display:'flex', gap:5, flexWrap:'wrap' }} onClick={e => e.stopPropagation()}>
        {agent.status === 'active' && (
          <button className="btn btn-outline btn-sm" onClick={handleHB} disabled={running}>
            {running ? <Spinner/> : '❤ Heartbeat'}
          </button>
        )}
        <button className="btn btn-primary btn-sm" onClick={onClick}>👤 Profile</button>
        {agent.status === 'active' && !agent.is_ceo && (
          <button className="btn btn-danger btn-sm" onClick={e => { e.stopPropagation(); onFire(agent) }}>🔥 Fire</button>
        )}
      </div>
      {agent.last_heartbeat && (
        <div style={{ fontSize:10, color:'var(--muted)', marginTop:6 }}>
          Last beat: {agent.last_heartbeat.substring(0,16).replace('T',' ')}
        </div>
      )}
    </div>
  )
}

function CreateAgentModal({ defaultDept, parentAgentId, onSave, onClose }) {
  const [name,        setName]       = useState('')
  const [role,        setRole]       = useState('analyst')
  const [title,       setTitle]      = useState('')
  const [dept,        setDept]       = useState(defaultDept || 'HF')
  const [personality, setPersonality]= useState('')
  const [tone,        setTone]       = useState('')
  const [heartbeat,   setHeartbeat]  = useState(5)
  const [model,       setModel]      = useState('')
  const [saving,      setSaving]     = useState(false)
  const [err,         setErr]        = useState('')

  const save = async () => {
    if (!name.trim()) { setErr('Name required'); return }
    setErr(''); setSaving(true)
    try {
      await onSave({
        name: name.trim(), role, title, dept_id: dept,
        personality, tone, heartbeat_interval: heartbeat,
        model_override: model, parent_agent_id: parentAgentId || undefined,
        hierarchy_level: parentAgentId ? 4 : 3,
      })
    } catch(e) { setErr(e.message) }
    setSaving(false)
  }

  return (
    <Modal open onClose={onClose} wide>
      <h3 style={{ marginBottom:18 }}>Create Agent</h3>
      <div className="form-row form-row-2">
        <div className="form-group">
          <label className="form-label">Name *</label>
          <input className="form-control" value={name} onChange={e=>setName(e.target.value)} placeholder="Agent's full name" />
        </div>
        <div className="form-group">
          <label className="form-label">Title</label>
          <input className="form-control" value={title} onChange={e=>setTitle(e.target.value)} placeholder="e.g. Senior Analyst" />
        </div>
      </div>
      <div className="form-row form-row-3">
        <div className="form-group">
          <label className="form-label">Department</label>
          <select className="form-control" value={dept} onChange={e=>setDept(e.target.value)}>
            {DEPT_IDS.map(id=><option key={id} value={id}>{id}</option>)}
          </select>
        </div>
        <div className="form-group">
          <label className="form-label">Role</label>
          <select className="form-control" value={role} onChange={e=>setRole(e.target.value)}>
            <option value="ceo">CEO</option>
            <option value="senior">Senior Agent</option>
            <option value="analyst">Analyst</option>
            <option value="junior">Junior Agent</option>
            <option value="specialist">Specialist</option>
          </select>
        </div>
        <div className="form-group">
          <label className="form-label">Heartbeat (cycles)</label>
          <input type="number" className="form-control" min={1} max={100} value={heartbeat} onChange={e=>setHeartbeat(Number(e.target.value))} />
        </div>
      </div>
      <div className="form-group">
        <label className="form-label">Personality & Traits</label>
        <textarea className="form-control" rows={3} style={{ resize:'vertical' }}
          value={personality} onChange={e=>setPersonality(e.target.value)}
          placeholder="Describe the agent's personality, strengths, biases, approach…" />
      </div>
      <div className="form-group">
        <label className="form-label">Communication Tone</label>
        <input className="form-control" value={tone} onChange={e=>setTone(e.target.value)}
          placeholder="e.g. Formal and precise, data-driven, empathetic and warm…" />
      </div>
      <div className="form-group">
        <label className="form-label">Model Override <span style={{ textTransform:'none', fontWeight:400, color:'var(--muted)' }}>(optional — uses global setting if blank)</span></label>
        <input className="form-control" value={model} onChange={e=>setModel(e.target.value)} placeholder="e.g. llama3.2, claude-sonnet-4-20250514" />
      </div>
      <div style={{ display:'flex', gap:8, alignItems:'center' }}>
        <button className="btn btn-success" onClick={save} disabled={saving}>{saving?<Spinner/>:'💾 Create Agent'}</button>
        <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
        {err && <span style={{ fontSize:12, color:'var(--red)' }}>{err}</span>}
      </div>
    </Modal>
  )
}

export default function AgentsPage() {
  const { toast } = useApp()
  const navigate  = useNavigate()
  const [agents,   setAgents]   = useState([])
  const [spawns,   setSpawns]   = useState([])
  const [loading,  setLoading]  = useState(true)
  const [tab,      setTab]      = useState('all')
  const [deptFilter,setDeptFilter]=useState('all')
  const [modal,    setModal]    = useState(false)
  const [firing,   setFiring]   = useState(null)
  const [fireReason,setFireReason]=useState('')
  const [chatAgent, setChatAgent]= useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    const [ag, sp] = await Promise.all([
      getAgents().catch(()=>[]),
      getSpawnRequests({ status:'pending' }).catch(()=>[]),
    ])
    setAgents(ag); setSpawns(sp)
    setLoading(false)
  }, [])

  useEffect(() => { load() }, [load])

  const handleHB = async (id) => {
    toast('Running heartbeat…')
    const r = await triggerHeartbeat(id).catch(e=>({ ok:false, error:e.message }))
    toast(r.ok ? `✓ ${r.summary||'Done'}` : `✗ ${r.error}`, r.ok?'success':'error')
    load()
  }

  const handleFire = async () => {
    if (!firing) return
    await fireAgent(firing.id, { fired_by:'founder', reason:fireReason })
    toast(`${firing.name} has been fired`)
    setFiring(null); setFireReason('')
    load()
  }

  const handleCreate = async (body) => {
    await createAgent(body)
    toast('Agent created ✓')
    setModal(false); load()
  }

  const handleApproveSpawn = async (sid) => {
    await approveSpawn(sid, { approved_by:'founder' })
    toast('Spawn approved ✓'); load()
  }

  const handleRejectSpawn = async (sid) => {
    await rejectSpawn(sid, { reason:'Rejected by Founder' })
    toast('Spawn rejected'); load()
  }

  const depts = ['all', ...DEPT_IDS]
  const filtered = agents.filter(a => {
    if (tab === 'ceo')    return a.is_ceo
    if (tab === 'active') return a.status === 'active'
    if (tab === 'fired')  return a.status === 'fired'
    return true
  }).filter(a => deptFilter === 'all' || a.dept_id === deptFilter)

  return (
    <div>
      <div className="page-header" style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start' }}>
        <div>
          <h2>🤖 Agents</h2>
          <p>All autonomous agents across the Think Tank · {agents.filter(a=>a.status==='active').length} active</p>
        </div>
        <button className="btn btn-success" onClick={()=>setModal(true)}>＋ New Agent</button>
      </div>

      {/* Spawn requests banner */}
      {spawns.length > 0 && (
        <div style={{ background:'rgba(210,153,34,.1)', border:'1px solid rgba(210,153,34,.3)', borderRadius:8, padding:'12px 16px', marginBottom:16 }}>
          <div style={{ fontSize:13, fontWeight:700, color:'var(--orange)', marginBottom:8 }}>
            🧬 {spawns.length} Pending Spawn Request{spawns.length>1?'s':''}
          </div>
          {spawns.map(s => (
            <div key={s.id} style={{ display:'flex', alignItems:'center', gap:10, padding:'6px 0', borderBottom:'1px solid rgba(210,153,34,.15)' }}>
              <span className="dept-tag" style={{ background: COLORS[s.dept_id]||'#607D8B' }}>{s.dept_id}</span>
              <div style={{ flex:1 }}>
                <strong>{s.proposed_name}</strong> as {s.proposed_role}
                <span style={{ fontSize:11, color:'var(--muted)', marginLeft:6 }}>requested by {s.requester_name}</span>
              </div>
              <button className="btn btn-success btn-sm" onClick={()=>handleApproveSpawn(s.id)}>✓ Approve</button>
              <button className="btn btn-danger  btn-sm" onClick={()=>handleRejectSpawn(s.id)}>✗ Reject</button>
            </div>
          ))}
        </div>
      )}

      {/* Filters */}
      <div style={{ display:'flex', gap:12, marginBottom:20, alignItems:'center', flexWrap:'wrap' }}>
        <div className="tabs" style={{ marginBottom:0, borderBottom:'none', gap:2 }}>
          {['all','ceo','active','fired'].map(t=>(
            <button key={t} className={`tab${tab===t?' active':''}`} onClick={()=>setTab(t)} style={{ padding:'6px 14px' }}>
              {t==='ceo'?'👑 CEOs':t.charAt(0).toUpperCase()+t.slice(1)}
            </button>
          ))}
        </div>
        <select className="form-control" style={{ maxWidth:160 }} value={deptFilter} onChange={e=>setDeptFilter(e.target.value)}>
          <option value="all">All Depts</option>
          {DEPT_IDS.map(id=><option key={id} value={id}>{id}</option>)}
        </select>
      </div>

      {loading ? <div className="empty"><Spinner lg/></div> : (
        filtered.length === 0 ? (
          <div className="empty">No agents found.</div>
        ) : (
          <div className="grid grid-2" style={{ gridTemplateColumns:'repeat(auto-fill,minmax(320px,1fr))' }}>
            {filtered.map(a => (
              <AgentCard key={a.id} agent={a}
                onHeartbeat={handleHB}
                onFire={a => setFiring(a)}
                onClick={()=>navigate(`/agents/${a.id}`)}
              />
            ))}
          </div>
        )
      )}

      {modal && <CreateAgentModal onSave={handleCreate} onClose={()=>setModal(false)} />}
      {chatAgent && <AgentChat agent={chatAgent} onClose={()=>setChatAgent(null)} />}

      {/* Fire confirmation */}
      <Modal open={!!firing} onClose={()=>setFiring(null)}>
        {firing && <>
          <h3 style={{ marginBottom:12, color:'var(--red)' }}>🔥 Fire {firing.name}?</h3>
          <p style={{ fontSize:13, color:'var(--muted)', marginBottom:14 }}>
            This is permanent. The agent will be deactivated immediately.
          </p>
          <div className="form-group">
            <label className="form-label">Reason</label>
            <textarea className="form-control" rows={3} value={fireReason} onChange={e=>setFireReason(e.target.value)} placeholder="Why is this agent being fired?" />
          </div>
          <div style={{ display:'flex', gap:8 }}>
            <button className="btn btn-danger" onClick={handleFire}>🔥 Confirm Fire</button>
            <button className="btn btn-ghost" onClick={()=>setFiring(null)}>Cancel</button>
          </div>
        </>}
      </Modal>
    </div>
  )
}
