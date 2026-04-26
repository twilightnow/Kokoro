<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import SpritePanel from './components/SpritePanel.vue'
import BubbleBox from './components/BubbleBox.vue'
import InputBar from './components/InputBar.vue'
import { useChatStore } from './stores/chat'
import { useChat } from './composables/useChat'
import { useWindowPosition } from './composables/useWindowPosition'
import { sidecarHttpUrl } from './shared/sidecar'
import { errorDetails, reportClientLog } from './shared/diagnostics'
import type { CharacterDisplayConfig } from './types/chat'
import { useSpeechOutput } from './composables/useSpeechOutput'

type TauriRuntimeWindow = Window & {
  __TAURI_INTERNALS__?: {
    invoke?: unknown
  }
}

function hasTauriInvoke(): boolean {
  if (typeof window === 'undefined') {
    return false
  }

  const tauriWindow = window as TauriRuntimeWindow
  return typeof tauriWindow.__TAURI_INTERNALS__?.invoke === 'function'
}

async function invokeTauriCommand(
  command: string,
  args?: Record<string, unknown>,
): Promise<boolean> {
  if (!hasTauriInvoke()) {
    return false
  }

  try {
    const { invoke } = await import('@tauri-apps/api/core')
    await invoke(command, args)
    return true
  } catch {
    return false
  }
}

async function getTauriWindow() {
  if (!hasTauriInvoke()) {
    return null
  }

  try {
    const { getCurrentWindow } = await import('@tauri-apps/api/window')
    return getCurrentWindow()
  } catch {
    return null
  }
}

const chatStore = useChatStore()
const { status, errorMessage, init, sendMessage, sendProactiveFeedback, syncState } = useChat()
const { restorePosition, startTracking } = useWindowPosition()
const { ttsEnabled, lipSyncLevel, speechError, toggleTts } = useSpeechOutput()

const PASSTHROUGH_KEY = 'kokoro-passthrough-lock'
const MAIN_ALWAYS_ON_TOP_KEY = 'kokoro-main-always-on-top'
const WINDOW_SCALE_KEY = 'kokoro-window-scale'
const CHARACTER_SCALE_KEY = 'kokoro-character-scale'
const CHARACTER_OFFSET_KEY = 'kokoro-character-offset'
const SYNC_REQUEST_KEY = 'kokoro-main-sync-request'
const INPUT_BAR_VISIBLE_KEY = 'kokoro-input-bar-visible'
const SHOW_FRAME_KEY = 'kokoro-show-frame'
const BUBBLE_DURATION_KEY = 'kokoro-bubble-duration'
const LAST_CHARACTER_KEY = 'kokoro-last-character'
const BASE_WINDOW_WIDTH = 360
const BASE_WINDOW_HEIGHT = 620
const passthroughLocked = ref(false)
const alwaysOnTop = ref(false)
const windowScale = ref(1)
const characterScale = ref(1)
const characterOffset = ref({ x: 0, y: 0 })
const showConnectionBanner = ref(false)
const showSpeechBanner = ref(false)
const inputBarVisible = ref(false)
const showFrame = ref(false)
const bubbleDuration = ref(0)
type TauriWindowHandle = Awaited<ReturnType<typeof getTauriWindow>>
let mainTauriWindow: TauriWindowHandle = null
let stopWindowFocusListener: (() => void) | null = null
let stopCharacterSwitchListener: (() => void) | null = null
let stopCloseRequestedListener: (() => void) | null = null
let stateSyncTimer: number | null = null
let connectionBannerTimer: number | null = null
let speechBannerTimer: number | null = null
let bubbleAutoHideTimer: number | null = null

function readStoredNumber(key: string, fallback: number): number {
  const value = Number(localStorage.getItem(key))
  return Number.isFinite(value) ? value : fallback
}

function readStoredOffset(): { x: number; y: number } {
  try {
    const parsed = JSON.parse(localStorage.getItem(CHARACTER_OFFSET_KEY) || '{}') as {
      x?: unknown
      y?: unknown
    }
    const x = typeof parsed.x === 'number' && Number.isFinite(parsed.x) ? parsed.x : 0
    const y = typeof parsed.y === 'number' && Number.isFinite(parsed.y) ? parsed.y : 0
    return { x: clamp(x, -140, 140), y: clamp(y, -180, 180) }
  } catch {
    return { x: 0, y: 0 }
  }
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value))
}

