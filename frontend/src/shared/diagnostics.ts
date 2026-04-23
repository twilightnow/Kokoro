import { sidecarHttpUrl } from './sidecar'

type LogLevel = 'debug' | 'info' | 'warn' | 'error'

interface ClientLog {
  source: string
  event: string
  level?: LogLevel
  message?: string
  details?: Record<string, unknown>
}

function normalizeError(error: unknown): Record<string, unknown> {
  if (error instanceof Error) {
    return {
      name: error.name,
      message: error.message,
      stack: error.stack,
    }
  }
  return { value: String(error) }
}

export async function reportClientLog(log: ClientLog): Promise<void> {
  try {
    await fetch(sidecarHttpUrl('/admin/debug/client-log'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        level: 'info',
        message: '',
        details: {},
        ...log,
      }),
    })
  } catch {
    // Logging must never affect the UI path being diagnosed.
  }
}

export function errorDetails(error: unknown): Record<string, unknown> {
  return normalizeError(error)
}
