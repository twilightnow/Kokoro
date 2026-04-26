<template>
  <div>
    <h1 class="page-title">调试工具</h1>

    <div v-if="error" class="banner-error">{{ error }}</div>

    <div class="card">
      <div class="card-header">
        <div>
          <div class="card-title">实时状态快照</div>
          <div class="section-note">直接读取当前 ConversationService 内存状态，不访问磁盘日志。</div>
        </div>
        <div class="section-inline section-inline--wrap">
          <label class="inline-check">
            <input type="checkbox" v-model="autoRefresh" @change="toggleAutoRefresh" />
            自动刷新（2s）
          </label>
          <button class="btn btn-secondary btn-sm" @click="reloadCharacterConfig">重载角色配置</button>
          <button class="btn btn-secondary btn-sm" @click="loadDebugData">刷新</button>
        </div>
      </div>

      <div v-if="loading && !debugState" class="loading">加载中…</div>
      <template v-else-if="debugState">
        <div class="state-grid">
          <div class="state-row"><span class="state-k">角色</span><span>{{ debugState.character_id }} / {{ debugState.character_name }}</span></div>
          <div class="state-row">
            <span class="state-k">情绪</span>
            <span>{{ debugState.mood }}（预计剩余 {{ debugState.estimated_remaining_turns }} 轮，兼容值 {{ debugState.persist_count }}）</span>
          </div>
          <div class="state-row">
            <span class="state-k">强度</span>
            <span>{{ emotionIntensityLabel(debugState.intensity) }}（{{ formatIntensity(debugState.intensity) }}） · 恢复速率 {{ formatIntensity(debugState.recovery_rate) }}</span>
          </div>
          <div class="state-row"><span class="state-k">触发词</span><span>{{ debugState.keyword || '—' }}</span></div>
          <div class="state-row"><span class="state-k">原因</span><span>{{ debugState.reason || '—' }}</span></div>
          <div class="state-row"><span class="state-k">来源</span><span>{{ debugState.source || '—' }}</span></div>
          <div class="state-row"><span class="state-k">开始轮次</span><span>{{ debugState.started_at_turn || '—' }} / 已持续 {{ debugState.elapsed_turns || 0 }} 轮 / 兼容持续 {{ debugState.duration_turns || 0 }} 轮</span></div>
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

        <div class="emotion-events mt-4">
          <div class="section-inline section-inline--wrap emotion-events-header">
            <div class="card-title card-title--sm">当前情绪片段</div>
            <span class="section-note">展示当前片段的持续状态、恢复阶段和 TTS 调整。</span>
          </div>
          <div v-if="!debugState.current_segment" class="empty-state">当前没有激活的情绪片段。</div>
          <div v-else class="emotion-event-item">
            <div class="emotion-event-top">
              <span class="emotion-chip">{{ debugState.current_segment.mood }}</span>
              <span class="emotion-event-meta">turn {{ debugState.current_segment.started_at_turn }}</span>
              <span class="emotion-event-meta">已持续 {{ debugState.current_segment.elapsed_turns }} 轮</span>
              <span class="emotion-event-meta">剩余 {{ debugState.current_segment.estimated_remaining_turns }} 轮</span>
            </div>
            <div class="emotion-event-body">
              <span>强度 {{ emotionIntensityLabel(debugState.current_segment.intensity) }}（{{ formatIntensity(debugState.current_segment.intensity) }}）</span>
              <span>恢复速率 {{ formatIntensity(debugState.current_segment.recovery_rate) }}</span>
              <span v-if="debugState.current_segment.tts_rate_delta">TTS 语速 {{ debugState.current_segment.tts_rate_delta }}</span>
              <span v-if="debugState.current_segment.tts_volume_delta">TTS 音量 {{ debugState.current_segment.tts_volume_delta }}</span>
            </div>
            <div class="emotion-event-reason">{{ debugState.current_segment.reason || '（无原因）' }}</div>
          </div>
        </div>

        <div class="emotion-events mt-4">
          <div class="section-inline section-inline--wrap emotion-events-header">
            <div class="card-title card-title--sm">最近 5 条情绪事件</div>
            <span class="section-note">按最近触发倒序显示，只记录触发事件，不记录自然衰减。</span>
          </div>
          <div v-if="!recentEmotionEvents.length" class="empty-state">最近还没有情绪事件。</div>
          <div v-else class="emotion-event-list">
            <div
              v-for="event in recentEmotionEvents"
              :key="`${event.started_at_turn}-${event.mood}-${event.keyword}-${event.reason}`"
              class="emotion-event-item"
            >
              <div class="emotion-event-top">
                <span class="emotion-chip">{{ event.mood }}</span>
                <span class="emotion-event-meta">turn {{ event.started_at_turn || 0 }}</span>
                <span class="emotion-event-meta">{{ event.source || 'unknown' }}</span>
              </div>
              <div class="emotion-event-body">
                <span>强度 {{ emotionIntensityLabel(event.intensity) }}（{{ formatIntensity(event.intensity) }}）</span>
                <span>初始持续 {{ event.duration_turns }} 轮</span>
                <span v-if="event.keyword">触发词 {{ event.keyword }}</span>
              </div>
              <div class="emotion-event-reason">{{ event.reason || '（无原因）' }}</div>
            </div>
          </div>
        </div>

        <div class="emotion-events mt-4">
          <div class="section-inline section-inline--wrap emotion-events-header">
            <div class="card-title card-title--sm">最近安全事件</div>
            <span class="section-note">只展示风险级别、动作和规则名，不展示完整原文。</span>
          </div>
          <div v-if="!debugState.recent_safety_events.length" class="empty-state">最近还没有安全事件。</div>
          <div v-else class="emotion-event-list">
            <div
              v-for="event in debugState.recent_safety_events"
              :key="`${event.turn}-${event.level}-${event.action}-${event.rule_names.join(',')}`"
              class="emotion-event-item"
            >
              <div class="emotion-event-top">
                <span class="emotion-chip">{{ event.level }}</span>
                <span class="emotion-event-meta">turn {{ event.turn }}</span>
                <span class="emotion-event-meta">{{ event.action }}</span>
                <span class="emotion-event-meta">{{ event.relationship_type || 'friend' }}</span>
              </div>
              <div class="emotion-event-reason">{{ event.rule_names.join(' / ') || event.reason || '—' }}</div>
            </div>
          </div>
        </div>

        <div class="emotion-events mt-4">
          <div class="section-inline section-inline--wrap emotion-events-header">
            <div class="card-title card-title--sm">最近情绪片段</div>
            <span class="section-note">按片段结束顺序倒序显示，用于观察覆盖、恢复与重置原因。</span>
          </div>
          <div v-if="!debugState.segments.length" class="empty-state">还没有结束的情绪片段。</div>
          <div v-else class="emotion-event-list">
            <div
              v-for="segment in debugState.segments"
              :key="`${segment.started_at_turn}-${segment.mood}-${segment.end_reason}`"
              class="emotion-event-item"
            >
              <div class="emotion-event-top">
                <span class="emotion-chip">{{ segment.mood }}</span>
                <span class="emotion-event-meta">turn {{ segment.started_at_turn }} → {{ segment.ended_at_turn ?? '—' }}</span>
                <span class="emotion-event-meta">已持续 {{ segment.elapsed_turns }} 轮</span>
                <span class="emotion-event-meta">{{ segment.source || 'unknown' }}</span>
              </div>
              <div class="emotion-event-body">
                <span>结束原因 {{ segment.end_reason || '—' }}</span>
                <span>最终强度 {{ formatIntensity(segment.intensity) }}</span>
                <span v-if="segment.keyword">触发词 {{ segment.keyword }}</span>
              </div>
              <div class="emotion-event-reason">{{ segment.reason || '（无原因）' }}</div>
            </div>
          </div>
        </div>

        <div class="section-actions mt-4">
          <div class="section-inline section-inline--wrap">
            <button class="btn btn-secondary btn-sm" @click="showPrompt = !showPrompt">
              {{ showPrompt ? '折叠' : '展开' }} System Prompt 全文
            </button>
            <span class="metric-chip">~{{ debugState.system_prompt_estimated_tokens }} tokens</span>
            <span v-if="promptShareLabel" class="section-note">{{ promptShareLabel }}</span>
          </div>
          <div class="section-inline section-inline--wrap">
            <button class="btn btn-secondary btn-sm" @click="showWorkingMemory = !showWorkingMemory">
              {{ showWorkingMemory ? '收起工作记忆' : '展开工作记忆' }}
            </button>
            <button class="btn btn-danger btn-sm" @click="clearWorkingMemory">清空工作记忆</button>
          </div>
        </div>

        <div v-if="showPrompt" class="prompt-box">{{ debugState.system_prompt || '（暂无）' }}</div>

        <div v-if="showWorkingMemory" class="working-memory-list mt-4">
          <div v-if="!workingMemory.length" class="empty-state">当前工作记忆为空。</div>
          <div v-for="message in workingMemory" :key="message.index" class="memory-item">
            <div class="memory-meta">
              <span class="memory-index">#{{ message.index }}</span>
              <span class="memory-role" :class="`memory-role--${message.role}`">{{ message.role }}</span>
            </div>
            <div class="memory-content">{{ message.content }}</div>
          </div>
        </div>
      </template>
    </div>

    <div class="card mt-4">
      <div class="card-header">
        <div>
          <div class="card-title">Token 消耗</div>
          <div class="section-note">按轮显示当前会话内存中的 usage 记录。</div>
        </div>
      </div>

      <div v-if="!tokenHistory?.items?.length" class="empty-state">当前会话还没有 token 使用记录。</div>
      <div v-else class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>轮次</th>
              <th>Input</th>
              <th>Output</th>
              <th>Model</th>
              <th>Provider</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in tokenHistory.items" :key="item.turn">
              <td>{{ item.turn }}</td>
              <td>{{ item.input_tokens }}</td>
              <td>{{ item.output_tokens }}</td>
              <td>{{ item.model || '—' }}</td>
              <td>{{ item.provider || '—' }}</td>
            </tr>
          </tbody>
          <tfoot>
            <tr>
              <td>Session 合计</td>
              <td>{{ tokenHistory.session_input_tokens }}</td>
              <td>{{ tokenHistory.session_output_tokens }}</td>
              <td colspan="2">总计 {{ tokenHistory.session_total_tokens }}</td>
            </tr>
          </tfoot>
        </table>
      </div>
    </div>

    <div class="card mt-4">
      <div class="card-title">情绪注入</div>
      <div class="section-inline section-inline--wrap section-inline--end">
        <div class="form-group form-group--compact">
          <label class="form-label">情绪</label>
          <select v-model="injectMood">
            <option v-for="m in moodOptions" :key="m" :value="m">{{ m }}</option>
          </select>
        </div>
        <div class="form-group form-group--compact form-group--short">
          <label class="form-label">持续轮数</label>
          <input type="number" v-model.number="injectPersist" min="0" max="10" />
        </div>
        <button class="btn btn-primary" @click="doInjectEmotion">注入情绪</button>
      </div>
      <div class="section-note">注入后下轮对话立即生效，不写入日志。</div>
    </div>

    <div class="card mt-4">
      <div class="card-title">临时事实注入（会话内有效，不写磁盘）</div>
      <div class="section-inline section-inline--wrap" style="margin-bottom: 12px;">
        <input v-model="tempKey" class="input-inline input-inline--key" placeholder="Key" />
        <input v-model="tempValue" class="input-inline input-inline--value" placeholder="Value" />
        <button class="btn btn-primary btn-sm" @click="doInjectFact">注入</button>
        <button class="btn btn-danger btn-sm" @click="clearAllTempFacts">清除全部</button>
      </div>
      <div v-if="Object.keys(tempFacts).length === 0" class="empty-state">暂无临时注入。</div>
      <div v-else class="table-wrap">
        <table>
          <thead><tr><th>Key</th><th>Value</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="(value, key) in tempFacts" :key="key">
              <td>{{ key }}</td>
              <td>{{ value }}</td>
              <td><button class="btn btn-danger btn-sm" @click="removeTempFact(key)">移除</button></td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div class="card mt-4">
      <div class="card-header">
        <div>
          <div class="card-title">LLM 沙盒</div>
          <div class="section-note">不写日志，不改记忆状态；可选择带上当前工作记忆做上下文测试。</div>
        </div>
        <label class="inline-check">
          <input type="checkbox" v-model="sandboxUseWorkingMemory" />
          携带当前工作记忆
        </label>
      </div>

      <div class="form-group">
        <label class="form-label">System Prompt</label>
        <textarea v-model="sandboxSystem" rows="5" class="prompt-input" />
      </div>
      <button class="btn btn-secondary btn-sm" style="margin-bottom: 8px; margin-top: -4px;" @click="fillCurrentPrompt">
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

    <div class="card mt-4">
      <div class="card-header">
        <div>
          <div class="card-title">客户端日志</div>
          <div class="section-note">查看 sidecar 内存中的客户端诊断 buffer，可按 level 过滤。</div>
        </div>
        <div class="section-inline section-inline--wrap">
          <select v-model="clientLogLevel" class="mini-select">
            <option value="all">全部 level</option>
            <option value="debug">debug</option>
            <option value="info">info</option>
            <option value="warn">warn</option>
            <option value="error">error</option>
          </select>
          <button class="btn btn-secondary btn-sm" @click="clearRenderedLogs">清空显示</button>
        </div>
      </div>

      <div v-if="!filteredClientLogs.length" class="empty-state">暂无匹配的客户端日志。</div>
      <div v-else class="client-log-list">
        <div v-for="item in filteredClientLogs" :key="`${item.time}-${item.source}-${item.event}-${item.message}`" class="client-log-item">
          <div class="client-log-top">
            <span class="client-log-time">{{ item.time }}</span>
            <span class="client-log-level" :class="`client-log-level--${item.level}`">{{ item.level }}</span>
            <span class="client-log-source">{{ item.source }}</span>
            <span class="client-log-event">{{ item.event }}</span>
          </div>
          <div class="client-log-message">{{ item.message || '（无消息）' }}</div>
          <pre v-if="item.details && Object.keys(item.details).length" class="client-log-details">{{ JSON.stringify(item.details, null, 2) }}</pre>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, inject, onMounted, onUnmounted, ref } from 'vue'
