<template>
  <div>
    <h1 class="page-title">交互设置</h1>

    <div v-if="loading" class="loading">加载中…</div>

    <template v-else>
      <div class="card">
        <div class="card-title">窗口与人物</div>
        <div class="grid-2">
          <div class="form-group">
            <label class="form-label">窗口缩放</label>
            <input type="range" v-model.number="windowScale" min="0.8" max="1.4" step="0.05" />
            <div class="metric-row">
              <span>{{ Math.round(windowScale * 100) }}%</span>
              <button class="btn btn-secondary btn-sm" type="button" @click="windowScale = 1">重置</button>
            </div>
          </div>
          <div class="form-group">
            <label class="form-label">人物缩放</label>
            <input type="range" v-model.number="characterScale" min="0.75" max="1.45" step="0.05" />
            <div class="metric-row">
              <span>{{ Math.round(characterScale * 100) }}%</span>
              <button class="btn btn-secondary btn-sm" type="button" @click="characterScale = 1">重置</button>
            </div>
          </div>
        </div>
        <div class="grid-2 mt-4">
          <div class="form-group">
            <label class="form-label">人物水平位置</label>
            <input type="range" v-model.number="characterOffset.x" min="-140" max="140" step="1" />
            <div class="metric-row">
              <span>{{ characterOffset.x }} px</span>
              <button class="btn btn-secondary btn-sm" type="button" @click="characterOffset.x = 0">归中</button>
            </div>
          </div>
          <div class="form-group">
            <label class="form-label">人物垂直位置</label>
            <input type="range" v-model.number="characterOffset.y" min="-180" max="180" step="1" />
            <div class="metric-row">
              <span>{{ characterOffset.y }} px</span>
              <button class="btn btn-secondary btn-sm" type="button" @click="characterOffset.y = 0">归中</button>
            </div>
          </div>
        </div>
        <div class="hint">主窗口边缘可直接拖拽改变大小；人物区域支持滚轮缩放和鼠标拖动。</div>
        <div class="form-group mt-4">
          <label class="form-label">外边框与透明背景</label>
          <label><input type="checkbox" v-model="showFrame" /> 显示外边框和半透明背景效果</label>
          <div class="hint">开启后主窗口显示淡色边框和磨砂背景；默认关闭。</div>
        </div>
      </div>

      <div class="card mt-4">
        <div class="card-title">输入控制</div>
        <div class="settings-list">
          <label><input type="checkbox" v-model="passthroughLocked" /> 主窗口鼠标穿透</label>
          <label><input type="checkbox" v-model="mainAlwaysOnTop" /> 主窗口默认置顶</label>
          <label><input type="checkbox" v-model="startOnBoot" /> 开机启动</label>
          <label><input type="checkbox" v-model="ttsEnabled" /> 启用语音播报</label>
        </div>
        <div class="form-group mt-4">
          <label class="form-label">气泡显示时长</label>
          <select v-model.number="bubbleDuration">
            <option :value="0">一直显示</option>
            <option :value="5">5 秒后隐藏</option>
            <option :value="10">10 秒后隐藏</option>
            <option :value="30">30 秒后隐藏</option>
            <option :value="60">60 秒后隐藏</option>
          </select>
          <div class="hint">仅对普通回复气泡生效；主动陪伴短句有独立计时。</div>
        </div>
        <div class="form-group mt-4">
          <label class="form-label">语音输入来源</label>
          <select v-model="speechInputSource">
            <option value="browser">浏览器麦克风</option>
            <option value="internal">系统内部事件</option>
          </select>
          <div class="hint">内部来源会监听主窗口的 kokoro:speech-input DOM 事件和 Tauri speech-input 事件。</div>
        </div>
      </div>

      <div class="actions">
        <button class="btn btn-primary" :disabled="saving" type="button" @click="save">
          {{ saving ? '保存中…' : '保存交互设置' }}
        </button>
        <button class="btn btn-secondary" :disabled="syncing" type="button" @click="requestMainSync">
          {{ syncing ? '同步中…' : '同步主窗口状态' }}
        </button>
        <button class="btn btn-secondary" :disabled="saving" type="button" @click="resetView">
          重置视野
        </button>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { inject, onMounted, ref } from 'vue'
