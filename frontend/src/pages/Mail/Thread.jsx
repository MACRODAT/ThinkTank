import React, { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate, useLocation } from 'react-router-dom'
import { getThread, getMailChain, getMailById, markRead } from '../../api'
import { COLORS } from '../../constants'
import Spinner from '../../components/UI/Spinner'
import DeptTag from '../../components/UI/DeptTag'
import MarkdownPreview from '../../components/Editor/MarkdownPreview'

const PRIORITY_COLOR = { urgent:'var(--red)', high:'var(--orange)', normal:'var(--muted)' }

function MailCard({ m, highlight = false, depth = 0, label = null }) {
  const [expanded, setExpanded] = useState(true)
  return (
    <div style={{
      marginLeft: depth * 16,
      border: `1px solid ${highlight ? 'var(--accent)' : 'var(--border)'}`,
      borderLeft: `4px solid ${COLORS[m.from_dept] || '#607D8B'}`,
      borderRadius: 10,
      background: highlight ? 'rgba(88,166,255,.04)' : 'var(--surface)',
      overflow: 'hidden',
      transition: 'all 0.15s',
    }}>
      {/* Header row */}
      <div style={{
        display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap',
        padding: '10px 16px',
        background: 'var(--bg)',
        cursor: 'pointer',
        borderBottom: expanded ? '1px solid var(--border)' : 'none',
      }} onClick={() => setExpanded(e => !e)}>
        {label && (
          <span style={{ fontSize: 9, fontWeight: 800, textTransform: 'uppercase',
            color: label === 'Current' ? 'var(--accent)' : 'var(--muted)',
            background: label === 'Current' ? 'rgba(88,166,255,.15)' : 'rgba(139,148,158,.1)',
            padding: '1px 6px', borderRadius: 4, flexShrink: 0 }}>
            {label}
          </span>
        )}
        <DeptTag id={m.from_dept} />
        <span style={{ fontSize: 12, color: 'var(--muted)' }}>→</span>
        <DeptTag id={m.to_dept} />
        <span style={{ flex: 1, fontSize: 13, fontWeight: 600, minWidth: 0,
          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {m.subject}
        </span>
        <span style={{ fontSize: 10, fontWeight: 700, color: PRIORITY_COLOR[m.priority] || 'var(--muted)',
          textTransform: 'uppercase', flexShrink: 0 }}>{m.priority}</span>
        <span style={{ fontSize: 11, color: 'var(--muted)', flexShrink: 0 }}>
          {m.created_at?.substring(0, 16).replace('T', ' ')}
        </span>
        <span style={{ fontSize: 11, color: 'var(--muted)', flexShrink: 0 }}>{expanded ? '▲' : '▼'}</span>
      </div>

      {expanded && (
        <div style={{ padding: '14px 20px' }}>
          <MarkdownPreview content={m.body || ''} />
          {m.metadata && m.metadata !== '{}' && (
            <details style={{ marginTop: 10 }}>
              <summary style={{ fontSize: 11, color: 'var(--muted)', cursor: 'pointer' }}>Metadata</summary>
              <pre style={{ fontSize: 10, color: 'var(--muted)', marginTop: 6 }}>{m.metadata}</pre>
            </details>
          )}
        </div>
      )}
    </div>
  )
}

export default function Thread() {
  const { tid }      = useParams()
  const navigate     = useNavigate()
  const location     = useLocation()
  // Optional: if coming from mail list with a specific mail_id highlighted
  const highlightId  = location.state?.mail_id || null

  const [thread,   setThread]   = useState([])
  const [chain,    setChain]    = useState([])  // ref_mail_prev chain
  const [chainMap, setChainMap] = useState({})  // id → mail
  const [loading,  setLoading]  = useState(true)
  const [view,     setView]     = useState('thread') // 'thread' | 'chain'

  const load = useCallback(async () => {
    setLoading(true)
    const msgs = await getThread(tid).catch(() => [])
    setThread(msgs)
    // Also load reply-chain for the most recent mail (or highlighted one)
    const targetId = highlightId || msgs[msgs.length - 1]?.id
    if (targetId) {
      const ch = await getMailChain(targetId).catch(() => [])
      setChain(ch)
      const map = {}
      ch.forEach(m => { map[m.id] = m })
      msgs.forEach(m => { map[m.id] = m })
      setChainMap(map)
    }
    // Mark unread as read
    for (const m of msgs) {
      if (m.status === 'unread') await markRead(m.id).catch(() => {})
    }
    setLoading(false)
  }, [tid, highlightId])

  useEffect(() => { load() }, [load])

  const first = thread[0] || chain[0] || {}

  // Merge thread + chain without duplicates, sorted by date
  const allMails = Object.values(chainMap).sort((a, b) =>
    (a.created_at || '').localeCompare(b.created_at || '')
  )

  return (
    <div>
      <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 16, flexWrap: 'wrap' }}>
        <button className="btn btn-ghost btn-sm" onClick={() => navigate('/mail')}>← Mail Room</button>
        <h2 style={{ flex: 1, fontSize: 18, fontWeight: 800, margin: 0 }}>
          {first.subject || 'Thread'}
        </h2>
        <div className="toggle-wrap">
          <button className={`toggle-opt${view === 'thread' ? ' on' : ''}`} onClick={() => setView('thread')}>
            📧 Thread ({thread.length})
          </button>
          <button className={`toggle-opt${view === 'chain' ? ' on' : ''}`} onClick={() => setView('chain')}>
            🔗 Full Chain ({allMails.length})
          </button>
        </div>
      </div>

      {loading ? (
        <div className="empty"><Spinner /></div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {view === 'thread' ? (
            // Standard thread view
            thread.length === 0 ? (
              <div className="empty">No messages found</div>
            ) : thread.map((m, i) => (
              <MailCard key={m.id} m={m}
                highlight={m.id === highlightId}
                label={i === 0 ? 'First' : i === thread.length - 1 ? 'Latest' : null} />
            ))
          ) : (
            // Full chain view — shows all referenced prior mails
            allMails.length === 0 ? (
              <div className="empty">No chain data</div>
            ) : (
              <>
                <div style={{ fontSize: 12, color: 'var(--muted)', padding: '8px 12px',
                  background: 'rgba(88,166,255,.05)', border: '1px solid rgba(88,166,255,.15)',
                  borderRadius: 8, marginBottom: 4 }}>
                  🔗 Full conversation chain — {allMails.length} messages tracked via{' '}
                  <code>ref_mail_prev</code> links. Oldest first.
                </div>
                {allMails.map((m, i) => (
                  <MailCard key={m.id} m={m}
                    highlight={m.id === highlightId || thread.some(t => t.id === m.id)}
                    depth={0}
                    label={
                      m.id === highlightId ? 'Current'
                      : thread.some(t => t.id === m.id) ? 'This thread'
                      : 'Referenced'
                    } />
                ))}
              </>
            )
          )}
        </div>
      )}
    </div>
  )
}
