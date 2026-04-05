import { API_BASE } from './constants'

async function req(path, opts = {}) {
  const res = await fetch(API_BASE + path, {
    headers: { 'Content-Type': 'application/json', ...opts.headers },
    ...opts,
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  })
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

// Departments
export const getDepartments   = ()    => req('/departments')
export const getDepartment    = (id)  => req(`/departments/${id}`)
export const runDepartment    = (id)  => req(`/departments/${id}/run`, { method: 'POST' })
export const runAllDepts      = ()    => req('/departments/run-all',   { method: 'POST' })

// Drafts
export const getDrafts        = (limit = 100) => req(`/drafts?limit=${limit}`)
export const getPendingDrafts = (deptId)      => req(`/drafts/pending${deptId ? `?dept_id=${deptId}` : ''}`)
export const getDraft         = (id)          => req(`/drafts/${id}`)
export const getDraftStats    = ()            => req('/drafts/stats')
export const createDraft      = (body)        => req('/drafts', { method: 'POST', body })
export const reviewDraft      = (id, action)  => req(`/drafts/${id}/review`, { method: 'POST', body: { action } })
export const updateDraft      = (id, body)    => req(`/drafts/${id}/update`, { method: 'POST', body })

// Mail
export const getAllMail  = (limit = 100)            => req(`/mail?limit=${limit}`)
export const getDeptMail = (deptId, limit = 50)     => req(`/mail/${deptId}/all?limit=${limit}`)
export const getThread   = (threadId)               => req(`/mail/thread/${threadId}`)
export const markRead    = (mailId)                 => req(`/mail/${mailId}/read`, { method: 'POST' })

// Projects
export const getProjects   = (params = {}) => {
  const qs = new URLSearchParams(params).toString()
  return req(`/admin/projects${qs ? '?' + qs : ''}`)
}
export const getProject    = (id)        => req(`/admin/projects/${id}`)
export const createProject = (body)      => req('/admin/projects',       { method: 'POST',   body })
export const updateProject = (id, body)  => req(`/admin/projects/${id}`, { method: 'POST',   body })
export const deleteProject = (id)        => req(`/admin/projects/${id}`, { method: 'DELETE' })

// Dept prompt
export const getDeptPrompt  = (id)       => req(`/admin/dept-prompt/${id}`)
export const saveDeptPrompt = (id, body) => req(`/admin/dept-prompt/${id}`, { method: 'POST', body })

// Audit
export const getAuditLog = (limit = 100) => req(`/admin/audit?limit=${limit}`)

// Settings
export const getSettings    = ()     => req('/settings')
export const saveSettings   = (body) => req('/settings', { method: 'POST', body })
export const probeOllama    = (url)  => req(`/settings/ollama-models?base_url=${encodeURIComponent(url)}`)
export const getThinkingLog = (limit = 50) => req(`/settings/thinking-log?limit=${limit}`)
