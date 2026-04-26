import { computed, onBeforeUnmount, ref } from 'vue'

type SpeechRecognitionAlternativeLike = {
  transcript: string
}

type SpeechRecognitionResultLike = {
  isFinal: boolean
  length: number
  [index: number]: SpeechRecognitionAlternativeLike
}

type SpeechRecognitionEventLike = {
  resultIndex: number
  results: ArrayLike<SpeechRecognitionResultLike>
}

type SpeechRecognitionErrorEventLike = {
  error: string
}

type BrowserSpeechRecognition = {
  continuous: boolean
  interimResults: boolean
  lang: string
  onresult: ((event: SpeechRecognitionEventLike) => void) | null
  onerror: ((event: SpeechRecognitionErrorEventLike) => void) | null
  onend: (() => void) | null
  start: () => void
  stop: () => void
}

type SpeechRecognitionCtor = new () => BrowserSpeechRecognition

declare global {
  interface Window {
    SpeechRecognition?: SpeechRecognitionCtor
    webkitSpeechRecognition?: SpeechRecognitionCtor
  }

  interface WindowEventMap {
    'kokoro:speech-input': CustomEvent<string | { text?: string; final?: boolean }>
  }
}

type UseSpeechInputOptions = {
  onInterim: (text: string) => void
  onFinal: (text: string) => void
}

type SpeechInputSource = 'browser' | 'internal'
const SPEECH_SOURCE_KEY = 'kokoro-speech-input-source'

function readSpeechSource(): SpeechInputSource {
  if (typeof window === 'undefined') return 'browser'
  return window.localStorage.getItem(SPEECH_SOURCE_KEY) === 'internal' ? 'internal' : 'browser'
}

export function useSpeechInput(options: UseSpeechInputOptions) {
  const isListening = ref(false)
  const speechError = ref('')
  const inputSource = ref<SpeechInputSource>(readSpeechSource())
  const browserSupported = typeof window !== 'undefined'
    && Boolean(window.SpeechRecognition || window.webkitSpeechRecognition)
  const supported = computed(() => inputSource.value === 'internal' || browserSupported)

  let recognition: BrowserSpeechRecognition | null = null
  let latestTranscript = ''
  let stopRequested = false
  let stopTauriListen: (() => void) | null = null

  function ensureRecognition(): BrowserSpeechRecognition | null {
    if (!browserSupported) {
      return null
    }
    if (!recognition) {
      const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition
      if (!Recognition) {
        return null
      }
      recognition = new Recognition()
      recognition.continuous = false
      recognition.interimResults = true
      recognition.lang = 'zh-CN'
      recognition.onresult = (event) => {
        let finalText = ''
        let interimText = ''
        for (let index = 0; index < event.results.length; index += 1) {
          const result = event.results[index]
          const transcript = result[0]?.transcript ?? ''
          if (result.isFinal) {
            finalText += transcript
          } else {
            interimText += transcript
          }
        }
        latestTranscript = `${finalText}${interimText}`.trim()
        options.onInterim(latestTranscript)
      }
      recognition.onerror = (event) => {
        isListening.value = false
        if (stopRequested && event.error === 'aborted') {
          speechError.value = ''
          return
        }
        if (event.error === 'no-speech') {
          speechError.value = '没有识别到语音，请再试一次'
          return
        }
        speechError.value = `语音识别失败: ${event.error}`
      }
      recognition.onend = () => {
        isListening.value = false
        stopRequested = false
        if (latestTranscript) {
          options.onFinal(latestTranscript)
          latestTranscript = ''
        }
      }
    }
    return recognition
  }

  function startListening(): void {
    if (inputSource.value === 'internal') {
      speechError.value = ''
      isListening.value = true
      return
    }

    const instance = ensureRecognition()
    if (!instance) {
      speechError.value = '当前环境不支持语音识别'
      return
    }
    speechError.value = ''
    latestTranscript = ''
    stopRequested = false
    isListening.value = true
    try {
      instance.start()
    } catch (error) {
      isListening.value = false
      speechError.value = error instanceof Error ? error.message : '语音识别启动失败'
    }
  }

  function stopListening(): void {
    stopRequested = true
    if (inputSource.value === 'internal') {
      isListening.value = false
      return
    }
    recognition?.stop()
  }

  function toggleListening(): void {
    if (isListening.value) {
      stopListening()
      return
    }
    startListening()
  }

  function handleInternalSpeech(text: string, final = true): void {
    if (inputSource.value !== 'internal' || !isListening.value) return
    const normalized = text.trim()
    if (!normalized) return
    speechError.value = ''
    options.onInterim(normalized)
    if (final) {
      options.onFinal(normalized)
    }
  }

  function onWindowSpeechInput(event: WindowEventMap['kokoro:speech-input']): void {
    const detail = event.detail
    if (typeof detail === 'string') {
      handleInternalSpeech(detail)
      return
    }
    handleInternalSpeech(detail.text ?? '', detail.final ?? true)
  }

  function onStorageChange(event: StorageEvent): void {
    if (event.key !== SPEECH_SOURCE_KEY) return
    inputSource.value = event.newValue === 'internal' ? 'internal' : 'browser'
    if (inputSource.value === 'internal') {
      stopRequested = true
      recognition?.stop()
    } else {
      isListening.value = false
    }
    speechError.value = ''
  }

  if (typeof window !== 'undefined') {
    window.addEventListener('kokoro:speech-input', onWindowSpeechInput)
    window.addEventListener('storage', onStorageChange)

    if ((window as Window & { __TAURI_INTERNALS__?: { invoke?: unknown } }).__TAURI_INTERNALS__?.invoke) {
      import('@tauri-apps/api/event')
        .then(({ listen }) => listen<string>('speech-input', (event) => handleInternalSpeech(event.payload)))
        .then((unlisten) => {
          stopTauriListen = unlisten
        })
        .catch(() => {
          // Browser mode or missing event permission keeps using DOM events.
        })
    }
  }

  onBeforeUnmount(() => {
    stopRequested = true
    recognition?.stop()
    recognition = null
    stopTauriListen?.()
    window.removeEventListener('kokoro:speech-input', onWindowSpeechInput)
    window.removeEventListener('storage', onStorageChange)
  })

  return {
    supported,
    inputSource,
    isListening,
    speechError,
    toggleListening,
  }
}