if (import.meta.env.DEV) {
  ;(window as unknown as Record<string, unknown>).__store = chatStore
}

onMounted(async () => {
  // Restore passthrough lock state from localStorage (shared with admin window)
  passthroughLocked.value = localStorage.getItem(PASSTHROUGH_KEY) === '1'
  alwaysOnTop.value = localStorage.getItem(MAIN_ALWAYS_ON_TOP_KEY) !== '0'
  windowScale.value = clamp(readStoredNumber(WINDOW_SCALE_KEY, 1), 0.8, 1.4)
  characterScale.value = clamp(readStoredNumber(CHARACTER_SCALE_KEY, 1), 0.75, 1.45)
  characterOffset.value = readStoredOffset()
  inputBarVisible.value = localStorage.getItem(INPUT_BAR_VISIBLE_KEY) === '1'
  showFrame.value = localStorage.getItem(SHOW_FRAME_KEY) === '1'
  bubbleDuration.value = Number(localStorage.getItem(BUBBLE_DURATION_KEY) || '0')
  const savedCharStr = localStorage.getItem(LAST_CHARACTER_KEY)
  if (savedCharStr) {
    try {
      const saved = JSON.parse(savedCharStr) as { id?: string; name?: string; display?: CharacterDisplayConfig; turn?: number }
      if (saved?.id && saved?.display) {
        chatStore.setCharacterInfo(saved.id, saved.name ?? '', saved.turn ?? 0, saved.display)
      }
    } catch {}
  }
  window.addEventListener('storage', onStorageChange)

  // Respect persisted window behavior instead of changing it on hover.
  await invokeTauriCommand('set_passthrough', { enabled: passthroughLocked.value })
  await invokeTauriCommand('set_main_always_on_top', { enabled: alwaysOnTop.value })
  await applyWindowScale()
  await restorePosition()
  await startTracking()
  await init()

  const syncCurrentState = async () => {
    await syncState()
  }

  const tauriWindow = await getTauriWindow()
  mainTauriWindow = tauriWindow
  if (tauriWindow) {
    stopWindowFocusListener = await tauriWindow.onFocusChanged(async ({ payload }) => {
      if (payload) {
        await syncCurrentState()
      }
    })
  }

  document.addEventListener('visibilitychange', syncOnVisible)
  stateSyncTimer = window.setInterval(() => {
    void syncCurrentState()
  }, 3000)

  if (tauriWindow) {
    try {
      const { listen } = await import('@tauri-apps/api/event')
      stopCharacterSwitchListener = await listen<string>('character-switch-requested', async (event) => {
        const name = event.payload
        try {
          const resp = await fetch(
            sidecarHttpUrl(`/switch-character?name=${encodeURIComponent(name)}`),
            { method: 'POST' },
          )
          if (!resp.ok) throw new Error(await resp.text())
          const data = await resp.json() as {
            character_id: string
            character_name: string
            display?: CharacterDisplayConfig
          }
          chatStore.resetForNewCharacter(
            data.character_id,
            data.character_name,
            data.display ?? { mode: 'placeholder' },
          )
          chatStore.setReply(`[ 已切换到 ${data.character_name} ]`)
        } catch (e) {
          console.error('[tray] character switch failed', e)
        }
      })

      stopCloseRequestedListener = await tauriWindow.onCloseRequested(async (event) => {
        event.preventDefault()
        const { invoke } = await import('@tauri-apps/api/core')
        const pos = await invoke<[number, number]>('get_window_position')
        localStorage.setItem('kokoro-window-position', JSON.stringify({ x: pos[0], y: pos[1] }))
        await tauriWindow.destroy()
      })
    } catch {
      // Browser mode keeps working without window/event bindings.
    }
  }
})

function syncOnVisible(): void {
  if (document.visibilityState === 'visible') {
    void syncState()
  }
}