import { api } from '../api'

type ToastType = 'info' | 'success' | 'error'

interface DebugState {
  character_id: string
  character_name: string
  mood: string
  persist_count: number
  keyword: string
  reason: string
  source: string
  intensity: number
  started_at_turn: number
  duration_turns: number
  elapsed_turns: number
  recovery_rate: number
  estimated_remaining_turns: number
  turn: number
  working_memory_count: number
  working_memory_truncation_count: number
  memory_summary_count: number
  memory_fact_count: number
  session_token_input: number
  session_token_output: number
  system_prompt: string
  system_prompt_estimated_tokens: number
  temp_facts: Record<string, string>
  recent_events: DebugEmotionEvent[]
  recent_safety_events: DebugSafetyEvent[]
  current_segment: DebugTimelineSegment | null
  segments: DebugTimelineSegment[]
}

interface DebugEmotionEvent {
  mood: string
  keyword: string
  reason: string
  source: string
  intensity: number
  recovery_rate: number
  started_at_turn: number
  duration_turns: number
}

interface DebugTimelineSegment {
  mood: string
  keyword: string
  reason: string
  source: string
  intensity: number
  recovery_rate: number
  started_at_turn: number
  last_updated_turn: number
  elapsed_turns: number
  estimated_remaining_turns: number
  ended_at_turn: number | null
  end_reason: string
  tts_rate_delta: string
  tts_volume_delta: string
}

