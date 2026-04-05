import React from 'react'
import { COLORS } from '../../constants'
export default function DeptTag({ id, style }) {
  return <span className="dept-tag" style={{ background: COLORS[id] || '#607D8B', ...style }}>{id}</span>
}
