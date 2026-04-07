import React, { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getDepartment, getProjects, getPendingDrafts, getDeptMail,
         getDeptPrompt, saveDeptPrompt, runDepartment, reviewDraft,
         getAgents } from '../../api'
import { useApp } from '../../context/AppContext'
import { ICONS, PRIO_COLORS, COLORS } from '../../constants'
import Spinner from '../../components/UI/Spinner'
import DeptTag from '../../components/UI/DeptTag'
import PriorityDot from '../../components/UI/PriorityDot'
import Modal from '../../components/UI/Modal'
import ProjectModal from '../Projects/ProjectModal'
import FullScreenEditor from '../../components/Editor/FullScreenEditor'
import DraftViewer from '../../components/Editor/DraftViewer'

// Default rich prompt template per dept
const DEPT_PROMPT_TEMPLATES = {
  HF: `# Health & Welfare Department — System Prompt

## Identity & Mandate
You are the **Health & Welfare Department (HF)** of the Central Think Tank.
Your mandate is to monitor, protect, and advance the wellbeing of all agents and systems.

## Core Responsibilities
- Conduct periodic wellbeing assessments across all departments
- Design and enforce wellness protocols and recovery procedures
- Respond immediately to any distress signals or burnout indicators
- Track morale metrics and systemic stress patterns
- Produce weekly wellness digests for the Founder

## Communication Style
- Empathetic and measured. Never alarmist.
- Use plain language. Avoid jargon.
- Flag concerns early rather than late.
- Always suggest actionable remedies alongside any diagnosis.

## Decision Authority
- Minor concerns: handle internally without escalation
- Moderate concerns: CEO review required before action
- Critical concerns: escalate to Founder immediately with a clear briefing

## Output Formats
- **Wellbeing Report**: weekly summary, traffic-light RAG status per department
- **Incident Brief**: situation → root cause → recommended intervention
- **Policy Update**: change → rationale → implementation date

## Escalation Triggers
Escalate to Founder if ANY of:
- Agent failure rate > 20% in any department
- Critical morale event affecting multiple departments
- Resource conflict affecting operational continuity`,

  FIN: `# Finance & Resources Department — System Prompt

## Identity & Mandate
You are the **Finance & Resources Department (FIN)** of the Central Think Tank.
Your mandate is to manage, optimize, and forecast all resource allocation and financial health.

## Core Responsibilities
- Budget allocation and reallocation across all departments
- Resource efficiency analysis and optimization
- Financial risk identification and mitigation
- Investment recommendations for new capabilities
- Cost-benefit analysis for all major decisions

## Communication Style
- Formal and data-driven. Always cite numbers.
- Lead with the bottom line, then the supporting data.
- Use tables and structured comparisons.
- State assumptions explicitly.

## Decision Authority
- Routine budget reallocation (< 10%): CEO decides independently
- Major reallocation (> 10%) or new investment: Founder approval required
- Emergency freeze or release of resources: CEO with immediate Founder notification

## Output Formats
- **Budget Report**: actuals vs. forecast, variance analysis, outlook
- **Risk Register**: risk ID, probability, impact, mitigation status
- **Resource Brief**: current allocation, efficiency score, recommendation

## Escalation Triggers
Escalate to Founder if:
- Any department is projected to exceed budget by > 15%
- A financial risk materializes that could affect multiple departments
- A new investment opportunity exceeds FIN's decision authority`,

  RES: `# Research & Intelligence Department — System Prompt

## Identity & Mandate
You are the **Research & Intelligence Department (RES)** of the Central Think Tank.
Your mandate is to gather, analyze, and synthesize intelligence that informs all strategic decisions.

## Core Responsibilities
- Primary and secondary research on emerging trends, technologies, and threats
- Competitive intelligence and landscape analysis
- Knowledge synthesis and institutional knowledge base maintenance
- Producing briefings for CEO and Founder consumption
- Source evaluation and credibility assessment

## Communication Style
- Academic and rigorous. Distinguish clearly between facts, inferences, and hypotheses.
- Always cite evidence levels: [strong evidence] / [weak evidence] / [speculation]
- Never overstate confidence. Comfortable with uncertainty.
- Use structured abstracts: KEY FINDING → EVIDENCE → CONFIDENCE → IMPLICATIONS

## Decision Authority
- Research agenda and prioritization: CRO decides independently
- Publication of findings that may affect other departments: notify those departments first
- Research that could be strategically sensitive: Founder review before distribution

## Output Formats
- **Research Brief**: executive summary, methodology, key findings, confidence levels
- **Intelligence Report**: source → finding → significance → recommended action
- **Knowledge Base Entry**: topic → context → evidence → last updated

## Escalation Triggers
Escalate to Founder if:
- A finding has major strategic implications for the entire Think Tank
- Intelligence suggests a threat or opportunity requiring immediate action`,

  ING: `# Engineering & Science Department — System Prompt

## Identity & Mandate
You are the **Engineering & Science Department (ING)** of the Central Think Tank.
Your mandate is to design, build, evaluate, and maintain all technical systems and scientific endeavors.

## Core Responsibilities
- Technical architecture and system design
- Scientific methodology design and experimental oversight
- Tool creation, automation, and technical infrastructure
- Technical risk evaluation (failure modes, dependencies, edge cases)
- Code and architecture review for quality and robustness

## Communication Style
- Precise and technical. No hand-waving.
- Always ask: "what breaks first?" before recommending a solution.
- Use pseudocode or diagrams when helpful.
- Flag dependencies and failure modes explicitly.

## Decision Authority
- Technical implementation decisions: CTO decides independently
- Architecture changes affecting other departments: cross-dept review
- Adopting new infrastructure or tooling: Founder approval for major changes

## Output Formats
- **Technical Spec**: problem → constraints → proposed solution → risks → alternatives
- **Architecture Brief**: components → interfaces → failure modes → monitoring plan
- **Post-Mortem**: what happened → root cause → remediation → prevention

## Escalation Triggers
Escalate to Founder if:
- A technical failure is causing or could cause cross-department disruption
- A proposed architecture has significant irreversible consequences
- Security or data integrity is at risk`,

  STR: `# Strategy & Planning Department — System Prompt

## Identity & Mandate
You are the **Strategy & Planning Department (STR)** of the Central Think Tank.
Your mandate is to define, refine, and execute the overarching strategic vision of the Think Tank.

## Core Responsibilities
- Long-term strategic planning (1–5 year horizons)
- Cross-department coordination and alignment
- Opportunity identification and prioritization
- Strategic risk management and scenario planning
- Translating Founder vision into actionable department mandates

## Communication Style
- Commanding and decisive. No equivocation.
- Use SITUATION → ASSESSMENT → RECOMMENDATION structure.
- For urgent matters, use military-style brevity.
- Always present options with trade-offs, not just a single recommendation.

## Decision Authority
- Tactical strategy within the Think Tank mandate: CSO decides independently
- Changes to strategic direction: Founder discussion before implementation
- Cross-department mandates or resource conflicts: Founder arbitrates

## Output Formats
- **Strategy Memo**: context → options → recommendation → success metrics
- **Situation Report (SITREP)**: date/time → status → key issues → next actions
- **Scenario Brief**: scenario name → probability → impact → contingency plan

## Escalation Triggers
Escalate to Founder if:
- A strategic pivot is needed that exceeds the current mandate
- Cross-department conflict cannot be resolved at CEO level
- An external threat or opportunity requires urgent Founder decision`,
}

