import React, { useState, useEffect } from 'react'
import Modal from './Modal'
import Spinner from './Spinner'
import { getPresetList, getPreset } from '../../api'

// ── Fallback built-in presets (used if no external JSON files exist yet) ─────
import { BUILTIN_PRESETS } from './ModelImporterBuiltin'

export default function ModelImporter({ onImport, defaultCategory = 'personality' }) {
  const [open,         setOpen]         = useState(false)
  const [category,     setCategory]     = useState(defaultCategory)
  const [items,        setItems]        = useState([])
  const [categories,   setCategories]   = useState(['personality','tone','skills','traits'])
  const [selected,     setSelected]     = useState(null)
  const [preview,      setPreview]      = useState(null)
  const [loading,      setLoading]      = useState(false)
  const [custom,       setCustom]       = useState(false)
  const [customUrl,    setCustomUrl]    = useState('')
  const [fetching,     setFetching]     = useState(false)
  const [fetchErr,     setFetchErr]     = useState('')
  const [externalFiles,setExternalFiles]= useState([])

  // Load list of external preset JSON files
  useEffect(() => {
    if (!open) return
    getPresetList().then(d => {
      setExternalFiles(d.files || [])
    }).catch(() => {})
  }, [open])

  // Load items when category changes
  useEffect(() => {
    if (!open) return
    loadCategory(category)
  }, [category, open])

  const loadCategory = async (cat) => {
    setLoading(true)
    setItems([])
    setSelected(null)
    setPreview(null)
    try {
      // Try to load from external JSON file named after category
      const data = await getPreset(cat)
      if (Array.isArray(data)) {
        setItems(data)
      } else if (data.items) {
        setItems(data.items)
      } else {
        throw new Error('bad format')
      }
    } catch {
      // Fall back to built-in
      const builtin = BUILTIN_PRESETS[cat] || []
      setItems(builtin)
    }
    setLoading(false)
  }

  const handleImport = () => {
    if (!selected) return
    onImport?.({ category, content: selected.content, name: selected.name })
    setOpen(false)
    setSelected(null)
  }

  const handleFetchCustom = async () => {
    if (!customUrl.trim()) return
    setFetching(true); setFetchErr('')
    try {
      const res = await fetch(customUrl)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const text = await res.text()
      const trimmed = text.slice(0, 8000)
      const item = { name: 'Custom Import', content: trimmed, source: customUrl }
      setPreview(item); setSelected(item)
    } catch (e) {
      setFetchErr(`Failed: ${e.message}`)
    }
    setFetching(false)
  }

  return (
    <>
      <button className="btn btn-outline btn-sm" onClick={() => setOpen(true)}>
        📚 Import Template
      </button>

      <Modal open={open} onClose={() => { setOpen(false); setSelected(null) }} wide>
        <h3 style={{ marginBottom: 12 }}>📚 Import Personality / Skills Template</h3>

        {/* External file picker */}
        {externalFiles.length > 0 && (
          <div style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 10 }}>
            <strong>External preset packs:</strong>{' '}
            {externalFiles.map(f => (
              <button key={f} className={`btn btn-sm ${category===f?'btn-primary':'btn-outline'}`}
                style={{ marginRight: 4, marginBottom: 4 }}
                onClick={() => { setCategory(f); setCustom(false) }}>
                📁 {f}
              </button>
            ))}
          </div>
        )}

        {/* Category tabs */}
        <div className="tabs" style={{ marginBottom: 12 }}>
          {['personality','tone','skills','traits'].map(c => (
            <button key={c} className={`tab${category===c&&!custom?' active':''}`}
              onClick={() => { setCategory(c); setCustom(false) }}>
              {c.charAt(0).toUpperCase() + c.slice(1)}
            </button>
          ))}
          <button className={`tab${custom?' active':''}`}
            onClick={() => { setCustom(true); setSelected(null); setPreview(null) }}>
            🔗 URL Import
          </button>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '240px 1fr', gap: 16, minHeight: 360 }}>
          {/* List */}
          <div style={{ display:'flex', flexDirection:'column', gap:4, overflowY:'auto', maxHeight:420 }}>
            {custom ? (
              <div style={{ padding: 12 }}>
                <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 8 }}>
                  Enter URL to a raw Markdown or JSON preset file.
                </div>
                <input className="form-control" style={{ fontSize:12, marginBottom:6 }}
                  value={customUrl} onChange={e => setCustomUrl(e.target.value)}
                  placeholder="https://raw.githubusercontent.com/…/skills.md" />
                <button className="btn btn-primary btn-sm" onClick={handleFetchCustom} disabled={fetching}>
                  {fetching ? 'Fetching…' : '⬇ Fetch'}
                </button>
                {fetchErr && <div style={{ fontSize:11, color:'var(--red)', marginTop:6 }}>{fetchErr}</div>}
              </div>
            ) : loading ? (
              <div style={{ padding: 20, textAlign: 'center' }}><Spinner /></div>
            ) : items.map(item => (
              <div key={item.name}
                onClick={() => { setSelected(item); setPreview(item) }}
                style={{
                  padding:'8px 12px', borderRadius:7, cursor:'pointer',
                  background: selected?.name===item.name ? 'rgba(88,166,255,.12)' : 'var(--bg)',
                  border: `1px solid ${selected?.name===item.name ? 'var(--accent)' : 'var(--border)'}`,
                }}>
                <div style={{ fontSize:13, fontWeight:600, color:'var(--text)' }}>{item.name}</div>
                <div style={{ fontSize:11, color:'var(--muted)', marginTop:2 }}>{item.source || item.category || ''}</div>
              </div>
            ))}
            {!custom && !loading && items.length === 0 && (
              <div style={{ padding:12, fontSize:12, color:'var(--muted)' }}>No presets for this category.</div>
            )}
          </div>

          {/* Preview */}
          <div style={{ background:'var(--bg)', border:'1px solid var(--border)', borderRadius:8, overflowY:'auto', maxHeight:420 }}>
            {preview ? (
              <pre style={{ padding:14, fontSize:12, lineHeight:1.6, color:'var(--text)', whiteSpace:'pre-wrap', wordBreak:'break-word', margin:0 }}>
                {preview.content}
              </pre>
            ) : (
              <div style={{ padding:24, textAlign:'center', color:'var(--muted)', fontSize:13 }}>
                Select a template to preview
              </div>
            )}
          </div>
        </div>

        <div style={{ display:'flex', gap:8, marginTop:14, alignItems:'center' }}>
          <button className="btn btn-success" onClick={handleImport} disabled={!selected}>
            ✓ Import into Agent
          </button>
          <button className="btn btn-ghost" onClick={() => setOpen(false)}>Cancel</button>
          {selected && (
            <span style={{ fontSize:11, color:'var(--muted)' }}>
              Will be saved as a {category} file for this agent
            </span>
          )}
        </div>
      </Modal>
    </>
  )
}
