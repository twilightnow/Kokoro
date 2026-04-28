import { ref } from 'vue'
import type { ExpressionEvent } from '../types/chat'

const DEFAULT_EVENT: ExpressionEvent = {
  emotion: { name: 'normal', intensity: 0, keyword: '', reason: '' },
  motion: { name: '', priority: 50 },
  speech: { rate_delta: '', volume_delta: '', pause_ms: 0 },
  playback: { intent: 'queue' },
}

function cloneDefault(): ExpressionEvent {
  return {
    emotion: { ...DEFAULT_EVENT.emotion },
    motion: { ...DEFAULT_EVENT.motion },
    speech: { ...DEFAULT_EVENT.speech },
    playback: { ...DEFAULT_EVENT.playback },
  }
}

const currentExpressionEvent = ref<ExpressionEvent>(cloneDefault())

function setExpressionEvent(event: ExpressionEvent): void {
  currentExpressionEvent.value = event
}

function resetExpressionEvent(): void {
  currentExpressionEvent.value = cloneDefault()
}

export function useExpressionEvent() {
  return {
    currentExpressionEvent,
    setExpressionEvent,
    resetExpressionEvent,
  }
}
