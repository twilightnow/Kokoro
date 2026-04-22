<script setup lang="ts">
import { ref, nextTick } from 'vue'

const emit = defineEmits<{ (e: 'submit', text: string): void }>()

const visible  = ref(false)
const draft    = ref('')
const inputRef = ref<HTMLInputElement | null>(null)

function show(): void {
  visible.value = true
  nextTick(() => inputRef.value?.focus())
}

function hide(): void {
  visible.value = false
  draft.value = ''
}

function onSubmit(): void {
  const text = draft.value.trim()
  if (!text) return
  emit('submit', text)
  hide()
}

function onKeydown(e: KeyboardEvent): void {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    onSubmit()
  } else if (e.key === 'Escape') {
    hide()
  }
}

defineExpose({ show, hide })
</script>

<template>
  <Transition name="inputbar">
    <div v-if="visible" class="input-bar">
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
  </Transition>
</template>

<style scoped>
.input-bar {
  display: flex;
  gap: 6px;
  padding: 8px 4px 0;
}

.input-field {
  flex: 1;
  border: 1.5px solid #ffb3c6;
  border-radius: 8px;
  padding: 6px 10px;
  font-size: 13px;
  outline: none;
  background: rgba(255, 255, 255, 0.95);
  color: #333;
  font-family: inherit;
}

.input-field:focus {
  border-color: #ff8cb0;
  box-shadow: 0 0 0 2px rgba(255, 140, 176, 0.2);
}

.send-btn {
  border: 1.5px solid #ffb3c6;
  border-radius: 8px;
  background: #fff0f5;
  color: #c0405f;
  padding: 6px 12px;
  font-size: 13px;
  cursor: pointer;
  transition: background 0.15s;
  white-space: nowrap;
}

.send-btn:hover {
  background: #ffe0eb;
}

.inputbar-enter-active,
.inputbar-leave-active {
  transition: opacity 0.2s ease;
}

.inputbar-enter-from,
.inputbar-leave-to {
  opacity: 0;
}
</style>
