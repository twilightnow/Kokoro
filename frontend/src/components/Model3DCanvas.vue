<script setup lang="ts">
import {
  AnimationClip,
  AmbientLight,
  Box3,
  Clock,
  Color,
  DirectionalLight,
  MathUtils,
  Object3D,
  PerspectiveCamera,
  Scene,
  Vector3,
  WebGLRenderer,
} from 'three'
import { MMDAnimationHelper, MMDLoader } from 'three-stdlib'
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import type { Model3DSkinConfig, Mood } from '../types/chat'

const props = defineProps<{
  skin: Model3DSkinConfig
  mood: Mood
  lipSyncLevel: number
}>()

const hostRef = ref<HTMLDivElement | null>(null)
const errorText = ref('')

const moodColors: Record<string, string> = {
  normal: '#f6fbff',
  happy: '#ffeab6',
  angry: '#ffd0c6',
  shy: '#ffe0f0',
  cold: '#dff1ff',
}

let renderer: WebGLRenderer | null = null
let scene: Scene | null = null
let camera: PerspectiveCamera | null = null
let ambientLight: AmbientLight | null = null
let directionalLight: DirectionalLight | null = null
type MorphCapableObject = Object3D & {
  morphTargetDictionary?: Record<string, number>
  morphTargetInfluences?: number[]
}

let currentModel: Object3D | null = null
let loader: MMDLoader | null = null
let helper: MMDAnimationHelper | null = null
let clock: Clock | null = null
let animationPlaying = false
let resizeObserver: ResizeObserver | null = null
let animationFrame = 0
let disposed = false
let activeAnimationUrl = ''
let smoothedLipSync = 0

function disposeMaterial(material: unknown): void {
  if (!material || typeof material !== 'object') {
    return
  }

  const disposable = material as { dispose?: () => void; map?: { dispose?: () => void } | null }
  disposable.map?.dispose?.()
  disposable.dispose?.()
}

function disposeModel(): void {
  if (!currentModel) {
    return
  }

  disposeAnimation()

  currentModel.traverse((child: Object3D) => {
    const mesh = child as {
      geometry?: { dispose?: () => void }
      material?: unknown
    }

    mesh.geometry?.dispose?.()
    if (Array.isArray(mesh.material)) {
      mesh.material.forEach(disposeMaterial)
      return
    }
    disposeMaterial(mesh.material)
  })

  scene?.remove(currentModel)
  currentModel = null
}

function disposeAnimation(): void {
  if (helper && currentModel) {
    try {
      helper.remove(currentModel as never)
    } catch {
      // Helper state can already be detached.
    }
  }
  helper = null
  animationPlaying = false
  activeAnimationUrl = ''
}

function resizeRenderer(): void {
  if (!hostRef.value || !renderer || !camera) {
    return
  }

  const width = Math.max(hostRef.value.clientWidth, 1)
  const height = Math.max(hostRef.value.clientHeight, 1)

  renderer.setSize(width, height, false)
  camera.aspect = width / height
  camera.updateProjectionMatrix()
}

function applyLighting(): void {
  if (!ambientLight || !directionalLight) {
    return
  }

  const baseColor = new Color(moodColors[props.mood] ?? moodColors.normal)
  ambientLight.color.copy(baseColor)
  directionalLight.color.copy(baseColor)
  ambientLight.intensity = props.skin.lights.ambient_intensity
  directionalLight.intensity = props.skin.lights.directional_intensity
  directionalLight.position.set(
    props.skin.lights.directional_position.x,
    props.skin.lights.directional_position.y,
    props.skin.lights.directional_position.z,
  )
}

function applyCamera(): void {
  if (!camera) {
    return
  }

  const target = new Vector3(
    props.skin.camera.target.x,
    props.skin.camera.target.y,
    props.skin.camera.target.z,
  )

  camera.fov = props.skin.camera.fov
  camera.position.set(0, target.y, props.skin.camera.distance)
  camera.lookAt(target)
  camera.updateProjectionMatrix()
}

function applyModelTransform(): void {
  if (!currentModel) {
    return
  }

  currentModel.scale.setScalar(props.skin.scale)
  currentModel.position.set(
    props.skin.position.x,
    props.skin.position.y,
    props.skin.position.z,
  )
  currentModel.rotation.set(
    MathUtils.degToRad(props.skin.rotation_deg.x),
    MathUtils.degToRad(props.skin.rotation_deg.y),
    MathUtils.degToRad(props.skin.rotation_deg.z),
  )
}

