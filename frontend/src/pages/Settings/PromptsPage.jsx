import React, { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { getAllPrompts, saveDeptPrompt, updateAgent, saveSettings, getSettings } from '../../api'
import { useApp } from '../../context/AppContext'
import { COLORS } from '../../constants'
import Spinner from '../../components/UI/Spinner'
import MarkdownPreview from '../../components/Editor/MarkdownPreview'

// ── Prompt descriptions for each section ─────────────────────────────────────
const PROMPT_DESCRIPTIONS = {
  global_prepend: {
    label: '🌐 Global Prepend',
    desc: 'Injected at the very START of every agent\'s system prompt, across ALL departments. Use for: company-wide rules, universal policies, operational constraints that every agent must follow regardless of role.',
    example: 'e.g. "You are part of the Central Think Tank. Never share confidential data with external parties."'
  },
  global_append: {
    label: '🌐 Global Append',
    desc: 'Injected at the very END of every agent\'s system prompt. Use for: formatting rules, final fallback instructions, output constraints. Evaluated last, so it can override earlier instructions.',
    example: 'e.g. "Always respond in English. Never exceed 500 words in a single message."'
  },
  dept_prompt: {
    label: '🏛 Department System Prompt',
    desc: 'The primary system prompt for this department. Defines the department\'s mandate, responsibilities, communication style, and decision authority. Injected after the global prepend and before the agent\'s own personality.',
    example: 'e.g. Mission, core responsibilities, escalation rules, output formats.'
  },
  agent_personality: {
    label: '🧠 Agent Personality (from files)',
    desc: 'Derived from the agent\'s personality MD file. Describes behavioral tendencies, decision-making style, strengths, and weaknesses. Injected after the department prompt. Read-only here — edit via agent Files tab.',
    example: 'e.g. "Analytical, data-driven. Never makes recommendations without evidence."'
  },
  agent_tone: {
    label: '🎙 Agent Tone (from files)',
    desc: 'Derived from the agent\'s tone MD file(s). Defines how the agent writes and communicates. Injected after personality. Read-only here — edit via agent Files tab.',
    example: 'e.g. "Military brief format. SITUATION / ASSESSMENT / RECOMMENDATION."'
  },
  agent_skills: {
    label: '⚡ Agent Skills & Knowledge',
    desc: 'All other MD files attached to the agent (skills, traits, guidelines, knowledge). These are included in the system prompt after personality/tone, giving the agent domain expertise.',
    example: 'e.g. Financial analysis frameworks, cybersecurity runbooks, product roadmap templates.'
  },
}

function PromptBox({ label, desc, example, value, onSave, readonly = false, rows = 8 }) {
  const { toast } = useApp()
  const [editing, setEditing] = useState(false)
  const [draft,   setDraft]   = useState(value || '')
  const [saving,  setSaving]  = useState(false)
  const [preview, setPreview] = useState(false)

  useEffect(() => { setDraft(value || '') }, [value])

  const save = async () => {
    setSaving(true)
    await onSave(draft)
    toast('Saved ✓')
    setSaving(false); setEditing(false)
  }

  return (
    <div style={{ marginBottom: 24 }}>
      <div style={{ display:'flex', alignItems:'flex-start', gap:10, marginBottom:6 }}>
        <div style={{ flex:1 }}>
          <div style={{ fontSize:13, fontWeight:700, color:'var(--text)' }}>{label}</div>
          <div style={{ fontSize:11, color:'var(--muted)', marginTop:2, lineHeight:1.5 }}>{desc}</div>
          {example && <div style={{ fontSize:10, color:'var(--accent)', marginTop:2, fontStyle:'italic' }}>{example}</div>}
        </div>
        {!readonly && (
          <div style={{ display:'flex', gap:6, flexShrink:0 }}>
            {editing && (
              <button className="btn btn-outline btn-sm" onClick={()=>setPreview(p=>!p)}>
                {preview ? '✏ Edit' : '👁 Preview'}
              </button>
            )}
            {editing ? (
              <>
                <button className="btn btn-success btn-sm" onClick={save} disabled={saving}>
                  {saving?<Spinner/>:'💾 Save'}
                </button>
                <button className="btn btn-ghost btn-sm" onClick={()=>{ setEditing(false); setDraft(value||'') }}>✕</button>
              </>
            ) : (
              <button className="btn btn-outline btn-sm" onClick={()=>setEditing(true)}>✏ Edit</button>
            )}
          </div>
        )}
        {readonly && <span style={{ fontSize:10, padding:'2px 8px', borderRadius:10, background:'var(--bg)', color:'var(--muted)', border:'1px solid var(--border)' }}>read-only</span>}
      </div>

      {editing && !preview ? (
        <textarea
          style={{ width:'100%', minHeight:rows*20, resize:'vertical', borderRadius:8,
            border:'1px solid var(--border)', background:'var(--surface)', color:'var(--text)',
            padding:'10px 12px', fontFamily:'monospace', fontSize:12, lineHeight:1.6, boxSizing:'border-box' }}
          value={draft} onChange={e=>setDraft(e.target.value)} />
      ) : editing && preview ? (
        <div style={{ minHeight:rows*20, padding:'10px 12px', background:'var(--bg)',
          border:'1px solid var(--border)', borderRadius:8 }}>
          <MarkdownPreview content={draft} />
        </div>
      ) : (
        <div style={{ padding:'10px 12px', background:'var(--bg)', borderRadius:8,
          border:'1px solid var(--border)', minHeight:40,
          fontSize:12, lineHeight:1.6, color: draft ? 'var(--text)' : 'var(--muted)',
          fontStyle: draft ? 'normal' : 'italic', whiteSpace:'pre-wrap', maxHeight:200, overflowY:'auto',
          cursor: readonly ? 'default' : 'pointer' }}
          onClick={()=>!readonly&&setEditing(true)}>
          {draft || 'Empty — click Edit to add content'}
        </div>
      )}
    </div>
  )
}

// ── Department section ────────────────────────────────────────────────────────

function DeptSection({ dept, onRefresh }) {
  const [open, setOpen] = useState(false)
  const color = COLORS[dept.id] || '#607D8B'

  return (
    <div className="card" style={{ marginBottom: 16, borderLeft: `3px solid ${color}` }}>
      <div style={{ display:'flex', alignItems:'center', gap:10, cursor:'pointer' }}
        onClick={() => setOpen(o=>!o)}>
        <span style={{ fontSize:18 }}>{open?'▼':'▶'}</span>
        <span style={{ fontSize:14, fontWeight:700 }}>{dept.name}</span>
        <span style={{ fontSize:11, padding:'2px 8px', borderRadius:4, background:color, color:'#fff', fontWeight:700 }}>{dept.code}</span>
        {!dept.system_prompt && (
          <span style={{ fontSize:11, color:'var(--orange)' }}>⚠ No system prompt</span>
        )}
        <span style={{ marginLeft:'auto', fontSize:11, color:'var(--muted)' }}>
          {dept.system_prompt?.length || 0} chars
        </span>
      </div>
      {open && (
        <div style={{ marginTop:16 }}>
          <PromptBox
            {...PROMPT_DESCRIPTIONS.dept_prompt}
            value={dept.system_prompt}
            onSave={async (v) => { await saveDeptPrompt(dept.id, { system_prompt: v }); onRefresh() }}
          />
        </div>
      )}
    </div>
  )
}

// ── Agent section ─────────────────────────────────────────────────────────────

function AgentSection({ agent, onRefresh }) {
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const color = COLORS[agent.dept_id] || '#607D8B'

  const personalityFile = agent.md_files?.find(f => f.category==='personality')
  const toneFiles       = agent.md_files?.filter(f => f.category==='tone') || []
  const skillFiles      = agent.md_files?.filter(f => !['personality','tone'].includes(f.category)) || []

  return (
    <div style={{ marginBottom:8, borderRadius:8, border:'1px solid var(--border)', overflow:'hidden' }}>
      <div style={{ display:'flex', alignItems:'center', gap:10, padding:'10px 14px',
        background:'var(--surface)', cursor:'pointer' }}
        onClick={() => setOpen(o=>!o)}>
        <span style={{ color:'var(--muted)', fontSize:12 }}>{open?'▼':'▶'}</span>
        {agent.is_ceo && <span title="CEO" style={{ fontSize:14 }}>👑</span>}
        <span style={{ fontSize:13, fontWeight:600 }}>{agent.name}</span>
        <span style={{ fontSize:11, color:'var(--muted)' }}>{agent.title||agent.role}</span>
        <span style={{ fontSize:10, padding:'1px 6px', borderRadius:3, background:color, color:'#fff', fontWeight:700 }}>{agent.dept_id}</span>
        <div style={{ marginLeft:'auto', display:'flex', gap:8, alignItems:'center' }}>
          {personalityFile && <span style={{ fontSize:10, color:'var(--green)' }}>🧠 personality</span>}
          {toneFiles.length>0 && <span style={{ fontSize:10, color:'var(--accent)' }}>🎙 tone</span>}
          {skillFiles.length>0 && <span style={{ fontSize:10, color:'var(--muted)' }}>⚡ {skillFiles.length} files</span>}
          <button className="btn btn-ghost btn-sm" style={{ fontSize:11, padding:'1px 8px' }}
            onClick={e=>{ e.stopPropagation(); navigate(`/agents/${agent.id}`) }}>
            Open →
          </button>
        </div>
      </div>
      {open && (
        <div style={{ padding:'14px 14px', borderTop:'1px solid var(--border)' }}>
          <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:20 }}>
            <div>
              <PromptBox
                {...PROMPT_DESCRIPTIONS.agent_personality}
                label="🧠 Personality"
                value={personalityFile?.content || agent.personality || ''}
                readonly
              />
              <PromptBox
                {...PROMPT_DESCRIPTIONS.agent_tone}
                label="🎙 Tone"
                value={toneFiles.map(f=>f.content).join('\n\n---\n\n') || agent.tone || ''}
                readonly
              />
            </div>
            <div>
              <div style={{ fontSize:12, fontWeight:600, color:'var(--muted)', marginBottom:8, textTransform:'uppercase', letterSpacing:'.04em' }}>
                Skills & Knowledge Files
              </div>
              {skillFiles.length === 0 ? (
                <div style={{ fontSize:12, color:'var(--muted)', fontStyle:'italic' }}>No skill files.</div>
              ) : skillFiles.map(f => (
                <div key={f.id} style={{ fontSize:12, padding:'5px 8px', background:'var(--bg)',
                  border:'1px solid var(--border)', borderRadius:5, marginBottom:5 }}>
                  <span style={{ fontWeight:600 }}>📄 {f.filename}</span>
                  <span style={{ marginLeft:8, color:'var(--muted)' }}>[{f.category}]</span>
                  <span style={{ marginLeft:8, color:'var(--muted)' }}>{f.content.length} chars</span>
                </div>
              ))}
              <button className="btn btn-outline btn-sm" style={{ marginTop:8 }}
                onClick={()=>navigate(`/agents/${agent.id}?tab=files`)}>
                Edit Files →
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ── PromptsPage ───────────────────────────────────────────────────────────────

export default function PromptsPage() {
  const { toast }   = useApp()
  const [data,      setData]      = useState(null)
  const [loading,   setLoading]   = useState(true)
  const [section,   setSection]   = useState('global')
  const [deptFilter,setDeptFilter]= useState('')

  const load = useCallback(async () => {
    setLoading(true)
    const [prompts] = await Promise.all([getAllPrompts().catch(()=>null)])
    setData(prompts)
    setLoading(false)
  }, [])

  useEffect(() => { load() }, [load])

  const saveGlobal = async (key, value) => {
    const current = await getSettings()
    await saveSettings({ ...current, [key]: value })
    load()
  }

  if (loading) return <div className="empty"><Spinner lg /></div>
  if (!data)   return <div className="empty">Failed to load prompts.</div>

  const depts  = data.departments || []
  const agents = (data.agents || []).filter(a =>
    !deptFilter || a.dept_id === deptFilter
  )

  return (
    <div>
      <div className="page-header">
        <h2>🔧 Prompt Manager</h2>
        <p>View and edit every prompt in the system. Changes take effect on the next agent heartbeat.</p>
      </div>

      {/* Section tabs */}
      <div className="tabs" style={{ marginBottom: 24 }}>
        {['global','departments','agents'].map(s=>(
          <button key={s} className={`tab${section===s?' active':''}`} onClick={()=>setSection(s)}>
            {{ global:'🌐 Global', departments:'🏛 Departments', agents:'🤖 Agents' }[s]}
          </button>
        ))}
      </div>

      {/* ── GLOBAL ── */}
      {section === 'global' && (
        <div className="card">
          <div style={{ fontSize:12, color:'var(--muted)', marginBottom:20, padding:'10px 12px',
            background:'rgba(88,166,255,.06)', borderRadius:8, border:'1px solid rgba(88,166,255,.15)',
            lineHeight:1.7 }}>
            <strong>Prompt injection order for every agent:</strong><br/>
            <code style={{ fontSize:11 }}>
              Global Prepend → Department Prompt → Agent Personality → Agent Tone → Agent Skill Files → Global Append
            </code>
          </div>

          <PromptBox
            {...PROMPT_DESCRIPTIONS.global_prepend}
            value={data.global_prepend}
            rows={6}
            onSave={v => saveGlobal('custom_prompt_prepend', v)}
          />
          <PromptBox
            {...PROMPT_DESCRIPTIONS.global_append}
            value={data.global_append}
            rows={6}
            onSave={v => saveGlobal('custom_prompt_append', v)}
          />
        </div>
      )}

      {/* ── DEPARTMENTS ── */}
      {section === 'departments' && (
        <div>
          {depts.map(d => <DeptSection key={d.id} dept={d} onRefresh={load} />)}
        </div>
      )}

      {/* ── AGENTS ── */}
      {section === 'agents' && (
        <div>
          <div style={{ display:'flex', gap:8, marginBottom:14, flexWrap:'wrap' }}>
            <button className={`btn btn-sm ${!deptFilter?'btn-primary':'btn-outline'}`}
              onClick={()=>setDeptFilter('')}>All</button>
            {depts.map(d=>(
              <button key={d.id} className={`btn btn-sm ${deptFilter===d.id?'btn-primary':'btn-outline'}`}
                onClick={()=>setDeptFilter(d.id)}
                style={{ borderColor:COLORS[d.id]||'var(--border)' }}>
                {d.code}
              </button>
            ))}
          </div>
          {agents.map(a => <AgentSection key={a.id} agent={a} onRefresh={load} />)}
          {agents.length === 0 && <div className="empty">No agents found.</div>}
        </div>
      )}
    </div>
  )
}