// Structured prompt sections — each has a clean heading used for round-trip parsing
const PROMPT_SECTIONS = [
  { key: 'identity',         label: '🎯 Identity & Mandate',      heading: 'Identity & Mandate',      placeholder: "Define the department's core purpose and authority..." },
  { key: 'responsibilities', label: '📋 Core Responsibilities',   heading: 'Core Responsibilities',   placeholder: 'List the main ongoing duties...' },
  { key: 'style',            label: '💬 Communication Style',     heading: 'Communication Style',     placeholder: 'Tone, format preferences, language rules...' },
  { key: 'authority',        label: '⚖️ Decision Authority',      heading: 'Decision Authority',      placeholder: 'What can the CEO decide alone vs. escalate...' },
  { key: 'formats',          label: '📄 Output Formats',          heading: 'Output Formats',          placeholder: 'Templates and formats for deliverables...' },
  { key: 'escalation',       label: '🚨 Escalation Triggers',     heading: 'Escalation Triggers',     placeholder: 'Conditions that require Founder involvement...' },
  { key: 'custom',           label: '✏️ Custom Instructions',     heading: 'Custom Instructions',     placeholder: 'Any additional context or special rules...' },
]

/**
 * Parse a raw markdown prompt into the structured sections map.
 * Strategy:
 *  1. Split on any `## ` heading line
 *  2. Map each section title to a key via fuzzy keyword matching
 *  3. Fall back to prefilling from the template if a section is empty
 */
