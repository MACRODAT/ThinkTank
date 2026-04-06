import React, { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  getAgent, updateAgent, fireAgent, triggerHeartbeat,
  getAgentFiles, upsertAgentFile, deleteAgentFile,
  requestSpawn,
} from '../../api'
import { useApp } from '../../context/AppContext'
import { COLORS } from '../../constants'
import Spinner from '../../components/UI/Spinner'
import Modal from '../../components/UI/Modal'
import MarkdownPreview from '../../components/Editor/MarkdownPreview'
import AgentChat from './AgentChat'

const FILE_CATEGORIES = ['skills','personality','traits','tone','guidelines','prompts','knowledge']

/* ── Preset model templates (importable) ──────────────────── */
const PRESET_PERSONALITIES = [
  { label: 'Analytical Strategist', value: 'Highly analytical and data-driven. Approaches every problem by breaking it into components. Never makes recommendations without evidence. Comfortable with uncertainty but always quantifies it. Strong at pattern recognition and second-order effects.' },
  { label: 'Empathetic Leader', value: 'Leads with empathy and deep people awareness. Notices emotional undercurrents before they become problems. Protective of team wellbeing. Builds trust through consistency and vulnerability. Occasionally TOO cautious about conflict.' },
  { label: 'Bold Innovator', value: 'Fearless about proposing radical ideas. High risk tolerance. Moves fast and iterates. Occasionally needs others to slow them down. Infectious enthusiasm. Hates bureaucracy and slow processes.' },
  { label: 'Methodical Engineer', value: 'Precise, rigorous, and thorough. Documents everything. Asks \"what breaks first?\" before moving forward. Allergic to vague requirements. Trusted for quality but sometimes too slow for fast-moving environments.' },
  { label: 'Diplomatic Negotiator', value: 'Masterful at finding common ground. Never appears to take sides but always advances their position. Patient. Willing to take a long view. Excellent at defusing tension.' },
  { label: 'Visionary Executive', value: 'Sees 10 years ahead and connects trends others miss. Inspiring but sometimes impatient with execution details. Delegates heavily. Needs strong operators around them to turn vision into reality.' },
]

const PRESET_TONES = [
  { label: 'Military Brief', value: 'Concise, commanding, no filler. Uses structured formats: SITUATION / ASSESSMENT / RECOMMENDATION. States facts before opinions. Uses military time and compass bearing-style precision.' },
  { label: 'Academic Rigorous', value: 'Careful with claims. Cites reasoning. Distinguishes hypothesis from evidence. Uses precise language. Never overstates confidence. Comfortable with nuance and ambiguity.' },
  { label: 'Executive Summary', value: 'Leads with conclusion. Buries supporting detail at the end. Uses bullet points and headers. Respects that the audience is time-constrained. Never buries the lede.' },
  { label: 'Collaborative Coach', value: 'Asks questions before giving answers. Uses inclusive language (\"we\", \"our\"). Celebrates small wins. Frames critique as opportunity. Checks understanding before moving on.' },
  { label: 'Direct & Blunt', value: 'No pleasantries. States the uncomfortable truth. Short sentences. Low tolerance for waffle. Respects others enough to give them the unvarnished reality.' },
]

