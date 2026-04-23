<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  text: string
  isThinking: boolean
  actions?: string[]
}>()

const emit = defineEmits<{ (e: 'action', text: string): void }>()

const visible = computed(() => props.isThinking || Boolean(props.text))
</script>

<template>
  <Transition name="bubble">
    <div v-if="visible" class="bubble-box">
      <span v-if="isThinking" class="thinking-dots">
        <span /><span /><span />
      </span>
      <span v-else>{{ text }}</span>
      <div v-if="!isThinking && actions?.length" class="actions">
        <button
          v-for="action in actions"
          :key="action"
          class="action-btn"
          @click="emit('action', action)"
        >
          {{ action }}
        </button>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.bubble-box {
  position: relative;
  width: fit-content;
  max-width: 100%;
  margin-inline: auto;
  background: rgba(255, 255, 255, 0.94);
  border: 1.5px solid #f2a4b8;
  border-radius: 18px;
  padding: 12px 16px;
  font-size: 13px;
  color: #333;
  min-height: 44px;
  font-family: 'Hiragino Kaku Gothic Pro', 'Meiryo', sans-serif;
  line-height: 1.5;
  box-shadow: 0 14px 28px rgba(15, 23, 42, 0.16);
}

.bubble-box::after {
  content: '';
  position: absolute;
  left: 34px;
  bottom: -8px;
  width: 14px;
  height: 14px;
  background: rgba(255, 255, 255, 0.94);
  border-right: 1.5px solid #f2a4b8;
  border-bottom: 1.5px solid #f2a4b8;
  transform: rotate(45deg);
  pointer-events: none;
}

.bubble-enter-active,
.bubble-leave-active {
  transition: opacity 0.3s ease, transform 0.3s ease;
}

.bubble-enter-from {
  opacity: 0;
  transform: translateY(8px);
}

.bubble-leave-to {
  opacity: 0;
  transform: translateY(4px);
}

.thinking-dots {
  display: inline-flex;
  gap: 4px;
  align-items: center;
  height: 20px;
}

.thinking-dots span {
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #ff8cb0;
  animation: bounce 1.2s infinite ease-in-out;
}

.thinking-dots span:nth-child(2) {
  animation-delay: 0.2s;
}

.thinking-dots span:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes bounce {
  0%,
  80%,
  100% {
    transform: translateY(0);
  }
  40% {
    transform: translateY(-6px);
  }
}

.actions {
  display: flex;
  gap: 6px;
  margin-top: 8px;
  flex-wrap: wrap;
}

.action-btn {
  background: #fff0f5;
  border: 1px solid #ffb3c6;
  border-radius: 8px;
  padding: 3px 10px;
  font-size: 12px;
  color: #c0405f;
  cursor: pointer;
  transition: background 0.15s;
}

.action-btn:hover {
  background: #ffe0eb;
}

.bubble-box > span {
  white-space: pre-wrap;
}
</style>
