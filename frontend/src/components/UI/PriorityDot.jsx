import React from 'react'
import { PRIO_COLORS } from '../../constants'
export default function PriorityDot({ priority, style }) {
  return <span className="prio-dot" style={{ background: PRIO_COLORS[priority] || '#8b949e', marginTop: 4, ...style }} />
}
