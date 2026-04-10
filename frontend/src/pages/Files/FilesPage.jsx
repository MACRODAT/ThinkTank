import React, { useState, useEffect } from 'react'
import FileDrop from '../../components/Files/FileDrop'
import { getDroppedFiles } from '../../api'
import Spinner from '../../components/UI/Spinner'

export default function FilesPage() {
  const [history, setHistory]   = useState([])
  const [loading, setLoading]   = useState(true)
  const [viewing, setViewing]   = useState(null)

  const loadHistory = async () => {
    setLoading(true)
    const d = await getDroppedFiles().catch(() => [])
    setHistory(d); setLoading(false)
  }

  useEffect(() => { loadHistory() }, [])

  const fetchContent = async (id) => {
    const r = await fetch(`/api/files/dropped/${id}`).then(res => res.json()).catch(() => null)
    setViewing(r)
  }

  return (
    <div>
      <div className="page-header">
        <h2>📁 File Drop</h2>
        <p>Drop spreadsheets, PDFs, CSVs, or JSON — data is mined and stored for agent reference</p>
      </div>

      <div style={{ maxWidth:680, marginBottom:28 }}>
        <FileDrop onMined={() => loadHistory()} />
      </div>

      <h3 style={{ marginBottom:12, fontSize:14, fontWeight:700 }}>Previously Dropped Files</h3>
      {loading ? <div className="empty"><Spinner /></div> : history.length === 0 ? (
        <div className="empty" style={{ padding:24 }}>No files dropped yet.</div>
      ) : (
        <div className="card" style={{ padding:0 }}>
          {history.map(f => (
            <div key={f.id} style={{ display:'flex', gap:12, alignItems:'center',
              padding:'12px 16px', borderBottom:'1px solid var(--border)', cursor:'pointer' }}
              onClick={() => fetchContent(f.id)}>
              <span style={{ fontSize:20, flexShrink:0 }}>
                {f.file_type==='.pdf'?'📄':f.file_type==='.csv'?'📊':
                 f.file_type==='.xlsx'||f.file_type==='.xls'?'📈':
                 f.file_type==='.json'?'🔧':'📝'}
              </span>
              <div style={{ flex:1, minWidth:0 }}>
                <div style={{ fontSize:13, fontWeight:600 }}>{f.filename}</div>
                <div style={{ fontSize:11, color:'var(--muted)', marginTop:2 }}>{f.summary}</div>
              </div>
              <span style={{ fontSize:10, color:'var(--muted)', flexShrink:0 }}>
                {f.created_at?.substring(0,16).replace('T',' ')}
              </span>
            </div>
          ))}
        </div>
      )}

      {viewing && (
        <div style={{ position:'fixed', inset:0, background:'rgba(0,0,0,.72)', zIndex:200,
          display:'flex', alignItems:'center', justifyContent:'center' }}
          onClick={() => setViewing(null)}>
          <div style={{ background:'var(--surface)', border:'1px solid var(--border)', borderRadius:12,
            padding:24, maxWidth:780, width:'92%', maxHeight:'85vh', overflow:'auto' }}
            onClick={e => e.stopPropagation()}>
            <div style={{ display:'flex', justifyContent:'space-between', marginBottom:14 }}>
              <h3>{viewing.filename}</h3>
              <button className="btn btn-ghost btn-sm" onClick={() => setViewing(null)}>✕</button>
            </div>
            <div style={{ fontSize:12, color:'var(--muted)', marginBottom:10 }}>{viewing.summary}</div>
            <pre style={{ fontSize:11, background:'var(--bg)', border:'1px solid var(--border)',
              borderRadius:8, padding:14, overflow:'auto', maxHeight:400,
              whiteSpace:'pre-wrap', wordBreak:'break-word', color:'var(--text)' }}>
              {viewing.content?.substring(0, 8000) || '(empty)'}
            </pre>
          </div>
        </div>
      )}
    </div>
  )
}
