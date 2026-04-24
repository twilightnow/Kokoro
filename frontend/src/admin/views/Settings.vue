<template>
  <div>
    <h1 class="page-title">配置设置</h1>

    <div v-if="error" class="banner-error">{{ error }}</div>
    <div v-if="loadingConfig" class="loading">加载中…</div>

    <template v-else-if="configData">
      <!-- LLM 配置 -->
      <div class="card">
        <div class="card-title">LLM 配置</div>

        <div class="form-group">
          <label class="form-label">供应商 (LLM_PROVIDER)</label>
          <select v-model="updates.LLM_PROVIDER">
            <optgroup label="CLI 模式">
              <option value="claude-cli">claude-cli</option>
              <option value="gemini-cli">gemini-cli</option>
              <option value="codex-cli">codex-cli</option>
            </optgroup>
            <optgroup label="API Key 模式">
              <option value="anthropic">anthropic</option>
              <option value="openai">openai</option>
              <option value="gemini">gemini</option>
              <option value="deepseek">deepseek</option>
              <option value="openrouter">openrouter</option>
              <option value="copilot">copilot</option>
            </optgroup>
          </select>
        </div>

        <div class="form-group">
          <label class="form-label">模型 (LLM_MODEL)</label>
          <input type="text" v-model="updates.LLM_MODEL" placeholder="例如: claude-sonnet-4-5" />
        </div>

        <div class="form-group">
          <label class="form-label">最大输出 Token (LLM_MAX_TOKENS)</label>
          <input type="number" v-model="updates.LLM_MAX_TOKENS" min="50" max="4096" />
        </div>

        <div v-if="isApiKeyProvider" class="form-group">
          <label class="form-label">API Key</label>
          <input
            type="password"
            v-model="updates[apiKeyEnvName]"
            :placeholder="apiKeyIsSet ? '已配置，留空不修改' : '输入 API Key'"
            autocomplete="new-password"
          />
          <div class="hint">出于安全考虑，这里只允许替换或清空，不显示已保存的明文 key。</div>
          <button class="btn btn-secondary btn-sm mt-4" :disabled="saving" @click="testLlm">
            测试连接
          </button>
        </div>
      </div>

      <div class="card mt-4">
        <div class="card-title">TTS 语音</div>
        <div class="form-group inline-check">
          <label>
            <input type="checkbox" v-model="ttsEnabled" />
            启用语音输出
          </label>
        </div>
        <div class="form-group">
          <label class="form-label">供应商 (TTS_PROVIDER)</label>
          <select v-model="updates.TTS_PROVIDER">
            <option value="edge-tts">edge-tts</option>
          </select>
        </div>
        <div class="form-group">
          <label class="form-label">声线 (TTS_VOICE)</label>
          <input type="text" v-model="updates.TTS_VOICE" placeholder="zh-CN-XiaoxiaoNeural" />
        </div>
        <div class="grid-2">
          <div class="form-group">
            <label class="form-label">语速 (TTS_RATE)</label>
            <input type="text" v-model="updates.TTS_RATE" placeholder="+0%" />
          </div>
          <div class="form-group">
            <label class="form-label">音量 (TTS_VOLUME)</label>
            <input type="text" v-model="updates.TTS_VOLUME" placeholder="+0%" />
          </div>
        </div>
      </div>

      <div class="card mt-4">
        <div class="card-title">桌面行为</div>
        <div class="settings-list">
          <label><input type="checkbox" v-model="startOnBoot" /> 开机启动</label>
          <label><input type="checkbox" v-model="mainAlwaysOnTop" /> 主窗口默认置顶</label>
          <label><input type="checkbox" v-model="enablePerception" /> 启用感知能力</label>
        </div>
        <div class="hint">感知默认关闭；开机启动会写入当前 Windows 用户的启动项。</div>
      </div>

      <!-- 记忆配置 -->
      <div class="card mt-4">
        <div class="card-title">记忆配置</div>
        <div class="form-group">
          <label class="form-label">记忆 Token 预算 (MEMORY_TOKEN_BUDGET)</label>
          <input type="number" v-model="updates.MEMORY_TOKEN_BUDGET" min="100" max="2000" />
        </div>
        <div class="form-group">
          <label class="form-label">
            数据目录 (KOKORO_DATA_DIR)
            <span class="badge badge-yellow" style="margin-left:6px">⚠️ 重启生效</span>
          </label>
          <input type="text" v-model="updates.KOKORO_DATA_DIR" placeholder="./data" />
        </div>
      </div>

      <!-- 操作按钮 -->
      <div style="display:flex; gap:8px; margin-top:16px">
        <button class="btn btn-primary" :disabled="saving" @click="saveConfig">
          {{ saving ? '保存中…' : '保存配置' }}
        </button>
        <button class="btn btn-secondary" :disabled="saving" @click="saveAndReload">
          保存并热更新
        </button>
        <button class="btn btn-secondary" :disabled="saving" @click="exportDiagnostics">
          导出诊断
        </button>
      </div>

      <div v-if="restartRequired" class="banner-warn mt-4">
        ⚠️ 包含需要重启 Sidecar 才能生效的配置项（KOKORO_DATA_DIR）。
      </div>

      <!-- 当前完整 .env 路径 -->
      <div style="margin-top:20px; font-size:11px; color:#9ca3af">
        配置文件: {{ configData.env_path }}
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, inject, onMounted } from 'vue'
import { api } from '../api'

