export const API_BASE = '/api'

export const COLORS = {
  HF:  '#4CAF50',
  FIN: '#2196F3',
  RES: '#9C27B0',
  ING: '#FF9800',
  STR: '#F44336',
}

export const ICONS = {
  HF:  '🩺',
  FIN: '💰',
  RES: '🔬',
  ING: '⚙️',
  STR: '🎯',
}

export const DEPT_NAMES = {
  HF:  'Health & Welfare',
  FIN: 'Finance & Resources',
  RES: 'Research & Intelligence',
  ING: 'Engineering & Science',
  STR: 'Strategy & Planning',
}

export const PRIO_COLORS = {
  urgent: '#f85149',
  high:   '#d29922',
  normal: '#3fb950',
  low:    '#8b949e',
}

export const DEPT_IDS = ['HF', 'FIN', 'RES', 'ING', 'STR']

export const DRAFT_TYPES = [
  { value: 'strategy',             label: 'Strategy' },
  { value: 'comprehensive_report', label: 'Report' },
  { value: 'research_brief',       label: 'Research Brief' },
  { value: 'memo',                 label: 'Memo' },
  { value: 'recommendation',       label: 'Recommendation' },
  { value: 'policy_document',      label: 'Policy Document' },
  { value: 'full_analysis',        label: 'Analysis' },
]

export const PRIORITIES = ['normal', 'high', 'urgent', 'low']

export const PROJECT_STATUSES = ['active', 'paused', 'completed', 'cancelled']
