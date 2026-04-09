import React, { useState, useEffect } from 'react'
import { getSettings, saveSettings, probeOllama, getThinkingLog } from '../../api'
import { useApp } from '../../context/AppContext'
import Spinner from '../../components/UI/Spinner'
import Modal from '../../components/UI/Modal'
import MarkdownPreview from '../../components/Editor/MarkdownPreview'

// ── Prompt template descriptions ──────────────────────────────────────────────
const PROMPT_DOCS = {
  prompt_ceo_authority: {
    label: 'CEO Authority Block',
    desc: 'Injected into every CEO agent\'s system prompt. Defines what they can decide independently vs. what needs Founder approval. Also sets dedup rules and mail discipline.',
    placeholder: '## CEO Authority\nYou lead your department...',
  },
  prompt_agent_role: {
    label: 'Regular Agent Role Block',
    desc: 'Injected into every non-CEO agent\'s prompt. Defines their responsibilities, reporting rules, and tool usage constraints.',
    placeholder: '## Your Role\n- Check existing drafts before creating...',
  },
  prompt_chat_mode: {
    label: 'Chat Mode Instructions',
    desc: 'Added when an agent is in direct conversation with the Founder. Sets tone and expectations for real-time chat with tool use.',
    placeholder: '## Chat Mode\nYou are speaking with the Founder...',
  },
  prompt_tools_spec_header: {
    label: 'Tools Spec Header',
    desc: 'The introductory text shown before the tool table in chat mode. Use to emphasize correct tool selection rules (e.g. hire_agent vs create_draft).',
    placeholder: '## Available Tools\nEmit: [TOOL_CALL: {...}]...',
  },
  prompt_heartbeat_rules: {
    label: 'Heartbeat Rules',
    desc: 'The numbered rules injected before the actions list during automated heartbeats. Controls dedup, mail discipline, tool selection, and hierarchy enforcement.',
    placeholder: '## Heartbeat Rules\n1. MINIMIZE...',
  },
}

function PromptEditor({ fieldKey, value, onChange }) {
  const doc = PROMPT_DOCS[fieldKey]
  const [expanded, setExpanded] = useState(false)
  const [preview,  setPreview]  = useState(false)

  return (
    <div style={{ marginBottom: 20, border: '1px solid var(--border)', borderRadius: 8, overflow: 'hidden' }}>
      <div
        style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 14px',
          background: 'var(--surface)', cursor: 'pointer' }}
        onClick={() => setExpanded(e => !e)}>
        <span style={{ fontSize: 13, fontWeight: 700 }}>{doc.label}</span>
        <span style={{ fontSize: 11, color: 'var(--muted)', flex: 1 }}>{doc.desc.substring(0, 80)}…</span>
        <span style={{ fontSize: 10, color: 'var(--muted)', flexShrink: 0 }}>{value?.length || 0} chars</span>
        <span style={{ color: 'var(--muted)', fontSize: 12 }}>{expanded ? '▲' : '▼'}</span>
      </div>
      {expanded && (
        <div style={{ padding: '10px 14px', background: 'var(--bg)' }}>
          <div style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 8, lineHeight: 1.6 }}>{doc.desc}</div>
          <div style={{ display: 'flex', gap: 6, marginBottom: 6 }}>
            <button className={`btn btn-sm ${!preview ? 'btn-primary' : 'btn-outline'}`}
              onClick={() => setPreview(false)}>✏ Edit</button>
            <button className={`btn btn-sm ${preview ? 'btn-primary' : 'btn-outline'}`}
              onClick={() => setPreview(true)}>👁 Preview</button>
            {value && (
              <button className="btn btn-ghost btn-sm"
                onClick={() => onChange(fieldKey, '')}>
                ↩ Reset to default
              </button>
            )}
          </div>
          {preview ? (
            <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 6, padding: 12, minHeight: 120 }}>
              <MarkdownPreview content={value || doc.placeholder} />
            </div>
          ) : (
            <textarea
              style={{ width: '100%', minHeight: 160, resize: 'vertical', borderRadius: 6,
                border: '1px solid var(--border)', background: 'var(--surface)', color: 'var(--text)',
                padding: '8px 10px', fontFamily: 'monospace', fontSize: 12, lineHeight: 1.6, boxSizing: 'border-box' }}
              value={value || ''}
              placeholder={`Leave blank to use built-in default.\n\n${doc.placeholder}`}
              onChange={e => onChange(fieldKey, e.target.value)}
            />
          )}
          <div style={{ fontSize: 10, color: 'var(--muted)', marginTop: 4 }}>
            Leave blank to use the system default. Changes take effect on the next heartbeat.
          </div>
        </div>
      )}
    </div>
  )
}

