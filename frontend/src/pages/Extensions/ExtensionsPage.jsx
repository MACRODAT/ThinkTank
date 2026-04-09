import React, { useState, useEffect, useRef } from 'react'
import { useApp } from '../../context/AppContext'
import Spinner from '../../components/UI/Spinner'

const CATEGORY_LABELS = {
  tool:         { label:'🔧 Tools',         color:'#58a6ff' },
  formatting:   { label:'🎨 Formatting',    color:'#d29922' },
  audit:        { label:'🔍 Audit',         color:'#8b949e' },
  organisation: { label:'📂 Organisation',  color:'#a371f7' },
  integration:  { label:'🔗 Integrations',  color:'#3fb950' },
  content:      { label:'📦 Content',       color:'#f0883e' },
  dev:          { label:'⚙️ Dev',           color:'#e3b341' },
  custom:       { label:'🧪 Custom',        color:'#e05050' },
}

function ExtCard({ ext, onToggle, onConfigSave }) {
  const cat    = CATEGORY_LABELS[ext.category] || { label: ext.category, color:'#888' }
  const [open, setOpen] = useState(false)
  const [cfg,  setCfg]  = useState(JSON.stringify(ext.config || {}, null, 2))
  const [busy, setBusy] = useState(false)

  const toggle = async () => {
    if (ext.builtin) return
    setBusy(true)
    await onToggle(ext.id, !ext.enabled)
    setBusy(false)
  }

  const saveConfig = async () => {
    try {
      const parsed = JSON.parse(cfg)
      setBusy(true)
      await onConfigSave(ext.id, parsed)
      setBusy(false)
      setOpen(false)
    } catch { alert('Invalid JSON in config') }
  }

  return (
    <div className={`ext-card${ext.enabled ? ' installed' : ''}`}>
      <div style={{ display:'flex', gap:10, alignItems:'flex-start' }}>
        <button onClick={toggle} disabled={busy || ext.builtin} title={ext.builtin ? 'Built-in (always on)' : (ext.enabled ? 'Disable' : 'Enable')}
          style={{
            flexShrink:0, width:36, height:20, borderRadius:10, border:'none',
            cursor: ext.builtin ? 'not-allowed' : 'pointer',
            background: ext.enabled ? 'var(--green)' : 'var(--border)',
            position:'relative', transition:'background 0.2s',
            opacity: ext.builtin ? 0.7 : 1,
          }}>
          <span style={{
            position:'absolute', top:2, borderRadius:'50%', width:16, height:16,
            background:'#fff', left: ext.enabled ? 18 : 2, transition:'left 0.2s', display:'block',
          }} />
        </button>

        <div style={{ flex:1, minWidth:0 }}>
          <div style={{ display:'flex', gap:8, alignItems:'center', flexWrap:'wrap', marginBottom:3 }}>
            <span style={{ fontSize:14, fontWeight:700 }}>{ext.name}</span>
            <span style={{ fontSize:10, padding:'2px 7px', borderRadius:4, fontWeight:700,
              background: cat.color + '22', color: cat.color }}>{cat.label}</span>
            <span style={{ fontSize:10, color:'var(--muted)' }}>v{ext.version} · {ext.author}</span>
            {ext.builtin && <span style={{ fontSize:9, color:'var(--accent)', background:'rgba(88,166,255,.1)', padding:'1px 5px', borderRadius:3 }}>BUILT-IN</span>}
          </div>
          <div style={{ fontSize:12, color:'var(--muted)', lineHeight:1.6 }}>{ext.description}</div>
          {ext.install_hint && !ext.enabled && (
            <div style={{ fontSize:11, color:'var(--orange)', marginTop:5, fontStyle:'italic' }}>💡 {ext.install_hint}</div>
          )}
          {ext.source_file && (
            <div style={{ fontSize:10, color:'var(--muted)', marginTop:3 }}>📄 {ext.source_file}</div>
          )}
        </div>

        <div style={{ display:'flex', gap:6, flexShrink:0, alignItems:'center' }}>
          {busy && <Spinner />}
          {(ext.config_keys?.length > 0 || ext.category === 'custom' || ext.category === 'dev') && (
            <button className="btn btn-outline btn-sm" onClick={() => setOpen(o => !o)}>
              {open ? '▲' : '▼'} Config
            </button>
          )}
          <span style={{ fontSize:11, fontWeight:700, color: ext.enabled ? 'var(--green)' : 'var(--muted)', minWidth:36 }}>
            {ext.enabled ? '● ON' : '○ OFF'}
          </span>
        </div>
      </div>

      {open && (
        <div style={{ marginTop:12, borderTop:'1px solid var(--border)', paddingTop:12 }}>
          {ext.config_keys?.length > 0 && (
            <div style={{ fontSize:11, color:'var(--muted)', marginBottom:8 }}>
              Config keys: {ext.config_keys.map(k => <code key={k} style={{ marginRight:6, color:'var(--accent)' }}>{k}</code>)}
            </div>
          )}
          <textarea value={cfg} onChange={e => setCfg(e.target.value)}
            style={{ width:'100%', minHeight:100, fontFamily:'monospace', fontSize:12,
              background:'var(--bg)', border:'1px solid var(--border)', color:'var(--text)',
              borderRadius:6, padding:10, resize:'vertical' }} />
          <div style={{ display:'flex', gap:8, marginTop:8 }}>
            <button className="btn btn-primary btn-sm" onClick={saveConfig}>💾 Save Config</button>
            <button className="btn btn-ghost btn-sm" onClick={() => setOpen(false)}>Cancel</button>
          </div>
        </div>
      )}
    </div>
  )
}

