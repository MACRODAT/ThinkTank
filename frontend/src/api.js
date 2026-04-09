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
export const getDepartments  = ()     => req('/departments')
export const getDepartment   = (id)   => req(`/departments/${id}`)
export const runDepartment   = (id)   => req(`/departments/${id}/run`, { method: 'POST' })
export const runAllDepts     = ()     => req('/departments/run-all',   { method: 'POST' })

// Drafts
export const getDrafts        = (limit=100) => req(`/drafts?limit=${limit}`)
export const getPendingDrafts = (deptId)    => req(`/drafts/pending${deptId ? `?dept_id=${deptId}` : ''}`)
export const getDraft         = (id)        => req(`/drafts/${id}`)
export const getDraftStats    = ()          => req('/drafts/stats')
export const createDraft      = (body)      => req('/drafts',              { method: 'POST', body })
export const reviewDraft      = (id, action, notes, reviewed_by) => req(`/drafts/${id}/review`, { method: 'POST', body: { action, notes, reviewed_by: reviewed_by || 'founder' } })
export const updateDraft      = (id, body)  => req(`/drafts/${id}/update`, { method: 'POST', body })

// Mail
export const getAllMail   = (limit=100) => req(`/mail?limit=${limit}`)
export const getInbox     = (deptId, status='unread') => req(`/mail/${deptId}/inbox?status=${status}`)
export const getDeptMail  = (deptId, limit=50)        => req(`/mail/${deptId}/all?limit=${limit}`)
export const getThread    = (threadId) => req(`/mail/thread/${threadId}`)
export const markRead     = (mailId)   => req(`/mail/${mailId}/read`,  { method: 'POST' })
export const sendMail     = (body)     => req('/mail/send',            { method: 'POST', body })

// Projects
export const getProjects    = (params={}) => { const qs = new URLSearchParams(params).toString(); return req(`/admin/projects${qs ? '?' + qs : ''}`) }
export const getProject     = (id)        => req(`/admin/projects/${id}`)
export const createProject  = (body)      => req('/admin/projects',    { method: 'POST', body })
export const updateProject  = (id, body)  => req(`/admin/projects/${id}`, { method: 'POST', body })
export const deleteProject  = (id)        => req(`/admin/projects/${id}`, { method: 'DELETE' })

// Dept prompt
export const getDeptPrompt  = (id)        => req(`/admin/dept-prompt/${id}`)
export const saveDeptPrompt = (id, body)  => req(`/admin/dept-prompt/${id}`, { method: 'POST', body })

// Audit
export const getAuditLog    = (limit=100) => req(`/admin/audit?limit=${limit}`)

// Settings
export const getSettings    = ()          => req('/settings')
export const saveSettings   = (body)      => req('/settings',          { method: 'POST', body })
export const probeOllama    = (url)       => req(`/settings/ollama-models?base_url=${encodeURIComponent(url)}`)
export const getThinkingLog = (limit=50)  => req(`/settings/thinking-log?limit=${limit}`)

// ── Endeavors ────────────────────────────────────────────────────────────────
export const getEndeavors      = (p={})   => { const qs = new URLSearchParams(p).toString(); return req(`/endeavors${qs ? '?' + qs : ''}`) }
export const createEndeavor    = (body)   => req('/endeavors',            { method: 'POST', body })
export const getEndeavor       = (id)     => req(`/endeavors/${id}`)
export const updateEndeavor    = (id, b)  => req(`/endeavors/${id}`,      { method: 'PUT', body: b })
export const deleteEndeavor    = (id)     => req(`/endeavors/${id}`,      { method: 'DELETE' })
export const getTodayTasks     = ()       => req('/endeavors/today')
export const getCalendarEvents = (y, m)   => req(`/endeavors/calendar?year=${y}&month=${m}`)

// Phases
export const addPhase          = (eid, b) => req(`/endeavors/${eid}/phases`, { method: 'POST', body: b })
export const updatePhase       = (pid, b) => req(`/phases/${pid}`,            { method: 'PUT',  body: b })
export const deletePhase       = (pid)    => req(`/phases/${pid}`,            { method: 'DELETE' })
export const setCurrentPhase   = (pid, b) => req(`/phases/${pid}/set-current`,{ method: 'POST', body: b })
export const extendPhase       = (pid, b) => req(`/phases/${pid}/extend`,     { method: 'POST', body: b })

// Objectives
export const addObjective      = (pid, b) => req(`/phases/${pid}/objectives`, { method: 'POST', body: b })
export const updateObjective   = (oid, b) => req(`/objectives/${oid}`,        { method: 'PUT',  body: b })
export const deleteObjective   = (oid)    => req(`/objectives/${oid}`,        { method: 'DELETE' })
export const toggleObjective   = (oid)    => req(`/objectives/${oid}/toggle`, { method: 'POST' })

// Time tracking
export const startTimer        = (oid)    => req(`/objectives/${oid}/time/start`, { method: 'POST' })
export const stopTimer         = (oid)    => req(`/objectives/${oid}/time/stop`,  { method: 'POST' })
export const getTimeLog        = (oid)    => req(`/objectives/${oid}/time`)

