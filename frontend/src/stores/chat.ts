import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { CharacterDisplayConfig, Mood } from '../types/chat'

export const useChatStore = defineStore('chat', () => {
  const mood = ref<Mood>('normal')
  const reply = ref<string>('')
  const isThinking = ref<boolean>(false)
  const proactiveActions = ref<string[]>([])
  const characterId = ref<string>('')
  const characterName = ref<string>('')
  const display = ref<CharacterDisplayConfig>({ mode: 'placeholder' })
  const turn = ref<number>(0)

  function setMood(m: Mood): void {
    mood.value = m
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
      proactiveActions.value = []
    }
  }

  function setProactiveMessage(msg: string, actions: string[] = ['好', '知道了', '不想说']): void {
    reply.value = msg
    proactiveActions.value = actions
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
    reply.value = ''
    isThinking.value = false
    proactiveActions.value = []
  }

  return {
    mood,
    reply,
    isThinking,
    proactiveActions,
    characterId,
    characterName,
    display,
    turn,
    setMood,
    setReply,
    appendReply,
    setThinking,
    setProactiveMessage,
    setCharacterInfo,
    incrementTurn,
    resetForNewCharacter,
  }
})
