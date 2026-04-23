<script setup lang="ts">
import { nextTick, ref } from 'vue'

const emit = defineEmits<{ (e: 'submit', text: string): void }>()

const draft = ref('')
const inputRef = ref<HTMLInputElement | null>(null)

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
</template>

<style scoped>
.input-bar {
  display: flex;
  gap: 8px;
  align-items: center;
  width: 100%;
}

.input-field {
  flex: 1;
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
</style>