interface DebugSafetyEvent {
  turn: number
  level: string
  action: string
  reason: string
  rule_names: string[]
  relationship_type: string
}

interface TokenHistoryItem {
  turn: number
  input_tokens: number
  output_tokens: number
  provider: string
  model: string
}

interface TokenHistoryResponse {
  items: TokenHistoryItem[]
  session_input_tokens: number
  session_output_tokens: number
  session_total_tokens: number
}

interface WorkingMemoryItem {
  index: number
  role: string
  content: string
}

interface ClientLogItem {
  time: string
  source: string
  event: string
  level: string
  message: string
  details: Record<string, unknown>
}

interface SandboxResult {
  reply: string
  input_tokens: number
  output_tokens: number
  provider: string
  model: string
  elapsed_ms: number
}

const showToast = inject<(message: string, type?: ToastType) => void>('showToast', () => {})

const debugState = ref<DebugState | null>(null)
const tokenHistory = ref<TokenHistoryResponse | null>(null)
const workingMemory = ref<WorkingMemoryItem[]>([])
const clientLogs = ref<ClientLogItem[]>([])
const loading = ref(false)
const error = ref('')
const showPrompt = ref(false)
const showWorkingMemory = ref(false)
const autoRefresh = ref(false)
const clientLogLevel = ref('all')
let autoTimer: ReturnType<typeof setInterval> | null = null

