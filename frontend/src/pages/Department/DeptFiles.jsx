import React, { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getDeptFiles, upsertDeptFile, deleteDeptFile, getAgents } from '../../api'
import { useApp } from '../../context/AppContext'
import { COLORS, ICONS } from '../../constants'
import Spinner from '../../components/UI/Spinner'
import Modal from '../../components/UI/Modal'
import MarkdownPreview from '../../components/Editor/MarkdownPreview'

const CATEGORIES = ['purpose','roles','policy','guidelines','charts','culture','workflows','knowledge']

export default function DeptFiles() {
  const { id }   = useParams()
  const navigate = useNavigate()
  const { toast }= useApp()

  const [files,   setFiles]   = useState([])
  const [agents,  setAgents]  = useState([])
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState(null)
  const [adding,  setAdding]  = useState(false)
  const [newCat,  setNewCat]  = useState('purpose')
  const [newName, setNewName] = useState('')
  const [newContent, setNewContent] = useState('')
  const [saving,  setSaving]  = useState(false)
  const [preview, setPreview] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    const [f, a] = await Promise.all([
      getDeptFiles(id).catch(()=>[]),
      getAgents({ dept_id: id }).catch(()=>[]),
    ])
    setFiles(f); setAgents(a)
    setLoading(false)
  }, [id])

  useEffect(() => { load() }, [load])

  const save = async (category, filename, content, existingId) => {
    setSaving(true)
    await upsertDeptFile(id, { category, filename, content })
    toast('Saved ✓'); setSaving(false); setEditing(null); setAdding(false)
    load()
  }

  const del = async (fid) => {
    if (!confirm('Delete this file?')) return
    await deleteDeptFile(id, fid)
    toast('Deleted'); load()
  }

  const grouped = {}
  for (const f of files) {
    if (!grouped[f.category]) grouped[f.category] = []
    grouped[f.category].push(f)
  }

  const color = COLORS[id] || '#607D8B'

  return (
    <div>
      {/* Header */}
      <div className="page-header" style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start' }}>
        <div style={{ display:'flex', gap:12, alignItems:'center' }}>
          <span style={{ fontSize:32 }}>{ICONS[id]||'🏛️'}</span>
          <div>
            <h2>{id} Department — Files</h2>
            <p>Policy, guidelines, roles, charts, culture and knowledge base</p>
          </div>
        </div>
        <div style={{ display:'flex', gap:8 }}>
          <button className="btn btn-ghost btn-sm" onClick={()=>navigate(`/dept/${id}`)}>← Department</button>
          <button className="btn btn-ghost btn-sm" onClick={()=>navigate(`/dept/${id}/agents`)}>👥 Agents</button>
          <button className="btn btn-success" onClick={()=>setAdding(true)}>＋ New File</button>
        </div>
      </div>

      {loading ? <div className="empty"><Spinner/></div> : (
        <div style={{ display:'grid', gridTemplateColumns:'240px 1fr', gap:20, alignItems:'start' }}>
          {/* File tree sidebar */}
          <div className="card" style={{ padding:0, position:'sticky', top:0 }}>
            <div style={{ padding:'12px 16px', borderBottom:'1px solid var(--border)', fontSize:11, fontWeight:700, textTransform:'uppercase', color:'var(--muted)' }}>
              📁 {files.length} Files
            </div>
            {CATEGORIES.map(cat => {
              const catFiles = grouped[cat] || []
              if (!catFiles.length) return null
              return (
                <div key={cat}>
                  <div style={{ padding:'6px 16px 3px', fontSize:10, fontWeight:700, textTransform:'uppercase', color:'var(--muted)', background:'var(--bg)' }}>{cat}</div>
                  {catFiles.map(f => (
                    <div key={f.id}
                      style={{ padding:'7px 16px', cursor:'pointer', fontSize:13,
                        background: editing?.id === f.id ? `${color}18` : 'transparent',
                        borderLeft: editing?.id===f.id ? `3px solid ${color}` : '3px solid transparent',
                        transition:'all .1s' }}
                      onClick={()=>setEditing({...f})}>
                      📄 {f.filename}
                    </div>
                  ))}
                </div>
              )
            })}
            {files.length === 0 && (
              <div style={{ padding:20, textAlign:'center', color:'var(--muted)', fontSize:12 }}>
                No files yet.
              </div>
            )}
          </div>

          {/* Editor area */}
          <div>
            {editing ? (
              <div className="card" style={{ padding:0 }}>
                <div style={{ display:'flex', alignItems:'center', gap:10, padding:'12px 16px', borderBottom:'1px solid var(--border)' }}>
                  <span style={{ fontSize:13, fontWeight:700 }}>📄 {editing.filename}</span>
                  <span style={{ fontSize:11, color:'var(--muted)', background:'var(--bg)', padding:'2px 6px', borderRadius:4 }}>{editing.category}</span>
                  <div style={{ marginLeft:'auto', display:'flex', gap:6 }}>
                    <button className="btn btn-outline btn-sm" onClick={()=>setPreview(v=>!v)}>{preview ? '✎ Edit only' : '⊟ Split'}</button>
                    <button className="btn btn-success btn-sm" onClick={()=>save(editing.category, editing.filename, editing.content)} disabled={saving}>
                      {saving?<Spinner/>:'💾 Save'}
                    </button>
                    <button className="btn btn-danger  btn-sm" onClick={()=>del(editing.id)}>🗑</button>
                    <button className="btn btn-ghost   btn-sm" onClick={()=>setEditing(null)}>✕</button>
                  </div>
                </div>
                <div style={{ display:'grid', gridTemplateColumns: preview ? '1fr 1fr' : '1fr', minHeight:500 }}>
                  <textarea
                    className="prompt-editor"
                    style={{ border:'none', borderRadius:0, borderRight: preview ? '1px solid var(--border)' : 'none', minHeight:500 }}
                    value={editing.content}
                    onChange={e=>setEditing({...editing, content:e.target.value})}
                  />
                  {preview && <div style={{ overflowY:'auto' }}><MarkdownPreview content={editing.content} /></div>}
                </div>
              </div>
            ) : (
              <div className="empty" style={{ border:'2px dashed var(--border)', borderRadius:10, cursor:'pointer' }} onClick={()=>setAdding(true)}>
                Select a file from the tree or click ＋ to create one
              </div>
            )}
          </div>
        </div>
      )}

      {/* Add modal */}
      <Modal open={adding} onClose={()=>setAdding(false)}>
        <h3 style={{ marginBottom:14 }}>New Department File</h3>
        <div className="form-row form-row-2">
          <div className="form-group">
            <label className="form-label">Category</label>
            <select className="form-control" value={newCat} onChange={e=>setNewCat(e.target.value)}>
              {CATEGORIES.map(c=><option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          <div className="form-group">
            <label className="form-label">Filename</label>
            <input className="form-control" value={newName} onChange={e=>setNewName(e.target.value)} placeholder="e.g. guidelines.md" />
          </div>
        </div>
        <div className="form-group">
          <label className="form-label">Content (Markdown)</label>
          <textarea className="form-control" rows={10} style={{ fontFamily:'monospace', fontSize:12, resize:'vertical' }}
            value={newContent} onChange={e=>setNewContent(e.target.value)}
            placeholder={`# ${newCat.charAt(0).toUpperCase()+newCat.slice(1)}\n\n## Overview\n\n...`} />
        </div>
        <div style={{ display:'flex', gap:8 }}>
          <button className="btn btn-success" onClick={()=>save(newCat, newName||`${newCat}.md`, newContent)} disabled={saving}>
            {saving?<Spinner/>:'💾 Save'}
          </button>
          <button className="btn btn-ghost" onClick={()=>setAdding(false)}>Cancel</button>
        </div>
      </Modal>
    </div>
  )
}
