import React, { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getEndeavor, toggleObjective, addObjective } from '../../api'
import { useApp } from '../../context/AppContext'
import Spinner from '../../components/UI/Spinner'
import ObjectiveItem from './ObjectiveItem'

const STATUS_BG = { pending:'rgba(139,148,158,.1)', active:'rgba(88,166,255,.1)', completed:'rgba(63,185,80,.1)' }
const STATUS_COLOR = { pending:'var(--muted)', active:'var(--accent)', completed:'var(--green)' }

export default function KanbanBoard() {
  const { id }    = useParams()
  const navigate  = useNavigate()
  const { toast } = useApp()

  const [endeavor, setEndeavor] = useState(null)
  const [loading,  setLoading]  = useState(true)
  const [adding,   setAdding]   = useState(null)  // phase_id to add to
  const [addTitle, setAddTitle] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    const data = await getEndeavor(id).catch(() => null)
    setEndeavor(data)
    setLoading(false)
  }, [id])

  useEffect(() => { load() }, [load])

  const handleAdd = async (phaseId) => {
    if (!addTitle.trim()) return
    await addObjective(phaseId, { title: addTitle.trim() })
    setAdding(null); setAddTitle('')
    toast('Objective added ✓')
    load()
  }

  if (loading) return <div className="empty"><Spinner lg /></div>
  if (!endeavor) return <div className="empty">Not found.</div>

  const totalCols = endeavor.phases?.length || 1

  return (
    <div style={{ height: 'calc(100vh - 56px)', display:'flex', flexDirection:'column' }}>
      {/* Header */}
      <div style={{ display:'flex', alignItems:'center', gap:12, marginBottom:16, flexShrink:0 }}>
        <button className="btn btn-ghost btn-sm" onClick={() => navigate(`/endeavors/${id}`)}>← Detail</button>
        <div style={{ width:12, height:12, borderRadius:'50%', background:endeavor.color }} />
        <h2 style={{ fontSize:18, fontWeight:800 }}>{endeavor.name} — Kanban</h2>
        <button className="btn btn-ghost btn-sm" style={{ marginLeft:'auto' }} onClick={() => navigate('/endeavors')}>← All Endeavors</button>
      </div>

      {/* Board */}
      <div style={{
        flex:1, overflowX:'auto', overflowY:'hidden',
        display:'flex', gap:14, paddingBottom:16, alignItems:'flex-start',
      }}>
        {(endeavor.phases || []).map(phase => {
          const isCurrent  = !!phase.is_current
          const isCompleted= phase.status === 'completed'
          const effectiveEnd = phase.extended_end_date || phase.planned_end_date
          const today = new Date()
          const endDate = effectiveEnd ? new Date(effectiveEnd) : null
          const overdue = isCurrent && endDate && endDate < today

          const allObjs = phase.objectives || []
          const pending = allObjs.filter(o => !o.is_done)
          const done    = allObjs.filter(o =>  o.is_done)
          const pct     = allObjs.length ? Math.round((done.length / allObjs.length) * 100) : 0

          return (
            <div key={phase.id} style={{
              width: 280, minWidth: 280, flexShrink:0,
              display:'flex', flexDirection:'column', maxHeight:'100%',
            }}>
              {/* Column header */}
              <div style={{
                background: isCurrent ? `${endeavor.color}18` : 'var(--surface)',
                border: `1px solid ${isCurrent ? endeavor.color : 'var(--border)'}`,
                borderRadius:'10px 10px 0 0',
                padding:'12px 14px',
              }}>
                <div style={{ display:'flex', alignItems:'center', gap:6, marginBottom:4 }}>
                  <span style={{ fontSize:13, fontWeight:700, flex:1 }}>{phase.name}</span>
                  {isCurrent   && <span style={{ fontSize:9, background:endeavor.color, color:'#000', padding:'2px 6px', borderRadius:8, fontWeight:700 }}>NOW</span>}
                  {isCompleted && <span style={{ fontSize:9, background:'var(--green)', color:'#000', padding:'2px 6px', borderRadius:8, fontWeight:700 }}>✓</span>}
                </div>
                {effectiveEnd && (
                  <div style={{ fontSize:11, color: overdue ? 'var(--red)' : 'var(--muted)' }}>
                    {isCurrent ? '→ ' : '~'}{effectiveEnd}
                    {phase.extended_end_date && <span style={{ color:'var(--orange)', marginLeft:4 }}>⚠ ext.</span>}
                    {overdue && <span style={{ color:'var(--red)', marginLeft:4 }}>OVERDUE</span>}
                  </div>
                )}
                {!isCurrent && !effectiveEnd && (
                  <div style={{ fontSize:11, color:'var(--muted)' }}>~{phase.duration_days} days</div>
                )}
                {/* Progress bar */}
                <div style={{ marginTop:6, height:3, background:'var(--border)', borderRadius:2 }}>
                  <div style={{ width:`${pct}%`, height:'100%', background: isCurrent ? endeavor.color : 'var(--green)', borderRadius:2 }} />
                </div>
                <div style={{ fontSize:10, color:'var(--muted)', marginTop:3 }}>{done.length}/{allObjs.length} done</div>
              </div>

              {/* Cards */}
              <div style={{
                flex:1, overflowY:'auto',
                background:'var(--bg)',
                border:`1px solid ${isCurrent ? endeavor.color : 'var(--border)'}`,
                borderTop:'none',
                borderRadius:'0 0 10px 10px',
                padding:'8px',
                display:'flex', flexDirection:'column', gap:6,
              }}>
                {/* Pending objectives */}
                {pending.map(obj => (
                  <div key={obj.id} className="kb-card">
                    <ObjectiveItem obj={obj} onChanged={load} />
                  </div>
                ))}

                {/* Add objective inline */}
                {adding === phase.id ? (
                  <div style={{ padding:'6px 0' }}>
                    <input className="form-control" style={{ fontSize:12, padding:'6px 10px', marginBottom:6 }}
                      placeholder="Objective title…"
                      value={addTitle}
                      onChange={e => setAddTitle(e.target.value)}
                      onKeyDown={e => { if(e.key==='Enter') handleAdd(phase.id); if(e.key==='Escape'){setAdding(null);setAddTitle('')} }}
                      autoFocus />
                    <div style={{ display:'flex', gap:4 }}>
                      <button className="btn btn-success btn-sm" style={{ flex:1 }} onClick={() => handleAdd(phase.id)}>Add</button>
                      <button className="btn btn-ghost   btn-sm" onClick={() => { setAdding(null); setAddTitle('') }}>✕</button>
                    </div>
                  </div>
                ) : (
                  <button className="btn btn-outline btn-sm" style={{ width:'100%', marginTop:4 }}
                    onClick={() => { setAdding(phase.id); setAddTitle('') }}>
                    ＋ Add
                  </button>
                )}

                {/* Done objectives (collapsed) */}
                {done.length > 0 && (
                  <details style={{ marginTop:4 }}>
                    <summary style={{ fontSize:11, color:'var(--muted)', cursor:'pointer', padding:'4px 0' }}>
                      {done.length} completed
                    </summary>
                    {done.map(obj => (
                      <div key={obj.id} className="kb-card" style={{ opacity:0.6 }}>
                        <ObjectiveItem obj={obj} onChanged={load} />
                      </div>
                    ))}
                  </details>
                )}
              </div>
            </div>
          )
        })}

        {/* Empty state */}
        {(endeavor.phases || []).length === 0 && (
          <div className="empty" style={{ width:'100%' }}>
            No phases yet. <button className="btn btn-primary btn-sm" style={{ marginLeft:8 }} onClick={() => navigate(`/endeavors/${id}`)}>Add phases</button>
          </div>
        )}
      </div>
    </div>
  )
}