const showToast = inject<(msg: string, type?: any) => void>('showToast', () => {})

const configData = ref<any>(null)
const loadingConfig = ref(false)
const error = ref('')
const saving = ref(false)
const restartRequired = ref(false)
const ttsEnabled = ref(true)
const startOnBoot = ref(false)
const mainAlwaysOnTop = ref(true)
const enablePerception = ref(false)

// 可编辑的配置键
const updates = ref<Record<string, string>>({
  LLM_PROVIDER: '',
  LLM_MODEL: '',
  LLM_MAX_TOKENS: '300',
  TTS_PROVIDER: 'edge-tts',
  TTS_VOICE: 'zh-CN-XiaoxiaoNeural',
  TTS_RATE: '+0%',
  TTS_VOLUME: '+0%',
  MEMORY_TOKEN_BUDGET: '500',
  KOKORO_DATA_DIR: './data',
  KOKORO_START_ON_BOOT: '0',
  KOKORO_ALWAYS_ON_TOP: '1',
  KOKORO_ENABLE_PERCEPTION: '0',
  ANTHROPIC_API_KEY: '',
  OPENAI_API_KEY: '',
  GEMINI_API_KEY: '',
  DEEPSEEK_API_KEY: '',
  OPENROUTER_API_KEY: '',
  LLM_API_KEY: '',
})

const apiKeyMap: Record<string, string> = {
  anthropic: 'ANTHROPIC_API_KEY',
  openai: 'OPENAI_API_KEY',
  gemini: 'GEMINI_API_KEY',
  deepseek: 'DEEPSEEK_API_KEY',
  openrouter: 'OPENROUTER_API_KEY',
  copilot: 'LLM_API_KEY',
}

const cliProviders = new Set(['claude-cli', 'gemini-cli', 'codex-cli'])
const isApiKeyProvider = computed(() => !cliProviders.has(updates.value.LLM_PROVIDER))
const apiKeyEnvName = computed(() => apiKeyMap[updates.value.LLM_PROVIDER] ?? 'LLM_API_KEY')
const apiKeyIsSet = computed(() => {
  const k = apiKeyEnvName.value
  return configData.value?.entries?.some((e: any) => e.key === k && e.is_set)
})