import { api } from '../api'

type SpeechInputSource = 'browser' | 'internal'
type TauriRuntimeWindow = Window & {
  __TAURI_INTERNALS__?: {
    invoke?: unknown
  }
}

const showToast = inject<(msg: string, type?: any) => void>('showToast', () => {})

const loading = ref(false)
const saving = ref(false)
const syncing = ref(false)
const startOnBoot = ref(false)
const mainAlwaysOnTop = ref(true)
const passthroughLocked = ref(false)
const windowScale = ref(1)
const characterScale = ref(1)
const characterOffset = ref({ x: 0, y: 0 })
const speechInputSource = ref<SpeechInputSource>('browser')
const ttsEnabled = ref(true)
const showFrame = ref(false)
const bubbleDuration = ref(0)

const PASSTHROUGH_KEY = 'kokoro-passthrough-lock'
const MAIN_ALWAYS_ON_TOP_KEY = 'kokoro-main-always-on-top'
const WINDOW_SCALE_KEY = 'kokoro-window-scale'
const CHARACTER_SCALE_KEY = 'kokoro-character-scale'
const CHARACTER_OFFSET_KEY = 'kokoro-character-offset'
const SPEECH_SOURCE_KEY = 'kokoro-speech-input-source'
const TTS_STORAGE_KEY = 'kokoro-tts-enabled'
const SYNC_REQUEST_KEY = 'kokoro-main-sync-request'
const SHOW_FRAME_KEY = 'kokoro-show-frame'
const BUBBLE_DURATION_KEY = 'kokoro-bubble-duration'

function hasTauriInvoke(): boolean {
  if (typeof window === 'undefined') return false
  const tauriWindow = window as TauriRuntimeWindow
  return typeof tauriWindow.__TAURI_INTERNALS__?.invoke === 'function'
}

async function invokeTauriCommand(
  command: string,
  args?: Record<string, unknown>,
): Promise<boolean> {
  if (!hasTauriInvoke()) return false
  const { invoke } = await import('@tauri-apps/api/core')
  await invoke(command, args)
  return true
}

function clampNumber(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value))
}

function readLocalNumber(key: string, fallback: number): number {
  const value = Number(localStorage.getItem(key))
  return Number.isFinite(value) ? value : fallback
}

function readLocalOffset(): { x: number; y: number } {
  try {
    const parsed = JSON.parse(localStorage.getItem(CHARACTER_OFFSET_KEY) || '{}') as {
      x?: unknown
      y?: unknown
    }
    const x = typeof parsed.x === 'number' && Number.isFinite(parsed.x) ? parsed.x : 0
    const y = typeof parsed.y === 'number' && Number.isFinite(parsed.y) ? parsed.y : 0
    return {
      x: clampNumber(Math.round(x), -140, 140),
      y: clampNumber(Math.round(y), -180, 180),
    }
  } catch {
    return { x: 0, y: 0 }
  }
}

