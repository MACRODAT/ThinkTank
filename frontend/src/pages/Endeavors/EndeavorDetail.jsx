import React, { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  getEndeavor, updateEndeavor,
  addPhase, updatePhase, deletePhase, setCurrentPhase, extendPhase,
  addObjective,
} from '../../api'
import { useApp } from '../../context/AppContext'
import Spinner from '../../components/UI/Spinner'
import Modal from '../../components/UI/Modal'
import ObjectiveItem from './ObjectiveItem'

// ── Phase timeline helpers ────────────────────────────────────────────────────

function phaseDateLabel(p) {
  const end = p.extended_end_date || p.planned_end_date
  if (p.status === 'completed') return `✓ Completed`
  if (p.is_current) {
    const today = new Date(); const endDate = end ? new Date(end) : null
    const daysLeft = endDate ? Math.ceil((endDate - today) / 86400000) : null
    const overdue  = daysLeft !== null && daysLeft < 0
    return (
      <span>
        {p.start_date} → <span style={{ color: overdue ? 'var(--red)' : 'var(--green)', fontWeight:700 }}>
          {end}{overdue ? ` (${Math.abs(daysLeft)}d overdue)` : daysLeft !== null ? ` (${daysLeft}d left)` : ''}
        </span>
        {p.extended_end_date && <span style={{ color:'var(--orange)', marginLeft:6 }}>⚠ Extended</span>}
      </span>
    )
  }
  return `~${p.duration_days} days`
}

function PhaseProgress({ done, total }) {
  const pct = total > 0 ? Math.round((done / total) * 100) : 0
  return (
    <div style={{ display:'flex', alignItems:'center', gap:8, marginTop:6 }}>
      <div style={{ flex:1, height:4, background:'var(--border)', borderRadius:2 }}>
        <div style={{ width:`${pct}%`, height:'100%', background:'var(--green)', borderRadius:2, transition:'width .3s' }} />
      </div>
      <span style={{ fontSize:11, color:'var(--muted)', flexShrink:0 }}>{done}/{total}</span>
    </div>
  )
}

// ── Extend modal ──────────────────────────────────────────────────────────────

function ExtendModal({ phase, onSave, onClose }) {
  const [date, setDate] = useState(phase.extended_end_date || phase.planned_end_date || '')
  return (
    <Modal open onClose={onClose}>
      <h3 style={{ marginBottom:16 }}>Extend Phase: {phase.name}</h3>
      <p style={{ fontSize:13, color:'var(--muted)', marginBottom:14 }}>
        Original end: <strong>{phase.planned_end_date || 'not set'}</strong>
        {phase.extended_end_date && <> · Previously extended to: <strong>{phase.extended_end_date}</strong></>}
      </p>
      <div className="form-group">
        <label className="form-label">New End Date</label>
        <input type="date" className="form-control" value={date} onChange={e => setDate(e.target.value)} />
      </div>
      <div style={{ display:'flex', gap:8 }}>
        <button className="btn btn-success" onClick={() => onSave(date)}>💾 Extend</button>
        <button className="btn btn-ghost"   onClick={onClose}>Cancel</button>
      </div>
    </Modal>
  )
}

// ── Add phase modal ───────────────────────────────────────────────────────────

function AddPhaseModal({ endeavorId, onSave, onClose }) {
  const [name,     setName]     = useState('')
  const [desc,     setDesc]     = useState('')
  const [duration, setDuration] = useState(7)
  const [startDate,setStartDate]= useState('')
  const [saving,   setSaving]   = useState(false)
  const [err,      setErr]      = useState('')

  const save = async () => {
    if (!name.trim()) { setErr('Name required'); return }
    setErr(''); setSaving(true)
    await onSave({ name: name.trim(), description: desc.trim(), duration_days: duration, start_date: startDate || undefined })
    setSaving(false)
  }

  return (
    <Modal open onClose={onClose}>
      <h3 style={{ marginBottom:16 }}>Add Phase</h3>
      <div className="form-group">
        <label className="form-label">Phase Name *</label>
        <input className="form-control" value={name} onChange={e => setName(e.target.value)} placeholder="e.g. Discovery, Implementation, Review…" />
      </div>
      <div className="form-group">
        <label className="form-label">Description</label>
        <textarea className="form-control" rows={2} value={desc} onChange={e => setDesc(e.target.value)} />
      </div>
      <div className="form-row form-row-2">
        <div className="form-group">
          <label className="form-label">Duration (days)</label>
          <input type="number" className="form-control" min={1} value={duration} onChange={e => setDuration(Number(e.target.value))} />
        </div>
        <div className="form-group">
          <label className="form-label">Start Date (if current)</label>
          <input type="date" className="form-control" value={startDate} onChange={e => setStartDate(e.target.value)} />
        </div>
      </div>
      <div style={{ display:'flex', gap:8, alignItems:'center' }}>
        <button className="btn btn-success" onClick={save} disabled={saving}>{saving?<Spinner/>:'💾 Add Phase'}</button>
        <button className="btn btn-ghost"   onClick={onClose}>Cancel</button>
        {err && <span style={{ fontSize:12, color:'var(--red)' }}>{err}</span>}
      </div>
    </Modal>
  )
}