const PRESET_SKILLS = [
  { label: 'Strategic Planning', value: '# Strategic Planning Skills\n\n## Core Competencies\n- Long-horizon thinking (3-10 year scenarios)\n- Competitive positioning and market analysis\n- Resource allocation under constraint\n- Stakeholder mapping and influence\n\n## Frameworks\n- SWOT, Porter\'s 5 Forces, OKRs\n- Scenario planning (best/worst/likely)\n- Strategic narrative building\n\n## Deliverables\n- Strategy memos, roadmaps, competitive briefs\n- Quarterly strategic reviews\n- Board-level presentations' },
  { label: 'Financial Analysis', value: '# Financial Analysis Skills\n\n## Core Competencies\n- Budget modeling and forecasting\n- Risk quantification (VaR, scenario analysis)\n- Resource efficiency metrics\n- Cost-benefit analysis\n\n## Tools\n- Spreadsheet modeling\n- Financial statements (P&L, balance sheet, cash flow)\n- ROI and NPV calculations\n\n## Deliverables\n- Budget reports, financial briefs, risk assessments' },
  { label: 'Research & Intelligence', value: '# Research & Intelligence Skills\n\n## Core Competencies\n- Primary and secondary research\n- Source evaluation and credibility assessment\n- Synthesis and knowledge distillation\n- Intelligence briefing production\n\n## Methods\n- Literature review\n- Expert interviews\n- Data triangulation\n\n## Deliverables\n- Research briefs, intelligence reports, knowledge bases' },
  { label: 'Technical Engineering', value: '# Technical Engineering Skills\n\n## Core Competencies\n- Systems architecture and design\n- Technical risk assessment\n- Code review and quality standards\n- Dependency mapping\n\n## Languages & Tools\n- Python, JavaScript, SQL\n- System design patterns\n- CI/CD and DevOps fundamentals\n\n## Deliverables\n- Technical specs, architecture diagrams, code reviews' },
]

function AgentAvatar({ agent, size = 80 }) {
  if (agent.profile_image_url) {
    return <img src={agent.profile_image_url} alt={agent.name}
      style={{ width:size, height:size, borderRadius:'50%', objectFit:'cover', border:'3px solid var(--border)' }} />
  }
  const initials = agent.name.split(' ').map(w=>w[0]).join('').toUpperCase().slice(0,2)
  return (
    <div style={{ width:size, height:size, borderRadius:'50%', background:COLORS[agent.dept_id]||'#607D8B',
      display:'flex', alignItems:'center', justifyContent:'center',
      fontSize:size*0.35, fontWeight:800, color:'#fff', flexShrink:0,
      border: agent.is_ceo ? '4px solid gold' : '3px solid var(--border)' }}>
      {initials}
    </div>
  )
}

