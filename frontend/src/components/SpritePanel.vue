<script setup lang="ts">
import { computed, defineAsyncComponent, ref, watch } from 'vue'
import type { CharacterDisplayConfig, Model3DSkinConfig, Mood } from '../types/chat'

const Live2DCanvas = defineAsyncComponent(() => import('./Live2DCanvas.vue'))
const Model3DCanvas = defineAsyncComponent(() => import('./Model3DCanvas.vue'))

const props = defineProps<{
  mood: Mood
  characterId?: string
  characterName?: string
  display?: CharacterDisplayConfig
  turn?: number
}>()

type MoodVisual = { emoji: string; label: string; bg: string; border: string; text: string }

const moodConfig: Record<string, MoodVisual> = {
  normal: { emoji: '( •_• )', label: '平静', bg: 'rgba(200,210,230,0.55)', border: '#9aafc8', text: '#3a5068' },
  happy: { emoji: '( ^_^ )', label: '开心', bg: 'rgba(255,220,100,0.55)', border: '#e0b840', text: '#7a5800' },
  angry: { emoji: '( >_< )', label: '生气', bg: 'rgba(255,120,100,0.55)', border: '#d95040', text: '#7a1a10' },
  shy: { emoji: '( ˶ᵔ ᵕ ᵔ˶ )', label: '害羞', bg: 'rgba(255,182,193,0.55)', border: '#f090a8', text: '#8a3050' },
  cold: { emoji: '( -.- )', label: '冷淡', bg: 'rgba(160,200,230,0.55)', border: '#70a8c8', text: '#1a4060' },
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

const live2dConfig = computed(() => (
  props.display?.mode === 'live2d' ? props.display.live2d : undefined
))

const model3dConfig = computed(() => (
  props.display?.mode === 'model3d' ? props.display.model3d : undefined
))

const manualSkinId = ref('')

watch(
  () => [props.characterId, props.display?.mode, model3dConfig.value?.default_skin],
  () => {
    manualSkinId.value = ''
  },
)

const model3dSkins = computed(() => {
  const config = model3dConfig.value
  if (!config) {
    return [] as Array<{ id: string; skin: Model3DSkinConfig }>
  }

  return config.skin_order
    .map((skinId) => {
      const skin = config.skins[skinId]
      return skin ? { id: skinId, skin } : null
    })
    .filter((value): value is { id: string; skin: Model3DSkinConfig } => value !== null)
})

const autoSkinId = computed(() => {
  const config = model3dConfig.value
  if (!config?.auto_switch.enabled) {
    return ''
  }

  const mappedSkinId = config.auto_switch.mood_skins[props.mood]
  return mappedSkinId && config.skins[mappedSkinId] ? mappedSkinId : ''
})

const activeModel3dSkinId = computed(() => {
  const config = model3dConfig.value
  if (!config) {
    return ''
  }

  if (manualSkinId.value && (!config.auto_switch.enabled || config.auto_switch.prefer_manual)) {
    return manualSkinId.value
  }

  if (autoSkinId.value) {
    return autoSkinId.value
  }

  if (manualSkinId.value) {
    return manualSkinId.value
  }

  return config.default_skin
})

const activeModel3dSkin = computed(() => {
  const config = model3dConfig.value
  if (!config) {
    return undefined
  }
  return config.skins[activeModel3dSkinId.value] ?? config.skins[config.default_skin]
})

const activeSkinLabel = computed(() => activeModel3dSkin.value?.label ?? '')

const spriteKey = computed(() => {
  const base = `${props.characterId || props.characterName || 'default'}:${props.display?.mode || 'placeholder'}`
  if (activeModel3dSkinId.value) {
    return `${base}:${activeModel3dSkinId.value}`
  }
  return live2dConfig.value ? base : `${base}:${props.mood}`
})

function toggleSkin(skinId: string): void {
  manualSkinId.value = manualSkinId.value === skinId ? '' : skinId
}

function clearManualSkin(): void {
  manualSkinId.value = ''
}
</script>

<template>
  <div class="sprite-panel">
    <div v-if="characterName" class="char-name" :style="{ color: currentMood.text }">
      {{ characterName }}
    </div>

    <Transition name="sprite" mode="out-in">
      <div :key="spriteKey" class="sprite-inner">
        <Live2DCanvas
          v-if="live2dConfig"
          :config="live2dConfig"
          :mood="mood"
        />
        <Model3DCanvas
          v-else-if="activeModel3dSkin"
          :skin="activeModel3dSkin"
          :mood="mood"
        />
        <template v-else>
          <div class="sprite-emoji">{{ currentMood.emoji }}</div>
          <div class="sprite-label" :style="{ color: currentMood.text }">
            {{ currentMood.label }}
          </div>
        </template>

        <div v-if="model3dSkins.length" class="skin-switcher">
          <button
            class="skin-chip"
            :class="{ 'skin-chip--active': !manualSkinId }"
            type="button"
            @click="clearManualSkin"
          >
            自动
          </button>
          <button
            v-for="item in model3dSkins"
            :key="item.id"
            class="skin-chip"
            :class="{ 'skin-chip--active': activeModel3dSkinId === item.id }"
            type="button"
            @click="toggleSkin(item.id)"
          >
            {{ item.skin.label }}
          </button>
        </div>
      </div>
    </Transition>

    <div class="sprite-footer" :style="{ color: currentMood.text }">
      <span v-if="activeSkinLabel" class="skin-label">{{ activeSkinLabel }}</span>
      <span v-if="turn !== undefined && turn > 0">第 {{ turn }} 轮</span>
      <span v-else class="hint">点击开始对话</span>
    </div>
  </div>
</template>

<style scoped>
.sprite-panel {
  width: 100%;
  height: 100%;
  cursor: default;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: space-between;
  padding: 20px 8px 10px;
  -webkit-app-region: no-drag;
}

.char-name {
  font-size: 13px;
  font-family: 'Hiragino Kaku Gothic Pro', 'Meiryo', sans-serif;
  font-weight: bold;
  letter-spacing: 2px;
  opacity: 0.85;
  align-self: flex-start;
  text-shadow: 0 2px 8px rgba(255, 255, 255, 0.72);
}

.sprite-inner {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  user-select: none;
  width: 100%;
  flex: 1;
  min-height: 0;
}

.sprite-emoji {
  font-size: 38px;
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
  align-self: center;
  text-shadow: 0 2px 8px rgba(255, 255, 255, 0.72);
  display: flex;
  gap: 10px;
  align-items: center;
}

.hint {
  opacity: 0.5;
}

.skin-switcher {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: center;
  align-items: center;
  max-width: 100%;
}

.skin-chip {
  border: 1px solid rgba(138, 153, 172, 0.36);
  background: rgba(255, 255, 255, 0.62);
  color: #304256;
  border-radius: 999px;
  padding: 4px 10px;
  font-size: 11px;
  letter-spacing: 0.5px;
  cursor: pointer;
}

.skin-chip--active {
  border-color: rgba(88, 118, 146, 0.65);
  background: rgba(232, 240, 249, 0.92);
}

.skin-label {
  font-size: 10px;
  letter-spacing: 2px;
  opacity: 0.78;
}

.sprite-enter-active,
.sprite-leave-active {
  transition: opacity 0.25s ease, transform 0.25s ease;
}

.sprite-enter-from {
  opacity: 0;
  transform: scale(0.92);
}

.sprite-leave-to {
  opacity: 0;
  transform: scale(1.06);
}
</style>