function onStorageChange(event: StorageEvent): void {
  if (event.key === PASSTHROUGH_KEY) {
    const locked = event.newValue === '1'
    passthroughLocked.value = locked
    void invokeTauriCommand('set_passthrough', { enabled: locked })
  }

  if (event.key === MAIN_ALWAYS_ON_TOP_KEY) {
    alwaysOnTop.value = event.newValue === '1'
    void invokeTauriCommand('set_main_always_on_top', {
      enabled: alwaysOnTop.value,
    })
  }

  if (event.key === WINDOW_SCALE_KEY) {
    windowScale.value = clamp(Number(event.newValue || 1), 0.8, 1.4)
    void applyWindowScale()
  }

  if (event.key === CHARACTER_SCALE_KEY) {
    characterScale.value = clamp(Number(event.newValue || 1), 0.75, 1.45)
  }

  if (event.key === CHARACTER_OFFSET_KEY) {
    characterOffset.value = readStoredOffset()
  }

  if (event.key === SYNC_REQUEST_KEY) {
    void syncState()
  }

  if (event.key === INPUT_BAR_VISIBLE_KEY) {
    inputBarVisible.value = event.newValue === '1'
  }

  if (event.key === SHOW_FRAME_KEY) {
    showFrame.value = event.newValue === '1'
  }

  if (event.key === BUBBLE_DURATION_KEY) {
    bubbleDuration.value = Number(event.newValue || '0')
  }
}

onBeforeUnmount(() => {
  stopWindowFocusListener?.()
  stopWindowFocusListener = null
  stopCharacterSwitchListener?.()
  stopCharacterSwitchListener = null
  stopCloseRequestedListener?.()
  stopCloseRequestedListener = null
  mainTauriWindow = null
  document.removeEventListener('visibilitychange', syncOnVisible)
  window.removeEventListener('storage', onStorageChange)
  if (stateSyncTimer !== null) {
    window.clearInterval(stateSyncTimer)
    stateSyncTimer = null
  }
  if (connectionBannerTimer !== null) {
    window.clearTimeout(connectionBannerTimer)
    connectionBannerTimer = null
  }
  if (speechBannerTimer !== null) {
    window.clearTimeout(speechBannerTimer)
    speechBannerTimer = null
  }
  if (bubbleAutoHideTimer !== null) {
    window.clearTimeout(bubbleAutoHideTimer)
    bubbleAutoHideTimer = null
  }
})

function onSubmit(text: string): void {
  sendMessage(text)
}

async function onProactiveAction(text: string): Promise<void> {
  await sendProactiveFeedback(text)
  sendMessage(text)
}

async function openAdmin(): Promise<void> {
  void reportClientLog({
    source: 'main-window',
    event: 'admin-open-click',
    message: '管理界面齿轮入口被点击',
  })
  if (!hasTauriInvoke()) {
    window.open('/admin.html', '_blank', 'noopener,noreferrer')
    return
  }
  try {
    await invokeTauriCommand('open_admin_window')
    void reportClientLog({
      source: 'main-window',
      event: 'admin-open-invoke-ok',
      message: 'open_admin_window invoke completed',
    })
  } catch (error) {
    console.error('[ui] failed to open admin window', error)
    void reportClientLog({
      source: 'main-window',
      event: 'admin-open-invoke-error',
      level: 'error',
      message: 'open_admin_window invoke failed',
      details: errorDetails(error),
    })
  }
}

async function applyWindowScale(): Promise<void> {
  await invokeTauriCommand('set_main_window_size', {
    width: Math.round(BASE_WINDOW_WIDTH * windowScale.value),
    height: Math.round(BASE_WINDOW_HEIGHT * windowScale.value),
  })
}

function setCharacterScale(next: number): void {
  characterScale.value = clamp(next, 0.75, 1.45)
  localStorage.setItem(CHARACTER_SCALE_KEY, String(characterScale.value))
}

function setCharacterOffset(next: { x: number; y: number }): void {
  characterOffset.value = {
    x: clamp(next.x, -140, 140),
    y: clamp(next.y, -180, 180),
  }
  localStorage.setItem(CHARACTER_OFFSET_KEY, JSON.stringify(characterOffset.value))
}

const showInputArea = computed(() => !passthroughLocked.value)

function toggleInputBar(): void {
  inputBarVisible.value = !inputBarVisible.value
  localStorage.setItem(INPUT_BAR_VISIBLE_KEY, inputBarVisible.value ? '1' : '0')
}