async function loadConfig() {
  loadingConfig.value = true
  error.value = ''
  try {
    configData.value = await api.getConfig()
    // 填入当前值
    for (const entry of configData.value.entries) {
      if (entry.key in updates.value && !entry.is_sensitive) {
        updates.value[entry.key] = entry.value
      }
    }
    startOnBoot.value = updates.value.KOKORO_START_ON_BOOT === '1'
    mainAlwaysOnTop.value = updates.value.KOKORO_ALWAYS_ON_TOP !== '0'
    enablePerception.value = updates.value.KOKORO_ENABLE_PERCEPTION === '1'
    ttsEnabled.value = updates.value.TTS_PROVIDER !== 'disabled'
  } catch (e: any) {
    error.value = e.message
  } finally {
    loadingConfig.value = false
  }
}

function buildPayload(): Record<string, string> {
  updates.value.KOKORO_START_ON_BOOT = startOnBoot.value ? '1' : '0'
  updates.value.KOKORO_ALWAYS_ON_TOP = mainAlwaysOnTop.value ? '1' : '0'
  updates.value.KOKORO_ENABLE_PERCEPTION = enablePerception.value ? '1' : '0'
  updates.value.TTS_PROVIDER = ttsEnabled.value ? 'edge-tts' : 'disabled'
  const payload: Record<string, string> = {}
  for (const [k, v] of Object.entries(updates.value)) {
    if (v !== '') payload[k] = v
  }
  // 敏感 key 留空表示不修改，移除
  for (const k of Object.values(apiKeyMap)) {
    if (payload[k] === '' || (updates.value[k] === '' && apiKeyMap[updates.value.LLM_PROVIDER] !== k)) {
      delete payload[k]
    }
  }
  return payload
}

async function saveConfig() {
  saving.value = true
  restartRequired.value = false
  try {
    const r = await api.updateConfig(buildPayload())
    applyDesktopPreferences()
    restartRequired.value = r.restart_required
    showToast('配置已保存', 'success')
  } catch (e: any) {
    showToast(`保存失败: ${e.message}`, 'error')
  } finally {
    saving.value = false
  }
}

async function saveAndReload() {
  saving.value = true
  try {
    const r = await api.updateConfig(buildPayload())
    applyDesktopPreferences()
    restartRequired.value = r.restart_required
    await api.reloadConfig()
    showToast('配置已保存并热更新', 'success')
  } catch (e: any) {
    showToast(`操作失败: ${e.message}`, 'error')
  } finally {
    saving.value = false
  }
}

function applyDesktopPreferences() {
  localStorage.setItem('kokoro-main-always-on-top', mainAlwaysOnTop.value ? '1' : '0')
  localStorage.setItem('kokoro-tts-enabled', ttsEnabled.value ? '1' : '0')
  import('@tauri-apps/api/core')
    .then(({ invoke }) => invoke('set_start_on_boot', { enabled: startOnBoot.value }))
    .catch(() => {
      showToast('开机启动设置未写入系统启动项', 'error')
    })
}

async function testLlm() {
  saving.value = true
  try {
    await api.updateConfig(buildPayload())
    const r = await api.testLlmConfig()
    showToast(`连接配置可用: ${r.provider} / ${r.model}`, 'success')
  } catch (e: any) {
    showToast(`连接测试失败: ${e.message}`, 'error')
  } finally {
    saving.value = false
  }
}

async function exportDiagnostics() {
  try {
    const data = await api.exportDiagnostics()
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `kokoro-diagnostics-${new Date().toISOString().replace(/[:.]/g, '-')}.json`
    a.click()
    URL.revokeObjectURL(url)
  } catch (e: any) {
    showToast(`导出失败: ${e.message}`, 'error')
  }
}

onMounted(loadConfig)
</script>

<style scoped>
.hint {
  color: #6b7280;
  font-size: 11px;
  line-height: 1.5;
}

.settings-list {
  display: grid;
  gap: 8px;
  font-size: 13px;
}

.inline-check {
  display: block;
}
</style>
