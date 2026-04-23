import { onBeforeUnmount, ref } from 'vue'

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
}

type UseSpeechInputOptions = {
  onInterim: (text: string) => void
  onFinal: (text: string) => void
}

export function useSpeechInput(options: UseSpeechInputOptions) {
  const isListening = ref(false)
  const speechError = ref('')
  const supported = typeof window !== 'undefined'
    && Boolean(window.SpeechRecognition || window.webkitSpeechRecognition)

  let recognition: BrowserSpeechRecognition | null = null
  let lastFinalText = ''

  function ensureRecognition(): BrowserSpeechRecognition | null {
    if (!supported) {
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
        let interimText = ''
        let finalText = ''
        for (let index = event.resultIndex; index < event.results.length; index += 1) {
          const result = event.results[index]
          const transcript = result[0]?.transcript ?? ''
          if (result.isFinal) {
            finalText += transcript
          } else {
            interimText += transcript
          }
        }
        lastFinalText = finalText.trim() || lastFinalText
        options.onInterim((finalText || interimText).trim())
      }
      recognition.onerror = (event) => {
        isListening.value = false
        speechError.value = `语音识别失败: ${event.error}`
      }
      recognition.onend = () => {
        isListening.value = false
        if (lastFinalText) {
          options.onFinal(lastFinalText)
          lastFinalText = ''
        }
      }
    }
    return recognition
  }

  function startListening(): void {
    const instance = ensureRecognition()
    if (!instance) {
      speechError.value = '当前环境不支持语音识别'
      return
    }
    speechError.value = ''
    lastFinalText = ''
    isListening.value = true
    instance.start()
  }

  function stopListening(): void {
    recognition?.stop()
  }

  function toggleListening(): void {
    if (isListening.value) {
      stopListening()
      return
    }
    startListening()
  }

  onBeforeUnmount(() => {
    recognition?.stop()
    recognition = null
  })

  return {
    supported,
    isListening,
    speechError,
    toggleListening,
  }
}