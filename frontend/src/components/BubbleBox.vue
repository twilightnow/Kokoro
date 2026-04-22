<script setup lang="ts">
import { ref, watch } from 'vue'

const props = defineProps<{
  text: string
  isThinking: boolean
  actions?: string[]
}>()

const emit = defineEmits<{ (e: 'action', text: string): void }>()

const visible = ref(false)

// 思考開始 or テキスト更新でバブルを表示。
// 非表示にするのは親コンポーネントの責務（次のメッセージ送信時に自然に置き換わる）。
watch(
  () => props.isThinking,
  (thinking) => {
    if (thinking) visible.value = true
  },
)

watch(
  () => props.text,
  (text) => {
    if (text) visible.value = true
  },
)
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
  background: rgba(255, 255, 255, 0.92);
  border: 2px solid #ffb3c6;
  border-radius: 12px;
  padding: 10px 14px;
  font-size: 13px;
  color: #333;
  min-height: 42px;
  font-family: 'Hiragino Kaku Gothic Pro', 'Meiryo', sans-serif;
  line-height: 1.5;
  box-shadow: 0 2px 8px rgba(255, 100, 150, 0.15);
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
</style>
