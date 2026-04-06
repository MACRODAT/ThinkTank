import React, { useState, useEffect, useRef } from 'react'
import { chatWithAgent, clearAgentChat } from '../../api'
import { useApp } from '../../context/AppContext'
import { COLORS } from '../../constants'
import Spinner from '../../components/UI/Spinner'
import MarkdownPreview from '../../components/Editor/MarkdownPreview'

function AgentAvatar({ agent, size = 36 }) {
  if (agent.profile_image_url) {
    return <img src={agent.profile_image_url} alt={agent.name}
      style={{ width:size, height:size, borderRadius:'50%', objectFit:'cover', flexShrink:0 }} />
  }
  const initials = (agent.name||'?').split(' ').map(w=>w[0]).join('').toUpperCase().slice(0,2)
  return (
    <div style={{
      width:size, height:size, borderRadius:'50%',
      background: COLORS[agent.dept_id] || '#607D8B',
      display:'flex', alignItems:'center', justifyContent:'center',
      fontSize: size * 0.35, fontWeight:800, color:'#fff', flexShrink:0,
      border: agent.is_ceo ? '2px solid gold' : '2px solid var(--border)',
    }}>
      {initials}
    </div>
  )
}

export default function AgentChat({ agent, initialHistory = [] }) {
  const { toast } = useApp()
  const [messages,  setMessages]  = useState(initialHistory)
  const [input,     setInput]     = useState('')
  const [sending,   setSending]   = useState(false)
  const bottomRef = useRef(null)

  useEffect(() => {
    // Build messages from chat_history
    if (initialHistory.length > 0) {
      setMessages(initialHistory.map(h => ({ role: h.role, content: h.content })))
    }
  }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const send = async () => {
    if (!input.trim() || sending) return
    const userMsg = input.trim()
    setInput('')
    setMessages(prev => [...prev, { role:'user', content:userMsg }])
    setSending(true)
    try {
      const res = await chatWithAgent(agent.id, userMsg)
      setMessages(prev => [...prev, { role:'assistant', content: res.reply }])
    } catch(e) {
      toast('Chat error: ' + e.message, 'error')
      setMessages(prev => [...prev, { role:'assistant', content:`⚠ Error: ${e.message}` }])
    }
    setSending(false)
  }

  const clearHistory = async () => {
    if (!confirm('Clear chat history?')) return
    await clearAgentChat(agent.id).catch(()=>{})
    setMessages([])
    toast('Chat cleared')
  }

  const handleKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() }
  }

  const color = COLORS[agent.dept_id] || '#607D8B'

  return (
    <div className="agent-chat">
      {/* Chat header */}
      <div className="agent-chat-header" style={{ borderBottom:`2px solid ${color}30` }}>
        <AgentAvatar agent={agent} size={40} />
        <div style={{ flex:1 }}>
          <div style={{ fontWeight:700, fontSize:14 }}>{agent.name}</div>
          <div style={{ fontSize:11, color:'var(--muted)' }}>
            {agent.title || agent.role}
            {agent.is_ceo && <span style={{ marginLeft:6, color:'gold' }}>👑</span>}
            <span className="dept-tag" style={{ background:color, marginLeft:6, fontSize:9 }}>{agent.dept_id}</span>
          </div>
        </div>
        <button className="btn btn-ghost btn-sm" onClick={clearHistory} title="Clear history">🗑 Clear</button>
      </div>

      {/* Messages */}
      <div className="agent-chat-body">
        {messages.length === 0 && (
          <div style={{ textAlign:'center', padding:'32px 20px', color:'var(--muted)', fontSize:13 }}>
            <div style={{ fontSize:32, marginBottom:8 }}>💬</div>
            <div>Start a conversation with {agent.name}</div>
            <div style={{ fontSize:11, marginTop:4 }}>Ask questions, request reports, give directives</div>
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`chat-msg chat-msg-${m.role}`}>
            {m.role === 'assistant' ? (
              <div style={{ display:'flex', gap:10, alignItems:'flex-start' }}>
                <AgentAvatar agent={agent} size={28} />
                <div className="chat-bubble chat-bubble-agent">
                  <MarkdownPreview content={m.content} className="chat-md" />
                </div>
              </div>
            ) : (
              <div style={{ display:'flex', gap:10, alignItems:'flex-start', justifyContent:'flex-end' }}>
                <div className="chat-bubble chat-bubble-user">{m.content}</div>
                <div style={{ width:28, height:28, borderRadius:'50%', background:'var(--accent)',
                  display:'flex', alignItems:'center', justifyContent:'center', fontSize:12,
                  fontWeight:800, color:'#000', flexShrink:0 }}>
                  F
                </div>
              </div>
            )}
          </div>
        ))}
        {sending && (
          <div style={{ display:'flex', gap:10, alignItems:'center', padding:'8px 0' }}>
            <AgentAvatar agent={agent} size={28} />
            <div className="chat-bubble chat-bubble-agent chat-typing">
              <span/>  <span/> <span/>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="agent-chat-footer">
        <textarea
          className="agent-chat-input"
          placeholder={`Message ${agent.name}… (Enter to send, Shift+Enter for newline)`}
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKey}
          rows={1}
          style={{ resize:'none' }}
          disabled={sending}
        />
        <button
          className="btn btn-primary"
          onClick={send}
          disabled={sending || !input.trim()}
          style={{ flexShrink:0 }}
        >
          {sending ? <Spinner/> : '➤ Send'}
        </button>
      </div>
    </div>
  )
}