function MdFileEditor({ agentId, files, onChanged }) {
  const { toast } = useApp()
  const [editing,    setEditing]    = useState(null)
  const [adding,     setAdding]     = useState(false)
  const [newCat,     setNewCat]     = useState(FILE_CATEGORIES[0])
  const [newName,    setNewName]    = useState('')
  const [newContent, setNewContent] = useState('')
  const [saving,     setSaving]     = useState(false)
  const [importOpen, setImportOpen] = useState(null) // 'personality'|'tone'|'skills'

  const save = async (category, filename, content) => {
    setSaving(true)
    await upsertAgentFile(agentId, { category, filename, content })
    toast('Saved ✓'); setSaving(false); setEditing(null); setAdding(false)
    onChanged()
  }

  const del = async (fid) => {
    if (!confirm('Delete this file?')) return
    await deleteAgentFile(agentId, fid)
    toast('Deleted'); onChanged()
  }

  const importPreset = async (preset) => {
    const cat = importOpen || 'knowledge'
    await upsertAgentFile(agentId, { category: cat, filename: `${preset.label.toLowerCase().replace(/\s+/g,'_')}.md`, content: preset.value })
    toast(`Imported: ${preset.label}`)
    setImportOpen(null); onChanged()
  }

  const grouped = {}
  for (const f of files) {
    if (!grouped[f.category]) grouped[f.category] = []
    grouped[f.category].push(f)
  }

  return (
    <div>
      <div style={{ display:'flex', alignItems:'center', gap:8, marginBottom:12 }}>
        <span className="card-title">Knowledge & Skill Files</span>
        <div style={{ display:'flex', gap:4, marginLeft:'auto' }}>
          <button className="btn btn-outline btn-sm" onClick={()=>setImportOpen('personality')}>⬇ Import Personality</button>
          <button className="btn btn-outline btn-sm" onClick={()=>setImportOpen('tone')}>⬇ Import Tone</button>
          <button className="btn btn-outline btn-sm" onClick={()=>setImportOpen('skills')}>⬇ Import Skills</button>
          <button className="btn btn-success  btn-sm" onClick={()=>setAdding(true)}>＋ Add File</button>
        </div>
      </div>

      {Object.entries(grouped).map(([cat, catFiles]) => (
        <div key={cat} style={{ marginBottom:10 }}>
          <div style={{ fontSize:10, fontWeight:700, textTransform:'uppercase', color:'var(--muted)', marginBottom:5 }}>{cat}</div>
          {catFiles.map(f => (
            <div key={f.id} style={{ display:'flex', alignItems:'center', gap:8, padding:'6px 8px',
              background:'var(--bg)', borderRadius:6, border:'1px solid var(--border)', marginBottom:4 }}>
              <span style={{ fontSize:13, flex:1 }}>📄 {f.filename}</span>
              <span style={{ fontSize:10, color:'var(--muted)' }}>{f.content.length} chars</span>
              <button className="btn btn-outline btn-sm" onClick={()=>setEditing(f)}>✏ Edit</button>
              <button className="btn btn-danger  btn-sm" onClick={()=>del(f.id)}>🗑</button>
            </div>
          ))}
        </div>
      ))}
      {files.length === 0 && !adding && (
        <div style={{ textAlign:'center', padding:'20px', color:'var(--muted)', fontSize:12 }}>
          No files yet. Import presets or add custom files.
        </div>
      )}

      {/* Edit modal */}
      <Modal open={!!editing} onClose={()=>setEditing(null)} fullish>
        {editing && (
          <>
            <div className="modal-header">
              <span style={{ fontWeight:700 }}>✏ {editing.filename}</span>
              <span style={{ fontSize:11, color:'var(--muted)', marginLeft:8 }}>[{editing.category}]</span>
              <button className="btn btn-success btn-sm" style={{ marginLeft:'auto' }}
                onClick={()=>save(editing.category, editing.filename, editing.content)} disabled={saving}>
                {saving?<Spinner/>:'💾 Save'}
              </button>
              <button className="btn btn-ghost btn-sm" onClick={()=>setEditing(null)}>✕</button>
            </div>
            <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', flex:1, overflow:'hidden' }}>
              <textarea className="prompt-editor" style={{ border:'none', borderRight:'1px solid var(--border)', borderRadius:0, minHeight:400 }}
                value={editing.content} onChange={e=>setEditing({...editing, content:e.target.value})} />
              <div style={{ overflowY:'auto' }}><MarkdownPreview content={editing.content} /></div>
            </div>
          </>
        )}
      </Modal>

      {/* Add new file modal */}
      <Modal open={adding} onClose={()=>setAdding(false)}>
        <h3 style={{ marginBottom:14 }}>Add Knowledge File</h3>
        <div className="form-row form-row-2">
          <div className="form-group">
            <label className="form-label">Category</label>
            <select className="form-control" value={newCat} onChange={e=>setNewCat(e.target.value)}>
              {FILE_CATEGORIES.map(c=><option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          <div className="form-group">
            <label className="form-label">Filename</label>
            <input className="form-control" value={newName} onChange={e=>setNewName(e.target.value)} placeholder="e.g. core_skills.md" />
          </div>
        </div>
        <div className="form-group">
          <label className="form-label">Content (Markdown)</label>
          <textarea className="form-control" rows={10} style={{ resize:'vertical', fontFamily:'monospace', fontSize:12 }}
            value={newContent} onChange={e=>setNewContent(e.target.value)} placeholder="# Skills" />
        </div>
        <div style={{ display:'flex', gap:8 }}>
          <button className="btn btn-success" onClick={()=>save(newCat, newName||`${newCat}.md`, newContent)} disabled={saving}>
            {saving?<Spinner/>:'💾 Save'}
          </button>
          <button className="btn btn-ghost" onClick={()=>setAdding(false)}>Cancel</button>
        </div>
      </Modal>

      {/* Import preset modal */}
      <Modal open={!!importOpen} onClose={()=>setImportOpen(null)}>
        <h3 style={{ marginBottom:14 }}>⬇ Import {importOpen} Preset</h3>
        <p style={{ fontSize:12, color:'var(--muted)', marginBottom:14 }}>Select a preset to import as a file for this agent:</p>
        {(importOpen === 'personality' ? PRESET_PERSONALITIES
          : importOpen === 'tone' ? PRESET_TONES
          : PRESET_SKILLS
        ).map(preset => (
          <div key={preset.label} style={{ display:'flex', alignItems:'center', gap:10, padding:'10px', background:'var(--bg)',
            border:'1px solid var(--border)', borderRadius:7, marginBottom:8, cursor:'pointer' }}
            onClick={()=>importPreset(preset)}>
            <div style={{ flex:1 }}>
              <div style={{ fontSize:13, fontWeight:600 }}>{preset.label}</div>
              <div style={{ fontSize:11, color:'var(--muted)', marginTop:2 }}>{preset.value.substring(0,100)}…</div>
            </div>
            <button className="btn btn-primary btn-sm">Import</button>
          </div>
        ))}
        <button className="btn btn-ghost btn-sm" style={{ marginTop:8 }} onClick={()=>setImportOpen(null)}>Cancel</button>
      </Modal>
    </div>
  )
}

export default function AgentProfile() {
  const { id }   = useParams()
  const navigate = useNavigate()
  const { toast }= useApp()

  const [agent,    setAgent]    = useState(null)
  const [loading,  setLoading]  = useState(true)
  const [tab,      setTab]      = useState('chat')
  const [editing,  setEditing]  = useState(false)
  const [runningHB,setRunningHB]= useState(false)

  const [editName,        setEditName]        = useState('')
  const [editTitle,       setEditTitle]       = useState('')
  const [editPersonality, setEditPersonality] = useState('')
  const [editTone,        setEditTone]        = useState('')
  const [editHB,          setEditHB]          = useState(5)
  const [editModel,       setEditModel]       = useState('')
  const [editImage,       setEditImage]       = useState('')
  const [editExtraModels, setEditExtraModels] = useState('')

  const [spawnOpen,        setSpawnOpen]        = useState(false)
  const [spawnName,        setSpawnName]        = useState('')
  const [spawnRole,        setSpawnRole]        = useState('analyst')
  const [spawnPersonality, setSpawnPersonality] = useState('')
  const [spawnTone,        setSpawnTone]        = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    const data = await getAgent(id).catch(()=>null)
    if (data) {
      setAgent(data)
      setEditName(data.name); setEditTitle(data.title||'')
      setEditPersonality(data.personality||''); setEditTone(data.tone||'')
      setEditHB(data.heartbeat_interval||5); setEditModel(data.model_override||'')
      setEditImage(data.profile_image_url||''); setEditExtraModels(data.extra_models||'[]')
    }
    setLoading(false)
  }, [id])

  useEffect(() => { load() }, [load])

  const handleSave = async () => {
    await updateAgent(id, {
      name:editName, title:editTitle, personality:editPersonality,
      tone:editTone, heartbeat_interval:editHB, model_override:editModel,
      profile_image_url:editImage, extra_models:editExtraModels,
    })
    toast('Agent updated ✓'); setEditing(false); load()
  }

  const handleHB = async () => {
    setRunningHB(true)
    const r = await triggerHeartbeat(id).catch(e=>({ok:false,error:e.message}))
    toast(r.ok ? `✓ ${r.summary||'Done'}` : `✗ ${r.error}`, r.ok?'success':'error')
    setRunningHB(false); load()
  }

  const handleFire = async () => {
    if (!confirm(`Fire ${agent.name}? This is permanent.`)) return
    await fireAgent(id, { fired_by:'founder', reason:'Fired by Founder' })
    toast(`${agent.name} fired`); navigate('/agents')
  }

  const handleSpawn = async () => {
    if (!spawnName.trim()) return
    const r = await requestSpawn({
      requesting_agent_id: id, dept_id: agent.dept_id,
      proposed_name: spawnName, proposed_role: spawnRole,
      proposed_personality: spawnPersonality, proposed_tone: spawnTone,
      proposed_heartbeat: 5,
    })
    toast(r.auto_approved ? `"${spawnName}" spawned ✓` : 'Spawn request submitted')
    setSpawnOpen(false); setSpawnName(''); load()
  }

  if (loading) return <div className="empty"><Spinner lg /></div>
  if (!agent)  return <div className="empty">Agent not found.</div>

  const color = COLORS[agent.dept_id] || '#607D8B'

  return (
    <div>
      {/* Header */}
      <div style={{ display:'flex', gap:20, alignItems:'flex-start', marginBottom:24 }}>
        <AgentAvatar agent={agent} size={88} />
        <div style={{ flex:1 }}>
          <div style={{ display:'flex', alignItems:'center', gap:10, flexWrap:'wrap', marginBottom:6 }}>
            <h2 style={{ fontSize:24, fontWeight:800 }}>{agent.name}</h2>
            {agent.is_ceo && <span style={{ fontSize:12, background:'rgba(255,215,0,.2)', color:'gold', padding:'3px 10px', borderRadius:20, fontWeight:700, border:'1px solid rgba(255,215,0,.3)' }}>👑 CEO</span>}
            <span className="dept-tag" style={{ background:color }}>{agent.dept_id}</span>
            <span style={{ fontSize:11, padding:'3px 8px', borderRadius:4, fontWeight:700, textTransform:'uppercase',
              background:agent.status==='active'?'rgba(63,185,80,.15)':'rgba(248,81,73,.15)',
              color:agent.status==='active'?'var(--green)':'var(--red)' }}>{agent.status}</span>
          </div>
          <div style={{ fontSize:14, color:'var(--muted)', marginBottom:8 }}>{agent.title || agent.role}</div>
          <div style={{ fontSize:12, color:'var(--muted)' }}>
            L{agent.hierarchy_level} hierarchy
            {agent.parent_name && ` · Reports to ${agent.parent_name}`}
            {agent.subordinate_count > 0 && ` · ${agent.subordinate_count} subordinates`}
            {` · ❤ every ${agent.heartbeat_interval} cycles`}
            {agent.model_override && ` · 🤖 ${agent.model_override}`}
          </div>
        </div>
        <div style={{ display:'flex', gap:8, flexWrap:'wrap', justifyContent:'flex-end' }}>
          <button className="btn btn-ghost btn-sm" onClick={()=>navigate('/agents')}>← Back</button>
          {agent.status==='active' && (
            <>
              <button className="btn btn-outline btn-sm" onClick={handleHB} disabled={runningHB}>
                {runningHB?<><Spinner/> Running…</>:'❤ Heartbeat'}
              </button>
              <button className="btn btn-primary btn-sm" onClick={()=>setSpawnOpen(true)}>🧬 Spawn</button>
              <button className="btn btn-outline btn-sm" onClick={()=>setEditing(true)}>✏ Edit</button>
              {!agent.is_ceo && <button className="btn btn-danger btn-sm" onClick={handleFire}>🔥 Fire</button>}
            </>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className="tabs">
        {['chat','profile','files','subordinates','log'].map(t=>(
          <button key={t} className={`tab${tab===t?' active':''}`} onClick={()=>setTab(t)}>
            {{ chat:'💬 Chat', profile:'👤 Profile', files:'📄 Files', subordinates:'👥 Team', log:'📋 Log' }[t]}
          </button>
        ))}
      </div>

      {/* CHAT TAB */}
      {tab === 'chat' && (
        <AgentChat agent={agent} initialHistory={agent.chat_history || []} />
      )}

      {/* PROFILE TAB */}
      {tab === 'profile' && (
        <div className="grid grid-2">
          <div className="card">
            <div className="card-header"><span className="card-title">Personality & Tone</span></div>
            <div style={{ marginBottom:12 }}>
              <div style={{ fontSize:11, fontWeight:700, color:'var(--muted)', textTransform:'uppercase', marginBottom:6 }}>Personality</div>
              <p style={{ fontSize:13, lineHeight:1.7 }}>{agent.personality || '—'}</p>
            </div>
            <div>
              <div style={{ fontSize:11, fontWeight:700, color:'var(--muted)', textTransform:'uppercase', marginBottom:6 }}>Tone</div>
              <p style={{ fontSize:13, lineHeight:1.7 }}>{agent.tone || '—'}</p>
            </div>
          </div>
          <div className="card">
            <div className="card-header"><span className="card-title">Technical Config</span></div>
            {[
              ['Heartbeat',     `Every ${agent.heartbeat_interval} cycles`],
              ['Model',         agent.model_override || 'Uses global setting'],
              ['Extra Models',  agent.extra_models === '[]' || !agent.extra_models ? 'None' : agent.extra_models],
              ['Last Heartbeat',agent.last_heartbeat ? agent.last_heartbeat.substring(0,16).replace('T',' ') : 'Never'],
              ['Created By',    agent.created_by],
              ['Created',       agent.created_at?.substring(0,10)],
            ].map(([l,v])=>(
              <div key={l} style={{ display:'flex', gap:10, padding:'7px 0', borderBottom:'1px solid var(--border)', fontSize:13 }}>
                <span style={{ color:'var(--muted)', width:130, flexShrink:0 }}>{l}</span>
                <span>{v}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* FILES TAB */}
      {tab === 'files' && (
        <div className="card">
          <MdFileEditor agentId={id} files={agent.md_files || []} onChanged={load} />
        </div>
      )}

      {/* SUBORDINATES TAB */}
      {tab === 'subordinates' && (
        <div>
          {(agent.subordinates||[]).length === 0 ? (
            <div className="empty">No subordinates.
              {agent.status==='active' && <button className="btn btn-primary btn-sm" style={{ marginLeft:8 }} onClick={()=>setSpawnOpen(true)}>🧬 Spawn one</button>}
            </div>
          ) : (
            <div className="grid grid-2" style={{ gridTemplateColumns:'repeat(auto-fill,minmax(280px,1fr))' }}>
              {agent.subordinates.map(s=>(
                <div key={s.id} className="card" style={{ cursor:'pointer' }} onClick={()=>navigate(`/agents/${s.id}`)}>
                  <div style={{ fontSize:14, fontWeight:700 }}>{s.name}</div>
                  <div style={{ fontSize:12, color:'var(--muted)' }}>{s.title||s.role} · L{s.hierarchy_level}</div>
                  <div style={{ fontSize:11, marginTop:4, color:s.status==='active'?'var(--green)':'var(--red)' }}>{s.status}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* LOG TAB */}
      {tab === 'log' && (
        <div className="card" style={{ padding:0 }}>
          {(agent.recent_heartbeats||[]).length === 0 ? (
            <div className="empty">No heartbeat history yet.</div>
          ) : agent.recent_heartbeats.map(b=>(
            <div key={b.id} style={{ display:'flex', gap:12, padding:'10px 16px', borderBottom:'1px solid var(--border)', alignItems:'flex-start' }}>
              <span style={{ fontSize:16 }}>{b.result_type==='ok'?'✅':'❌'}</span>
              <div style={{ flex:1 }}>
                <div style={{ fontSize:13 }}>{b.summary||'Heartbeat complete'}</div>
                {b.actions_json && b.actions_json !== '[]' && (
                  <div style={{ fontSize:11, color:'var(--muted)', marginTop:3 }}>
                    Actions: {(() => { try { const a=JSON.parse(b.actions_json); return a.join(' · ') } catch { return '' } })()}
                  </div>
                )}
              </div>
              <span style={{ fontSize:11, color:'var(--muted)', whiteSpace:'nowrap' }}>{b.ran_at?.substring(0,16).replace('T',' ')}</span>
            </div>
          ))}
        </div>
      )}

      {/* EDIT MODAL */}
      <Modal open={editing} onClose={()=>setEditing(false)} wide>
        <h3 style={{ marginBottom:16 }}>Edit {agent.name}</h3>
        <div className="form-row form-row-2">
          <div className="form-group">
            <label className="form-label">Name</label>
            <input className="form-control" value={editName} onChange={e=>setEditName(e.target.value)} />
          </div>
          <div className="form-group">
            <label className="form-label">Title</label>
            <input className="form-control" value={editTitle} onChange={e=>setEditTitle(e.target.value)} />
          </div>
        </div>
        <div className="form-group">
          <label className="form-label">Personality & Traits</label>
          <textarea className="form-control" rows={4} style={{ resize:'vertical' }}
            value={editPersonality} onChange={e=>setEditPersonality(e.target.value)} />
        </div>
        <div className="form-group">
          <label className="form-label">Communication Tone</label>
          <input className="form-control" value={editTone} onChange={e=>setEditTone(e.target.value)} />
        </div>
        <div className="form-row form-row-2">
          <div className="form-group">
            <label className="form-label">Heartbeat Interval</label>
            <input type="number" className="form-control" min={1} value={editHB} onChange={e=>setEditHB(Number(e.target.value))} />
          </div>
          <div className="form-group">
            <label className="form-label">Model Override</label>
            <input className="form-control" list="model-dl" value={editModel} onChange={e=>setEditModel(e.target.value)} placeholder="e.g. ollama:llama3, claude-haiku" />
            <datalist id="model-dl">
              <option value="claude-sonnet-4-20250514"/>
              <option value="claude-haiku-4-5"/>
              <option value="ollama:llama3"/>
              <option value="ollama:mistral"/>
              <option value="ollama:deepseek-r1:7b"/>
              <option value="ollama:qwq:32b"/>
              <option value="ollama:gemma3:4b"/>
            </datalist>
          </div>
        </div>
        <div className="form-group">
          <label className="form-label">Profile Image URL</label>
          <input className="form-control" value={editImage} onChange={e=>setEditImage(e.target.value)} placeholder="https://…" />
        </div>
        <div className="form-group">
          <label className="form-label">Extra Models (JSON array)
            <span style={{ fontWeight:400, textTransform:'none', color:'var(--muted)' }}> — image gen, eval, etc.</span>
          </label>
          <input className="form-control" value={editExtraModels} onChange={e=>setEditExtraModels(e.target.value)}
            placeholder='["dall-e-3", "clip-vit-large"]' />
        </div>
        <div style={{ display:'flex', gap:8 }}>
          <button className="btn btn-success" onClick={handleSave}>💾 Save</button>
          <button className="btn btn-ghost"   onClick={()=>setEditing(false)}>Cancel</button>
        </div>
      </Modal>

      {/* SPAWN MODAL */}
      <Modal open={spawnOpen} onClose={()=>setSpawnOpen(false)}>
        <h3 style={{ marginBottom:16 }}>🧬 Spawn Sub-agent under {agent.name}</h3>
        <div className="form-row form-row-2">
          <div className="form-group">
            <label className="form-label">Name *</label>
            <input className="form-control" value={spawnName} onChange={e=>setSpawnName(e.target.value)} />
          </div>
          <div className="form-group">
            <label className="form-label">Role</label>
            <select className="form-control" value={spawnRole} onChange={e=>setSpawnRole(e.target.value)}>
              <option value="analyst">Analyst</option>
              <option value="junior">Junior Agent</option>
              <option value="specialist">Specialist</option>
              <option value="senior">Senior Agent</option>
            </select>
          </div>
        </div>
        <div className="form-group">
          <label className="form-label">Personality</label>
          <textarea className="form-control" rows={2} value={spawnPersonality} onChange={e=>setSpawnPersonality(e.target.value)} />
        </div>
        <div className="form-group">
          <label className="form-label">Tone</label>
          <input className="form-control" value={spawnTone} onChange={e=>setSpawnTone(e.target.value)} />
        </div>
        {agent.is_ceo
          ? <p style={{ fontSize:12, color:'var(--green)', marginBottom:8 }}>✓ As CEO, this spawn is auto-approved.</p>
          : <p style={{ fontSize:12, color:'var(--orange)', marginBottom:8 }}>⚠ Requires Founder approval.</p>}
        <div style={{ display:'flex', gap:8 }}>
          <button className="btn btn-success" onClick={handleSpawn}>🧬 Spawn</button>
          <button className="btn btn-ghost"   onClick={()=>setSpawnOpen(false)}>Cancel</button>
        </div>
      </Modal>
    </div>
  )
}
