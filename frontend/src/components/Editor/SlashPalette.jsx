import React, { useState, useEffect, useRef } from 'react'
import { SLASH_BLOCKS } from './editorBlocks'

export default function SlashPalette({ pos, onSelect, onClose }) {
  const [query, setQuery]   = useState('')
  const [cursor, setCursor] = useState(0)
  const ref = useRef(null)

  const filtered = query.trim()
    ? SLASH_BLOCKS.filter(b =>
        b.n.toLowerCase().includes(query.toLowerCase()) ||
        b.d.toLowerCase().includes(query.toLowerCase()))
    : SLASH_BLOCKS

  useEffect(() => { setCursor(0) }, [query])
  useEffect(() => { ref.current?.focus() }, [])

  useEffect(() => {
    const h = e => {
      if (e.key === 'ArrowDown') { e.preventDefault(); setCursor(c => Math.min(c+1, filtered.length-1)) }
      if (e.key === 'ArrowUp')   { e.preventDefault(); setCursor(c => Math.max(c-1, 0)) }
      if (e.key === 'Enter')     { e.preventDefault(); if (filtered[cursor]) onSelect(filtered[cursor]) }
      if (e.key === 'Escape')    { onClose() }
    }
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [cursor, filtered, onSelect, onClose])

  let lastGroup = null
  return (
    <div className="slash-pal" style={{ top: pos.top, left: pos.left }}>
      <input ref={ref} className="slash-search" placeholder="Search blocks…"
        value={query} onChange={e => setQuery(e.target.value)} />
      <div>
        {filtered.length === 0 && (
          <div style={{ padding: '16px', textAlign: 'center', color: 'var(--muted)', fontSize: 13 }}>No results</div>
        )}
        {filtered.map((b, i) => {
          const showGroup = b.g !== lastGroup; lastGroup = b.g
          return (
            <React.Fragment key={i}>
              {showGroup && <div className="slash-grp">{b.g}</div>}
              <div className={`slash-item${i === cursor ? ' sel' : ''}`}
                onClick={() => onSelect(b)} onMouseEnter={() => setCursor(i)}>
                <div className="slash-ico">{b.ic}</div>
                <div><div className="slash-name">{b.n}</div><div className="slash-desc">{b.d}</div></div>
              </div>
            </React.Fragment>
          )
        })}
      </div>
    </div>
  )
}