export default function Settings() {
  const { toast } = useApp()
  const [s,          setS]         = useState(null)
  const [saving,     setSaving]    = useState(false)
  const [probing,    setProbing]   = useState(false)
  const [probeRes,   setProbeRes]  = useState(null)
  const [thinkOpen,  setThinkOpen] = useState(false)
  const [thinking,   setThinking]  = useState([])
  const [activeTab,  setActiveTab] = useState('ai')

  // AI settings
  const [backend,    setBackend]   = useState('claude')
  const [apiKey,     setApiKey]    = useState('')
  const [cModel,     setCModel]    = useState('claude-sonnet-4-20250514')
  const [oUrl,       setOUrl]      = useState('http://localhost:11434')
  const [oModel,     setOModel]    = useState('llama3')
  const [oTimeout,   setOTimeout]  = useState('120')
  const [verbose,    setVerbose]   = useState(false)
  const [ollamaModels, setOllamaModels] = useState([])

  // Heartbeat
  const [tickSeconds, setTickSeconds] = useState(60)
  const [tickMode,    setTickMode]    = useState('seconds')

  // Global prompts
  const [customP,    setCustomP]   = useState('')
  const [prepend,    setPrepend]   = useState('')
  const [appendP,    setAppendP]   = useState('')

  // Web search
  const [wsEnabled,   setWsEnabled]   = useState(false)
  const [wsProvider,  setWsProvider]  = useState('brave')
  const [wsApiKey,    setWsApiKey]    = useState('')
  const [wsMaxR,      setWsMaxR]      = useState('5')
  const [wsTesting,   setWsTesting]   = useState(false)
  const [wsTestRes,   setWsTestRes]   = useState(null)

  // Prompt templates
  const [promptFields, setPromptFields] = useState({
    prompt_ceo_authority:     '',
    prompt_agent_role:        '',
    prompt_chat_mode:         '',
    prompt_tools_spec_header: '',
    prompt_heartbeat_rules:   '',
  })

  useEffect(() => {
    getSettings().then(d => {
      setS(d)
      setBackend(d.ai_backend||'claude')
      setApiKey(d.claude_api_key||'')
      setCModel(d.claude_model||'claude-sonnet-4-20250514')
      setOUrl(d.ollama_base_url||'http://localhost:11434')
      setOModel(d.ollama_model||'llama3')
      setOTimeout(d.ollama_timeout||'120')
      setCustomP(d.custom_prompt||'')
      setPrepend(d.custom_prompt_prepend||'')
      setAppendP(d.custom_prompt_append||'')
      setVerbose(d.verbose_thinking==='true')
      const tick = Number(d.heartbeat_tick_seconds||60)
      setTickSeconds(tick)
      setTickMode(tick >= 60 ? 'minutes' : 'seconds')
      setWsEnabled(d.web_search_enabled==='true')
      setWsProvider(d.web_search_provider||'brave')
      setWsApiKey(d.web_search_api_key||'')
      setWsMaxR(d.web_search_max_results||'5')
      setPromptFields({
        prompt_ceo_authority:     d.prompt_ceo_authority     || '',
        prompt_agent_role:        d.prompt_agent_role        || '',
        prompt_chat_mode:         d.prompt_chat_mode         || '',
        prompt_tools_spec_header: d.prompt_tools_spec_header || '',
        prompt_heartbeat_rules:   d.prompt_heartbeat_rules   || '',
      })
    })
  }, [])

  const handlePromptChange = (key, val) => {
    setPromptFields(prev => ({ ...prev, [key]: val }))
  }

  const probe = async () => {
    setProbing(true); setProbeRes(null)
    try {
      const d = await probeOllama(oUrl)
      setProbeRes(d)
      if (d.ok && d.models.length) setOllamaModels(d.models)
    } finally { setProbing(false) }
  }

  const testSearch = async () => {
    setWsTesting(true); setWsTestRes(null)
    try {
      const r = await fetch('/api/settings/test-search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider: wsProvider, api_key: wsApiKey }),
      })
      const d = await r.json()
      setWsTestRes(d)
    } catch(e) {
      setWsTestRes({ ok: false, error: e.message })
    }
    setWsTesting(false)
  }

  const save = async () => {
    setSaving(true)
    try {
      await saveSettings({
        ai_backend: backend, claude_api_key: apiKey, claude_model: cModel,
        ollama_base_url: oUrl, ollama_model: oModel, ollama_timeout: oTimeout,
        custom_prompt: customP, custom_prompt_prepend: prepend, custom_prompt_append: appendP,
        verbose_thinking: verbose ? 'true' : 'false',
        heartbeat_tick_seconds: String(tickSeconds),
        web_search_enabled:     wsEnabled ? 'true' : 'false',
        web_search_provider:    wsProvider,
        web_search_api_key:     wsApiKey,
        web_search_max_results: wsMaxR,
        ...promptFields,
      })
      toast('Settings saved ✓')
    } catch(e) { toast(e.message, 'error') }
    setSaving(false)
  }

  const openThinking = async () => {
    const data = await getThinkingLog(50).catch(() => [])
    setThinking(data); setThinkOpen(true)
  }

  if (!s) return <div className="empty"><Spinner/></div>

  const Toggle = ({ on, onChange, labels=['Off','On'] }) => (
    <div className="toggle-wrap">
      <button className={`toggle-opt${!on?' on':''}`} onClick={() => onChange(false)}>{labels[0]}</button>
      <button className={`toggle-opt${on?' on':''}`}  onClick={() => onChange(true)}>{labels[1]}</button>
    </div>
  )

  const TABS = [
    { key: 'ai',      label: '🤖 AI Backend' },
    { key: 'search',  label: '🔍 Web Search' },
    { key: 'prompts', label: '📝 Prompt Templates' },
    { key: 'global',  label: '🌐 Global Prompts' },
    { key: 'timing',  label: '❤ Heartbeat' },
  ]

  return (
    <div>
      <div className="page-header">
        <h2>⚙️ Settings</h2>
        <p>AI backend, web search, editable system prompts, heartbeat timer</p>
      </div>

      {/* Tabs */}
      <div className="tabs" style={{ marginBottom: 20 }}>
        {TABS.map(t => (
          <button key={t.key} className={`tab${activeTab===t.key?' active':''}`}
            onClick={() => setActiveTab(t.key)}>
            {t.label}
          </button>
        ))}
      </div>

      {/* ── AI Backend ── */}
      {activeTab === 'ai' && (
        <>
          <div className="s-section">
            <h3>Backend Selection</h3>
            <div className="s-row">
              <div className="s-info">
                <div className="s-label">Active Backend</div>
                <div className="s-desc"><b>Claude API</b> — cloud, needs API key.<br/><b>Ollama</b> — fully local, offline.</div>
              </div>
              <div className="s-ctrl">
                <Toggle on={backend==='ollama'} onChange={v => setBackend(v?'ollama':'claude')}
                  labels={['🔵 Claude API','🟢 Ollama']} />
              </div>
            </div>
          </div>

          {backend === 'claude' && (
            <div className="s-section">
              <h3>🔵 Claude API</h3>
              <div className="s-row">
                <div className="s-info"><div className="s-label">API Key</div></div>
                <div className="s-ctrl">
                  <input className="s-inp wide" type="password" placeholder="sk-ant-…"
                    value={apiKey} onChange={e => setApiKey(e.target.value)} />
                </div>
              </div>
              <div className="s-row">
                <div className="s-info"><div className="s-label">Model</div></div>
                <div className="s-ctrl">
                  <input className="s-inp wide" list="claude-dl" value={cModel} onChange={e => setCModel(e.target.value)} />
                  <datalist id="claude-dl">
                    {['claude-sonnet-4-20250514','claude-opus-4-5','claude-sonnet-4-5','claude-haiku-4-5',
                      'claude-3-7-sonnet-20250219','claude-3-5-sonnet-20241022','claude-3-5-haiku-20241022'].map(m => <option key={m} value={m}/>)}
                  </datalist>
                </div>
              </div>
            </div>
          )}

          {backend === 'ollama' && (
            <div className="s-section">
              <h3>🟢 Ollama (Local)</h3>
              <div className="s-row">
                <div className="s-info"><div className="s-label">Ollama URL</div></div>
                <div className="s-ctrl">
                  <input className="s-inp" value={oUrl} onChange={e => setOUrl(e.target.value)} />
                  <button className="s-btn" onClick={probe} disabled={probing}>
                    {probing ? <Spinner/> : '🔍 Test'}
                  </button>
                </div>
              </div>
              {probeRes && (
                <div className={`probe-box${probeRes.ok?' probe-ok':' probe-err'}`} style={{ margin:'0 0 8px' }}>
                  {probeRes.ok ? `✓ ${probeRes.models.join(', ')||'none'}` : `✗ ${probeRes.error}`}
                </div>
              )}
              <div className="s-row">
                <div className="s-info"><div className="s-label">Model</div></div>
                <div className="s-ctrl">
                  <input className="s-inp" list="ollama-dl" value={oModel} onChange={e => setOModel(e.target.value)} placeholder="llama3" />
                  <datalist id="ollama-dl">
                    {[...new Set(['llama3','mistral','deepseek-r1:7b','qwq:32b','phi4','gemma3:4b', ...ollamaModels])].map(m => <option key={m} value={m}/>)}
                  </datalist>
                </div>
              </div>
              <div className="s-row">
                <div className="s-info"><div className="s-label">Timeout (seconds)</div></div>
                <div className="s-ctrl">
                  <input className="s-inp" type="number" min={10} max={600} value={oTimeout}
                    onChange={e => setOTimeout(e.target.value)} style={{ width:100 }} />
                </div>
              </div>
            </div>
          )}

          <div className="s-section">
            <h3>🧠 Verbose Thinking</h3>
            <div className="s-row">
              <div className="s-info">
                <div className="s-label">Capture AI Reasoning</div>
                <div className="s-desc">Claude 3.7+/Sonnet4: extended thinking API. Ollama deepseek-r1/qwq: extracts think blocks.</div>
              </div>
              <div className="s-ctrl"><Toggle on={verbose} onChange={setVerbose} /></div>
            </div>
            <div style={{ marginTop:12 }}>
              <button className="s-btn" style={{ color:'var(--accent)', borderColor:'var(--accent)' }} onClick={openThinking}>
                🧠 View Thinking Log
              </button>
            </div>
          </div>
        </>
      )}

      {/* ── Web Search ── */}
      {activeTab === 'search' && (
        <div className="s-section">
          <h3>🔍 Web Search</h3>
          <p style={{ fontSize:12, color:'var(--muted)', marginBottom:16, lineHeight:1.7 }}>
            Agents can call <code>web_search</code> tool during chat or heartbeats to fetch current information.
            Choose a provider and add your API key. DuckDuckGo is always used as a free fallback.
          </p>

          <div className="s-row">
            <div className="s-info">
              <div className="s-label">Enable Web Search</div>
              <div className="s-desc">Agents will see web_search in their tool list and can use it.</div>
            </div>
            <div className="s-ctrl">
              <Toggle on={wsEnabled} onChange={setWsEnabled} />
            </div>
          </div>

          <div className="s-row">
            <div className="s-info">
              <div className="s-label">Provider</div>
              <div className="s-desc">
                <b>Brave</b> — fast, privacy-focused, excellent quality ($3/1k queries)<br/>
                <b>Tavily</b> — AI-optimized with direct answers (1000 free/month)<br/>
                <b>SerpAPI</b> — Google results, most comprehensive ($50/5k queries)<br/>
                <b>DuckDuckGo</b> — free, no API key needed, limited results
              </div>
            </div>
            <div className="s-ctrl">
              <select className="s-inp" value={wsProvider} onChange={e => setWsProvider(e.target.value)}>
                <option value="brave">Brave Search</option>
                <option value="tavily">Tavily</option>
                <option value="serpapi">SerpAPI (Google)</option>
                <option value="duckduckgo">DuckDuckGo (free)</option>
              </select>
            </div>
          </div>

          {wsProvider !== 'duckduckgo' && (
            <div className="s-row">
              <div className="s-info">
                <div className="s-label">API Key</div>
                <div className="s-desc">
                  {wsProvider === 'brave'   && <><a href="https://api.search.brave.com" target="_blank" rel="noreferrer" style={{color:'var(--accent)'}}>Get Brave API key →</a></>}
                  {wsProvider === 'tavily'  && <><a href="https://tavily.com" target="_blank" rel="noreferrer" style={{color:'var(--accent)'}}>Get Tavily API key →</a></>}
                  {wsProvider === 'serpapi' && <><a href="https://serpapi.com" target="_blank" rel="noreferrer" style={{color:'var(--accent)'}}>Get SerpAPI key →</a></>}
                </div>
              </div>
              <div className="s-ctrl">
                <input className="s-inp wide" type="password" placeholder="API key…"
                  value={wsApiKey} onChange={e => setWsApiKey(e.target.value)} />
              </div>
            </div>
          )}

          <div className="s-row">
            <div className="s-info"><div className="s-label">Max Results</div></div>
            <div className="s-ctrl">
              {[3,5,8,10].map(n => (
                <button key={n} className={`btn btn-sm ${wsMaxR===String(n)?'btn-primary':'btn-outline'}`}
                  style={{ marginRight:4 }} onClick={() => setWsMaxR(String(n))}>
                  {n}
                </button>
              ))}
            </div>
          </div>

          {/* Test button */}
          <div style={{ marginTop: 16, display: 'flex', gap: 10, alignItems: 'center' }}>
            <button className="btn btn-outline" onClick={testSearch} disabled={wsTesting}>
              {wsTesting ? <><Spinner/> Testing…</> : '🧪 Test Connection'}
            </button>
          </div>
          {wsTestRes && (
            <div style={{ marginTop: 10, padding: '10px 14px', borderRadius: 8,
              background: wsTestRes.ok ? 'rgba(63,185,80,.08)' : 'rgba(248,81,73,.08)',
              border: `1px solid ${wsTestRes.ok ? 'var(--green)' : 'var(--red)'}` }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: wsTestRes.ok ? 'var(--green)' : 'var(--red)', marginBottom: 6 }}>
                {wsTestRes.ok ? '✓ Connection successful' : '✗ Connection failed'}
              </div>
              {wsTestRes.error && <div style={{ fontSize:11, color:'var(--red)' }}>{wsTestRes.error}</div>}
              {wsTestRes.preview && (
                <pre style={{ fontSize:11, color:'var(--muted)', marginTop:6, whiteSpace:'pre-wrap', wordBreak:'break-word', maxHeight:200, overflowY:'auto' }}>
                  {wsTestRes.preview}
                </pre>
              )}
            </div>
          )}
        </div>
      )}

      {/* ── Prompt Templates ── */}
      {activeTab === 'prompts' && (
        <div>
          <div style={{ fontSize:12, color:'var(--muted)', marginBottom:16, padding:'10px 14px',
            background:'rgba(88,166,255,.06)', borderRadius:8, border:'1px solid rgba(88,166,255,.15)', lineHeight:1.7 }}>
            <strong>How prompt injection works for each agent:</strong><br/>
            <code style={{ fontSize:11 }}>
              Global Prepend → Dept Prompt → Personality → Tone → Skill Files →
              [CEO Authority | Agent Role] → [Tools Spec | Heartbeat Rules] → Global Append
            </code><br/>
            <span style={{ marginTop:6, display:'block' }}>
              All fields below are optional — leave blank to use the system default.
              Changes apply on the next heartbeat cycle.
            </span>
          </div>

          {Object.keys(PROMPT_DOCS).map(key => (
            <PromptEditor
              key={key}
              fieldKey={key}
              value={promptFields[key]}
              onChange={handlePromptChange}
            />
          ))}
        </div>
      )}

      {/* ── Global Prompts ── */}
      {activeTab === 'global' && (
        <div className="s-section">
          <h3>🌐 Global Custom Prompts</h3>
          <p style={{ fontSize:12, color:'var(--muted)', marginBottom:14, lineHeight:1.6 }}>
            These wrap every agent's system prompt.<br/>
            Order: <code>[Prepend]</code> → dept → agent personality → files → role block → tools → <code>[Append]</code>
          </p>

          <div style={{ marginBottom:20 }}>
            <div className="form-label" style={{ marginBottom:6 }}>⬆ Prepend — injected before everything</div>
            <div style={{ fontSize:11, color:'var(--muted)', marginBottom:6 }}>
              Use for: global persona, language, company identity, universal rules that override all departments.
            </div>
            <textarea className="prompt-editor" style={{ minHeight:160, width:'100%' }}
              placeholder="e.g. You are an agent in the NESD Central Think Tank..."
              value={prepend} onChange={e => setPrepend(e.target.value)} />
            <div style={{ fontSize:11, color:'var(--muted)', marginTop:4 }}>{prepend.length} chars</div>
          </div>

          <div>
            <div className="form-label" style={{ marginBottom:6 }}>⬇ Append — injected after everything</div>
            <div style={{ fontSize:11, color:'var(--muted)', marginBottom:6 }}>
              Use for: final output format rules, safety requirements. Evaluated last — overrides earlier instructions.
            </div>
            <textarea className="prompt-editor" style={{ minHeight:120, width:'100%' }}
              placeholder="e.g. Always end with a one-line summary. Never create duplicate drafts."
              value={appendP} onChange={e => setAppendP(e.target.value)} />
            <div style={{ fontSize:11, color:'var(--muted)', marginTop:4 }}>{appendP.length} chars</div>
          </div>

          <details style={{ marginTop:16 }}>
            <summary style={{ fontSize:12, color:'var(--muted)', cursor:'pointer' }}>
              Legacy single prompt (deprecated)
            </summary>
            <textarea className="form-control" rows={3} style={{ marginTop:8, fontFamily:'monospace', fontSize:12 }}
              value={customP} onChange={e => setCustomP(e.target.value)} />
          </details>
        </div>
      )}

      {/* ── Heartbeat ── */}
      {activeTab === 'timing' && (
        <div className="s-section">
          <h3>❤ Heartbeat Timer</h3>
          <p style={{ fontSize:12, color:'var(--muted)', marginBottom:14 }}>
            How often the scheduler checks for agents due to run. Agents run every N ticks (configurable per-agent on their profile page).
          </p>
          <div className="s-row">
            <div className="s-info">
              <div className="s-label">Tick Interval</div>
              <div className="s-desc">Currently: <strong>
                {tickMode==='minutes' ? `${Math.round(tickSeconds/60)}m` : `${tickSeconds}s`}
              </strong></div>
            </div>
            <div className="s-ctrl" style={{ flexDirection:'column', gap:10, alignItems:'flex-start' }}>
              <div className="toggle-wrap">
                <button className={`toggle-opt${tickMode==='seconds'?' on':''}`} onClick={() => setTickMode('seconds')}>Seconds</button>
                <button className={`toggle-opt${tickMode==='minutes'?' on':''}`} onClick={() => setTickMode('minutes')}>Minutes</button>
              </div>
              <div style={{ display:'flex', alignItems:'center', gap:10 }}>
                <input type="range"
                  min={tickMode==='seconds' ? 5 : 1}
                  max={tickMode==='seconds' ? 300 : 60}
                  value={tickMode==='seconds' ? tickSeconds : Math.round(tickSeconds/60)}
                  onChange={e => setTickSeconds(tickMode==='seconds' ? Number(e.target.value) : Number(e.target.value)*60)}
                  style={{ width:200, accentColor:'var(--accent)' }} />
                <input type="number" className="form-control"
                  value={tickMode==='seconds' ? tickSeconds : Math.round(tickSeconds/60)}
                  onChange={e => setTickSeconds(tickMode==='seconds' ? Number(e.target.value) : Number(e.target.value)*60)}
                  style={{ width:80 }} />
                <span style={{ fontSize:12, color:'var(--muted)' }}>{tickMode}</span>
              </div>
              <div style={{ fontSize:11, color:'var(--muted)' }}>
                Presets: {[5,10,30,60,120,300].map(s => (
                  <button key={s} className={`btn btn-sm ${tickSeconds===s?'btn-primary':'btn-outline'}`}
                    style={{ marginRight:4 }} onClick={() => { setTickSeconds(s); setTickMode('seconds') }}>
                    {s >= 60 ? `${s/60}m` : `${s}s`}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Save button */}
      <div style={{ display:'flex', gap:12, alignItems:'center', marginTop: 24 }}>
        <button className="btn btn-primary" onClick={save} disabled={saving}>
          {saving ? <><Spinner/> Saving…</> : '💾 Save All Settings'}
        </button>
      </div>

      {/* Thinking log modal */}
      <Modal open={thinkOpen} onClose={() => setThinkOpen(false)} wide>
        <h3 style={{ marginBottom:16 }}>🧠 AI Thinking Log</h3>
        {thinking.length === 0
          ? <div className="empty">No thinking captured.</div>
          : thinking.map((e, i) => {
              const m = e.meta_parsed || {}
              return (
                <div key={i} style={{ background:'var(--bg)', border:'1px solid var(--border)', borderRadius:8, padding:14, marginBottom:10 }}>
                  <div style={{ display:'flex', gap:8, alignItems:'center', marginBottom:8 }}>
                    <span style={{ fontSize:11, fontWeight:700, color:'var(--accent)', background:'rgba(88,166,255,.1)', padding:'2px 8px', borderRadius:4 }}>{m.backend||'?'}</span>
                    {e.dept_id && <span style={{ fontSize:11, fontWeight:700 }}>[{e.dept_id}]</span>}
                    <span style={{ marginLeft:'auto', fontSize:11, color:'var(--muted)' }}>{e.created_at?.substring(0,16).replace('T',' ')}</span>
                  </div>
                  <div style={{ fontSize:12, lineHeight:1.7, color:'var(--muted)', whiteSpace:'pre-wrap', maxHeight:200, overflowY:'auto', fontStyle:'italic' }}>
                    {m.thinking||'(no thinking text)'}
                  </div>
                </div>
              )
            })
        }
        <button className="btn btn-ghost" style={{ marginTop:8 }} onClick={() => setThinkOpen(false)}>Close</button>
      </Modal>
    </div>
  )
}