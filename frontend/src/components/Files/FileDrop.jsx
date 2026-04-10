import React, { useState, useRef, useCallback } from 'react'
import { useApp } from '../../context/AppContext'
import Spinner from '../UI/Spinner'

const ACCEPTED = ['.txt','.md','.csv','.json','.xlsx','.xls','.pdf']

export default function FileDrop({ onMined }) {
  const { toast } = useApp()
  const [dragging, setDragging] = useState(false)
  const [files,    setFiles]    = useState([])
  const [mining,   setMining]   = useState(null)
  const inputRef = useRef()

  const processFile = useCallback(async (file) => {
    setMining(file.name)
    try {
      const b64 = await new Promise((res, rej) => {
        const r = new FileReader()
        r.onload  = e => res(btoa(e.target.result))
        r.onerror = rej
        r.readAsBinaryString(file)
      })
      const resp = await fetch('/api/files/drop', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filename: file.name, content_b64: b64, mime: file.type }),
      }).then(r => r.json())
      if (resp.error) { toast(resp.error, 'error'); return }
      const entry = { ...resp, name: file.name, size: file.size }
      setFiles(prev => [entry, ...prev])
      toast(`${file.name} mined ✓ — ${resp.summary}`)
      onMined?.(entry)
    } catch (e) {
      toast(`Failed to process ${file.name}: ${e.message}`, 'error')
    } finally {
      setMining(null)
    }
  }, [toast, onMined])

  const handleDrop = useCallback((e) => {
    e.preventDefault(); setDragging(false)
    Array.from(e.dataTransfer.files).forEach(processFile)
  }, [processFile])

  const handleSelect = useCallback((e) => {
    Array.from(e.target.files).forEach(processFile)
    e.target.value = ''
  }, [processFile])

  return (
    <div>
      <div
        onDragOver={e => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current.click()}
        style={{
          border: `2px dashed ${dragging ? 'var(--accent)' : 'var(--border)'}`,
          borderRadius: 10, padding: '28px 20px', textAlign: 'center',
          cursor: 'pointer', transition: 'all 0.15s',
          background: dragging ? 'rgba(88,166,255,.06)' : 'var(--bg)',
          animation: dragging ? 'pulse 1s ease infinite' : 'none',
        }}>
        <input ref={inputRef} type="file" multiple accept={ACCEPTED.join(',')}
          style={{ display:'none' }} onChange={handleSelect} />
        {mining ? (
          <div style={{ color:'var(--accent)', display:'flex', alignItems:'center', justifyContent:'center', gap:8 }}>
            <Spinner /> Mining {mining}…
          </div>
        ) : (
          <>
            <div style={{ fontSize:28, marginBottom:8 }}>📁</div>
            <div style={{ fontSize:13, fontWeight:600, color: dragging ? 'var(--accent)' : 'var(--text)' }}>
              {dragging ? 'Drop to mine data' : 'Drop files here or click to select'}
            </div>
            <div style={{ fontSize:11, color:'var(--muted)', marginTop:4 }}>
              Supported: {ACCEPTED.join(' ')}
            </div>
          </>
        )}
      </div>

      {files.length > 0 && (
        <div style={{ marginTop:12 }}>
          {files.map(f => (
            <div key={f.id} style={{ display:'flex', gap:10, alignItems:'flex-start',
              padding:'10px 12px', background:'var(--surface)', border:'1px solid var(--border)',
              borderRadius:8, marginBottom:6 }}>
              <span style={{ fontSize:20, flexShrink:0 }}>
                { f.name.endsWith('.pdf') ? '📄'
                : f.name.endsWith('.csv') ? '📊'
                : f.name.endsWith('.xlsx')||f.name.endsWith('.xls') ? '📈'
                : f.name.endsWith('.json') ? '🔧' : '📝' }
              </span>
              <div style={{ flex:1, minWidth:0 }}>
                <div style={{ fontSize:13, fontWeight:600 }}>{f.name}</div>
                <div style={{ fontSize:11, color:'var(--muted)', marginTop:2 }}>{f.summary}</div>
                {f.preview && (
                  <details style={{ marginTop:6 }}>
                    <summary style={{ fontSize:11, color:'var(--accent)', cursor:'pointer' }}>View extracted data</summary>
                    <pre style={{ fontSize:10, marginTop:6, maxHeight:200, overflow:'auto',
                      background:'var(--bg)', border:'1px solid var(--border)', borderRadius:6,
                      padding:10, whiteSpace:'pre-wrap', wordBreak:'break-all', color:'var(--muted)' }}>
                      {f.preview}
                    </pre>
                  </details>
                )}
              </div>
              <span style={{ fontSize:10, color:'var(--muted)', flexShrink:0 }}>
                {(f.size/1024).toFixed(1)} KB
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