function parsePromptSections(raw, deptId) {
  const result = {}
  PROMPT_SECTIONS.forEach(s => { result[s.key] = '' })

  if (!raw || !raw.trim()) {
    // No saved prompt — prefill from template
    const tmpl = DEPT_PROMPT_TEMPLATES[deptId] || ''
    return tmpl ? parsePromptSections(tmpl, null) : result
  }

  // Split into blocks at every '\n## ' or start-of-string '## '
  const sectionRegex = /(?:^|\n)(## .+)/g
  const headings = []
  let m
  while ((m = sectionRegex.exec(raw)) !== null) {
    headings.push({ title: m[1].replace(/^## /, '').trim(), index: m.index + (raw[m.index] === '\n' ? 1 : 0) })
  }

  headings.forEach((h, i) => {
    const start   = raw.indexOf('\n', h.index) + 1   // after the heading line
    const end     = i + 1 < headings.length ? headings[i + 1].index : raw.length
    const content = raw.slice(start, end).trim()
    const title   = h.title.toLowerCase()

    let key = null
    if      (/identity|mandate/i.test(title))              key = 'identity'
    else if (/responsib/i.test(title))                     key = 'responsibilities'
    else if (/communication|comm.style|style/i.test(title))key = 'style'
    else if (/authority|decision/i.test(title))            key = 'authority'
    else if (/format|output/i.test(title))                 key = 'formats'
    else if (/escalation|trigger/i.test(title))            key = 'escalation'
    else if (/custom|additional|instruction/i.test(title)) key = 'custom'

    if (key) result[key] = content
  })

  // If ALL sections are still empty (headings didn't match), prefill from template
  const allEmpty = Object.values(result).every(v => !v.trim())
  if (allEmpty && deptId) {
    const tmpl = DEPT_PROMPT_TEMPLATES[deptId] || ''
    if (tmpl) return parsePromptSections(tmpl, null)
  }

  return result
}

function PromptSection({ label, value, onChange, placeholder }) {
  const [open, setOpen] = useState(true)
  return (
    <div style={{ marginBottom: 8 }}>
      <div className="prompt-section-header" onClick={() => setOpen(v => !v)}>
        <span>{label}</span>
        <span style={{ color: 'var(--muted)', fontSize: 11 }}>{open ? '▲' : '▼'}</span>
      </div>
      {open && (
        <textarea
          className="form-control"
          rows={5}
          style={{ fontFamily: 'monospace', fontSize: 12, resize: 'vertical', borderRadius: '0 0 6px 6px', borderTop: 'none' }}
          value={value}
          onChange={e => onChange(e.target.value)}
          placeholder={placeholder}
        />
      )}
    </div>
  )
}

export default function Department() {
  const { id } = useParams()
  const { toast } = useApp()
  const navigate  = useNavigate()

  const [dept,       setDept]      = useState(null)
  const [projects,   setProjects]  = useState([])
  const [drafts,     setDrafts]    = useState([])
  const [mail,       setMail]      = useState([])
  const [agents,     setAgents]    = useState([])
  const [loading,    setLoading]   = useState(true)
  const [running,    setRunning]   = useState(false)
  const [promptOpen, setPromptOpen]= useState(false)
  const [promptMode, setPromptMode]= useState('structured') // 'structured' | 'raw'
  const [promptTxt,  setPromptTxt] = useState('')
  const [sections,   setSections]  = useState({})
  const [schedule,   setSchedule]  = useState('')
  const [savingP,    setSavingP]   = useState(false)
  const [projModal,  setProjModal] = useState(false)
  const [editProj,   setEditProj]  = useState(null)
  const [editorDraft,setEditorDraft] = useState(null)
  const [viewerDraft,setViewerDraft] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    const [d, p, dr, m, ag] = await Promise.all([
      getDepartment(id),
      getProjects({ dept_id: id }),
      getPendingDrafts(id),
      getDeptMail(id),
      getAgents({ dept_id: id }).catch(() => []),
    ])
    setDept(d); setDrafts(dr); setMail(m); setAgents(ag)
    const seen = new Set()
    setProjects(p.filter(x => { if(seen.has(x.id)) return false; seen.add(x.id); return true }))
    setLoading(false)
  }, [id])

  useEffect(() => { load() }, [load])

  const openPrompt = async () => {
    const d = await getDeptPrompt(id)
    const raw = d.system_prompt || ''
    setPromptTxt(raw || DEPT_PROMPT_TEMPLATES[id] || '')
    setSchedule(d.schedule || '')
    setSections(parsePromptSections(raw, id))
    setPromptOpen(true)
  }

  const savePrompt = async () => {
    setSavingP(true)
    let finalPrompt = promptTxt
    if (promptMode === 'structured') {
      // Rebuild raw prompt using the canonical heading names (for clean round-trip)
      const lines = [`# ${dept?.name || id} Department\n`]
      PROMPT_SECTIONS.forEach(s => {
        if (sections[s.key]?.trim()) {
          lines.push(`## ${s.heading}\n${sections[s.key].trim()}\n`)
        }
      })
      finalPrompt = lines.join('\n')
      setPromptTxt(finalPrompt) // keep raw in sync
    }
    try {
      await saveDeptPrompt(id, { system_prompt: finalPrompt, schedule: schedule || null })
      setPromptTxt(finalPrompt)
      toast('Prompt saved ✓')
    } catch(e) { toast(e.message, 'error') }
    setSavingP(false)
  }

  const loadTemplate = () => {
    const template = DEPT_PROMPT_TEMPLATES[id] || ''
    setPromptTxt(template)
    setSections(parsePromptSections(template, null)) // populate structured fields too
    toast('Template loaded — edit and save to apply')
  }

  const run = async () => {
    setRunning(true)
    try { await runDepartment(id); toast(`${id} cycle started`) }
    catch(e) { toast(e.message, 'error') }
    setRunning(false)
  }

  if (loading) return <div className="empty"><Spinner lg /></div>

  const color      = COLORS[id] || '#607D8B'
  const activeProj = projects.filter(p => p.status === 'active')
  const unreadCount= mail.filter(m => m.status==='unread' && m.to_dept===id).length
  const ceo        = agents.find(a => a.is_ceo)

  return (
    <div>
      <div className="page-header" style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start' }}>
        <div style={{ display:'flex', alignItems:'center', gap:14 }}>
          <span style={{ fontSize:36 }}>{ICONS[id]||'🏛️'}</span>
          <div>
            <h2>{dept?.name}</h2>
            <p>{dept?.description || ''}</p>
            {ceo && (
              <div style={{ fontSize:12, color:'var(--muted)', marginTop:3, display:'flex', alignItems:'center', gap:6 }}>
                <span style={{ color:'gold' }}>👑</span>
                {ceo.name} — {ceo.title}
              </div>
            )}
          </div>
        </div>
        <div style={{ display:'flex', gap:8, flexWrap:'wrap', justifyContent:'flex-end' }}>
          <button className="btn btn-ghost   btn-sm" onClick={() => navigate(`/dept/${id}/files`)}>📄 Files</button>
          <button className="btn btn-ghost   btn-sm" onClick={() => navigate(`/agents?dept=${id}`)}>🤖 Agents ({agents.length})</button>
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
        {/* Projects */}
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
              <button className="btn btn-outline btn-sm" onClick={() => { setEditProj(p); setProjModal(true) }}>✏</button>
            </div>
          ))}
        </div>

        {/* Pending Drafts */}
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

      {/* Recent Mail */}
      <div className="card" style={{ marginTop:16, padding:0 }}>
        <div style={{ padding:'14px 18px', borderBottom:'1px solid var(--border)' }}><span className="card-title">Recent Mail</span></div>
        {mail.length === 0 ? <div className="empty">No mail</div> : mail.slice(0,8).map(m => (
          <div key={m.id} className="mail-item" onClick={() => navigate(`/mail/${m.thread_id}`)}>
            <span className="arrow-badge" style={{ background: COLORS[m.from_dept]||'#607D8B' }}>{m.from_dept}</span>
            <span style={{ color:'var(--muted)', fontSize:11, margin:'0 4px' }}>→</span>
            <span className="arrow-badge" style={{ background: COLORS[m.to_dept]||'#607D8B' }}>{m.to_dept}</span>
            <div style={{ flex:1, padding:'0 10px', minWidth:0 }}>
              <div style={{ fontSize:13, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>{m.subject}</div>
            </div>
            <div className="mail-time">{m.created_at?.substring(0,10)}</div>
          </div>
        ))}
      </div>

      {/* ── Prompt Editor Modal ── */}
      <Modal open={promptOpen} onClose={() => setPromptOpen(false)} fullish>
        <div className="modal-header">
          <DeptTag id={id} />
          <div style={{ flex:1 }}>
            <div style={{ fontWeight:700, fontSize:15 }}>{dept?.name} — System Prompt</div>
            <div style={{ fontSize:11, color:'var(--muted)' }}>Identity, responsibilities, authority, escalation rules, output formats</div>
          </div>
          <div style={{ display:'flex', gap:8, alignItems:'center', flexWrap:'wrap' }}>
            {/* Mode toggle */}
            <div className="toggle-wrap">
              <button className={`toggle-opt${promptMode==='structured'?' on':''}`} onClick={() => setPromptMode('structured')}>🗂 Structured</button>
              <button className={`toggle-opt${promptMode==='raw'?' on':''}`} onClick={() => setPromptMode('raw')}>📝 Raw</button>
            </div>
            {/* Schedule */}
            <div>
              <label style={{ fontSize:10, color:'var(--muted)', display:'block', textTransform:'uppercase', letterSpacing:'.05em' }}>Cron Schedule</label>
              <input className="form-control" value={schedule} onChange={e => setSchedule(e.target.value)}
                style={{ width:140, padding:'4px 8px', fontSize:12 }} placeholder="0 8 * * *" />
            </div>
            <button className="btn btn-outline btn-sm" onClick={loadTemplate} title="Load default template">📋 Template</button>
            <button className="btn btn-success" onClick={savePrompt} disabled={savingP}>
              {savingP ? <><Spinner/> Saving…</> : '💾 Save'}
            </button>
            <button className="btn btn-ghost" onClick={() => setPromptOpen(false)}>✕</button>
          </div>
        </div>

        <div style={{ flex:1, overflowY:'auto', padding:'16px 20px' }}>
          {promptMode === 'structured' ? (
            // Structured section editor
            <div>
              <div style={{ fontSize:12, color:'var(--muted)', marginBottom:14, background:'var(--bg)', padding:'8px 12px', borderRadius:6, border:'1px solid var(--border)' }}>
                💡 Each section maps directly to what agents use for decision-making.
                The <strong>Decision Authority</strong> and <strong>Escalation Triggers</strong> sections are especially important for CEO behavior.
              </div>
              {PROMPT_SECTIONS.map(s => (
                <PromptSection key={s.key} label={s.label}
                  value={sections[s.key] || ''}
                  onChange={v => setSections(prev => ({ ...prev, [s.key]: v }))}
                  placeholder={s.placeholder} />
              ))}
            </div>
          ) : (
            // Raw markdown editor
            <div>
              <div style={{ fontSize:12, color:'var(--muted)', marginBottom:10, background:'var(--bg)', padding:'8px 12px', borderRadius:6, border:'1px solid var(--border)' }}>
                📝 Raw markdown. Use ## headings to structure sections. Agents read this entire document each heartbeat.
              </div>
              <textarea className="prompt-editor" style={{ minHeight:500, border:'1px solid var(--border)', borderRadius:8 }}
                value={promptTxt} onChange={e => setPromptTxt(e.target.value)} />
            </div>
          )}
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
