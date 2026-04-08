import React, { useState, useEffect, useCallback, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  getAgent, updateAgent, fireAgent, triggerHeartbeat,
  getAgentFiles, upsertAgentFile, deleteAgentFile,
  requestSpawn, updateHeartbeatInterval, getRandomFace,
} from '../../api'
import { useApp } from '../../context/AppContext'
import { COLORS } from '../../constants'
import Spinner from '../../components/UI/Spinner'
import Modal from '../../components/UI/Modal'
import MarkdownPreview from '../../components/Editor/MarkdownPreview'
import AgentChat from './AgentChat'
import ModelImporter from '../../components/UI/ModelImporter'

// Only ONE personality file per agent
const PERSONALITY_CAT = 'personality'
const TONE_CAT = 'tone'
const FILE_CATEGORIES = ['skills', PERSONALITY_CAT, 'traits', TONE_CAT, 'guidelines', 'prompts', 'knowledge']

// ── Heartbeat Scheduler ───────────────────────────────────────────────────────

const INTERVAL_PRESETS = [
  { label: 'Every cycle',     value: 1   },
  { label: 'Every 3',        value: 3   },
  { label: 'Every 5',        value: 5   },
  { label: 'Every 10',       value: 10  },
  { label: 'Every 30',       value: 30  },
  { label: 'Every 60',       value: 60  },
  { label: 'Hourly (120)',   value: 120 },
  { label: 'Daily (960)',    value: 960 },
  { label: 'Paused (never)', value: 9999},
]

function HeartbeatScheduler({ agent, onUpdated }) {
  const { toast } = useApp()
  const [interval, setIntervalVal] = useState(agent.heartbeat_interval || 5)
  const [saving, setSaving]        = useState(false)

  const save = async () => {
    setSaving(true)
    await updateHeartbeatInterval(agent.id, interval)
    toast(`Heartbeat set to every ${interval} cycles ✓`)
    setSaving(false); onUpdated?.()
  }

  const nextBeat = () => {
    if (!agent.last_heartbeat || interval >= 9999) return 'Paused'
    const last = new Date(agent.last_heartbeat)
    const nextMs = last.getTime() + interval * 60 * 1000
    const diff   = Math.round((nextMs - Date.now()) / 60000)
    if (diff <= 0) return 'Overdue'
    return `in ~${diff}m`
  }

  const isPaused = interval >= 9999

  return (
    <div className="card">
      <div className="card-header">
        <span className="card-title">❤ Heartbeat Schedule</span>
        <span style={{ fontSize:12, color:isPaused?'var(--red)':'var(--green)', fontWeight:700 }}>
          {isPaused ? '⏸ Paused' : `Next: ${nextBeat()}`}
        </span>
      </div>
      <div style={{ display:'flex', gap:8, flexWrap:'wrap', marginBottom:12 }}>
        {INTERVAL_PRESETS.map(p => (
          <button key={p.value} className={`btn btn-sm ${interval===p.value?'btn-primary':'btn-outline'}`}
            onClick={() => setIntervalVal(p.value)}>{p.label}</button>
        ))}
      </div>
      <div style={{ display:'flex', gap:10, alignItems:'center' }}>
        <div style={{ flex:1 }}>
          <label className="form-label">Custom (cycles)</label>
          <div style={{ display:'flex', gap:8, alignItems:'center', marginTop:4 }}>
            <input type="range" min={1} max={1440} value={Math.min(interval,1440)}
              onChange={e=>setIntervalVal(Number(e.target.value))}
              style={{ flex:1, accentColor:'var(--accent)' }} />
            <input type="number" className="form-control" min={1} max={9999}
              value={interval} onChange={e=>setIntervalVal(Number(e.target.value))}
              style={{ width:72 }} />
          </div>
        </div>
        <button className="btn btn-success" onClick={save} disabled={saving} style={{ alignSelf:'flex-end' }}>
          {saving?<Spinner/>:'💾 Save'}
        </button>
      </div>
      {agent.last_heartbeat && (
        <div style={{ fontSize:11, color:'var(--muted)', marginTop:10 }}>
          Last run: {agent.last_heartbeat.substring(0,16).replace('T',' ')} UTC
        </div>
      )}
    </div>
  )
}

