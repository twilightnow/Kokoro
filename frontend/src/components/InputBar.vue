<script setup lang="ts">
import { nextTick, ref } from 'vue'
import { useSpeechInput } from '../composables/useSpeechInput'
import { useSpeechOutput } from '../composables/useSpeechOutput'

const emit = defineEmits<{ (e: 'submit', text: string): void }>()

const draft = ref('')
const inputRef = ref<HTMLInputElement | null>(null)
const { ttsEnabled, toggleTts } = useSpeechOutput()

const {
  supported: speechSupported,
  isListening,
  speechError,
  toggleListening,
} = useSpeechInput({
  onInterim: (text) => {
    draft.value = text
  },
  onFinal: (text) => {
    draft.value = text
    onSubmit()
  },
})

function focusInput(): void {
  nextTick(() => inputRef.value?.focus())
}

function clearDraft(): void {
  draft.value = ''
}

function onSubmit(): void {
  const text = draft.value.trim()
  if (!text) return
  emit('submit', text)
  clearDraft()
  focusInput()
}

function onKeydown(e: KeyboardEvent): void {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    onSubmit()
  } else if (e.key === 'Escape') {
    clearDraft()
  }
}
</script>

<template>
  <div class="input-bar">
    <div class="voice-controls" aria-label="语音设置">
      <button
        class="voice-btn"
        :class="{ 'voice-btn--active': speechSupported && isListening }"
        :disabled="!speechSupported"
        :title="speechSupported ? (isListening ? '停止语音输入' : '语音输入') : '当前环境不支持语音输入'"
        type="button"
        @mousedown.prevent
        @click="toggleListening"
      >
        <span class="voice-icon">🎙</span>
      </button>
      <button
        class="voice-btn"
        :class="{ 'voice-btn--active': ttsEnabled }"
        :title="ttsEnabled ? '关闭语音播放' : '开启语音播放'"
        type="button"
        @mousedown.prevent
        @click="toggleTts"
      >
        <span class="voice-icon">🔊</span>
      </button>
    </div>
    <input
      ref="inputRef"
      v-model="draft"
      class="input-field"
      placeholder="说点什么…"
      @keydown="onKeydown"
      @mousedown.stop
    />
    <button class="send-btn" @mousedown.prevent @click="onSubmit">送信</button>
  </div>
  <div v-if="speechError" class="input-hint input-hint--error">{{ speechError }}</div>
</template>

<style scoped>
.input-bar {
  display: flex;
  gap: 8px;
  align-items: center;
  width: 100%;
}

.voice-controls {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
  width: 102px;
  flex: 0 0 102px;
}

.voice-btn {
  min-width: 0;
  height: 38px;
  border: 1.5px solid rgba(255, 179, 198, 0.92);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.94);
  color: #c0405f;
  font-size: 14px;
  cursor: pointer;
  box-shadow: 0 10px 22px rgba(15, 23, 42, 0.14);
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.voice-btn--active {
  background: #ffe0eb;
  border-color: #ff8cb0;
}

.voice-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.voice-icon {
  font-size: 15px;
  line-height: 1;
}

.input-field {
  flex: 1;
  min-width: 0;
  border: 1.5px solid rgba(255, 179, 198, 0.92);
  border-radius: 999px;
  padding: 10px 14px;
  font-size: 14px;
  outline: none;
  background: rgba(255, 255, 255, 0.94);
  color: #333;
  font-family: inherit;
  box-shadow: 0 10px 22px rgba(15, 23, 42, 0.14);
}

.input-field:focus {
  border-color: #ff8cb0;
  box-shadow: 0 0 0 2px rgba(255, 140, 176, 0.2);
}

.send-btn {
  border: 1.5px solid rgba(255, 179, 198, 0.92);
  border-radius: 999px;
  background: #fff0f5;
  color: #c0405f;
  padding: 10px 16px;
  font-size: 14px;
  cursor: pointer;
  transition: background 0.15s;
  white-space: nowrap;
  box-shadow: 0 10px 22px rgba(15, 23, 42, 0.14);
}

.send-btn:hover {
  background: #ffe0eb;
}

.input-hint {
  margin-top: 6px;
  padding-left: 10px;
  font-size: 11px;
  line-height: 1.4;
}

.input-hint--error {
  color: #a3364f;
}
</style>
