/**
 * useChat — WebSocket 通信 composable。
 *
 * 职责：封装 WebSocket 连接管理、消息发送、帧解析、断线重连。
 * 状态通过 Pinia store 传递，不直接操作 DOM 或组件。
 */
import { ref } from 'vue'
import { useChatStore } from '../stores/chat'
import type { Mood, StreamChunk } from '../types/chat'

// ── 常量 ──────────────────────────────────────────────────────────────────────
const WS_URL    = 'ws://127.0.0.1:18765/stream'
const HEALTH_URL = 'http://127.0.0.1:18765/health'
const STATE_URL  = 'http://127.0.0.1:18765/state'
const MAX_RETRIES = 3
const RETRY_DELAYS: number[] = [1000, 2000, 4000]

// ── 类型 ──────────────────────────────────────────────────────────────────────
export type ConnectionStatus =
  | 'idle'
  | 'connecting'
  | 'connected'
  | 'disconnected'
  | 'error'
  | 'connection_failed'

// ── 模块级单例（全 app 共享） ──────────────────────────────────────────────────
const status = ref<ConnectionStatus>('idle')
const errorMessage = ref<string>('')

let ws: WebSocket | null = null
let retryCount = 0
let pendingMessage: string | null = null

// ── 类型守卫 ──────────────────────────────────────────────────────────────────
function isMood(value: unknown): value is Mood {
  return typeof value === 'string' && value.trim().length > 0
}

// ── 内部函数 ──────────────────────────────────────────────────────────────────
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
      break
    case 'token':
      store.appendReply(chunk.content)
      break
    case 'done':
      store.setThinking(false)
      if (chunk.content) store.setReply(chunk.content)
      if (isMood(chunk.mood)) store.setMood(chunk.mood)
      store.incrementTurn()
      break
    case 'error':
      store.setThinking(false)
      errorMessage.value = chunk.content
      break
    case 'proactive':
      store.setThinking(false)
      store.setProactiveMessage(chunk.content)
      break
    default:
      break
  }
}

// ── 公开函数 ──────────────────────────────────────────────────────────────────
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
    const data = await resp.json() as { character_id: string; character_name: string; turn: number; mood: string }
    useChatStore().setCharacterInfo(data.character_name, data.turn)
    if (isMood(data.mood)) useChatStore().setMood(data.mood)
  } catch {
    // サイレントに無視
  }
}

async function init(): Promise<void> {
  const ok = await checkHealth()
  if (!ok) {
    status.value = 'error'
    errorMessage.value = '请先启动 sidecar（python -m src.api.server）'
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

// ── composable エントリ ────────────────────────────────────────────────────────
export function useChat() {
  return { status, errorMessage, init, sendMessage }
}
