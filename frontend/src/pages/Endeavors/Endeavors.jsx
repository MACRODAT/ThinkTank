import React, { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { getEndeavors, createEndeavor, updateEndeavor, deleteEndeavor } from '../../api'
import { useApp } from '../../context/AppContext'
import { COLORS, DEPT_IDS, DEPT_NAMES } from '../../constants'
import Spinner from '../../components/UI/Spinner'
import Modal from '../../components/UI/Modal'

const STATUS_COLORS = { active:'var(--green)', paused:'var(--orange)', completed:'var(--muted)', archived:'var(--red)' }

const PRESET_COLORS = [
  '#58a6ff','#3fb950','#d29922','#f85149','#9C27B0',
  '#FF9800','#2196F3','#4CAF50','#E91E63','#00BCD4',
]

function EndeavorForm({ initial, onSave, onClose }) {
  const [name,  setName]  = useState(initial?.name || '')
  const [desc,  setDesc]  = useState(initial?.description || '')
  const [dept,  setDept]  = useState(initial?.dept_id || '')
  const [color, setColor] = useState(initial?.color || '#58a6ff')
  const [status,setStatus]= useState(initial?.status || 'active')
  const [saving,setSaving]= useState(false)
  const [err,   setErr]   = useState('')
  const { toast } = useApp()

  const save = async () => {
    if (!name.trim()) { setErr('Name is required.'); return }
    setErr(''); setSaving(true)
    try {
      await onSave({ name: name.trim(), description: desc.trim(), dept_id: dept || undefined, color, status })
    } catch(e) { setErr(e.message) }
    setSaving(false)
  }

  return (
    <Modal open onClose={onClose}>
      <h3 style={{ marginBottom:18 }}>{initial ? 'Edit Endeavor' : 'New Endeavor'}</h3>
      <div className="form-group">
        <label className="form-label">Name *</label>
        <input className="form-control" value={name} onChange={e => setName(e.target.value)} placeholder="Endeavor name" />
      </div>
      <div className="form-group">
        <label className="form-label">Description</label>
        <textarea className="form-control" rows={3} style={{ resize:'vertical' }}
          value={desc} onChange={e => setDesc(e.target.value)} placeholder="What is this endeavor about?" />
      </div>
      <div className="form-row form-row-2">
        <div className="form-group">
          <label className="form-label">Department (optional)</label>
          <select className="form-control" value={dept} onChange={e => setDept(e.target.value)}>
            <option value="">— None —</option>
            {DEPT_IDS.map(id => <option key={id} value={id}>{id} — {DEPT_NAMES[id]}</option>)}
          </select>
        </div>
        <div className="form-group">
          <label className="form-label">Status</label>
          <select className="form-control" value={status} onChange={e => setStatus(e.target.value)}>
            <option value="active">Active</option>
            <option value="paused">Paused</option>
            <option value="completed">Completed</option>
            <option value="archived">Archived</option>
          </select>
        </div>
      </div>
      <div className="form-group">
        <label className="form-label">Color</label>
        <div style={{ display:'flex', gap:8, flexWrap:'wrap', marginTop:4 }}>
          {PRESET_COLORS.map(c => (
            <button key={c} onClick={() => setColor(c)}
              style={{ width:28, height:28, borderRadius:'50%', background:c,
                       border: color===c ? '3px solid white' : '2px solid transparent',
                       outline: color===c ? `2px solid ${c}` : 'none', cursor:'pointer' }} />
          ))}
          <input type="color" value={color} onChange={e => setColor(e.target.value)}
            style={{ width:28, height:28, borderRadius:'50%', border:'none', cursor:'pointer', padding:0 }} />
        </div>
      </div>
      <div style={{ display:'flex', gap:8, alignItems:'center', marginTop:4 }}>
        <button className="btn btn-success" onClick={save} disabled={saving}>
          {saving ? <><Spinner/> Saving…</> : '💾 Save'}
        </button>
        <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
        {err && <span style={{ fontSize:12, color:'var(--red)' }}>{err}</span>}
      </div>
    </Modal>
  )
}

export default function Endeavors() {
  const { toast } = useApp()
  const navigate  = useNavigate()
  const [endeavors, setEndeavors] = useState([])
  const [loading,   setLoading]   = useState(true)
  const [modal,     setModal]     = useState(false)
  const [editing,   setEditing]   = useState(null)
  const [filter,    setFilter]    = useState('all')

  const load = useCallback(async () => {
    setLoading(true)
    const data = await getEndeavors().catch(() => [])
    setEndeavors(data)
    setLoading(false)
  }, [])

  useEffect(() => { load() }, [load])

  const filtered = filter === 'all' ? endeavors : endeavors.filter(e => e.status === filter)

  const handleCreate = async (body) => {
    const res = await createEndeavor(body)
    toast('Endeavor created ✓')
    setModal(false)
    await load()
    if (res.id) navigate(`/endeavors/${res.id}`)
  }

  const handleEdit = async (body) => {
    await updateEndeavor(editing.id, body)
    toast('Updated ✓')
    setEditing(null)
    load()
  }

  const del = async (id) => {
    if (!confirm('Delete this endeavor and all its phases/objectives?')) return
    await deleteEndeavor(id)
    toast('Deleted')
    load()
  }

  return (
    <div>
      <div className="page-header" style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start' }}>
        <div><h2>🚀 Endeavors</h2><p>Long-running efforts with phases, objectives and time tracking</p></div>
        <button className="btn btn-success" onClick={() => setModal(true)}>＋ New Endeavor</button>
      </div>

      <div className="tabs">
        {['all','active','paused','completed'].map(t => (
          <button key={t} className={`tab${filter===t?' active':''}`} onClick={() => setFilter(t)}>
            {t.charAt(0).toUpperCase()+t.slice(1)}
          </button>
        ))}
      </div>

      {loading ? <div className="empty"><Spinner lg/></div> : (
        filtered.length === 0 ? (
          <div className="empty">
            No {filter !== 'all' ? filter : ''} endeavors yet.<br/>
            <button className="btn btn-primary" style={{ marginTop:12 }} onClick={() => setModal(true)}>＋ Create one</button>
          </div>
        ) : (
          <div className="grid grid-2">
            {filtered.map(e => (
              <div key={e.id} className="card" style={{ borderLeft:`4px solid ${e.color||'var(--accent)'}`, cursor:'pointer' }}
                onClick={() => navigate(`/endeavors/${e.id}`)}>
                <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start', marginBottom:12 }}>
                  <div>
                    <div style={{ fontSize:16, fontWeight:700, marginBottom:4 }}>{e.name}</div>
                    <div style={{ fontSize:12, color:'var(--muted)', lineHeight:1.4 }}>{e.description || '—'}</div>
                  </div>
                  <span style={{ fontSize:11, fontWeight:700, textTransform:'uppercase', padding:'3px 8px', borderRadius:4,
                    background: `${STATUS_COLORS[e.status]}22`, color:STATUS_COLORS[e.status] }}>
                    {e.status}
                  </span>
                </div>

                <div style={{ display:'flex', gap:16, marginBottom:12 }}>
                  <div style={{ textAlign:'center' }}>
                    <div style={{ fontSize:22, fontWeight:800 }}>{e.phase_count || 0}</div>
                    <div style={{ fontSize:10, color:'var(--muted)', textTransform:'uppercase' }}>Phases</div>
                  </div>
                  <div style={{ textAlign:'center' }}>
                    <div style={{ fontSize:22, fontWeight:800, color:'var(--orange)' }}>{e.pending_tasks || 0}</div>
                    <div style={{ fontSize:10, color:'var(--muted)', textTransform:'uppercase' }}>Pending</div>
                  </div>
                  {e.dept_id && (
                    <div style={{ marginLeft:'auto' }}>
                      <span className="dept-tag" style={{ background: COLORS[e.dept_id] || '#607D8B' }}>{e.dept_id}</span>
                    </div>
                  )}
                </div>

                {e.current_phase && (
                  <div style={{ fontSize:12, color:'var(--muted)', background:'var(--bg)', padding:'6px 10px', borderRadius:6 }}>
                    📍 Current phase: <strong style={{ color:'var(--text)' }}>{e.current_phase}</strong>
                  </div>
                )}

                <div style={{ display:'flex', gap:6, marginTop:12 }} onClick={ev => ev.stopPropagation()}>
                  <button className="btn btn-outline btn-sm" onClick={() => { setEditing(e); }}>✏ Edit</button>
                  <button className="btn btn-primary  btn-sm" onClick={() => navigate(`/endeavors/${e.id}/kanban`)}>⊞ Kanban</button>
                  <button className="btn btn-danger   btn-sm" style={{ marginLeft:'auto' }} onClick={() => del(e.id)}>🗑</button>
                </div>
              </div>
            ))}
          </div>
        )
      )}

      {modal    && <EndeavorForm onSave={handleCreate} onClose={() => setModal(false)} />}
      {editing  && <EndeavorForm initial={editing} onSave={handleEdit} onClose={() => setEditing(null)} />}
    </div>
  )
}
