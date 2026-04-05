import React, { useMemo } from 'react'
import { marked } from 'marked'

// Configure marked once
marked.setOptions({ gfm: true, breaks: true })

export default function MarkdownPreview({ content, className = '' }) {
  const html = useMemo(() => {
    if (!content || !content.trim()) return '<p style="color:var(--muted);font-style:italic">Nothing to preview yet…</p>'
    try { return marked.parse(content) }
    catch { return `<pre>${content}</pre>` }
  }, [content])

  return (
    <div
      className={`markdown-body ${className}`}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  )
}
