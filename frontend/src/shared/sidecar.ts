const SIDECAR_HOST = '127.0.0.1'
const SIDECAR_PORT = 18765

export const SIDECAR_HTTP_BASE = `http://${SIDECAR_HOST}:${SIDECAR_PORT}`
export const SIDECAR_WS_BASE = `ws://${SIDECAR_HOST}:${SIDECAR_PORT}`

export function sidecarHttpUrl(path: string): string {
  return `${SIDECAR_HTTP_BASE}${path.startsWith('/') ? path : `/${path}`}`
}

export function sidecarWsUrl(path: string): string {
  return `${SIDECAR_WS_BASE}${path.startsWith('/') ? path : `/${path}`}`
}