type ResizeDirection =
  | 'North'
  | 'South'
  | 'East'
  | 'West'
  | 'NorthEast'
  | 'NorthWest'
  | 'SouthEast'
  | 'SouthWest'

async function startResize(direction: ResizeDirection): Promise<void> {
  const tauriWindow = mainTauriWindow ?? await getTauriWindow()
  if (!tauriWindow) return
  try {
    await tauriWindow.startResizeDragging(direction)
  } catch {
    // Browser mode and unsupported platforms keep the resize handles inert.
  }
}

watch(
  () => [status.value, errorMessage.value],
  () => {
    if (connectionBannerTimer !== null) window.clearTimeout(connectionBannerTimer)
    showConnectionBanner.value = status.value === 'error' || status.value === 'connection_failed'
    if (showConnectionBanner.value) {
      connectionBannerTimer = window.setTimeout(() => {
        showConnectionBanner.value = false
      }, 6000)
    }
  },
)

watch(
  () => speechError.value,
  (message) => {
    if (speechBannerTimer !== null) window.clearTimeout(speechBannerTimer)
    showSpeechBanner.value = Boolean(message)
    if (message) {
      speechBannerTimer = window.setTimeout(() => {
        showSpeechBanner.value = false
      }, 5000)
    }
  },
)

watch(
  () => chatStore.reply,
  (reply) => {
    if (bubbleAutoHideTimer !== null) {
      window.clearTimeout(bubbleAutoHideTimer)
      bubbleAutoHideTimer = null
    }
    if (reply && !chatStore.isThinking && chatStore.proactiveLevel === 'silent' && bubbleDuration.value > 0) {
      bubbleAutoHideTimer = window.setTimeout(() => {
        if (chatStore.proactiveLevel === 'silent') {
          chatStore.setReply('')
        }
        bubbleAutoHideTimer = null
      }, bubbleDuration.value * 1000)
    }
  },
)

watch(
  () => chatStore.characterId,
  () => {
    if (chatStore.characterId) {
      localStorage.setItem(LAST_CHARACTER_KEY, JSON.stringify({
        id: chatStore.characterId,
        name: chatStore.characterName,
        display: chatStore.display,
        turn: chatStore.turn,
      }))
    }
  },
)
</script>

<template>
  <div class="app" :class="{ 'app--framed': showFrame }">
    <Transition name="banner">
      <div
        v-if="showConnectionBanner"
        class="status-banner"
      >
        {{ errorMessage || 'sidecar 连接失败' }}
      </div>
    </Transition>

    <Transition name="banner">
      <div v-if="showSpeechBanner" class="status-banner status-banner--speech">
        {{ speechError }}
      </div>
    </Transition>

    <div class="resize-handles" aria-hidden="true">
      <span class="resize-handle resize-handle--n" @mousedown.prevent="startResize('North')" />
      <span class="resize-handle resize-handle--s" @mousedown.prevent="startResize('South')" />
      <span class="resize-handle resize-handle--e" @mousedown.prevent="startResize('East')" />
      <span class="resize-handle resize-handle--w" @mousedown.prevent="startResize('West')" />
      <span class="resize-handle resize-handle--ne" @mousedown.prevent="startResize('NorthEast')" />
      <span class="resize-handle resize-handle--nw" @mousedown.prevent="startResize('NorthWest')" />
      <span class="resize-handle resize-handle--se" @mousedown.prevent="startResize('SouthEast')" />
      <span class="resize-handle resize-handle--sw" @mousedown.prevent="startResize('SouthWest')" />
    </div>

    <div class="stage-shell">
      <div class="bubble-layer">
        <BubbleBox
          :text="chatStore.reply"
          :is-thinking="chatStore.isThinking"
          :actions="chatStore.proactiveActions.length ? chatStore.proactiveActions : undefined"
          @action="onProactiveAction"
        />
      </div>

      <div class="sprite-area">
        <SpritePanel
          :mood="chatStore.mood"
          :character-id="chatStore.characterId"
          :character-name="chatStore.characterName"
          :display="chatStore.display"
          :turn="chatStore.turn"
          :lip-sync-level="lipSyncLevel"
          :visual-scale="characterScale"
          :visual-offset="characterOffset"
          @update:visual-scale="setCharacterScale"
          @update:visual-offset="setCharacterOffset"
        />
      </div>
    </div>

    <div v-if="showInputArea" class="input-area">
      <button
        class="drawer-toggle"
        :class="{ 'drawer-toggle--open': inputBarVisible }"
        type="button"
        aria-label="切换输入栏"
        @mousedown.prevent
        @click="toggleInputBar"
      >
        <span class="toggle-arrow">⌃</span>
      </button>
      <Transition name="drawer">
        <InputBar
          v-if="inputBarVisible"
          :tts-enabled="ttsEnabled"
          @submit="onSubmit"
          @open-admin="openAdmin"
          @toggle-tts="toggleTts"
        />
      </Transition>
    </div>
  </div>