// ── Agent avatar + image manager ─────────────────────────────────────────────

function AgentAvatar({ agent, size=80, onImageChanged }) {
  const { toast } = useApp()
  const [loading, setLoading] = useState(false)
  const fileRef = useRef()

  const fetchRandomFace = async () => {
    setLoading(true)
    try {
      const r = await getRandomFace()
      if (r.data_url) {
        await updateAgent(agent.id, { profile_image_url: r.data_url })
        toast('Profile image updated ✓')
        onImageChanged?.(r.data_url)
      } else {
        toast('Could not fetch face: ' + (r.error||'Unknown error'), 'error')
      }
    } catch (e) {
      toast('Failed: ' + e.message, 'error')
    }
    setLoading(false)
  }

  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    if (!file.type.startsWith('image/')) { toast('Please upload an image file', 'error'); return }
    setLoading(true)
    const reader = new FileReader()
    reader.onload = async (ev) => {
      const dataUrl = ev.target.result
      await updateAgent(agent.id, { profile_image_url: dataUrl })
      toast('Profile image updated ✓')
      onImageChanged?.(dataUrl)
      setLoading(false)
    }
    reader.readAsDataURL(file)
  }

  return (
    <div style={{ position:'relative', flexShrink:0 }}>
      {agent.profile_image_url ? (
        <img src={agent.profile_image_url} alt={agent.name}
          style={{ width:size, height:size, borderRadius:'50%', objectFit:'cover',
            border:`3px solid ${agent.is_ceo?'gold':'var(--border)'}` }} />
      ) : (
        <div style={{ width:size, height:size, borderRadius:'50%',
          background:COLORS[agent.dept_id]||'#607D8B',
          display:'flex', alignItems:'center', justifyContent:'center',
          fontSize:size*0.35, fontWeight:800, color:'#fff',
          border:`${agent.is_ceo?4:3}px solid ${agent.is_ceo?'gold':'var(--border)'}` }}>
          {agent.name.split(' ').map(w=>w[0]).join('').toUpperCase().slice(0,2)}
        </div>
      )}
      {onImageChanged && (
        <div style={{ position:'absolute', bottom:-4, right:-4, display:'flex', gap:3 }}>
          <button className="btn btn-sm" title="Upload image"
            style={{ padding:'2px 6px', fontSize:11, borderRadius:10 }}
            onClick={() => fileRef.current?.click()}>📷</button>
          <button className="btn btn-sm" title="Random face (thispersondoesnotexist.com)"
            style={{ padding:'2px 6px', fontSize:11, borderRadius:10 }}
            onClick={fetchRandomFace} disabled={loading}>
            {loading ? <Spinner /> : '🎲'}
          </button>
          <input ref={fileRef} type="file" accept="image/*" style={{ display:'none' }} onChange={handleFileUpload} />
        </div>
      )}
    </div>
  )
}

// ── MD Files editor ───────────────────────────────────────────────────────────

