<script setup lang="ts">
import {
  AmbientLight,
  Box3,
  Color,
  DirectionalLight,
  MathUtils,
  Object3D,
  PerspectiveCamera,
  Scene,
  SkinnedMesh,
  Vector3,
  WebGLRenderer,
} from 'three'
import { MMDLoader } from 'three-stdlib'
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import type { Model3DSkinConfig, Mood } from '../types/chat'

const props = defineProps<{
  skin: Model3DSkinConfig
  mood: Mood
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
let currentModel: SkinnedMesh | null = null
let loader: MMDLoader | null = null
let resizeObserver: ResizeObserver | null = null
let animationFrame = 0
let disposed = false

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
    console.info('[model3d] camera target.y:', props.skin.camera.target.y, 'distance:', props.skin.camera.distance)
  } catch (error) {
    console.error('[model3d] failed to load model', error)
    errorText.value = '3D 模型加载失败'
  }
}

function renderFrame(): void {
  if (disposed || !renderer || !scene || !camera) {
    return
  }

  if (currentModel) {
    currentModel.rotation.y = MathUtils.degToRad(props.skin.rotation_deg.y)
      + Math.sin(performance.now() / 900) * 0.025
  }

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

watch(
  () => props.skin,
  async () => {
    if (!renderer) {
      return
    }

    applyCamera()
    applyLighting()
    await loadModel()
  },
  { deep: true },
)

watch(
  () => props.mood,
  () => {
    applyLighting()
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