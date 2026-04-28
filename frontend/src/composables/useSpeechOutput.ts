import { ref } from 'vue'
import { sidecarHttpUrl } from '../shared/sidecar'
import type { EmotionSummary } from '../types/chat'
import { SpeechPipeline } from '../lib/speechPipeline'
import type { SpeechOwner } from '../lib/speechPipeline'

// ─── Constants ────────────────────────────────────────────────────────────────

const TTS_STORAGE_KEY = 'kokoro-tts-enabled'
const TTS_URL = sidecarHttpUrl('/tts')

// ─── Vue reactive state ───────────────────────────────────────────────────────

const ttsEnabled = ref(readInitialEnabled())
const isSpeaking = ref(false)
const lipSyncLevel = ref(0)
const speechError = ref('')

// ─── Text segmentation ────────────────────────────────────────────────────────

interface ReadySegments {
  ready: string[]
  remaining: string
}

function splitReadySegments(text: string): ReadySegments {
  const ready: string[] = []
  let remaining = text

  while (remaining.length > 0) {
    const breakMatch = remaining.match(/[。！？!?；;：:\n]/)
    if (breakMatch && breakMatch.index !== undefined) {
      const endIndex = breakMatch.index + breakMatch[0].length
      ready.push(remaining.slice(0, endIndex))
      remaining = remaining.slice(endIndex)
      continue
    }

    if (remaining.length >= 28) {
      const softBreak = Math.max(
        remaining.lastIndexOf('，', 28),
        remaining.lastIndexOf(',', 28),
        remaining.lastIndexOf(' ', 28),
      )
      if (softBreak >= 10) {
        ready.push(remaining.slice(0, softBreak + 1))
        remaining = remaining.slice(softBreak + 1)
        continue
      }
    }

    break
  }

  return {
    ready: ready.map(s => s.replace(/\s+/g, ' ').trim()).filter(Boolean),
    remaining,
  }
}

// ─── TTS fetch ────────────────────────────────────────────────────────────────

function getEmotionSpeechParams(emotion: EmotionSummary | null): { rate?: string; volume?: string } {
  if (!emotion || !emotion.mood || emotion.mood === 'normal' || emotion.intensity <= 0) {
    return {}
  }
  return {
    rate: emotion.rate_delta || undefined,
    volume: emotion.volume_delta || undefined,
  }
}

async function readSpeechError(response: Response): Promise<string> {
  const contentType = response.headers.get('content-type') ?? ''
  if (contentType.includes('application/json')) {
    try {
      const payload = await response.json() as { detail?: unknown; message?: unknown }
      if (typeof payload.detail === 'string' && payload.detail.trim()) {
        return payload.detail
      }
      if (typeof payload.message === 'string' && payload.message.trim()) {
        return payload.message
      }
    } catch {
      // fall through to plain text
    }
  }
  const message = await response.text()
  return message || 'TTS 请求失败'
}

async function fetchAudio(text: string, emotion: EmotionSummary | null): Promise<string | null> {
  const params = getEmotionSpeechParams(emotion)
  const response = await fetch(TTS_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      text,
      ...(params.rate ? { rate: params.rate } : {}),
      ...(params.volume ? { volume: params.volume } : {}),
    }),
  })

  if (!response.ok) {
    throw new Error(await readSpeechError(response))
  }

  const blob = await response.blob()
  return URL.createObjectURL(blob)
}

// ─── SpeechPipeline singleton ────────────────────────────────────────────────

const pipeline = new SpeechPipeline({
  onSpeakingChange(speaking) {
    isSpeaking.value = speaking
  },
  onLipSyncLevel(level) {
    lipSyncLevel.value = level
  },
  onError(message) {
    speechError.value = message
  },
  fetchAudio,
})

// ─── Stream state ─────────────────────────────────────────────────────────────

let pendingText = ''
let streamedTokenSeen = false
let currentEmotion: EmotionSummary | null = null

