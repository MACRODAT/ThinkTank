import React, { useState, useEffect } from 'react'
import { getSettings, saveSettings, probeOllama, getThinkingLog } from '../../api'
import { useApp } from '../../context/AppContext'
import Spinner from '../../components/UI/Spinner'
import Modal from '../../components/UI/Modal'

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
  const [verbose,    setVerbose]   = useState(false)
  const [ollamaModels, setOllamaModels] = useState([])

  useEffect(() => {
    getSettings().then(d => {
      setS(d); setBackend(d.ai_backend||'claude'); setApiKey(d.claude_api_key||'')
      setCModel(d.claude_model||'claude-sonnet-4-20250514')
      setOUrl(d.ollama_base_url||'http://localhost:11434')
      setOModel(d.ollama_model||'llama3'); setOTimeout(d.ollama_timeout||'120')
      setCustomP(d.custom_prompt||''); setVerbose(d.verbose_thinking==='true')
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
        custom_prompt: customP, verbose_thinking: verbose ? 'true' : 'false'
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

  return (
    <div>
      <div className="page-header"><h2>⚙️ Settings</h2><p>AI backend, models, prompt and verbosity</p></div>

      <div className="s-section">
        <h3>Active Configuration</h3>
        <div className="s-row">
          <div className="s-info"><div className="s-label">Current backend</div><div className="s-desc">All department cycles use this.</div></div>
          <div className="s-ctrl">
            <span className={`backend-ind ${backend==='ollama'?'bi-ollama':'bi-claude'}`}>
              {backend==='ollama' ? '🟢 Ollama (local)' : '🔵 Claude API'}
            </span>
          </div>
        </div>
      </div>

      <div className="s-section">
        <h3>🤖 Backend</h3>
        <div className="s-row">
          <div className="s-info">
            <div className="s-label">Select Backend</div>
            <div className="s-desc">
              <b>Claude API</b> — cloud, needs API key &amp; credits.<br/>
              <b>Ollama</b> — fully local, offline. All tasks go to Ollama, no silent fallback.
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
            <div className="s-info"><div className="s-label">Model</div><div className="s-desc">Type any model ID or pick from list.</div></div>
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
              {probeRes.ok
                ? `✓ Connected — ${probeRes.models.length} model(s): ${probeRes.models.join(', ')||'none'}`
                : `✗ ${probeRes.error}`}
            </div>
          )}
          <div className="s-row">
            <div className="s-info">
              <div className="s-label">Model</div>
              <div className="s-desc">Type any model name or click Test to load installed ones.</div>
            </div>
            <div className="s-ctrl">
              <input className="s-inp" list="ollama-dl" value={oModel} onChange={e => setOModel(e.target.value)}
                placeholder="e.g. llama3, deepseek-r1:7b" />
              <datalist id="ollama-dl">
                {[...new Set(['llama3','llama3.2:3b','mistral','deepseek-r1:7b','deepseek-r1:14b',
                  'qwq:32b','phi4','gemma3:4b','qwen2.5:7b','qwen2.5:14b', ...ollamaModels])]
                  .map(m => <option key={m} value={m}/>)}
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

      <div className="s-section">
        <h3>📝 Global Custom Prompt</h3>
        <div className="s-row" style={{ alignItems:'flex-start' }}>
          <div className="s-info">
            <div className="s-label">Appended to all system prompts</div>
            <div className="s-desc">
              Added before each AI call globally. Use for personal context, language, style.<br/>
              <em>e.g. "Always be concise. User is a Moroccan mechanical engineer."</em>
            </div>
          </div>
          <div className="s-ctrl" style={{ alignItems:'flex-start' }}>
            <textarea className="s-inp" style={{ width:300, minHeight:90, resize:'vertical', lineHeight:1.5 }}
              placeholder="e.g. Keep responses under 300 words unless asked."
              value={customP} onChange={e => setCustomP(e.target.value)} />
          </div>
        </div>
      </div>

      <div className="s-section">
        <h3>🧠 Verbose Thinking</h3>
        <div className="s-row">
          <div className="s-info">
            <div className="s-label">Capture AI Reasoning</div>
            <div className="s-desc">
              Claude 3.7+/Sonnet4/Opus4: uses extended thinking API.<br/>
              Ollama deepseek-r1/qwq: extracts &lt;think&gt; tags automatically.
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

      <Modal open={thinkOpen} onClose={() => setThinkOpen(false)} wide>
        <h3 style={{ marginBottom:16 }}>🧠 AI Thinking Log</h3>
        {thinking.length === 0
          ? <div className="empty">No thinking captured yet. Enable Verbose Thinking and run a cycle.</div>
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