async function load(): Promise<void> {
  loading.value = true
  try {
    const config = await api.getConfig()
    const entries = Array.isArray(config.entries) ? config.entries : []
    const entryValue = (key: string, fallback: string) => {
      const entry = entries.find((item: any) => item.key === key)
      return String(entry?.value ?? fallback)
    }
    startOnBoot.value = entryValue('KOKORO_START_ON_BOOT', '0') === '1'
    mainAlwaysOnTop.value = localStorage.getItem(MAIN_ALWAYS_ON_TOP_KEY) !== '0'
      && entryValue('KOKORO_ALWAYS_ON_TOP', '1') !== '0'
  } catch (error: any) {
    showToast(`加载配置失败: ${error.message}`, 'error')
  } finally {
    passthroughLocked.value = localStorage.getItem(PASSTHROUGH_KEY) === '1'
    windowScale.value = clampNumber(readLocalNumber(WINDOW_SCALE_KEY, 1), 0.8, 1.4)
    characterScale.value = clampNumber(readLocalNumber(CHARACTER_SCALE_KEY, 1), 0.75, 1.45)
    characterOffset.value = readLocalOffset()
    speechInputSource.value = localStorage.getItem(SPEECH_SOURCE_KEY) === 'internal'
      ? 'internal'
      : 'browser'
    ttsEnabled.value = localStorage.getItem(TTS_STORAGE_KEY) !== '0'
    showFrame.value = localStorage.getItem(SHOW_FRAME_KEY) === '1'
    bubbleDuration.value = Number(localStorage.getItem(BUBBLE_DURATION_KEY) || '0')
    loading.value = false
  }
}

function resetView(): void {
  characterScale.value = 1
  characterOffset.value = { x: 0, y: 0 }
}

async function requestMainSync(): Promise<void> {
  syncing.value = true
  try {
    localStorage.setItem(SYNC_REQUEST_KEY, String(Date.now()))
    showToast('已请求主窗口同步状态', 'success')
  } finally {
    window.setTimeout(() => {
      syncing.value = false
    }, 400)
  }
}

async function save(): Promise<void> {
  saving.value = true
  try {
    await api.updateConfig({
      KOKORO_START_ON_BOOT: startOnBoot.value ? '1' : '0',
      KOKORO_ALWAYS_ON_TOP: mainAlwaysOnTop.value ? '1' : '0',
    })
    localStorage.setItem(PASSTHROUGH_KEY, passthroughLocked.value ? '1' : '0')
    localStorage.setItem(MAIN_ALWAYS_ON_TOP_KEY, mainAlwaysOnTop.value ? '1' : '0')
    localStorage.setItem(WINDOW_SCALE_KEY, String(clampNumber(windowScale.value, 0.8, 1.4)))
    localStorage.setItem(CHARACTER_SCALE_KEY, String(clampNumber(characterScale.value, 0.75, 1.45)))
    localStorage.setItem(CHARACTER_OFFSET_KEY, JSON.stringify({
      x: clampNumber(characterOffset.value.x, -140, 140),
      y: clampNumber(characterOffset.value.y, -180, 180),
    }))
    localStorage.setItem(SPEECH_SOURCE_KEY, speechInputSource.value)
    localStorage.setItem(TTS_STORAGE_KEY, ttsEnabled.value ? '1' : '0')
    localStorage.setItem(SHOW_FRAME_KEY, showFrame.value ? '1' : '0')
    localStorage.setItem(BUBBLE_DURATION_KEY, String(bubbleDuration.value))
    const applyResults = await Promise.allSettled([
      invokeTauriCommand('set_passthrough', { enabled: passthroughLocked.value }),
      invokeTauriCommand('set_main_always_on_top', { enabled: mainAlwaysOnTop.value }),
      invokeTauriCommand('set_start_on_boot', { enabled: startOnBoot.value }),
    ])
    if (applyResults.some((result) => result.status === 'rejected')) {
      showToast('交互设置已保存，部分系统设置未立即写入', 'error')
      return
    }
    showToast('交互设置已保存', 'success')
  } catch (error: any) {
    showToast(`保存失败: ${error.message}`, 'error')
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.settings-list {
  display: grid;
  gap: 8px;
  font-size: 13px;
}

.metric-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: #6b7280;
  font-size: 12px;
}

.hint {
  color: #6b7280;
  font-size: 11px;
  line-height: 1.5;
}

.actions {
  display: flex;
  gap: 8px;
  margin-top: 16px;
}
</style>