// ─── Enabled / storage sync ──────────────────────────────────────────────────

function readInitialEnabled(): boolean {
  if (typeof window === 'undefined') {
    return true
  }
  return window.localStorage.getItem(TTS_STORAGE_KEY) !== '0'
}

function persistEnabled(): void {
  if (typeof window === 'undefined') {
    return
  }
  window.localStorage.setItem(TTS_STORAGE_KEY, ttsEnabled.value ? '1' : '0')
}

function syncEnabledState(enabled: boolean): void {
  ttsEnabled.value = enabled
  pipeline.setEnabled(enabled)
}

function bindStorageSync(): void {
  if (typeof window === 'undefined') {
    return
  }
  window.addEventListener('storage', (event) => {
    if (event.key !== TTS_STORAGE_KEY) {
      return
    }
    syncEnabledState(event.newValue !== '0')
  })
}

// ─── Stream API ───────────────────────────────────────────────────────────────

/**
 * 开始新一轮流式输出。
 * 会中断当前所有进行中的 TTS 播放（chat 轮次切换）。
 */
function beginStream(emotion?: EmotionSummary | null): void {
  pendingText = ''
  streamedTokenSeen = false
  speechError.value = ''
  currentEmotion = emotion ?? currentEmotion
  pipeline.stop()
}

/**
 * 推送流式 token，内部按标点切分后自动入队。
 */
function pushToken(token: string): void {
  if (!ttsEnabled.value || !token) {
    return
  }

  streamedTokenSeen = true
  pendingText += token
  const { ready, remaining } = splitReadySegments(pendingText)
  pendingText = remaining

  for (const segment of ready) {
    pipeline.enqueue({
      text: segment,
      owner: 'chat',
      intent: 'queue',
      emotion: currentEmotion,
    })
  }
}

/**
 * 完成流式输出，将剩余 pending text 入队。
 */
function finishStream(finalText?: string, emotion?: EmotionSummary | null, pauseMs = 0): void {
  if (emotion) {
    currentEmotion = emotion
  }

  let flushText: string
  if (streamedTokenSeen) {
    flushText = pendingText
  } else {
    flushText = finalText && !pendingText.trim() ? finalText : pendingText
  }

  pendingText = ''
  streamedTokenSeen = false

  const segment = flushText.replace(/\s+/g, ' ').trim()
  if (segment) {
    pipeline.enqueue({
      text: segment,
      owner: 'chat',
      intent: 'queue',
      emotion: currentEmotion,
      pauseMs,
    })
  }
}

/**
 * 立即朗读一段文字，中断当前所有播放（适用于主动提醒等高优先级场景）。
 * owner 默认 'proactive'，可传入 'system' / 'reminder' 等。
 */
function speakNow(
  text: string,
  emotion?: EmotionSummary | null,
  pauseMs = 0,
  owner: SpeechOwner = 'proactive',
): void {
  pendingText = ''
  streamedTokenSeen = false
  if (emotion) {
    currentEmotion = emotion
  }

  const segment = text.replace(/\s+/g, ' ').trim()
  if (!segment) {
    return
  }

  pipeline.enqueue({
    text: segment,
    owner,
    intent: 'interrupt',
    emotion: emotion ?? currentEmotion,
    pauseMs,
  })
}

/**
 * 停止一切 TTS 播放并清空队列。
 */
function stop(): void {
  pendingText = ''
  currentEmotion = null
  pipeline.stop()
}

function toggleTts(): void {
  syncEnabledState(!ttsEnabled.value)
  persistEnabled()
}

bindStorageSync()

// ─── Composable export ────────────────────────────────────────────────────────

export function useSpeechOutput() {
  return {
    ttsEnabled,
    isSpeaking,
    lipSyncLevel,
    speechError,
    beginStream,
    pushToken,
    finishStream,
    speakNow,
    stop,
    toggleTts,
  }
}