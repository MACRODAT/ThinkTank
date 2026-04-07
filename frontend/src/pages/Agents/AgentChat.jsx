import React, { useState, useEffect, useRef, useCallback } from 'react'
import { chatWithAgent, clearAgentChat } from '../../api'
import { useApp } from '../../context/AppContext'
import { COLORS } from '../../constants'
import Spinner from '../../components/UI/Spinner'
import MarkdownPreview from '../../components/Editor/MarkdownPreview'

// ─────────────────────────────────────────────────────────────────────────────
// MODULE-LEVEL cache — survives component unmount/remount (tab switches)
// Key: agentId → array of message objects
// ─────────────────────────────────────────────────────────────────────────────
const MESSAGE_CACHE = {}

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────

function AgentAvatar({ agent, size = 36 }) {
  if (agent.profile_image_url) {
    return (
      <img src={agent.profile_image_url} alt={agent.name}
        style={{ width:size, height:size, borderRadius:'50%', objectFit:'cover', flexShrink:0 }} />
    )
  }
  const initials = (agent.name || '?').split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2)
  return (
    <div style={{
      width: size, height: size, borderRadius: '50%',
      background: COLORS[agent.dept_id] || '#607D8B',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontSize: size * 0.35, fontWeight: 800, color: '#fff', flexShrink: 0,
      border: agent.is_ceo ? '2px solid gold' : '2px solid var(--border)',
    }}>
      {initials}
    </div>
  )
}

