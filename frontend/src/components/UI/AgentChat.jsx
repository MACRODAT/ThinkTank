import React, { useState, useRef, useEffect } from 'react'
import { chatWithAgent } from '../../api'
import { COLORS } from '../../constants'
import Spinner from './Spinner'

function AgentAvatar({ agent, size = 32 }) {
  if (agent?.profile_image_url) {
    return <img src={agent.profile_image_url} alt={agent.name}
      style={{ width: size, height: size, borderRadius: '50%', objectFit: 'cover', flexShrink: 0 }} />
  }
  const initials = (agent?.name || '?').split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2)
  const bg = COLORS[agent?.dept_id] || '#607D8B'
  return (
    <div style={{
      width: size, height: size, borderRadius: '50%', background: bg,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontSize: size * 0.38, fontWeight: 800, color: '#fff', flexShrink: 0,
      border: agent?.is_ceo ? '2px solid gold' : '1px solid rgba(255,255,255,.2)',
    }}>
      {initials}
    </div>
  )
}

export default function AgentChat({ agent, onClose }) {
  const [messages, setMessages] = useState([
    {
      role: 'agent',
      content: `Hello, Founder. I'm ${agent?.name}, ${agent?.title || agent?.role} of the ${agent?.dept_id} department. How can I assist you?`,
      actions: [],
    }
  ])
  const [input,   setInput]   = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef(null)
  const inputRef  = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  const send = async () => {
    const msg = input.trim()
    if (!msg || loading) return
    setInput('')
    setMessages(prev => [...prev, { role: 'founder', content: msg }])
    setLoading(true)

    try {
      const res = await chatWithAgent(agent.id, msg)
      if (res.ok) {
        setMessages(prev => [...prev, {
          role: 'agent',
          content: res.reply || '(No response)',
          thinking: res.thinking,
          actions: res.actions_taken || [],
        }])
      } else {
        setMessages(prev => [...prev, {
          role: 'system',
          content: `Error: ${res.error || 'Agent unavailable'}`,
        }])
      }
    } catch (e) {
      setMessages(prev => [...prev, { role: 'system', content: `Network error: ${e.message}` }])
    }
    setLoading(false)
  }

  const handleKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() }
  }

  const agentColor = COLORS[agent?.dept_id] || '#607D8B'

  return (
    <div className="agent-chat-overlay" onClick={e => { if (e.target === e.currentTarget) onClose?.() }}>
      <div className="agent-chat-box">
        {/* Header */}
        <div className="agent-chat-header" style={{ borderBottom: `2px solid ${agentColor}` }}>
          <AgentAvatar agent={agent} size={40} />
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 700, fontSize: 14 }}>{agent?.name}</div>
            <div style={{ fontSize: 11, color: 'var(--muted)' }}>
              {agent?.title || agent?.role} ·
              <span className="dept-tag" style={{ background: agentColor, marginLeft: 6, fontSize: 10 }}>
                {agent?.dept_id}
              </span>
              {agent?.is_ceo && <span style={{ marginLeft: 6, fontSize: 10, color: 'gold' }}>👑 CEO</span>}
            </div>
          </div>
          <button className="btn btn-ghost btn-sm" onClick={onClose}>✕</button>
        </div>

        {/* Messages */}
        <div className="agent-chat-messages">
          {messages.map((m, i) => (
            <div key={i} className={`chat-msg chat-msg-${m.role}`}>
              {m.role === 'agent' && (
                <div style={{ flexShrink: 0 }}><AgentAvatar agent={agent} size={28} /></div>
              )}
              {m.role === 'founder' && (
                <div style={{ width: 28, height: 28, borderRadius: '50%', background: 'rgba(248,81,73,.2)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 14, flexShrink: 0 }}>
                  👑
                </div>
              )}
              <div className={`chat-bubble chat-bubble-${m.role}`}>
                {m.thinking && (
                  <div style={{ fontSize: 11, color: 'var(--muted)', fontStyle: 'italic',
                    marginBottom: 6, padding: '4px 8px', borderRadius: 4,
                    background: 'rgba(139,148,158,.08)', borderLeft: '2px solid var(--muted)' }}>
                    💭 {m.thinking}
                  </div>
                )}
                <div style={{ fontSize: 13, lineHeight: 1.6, whiteSpace: 'pre-wrap' }}>{m.content}</div>
                {m.actions && m.actions.length > 0 && (
                  <div style={{ marginTop: 8, paddingTop: 6, borderTop: '1px solid rgba(255,255,255,.1)' }}>
                    {m.actions.map((a, j) => (
                      <div key={j} style={{ fontSize: 11, color: 'var(--accent)', marginTop: 2 }}>⚡ {a}</div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}
          {loading && (
            <div className="chat-msg chat-msg-agent">
              <AgentAvatar agent={agent} size={28} />
              <div className="chat-bubble chat-bubble-agent" style={{ padding: '10px 14px' }}>
                <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
                  <span style={{ fontSize: 11, color: 'var(--muted)' }}>{agent?.name} is thinking</span>
                  <Spinner />
                </div>
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <div className="agent-chat-input-row">
          <textarea
            ref={inputRef}
            className="agent-chat-input"
            placeholder={`Message ${agent?.name}… (Enter to send, Shift+Enter for newline)`}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKey}
            rows={2}
          />
          <button className="btn btn-primary" onClick={send} disabled={loading || !input.trim()}>
            Send
          </button>
        </div>
      </div>
    </div>
  )
}
