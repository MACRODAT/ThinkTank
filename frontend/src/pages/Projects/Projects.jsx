import React, { useState, useEffect, useCallback } from 'react'
import { getProjects, deleteProject } from '../../api'
import { useApp } from '../../context/AppContext'
import { PRIO_COLORS } from '../../constants'
import Spinner from '../../components/UI/Spinner'
import DeptTag from '../../components/UI/DeptTag'
import PriorityDot from '../../components/UI/PriorityDot'
import ProjectModal from './ProjectModal'

const STATUS_TABS = ['active','paused','completed','all']
const statusColor = s => ({ active:'var(--green)', paused:'var(--orange)', completed:'var(--muted)', cancelled:'var(--red)' }[s] || 'var(--muted)')

export default function Projects() {
  const { toast } = useApp()
  const [tab,      setTab]     = useState('active')
  const [projects, setProjects]= useState([])
  const [loading,  setLoading] = useState(true)
  const [modal,    setModal]   = useState(false)
  const [editing,  setEditing] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    const params = tab === 'all' ? {} : { status: tab }
    const data = await getProjects(params)
    const seen = new Set()
    setProjects(data.filter(p => { if(seen.has(p.id)) return false; seen.add(p.id); return true }))
    setLoading(false)
  }, [tab])

  useEffect(() => { load() }, [load])

  const del = async (id) => {
    if (!confirm('Delete this project? Cannot be undone.')) return
    await deleteProject(id)
    toast('Project deleted')
    load()
  }

  let lastDept = null

  return (
    <div>
      <div className="page-header" style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start' }}>
        <div><h2>📁 All Projects</h2><p>Projects across all departments</p></div>
        <button className="btn btn-success" onClick={() => { setEditing(null); setModal(true) }}>＋ New Project</button>
      </div>

      <div className="tabs">
        {STATUS_TABS.map(t => (
          <button key={t} className={`tab${tab===t?' active':''}`} onClick={() => setTab(t)}>
            {t.charAt(0).toUpperCase()+t.slice(1)}
          </button>
        ))}
      </div>

      <div className="card" style={{ padding:0 }}>
        {loading ? <div className="empty"><Spinner/></div>
          : projects.length === 0 ? <div className="empty">No {tab} projects</div>
          : projects.map(p => {
            const showHeader = p.dept_id !== lastDept; lastDept = p.dept_id
            return (
              <React.Fragment key={p.id}>
                {showHeader && (
                  <div style={{ padding:'10px 16px 4px', background:'var(--bg)', borderBottom:'1px solid var(--border)', display:'flex', alignItems:'center', gap:8 }}>
                    <DeptTag id={p.dept_id} />
                    <span style={{ fontSize:12, color:'var(--muted)' }}>{p.dept_name}</span>
                  </div>
                )}
                <div style={{ padding:'12px 16px', borderBottom:'1px solid var(--border)', display:'flex', gap:10, alignItems:'flex-start' }}>
                  <PriorityDot priority={p.priority} />
                  <div style={{ flex:1, minWidth:0 }}>
                    <div style={{ fontSize:13, fontWeight:600 }}>{p.name}</div>
                    <div style={{ fontSize:11, color:'var(--muted)', marginTop:2, lineHeight:1.4 }}>{p.description}</div>
                    <div style={{ display:'flex', gap:8, marginTop:4 }}>
                      <span style={{ fontSize:10, fontWeight:700, color:statusColor(p.status), textTransform:'uppercase' }}>{p.status}</span>
                      <span style={{ fontSize:10, fontWeight:600, color:PRIO_COLORS[p.priority], textTransform:'uppercase' }}>{p.priority}</span>
                    </div>
                  </div>
                  <div style={{ display:'flex', gap:4 }}>
                    <button className="btn btn-outline btn-sm" onClick={() => { setEditing(p); setModal(true) }}>✏ Edit</button>
                    <button className="btn btn-danger  btn-sm" onClick={() => del(p.id)}>🗑</button>
                  </div>
                </div>
              </React.Fragment>
            )
          })
        }
      </div>

      {modal && (
        <ProjectModal
          initial={editing}
          onClose={() => { setModal(false); setEditing(null) }}
          onSaved={() => { setModal(false); setEditing(null); load() }}
        />
      )}
    </div>
  )
}
