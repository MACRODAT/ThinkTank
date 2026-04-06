import React, { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { getHeartbeatStatus } from '../../api'
import { COLORS } from '../../constants'

function AgentPill({ name, deptId, label, pulse, color }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 8,
      padding: '6px 12px', borderRadius: 20,
      background: color ? `${color}18` : 'var(--surface)',
      border: `1px solid ${color || 'var(--border)'}`,
      fontSize: 12, fontWeight: 600,
    }}>
      {pulse && (
        <span style={{
          width: 8, height: 8, borderRadius: '50%',
          background: color || 'var(--green)',
          animation: 'pulse 1.4s infinite',
          flexShrink: 0,
        }} />
      )}
      <span style={{ color: 'var(--muted)', fontSize: 10, textTransform: 'uppercase', marginRight: 2 }}>{label}</span>
      <span style={{ color: 'var(--text)' }}>{name || '—'}</span>
      {deptId && (
        <span style={{ fontSize: 10, fontWeight: 700, padding: '1px 5px', borderRadius: 3,
          background: COLORS[deptId] || '#607D8B', color: '#fff' }}>{deptId}</span>
      )}
    </div>
  )
}

export default function HeartbeatMonitor({ compact = false }) {
  const navigate = useNavigate()
  const [status,   setStatus]   = useState(null)
  const [elapsed,  setElapsed]  = useState(0)
  const startRef = useRef(null)

  useEffect(() => {
    const load = () => getHeartbeatStatus().then(s => {
      setStatus(s)
      if (s.current_started_at) {
        startRef.current = new Date(s.current_started_at)
      } else {
        startRef.current = null
      }
    }).catch(() => {})
    load()
    const t = setInterval(load, 4000)
    return () => clearInterval(t)
  }, [])

  // Tick elapsed timer
  useEffect(() => {
    const t = setInterval(() => {
      if (startRef.current) {
        setElapsed(Math.floor((Date.now() - startRef.current.getTime()) / 1000))
      } else {
        setElapsed(0)
      }
    }, 1000)
    return () => clearInterval(t)
  }, [])

  if (!status) return null

  const isRunning = !!status.current_agent_id
  const history   = status.history || []
  const queue     = status.queue   || []
  const tick      = status.tick    || 0

  if (compact) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        {isRunning ? (
          <AgentPill name={status.current_agent_name} label="▶" pulse color="var(--green)" />
        ) : (
          <span style={{ fontSize: 11, color: 'var(--muted)', padding: '4px 10px' }}>⏸ Idle</span>
        )}
        {status.next_agent_name && (
          <AgentPill name={status.next_agent_name} label="Next" color="var(--accent)" />
        )}
        <span style={{ fontSize: 10, color: 'var(--muted)' }}>Tick {tick}</span>
      </div>
    )
  }

  return (
    <div className="hb-monitor">
      {/* Header */}
      <div className="hb-header">
        <span style={{ fontSize: 12, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '.06em', color: 'var(--muted)' }}>
          ❤ Heartbeat Monitor
        </span>
        <span style={{ fontSize: 11, color: 'var(--muted)', marginLeft: 'auto' }}>Tick {tick}</span>
      </div>

      {/* Current / Next */}
      <div style={{ display: 'flex', gap: 10, padding: '12px 14px', borderBottom: '1px solid var(--border)' }}>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', color: 'var(--muted)', marginBottom: 5 }}>Running Now</div>
          {isRunning ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ width: 9, height: 9, borderRadius: '50%', background: 'var(--green)', animation: 'pulse 1.4s infinite', flexShrink: 0 }} />
              <div>
                <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text)' }}>{status.current_agent_name}</div>
                <div style={{ fontSize: 11, color: 'var(--muted)' }}>Running for {elapsed}s</div>
              </div>
            </div>
          ) : (
            <div style={{ fontSize: 13, color: 'var(--muted)', fontStyle: 'italic' }}>Idle…</div>
          )}
        </div>

        <div style={{ width: 1, background: 'var(--border)' }} />

        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', color: 'var(--muted)', marginBottom: 5 }}>Up Next</div>
          {status.next_agent_name ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ width: 9, height: 9, borderRadius: '50%', background: 'var(--accent)', opacity: 0.6, flexShrink: 0 }} />
              <div style={{ fontSize: 13, color: 'var(--text)' }}>{status.next_agent_name}</div>
            </div>
          ) : (
            <div style={{ fontSize: 13, color: 'var(--muted)', fontStyle: 'italic' }}>—</div>
          )}
        </div>
      </div>

      {/* Queue */}
      {queue.length > 0 && (
        <div style={{ padding: '8px 14px', borderBottom: '1px solid var(--border)' }}>
          <div style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', color: 'var(--muted)', marginBottom: 5 }}>
            Queue ({queue.length})
          </div>
          <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
            {queue.slice(0, 8).map((a, i) => (
              <span key={a.id} style={{
                fontSize: 11, padding: '2px 8px', borderRadius: 10,
                background: i === 0 && isRunning ? 'rgba(63,185,80,.15)' : 'var(--bg)',
                border: `1px solid ${i === 0 && isRunning ? 'var(--green)' : 'var(--border)'}`,
                color: i === 0 && isRunning ? 'var(--green)' : 'var(--muted)',
              }}>
                {a.name.split(' ')[0]}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* History */}
      <div style={{ padding: '8px 14px' }}>
        <div style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', color: 'var(--muted)', marginBottom: 6 }}>
          Recent Activity
        </div>
        {history.length === 0 ? (
          <div style={{ fontSize: 12, color: 'var(--muted)', fontStyle: 'italic' }}>No activity yet</div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4, maxHeight: 220, overflowY: 'auto' }}>
            {history.map((h, i) => (
              <div key={i} style={{ display: 'flex', gap: 8, alignItems: 'flex-start', padding: '5px 0',
                borderBottom: i < history.length - 1 ? '1px solid var(--border)' : 'none' }}>
                <span style={{ fontSize: 12 }}>{h.ok ? '✅' : '❌'}</span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text)' }}>{h.agent_name}</span>
                    <span style={{ fontSize: 9, fontWeight: 700, padding: '1px 5px', borderRadius: 3,
                      background: COLORS[h.dept_id] || '#607D8B', color: '#fff', flexShrink: 0 }}>{h.dept_id}</span>
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {h.summary}
                  </div>
                  {h.actions && h.actions.length > 0 && (
                    <div style={{ fontSize: 10, color: 'var(--accent)', marginTop: 2 }}>
                      {h.actions.slice(0, 3).join(' · ')}
                    </div>
                  )}
                </div>
                <span style={{ fontSize: 10, color: 'var(--muted)', whiteSpace: 'nowrap', flexShrink: 0 }}>
                  {h.ran_at?.substring(11, 16)}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
