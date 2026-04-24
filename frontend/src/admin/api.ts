// Admin API client — 所有对 sidecar 的 fetch 调用集中在此，便于统一替换 base URL
import { sidecarHttpUrl } from '../shared/sidecar'

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message)
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(sidecarHttpUrl(path), {
    headers: { 'Content-Type': 'application/json', ...init?.headers },
    ...init,
  })
  if (!res.ok) {
    let detail = `HTTP ${res.status}`
    try {
      const body = await res.json()
      detail = body.detail ?? detail
    } catch {
      // ignore
    }
    throw new ApiError(res.status, detail)
  }
  return res.json() as Promise<T>
}

// ── /state & /health ─────────────────────────────────────────────────────────
export const api = {
  getState: () => request<any>('/state'),
  getHealth: () => request<any>('/health'),

  // ── /admin/characters ──────────────────────────────────────────────────────
  listCharacters: () => request<any[]>('/admin/characters'),
  getCharacter: (id: string) => request<any>(`/admin/characters/${id}`),
  updateCharacter: (id: string, rawYaml: string) =>
    request<any>(`/admin/characters/${id}`, {
      method: 'PUT',
      body: JSON.stringify({ raw_yaml: rawYaml }),
    }),
  reloadCharacter: (id: string) =>
    request<any>(`/admin/characters/${id}/reload`, { method: 'POST' }),
  setDefaultStartupCharacter: (id: string) =>
    request<any>(`/admin/characters/${id}/set-default-startup`, { method: 'POST' }),

  // ── /admin/memories ────────────────────────────────────────────────────────
  listFacts: (charId: string) => request<any[]>(`/admin/memories/${charId}/facts`),
  createFact: (charId: string, key: string, value: string) =>
    request<any>(`/admin/memories/${charId}/facts?key=${encodeURIComponent(key)}`, {
      method: 'POST',
      body: JSON.stringify({ value }),
    }),
  updateFact: (charId: string, key: string, value: string) =>
    request<any>(`/admin/memories/${charId}/facts/${encodeURIComponent(key)}`, {
      method: 'PUT',
      body: JSON.stringify({ value }),
    }),
  resolveConflict: (charId: string, key: string, adoptNew: boolean) =>
    request<any>(`/admin/memories/${charId}/facts/${encodeURIComponent(key)}/resolve`, {
      method: 'POST',
      body: JSON.stringify({ adopt_new: adoptNew }),
    }),
  deleteFact: (charId: string, key: string) =>
    request<any>(`/admin/memories/${charId}/facts/${encodeURIComponent(key)}`, {
      method: 'DELETE',
    }),
  listSummaries: (charId: string, offset = 0, limit = 20) =>
    request<any>(`/admin/memories/${charId}/summaries?offset=${offset}&limit=${limit}`),
  deleteSummary: (charId: string, index: number) =>
    request<any>(`/admin/memories/${charId}/summaries/${index}`, { method: 'DELETE' }),
  clearMemories: (charId: string) =>
    request<any>(`/admin/memories/${charId}`, { method: 'DELETE' }),

  // ── /admin/logs ─────────────────────────────────────────────────────────────
  listLogs: (offset = 0, limit = 30) =>
    request<any>(`/admin/logs?offset=${offset}&limit=${limit}`),
  getLog: (filename: string) => request<any[]>(`/admin/logs/${encodeURIComponent(filename)}`),
  clearAllLogs: () => request<any>('/admin/logs', { method: 'DELETE' }),

  // ── /admin/stats ────────────────────────────────────────────────────────────
  emotionStats: (days = 30) => request<any>(`/admin/stats/emotion?days=${days}`),
  triggerStats: (top = 10, days = 30) =>
    request<any>(`/admin/stats/triggers?top=${top}&days=${days}`),

  // ── /admin/debug ────────────────────────────────────────────────────────────
  debugState: () => request<any>('/admin/debug/state'),
  injectEmotion: (mood: string, persistCount = 3) =>
    request<any>('/admin/debug/emotion', {
      method: 'POST',
      body: JSON.stringify({ mood, persist_count: persistCount }),
    }),
  listTempFacts: () => request<Record<string, string>>('/admin/debug/inject-fact'),
  injectTempFact: (key: string, value: string) =>
    request<any>('/admin/debug/inject-fact', {
      method: 'POST',
      body: JSON.stringify({ key, value }),
    }),
  clearTempFact: (key?: string) => {
    const url = key
      ? `/admin/debug/inject-fact?key=${encodeURIComponent(key)}`
      : '/admin/debug/inject-fact'
    return request<any>(url, { method: 'DELETE' })
  },
  sandbox: (systemPrompt: string, userMessage: string) =>
    request<any>('/admin/debug/sandbox', {
      method: 'POST',
      body: JSON.stringify({ system_prompt: systemPrompt, user_message: userMessage }),
    }),

  // ── /admin/config ───────────────────────────────────────────────────────────
  getConfig: () => request<any>('/admin/config'),
  updateConfig: (updates: Record<string, string>) =>
    request<any>('/admin/config', {
      method: 'PUT',
      body: JSON.stringify({ updates }),
    }),
  reloadConfig: () => request<any>('/admin/config/reload', { method: 'POST' }),
  testLlmConfig: () => request<any>('/admin/config/test-llm', { method: 'POST' }),
  exportDiagnostics: () => request<any>('/admin/diagnostics/export'),
}
