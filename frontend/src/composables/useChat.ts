import { ref } from 'vue'
import { useChatStore } from '../stores/chat'
import type { CharacterDisplayConfig, EmotionSummary, ExpressionEvent, Mood, StreamChunk } from '../types/chat'
import { sidecarHttpUrl, sidecarWsUrl } from '../shared/sidecar'
import { useSpeechOutput } from './useSpeechOutput'
import { useExpressionEvent } from './useExpressionEvent'

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
let proactiveTimer: number | null = null
const speechOutput = useSpeechOutput()
const expressionEvent = useExpressionEvent()

function isMood(value: unknown): value is Mood {
  return typeof value === 'string' && value.trim().length > 0
}

function isEmotionSummary(value: unknown): value is EmotionSummary {
  return typeof value === 'object' && value !== null && typeof (value as EmotionSummary).mood === 'string'
}

function isExpressionEvent(value: unknown): value is ExpressionEvent {
  if (typeof value !== 'object' || value === null) return false
  const v = value as Record<string, unknown>
  return (
    typeof v.emotion === 'object' && v.emotion !== null &&
    typeof v.motion === 'object' && v.motion !== null &&
    typeof v.speech === 'object' && v.speech !== null &&
    typeof v.playback === 'object' && v.playback !== null
  )
}

function _doSend(text: string): void {
  if (ws?.readyState !== WebSocket.OPEN) return
  ws.send(JSON.stringify({ message: text }))
}

function _clearProactiveTimer(): void {
  if (proactiveTimer !== null) {
    window.clearTimeout(proactiveTimer)
    proactiveTimer = null
  }
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
      _clearProactiveTimer()
      store.setThinking(true)
      speechOutput.beginStream(store.emotion)
      break
    case 'token':
      store.appendReply(chunk.content)
      speechOutput.pushToken(chunk.content)
      break
    case 'done': {
      _clearProactiveTimer()
      store.setThinking(false)
      if (chunk.content) store.setReply(chunk.content)
      if (isEmotionSummary(chunk.emotion)) store.setEmotion(chunk.emotion)
      if (isMood(chunk.mood)) store.setMood(chunk.mood)
      if (isExpressionEvent(chunk.expression_event)) {
        expressionEvent.setExpressionEvent(chunk.expression_event)
      }
      const currentEmotion = isEmotionSummary(chunk.emotion) ? chunk.emotion : store.emotion
      const pauseMs = isExpressionEvent(chunk.expression_event) ? chunk.expression_event.speech.pause_ms : 0
      speechOutput.finishStream(chunk.content, currentEmotion, pauseMs)
      store.incrementTurn()
      break
    }
    case 'error':
      _clearProactiveTimer()
      store.setThinking(false)
      speechOutput.stop()
      errorMessage.value = chunk.content
      break
    case 'proactive':
      _clearProactiveTimer()
      store.setThinking(false)
      if (isEmotionSummary(chunk.emotion)) {
        store.setEmotion(chunk.emotion)
      }
      if (isMood(chunk.expression ?? chunk.mood)) {
        store.setMood((chunk.expression ?? chunk.mood) as Mood)
      }
      store.setProactiveFrame({
        eventId: chunk.id,
        level: chunk.level,
        scene: chunk.scene,
        source: chunk.source,
        urgency: chunk.urgency,
        content: chunk.content,
        actions: chunk.actions,
      })
      if (chunk.level === 'short') {
        proactiveTimer = window.setTimeout(() => {
          store.clearProactiveMessage()
        }, 6000)
      }
      if (chunk.level === 'expression') {
        proactiveTimer = window.setTimeout(() => {
          store.clearProactiveMessage()
        }, 1500)
      }
      if (chunk.level === 'full' && chunk.content) {
        speechOutput.speakNow(
          chunk.content,
          isEmotionSummary(chunk.emotion) ? chunk.emotion : store.emotion,
          0,
          'proactive',
        )
      }
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
      emotion?: EmotionSummary
    }
    useChatStore().setCharacterInfo(
      data.character_id,
      data.character_name,
      data.turn,
      data.display ?? { mode: 'placeholder' },
    )
    if (isEmotionSummary(data.emotion)) useChatStore().setEmotion(data.emotion)
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

async function sendProactiveFeedback(feedback: string): Promise<void> {
  const store = useChatStore()
  if (!store.proactiveEventId) return

  try {
    await fetch(sidecarHttpUrl('/admin/proactive/feedback'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        event_id: store.proactiveEventId,
        feedback,
        responded: true,
      }),
    })
  } catch {
    // 反馈记录失败时不阻断正常聊天。
  }
}

export function useChat() {
  return { status, errorMessage, init, sendMessage, sendProactiveFeedback, syncState }
}
