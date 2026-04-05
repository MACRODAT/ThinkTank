import React, { useEffect } from 'react'
export default function Modal({ open, onClose, children, wide, fullish }) {
  useEffect(() => {
    const h = e => { if (e.key === 'Escape') onClose?.() }
    if (open) window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [open, onClose])
  if (!open) return null
  return (
    <div className="modal-overlay" onClick={e => { if (e.target === e.currentTarget) onClose?.() }}>
      <div className={`modal-box${wide ? ' modal-wide' : ''}${fullish ? ' modal-fullish' : ''}`}>
        {children}
      </div>
    </div>
  )
}
