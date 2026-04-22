<template>
  <div>
    <h1 class="page-title">调试工具</h1>

    <div v-if="error" class="banner-error">{{ error }}</div>

    <!-- 状态快照 -->
    <div class="card">
      <div style="display:flex; justify-content:space-between; margin-bottom:12px">
        <div class="card-title" style="margin:0">实时状态快照</div>
        <div style="display:flex; gap:8px; align-items:center">
          <label style="font-size:12px; display:flex; align-items:center; gap:4px; cursor:pointer">
            <input type="checkbox" v-model="autoRefresh" @change="toggleAutoRefresh" />
            自动刷新（2s）
          </label>
          <button class="btn btn-secondary btn-sm" @click="loadState">刷新</button>
        </div>
      </div>

      <div v-if="loading && !debugState" class="loading">加载中…</div>
      <template v-else-if="debugState">
        <div class="state-grid">
          <div class="state-row"><span class="state-k">角色</span><span>{{ debugState.character_id }} / {{ debugState.character_name }}</span></div>
          <div class="state-row"><span class="state-k">情绪</span><span>{{ debugState.mood }}（剩余 {{ debugState.persist_count }} 轮）</span></div>
          <div class="state-row"><span class="state-k">对话轮数</span><span>{{ debugState.turn }}</span></div>
          <div class="state-row">
            <span class="state-k">工作记忆</span>
            <span>{{ debugState.working_memory_count }} 条消息（本次会话截断 {{ debugState.working_memory_truncation_count }} 次）</span>
          </div>
          <div class="state-row">
            <span class="state-k">Session Token</span>
            <span>输入 {{ debugState.session_token_input }} / 输出 {{ debugState.session_token_output }}</span>
          </div>
        </div>

        <!-- 展开 System Prompt -->
        <div class="mt-4">
          <button class="btn btn-secondary btn-sm" @click="showPrompt = !showPrompt">
            {{ showPrompt ? '折叠' : '展开' }} System Prompt 全文
          </button>
          <div v-if="showPrompt" class="prompt-box">{{ debugState.system_prompt || '（暂无）' }}</div>
        </div>
      </template>
    </div>

    <!-- 情绪注入 -->
    <div class="card mt-4">
      <div class="card-title">情绪注入</div>
      <div style="display:flex; gap:8px; align-items:flex-end">
        <div class="form-group" style="margin:0; min-width:120px">
          <label class="form-label">情绪</label>
          <select v-model="injectMood">
            <option v-for="m in moodOptions" :key="m" :value="m">{{ m }}</option>
          </select>
        </div>
        <div class="form-group" style="margin:0; width:80px">
          <label class="form-label">持续轮数</label>
          <input type="number" v-model.number="injectPersist" min="0" max="10" />
        </div>
        <button class="btn btn-primary" @click="doInjectEmotion">注入情绪</button>
      </div>
      <div style="font-size:11px; color:#9ca3af; margin-top:6px">注入后下轮对话立即生效，不写入日志。</div>
    </div>

    <!-- 临时事实注入 -->
    <div class="card mt-4">
      <div class="card-title">临时事实注入（会话内有效，不写磁盘）</div>
      <div style="display:flex; gap:8px; margin-bottom:12px">
        <input v-model="tempKey" placeholder="Key" style="width:140px" />
        <input v-model="tempValue" placeholder="Value" style="flex:1" />
        <button class="btn btn-primary btn-sm" @click="doInjectFact">注入</button>
        <button class="btn btn-danger btn-sm" @click="clearAllTempFacts">清除全部</button>
      </div>
      <div v-if="Object.keys(tempFacts).length === 0" style="font-size:12px; color:#9ca3af">暂无临时注入</div>
      <div v-else class="table-wrap">
        <table>
          <thead><tr><th>Key</th><th>Value</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="(v, k) in tempFacts" :key="k">
              <td><code>{{ k }}</code></td>
              <td>{{ v }}</td>
              <td><button class="btn btn-danger btn-sm" @click="removeTempFact(k)">移除</button></td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- LLM 沙盒 -->
    <div class="card mt-4">
      <div class="card-title">LLM 沙盒</div>
      <div class="form-group">
        <label class="form-label">System Prompt</label>
        <textarea v-model="sandboxSystem" rows="5" style="font-family:monospace;font-size:12px" />
      </div>
      <button class="btn btn-secondary btn-sm" style="margin-bottom:8px; margin-top:-4px" @click="fillCurrentPrompt">
        使用当前角色 System Prompt
      </button>
      <div class="form-group">
        <label class="form-label">User Message</label>
        <textarea v-model="sandboxUser" rows="3" />
      </div>
      <button class="btn btn-primary" :disabled="sandboxLoading" @click="doSandbox">
        {{ sandboxLoading ? '发送中…' : '发送' }}
      </button>
      <div v-if="sandboxResult" class="sandbox-result mt-4">
        <div class="sandbox-reply">{{ sandboxResult.reply }}</div>
        <div class="sandbox-meta">
          耗时 {{ sandboxResult.elapsed_ms }}ms ·
          Input {{ sandboxResult.input_tokens }} · Output {{ sandboxResult.output_tokens }} ·
          {{ sandboxResult.provider }}/{{ sandboxResult.model }}
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, inject, onMounted, onUnmounted } from 'vue'
import { api } from '../api'

