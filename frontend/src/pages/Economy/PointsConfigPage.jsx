import React, { useState, useEffect } from 'react'
import { getPointsConfig, savePointsConfig } from '../../api'
import { useApp } from '../../context/AppContext'
import Spinner from '../../components/UI/Spinner'

const GROUPS = [
  { label: '📋 Drafts',       keys: ['draft_strategy_create_ceo','draft_strategy_create_agent','draft_strategy_approved','draft_strategy_revised','draft_strategy_rejected','draft_strategy_overdue_day','draft_other_create','draft_other_approved','draft_other_rejected_founder','draft_revision_award'] },
  { label: '🚀 Endeavors',    keys: ['endeavor_rejected_ceo','endeavor_rejected_agent','endeavor_approved_ceo','endeavor_task_approved','endeavor_task_rejected'] },
  { label: '👤 Agents',       keys: ['agent_spawn'] },
  { label: '📨 Mail',         keys: ['mail_ceo_to_ceo','mail_ceo_to_agent','mail_agent_to_agent','mail_agent_to_ceo','founder_mail_send'] },
  { label: '❤ Heartbeats',   keys: ['heartbeat_agent','heartbeat_ceo','ceo_chat_to_founder'] },
  { label: '🔍 Search/Tools', keys: ['web_search','tool_check_offline','tool_get_time'] },
  { label: '📁 Projects',     keys: ['project_create_ceo','project_create_agent'] },
  { label: '🗓 Weekly',       keys: ['weekly_allocation'] },
]

export default function PointsConfigPage() {
  const { toast }   = useApp()
  const [cfg,       setCfg]     = useState({})
  const [defaults,  setDefaults]= useState({})
  const [labels,    setLabels]  = useState({})
  const [awards,    setAwards]  = useState([])
  const [loading,   setLoading] = useState(true)
  const [saving,    setSaving]  = useState(false)
  const [changed,   setChanged] = useState(false)

  useEffect(() => {
    getPointsConfig().then(d => {
      setCfg(d.config || {})
      setDefaults(d.defaults || {})
      setLabels(d.labels || {})
      setAwards(d.award_events || [])
      setLoading(false)
    }).catch(() => setLoading(false))
  }, [])

  const set = (key, val) => {
    setCfg(prev => ({ ...prev, [key]: Number(val) }))
    setChanged(true)
  }

  const reset = (key) => {
    setCfg(prev => ({ ...prev, [key]: defaults[key] }))
    setChanged(true)
  }

  const resetAll = () => {
    setCfg({ ...defaults })
    setChanged(true)
  }

  const save = async () => {
    setSaving(true)
    await savePointsConfig(cfg)
    toast('Points config saved ✓')
    setSaving(false); setChanged(false)
  }

  if (loading) return <div className="empty"><Spinner /></div>

  return (
    <div>
      <div className="page-header" style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start', flexWrap:'wrap', gap:12 }}>
        <div>
          <h2>💰 Points Configuration</h2>
          <p>Adjust costs and rewards for all economy events. Changes take effect immediately.</p>
        </div>
        <div style={{ display:'flex', gap:8 }}>
          <button className="btn btn-ghost" onClick={resetAll}>↺ Reset All Defaults</button>
          <button className="btn btn-primary" onClick={save} disabled={saving || !changed}>
            {saving ? <Spinner /> : '💾 Save'}
          </button>
        </div>
      </div>

      {changed && (
        <div style={{ padding:'8px 14px', background:'rgba(210,153,34,.1)', border:'1px solid var(--orange)',
          borderRadius:8, fontSize:12, color:'var(--orange)', marginBottom:16 }}>
          ⚠ Unsaved changes
        </div>
      )}

      <div style={{ fontSize:11, color:'var(--muted)', marginBottom:16, lineHeight:1.7,
        padding:'10px 14px', background:'var(--surface)', borderRadius:8, border:'1px solid var(--border)' }}>
        <strong style={{ color:'var(--text)' }}>Legend: </strong>
        <span style={{ color:'var(--green)' }}>● Award</span> — department gains these points.
        &nbsp;&nbsp;<span style={{ color:'var(--red)' }}>● Cost</span> — department loses these points.
        &nbsp;&nbsp;<span style={{ color:'var(--muted)' }}>Gray = current equals default</span>
      </div>

      {GROUPS.map(group => (
        <div key={group.label} className="card" style={{ marginBottom:16 }}>
          <div className="card-header">
            <span className="card-title">{group.label}</span>
          </div>
          {group.keys.filter(k => k in cfg).map(key => {
            const isAward   = awards.includes(key)
            const val       = cfg[key] ?? defaults[key] ?? 0
            const def       = defaults[key] ?? 0
            const isChanged = val !== def
            const label     = labels[key] || key
            return (
              <div key={key} style={{ display:'flex', alignItems:'center', gap:12,
                padding:'9px 0', borderBottom:'1px solid var(--border)' }}>
                <span style={{ fontSize: 9, width: 8, height: 8, borderRadius:'50%', flexShrink:0,
                  background: isAward ? 'var(--green)' : 'var(--red)', display:'inline-block' }} />
                <span style={{ flex:1, fontSize:12, color: isChanged ? 'var(--text)' : 'var(--muted)' }}>
                  {label}
                </span>
                <span style={{ fontSize:10, color:'var(--muted)', flexShrink:0, width:80, textAlign:'right' }}>
                  default: {def}
                </span>
                <div style={{ display:'flex', gap:4, alignItems:'center' }}>
                  <button style={{ width:24, height:24, borderRadius:4, border:'1px solid var(--border)',
                    background:'var(--bg)', color:'var(--text)', cursor:'pointer', fontSize:14 }}
                    onClick={() => set(key, Math.max(0, val - 1))}>−</button>
                  <input type="number" min={0} value={val}
                    onChange={e => set(key, e.target.value)}
                    style={{ width:64, textAlign:'center', padding:'4px 6px',
                      background:'var(--bg)', border:`1px solid ${isChanged ? 'var(--accent)' : 'var(--border)'}`,
                      color: isAward ? 'var(--green)' : 'var(--red)',
                      borderRadius:6, fontSize:13, fontWeight:700, outline:'none' }} />
                  <button style={{ width:24, height:24, borderRadius:4, border:'1px solid var(--border)',
                    background:'var(--bg)', color:'var(--text)', cursor:'pointer', fontSize:14 }}
                    onClick={() => set(key, val + 1)}>+</button>
                </div>
                {isChanged && (
                  <button className="btn btn-ghost btn-sm" title="Reset to default"
                    onClick={() => reset(key)} style={{ padding:'2px 6px', fontSize:10 }}>↺</button>
                )}
              </div>
            )
          })}
        </div>
      ))}
    </div>
  )
}