function MdFileEditor({ agentId, files, onChanged }) {
  const { toast } = useApp()
  const [editing,    setEditing]    = useState(null)
  const [adding,     setAdding]     = useState(false)
  const [newCat,     setNewCat]     = useState(FILE_CATEGORIES[0])
  const [newName,    setNewName]    = useState('')
  const [newContent, setNewContent] = useState('')
  const [saving,     setSaving]     = useState(false)
  const fileUploadRef = useRef()

  // Personality/tone are derived from these special files
  const personalityFile = files.find(f => f.category === PERSONALITY_CAT)
  const toneFiles       = files.filter(f => f.category === TONE_CAT)

  const save = async (category, filename, content) => {
    setSaving(true)
    // Enforce: only ONE personality file per agent
    if (category === PERSONALITY_CAT) {
      const existing = files.find(f => f.category === PERSONALITY_CAT && f.id !== editing?.id)
      if (existing) {
        // Replace it
        await deleteAgentFile(agentId, existing.id)
      }
    }
    await upsertAgentFile(agentId, { category, filename, content })
    // Sync personality/tone fields on the agent record
    if (category === PERSONALITY_CAT) {
      await updateAgent(agentId, { personality: content })
    } else if (category === TONE_CAT) {
      const allTone = files.filter(f => f.category===TONE_CAT && f.id !== editing?.id).map(f=>f.content)
      allTone.push(content)
      await updateAgent(agentId, { tone: allTone.join('\n\n---\n\n') })
    }
    toast('Saved ✓'); setSaving(false); setEditing(null); setAdding(false)
    onChanged()
  }

  const del = async (file) => {
    if (!confirm(`Delete "${file.filename}"?`)) return
    await deleteAgentFile(agentId, file.id)
    // Clear derived field if needed
    if (file.category === PERSONALITY_CAT) {
      await updateAgent(agentId, { personality: '' })
    } else if (file.category === TONE_CAT) {
      const remaining = files.filter(f => f.category===TONE_CAT && f.id !== file.id).map(f=>f.content)
      await updateAgent(agentId, { tone: remaining.join('\n\n---\n\n') })
    }
    toast('Deleted'); onChanged()
  }

  const handleFileImport = async (e) => {
    const f = e.target.files?.[0]
    if (!f) return
    const text = await f.text()
    setNewContent(text)
    setNewName(f.name.endsWith('.md') ? f.name : f.name + '.md')
    setAdding(true)
  }

  const handleModelImport = async ({ category, content, name }) => {
    const filename = name.toLowerCase().replace(/\s+/g, '_').replace(/[^a-z0-9_]/g, '') + '.md'
    await save(category, filename, content)
  }

  const grouped = {}
  for (const f of files) {
    if (!grouped[f.category]) grouped[f.category] = []
    grouped[f.category].push(f)
  }

  return (
    <div>
      <div style={{ display:'flex', alignItems:'center', gap:8, marginBottom:14 }}>
        <span className="card-title">Knowledge & Skill Files</span>
        <div style={{ marginLeft:'auto', display:'flex', gap:6 }}>
          <input ref={fileUploadRef} type="file" accept=".md,.txt,.json" style={{ display:'none' }} onChange={handleFileImport} />
          <button className="btn btn-outline btn-sm" onClick={() => fileUploadRef.current?.click()}>
            📎 Upload File
          </button>
          <ModelImporter onImport={handleModelImport} defaultCategory="personality" />
          <button className="btn btn-success btn-sm" onClick={() => setAdding(true)}>＋ Add File</button>
        </div>
      </div>

      {/* Special notice for personality */}
      {personalityFile && (
        <div style={{ fontSize:11, color:'var(--accent)', marginBottom:8, padding:'6px 10px',
          background:'rgba(88,166,255,.08)', borderRadius:6, border:'1px solid rgba(88,166,255,.2)' }}>
          📌 <strong>Personality</strong> is derived from <em>{personalityFile.filename}</em>.
          Agent tone, personality fields are read-only — edit the file to change them.
        </div>
      )}

      {Object.entries(grouped).map(([cat, catFiles]) => (
        <div key={cat} style={{ marginBottom:12 }}>
          <div style={{ fontSize:10, fontWeight:700, textTransform:'uppercase', color:'var(--muted)', marginBottom:5 }}>
            {cat}
            {cat===PERSONALITY_CAT && <span style={{ marginLeft:6, color:'var(--accent)' }}>— 1 max</span>}
          </div>
          {catFiles.map(f => (
            <div key={f.id} style={{ display:'flex', alignItems:'center', gap:8, padding:'6px 8px',
              background:'var(--bg)', borderRadius:6, border:'1px solid var(--border)', marginBottom:4 }}>
              <span style={{ fontSize:13, flex:1 }}>
                {cat===PERSONALITY_CAT?'🧠':cat===TONE_CAT?'🎙':cat==='skills'?'⚡':'📄'} {f.filename}
              </span>
              <span style={{ fontSize:10, color:'var(--muted)' }}>{f.content.length} chars</span>
              <button className="btn btn-outline btn-sm" onClick={()=>setEditing(f)}>✏ Edit</button>
              <button className="btn btn-danger btn-sm" onClick={()=>del(f)}>🗑</button>
            </div>
          ))}
        </div>
      ))}

      {files.length === 0 && !adding && (
        <div style={{ textAlign:'center', padding:'20px', color:'var(--muted)', fontSize:12 }}>
          No files yet. Use "Import Template" or "Add File" to get started.
        </div>
      )}

      {/* Edit modal */}
      <Modal open={!!editing} onClose={()=>setEditing(null)} fullish>
        {editing && (
          <>
            <div className="modal-header">
              <span style={{ fontWeight:700 }}>✏ {editing.filename}</span>
              <span style={{ fontSize:11, color:'var(--muted)', marginLeft:8 }}>[{editing.category}]</span>
              {editing.category===PERSONALITY_CAT && (
                <span style={{ fontSize:10, color:'var(--accent)', marginLeft:8 }}>
                  ⚡ Changes here update agent personality
                </span>
              )}
              <button className="btn btn-success btn-sm" style={{ marginLeft:'auto' }}
                onClick={()=>save(editing.category, editing.filename, editing.content)} disabled={saving}>
                {saving?<Spinner/>:'💾 Save'}
              </button>
              <button className="btn btn-ghost btn-sm" onClick={()=>setEditing(null)}>✕</button>
            </div>
            <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', flex:1, overflow:'hidden' }}>
              <textarea className="prompt-editor"
                style={{ border:'none', borderRight:'1px solid var(--border)', borderRadius:0, minHeight:400 }}
                value={editing.content} onChange={e=>setEditing({...editing, content:e.target.value})} />
              <div style={{ overflowY:'auto' }}><MarkdownPreview content={editing.content} /></div>
            </div>
          </>
        )}
      </Modal>

      {/* Add new file modal */}
      <Modal open={adding} onClose={()=>setAdding(false)}>
        <h3 style={{ marginBottom:14 }}>Add Knowledge File</h3>
        {newCat === PERSONALITY_CAT && personalityFile && (
          <div style={{ fontSize:12, color:'var(--orange)', marginBottom:10, padding:'6px 10px',
            background:'rgba(210,153,34,.1)', borderRadius:6 }}>
            ⚠ A personality file already exists ({personalityFile.filename}). Saving will replace it.
          </div>
        )}
        <div className="form-row form-row-2">
          <div className="form-group">
            <label className="form-label">Category</label>
            <select className="form-control" value={newCat} onChange={e=>setNewCat(e.target.value)}>
              {FILE_CATEGORIES.map(c=><option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          <div className="form-group">
            <label className="form-label">Filename</label>
            <input className="form-control" value={newName} onChange={e=>setNewName(e.target.value)}
              placeholder="e.g. core_skills.md" />
          </div>
        </div>
        <div className="form-group">
          <label className="form-label">Content (Markdown)</label>
          <textarea className="form-control" rows={10}
            style={{ resize:'vertical', fontFamily:'monospace', fontSize:12 }}
            value={newContent} onChange={e=>setNewContent(e.target.value)} placeholder="# Skills" />
        </div>
        <div style={{ display:'flex', gap:8 }}>
          <button className="btn btn-success"
            onClick={()=>save(newCat, newName||`${newCat}.md`, newContent)} disabled={saving}>
            {saving?<Spinner/>:'💾 Save'}
          </button>
          <button className="btn btn-ghost" onClick={()=>setAdding(false)}>Cancel</button>
        </div>
      </Modal>
    </div>
  )
}

// ── Main AgentProfile component ───────────────────────────────────────────────

export default function AgentProfile() {
  const { id }    = useParams()
  const navigate  = useNavigate()
  const { toast } = useApp()

  const [agent,     setAgent]     = useState(null)
  const [loading,   setLoading]   = useState(true)
  const [tab,       setTab]       = useState('chat')
  const [editing,   setEditing]   = useState(false)
  const [runningHB, setRunningHB] = useState(false)
  const [profileImg,setProfileImg]= useState('')

  const [editName,       setEditName]       = useState('')
  const [editTitle,      setEditTitle]      = useState('')
  const [editHB,         setEditHB]         = useState(5)
  const [editModel,      setEditModel]      = useState('')
  const [editExtraModels,setEditExtraModels]= useState('')

  const [spawnOpen,        setSpawnOpen]        = useState(false)
  const [spawnName,        setSpawnName]        = useState('')
  const [spawnRole,        setSpawnRole]        = useState('analyst')
  const [spawnPersonality, setSpawnPersonality] = useState('')
  const [spawnTone,        setSpawnTone]        = useState('')
  const [spawningFace,     setSpawningFace]     = useState(false)
  const [spawnFaceUrl,     setSpawnFaceUrl]     = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    const data = await getAgent(id).catch(()=>null)
    if (data) {
      setAgent(data)
      setEditName(data.name); setEditTitle(data.title||'')
      setEditHB(data.heartbeat_interval||5); setEditModel(data.model_override||'')
      setEditExtraModels(data.extra_models||'[]')
      setProfileImg(data.profile_image_url||'')
    }
    setLoading(false)
  }, [id])

  useEffect(() => { load() }, [load])

  // Personality and tone are READ-ONLY — derived from MD files
  const personalityFile = agent?.md_files?.find(f => f.category === PERSONALITY_CAT)
  const toneFiles       = agent?.md_files?.filter(f => f.category === TONE_CAT) || []
  const derivedPersonality = personalityFile?.content || agent?.personality || ''
  const derivedTone        = toneFiles.map(f=>f.content).join('\n\n---\n\n') || agent?.tone || ''

  const handleSave = async () => {
    await updateAgent(id, {
      name: editName, title: editTitle,
      heartbeat_interval: editHB, model_override: editModel,
      profile_image_url: profileImg, extra_models: editExtraModels,
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

  const fetchSpawnFace = async () => {
    setSpawningFace(true)
    const r = await getRandomFace().catch(()=>({}))
    if (r.data_url) setSpawnFaceUrl(r.data_url)
    setSpawningFace(false)
  }

  const handleSpawn = async () => {
    if (!spawnName.trim()) return
    // Auto-fetch a face if none yet
    let faceUrl = spawnFaceUrl
    if (!faceUrl) {
      const r = await getRandomFace().catch(()=>({}))
      faceUrl = r.data_url || ''
    }
    const r = await requestSpawn({
      requesting_agent_id: id, dept_id: agent.dept_id,
      proposed_name: spawnName, proposed_role: spawnRole,
      proposed_personality: spawnPersonality, proposed_tone: spawnTone,
      proposed_heartbeat: 5,
    })
    // Set the face on the new agent if auto-approved
    if (r.auto_approved && r.agent_id && faceUrl) {
      await updateAgent(r.agent_id, { profile_image_url: faceUrl }).catch(()=>{})
    }
    toast(r.auto_approved ? `"${spawnName}" spawned ✓` : 'Spawn request submitted')
    setSpawnOpen(false); setSpawnName(''); setSpawnFaceUrl(''); load()
  }

  if (loading) return <div className="empty"><Spinner lg /></div>
  if (!agent)  return <div className="empty">Agent not found.</div>

  const color = COLORS[agent.dept_id] || '#607D8B'

  return (
    <div>
      {/* Header */}
      <div style={{ display:'flex', gap:20, alignItems:'flex-start', marginBottom:24 }}>
        <AgentAvatar agent={{ ...agent, profile_image_url: profileImg }}
          size={88} onImageChanged={url => { setProfileImg(url); load() }} />
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
              <button className="btn btn-primary btn-sm" onClick={()=>{ setSpawnOpen(true); fetchSpawnFace() }}>🧬 Spawn</button>
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
        <div>
          <div className="grid grid-2" style={{ marginBottom:16 }}>
            <div className="card">
              <div className="card-header"><span className="card-title">🧠 Personality & Tone</span>
                <span style={{ fontSize:10, color:'var(--muted)', marginLeft:'auto' }}>
                  ⚡ Derived from Files tab — read only here
                </span>
              </div>
              <div style={{ marginBottom:12 }}>
                <div style={{ fontSize:11, fontWeight:700, color:'var(--muted)', textTransform:'uppercase', marginBottom:6 }}>
                  Personality
                  {personalityFile && <span style={{ marginLeft:6, fontWeight:400 }}>({personalityFile.filename})</span>}
                </div>
                {derivedPersonality ? (
                  <div style={{ fontSize:13, lineHeight:1.7, padding:'8px 10px', background:'var(--bg)',
                    borderRadius:6, border:'1px solid var(--border)', maxHeight:200, overflowY:'auto',
                    cursor:'not-allowed', opacity:.8 }}>
                    {derivedPersonality.substring(0, 400)}{derivedPersonality.length > 400 ? '…' : ''}
                  </div>
                ) : (
                  <div style={{ fontSize:12, color:'var(--muted)', fontStyle:'italic' }}>
                    No personality file yet. Add one in the Files tab.
                  </div>
                )}
              </div>
              <div>
                <div style={{ fontSize:11, fontWeight:700, color:'var(--muted)', textTransform:'uppercase', marginBottom:6 }}>
                  Tone {toneFiles.length > 0 && `(${toneFiles.length} file${toneFiles.length>1?'s':''})`}
                </div>
                {derivedTone ? (
                  <div style={{ fontSize:13, lineHeight:1.7, padding:'8px 10px', background:'var(--bg)',
                    borderRadius:6, border:'1px solid var(--border)', maxHeight:160, overflowY:'auto',
                    cursor:'not-allowed', opacity:.8 }}>
                    {derivedTone.substring(0, 300)}{derivedTone.length > 300 ? '…' : ''}
                  </div>
                ) : (
                  <div style={{ fontSize:12, color:'var(--muted)', fontStyle:'italic' }}>
                    No tone file yet. Add one in the Files tab.
                  </div>
                )}
              </div>
              <div style={{ marginTop:10 }}>
                <button className="btn btn-outline btn-sm" onClick={()=>setTab('files')}>
                  → Edit personality/tone in Files tab
                </button>
              </div>
            </div>
            <div className="card">
              <div className="card-header"><span className="card-title">⚙ Technical Config</span></div>
              {[
                ['Model',        agent.model_override || 'Uses global setting'],
                ['Extra Models', agent.extra_models==='[]'||!agent.extra_models ? 'None' : agent.extra_models],
                ['Last Heartbeat',agent.last_heartbeat ? agent.last_heartbeat.substring(0,16).replace('T',' ') : 'Never'],
                ['Created By',   agent.created_by],
                ['Created',      agent.created_at?.substring(0,10)],
              ].map(([l,v])=>(
                <div key={l} style={{ display:'flex', gap:10, padding:'7px 0', borderBottom:'1px solid var(--border)', fontSize:13 }}>
                  <span style={{ color:'var(--muted)', width:130, flexShrink:0 }}>{l}</span>
                  <span style={{ overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>{v}</span>
                </div>
              ))}
            </div>
          </div>
          <HeartbeatScheduler agent={agent} onUpdated={load} />
        </div>
      )}

      {/* FILES TAB */}
      {tab === 'files' && (
        <div className="card">
          <MdFileEditor agentId={id} files={agent.md_files||[]} onChanged={load} />
        </div>
      )}

      {/* SUBORDINATES TAB */}
      {tab === 'subordinates' && (
        <div>
          {(agent.subordinates||[]).length === 0 ? (
            <div className="empty">No subordinates.
              {agent.status==='active' && (
                <button className="btn btn-primary btn-sm" style={{ marginLeft:8 }}
                  onClick={()=>{ setSpawnOpen(true); fetchSpawnFace() }}>🧬 Spawn one</button>
              )}
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
                    Actions: {(() => { try { const a=JSON.parse(b.actions_json); return Array.isArray(a)?a.join(' · '):'' } catch { return '' } })()}
                  </div>
                )}
              </div>
              <span style={{ fontSize:11, color:'var(--muted)', whiteSpace:'nowrap' }}>{b.ran_at?.substring(0,16).replace('T',' ')}</span>
            </div>
          ))}
        </div>
      )}

      {/* EDIT MODAL — no personality/tone fields (those come from files) */}
      <Modal open={editing} onClose={()=>setEditing(false)} wide>
        <h3 style={{ marginBottom:16 }}>Edit {agent.name}</h3>
        <div style={{ fontSize:12, color:'var(--muted)', marginBottom:12, padding:'6px 10px',
          background:'rgba(88,166,255,.06)', borderRadius:6, border:'1px solid rgba(88,166,255,.15)' }}>
          💡 Personality &amp; Tone are derived from the agent's <strong>Files tab</strong> and cannot be edited here directly.
        </div>
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
        <div className="form-row form-row-2">
          <div className="form-group">
            <label className="form-label">Heartbeat Interval (cycles)</label>
            <input type="number" className="form-control" min={1} value={editHB}
              onChange={e=>setEditHB(Number(e.target.value))} />
          </div>
          <div className="form-group">
            <label className="form-label">Model Override</label>
            <input className="form-control" list="model-dl" value={editModel}
              onChange={e=>setEditModel(e.target.value)} placeholder="e.g. ollama:llama3, claude-haiku" />
            <datalist id="model-dl">
              <option value="claude-sonnet-4-20250514"/>
              <option value="claude-haiku-4-5"/>
              <option value="ollama:llama3"/>
              <option value="ollama:mistral"/>
              <option value="ollama:deepseek-r1:7b"/>
            </datalist>
          </div>
        </div>
        <div className="form-group">
          <label className="form-label">Extra Models (JSON array) — image gen, eval, etc.</label>
          <input className="form-control" value={editExtraModels} onChange={e=>setEditExtraModels(e.target.value)}
            placeholder='["dall-e-3", "clip-vit"]' />
        </div>
        <div style={{ display:'flex', gap:8 }}>
          <button className="btn btn-success" onClick={handleSave}>💾 Save</button>
          <button className="btn btn-ghost" onClick={()=>setEditing(false)}>Cancel</button>
        </div>
      </Modal>

      {/* SPAWN MODAL */}
      <Modal open={spawnOpen} onClose={()=>setSpawnOpen(false)}>
        <h3 style={{ marginBottom:16 }}>🧬 Spawn Sub-agent under {agent.name}</h3>
        {/* Face preview */}
        <div style={{ display:'flex', alignItems:'center', gap:12, marginBottom:14 }}>
          {spawnFaceUrl ? (
            <img src={spawnFaceUrl} alt="face"
              style={{ width:56, height:56, borderRadius:'50%', objectFit:'cover', border:'2px solid var(--border)' }} />
          ) : (
            <div style={{ width:56, height:56, borderRadius:'50%', background:'var(--bg)',
              border:'2px dashed var(--border)', display:'flex', alignItems:'center', justifyContent:'center', fontSize:20 }}>👤</div>
          )}
          <button className="btn btn-outline btn-sm" onClick={fetchSpawnFace} disabled={spawningFace}>
            {spawningFace ? <Spinner /> : '🎲 New Face'}
          </button>
          <span style={{ fontSize:11, color:'var(--muted)' }}>A random face will be auto-assigned if not retried.</span>
        </div>
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
          <button className="btn btn-ghost" onClick={()=>setSpawnOpen(false)}>Cancel</button>
        </div>
      </Modal>
    </div>
  )
}
