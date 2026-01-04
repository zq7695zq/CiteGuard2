// 中文注释：本文件(frontend/src/api/client.ts)用于实现该模块的核心逻辑、接口或页面渲染，便于定位职责与维护。
const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

export async function fetchJobs() {
  const res = await fetch(`${API_BASE}/jobs`)
  if (!res.ok) {
    return []
  }
  return res.json()
}

export async function createJob(paperText: string, bibText: string) {
  const res = await fetch(`${API_BASE}/jobs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ paper_text: paperText, bib_text: bibText, config: {} }),
  })
  if (!res.ok) throw new Error('Failed to create job')
  return res.json()
}

export async function fetchJob(jobId: string) {
  const res = await fetch(`${API_BASE}/jobs/${jobId}`)
  if (!res.ok) throw new Error('Job not found')
  return res.json()
}

export async function fetchTasks(jobId: string) {
  const res = await fetch(`${API_BASE}/jobs/${jobId}/tasks`)
  if (!res.ok) throw new Error('Tasks not found')
  return res.json()
}

export async function retryTasks(jobId: string, taskIds?: string[]) {
  const res = await fetch(`${API_BASE}/jobs/${jobId}/retry`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ task_ids: taskIds }),
  })
  if (!res.ok) throw new Error('Retry failed')
  return res.json()
}

export async function skipTasks(jobId: string, taskIds: string[]) {
  const res = await fetch(`${API_BASE}/jobs/${jobId}/skip`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ task_ids: taskIds }),
  })
  if (!res.ok) throw new Error('Skip failed')
  return res.json()
}

export async function pauseJob(jobId: string) {
  const res = await fetch(`${API_BASE}/jobs/${jobId}/pause`, { method: 'POST' })
  if (!res.ok) throw new Error('Pause failed')
  return res.json()
}

export async function resumeJob(jobId: string) {
  const res = await fetch(`${API_BASE}/jobs/${jobId}/resume`, { method: 'POST' })
  if (!res.ok) throw new Error('Resume failed')
  return res.json()
}

export async function cancelJob(jobId: string) {
  const res = await fetch(`${API_BASE}/jobs/${jobId}/cancel`, { method: 'POST' })
  if (!res.ok) throw new Error('Cancel failed')
  return res.json()
}

export function openEventSource(jobId: string, afterSeq: number, onMessage: (data: any) => void) {
  const url = `${API_BASE}/jobs/${jobId}/events?after_seq=${afterSeq}`
  const source = new EventSource(url)
  source.onmessage = (event) => {
    onMessage(JSON.parse(event.data))
  }
  return source
}
