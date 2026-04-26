<script setup lang="ts">
import { nextTick, ref } from 'vue'
import { useSpeechInput } from '../composables/useSpeechInput'

defineProps<{
  ttsEnabled: boolean
}>()

const emit = defineEmits<{
  (e: 'submit', text: string): void
  (e: 'open-admin'): void
  (e: 'toggle-tts'): void
}>()

const draft = ref('')
const inputRef = ref<HTMLInputElement | null>(null)

const {
  supported: speechSupported,
  inputSource,
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

async function startWindowDrag(): Promise<void> {
  try {
    const { getCurrentWindow } = await import('@tauri-apps/api/window')
    await getCurrentWindow().startDragging()
  } catch {
    // Browser mode keeps this decorative control inert.
  }
}

function openAdmin(): void {
  emit('open-admin')
}

function toggleSpeechOutput(): void {
  emit('toggle-tts')
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
        :title="speechSupported ? (isListening ? '停止语音输入' : (inputSource === 'internal' ? '等待内部语音输入' : '语音输入')) : '当前环境不支持语音输入'"
        type="button"
        @mousedown.prevent
        @click="toggleListening"
      >
        <span class="voice-icon">{{ inputSource === 'internal' ? '⌁' : '🎙' }}</span>
      </button>
      <button
        class="voice-btn"
        :class="{ 'voice-btn--muted': !ttsEnabled }"
        :title="ttsEnabled ? '关闭语音播报' : '开启语音播报'"
        type="button"
        @mousedown.prevent
        @click="toggleSpeechOutput"
      >
        <span class="voice-icon">{{ ttsEnabled ? '🔊' : '🔇' }}</span>
      </button>
    </div>
    <div class="input-wrap">
      <input
        ref="inputRef"
        v-model="draft"
        class="input-field"
        placeholder="说点什么…"
        @keydown="onKeydown"
        @mousedown.stop
      />
      <button
        class="send-icon-btn"
        :disabled="!draft.trim()"
        title="发送"
        type="button"
        aria-label="发送"
        @mousedown.prevent
        @click="onSubmit"
      >
        <span class="send-icon">➤</span>
      </button>
    </div>
    <button
      class="drag-btn"
      title="拖动窗口"
      type="button"
      aria-label="拖动窗口"
      @mousedown.prevent="startWindowDrag"
    >
      <span class="drag-icon">✥</span>
    </button>
    <button
      class="admin-btn"
      title="管理界面"
      type="button"
      aria-label="管理界面"
      @mousedown.prevent
      @click="openAdmin"
    >
      <span class="admin-icon">⚙</span>
    </button>
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
  display: flex;
  gap: 8px;
  width: 100px;
  flex: 0 0 100px;
}

.voice-btn {
  min-width: 0;
  width: 100%;
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

.voice-btn--muted {
  background: rgba(247, 241, 245, 0.95);
  border-color: rgba(201, 152, 170, 0.92);
  color: #8d5a6b;
}

.voice-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.voice-icon {
  font-size: 15px;
  line-height: 1;
}

.input-wrap {
  flex: 1;
  min-width: 0;
  position: relative;
}

.input-field {
  width: 100%;
  flex: 1;
  min-width: 0;
  border: 1.5px solid rgba(255, 179, 198, 0.92);
  border-radius: 999px;
  padding: 10px 44px 10px 14px;
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

.send-icon-btn {
  position: absolute;
  top: 50%;
  right: 4px;
  width: 30px;
  height: 30px;
  border: 0;
  border-radius: 999px;
  background: #ff8cb0;
  color: white;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transform: translateY(-50%);
  transition:
    background 0.15s,
    opacity 0.15s,
    transform 0.15s;
}

.send-icon-btn:hover:not(:disabled) {
  background: #e85f8b;
  transform: translateY(-50%) scale(1.04);
}

.send-icon-btn:disabled {
  opacity: 0.42;
  cursor: default;
}

.send-icon {
  font-size: 13px;
  line-height: 1;
  transform: translateX(1px);
}

.drag-btn,
.admin-btn {
  width: 40px;
  height: 38px;
  border: 1.5px solid rgba(255, 179, 198, 0.92);
  border-radius: 999px;
  background: #fff0f5;
  color: #c0405f;
  font-size: 14px;
  cursor: grab;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 40px;
  transition:
    background 0.15s,
    border-color 0.15s,
    transform 0.15s;
  box-shadow: 0 10px 22px rgba(15, 23, 42, 0.14);
}

.drag-btn {
  cursor: grab;
}

.admin-btn {
  cursor: pointer;
}

.drag-btn:hover,
.admin-btn:hover {
  background: #ffe0eb;
  border-color: #ff8cb0;
  transform: translateY(-1px);
}

.drag-btn:active {
  cursor: grabbing;
}

.drag-icon {
  font-size: 15px;
  line-height: 1;
}

.admin-icon {
  font-size: 16px;
  line-height: 1;
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