// Renders one assistant message — shows collapsible tool-call blocks
function AssistantMessage({ content }) {
  const toolRegex = /\[TOOL:([^\]]+)\]\s*([\s\S]*?)\[\/TOOL\]/g
  const parts = []
  let lastIndex = 0
  let match

  while ((match = toolRegex.exec(content)) !== null) {
    if (match.index > lastIndex) {
      parts.push({ type: 'text', content: content.slice(lastIndex, match.index) })
    }
    parts.push({ type: 'tool', name: match[1], result: match[2].trim() })
    lastIndex = match.index + match[0].length
  }
  if (lastIndex < content.length) {
    parts.push({ type: 'text', content: content.slice(lastIndex) })
  }

  if (parts.length === 0) {
    return <MarkdownPreview content={content} className="chat-md" />
  }

  return (
    <div>
      {parts.map((p, i) =>
        p.type === 'text' ? (
          <MarkdownPreview key={i} content={p.content} className="chat-md" />
        ) : (
          <details key={i} className="chat-tool-call">
            <summary>
              <span className="chat-tool-icon">⚙</span>
              <span className="chat-tool-name">{p.name}</span>
            </summary>
            <pre className="chat-tool-result">{p.result}</pre>
          </details>
        )
      )}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Main chat component
// ─────────────────────────────────────────────────────────────────────────────

export default function AgentChat({ agent, initialHistory = [] }) {
  const { toast }   = useApp()
  const agentId     = agent.id
  const color       = COLORS[agent.dept_id] || '#607D8B'

  // Seed MODULE_LEVEL cache on first render for this agent if not yet seeded
  if (!MESSAGE_CACHE[agentId]) {
    MESSAGE_CACHE[agentId] = (initialHistory || []).map(h => ({
      role: h.role,
      content: h.content,
    }))
  }

  // Local state always reads from the module cache
  const [messages, setMessages] = useState(() => MESSAGE_CACHE[agentId])
  const [input,    setInput]    = useState('')
  const [sending,  setSending]  = useState(false)
  const bottomRef  = useRef(null)
  const inputRef   = useRef(null)

  // When agent changes (navigating between agent profiles), re-seed
  useEffect(() => {
    if (!MESSAGE_CACHE[agentId]) {
      MESSAGE_CACHE[agentId] = (initialHistory || []).map(h => ({
        role: h.role,
        content: h.content,
      }))
    }
    setMessages(MESSAGE_CACHE[agentId])
    inputRef.current?.focus()
  }, [agentId]) // eslint-disable-line

  // When the tab is revisited (component remounts), pull from module cache
  useEffect(() => {
    const cached = MESSAGE_CACHE[agentId]
    if (cached && cached.length > 0) {
      setMessages(cached)
    }
  }, []) // runs once on every mount

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Writes to both React state AND the module-level cache
  const addMessage = useCallback((msg) => {
    setMessages(prev => {
      const next = [...prev, msg]
      MESSAGE_CACHE[agentId] = next
      return next
    })
  }, [agentId])

  const send = async () => {
    if (!input.trim() || sending) return
    const text = input.trim()
    setInput('')
    addMessage({ role: 'user', content: text })
    setSending(true)
    try {
      const res = await chatWithAgent(agentId, text)
      addMessage({ role: 'assistant', content: res.reply })
    } catch (e) {
      toast('Chat error: ' + e.message, 'error')
      addMessage({ role: 'assistant', content: `⚠ Error: ${e.message}` })
    }
    setSending(false)
  }

  const clearHistory = async () => {
    if (!confirm(`Clear all chat history with ${agent.name}?`)) return
    await clearAgentChat(agentId).catch(() => {})
    MESSAGE_CACHE[agentId] = []
    setMessages([])
    toast('Chat cleared')
  }

  const handleKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() }
  }

  return (
    <div className="agent-chat">
      {/* ── Header ── */}
      <div className="agent-chat-header" style={{ borderBottom: `2px solid ${color}30` }}>
        <AgentAvatar agent={agent} size={40} />
        <div style={{ flex: 1 }}>
          <div style={{ fontWeight: 700, fontSize: 14 }}>{agent.name}</div>
          <div style={{ fontSize: 11, color: 'var(--muted)' }}>
            {agent.title || agent.role}
            {agent.is_ceo && <span style={{ marginLeft: 6, color: 'gold' }}>👑</span>}
            <span className="dept-tag" style={{ background: color, marginLeft: 6, fontSize: 9 }}>
              {agent.dept_id}
            </span>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          <span style={{ fontSize: 10, color: 'var(--muted)' }}>{messages.length} messages</span>
          <button className="btn btn-ghost btn-sm" onClick={clearHistory}>🗑 Clear</button>
        </div>
      </div>

      {/* ── Tool palette hint ── */}
      <div style={{
        padding: '4px 14px',
        background: 'rgba(88,166,255,0.04)',
        borderBottom: '1px solid var(--border)',
        fontSize: 10, color: 'var(--muted)',
      }}>
        💡 Agent tools: read/write dept files · read/edit drafts · create endeavors · send mail · hire agents
      </div>

      {/* ── Messages ── */}
      <div className="agent-chat-body">
        {messages.length === 0 && (
          <div style={{ textAlign: 'center', padding: '40px 20px', color: 'var(--muted)' }}>
            <div style={{ fontSize: 36, marginBottom: 10 }}>💬</div>
            <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 6 }}>Chat with {agent.name}</div>
            <div style={{ fontSize: 12, lineHeight: 1.6, color: 'var(--muted)' }}>
              Give directives, request reports, or ask about department status.
              <br />The agent can read/write files, drafts, and take direct actions.
            </div>
          </div>
        )}

        {messages.map((m, i) => (
          <div key={i} className={`chat-msg chat-msg-${m.role}`}>
            {m.role === 'assistant' ? (
              <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
                <AgentAvatar agent={agent} size={28} />
                <div className="chat-bubble chat-bubble-agent">
                  <AssistantMessage content={m.content} />
                </div>
              </div>
            ) : (
              <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start', justifyContent: 'flex-end' }}>
                <div className="chat-bubble chat-bubble-user">{m.content}</div>
                <div style={{
                  width: 28, height: 28, borderRadius: '50%',
                  background: 'var(--accent)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 12, fontWeight: 800, color: '#000', flexShrink: 0,
                }}>
                  F
                </div>
              </div>
            )}
          </div>
        ))}

        {sending && (
          <div style={{ display: 'flex', gap: 10, alignItems: 'center', padding: '4px 0' }}>
            <AgentAvatar agent={agent} size={28} />
            <div className="chat-bubble chat-bubble-agent chat-typing">
              <span /><span /><span />
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* ── Input ── */}
      <div className="agent-chat-footer">
        <textarea
          ref={inputRef}
          className="agent-chat-input"
          placeholder={`Message ${agent.name}… (Enter to send, Shift+Enter for newline)`}
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKey}
          rows={1}
          disabled={sending}
        />
        <button
          className="btn btn-primary"
          onClick={send}
          disabled={sending || !input.trim()}
          style={{ flexShrink: 0 }}
        >
          {sending ? <Spinner /> : '➤ Send'}
        </button>
      </div>
    </div>
  )
}
