import React, { useState, useEffect } from 'react'
import { getSettings, saveSettings, probeOllama, getThinkingLog } from '../../api'
import { useApp } from '../../context/AppContext'
import Spinner from '../../components/UI/Spinner'
import Modal from '../../components/UI/Modal'
import MarkdownPreview from '../../components/Editor/MarkdownPreview'

export default function Settings() {
  const { toast } = useApp()
  const [s,          setS]         = useState(null)
  const [saving,     setSaving]    = useState(false)
  const [probing,    setProbing]   = useState(false)
  const [probeRes,   setProbeRes]  = useState(null)
  const [thinkOpen,  setThinkOpen] = useState(false)
  const [thinking,   setThinking]  = useState([])
  const [backend,    setBackend]   = useState('claude')
  const [apiKey,     setApiKey]    = useState('')
  const [cModel,     setCModel]    = useState('claude-sonnet-4-20250514')
  const [oUrl,       setOUrl]      = useState('http://localhost:11434')
  const [oModel,     setOModel]    = useState('llama3')
  const [oTimeout,   setOTimeout]  = useState('120')
  const [customP,    setCustomP]   = useState('')
  const [prepend,    setPrepend]   = useState('')
  const [appendP,    setAppendP]   = useState('')
  const [verbose,    setVerbose]   = useState(false)
  const [ollamaModels, setOllamaModels] = useState([])
  // Heartbeat timer
  const [tickSeconds,  setTickSeconds]  = useState(60)
  const [tickMode,     setTickMode]     = useState('seconds') // 'seconds' | 'minutes'

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
    })
  }, [])

  const probe = async () => {
    setProbing(true); setProbeRes(null)
    try {
      const d = await probeOllama(oUrl)
      setProbeRes(d)
      if (d.ok && d.models.length) setOllamaModels(d.models)
    } finally { setProbing(false) }
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

  const tickDisplay = tickMode === 'minutes'
    ? `${Math.round(tickSeconds / 60)} minute${Math.round(tickSeconds/60)!==1?'s':''}`
    : `${tickSeconds} second${tickSeconds!==1?'s':''}`

  return (
    <div>
      <div className="page-header"><h2>⚙️ Settings</h2><p>AI backend, models, global prompts, heartbeat timer</p></div>

      {/* Active backend indicator */}
      <div className="s-section">
        <h3>Active Configuration</h3>
        <div className="s-row">
          <div className="s-info"><div className="s-label">Current backend</div><div className="s-desc">All agent cycles use this setting.</div></div>
          <div className="s-ctrl">
            <span className={`backend-ind ${backend==='ollama'?'bi-ollama':'bi-claude'}`}>
              {backend==='ollama' ? '🟢 Ollama (local)' : '🔵 Claude API'}
            </span>
          </div>
        </div>
      </div>

      {/* Backend toggle */}
      <div className="s-section">
        <h3>🤖 Backend</h3>
        <div className="s-row">
          <div className="s-info">
            <div className="s-label">Select Backend</div>
            <div className="s-desc">
              <b>Claude API</b> — cloud, needs API key.<br/>
              <b>Ollama</b> — fully local, offline. No fallback.
            </div>
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
                  'claude-3-7-sonnet-20250219','claude-3-5-sonnet-20241022','claude-3-5-haiku-20241022',
                  'claude-3-opus-20240229'].map(m => <option key={m} value={m}/>)}
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
              {probeRes.ok ? `✓ Connected — ${probeRes.models.join(', ')||'none'}` : `✗ ${probeRes.error}`}
            </div>
          )}
          <div className="s-row">
            <div className="s-info"><div className="s-label">Model</div></div>
            <div className="s-ctrl">
              <input className="s-inp" list="ollama-dl" value={oModel} onChange={e => setOModel(e.target.value)} placeholder="e.g. llama3" />
              <datalist id="ollama-dl">
                {[...new Set(['llama3','llama3.2:3b','mistral','deepseek-r1:7b','deepseek-r1:14b',
                  'qwq:32b','phi4','gemma3:4b','qwen2.5:7b', ...ollamaModels])].map(m => <option key={m} value={m}/>)}
              </datalist>
            </div>
          </div>
          <div className="s-row">
            <div className="s-info"><div className="s-label">Timeout (seconds)</div></div>
            <div className="s-ctrl">
              <input className="s-inp" type="number" min={10} max={600}
                value={oTimeout} onChange={e => setOTimeout(e.target.value)} style={{ width:100 }} />
            </div>
          </div>
        </div>
      )}

      {/* ── Heartbeat Timer ── */}
      <div className="s-section">
        <h3>❤ Heartbeat Timer</h3>
        <p style={{ fontSize:12, color:'var(--muted)', marginBottom:14 }}>
          How often the scheduler checks for agents due to run. Agents run every N ticks
          (set per-agent on their profile page).
        </p>
        <div className="s-row">
          <div className="s-info">
            <div className="s-label">Tick Interval</div>
            <div className="s-desc">Currently: <strong>{tickDisplay}</strong></div>
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
                min={tickMode==='seconds' ? 5 : 1}
                max={tickMode==='seconds' ? 3600 : 1440}
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

      {/* ── Global Prompts ── */}
      <div className="s-section">
        <h3>📝 Global Custom Prompts</h3>
        <p style={{ fontSize:12, color:'var(--muted)', marginBottom:14, lineHeight:1.6 }}>
          These wrap every agent's system prompt.<br/>
          Order: <code>[Prepend]</code> → dept prompt → agent personality → agent files → <code>[Append]</code>
        </p>

        {/* Prepend */}
        <div style={{ marginBottom:20 }}>
          <div className="form-label" style={{ marginBottom:6 }}>⬆ Prepend (injected before everything)</div>
          <div style={{ fontSize:11, color:'var(--muted)', marginBottom:6 }}>
            Use for: global persona, language preferences, Think Tank context, rules that override all departments.
          </div>
          <textarea
            className="prompt-editor"
            style={{ minHeight:160, width:'100%' }}
            placeholder={`e.g.\nYou are an agent in the NESD Central Think Tank, a highly disciplined autonomous organization.\nLanguage: English. Timezone: UTC+1 (Morocco).\nFounder: Younes — mechanical engineer, decisive, values brevity.`}
            value={prepend}
            onChange={e => setPrepend(e.target.value)}
          />
          <div style={{ fontSize:11, color:'var(--muted)', marginTop:4 }}>{prepend.length} chars</div>
        </div>

        {/* Append */}
        <div>
          <div className="form-label" style={{ marginBottom:6 }}>⬇ Append (injected after everything)</div>
          <div style={{ fontSize:11, color:'var(--muted)', marginBottom:6 }}>
            Use for: final instructions, formatting requirements, safety rules, output format enforcement.
          </div>
          <textarea
            className="prompt-editor"
            style={{ minHeight:120, width:'100%' }}
            placeholder={`e.g.\nAlways end your response with a one-line summary.\nNever create duplicate drafts. Check existing ones first.\nUse military format for urgent messages.`}
            value={appendP}
            onChange={e => setAppendP(e.target.value)}
          />
          <div style={{ fontSize:11, color:'var(--muted)', marginTop:4 }}>{appendP.length} chars</div>
        </div>

        {/* Legacy single custom prompt */}
        <details style={{ marginTop:16 }}>
          <summary style={{ fontSize:12, color:'var(--muted)', cursor:'pointer' }}>
            Legacy: single custom prompt (deprecated — use prepend/append above)
          </summary>
          <textarea
            className="form-control"
            rows={3}
            style={{ marginTop:8, fontFamily:'monospace', fontSize:12 }}
            placeholder="Added to all system prompts (legacy field)"
            value={customP}
            onChange={e => setCustomP(e.target.value)}
          />
        </details>
      </div>

      {/* Verbose Thinking */}
      <div className="s-section">
        <h3>🧠 Verbose Thinking</h3>
        <div className="s-row">
          <div className="s-info">
            <div className="s-label">Capture AI Reasoning</div>
            <div className="s-desc">
              Claude 3.7+/Sonnet4: extended thinking API.<br/>
              Ollama deepseek-r1/qwq: extracts &lt;think&gt; blocks.
            </div>
          </div>
          <div className="s-ctrl"><Toggle on={verbose} onChange={setVerbose} /></div>
        </div>
        <div style={{ marginTop:12 }}>
          <button className="s-btn" style={{ color:'var(--accent)', borderColor:'var(--accent)' }} onClick={openThinking}>
            🧠 View Thinking Log
          </button>
        </div>
      </div>

      <div style={{ display:'flex', gap:12, alignItems:'center' }}>
        <button className="btn btn-primary" onClick={save} disabled={saving}>
          {saving ? <><Spinner/> Saving…</> : '💾 Save Settings'}
        </button>
      </div>

      {/* Thinking log modal */}
      <Modal open={thinkOpen} onClose={() => setThinkOpen(false)} wide>
        <h3 style={{ marginBottom:16 }}>🧠 AI Thinking Log</h3>
        {thinking.length === 0
          ? <div className="empty">No thinking captured. Enable Verbose Thinking and run a cycle.</div>
          : thinking.map((e, i) => {
            const m = e.meta_parsed || {}
            return (
              <div key={i} style={{ background:'var(--bg)', border:'1px solid var(--border)', borderRadius:8, padding:14, marginBottom:10 }}>
                <div style={{ display:'flex', gap:8, alignItems:'center', marginBottom:8 }}>
                  <span style={{ fontSize:11, fontWeight:700, color:'var(--accent)', background:'rgba(88,166,255,.1)', padding:'2px 8px', borderRadius:4 }}>{m.backend||'?'}</span>
                  {e.dept_id && <span style={{ fontSize:11, fontWeight:700, color:'#607D8B' }}>[{e.dept_id}]</span>}
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