// ── Main detail page ──────────────────────────────────────────────────────────

export default function EndeavorDetail() {
  const { id }   = useParams()
  const navigate = useNavigate()
  const { toast }= useApp()

  const [endeavor,    setEndeavor]    = useState(null)
  const [loading,     setLoading]     = useState(true)
  const [addPhaseOpen,setAddPhaseOpen]= useState(false)
  const [extendPhase_, setExtendPhase_] = useState(null)  // phase to extend
  const [newObjPhaseId, setNewObjPhaseId] = useState(null) // phase to add obj to
  const [newObjTitle,   setNewObjTitle]   = useState('')
  const [expandedPhases, setExpandedPhases] = useState({})

  const load = useCallback(async () => {
    setLoading(true)
    const data = await getEndeavor(id).catch(() => null)
    if (data) {
      setEndeavor(data)
      // Auto-expand current phase
      const cur = data.phases?.find(p => p.is_current)
      if (cur) setExpandedPhases(prev => ({ ...prev, [cur.id]: true }))
    }
    setLoading(false)
  }, [id])

  useEffect(() => { load() }, [load])

  const handleAddPhase = async (body) => {
    await addPhase(id, body)
    toast('Phase added ✓')
    setAddPhaseOpen(false)
    load()
  }

  const handleSetCurrent = async (pid) => {
    const today = new Date().toISOString().split('T')[0]
    await setCurrentPhase(pid, { start_date: today })
    toast('Phase set as current ✓')
    load()
  }

  const handleExtend = async (pid, newDate) => {
    await extendPhase(pid, { new_end_date: newDate })
    toast('Phase extended ✓')
    setExtendPhase_(null)
    load()
  }

  const handleDeletePhase = async (pid) => {
    if (!confirm('Delete this phase and all its objectives?')) return
    await deletePhase(pid)
    toast('Phase deleted')
    load()
  }

  const handleAddObjective = async (pid) => {
    if (!newObjTitle.trim()) return
    await addObjective(pid, { title: newObjTitle.trim() })
    setNewObjTitle('')
    setNewObjPhaseId(null)
    toast('Objective added ✓')
    load()
  }

  const toggleExpand = (pid) => setExpandedPhases(prev => ({ ...prev, [pid]: !prev[pid] }))

  if (loading) return <div className="empty"><Spinner lg /></div>
  if (!endeavor) return <div className="empty">Endeavor not found.</div>

  const totalObjectives = endeavor.phases?.reduce((s,p) => s + (p.total_objectives||0), 0) || 0
  const doneObjectives  = endeavor.phases?.reduce((s,p) => s + (p.done_objectives||0), 0) || 0

  return (
    <div>
      {/* Header */}
      <div className="page-header" style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start' }}>
        <div style={{ display:'flex', alignItems:'center', gap:14 }}>
          <div style={{ width:16, height:16, borderRadius:'50%', background:endeavor.color, flexShrink:0 }} />
          <div>
            <h2>{endeavor.name}</h2>
            <p>{endeavor.description}</p>
          </div>
        </div>
        <div style={{ display:'flex', gap:8 }}>
          <button className="btn btn-ghost btn-sm" onClick={() => navigate('/endeavors')}>← Back</button>
          <button className="btn btn-primary btn-sm" onClick={() => navigate(`/endeavors/${id}/kanban`)}>⊞ Kanban</button>
          <button className="btn btn-success" onClick={() => setAddPhaseOpen(true)}>＋ Add Phase</button>
        </div>
      </div>

      {/* Summary stats */}
      <div className="grid grid-3" style={{ marginBottom:24 }}>
        <div className="card stat">
          <div className="stat-value">{endeavor.phases?.length || 0}</div>
          <div className="stat-label">Phases</div>
        </div>
        <div className="card stat">
          <div className="stat-value" style={{ color:'var(--orange)' }}>{totalObjectives - doneObjectives}</div>
          <div className="stat-label">Pending Objectives</div>
        </div>
        <div className="card stat">
          <div className="stat-value" style={{ color:'var(--green)' }}>
            {totalObjectives > 0 ? Math.round((doneObjectives/totalObjectives)*100) : 0}%
          </div>
          <div className="stat-label">Complete</div>
        </div>
      </div>

      {/* Phases */}
      {(!endeavor.phases || endeavor.phases.length === 0) ? (
        <div className="empty">
          No phases yet.<br/>
          <button className="btn btn-primary" style={{ marginTop:12 }} onClick={() => setAddPhaseOpen(true)}>＋ Add First Phase</button>
        </div>
      ) : (
        <div style={{ display:'flex', flexDirection:'column', gap:12 }}>
          {endeavor.phases.map((phase, idx) => {
            const isExpanded = expandedPhases[phase.id]
            const isCurrent  = !!phase.is_current
            const isCompleted= phase.status === 'completed'
            const isPending  = phase.status === 'pending'
            const effectiveEnd = phase.extended_end_date || phase.planned_end_date

            return (
              <div key={phase.id} className="card" style={{
                borderLeft: `4px solid ${isCurrent ? endeavor.color : isCompleted ? 'var(--green)' : 'var(--border)'}`,
                opacity: isPending ? 0.8 : 1,
              }}>
                {/* Phase header */}
                <div style={{ display:'flex', alignItems:'center', gap:10, cursor:'pointer' }} onClick={() => toggleExpand(phase.id)}>
                  <span style={{ fontSize:13, fontWeight:700, color:'var(--muted)', width:24, textAlign:'center' }}>
                    {idx + 1}
                  </span>
                  <div style={{ flex:1 }}>
                    <div style={{ display:'flex', alignItems:'center', gap:8 }}>
                      <span style={{ fontSize:15, fontWeight:700 }}>{phase.name}</span>
                      {isCurrent  && <span style={{ fontSize:10, background:endeavor.color+'22', color:endeavor.color, padding:'2px 8px', borderRadius:10, fontWeight:700 }}>CURRENT</span>}
                      {isCompleted&& <span style={{ fontSize:10, background:'rgba(63,185,80,.15)', color:'var(--green)', padding:'2px 8px', borderRadius:10, fontWeight:700 }}>✓ DONE</span>}
                      {isPending  && <span style={{ fontSize:10, background:'var(--bg)', color:'var(--muted)', padding:'2px 8px', borderRadius:10, fontWeight:700 }}>PENDING</span>}
                    </div>
                    <div style={{ fontSize:12, color:'var(--muted)', marginTop:2 }}>{phaseDateLabel(phase)}</div>
                    <PhaseProgress done={phase.done_objectives||0} total={phase.total_objectives||0} />
                  </div>
                  <div style={{ display:'flex', gap:4 }} onClick={e => e.stopPropagation()}>
                    {!isCurrent && !isCompleted && (
                      <button className="btn btn-primary btn-sm" onClick={() => handleSetCurrent(phase.id)} title="Set as current">▶ Start</button>
                    )}
                    {isCurrent && (
                      <button className="btn btn-outline btn-sm" onClick={() => setExtendPhase_(phase)} title="Extend deadline">⏰ Extend</button>
                    )}
                    <button className="btn btn-danger btn-sm" onClick={() => handleDeletePhase(phase.id)} title="Delete phase">🗑</button>
                  </div>
                  <span style={{ color:'var(--muted)', fontSize:14 }}>{isExpanded ? '▲' : '▼'}</span>
                </div>

                {/* Phase objectives */}
                {isExpanded && (
                  <div style={{ marginTop:16, paddingTop:16, borderTop:'1px solid var(--border)' }}>
                    {phase.description && (
                      <p style={{ fontSize:13, color:'var(--muted)', marginBottom:12 }}>{phase.description}</p>
                    )}

                    {/* Objectives list */}
                    {(phase.objectives || []).map(obj => (
                      <ObjectiveItem key={obj.id} obj={obj} onChanged={load} />
                    ))}

                    {/* Add objective form */}
                    {newObjPhaseId === phase.id ? (
                      <div style={{ display:'flex', gap:8, marginTop:10 }}>
                        <input className="form-control" style={{ flex:1 }}
                          placeholder="Objective title…"
                          value={newObjTitle}
                          onChange={e => setNewObjTitle(e.target.value)}
                          onKeyDown={e => { if(e.key==='Enter') handleAddObjective(phase.id); if(e.key==='Escape'){setNewObjPhaseId(null);setNewObjTitle('')} }}
                          autoFocus />
                        <button className="btn btn-success btn-sm" onClick={() => handleAddObjective(phase.id)}>＋ Add</button>
                        <button className="btn btn-ghost   btn-sm" onClick={() => { setNewObjPhaseId(null); setNewObjTitle('') }}>✕</button>
                      </div>
                    ) : (
                      <button className="btn btn-outline btn-sm" style={{ marginTop:10 }}
                        onClick={() => { setNewObjPhaseId(phase.id); setNewObjTitle('') }}>
                        ＋ Add Objective
                      </button>
                    )}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}

      {addPhaseOpen && <AddPhaseModal endeavorId={id} onSave={handleAddPhase} onClose={() => setAddPhaseOpen(false)} />}
      {extendPhase_ && <ExtendModal phase={extendPhase_} onSave={(d) => handleExtend(extendPhase_.id, d)} onClose={() => setExtendPhase_(null)} />}
    </div>
  )
}
