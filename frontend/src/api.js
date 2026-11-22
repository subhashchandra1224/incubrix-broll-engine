// Minimal API client for the B-roll Engine backend.
// In dev, Vite proxies /api to http://localhost:8000 (see vite.config.js).
// In production, set VITE_API_BASE to the backend URL if not same-origin.

const API_BASE = import.meta.env.VITE_API_BASE || ''

export async function createJob(payload, idempotencyKey) {
  const headers = { 'Content-Type': 'application/json' }
  if (idempotencyKey) headers['Idempotency-Key'] = idempotencyKey
  const res = await fetch(`${API_BASE}/api/v1/broll/jobs`, {
    method: 'POST',
    headers,
    body: JSON.stringify(payload),
  })
  const data = await res.json()
  if (!res.ok) return { error: data.error || { code: 'HTTP_' + res.status, message: 'Request failed' } }
  return data
}

export async function getJobStatus(jobId) {
  const res = await fetch(`${API_BASE}/api/v1/jobs/${jobId}`)
  return res.json()
}

export async function getOutputsList(jobId) {
  const res = await fetch(`${API_BASE}/api/v1/broll/jobs/${jobId}/outputs`)
  return res.json()
}

export function fileDownloadUrl(jobId, filename) {
  return `${API_BASE}/api/v1/broll/jobs/${jobId}/outputs/${filename}`
}

export function timelineUrl(jobId) {
  return `${API_BASE}/api/v1/broll/jobs/${jobId}/timeline`
}

export function manifestUrl(jobId) {
  return `${API_BASE}/api/v1/broll/jobs/${jobId}/manifest`
}

export function newIdempotencyKey() {
  return crypto.randomUUID()
}