export default function ExtensionsPage() {
  const { toast }  = useApp()
  const [exts,     setExts]     = useState([])
  const [loading,  setLoading]  = useState(true)
  const [filter,   setFilter]   = useState('all')
  const [search,   setSearch]   = useState('')
  const [uploading,setUploading]= useState(false)
  const fileRef = useRef()

  const load = async () => {
    setLoading(true)
    const data = await fetch('/api/extensions').then(r => r.json()).catch(() => [])
    setExts(data); setLoading(false)
  }
  useEffect(() => { load() }, [])

  const onToggle = async (id, enabled) => {
    await fetch(`/api/extensions/${id}/toggle`, {
      method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ enabled }),
    })
    toast(enabled ? `${id} enabled ✓` : `${id} disabled`)
    load()
  }

  const onConfigSave = async (id, config) => {
    await fetch(`/api/extensions/${id}/config`, {
      method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(config),
    })
    toast('Config saved ✓'); load()
  }

  const handleUpload = async (e) => {
    const file = e.target.files[0]; if (!file) return
    if (!file.name.endsWith('.py')) { toast('Only .py files allowed', 'error'); return }
    setUploading(true)
    const reader = new FileReader()
    reader.onload = async (ev) => {
      const b64 = btoa(ev.target.result)
      const res = await fetch('/api/extensions/install-file', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({ filename: file.name, content_b64: b64 }),
      }).then(r => r.json())
      if (res.ok) { toast(`${file.name} installed ✓`); load() }
      else toast(res.error || 'Install failed', 'error')
      setUploading(false)
    }
    reader.readAsBinaryString(file)
    e.target.value = ''
  }

  const allCats  = ['all', ...new Set(exts.map(e => e.category))]
  const filtered = exts.filter(e => {
    const mc = filter === 'all' || e.category === filter
    const ms = !search || e.name.toLowerCase().includes(search.toLowerCase()) || e.description.toLowerCase().includes(search.toLowerCase())
    return mc && ms
  })
  const enabledCount = exts.filter(e => e.enabled).length

  return (
    <div>
      <div className="page-header" style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start', flexWrap:'wrap', gap:12 }}>
        <div>
          <h2>🧩 Extensions</h2>
          <p>Enable capabilities, integrations, and custom tools for your agents</p>
        </div>
        <div style={{ display:'flex', gap:8, alignItems:'center' }}>
          <span style={{ fontSize:12, color:'var(--muted)' }}>{enabledCount}/{exts.length} enabled</span>
          <input type="file" ref={fileRef} accept=".py" style={{ display:'none' }} onChange={handleUpload} />
          <button className="btn btn-outline" onClick={() => fileRef.current.click()} disabled={uploading}>
            {uploading ? <><Spinner /> Installing…</> : '📁 Install .py'}
          </button>
        </div>
      </div>

      <div style={{ display:'flex', gap:8, marginBottom:20, flexWrap:'wrap', alignItems:'center' }}>
        <input className="form-control" style={{ maxWidth:220 }}
          placeholder="Search…" value={search} onChange={e => setSearch(e.target.value)} />
        {allCats.map(c => (
          <button key={c} className={`btn btn-sm ${filter===c?'btn-primary':'btn-outline'}`} onClick={() => setFilter(c)}>
            {c === 'all' ? '🗂 All' : (CATEGORY_LABELS[c]?.label || c)}
          </button>
        ))}
      </div>

      {loading ? <div className="empty"><Spinner /></div>
       : filtered.length === 0 ? <div className="empty">No extensions match your filter.</div>
       : <div style={{ display:'grid', gap:12 }}>
           {filtered.map(ext => <ExtCard key={ext.id} ext={ext} onToggle={onToggle} onConfigSave={onConfigSave} />)}
         </div>}

      <div style={{ marginTop:28, padding:16, background:'var(--surface)', border:'1px solid var(--border)',
        borderRadius:10, fontSize:12, color:'var(--muted)', lineHeight:1.8 }}>
        <strong style={{ color:'var(--text)' }}>🔧 Build your own extension</strong><br />
        Create a <code>.py</code> file in <code>core/extensions/</code> with an async <code>run(params, agent)</code> function,
        then install it above. It becomes available as a new agent tool automatically.
        <pre style={{ background:'var(--bg)', border:'1px solid var(--border)', borderRadius:6, padding:'10px 14px',
          marginTop:10, fontSize:11, overflow:'auto' }}>
{`TOOL_NAME = "my_tool"
TOOL_DESCRIPTION = "What this tool does for agents"

async def run(params: dict, agent: dict) -> str:
    query = params.get("query", "")
    return f"Result for: {query}"`}
        </pre>
      </div>
    </div>
  )
}
