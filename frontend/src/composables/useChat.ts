import { ref } from 'vue'
import { useChatStore } from '../stores/chat'
import type { CharacterDisplayConfig, Mood, StreamChunk } from '../types/chat'
import { sidecarHttpUrl, sidecarWsUrl } from '../shared/sidecar'
import { useSpeechOutput } from './useSpeechOutput'

const WS_URL = sidecarWsUrl('/stream')
const HEALTH_URL = sidecarHttpUrl('/health')
const STATE_URL = sidecarHttpUrl('/state')
const MAX_RETRIES = 3
const RETRY_DELAYS: number[] = [1000, 2000, 4000]

export type ConnectionStatus =
  | 'idle'
  | 'connecting'
  | 'connected'
  | 'disconnected'
  | 'error'
  | 'connection_failed'

const status = ref<ConnectionStatus>('idle')
const errorMessage = ref<string>('')

let ws: WebSocket | null = null
let retryCount = 0
let pendingMessage: string | null = null
const speechOutput = useSpeechOutput()

function isMood(value: unknown): value is Mood {
  return typeof value === 'string' && value.trim().length > 0
}

function _doSend(text: string): void {
  if (ws?.readyState !== WebSocket.OPEN) return
  ws.send(JSON.stringify({ message: text }))
}

function _scheduleReconnect(): void {
  if (retryCount >= MAX_RETRIES) {
    status.value = 'connection_failed'
    errorMessage.value = '连接失败，请重新启动 sidecar'
    return
  }
  status.value = 'disconnected'
  const delay = RETRY_DELAYS[retryCount] ?? 4000
  retryCount++
  setTimeout(() => connect(), delay)
}

function _handleChunk(raw: string): void {
  const store = useChatStore()
  let chunk: StreamChunk
  try {
    chunk = JSON.parse(raw) as StreamChunk
  } catch {
    return
  }

  switch (chunk.type) {
    case 'thinking':
      store.setThinking(true)
      speechOutput.beginStream()
      break
    case 'token':
      store.appendReply(chunk.content)
      speechOutput.pushToken(chunk.content)
      break
    case 'done':
      store.setThinking(false)
      if (chunk.content) store.setReply(chunk.content)
      if (isMood(chunk.mood)) store.setMood(chunk.mood)
      speechOutput.finishStream(chunk.content)
      store.incrementTurn()
      break
    case 'error':
      store.setThinking(false)
      speechOutput.stop()
      errorMessage.value = chunk.content
      break
    case 'proactive':
      store.setThinking(false)
      store.setProactiveMessage(chunk.content)
      speechOutput.speakNow(chunk.content)
      break
    default:
      break
  }
}

function connect(): void {
  if (ws?.readyState === WebSocket.OPEN) return
  status.value = 'connecting'

  ws = new WebSocket(WS_URL)

  ws.onopen = () => {
    status.value = 'connected'
    retryCount = 0
    if (pendingMessage !== null) {
      _doSend(pendingMessage)
      pendingMessage = null
    }
  }

  ws.onmessage = (evt: MessageEvent<string>) => {
    _handleChunk(evt.data)
  }

  ws.onerror = () => {
    status.value = 'error'
  }

  ws.onclose = () => {
    if (status.value !== 'connection_failed') {
      _scheduleReconnect()
    }
  }
}

async function checkHealth(): Promise<boolean> {
  try {
    const resp = await fetch(HEALTH_URL)
    return resp.ok
  } catch {
    return false
  }
}

async function fetchCharacterInfo(): Promise<void> {
  try {
    const resp = await fetch(STATE_URL)
    if (!resp.ok) return
    const data = await resp.json() as {
      character_id: string
      character_name: string
      display?: CharacterDisplayConfig
      turn: number
      mood: string
    }
    useChatStore().setCharacterInfo(
      data.character_id,
      data.character_name,
      data.turn,
      data.display ?? { mode: 'placeholder' },
    )
    if (isMood(data.mood)) useChatStore().setMood(data.mood)
  } catch {
    // Ignore bootstrap errors here.
  }
}

async function syncState(): Promise<void> {
  await fetchCharacterInfo()
}

async function init(): Promise<void> {
  const ok = await checkHealth()
  if (!ok) {
    status.value = 'error'
    errorMessage.value = 'sidecar 正在启动或不可用，请稍后重试'
    return
  }
  await fetchCharacterInfo()
  connect()
}

function sendMessage(text: string): void {
  if (ws?.readyState === WebSocket.OPEN) {
    _doSend(text)
  } else {
    pendingMessage = text
    connect()
  }
}

export function useChat() {
  return { status, errorMessage, init, sendMessage, syncState }
}
