import React, { useState } from 'react'
import { createProject, updateProject } from '../../api'
import { useApp } from '../../context/AppContext'
import { DEPT_IDS, PRIORITIES, PROJECT_STATUSES } from '../../constants'
import Modal from '../../components/UI/Modal'
import Spinner from '../../components/UI/Spinner'

export default function ProjectModal({ initial, defaultDept, onClose, onSaved }) {
  const { toast } = useApp()
  const [name,   setName]   = useState(initial?.name        || '')
  const [desc,   setDesc]   = useState(initial?.description || '')
  const [dept,   setDept]   = useState(initial?.dept_id     || defaultDept || 'HF')
  const [prio,   setPrio]   = useState(initial?.priority    || 'normal')
  const [status, setStatus] = useState(initial?.status      || 'active')
  const [saving, setSaving] = useState(false)
  const [err,    setErr]    = useState('')

  const save = async () => {
    if (!name.trim()) { setErr('Name is required.'); return }
    setErr(''); setSaving(true)
    try {
      const body = { dept_id: dept, name: name.trim(), description: desc.trim(), priority: prio, status }
      if (initial?.id) await updateProject(initial.id, body)
      else             await createProject(body)
      toast(initial ? 'Project updated ✓' : 'Project created ✓')
      onSaved()
    } catch(e) { setErr(e.message) }
    setSaving(false)
  }

  return (
    <Modal open onClose={onClose}>
      <h3 style={{ marginBottom:18 }}>{initial ? 'Edit Project' : 'New Project'}</h3>
      <div className="form-row form-row-2">
        <div className="form-group">
          <label className="form-label">Department</label>
          <select className="form-control" value={dept} onChange={e => setDept(e.target.value)}>
            {DEPT_IDS.map(id => <option key={id} value={id}>{id}</option>)}
          </select>
        </div>
        <div className="form-group">
          <label className="form-label">Priority</label>
          <select className="form-control" value={prio} onChange={e => setPrio(e.target.value)}>
            {PRIORITIES.map(p => <option key={p} value={p}>{p}</option>)}
          </select>
        </div>
      </div>
      <div className="form-group">
        <label className="form-label">Name *</label>
        <input className="form-control" value={name} onChange={e => setName(e.target.value)} placeholder="Project name" />
      </div>
      <div className="form-group">
        <label className="form-label">Description</label>
        <textarea className="form-control" rows={4} style={{ resize:'vertical', lineHeight:1.6 }}
          value={desc} onChange={e => setDesc(e.target.value)}
          placeholder="What is this project about? What are the goals?" />
      </div>
      <div className="form-group">
        <label className="form-label">Status</label>
        <select className="form-control" value={status} onChange={e => setStatus(e.target.value)}>
          {PROJECT_STATUSES.map(s => <option key={s} value={s}>{s.charAt(0).toUpperCase()+s.slice(1)}</option>)}
        </select>
      </div>
      <div style={{ display:'flex', gap:8, alignItems:'center' }}>
        <button className="btn btn-success" onClick={save} disabled={saving}>
          {saving ? <><Spinner/> Saving…</> : '💾 Save'}
        </button>
        <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
        {err && <span style={{ fontSize:12, color:'var(--red)' }}>{err}</span>}
      </div>
    </Modal>
  )
}
