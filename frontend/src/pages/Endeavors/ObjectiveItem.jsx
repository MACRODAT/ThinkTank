import React, { useState, useEffect, useRef, useCallback } from 'react'
import { toggleObjective, updateObjective, deleteObjective, startTimer, stopTimer, getTimeLog } from '../../api'
import { useApp } from '../../context/AppContext'

function fmtSeconds(s) {
  if (!s) return '0m'
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60
  if (h > 0) return `${h}h ${m}m`
  if (m > 0) return `${m}m ${sec}s`
  return `${sec}s`
}

export default function ObjectiveItem({ obj, onChanged, readOnly = false }) {
  const { toast } = useApp()
  const [done,       setDone]       = useState(obj.is_done)
  const [title,      setTitle]      = useState(obj.title)
  const [notes,      setNotes]      = useState(obj.notes || '')
  const [editing,    setEditing]    = useState(false)
  const [showNotes,  setShowNotes]  = useState(false)
  const [savingNote, setSavingNote] = useState(false)

  // Time tracking
  const [totalSec,   setTotalSec]   = useState(obj.total_seconds || 0)
  const [activeLog,  setActiveLog]  = useState(obj.active_log_id ? { id: obj.active_log_id, started_at: obj.active_since } : null)
  const [elapsed,    setElapsed]    = useState(0)
  const timerRef = useRef(null)

  // Tick when active
  useEffect(() => {
    if (activeLog) {
      const start = new Date(activeLog.started_at)
      const tick = () => setElapsed(Math.floor((Date.now() - start.getTime()) / 1000))
      tick()
      timerRef.current = setInterval(tick, 1000)
    } else {
      setElapsed(0)
      clearInterval(timerRef.current)
    }
    return () => clearInterval(timerRef.current)
  }, [activeLog])

  const refreshTime = useCallback(async () => {
    const data = await getTimeLog(obj.id).catch(() => null)
    if (!data) return
    setTotalSec(data.total_seconds || 0)
    setActiveLog(data.active_log || null)
  }, [obj.id])

  const toggle = async () => {
    const res = await toggleObjective(obj.id)
    setDone(res.is_done)
    onChanged?.()
  }

  const saveTitle = async () => {
    if (!title.trim()) return
    await updateObjective(obj.id, { title: title.trim() })
    setEditing(false)
    onChanged?.()
  }

  const saveNotes = async () => {
    setSavingNote(true)
    await updateObjective(obj.id, { notes }).catch(() => {})
    setSavingNote(false)
    toast('Notes saved ✓')
  }

  const del = async () => {
    if (!confirm('Delete this objective?')) return
    await deleteObjective(obj.id)
    onChanged?.()
  }

  const handleStart = async () => {
    const res = await startTimer(obj.id)
    if (res.ok) { await refreshTime(); toast('Timer started') }
    else toast(res.error || 'Already running', 'error')
  }

  const handleStop = async () => {
    const res = await stopTimer(obj.id)
    if (res.ok) { await refreshTime(); toast(`Logged ${fmtSeconds(res.duration_seconds)}`) }
    else toast(res.error || 'No active timer', 'error')
  }

  const isTracking = !!activeLog
  const displayTime = totalSec + elapsed

  return (
    <div className={`obj-item${done ? ' obj-done' : ''}`}>
      {/* Main row */}
      <div className="obj-row">
        <button className="obj-check" onClick={toggle}>
          {done ? '✓' : ''}
        </button>

        {editing ? (
          <input className="obj-title-edit"
            value={title} onChange={e => setTitle(e.target.value)}
            onBlur={saveTitle}
            onKeyDown={e => { if(e.key==='Enter') saveTitle(); if(e.key==='Escape'){setTitle(obj.title);setEditing(false)} }}
            autoFocus />
        ) : (
          <span className="obj-title" onClick={() => !readOnly && setEditing(true)}>
            {title}
          </span>
        )}

        <div className="obj-actions">
          {/* Time display */}
          {displayTime > 0 && (
            <span className={`obj-time${isTracking?' obj-time-active':''}`}>
              {isTracking ? `▶ ${fmtSeconds(displayTime)}` : `⏱ ${fmtSeconds(displayTime)}`}
            </span>
          )}

          {/* Timer controls */}
          {!readOnly && !done && (
            isTracking
              ? <button className="btn btn-danger btn-sm" onClick={handleStop} title="Stop timer">⏹ Stop</button>
              : <button className="btn btn-outline btn-sm" onClick={handleStart} title="Start timer">▶ Start</button>
          )}

          {/* Notes toggle */}
          <button className="btn btn-ghost btn-sm" onClick={() => setShowNotes(v => !v)} title="Notes">
            {notes ? '📝' : '📄'} {showNotes ? '▲' : '▼'}
          </button>

          {!readOnly && (
            <>
              <button className="btn btn-outline btn-sm" onClick={() => setEditing(true)} title="Edit">✏</button>
              <button className="btn btn-danger  btn-sm" onClick={del} title="Delete">🗑</button>
            </>
          )}
        </div>
      </div>

      {/* Notes panel */}
      {showNotes && (
        <div className="obj-notes-panel">
          <textarea
            className="obj-notes-input"
            placeholder="Add notes for this objective…"
            value={notes}
            onChange={e => setNotes(e.target.value)}
            readOnly={readOnly}
            rows={3}
          />
          {!readOnly && (
            <div style={{ display:'flex', gap:8, marginTop:6 }}>
              <button className="btn btn-success btn-sm" onClick={saveNotes} disabled={savingNote}>
                {savingNote ? '⏳' : '💾 Save Notes'}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
