<script setup lang="ts">
import type { Mood } from '../types/chat'
import { computed } from 'vue'

const props = defineProps<{
  mood: Mood
  characterName?: string
  turn?: number
}>()
const emit = defineEmits<{ (e: 'click'): void }>()

type MoodVisual = { emoji: string; label: string; bg: string; border: string; text: string }

const moodConfig: Record<string, MoodVisual> = {
  normal: { emoji: '( ˘ω˘ )',   label: '普通', bg: 'rgba(200,210,230,0.55)', border: '#9aafc8', text: '#3a5068' },
  happy:  { emoji: '( ´ ▽ ` )', label: '开心', bg: 'rgba(255,220,100,0.55)', border: '#e0b840', text: '#7a5800' },
  angry:  { emoji: '( `д´ )',    label: '生气', bg: 'rgba(255,120,100,0.55)', border: '#d95040', text: '#7a1a10' },
  shy:    { emoji: '(〃▽〃)',    label: '害羞', bg: 'rgba(255,182,193,0.55)', border: '#f090a8', text: '#8a3050' },
  cold:   { emoji: '( ー_ー )',  label: '冷淡', bg: 'rgba(160,200,230,0.55)', border: '#70a8c8', text: '#1a4060' },
}

const fallbackMood: MoodVisual = {
  emoji: '( -_- )',
  label: '状态',
  bg: 'rgba(190, 200, 215, 0.52)',
  border: '#8a99ac',
  text: '#304256',
}

const currentMood = computed<MoodVisual>(() => {
  const visual = moodConfig[props.mood]
  if (visual) return visual
  return {
    ...fallbackMood,
    label: props.mood || fallbackMood.label,
  }
})
</script>

<template>
  <div
    class="sprite-panel"
    :style="{ background: currentMood.bg, borderColor: currentMood.border }"
    @click="emit('click')"
  >
    <!-- 角色名 -->
    <div v-if="characterName" class="char-name" :style="{ color: currentMood.text }">
      {{ characterName }}
    </div>

    <!-- 表情区域 -->
    <Transition name="sprite" mode="out-in">
      <div :key="mood" class="sprite-inner">
        <div class="sprite-emoji">{{ currentMood.emoji }}</div>
        <div class="sprite-label" :style="{ color: currentMood.text }">
          {{ currentMood.label }}
        </div>
      </div>
    </Transition>

    <!-- 底部信息栏 -->
    <div class="sprite-footer" :style="{ color: currentMood.text }">
      <span v-if="turn !== undefined && turn > 0">第 {{ turn }} 轮</span>
      <span v-else class="hint">点击开始对话</span>
    </div>
  </div>
</template>

<style scoped>
.sprite-panel {
  width: 200px;
  height: 320px;
  border: 2px solid;
  border-radius: 20px;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: space-between;
  padding: 16px 12px 14px;
  transition: background 0.4s ease, border-color 0.4s ease;
  -webkit-app-region: no-drag;
}

.sprite-panel:hover {
  filter: brightness(1.05);
}

.char-name {
  font-size: 13px;
  font-family: 'Hiragino Kaku Gothic Pro', 'Meiryo', sans-serif;
  font-weight: bold;
  letter-spacing: 2px;
  opacity: 0.85;
  align-self: flex-start;
}

.sprite-inner {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  user-select: none;
}

.sprite-emoji {
  font-size: 26px;
  line-height: 1;
  letter-spacing: 2px;
}

.sprite-label {
  font-size: 11px;
  font-family: 'Hiragino Kaku Gothic Pro', 'Meiryo', sans-serif;
  letter-spacing: 4px;
  opacity: 0.75;
}

.sprite-footer {
  font-size: 11px;
  font-family: 'Hiragino Kaku Gothic Pro', 'Meiryo', sans-serif;
  opacity: 0.6;
  letter-spacing: 1px;
  align-self: flex-end;
}

.hint {
  opacity: 0.5;
}

.sprite-enter-active,
.sprite-leave-active {
  transition: opacity 0.25s ease, transform 0.25s ease;
}
.sprite-enter-from { opacity: 0; transform: scale(0.92); }
.sprite-leave-to   { opacity: 0; transform: scale(1.06); }
</style>