const moodOptions = ['normal', 'happy', 'angry', 'shy', 'cold']
const injectMood = ref('normal')
const injectPersist = ref(3)

const tempFacts = ref<Record<string, string>>({})
const tempKey = ref('')
const tempValue = ref('')

const sandboxSystem = ref('')
const sandboxUser = ref('')
const sandboxUseWorkingMemory = ref(false)
const sandboxLoading = ref(false)
const sandboxResult = ref<SandboxResult | null>(null)

const promptShareLabel = computed(() => {
  const state = debugState.value
  if (!state || !state.system_prompt_estimated_tokens) {
    return ''
  }
  if (state.session_token_input <= 0) {
    return '当前还没有 session input token 可对比'
  }

  const ratio = Math.round((state.system_prompt_estimated_tokens / state.session_token_input) * 100)
  return `约占 session input ${ratio}%`
})

const recentEmotionEvents = computed(() => {
  const events = debugState.value?.recent_events ?? []
  return [...events].reverse()
})

const filteredClientLogs = computed(() => {
  if (clientLogLevel.value === 'all') {
    return clientLogs.value
  }
  return clientLogs.value.filter((item) => item.level === clientLogLevel.value)
})

function emotionIntensityLabel(intensity: number): string {
  if (intensity >= 0.75) {
    return '高'
  }
  if (intensity >= 0.35) {
    return '中'
  }
  if (intensity > 0) {
    return '低'
  }
  return '无'
}

