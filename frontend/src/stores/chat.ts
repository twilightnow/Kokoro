import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Mood } from '../types/chat'

export const useChatStore = defineStore('chat', () => {
  const mood = ref<Mood>('normal')
  const reply = ref<string>('')
  const isThinking = ref<boolean>(false)
  const proactiveActions = ref<string[]>([])
  const characterName = ref<string>('')
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

  function setProactiveMessage(msg: string, actions: string[] = ['嗯', '知道了', '不想说']): void {
    reply.value = msg
    proactiveActions.value = actions
  }

  function setCharacterInfo(name: string, initialTurn: number): void {
    characterName.value = name
    turn.value = initialTurn
  }

  function incrementTurn(): void {
    turn.value += 1
  }

  function resetForNewCharacter(name: string): void {
    characterName.value = name
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
    characterName,
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
