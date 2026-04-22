<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'
import { invoke } from '@tauri-apps/api/core'
import { getCurrentWindow } from '@tauri-apps/api/window'
import { listen } from '@tauri-apps/api/event'
import SpritePanel from './components/SpritePanel.vue'
import BubbleBox from './components/BubbleBox.vue'
import InputBar from './components/InputBar.vue'
import { useChatStore } from './stores/chat'
import { useUiStore } from './stores/ui'
import { useChat } from './composables/useChat'
import { useEdgeSnap } from './composables/useEdgeSnap'
import { useWindowPosition } from './composables/useWindowPosition'
import { sidecarHttpUrl } from './shared/sidecar'
import type { CharacterDisplayConfig } from './types/chat'

const chatStore = useChatStore()
const uiStore = useUiStore()
const { status, errorMessage, init, sendMessage, syncState } = useChat()
const { setup: setupEdgeSnap, unsnap } = useEdgeSnap()
const { restorePosition, startTracking } = useWindowPosition()

const PASSTHROUGH_KEY = 'kokoro-passthrough-lock'
const passthroughLocked = ref(false)

interface InputBarExpose {
  show(): void
  hide(): void
}

const inputBarRef = ref<InputBarExpose | null>(null)
let stopWindowFocusListener: (() => void) | null = null
let stateSyncTimer: number | null = null

if (import.meta.env.DEV) {
  ;(window as unknown as Record<string, unknown>).__store = chatStore
}

onMounted(async () => {
  // Restore passthrough lock state from localStorage (shared with admin window)
  passthroughLocked.value = localStorage.getItem(PASSTHROUGH_KEY) === '1'
  window.addEventListener('storage', onStorageChange)

  // Respect the persisted setting on startup instead of forcing passthrough on.
  await invoke('set_passthrough', { enabled: passthroughLocked.value })
  await restorePosition()
  await startTracking()
  await init()
  await setupEdgeSnap()

  const syncCurrentState = async () => {
    await syncState()
  }

  stopWindowFocusListener = await getCurrentWindow().onFocusChanged(async ({ payload }) => {
    if (payload) {
      await syncCurrentState()
    }
  })

  document.addEventListener('visibilitychange', syncOnVisible)
  stateSyncTimer = window.setInterval(() => {
    void syncCurrentState()
  }, 3000)

  await listen<string>('character-switch-requested', async (event) => {
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
      if (!passthroughLocked.value) {
        await invoke('set_passthrough', { enabled: false })
      }
      inputBarRef.value?.show()
    } catch (e) {
      console.error('[tray] character switch failed', e)
    }
  })

  const win = getCurrentWindow()
  await win.onCloseRequested(async (event) => {
    event.preventDefault()
    const pos = await invoke<[number, number]>('get_window_position')
    localStorage.setItem('kokoro-window-position', JSON.stringify({ x: pos[0], y: pos[1] }))
    await win.destroy()
  })
})

function syncOnVisible(): void {
  if (document.visibilityState === 'visible') {
    void syncState()
  }
}

function onStorageChange(event: StorageEvent): void {
  if (event.key !== PASSTHROUGH_KEY) return
  const locked = event.newValue === '1'
  passthroughLocked.value = locked
  void invoke('set_passthrough', { enabled: locked })
}

onBeforeUnmount(() => {
  stopWindowFocusListener?.()
  stopWindowFocusListener = null
  document.removeEventListener('visibilitychange', syncOnVisible)
  window.removeEventListener('storage', onStorageChange)
  if (stateSyncTimer !== null) {
    window.clearInterval(stateSyncTimer)
    stateSyncTimer = null
  }
})

watch(
  () => chatStore.isThinking,
  (thinking) => {
    if (!thinking && chatStore.reply) {
      inputBarRef.value?.show()
    }
  },
)

function onSpriteClick(): void {
  inputBarRef.value?.show()
}

function onSubmit(text: string): void {
  sendMessage(text)
}

function onProactiveAction(text: string): void {
  sendMessage(text)
}

async function onMouseEnter(): Promise<void> {
  // When locked to passthrough-mode, don't disable it on hover
  if (!passthroughLocked.value) {
    await invoke('set_passthrough', { enabled: false })
  }
  if (uiStore.isSnapped) await unsnap()
}

async function onMouseLeave(): Promise<void> {
  // Re-enable passthrough when mouse leaves so the window doesn't block desktop clicks
  if (!passthroughLocked.value) {
    await invoke('set_passthrough', { enabled: true })
  }
}

async function openAdmin(): Promise<void> {
  try {
    await invoke('open_admin_window')
  } catch (error) {
    console.error('[ui] failed to open admin window', error)
  }
}
</script>

<template>
  <div class="app" @mouseenter="onMouseEnter" @mouseleave="onMouseLeave">
    <Transition name="banner">
      <div
        v-if="status === 'error' || status === 'connection_failed'"
        class="status-banner"
      >
        {{ errorMessage || 'sidecar 连接失败' }}
      </div>
    </Transition>

    <button class="admin-button" type="button" title="管理界面" @click="openAdmin">
      ⚙
    </button>

    <div class="sprite-area">
      <SpritePanel
        :mood="chatStore.mood"
        :character-id="chatStore.characterId"
        :character-name="chatStore.characterName"
        :display="chatStore.display"
        :turn="chatStore.turn"
        @click="onSpriteClick"
      />
    </div>

    <div class="bubble-area">
      <BubbleBox
        :text="chatStore.reply"
        :is-thinking="chatStore.isThinking"
        :actions="chatStore.proactiveActions.length ? chatStore.proactiveActions : undefined"
        @action="onProactiveAction"
      />
      <InputBar ref="inputBarRef" @submit="onSubmit" />
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
  width: 320px;
  height: 520px;
  display: flex;
  flex-direction: column;
  align-items: center;
  position: relative;
}

.sprite-area {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.bubble-area {
  padding: 12px 16px 16px;
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

.admin-button {
  position: absolute;
  top: 10px;
  right: 10px;
  width: 28px;
  height: 28px;
  border: 1px solid rgba(120, 130, 150, 0.35);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.86);
  color: #4b5563;
  font-size: 15px;
  line-height: 1;
  cursor: pointer;
  z-index: 120;
  -webkit-app-region: no-drag;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 12px rgba(15, 23, 42, 0.12);
}

.admin-button:hover {
  background: rgba(255, 255, 255, 0.96);
}

.banner-enter-active,
.banner-leave-active {
  transition: opacity 0.3s ease;
}

.banner-enter-from,
.banner-leave-to {
  opacity: 0;
}
</style>