function formatIntensity(intensity: number): string {
  return intensity.toFixed(2)
}

function stopAutoRefresh(): void {
  if (autoTimer) {
    clearInterval(autoTimer)
    autoTimer = null
  }
}

function toggleAutoRefresh(): void {
  stopAutoRefresh()
  if (autoRefresh.value) {
    autoTimer = setInterval(() => {
      void loadDebugData()
    }, 2000)
  }
}

async function loadDebugData(): Promise<void> {
  loading.value = true
  error.value = ''
  try {
    const [nextState, nextTempFacts, nextTokenHistory, nextWorkingMemory, nextClientLogs] = await Promise.all([
      api.debugState(),
      api.listTempFacts(),
      api.debugTokenHistory(),
      api.getWorkingMemory(),
      api.getClientLogs(100),
    ])
    debugState.value = nextState as DebugState
    tempFacts.value = nextTempFacts as Record<string, string>
    tokenHistory.value = nextTokenHistory as TokenHistoryResponse
    workingMemory.value = nextWorkingMemory as WorkingMemoryItem[]
    clientLogs.value = nextClientLogs as ClientLogItem[]
    if (!sandboxSystem.value) {
      sandboxSystem.value = nextState.system_prompt ?? ''
    }
  } catch (e: any) {
    error.value = `连接失败: ${e.message}`
  } finally {
    loading.value = false
  }
}