const showToast = inject<(msg: string, type?: any) => void>('showToast', () => {})

const debugState = ref<any>(null)
const loading = ref(false)
const error = ref('')
const showPrompt = ref(false)
const autoRefresh = ref(false)
let autoTimer: ReturnType<typeof setInterval> | null = null

const moodOptions = ['normal', 'happy', 'angry', 'shy', 'cold']
const injectMood = ref('normal')
const injectPersist = ref(3)

const tempFacts = ref<Record<string, string>>({})
const tempKey = ref('')
const tempValue = ref('')

const sandboxSystem = ref('')
const sandboxUser = ref('')
const sandboxLoading = ref(false)
const sandboxResult = ref<any>(null)

async function loadState() {
  loading.value = true
  try {
    ;[debugState.value, tempFacts.value] = await Promise.all([
      api.debugState(),
      api.listTempFacts(),
    ])
  } catch (e: any) {
    error.value = `连接失败: ${e.message}`
  } finally {
    loading.value = false
  }
}

function toggleAutoRefresh() {
  if (autoRefresh.value) {
    autoTimer = setInterval(loadState, 2000)
  } else {
    if (autoTimer) clearInterval(autoTimer)
  }
}

async function doInjectEmotion() {
  try {
    await api.injectEmotion(injectMood.value, injectPersist.value)
    showToast(`情绪已注入: ${injectMood.value}`, 'success')
    await loadState()
  } catch (e: any) {
    showToast(`失败: ${e.message}`, 'error')
  }
}

async function doInjectFact() {
  if (!tempKey.value) return
  try {
    await api.injectTempFact(tempKey.value, tempValue.value)
    showToast('已注入', 'success')
    tempKey.value = ''
    tempValue.value = ''
    tempFacts.value = await api.listTempFacts()
  } catch (e: any) {
    showToast(`失败: ${e.message}`, 'error')
  }
}

async function removeTempFact(key: string) {
  try {
    await api.clearTempFact(key)
    tempFacts.value = await api.listTempFacts()
  } catch (e: any) {
    showToast(`失败: ${e.message}`, 'error')
  }
}

async function clearAllTempFacts() {
  try {
    await api.clearTempFact()
    tempFacts.value = {}
    showToast('已清除全部', 'success')
  } catch (e: any) {
    showToast(`失败: ${e.message}`, 'error')
  }
}

function fillCurrentPrompt() {
  sandboxSystem.value = debugState.value?.system_prompt ?? ''
}

async function doSandbox() {
  if (!sandboxUser.value) return
  sandboxLoading.value = true
  sandboxResult.value = null
  try {
    sandboxResult.value = await api.sandbox(sandboxSystem.value, sandboxUser.value)
  } catch (e: any) {
    showToast(`LLM 调用失败: ${e.message}`, 'error')
  } finally {
    sandboxLoading.value = false
  }
}

onMounted(loadState)
onUnmounted(() => { if (autoTimer) clearInterval(autoTimer) })
</script>

<style scoped>
.state-grid {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.state-row {
  display: flex;
  gap: 12px;
  font-size: 13px;
}

.state-k {
  width: 100px;
  flex-shrink: 0;
  font-size: 12px;
  color: #6b7280;
}

.prompt-box {
  margin-top: 8px;
  padding: 12px;
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  font-family: monospace;
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 400px;
  overflow-y: auto;
  color: #374151;
}

.sandbox-result {
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  padding: 12px;
}

.sandbox-reply {
  font-size: 13px;
  color: #1a1a1a;
  margin-bottom: 8px;
  line-height: 1.5;
  white-space: pre-wrap;
}

.sandbox-meta {
  font-size: 11px;
  color: #9ca3af;
}
</style>