function resolveAnimationUrl(): string {
  return props.skin.mood_vmd_urls?.[props.mood] ?? props.skin.vmd_url ?? ''
}

function resolveProceduralMotion(): string {
  return props.skin.mood_procedural_motions?.[props.mood]
    ?? props.skin.procedural_motion
    ?? 'idle'
}

function findMorphIndex(mesh: MorphCapableObject, name: string): number {
  const dictionary = mesh.morphTargetDictionary
  if (!dictionary) {
    return -1
  }

  const direct = dictionary[name]
  if (typeof direct === 'number') {
    return direct
  }

  const normalized = name.trim().toLowerCase()
  for (const [key, index] of Object.entries(dictionary)) {
    if (key.trim().toLowerCase() === normalized) {
      return index
    }
  }

  return -1
}

function applyMorphWeights(): void {
  if (!currentModel) {
    return
  }

  const morphConfig = props.skin.morphs
  if (!morphConfig) {
    return
  }

  const targetWeights = new Map<string, number>()
  for (const weights of Object.values(morphConfig.mood_weights ?? {})) {
    for (const item of weights) {
      targetWeights.set(item.name, 0)
    }
  }

  for (const item of morphConfig.mood_weights?.[props.mood] ?? []) {
    targetWeights.set(item.name, item.weight)
  }

  const lipSync = morphConfig.lip_sync
  if (lipSync?.names?.length) {
    smoothedLipSync = MathUtils.lerp(smoothedLipSync, props.lipSyncLevel, lipSync.smoothing)
    const mouthWeight = Math.min(1, smoothedLipSync) * lipSync.max_weight
    for (const name of lipSync.names) {
      targetWeights.set(name, Math.max(targetWeights.get(name) ?? 0, mouthWeight))
    }
  } else {
    smoothedLipSync = 0
  }

  currentModel.traverse((child) => {
    const mesh = child as MorphCapableObject
    if (!mesh.morphTargetDictionary || !mesh.morphTargetInfluences) {
      return
    }

    for (const [name, weight] of targetWeights.entries()) {
      const index = findMorphIndex(mesh, name)
      if (index >= 0) {
        mesh.morphTargetInfluences[index] = weight
      }
    }
  })
}

async function loadAnimationForCurrentMood(force = false): Promise<void> {
  if (!loader || !currentModel || disposed) {
    return
  }

  const nextAnimationUrl = resolveAnimationUrl()
  if (!force && nextAnimationUrl === activeAnimationUrl) {
    return
  }

  disposeAnimation()
  if (!nextAnimationUrl) {
    return
  }

  helper = new MMDAnimationHelper({ resetPhysicsOnLoop: true })
  await new Promise<void>((resolve) => {
    loader!.loadAnimation(
      nextAnimationUrl,
      currentModel as never,
      (clip) => {
        helper!.add(currentModel as never, { animation: clip as AnimationClip, physics: false })
        animationPlaying = true
        activeAnimationUrl = nextAnimationUrl
        console.info('[model3d] animation loaded:', nextAnimationUrl)
        resolve()
      },
      undefined,
      (err) => {
        console.warn('[model3d] failed to load animation', err)
        disposeAnimation()
        resolve()
      },
    )
  })
}

async function loadModel(): Promise<void> {
  if (!loader || !scene || disposed) {
    return
  }

  errorText.value = ''
  disposeModel()

  console.info('[model3d] loading', props.skin.model_url)

  try {
    const model = await loader.loadAsync(props.skin.model_url)

    if (disposed) {
      return
    }

    currentModel = model
    applyModelTransform()
    scene.add(model)

    // Log bounding box to help verify scale/position settings.
    const box = new Box3().setFromObject(model)
    const size = box.getSize(new Vector3())
    const center = box.getCenter(new Vector3())
    console.info('[model3d] loaded — size:', size, 'center:', center)

    await loadAnimationForCurrentMood(true)
  } catch (error) {
    console.error('[model3d] failed to load model', error)
    errorText.value = '3D 模型加载失败'
  }
}