</template>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  background: transparent;
  overflow: hidden;
  user-select: none;
  -webkit-app-region: drag;
}
</style>

<style scoped>
.app {
  width: 100vw;
  height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  position: relative;
}

.stage-shell {
  position: relative;
  width: 100%;
  flex: 1;
  min-height: 0;
  display: flex;
  padding: 8px 4px;
}

.sprite-area {
  flex: 1;
  display: flex;
  align-items: stretch;
  justify-content: center;
  width: 100%;
  min-height: 0;
}

.bubble-layer {
  position: absolute;
  top: 14px;
  left: 50%;
  transform: translateX(-50%);
  width: min(248px, calc(100% - 104px));
  z-index: 15;
  -webkit-app-region: no-drag;
}

.input-area {
  padding: 0 14px 10px;
  width: 100%;
  -webkit-app-region: no-drag;
}

.status-banner {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  background: rgba(210, 60, 60, 0.88);
  color: white;
  font-size: 11px;
  padding: 4px 8px;
  text-align: center;
  border-radius: 0 0 8px 8px;
  z-index: 100;
  font-family: sans-serif;
  line-height: 1.4;
}

.status-banner--speech {
  top: 30px;
  background: rgba(62, 108, 181, 0.9);
}

.resize-handles {
  position: absolute;
  inset: 0;
  z-index: 140;
  pointer-events: none;
  -webkit-app-region: no-drag;
}

.resize-handle {
  position: absolute;
  pointer-events: auto;
}

.resize-handle--n,
.resize-handle--s {
  left: 12px;
  right: 12px;
  height: 8px;
  cursor: ns-resize;
}

.resize-handle--n { top: 0; }
.resize-handle--s { bottom: 0; }

.resize-handle--e,
.resize-handle--w {
  top: 12px;
  bottom: 12px;
  width: 8px;
  cursor: ew-resize;
}

.resize-handle--e { right: 0; }
.resize-handle--w { left: 0; }

.resize-handle--ne,
.resize-handle--nw,
.resize-handle--se,
.resize-handle--sw {
  width: 16px;
  height: 16px;
}

.resize-handle--ne {
  top: 0;
  right: 0;
  cursor: nesw-resize;
}

.resize-handle--nw {
  top: 0;
  left: 0;
  cursor: nwse-resize;
}

.resize-handle--se {
  right: 0;
  bottom: 0;
  cursor: nwse-resize;
}

.resize-handle--sw {
  left: 0;
  bottom: 0;
  cursor: nesw-resize;
}

.banner-enter-active,
.banner-leave-active {
  transition: opacity 0.3s ease;
}

.banner-enter-from,
.banner-leave-to {
  opacity: 0;
}

.app--framed {
  border: 1.5px solid rgba(255, 179, 198, 0.45);
  background: rgba(255, 245, 248, 0.08);
  border-radius: 16px;
  backdrop-filter: blur(2px);
  overflow: hidden;
}

.drawer-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  padding: 3px 0 5px;
  background: none;
  border: none;
  cursor: pointer;
  -webkit-app-region: no-drag;
  color: rgba(192, 64, 95, 0.4);
  transition: color 0.2s;
}

.drawer-toggle:hover {
  color: rgba(192, 64, 95, 0.75);
}

.toggle-arrow {
  font-size: 14px;
  display: inline-block;
  transition: transform 0.25s ease;
  line-height: 1;
}

.drawer-toggle--open .toggle-arrow {
  transform: rotate(180deg);
}

.drawer-enter-active,
.drawer-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.drawer-enter-from,
.drawer-leave-to {
  opacity: 0;
  transform: translateY(6px);
}
</style>
