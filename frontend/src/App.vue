<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { invoke } from '@tauri-apps/api/core'
import { getCurrentWindow } from '@tauri-apps/api/window'
import { listen } from '@tauri-apps/api/event'
import SpritePanel from './components/SpritePanel.vue'
import BubbleBox from './components/BubbleBox.vue'
import InputBar from './components/InputBar.vue'
import { useChatStore } from './stores/chat'
import { useChat } from './composables/useChat'
import { useEdgeSnap } from './composables/useEdgeSnap'
import { useWindowPosition } from './composables/useWindowPosition'
import { sidecarHttpUrl } from './shared/sidecar'
import { errorDetails, reportClientLog } from './shared/diagnostics'
import type { CharacterDisplayConfig } from './types/chat'
import { useSpeechOutput } from './composables/useSpeechOutput'

const chatStore = useChatStore()
const { status, errorMessage, init, sendMessage, syncState } = useChat()
const { setup: setupEdgeSnap } = useEdgeSnap()
const { restorePosition, startTracking } = useWindowPosition()
const { lipSyncLevel, speechError } = useSpeechOutput()

const PASSTHROUGH_KEY = 'kokoro-passthrough-lock'
const MAIN_ALWAYS_ON_TOP_KEY = 'kokoro-main-always-on-top'
const passthroughLocked = ref(false)
let stopWindowFocusListener: (() => void) | null = null
let stateSyncTimer: number | null = null

if (import.meta.env.DEV) {
  ;(window as unknown as Record<string, unknown>).__store = chatStore
}

onMounted(async () => {
  // Restore passthrough lock state from localStorage (shared with admin window)
  passthroughLocked.value = localStorage.getItem(PASSTHROUGH_KEY) === '1'
  window.addEventListener('storage', onStorageChange)

  // Respect persisted window behavior instead of changing it on hover.
  await invoke('set_passthrough', { enabled: passthroughLocked.value })
  await invoke('set_main_always_on_top', {
    enabled: localStorage.getItem(MAIN_ALWAYS_ON_TOP_KEY) === '1',
  })
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
  if (event.key === PASSTHROUGH_KEY) {
    const locked = event.newValue === '1'
    passthroughLocked.value = locked
    void invoke('set_passthrough', { enabled: locked })
  }

  if (event.key === MAIN_ALWAYS_ON_TOP_KEY) {
    void invoke('set_main_always_on_top', {
      enabled: event.newValue === '1',
    })
  }
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

function onSubmit(text: string): void {
  sendMessage(text)
}

function onProactiveAction(text: string): void {
  sendMessage(text)
}

async function openAdmin(): Promise<void> {
  void reportClientLog({
    source: 'main-window',
    event: 'admin-open-click',
    message: '管理界面齿轮入口被点击',
  })
  try {
    await invoke('open_admin_window')
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
</script>

<template>
  <div class="app">
    <Transition name="banner">
      <div
        v-if="status === 'error' || status === 'connection_failed'"
        class="status-banner"
      >
        {{ errorMessage || 'sidecar 连接失败' }}
      </div>
    </Transition>

    <Transition name="banner">
      <div v-if="speechError" class="status-banner status-banner--speech">
        {{ speechError }}
      </div>
    </Transition>

    <button class="admin-button" type="button" title="管理界面" @click="openAdmin">
      ⚙
    </button>

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
        />
      </div>
    </div>

    <div class="input-area">
      <InputBar @submit="onSubmit" />
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
  width: 360px;
  height: 620px;
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
  padding: 48px 10px 8px;
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
  top: 54px;
  left: 50%;
  transform: translateX(-50%);
  width: min(248px, calc(100% - 104px));
  z-index: 15;
  -webkit-app-region: no-drag;
}

.input-area {
  padding: 0 14px 14px;
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

.admin-button {
  position: absolute;
  top: 10px;
  right: 10px;
  width: 28px;
  height: 28px;
  border: none;
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