async function reloadCharacterConfig(): Promise<void> {
  try {
    const result = await api.reloadCharacterConfig()
    showToast(`角色配置已重载: ${result.character_name}`, 'success')
    await loadDebugData()
  } catch (e: any) {
    showToast(`重载失败: ${e.message}`, 'error')
  }
}

async function clearWorkingMemory(): Promise<void> {
  if (!window.confirm('确认清空当前工作记忆吗？这不会影响长期记忆或事实。')) {
    return
  }

  try {
    const result = await api.clearWorkingMemory()
    showToast(`已清空 ${result.cleared} 条工作记忆`, 'success')
    await loadDebugData()
  } catch (e: any) {
    showToast(`清空失败: ${e.message}`, 'error')
  }
}

async function doInjectEmotion(): Promise<void> {
  try {
    await api.injectEmotion(injectMood.value, injectPersist.value)
    showToast(`情绪已注入: ${injectMood.value}`, 'success')
    await loadDebugData()
  } catch (e: any) {
    showToast(`失败: ${e.message}`, 'error')
  }
}

async function doInjectFact(): Promise<void> {
  if (!tempKey.value.trim()) {
    return
  }

  try {
    await api.injectTempFact(tempKey.value.trim(), tempValue.value.trim())
    showToast('已注入临时事实', 'success')
    tempKey.value = ''
    tempValue.value = ''
    tempFacts.value = await api.listTempFacts()
  } catch (e: any) {
    showToast(`失败: ${e.message}`, 'error')
  }
}

async function removeTempFact(key: string): Promise<void> {
  try {
    await api.clearTempFact(key)
    tempFacts.value = await api.listTempFacts()
  } catch (e: any) {
    showToast(`失败: ${e.message}`, 'error')
  }
}

async function clearAllTempFacts(): Promise<void> {
  try {
    await api.clearTempFact()
    tempFacts.value = {}
    showToast('已清除全部临时事实', 'success')
  } catch (e: any) {
    showToast(`失败: ${e.message}`, 'error')
  }
}

function fillCurrentPrompt(): void {
  sandboxSystem.value = debugState.value?.system_prompt ?? ''
}

async function doSandbox(): Promise<void> {
  if (!sandboxUser.value.trim()) {
    return
  }

  sandboxLoading.value = true
  sandboxResult.value = null
  try {
    sandboxResult.value = await api.sandbox(
      sandboxSystem.value,
      sandboxUser.value,
      sandboxUseWorkingMemory.value,
    ) as SandboxResult
  } catch (e: any) {
    showToast(`LLM 调用失败: ${e.message}`, 'error')
  } finally {
    sandboxLoading.value = false
  }
}

function clearRenderedLogs(): void {
  clientLogs.value = []
  showToast('客户端日志显示已清空', 'info')
}

onMounted(() => {
  void loadDebugData()
})

onUnmounted(() => {
  stopAutoRefresh()
})
</script>

<style scoped>
.card-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 12px;
}

.section-note {
  font-size: 11px;
  line-height: 1.5;
  color: #6b7280;
}

