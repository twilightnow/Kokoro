import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { CharacterDisplayConfig, EmotionSummary, Mood, ProactiveLevel } from '../types/chat'

const DEFAULT_EMOTION: EmotionSummary = {
  mood: 'normal',
  keyword: '',
  reason: '',
  source: '',
  intensity: 0,
  recovery_rate: 0.2,
  started_at_turn: 0,
  elapsed_turns: 0,
  estimated_remaining_turns: 0,
  phase: 'idle',
  rate_delta: '',
  volume_delta: '',
}

export const useChatStore = defineStore('chat', () => {
  const mood = ref<Mood>('normal')
  const emotion = ref<EmotionSummary>({ ...DEFAULT_EMOTION })
  const reply = ref<string>('')
  const isThinking = ref<boolean>(false)
  const proactiveActions = ref<string[]>([])
  const proactiveEventId = ref<string>('')
  const proactiveLevel = ref<ProactiveLevel>('silent')
  const proactiveScene = ref<string>('')
  const characterId = ref<string>('')
  const characterName = ref<string>('')
  const display = ref<CharacterDisplayConfig>({ mode: 'placeholder' })
  const turn = ref<number>(0)

  function setMood(m: Mood): void {
    mood.value = m
  }

  function setEmotion(nextEmotion?: EmotionSummary | null): void {
    emotion.value = nextEmotion ? { ...DEFAULT_EMOTION, ...nextEmotion } : { ...DEFAULT_EMOTION }
    mood.value = emotion.value.mood || 'normal'
  }

  function setReply(r: string): void {
    reply.value = r
  }

  function appendReply(token: string): void {
    reply.value += token
  }

  function setThinking(v: boolean): void {
    isThinking.value = v
    if (v) {
      reply.value = ''
      clearProactiveMessage()
    }
  }

  function setProactiveFrame(payload: {
    eventId?: string
    level?: ProactiveLevel
    scene?: string
    content: string
    actions?: string[]
  }): void {
    proactiveEventId.value = payload.eventId ?? ''
    proactiveLevel.value = payload.level ?? 'short'
    proactiveScene.value = payload.scene ?? ''
    proactiveActions.value = payload.level === 'expression'
      ? []
      : payload.actions ?? ['好', '知道了', '不想说']
    reply.value = payload.level === 'expression' ? '' : payload.content
  }

  function clearProactiveMessage(): void {
    proactiveEventId.value = ''
    proactiveLevel.value = 'silent'
    proactiveScene.value = ''
    proactiveActions.value = []
    if (!isThinking.value) {
      reply.value = ''
    }
  }

  function setCharacterInfo(
    id: string,
    name: string,
    initialTurn: number,
    nextDisplay: CharacterDisplayConfig,
  ): void {
    characterId.value = id
    characterName.value = name
    display.value = nextDisplay
    turn.value = initialTurn
  }

  function incrementTurn(): void {
    turn.value += 1
  }

  function resetForNewCharacter(
    id: string,
    name: string,
    nextDisplay: CharacterDisplayConfig,
  ): void {
    characterId.value = id
    characterName.value = name
    display.value = nextDisplay
    turn.value = 0
    mood.value = 'normal'
    emotion.value = { ...DEFAULT_EMOTION }
    isThinking.value = false
    clearProactiveMessage()
  }

  return {
    mood,
    emotion,
    reply,
    isThinking,
    proactiveActions,
    proactiveEventId,
    proactiveLevel,
    proactiveScene,
    characterId,
    characterName,
    display,
    turn,
    setMood,
    setEmotion,
    setReply,
    appendReply,
    setThinking,
    setProactiveFrame,
    clearProactiveMessage,
    setCharacterInfo,
    incrementTurn,
    resetForNewCharacter,
  }
})
