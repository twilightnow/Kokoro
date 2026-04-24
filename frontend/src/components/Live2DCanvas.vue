<script setup lang="ts">
import * as PIXI from 'pixi.js'
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import type { Live2DDisplayConfig, Mood } from '../types/chat'

const props = defineProps<{
  config: Live2DDisplayConfig
  mood: Mood
  lipSyncLevel: number
}>()

const hostRef = ref<HTMLDivElement | null>(null)
const canvasRef = ref<HTMLDivElement | null>(null)
const errorText = ref('')
let app: PIXI.Application | null = null
type Live2DModule = typeof import('pixi-live2d-display/cubism4')
type Live2DModelInstance = InstanceType<Live2DModule['Live2DModel']>

let live2dModule: Live2DModule | null = null
let model: Live2DModelInstance | null = null
let resizeObserver: ResizeObserver | null = null
let cubismStarted = false
let naturalBounds = { x: 0, y: 0, width: 1, height: 1 }

function ensurePixiGlobal(): void {
  ;(window as Window & { PIXI?: typeof PIXI }).PIXI = PIXI
}

async function ensureCubismCore(): Promise<void> {
  if ((window as Window & { Live2DCubismCore?: unknown }).Live2DCubismCore) return

  await new Promise<void>((resolve, reject) => {
    const src = '/vendor/live2d/live2dcubismcore.min.js'
    const existing = document.querySelector(`script[src="${src}"]`) as HTMLScriptElement | null
    if (existing) {
      existing.addEventListener('load', () => resolve(), { once: true })
      existing.addEventListener('error', () => reject(new Error('Failed to load Cubism Core')), { once: true })
      return
    }

    const script = document.createElement('script')
    script.src = src
    script.async = true
    script.onload = () => resolve()
    script.onerror = () => reject(new Error('Failed to load Cubism Core'))
    document.head.appendChild(script)
  })
}

async function ensureCubismReady(): Promise<void> {
  await ensureCubismCore()
  ensurePixiGlobal()

  if (!live2dModule) {
    live2dModule = await import('pixi-live2d-display/cubism4')
  }

  if (!cubismStarted) {
    live2dModule.startUpCubism4()
    cubismStarted = true
  }
  await live2dModule.cubism4Ready()
}

function measureModelBounds(): void {
  if (!model) return
  const bounds = model.getLocalBounds()
  naturalBounds = {
    x: bounds.x,
    y: bounds.y,
    width: Math.max(bounds.width, 1),
    height: Math.max(bounds.height, 1),
  }
}

function fitModel(): void {
  if (!hostRef.value || !app || !model) return

  const width = Math.max(hostRef.value.clientWidth, 1)
  const height = Math.max(hostRef.value.clientHeight, 1)
  app.renderer.resize(width, height)

  const usableWidth = width * 0.98
  const usableHeight = height * 0.94
  const baseScale = Math.min(
    usableWidth / naturalBounds.width,
    usableHeight / naturalBounds.height,
  )
  const visualScale = Math.max(baseScale * props.config.scale, 0.01)

  model.scale.set(visualScale)
  model.pivot.set(
    naturalBounds.x + naturalBounds.width / 2,
    naturalBounds.y + naturalBounds.height / 2,
  )
  model.position.set(
    width / 2 + props.config.offset_x,
    height / 2 + props.config.offset_y - height * 0.02,
  )
}

async function playMotion(group?: string): Promise<void> {
  if (!model || !group) return
  try {
    await model.motion(group)
  } catch {
    // Missing motion groups should not break the renderer.
  }
}

function applyLipSync(level: number): void {
  const coreModel = (model as unknown as {
    internalModel?: {
      coreModel?: {
        setParameterValueById?: (id: string, value: number) => void
      }
    }
  }).internalModel?.coreModel
  if (!coreModel?.setParameterValueById) {
    return
  }

  const normalized = Math.max(0, Math.min(level, 1))
  try {
    coreModel.setParameterValueById('ParamMouthOpenY', normalized)
    coreModel.setParameterValueById('ParamMouthForm', Math.min(1, normalized * 0.35))
  } catch {
    // Some models may not expose mouth parameters.
  }
}

async function mountModel(): Promise<void> {
  if (!hostRef.value) return
  errorText.value = ''

  ensurePixiGlobal()
  await ensureCubismReady()

  if (!app) {
    app = new PIXI.Application({
      width: Math.max(hostRef.value.clientWidth, 1),
      height: Math.max(hostRef.value.clientHeight, 1),
      backgroundAlpha: 0,
      antialias: true,
      autoStart: true,
    })
    canvasRef.value?.replaceChildren(app.view)
  }

  if (model) {
    app.stage.removeChild(model)
    model.destroy()
    model = null
  }

  model = await live2dModule!.Live2DModel.from(props.config.model_url, { autoInteract: false })
  measureModelBounds()

  app.stage.addChild(model)
  fitModel()
  await playMotion(props.config.idle_group)
}

async function remount(): Promise<void> {
  await nextTick()
  try {
    await mountModel()
  } catch (error) {
    console.error('[live2d] load failed', error)
    errorText.value = error instanceof Error ? error.message : 'Live2D load failed'
  }
}

onMounted(async () => {
  // Wait two animation frames so the flex layout fully resolves before reading clientHeight.
  await new Promise<void>((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve())))
  await remount()
  if (hostRef.value) {
    resizeObserver = new ResizeObserver(() => fitModel())
    resizeObserver.observe(hostRef.value)
  }
})

watch(
  () => props.config.model_url,
  async () => {
    await remount()
  },
)

watch(
  () => [props.config.scale, props.config.offset_x, props.config.offset_y],
  () => {
    fitModel()
  },
)

watch(
  () => props.mood,
  async (mood) => {
    const group = props.config.mood_motions[mood]
    if (group) {
      await playMotion(group)
    }
  },
)

watch(
  () => props.lipSyncLevel,
  (level) => {
    applyLipSync(level)
  },
)

onBeforeUnmount(() => {
  resizeObserver?.disconnect()
  resizeObserver = null
  if (model && app) {
    app.stage.removeChild(model)
    model.destroy()
    model = null
  }
  naturalBounds = { x: 0, y: 0, width: 1, height: 1 }
  app?.destroy(true, { children: true })
  app = null
})
</script>

<template>
  <div ref="hostRef" class="live2d-host">
    <div ref="canvasRef" class="live2d-canvas" />
    <div v-if="errorText" class="live2d-error">
      {{ errorText }}
    </div>
  </div>
</template>

<style scoped>
.live2d-host {
  width: 100%;
  height: 100%;
  flex: 1;
  min-height: 0;
  cursor: default;
  position: relative;
}

.live2d-canvas {
  position: absolute;
  inset: 0;
}

.live2d-error {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
  text-align: center;
  font-size: 11px;
  line-height: 1.4;
  color: rgba(120, 40, 40, 0.9);
}

.live2d-host :deep(canvas) {
  width: 100%;
  height: 100%;
  display: block;
  pointer-events: none;
}
</style>