// ── Agents ───────────────────────────────────────────────────────────────────
export const getAgents           = (p={})  => { const qs=new URLSearchParams(p).toString(); return req(`/agents${qs?'?'+qs:''}`) }
export const getAgent            = (id)    => req(`/agents/${id}`)
export const createAgent         = (body)  => req('/agents',               { method:'POST',   body })
export const updateAgent         = (id,b)  => req(`/agents/${id}`,         { method:'PUT',    body:b })
export const fireAgent           = (id,b)  => req(`/agents/${id}/fire`,    { method:'POST',   body:b })
export const triggerHeartbeat    = (id)    => req(`/agents/${id}/heartbeat`,{ method:'POST' })
export const chatWithAgent_old       = (id, msg)=> req(`/agents/${id}/chat`,     { method:'POST', body:{ message: msg } })
export const getHeartbeatStatus_old  = ()       => req('/heartbeat/status')

// Agent files
export const getAgentFiles       = (id)    => req(`/agents/${id}/files`)
export const upsertAgentFile     = (id,b)  => req(`/agents/${id}/files`,   { method:'POST',   body:b })
export const deleteAgentFile     = (id,fid)=> req(`/agents/${id}/files/${fid}`, { method:'DELETE' })

// Dept files
export const getDeptFiles        = (did)   => req(`/deptfiles/${did}`)
export const upsertDeptFile      = (did,b) => req(`/deptfiles/${did}`,     { method:'POST',   body:b })
export const deleteDeptFile      = (did,fid)=>req(`/deptfiles/${did}/${fid}`,{ method:'DELETE' })

// Founder
export const getFounderStats     = ()      => req('/founder/stats')
export const getFounderInbox     = (p={})  => { const qs=new URLSearchParams(p).toString(); return req(`/founder/inbox${qs?'?'+qs:''}`) }
export const markFounderRead     = (id)    => req(`/founder/inbox/${id}/read`,      { method:'POST' })
export const replyFounderMail    = (id,b)  => req(`/founder/inbox/${id}/reply`,     { method:'POST', body:b })
export const retriggerFounderMail= (id)    => req(`/founder/inbox/${id}/retrigger`, { method:'POST' })

// Spawn requests
export const getSpawnRequests    = (p={})  => { const qs=new URLSearchParams(p).toString(); return req(`/spawn-requests${qs?'?'+qs:''}`) }
export const requestSpawn        = (body)  => req('/spawn-requests',       { method:'POST',   body })
export const approveSpawn        = (id,b)  => req(`/spawn-requests/${id}/approve`, { method:'POST', body:b })
export const rejectSpawn         = (id,b)  => req(`/spawn-requests/${id}/reject`,  { method:'POST', body:b })

// Draft endeavors (agent-submitted)
export const getDraftEndeavors   = (p={})  => { const qs=new URLSearchParams(p).toString(); return req(`/draft-endeavors${qs?'?'+qs:''}`) }
export const createDraftEndeavor = (body)  => req('/draft-endeavors',     { method:'POST',   body })
export const approveDraftEndeavor= (id,b)  => req(`/draft-endeavors/${id}/approve`, { method:'POST', body:b })
export const rejectDraftEndeavor = (id,b)  => req(`/draft-endeavors/${id}/reject`,  { method:'POST', body:b })
export const editDraftEndeavor   = (id,b)  => req(`/draft-endeavors/${id}`,{ method:'PUT',   body:b })

// CEO decisions
export const getCeoDecisions     = (p={})  => { const qs=new URLSearchParams(p).toString(); return req(`/ceo-decisions${qs?'?'+qs:''}`) }

// Agent chat
export const chatWithAgent          = (id, message) => req(`/agents/${id}/chat`, { method:'POST', body:{ message } })
export const clearAgentChat         = (id)           => req(`/agents/${id}/chat`, { method:'DELETE' })
export const getHeartbeatStatus     = ()             => req('/agents/heartbeat/status')
export const updateHeartbeatInterval= (id, interval) => req(`/agents/${id}/heartbeat-interval`, { method:'PUT', body:{ interval } })

// Topics
export const getTopics       = ()           => req('/topics')
export const searchTopics    = (q)          => req(`/topics/search?q=${encodeURIComponent(q)}`)
export const createTopic     = (body)       => req('/topics',              { method:'POST',   body })
export const updateTopic     = (id, body)   => req(`/topics/${id}`,        { method:'PUT',    body })
export const deleteTopic     = (id)         => req(`/topics/${id}`,        { method:'DELETE' })
export const assignTopic     = (id, body)   => req(`/topics/${id}/assign`, { method:'POST',   body })

// Presets (external JSON files)
export const getPresetList   = ()           => req('/presets')
export const getPreset       = (name)       => req(`/presets/${name}`)
export const savePreset      = (name, body) => req(`/presets/${name}`,     { method:'PUT',    body })

// Random face for agent profile images
export const getRandomFace   = ()           => req('/agents/random-face')

// Prompts overview
export const getAllPrompts    = ()           => req('/admin/all-prompts')
export const saveAgentPrompt = (id, body)   => req(`/agents/${id}`,        { method:'PUT',    body })

