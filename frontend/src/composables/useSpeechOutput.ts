import { ref } from 'vue'
import { sidecarHttpUrl } from '../shared/sidecar'

type ReadySegments = {
  ready: string[]
  remaining: string
}

const TTS_STORAGE_KEY = 'kokoro-tts-enabled'
const TTS_URL = sidecarHttpUrl('/tts')

const ttsEnabled = ref(readInitialEnabled())
const isSpeaking = ref(false)
const lipSyncLevel = ref(0)
const speechError = ref('')

let pendingText = ''
let playbackChain: Promise<void> = Promise.resolve()
let revision = 0
let activeAudio: HTMLAudioElement | null = null
let activeAudioUrl: string | null = null
let audioContext: AudioContext | null = null
let analyser: AnalyserNode | null = null
let analyserBuffer: Uint8Array<ArrayBuffer> | null = null
let analyserFrame = 0

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

function normalizeSegment(text: string): string {
  return text.replace(/\s+/g, ' ').trim()
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
    ready: ready.map(normalizeSegment).filter(Boolean),
    remaining,
  }
}

function stopLipSync(): void {
  if (analyserFrame) {
    window.cancelAnimationFrame(analyserFrame)
    analyserFrame = 0
  }
  lipSyncLevel.value = 0
}

function startLipSync(): void {
  if (!analyser || !analyserBuffer) {
    lipSyncLevel.value = 0
    return
  }

  const tick = () => {
    if (!analyser || !analyserBuffer) {
      lipSyncLevel.value = 0
      return
    }
    analyser.getByteTimeDomainData(analyserBuffer)
    let total = 0
    for (const value of analyserBuffer) {
      const centered = (value - 128) / 128
      total += centered * centered
    }
    const rms = Math.sqrt(total / analyserBuffer.length)
    lipSyncLevel.value = Math.min(1, rms * 6.5)
    analyserFrame = window.requestAnimationFrame(tick)
  }

  stopLipSync()
  analyserFrame = window.requestAnimationFrame(tick)
}

async function ensureAudioGraph(audio: HTMLAudioElement): Promise<void> {
  if (typeof window === 'undefined' || typeof AudioContext === 'undefined') {
    return
  }
  if (!audioContext) {
    audioContext = new AudioContext()
  }
  if (audioContext.state === 'suspended') {
    await audioContext.resume()
  }

  analyser = audioContext.createAnalyser()
  analyser.fftSize = 512
  analyserBuffer = new Uint8Array(new ArrayBuffer(analyser.frequencyBinCount))

  const source = audioContext.createMediaElementSource(audio)
  source.connect(analyser)
  analyser.connect(audioContext.destination)
}

function clearActiveAudio(): void {
  activeAudio?.pause()
  activeAudio = null
  if (activeAudioUrl) {
    URL.revokeObjectURL(activeAudioUrl)
    activeAudioUrl = null
  }
  isSpeaking.value = false
  stopLipSync()
}

async function requestSpeech(segment: string, currentRevision: number): Promise<string | null> {
  const response = await fetch(TTS_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text: segment }),
  })

  if (currentRevision !== revision) {
    return null
  }

  if (!response.ok) {
    const message = await response.text()
    throw new Error(message || 'TTS 请求失败')
  }

  const blob = await response.blob()
  return URL.createObjectURL(blob)
}

async function playSegment(url: string, currentRevision: number): Promise<void> {
  if (currentRevision !== revision) {
    URL.revokeObjectURL(url)
    return
  }

  clearActiveAudio()
  const audio = new Audio(url)
  activeAudio = audio
  activeAudioUrl = url
  isSpeaking.value = true

  try {
    await ensureAudioGraph(audio)
  } catch {
    // Audio analysis is best-effort; playback should still continue.
  }

  await new Promise<void>((resolve, reject) => {
    audio.onended = () => resolve()
    audio.onerror = () => reject(new Error('音频播放失败'))
    void audio.play().then(() => {
      startLipSync()
    }).catch(reject)
  })

  clearActiveAudio()
}

function queueSegment(segment: string): void {
  if (!segment || !ttsEnabled.value) {
    return
  }

  const currentRevision = revision
  playbackChain = playbackChain.then(async () => {
    try {
      const url = await requestSpeech(segment, currentRevision)
      if (!url) {
        return
      }
      await playSegment(url, currentRevision)
    } catch (error) {
      speechError.value = error instanceof Error ? error.message : 'TTS 播放失败'
      clearActiveAudio()
    }
  })
}

function flushPending(finalText?: string): void {
  if (!ttsEnabled.value) {
    pendingText = ''
    return
  }

  if (finalText && !pendingText.trim()) {
    pendingText = finalText
  }

  const segment = normalizeSegment(pendingText)
  pendingText = ''
  if (segment) {
    queueSegment(segment)
  }
}

function beginStream(): void {
  revision += 1
  pendingText = ''
  speechError.value = ''
  playbackChain = Promise.resolve()
  clearActiveAudio()
}

function pushToken(token: string): void {
  if (!ttsEnabled.value || !token) {
    return
  }

  pendingText += token
  const { ready, remaining } = splitReadySegments(pendingText)
  pendingText = remaining
  ready.forEach(queueSegment)
}

function finishStream(finalText?: string): void {
  flushPending(finalText)
}

function speakNow(text: string): void {
  beginStream()
  flushPending(text)
}

function stop(): void {
  revision += 1
  pendingText = ''
  playbackChain = Promise.resolve()
  clearActiveAudio()
}

function toggleTts(): void {
  ttsEnabled.value = !ttsEnabled.value
  persistEnabled()
  if (!ttsEnabled.value) {
    stop()
  }
}

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