.section-actions {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.emotion-events-header {
  margin-bottom: 10px;
}

.section-inline {
  display: flex;
  align-items: center;
  gap: 8px;
}

.section-inline--wrap {
  flex-wrap: wrap;
}

.section-inline--end {
  align-items: flex-end;
}

.inline-check {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #4b5563;
  cursor: pointer;
}

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

.metric-chip {
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  border-radius: 999px;
  background: #eef2ff;
  color: #4338ca;
  font-size: 11px;
  font-weight: 600;
}

.prompt-box,
.sandbox-result,
.memory-item,
.client-log-item,
.emotion-event-item {
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
}

.emotion-event-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.emotion-event-item {
  padding: 12px;
}

.emotion-event-top,
.emotion-event-body {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.emotion-event-body {
  margin-top: 8px;
  font-size: 12px;
  color: #4b5563;
}

.emotion-event-meta {
  font-size: 11px;
  color: #6b7280;
}

.emotion-chip {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 999px;
  background: #ede9fe;
  color: #6d28d9;
  font-size: 11px;
  font-weight: 600;
}

.emotion-event-reason {
  margin-top: 8px;
  font-size: 13px;
  color: #1f2937;
  line-height: 1.5;
}

.prompt-box {
  margin-top: 8px;
  padding: 12px;
  font-family: monospace;
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 400px;
  overflow-y: auto;
  color: #374151;
}

.working-memory-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.memory-item {
  padding: 12px;
}

.memory-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.memory-index {
  font-size: 11px;
  color: #6b7280;
}

.memory-role {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
}

.memory-role--user {
  background: #dbeafe;
  color: #1d4ed8;
}

.memory-role--assistant {
  background: #fce7f3;
  color: #be185d;
}

.memory-content,
.sandbox-reply,
.client-log-message {
  font-size: 13px;
  color: #1f2937;
  line-height: 1.6;
  white-space: pre-wrap;
}

.empty-state {
  padding: 12px;
  border: 1px dashed #d1d5db;
  border-radius: 8px;
  font-size: 12px;
  color: #6b7280;
}

.form-group--compact {
  margin: 0;
  min-width: 140px;
}

.form-group--short {
  width: 88px;
  min-width: 88px;
}

.input-inline {
  border: 1px solid #d1d5db;
  border-radius: 8px;
  padding: 10px 12px;
  font-size: 13px;
  color: #111827;
  background: #fff;
}

.input-inline--key {
  width: 140px;
}

.input-inline--value {
  flex: 1;
}

.prompt-input {
  font-family: monospace;
  font-size: 12px;
}

tfoot td {
  font-weight: 600;
  color: #111827;
}

.sandbox-result {
  padding: 12px;
}

.sandbox-meta {
  margin-top: 8px;
  font-size: 11px;
  color: #9ca3af;
}

.mini-select {
  min-width: 110px;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  padding: 8px 10px;
  font-size: 12px;
  color: #111827;
  background: #fff;
}

.client-log-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: 420px;
  overflow-y: auto;
}

.client-log-item {
  padding: 12px;
}

.client-log-top {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 8px;
  font-size: 11px;
}

.client-log-time,
.client-log-source,
.client-log-event {
  color: #6b7280;
}

.client-log-level {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 999px;
  font-weight: 600;
}

.client-log-level--debug {
  background: #e0f2fe;
  color: #0369a1;
}

.client-log-level--info {
  background: #dcfce7;
  color: #15803d;
}

.client-log-level--warn {
  background: #fef3c7;
  color: #b45309;
}

.client-log-level--error {
  background: #fee2e2;
  color: #b91c1c;
}

.client-log-details {
  margin-top: 8px;
  padding: 10px;
  border-radius: 6px;
  background: #111827;
  color: #e5e7eb;
  font-size: 11px;
  white-space: pre-wrap;
  overflow-x: auto;
}

@media (max-width: 900px) {
  .card-header,
  .section-actions {
    flex-direction: column;
    align-items: stretch;
  }

  .input-inline--key,
  .input-inline--value {
    width: 100%;
  }
}
</style>