function renderFrame(): void {
  if (disposed || !renderer || !scene || !camera) {
    return
  }

  const delta = clock?.getDelta() ?? 0

  if (animationPlaying && helper) {
    helper.update(delta)
  } else if (currentModel) {
    const t = performance.now()
    const baseRotation = MathUtils.degToRad(props.skin.rotation_deg.y)
    const mode = resolveProceduralMotion()

    switch (mode) {
      case 'cheer':
        currentModel.rotation.y = baseRotation + Math.sin(t / 380) * 0.065
        currentModel.position.y = props.skin.position.y + Math.abs(Math.sin(t / 300)) * 0.22
        break
      case 'stomp':
        currentModel.rotation.y = baseRotation + Math.sin(t / 220) * 0.02
        currentModel.position.y = props.skin.position.y + Math.max(0, Math.sin(t / 180)) * 0.12
        break
      case 'glide':
        currentModel.rotation.y = baseRotation + Math.sin(t / 1200) * 0.018
        currentModel.position.y = props.skin.position.y + Math.sin(t / 2600) * 0.035
        break
      case 'breathe':
        currentModel.rotation.y = baseRotation + Math.sin(t / 1100) * 0.015
        currentModel.position.y = props.skin.position.y + Math.sin(t / 1800) * 0.08
        break
      default:
        currentModel.rotation.y = baseRotation + Math.sin(t / 900) * 0.025
        currentModel.position.y = props.skin.position.y + Math.sin(t / 2000) * 0.06
        break
    }
  }

  applyMorphWeights()

  renderer.render(scene, camera)
  animationFrame = window.requestAnimationFrame(renderFrame)
}

function mountRenderer(): void {
  if (!hostRef.value) {
    return
  }

  renderer = new WebGLRenderer({ alpha: true, antialias: true })
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2))
  renderer.setClearAlpha(0)

  scene = new Scene()
  camera = new PerspectiveCamera(30, 1, 0.1, 5000)
  ambientLight = new AmbientLight(0xffffff, props.skin.lights.ambient_intensity)
  directionalLight = new DirectionalLight(0xffffff, props.skin.lights.directional_intensity)
  loader = new MMDLoader()
  clock = new Clock()

  scene.add(ambientLight)
  scene.add(directionalLight)

  resizeRenderer()
  applyCamera()
  applyLighting()

  hostRef.value.replaceChildren(renderer.domElement)
  resizeObserver = new ResizeObserver(() => {
    resizeRenderer()
  })
  resizeObserver.observe(hostRef.value)
  animationFrame = window.requestAnimationFrame(renderFrame)
}

onMounted(async () => {
  mountRenderer()
  await loadModel()
})

// Only reload the model when the URL actually changes; apply visual updates otherwise.
// This prevents the 3-second state sync from causing flickering.
watch(
  () => props.skin,
  async (newSkin, oldSkin) => {
    if (!renderer) {
      return
    }

    applyCamera()
    applyLighting()
    applyModelTransform()

    const nextAnimationUrl = newSkin.mood_vmd_urls?.[props.mood] ?? newSkin.vmd_url ?? ''
    const prevAnimationUrl = oldSkin?.mood_vmd_urls?.[props.mood] ?? oldSkin?.vmd_url ?? ''

    if (!oldSkin || newSkin.model_url !== oldSkin.model_url) {
      await loadModel()
      return
    }

    if (nextAnimationUrl !== prevAnimationUrl) {
      await loadAnimationForCurrentMood()
    }
  },
  { deep: true },
)

watch(
  () => props.mood,
  async () => {
    applyLighting()
    await loadAnimationForCurrentMood()
  },
)

onBeforeUnmount(() => {
  disposed = true
  window.cancelAnimationFrame(animationFrame)
  resizeObserver?.disconnect()
  resizeObserver = null
  disposeModel()
  renderer?.dispose()
  renderer?.forceContextLoss()
  hostRef.value?.replaceChildren()
  renderer = null
  scene = null
  camera = null
  ambientLight = null
  directionalLight = null
  loader = null
  clock = null
})
</script>

<template>
  <div class="model3d-stage">
    <div ref="hostRef" class="model3d-canvas" />
    <div v-if="errorText" class="model3d-error">{{ errorText }}</div>
  </div>
</template>

<style scoped>
.model3d-stage {
  width: 100%;
  flex: 1;
  min-height: 0;
  display: flex;
  align-items: stretch;
  justify-content: center;
  position: relative;
}

.model3d-canvas {
  width: 100%;
  height: 100%;
  min-height: 0;
}

.model3d-error {
  position: absolute;
  inset: auto 0 20px;
  margin: 0 auto;
  width: fit-content;
  max-width: calc(100% - 24px);
  padding: 6px 12px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.82);
  border: 1px solid rgba(207, 88, 88, 0.25);
  color: #8f2b2b;
  font-size: 12px;
  letter-spacing: 0.5px;
}

:deep(canvas) {
  width: 100%;
  height: 100%;
  display: block;
}
</style>
