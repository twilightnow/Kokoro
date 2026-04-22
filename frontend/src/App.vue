<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
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

const chatStore = useChatStore()
const uiStore = useUiStore()
const { status, errorMessage, init, sendMessage } = useChat()
const { setup: setupEdgeSnap, unsnap } = useEdgeSnap()
const { restorePosition, startTracking } = useWindowPosition()

// InputBar の公開メソッド型
interface InputBarExpose {
  show(): void
  hide(): void
}
const inputBarRef = ref<InputBarExpose | null>(null)

// 開発モードのみ store を window に公開（型を二段階キャスト）
if (import.meta.env.DEV) {
  ;(window as unknown as Record<string, unknown>)['__store'] = chatStore
}

onMounted(async () => {
  // M4-E: 前回位置を復元、移動追跡を開始
  await restorePosition()
  await startTracking()

  // M3: sidecar WebSocket 接続
  await init()

  // M4-B: 端スナップ設定
  await setupEdgeSnap()

  // 角色切换事件
  await listen<string>('character-switch-requested', async (event) => {
    const name = event.payload
    try {
      const resp = await fetch(
        `http://127.0.0.1:18765/switch-character?name=${encodeURIComponent(name)}`,
        { method: 'POST' },
      )
      if (!resp.ok) throw new Error(await resp.text())
      const data = await resp.json() as { character_name: string }
      chatStore.resetForNewCharacter(data.character_name)
      chatStore.setReply(`[ 已切换到 ${data.character_name} ]`)
      await invoke('set_passthrough', { enabled: false })
      inputBarRef.value?.show()
    } catch (e) {
      console.error('[tray] 切换角色失败', e)
    }
  })

  // ウィンドウ閉じる前に位置保存
  const win = getCurrentWindow()
  await win.onCloseRequested(async (event) => {
    event.preventDefault()
    const pos = await invoke<[number, number]>('get_window_position')
    localStorage.setItem('kokoro-window-position', JSON.stringify({ x: pos[0], y: pos[1] }))
    await win.destroy()
  })
})

// 返回后自动重新显示输入框
watch(
  () => chatStore.isThinking,
  (thinking) => {
    if (!thinking && chatStore.reply) {
      inputBarRef.value?.show()
    }
  },
)

// 立绘クリック → 入力欄を表示
function onSpriteClick(): void {
  inputBarRef.value?.show()
}

// 送信 → WebSocket で sidecar へ
function onSubmit(text: string): void {
  sendMessage(text)
}

// 主动介入の快捷ボタン
function onProactiveAction(text: string): void {
  sendMessage(text)
}

// M4-A: マウスがウィンドウ内に入ったらパススルー解除
async function onMouseEnter(): Promise<void> {
  await invoke('set_passthrough', { enabled: false })
  if (uiStore.isSnapped) await unsnap()
}

// M4-A: マウスがウィンドウ外に出たらパススルー有効
async function onMouseLeave(): Promise<void> {
  if (!uiStore.isSnapped) {
    await invoke('set_passthrough', { enabled: true })
  }
}
</script>

<template>
  <div class="app" @mouseenter="onMouseEnter" @mouseleave="onMouseLeave">
    <!-- M3: 接続エラーバナー -->
    <Transition name="banner">
      <div
        v-if="status === 'error' || status === 'connection_failed'"
        class="status-banner"
      >
        {{ errorMessage || 'sidecar 连接失败' }}
      </div>
    </Transition>

    <div class="sprite-area">
      <SpritePanel
        :mood="chatStore.mood"
        :character-name="chatStore.characterName"
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

.banner-enter-active,
.banner-leave-active {
  transition: opacity 0.3s ease;
}

.banner-enter-from,
.banner-leave-to {
  opacity: 0;
}
</style>
