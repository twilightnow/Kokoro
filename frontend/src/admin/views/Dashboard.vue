<template>
  <div>
    <div class="page-header">
      <h1 class="page-title">状态总览</h1>
      <div class="page-actions">
        <span class="last-refresh">{{ lastRefreshLabel }}</span>
        <button class="btn btn-secondary btn-sm" @click="refresh">刷新</button>
      </div>
    </div>

    <div v-if="error" class="banner-error">{{ error }}</div>

    <div v-if="loading && !state" class="loading">加载中…</div>

    <template v-else-if="state">
      <div class="grid-3">
        <!-- 当前角色 -->
        <div class="card">
          <div class="card-title">当前角色</div>
          <div class="stat-value">{{ state.character_name }}</div>
          <div class="stat-sub">{{ state.character_id }}</div>
          <button class="btn btn-secondary btn-sm mt-4" @click="$router.push('/characters')">
            切换角色
          </button>
        </div>

        <!-- 当前情绪 -->
        <div class="card">
          <div class="card-title">当前情绪</div>
          <div class="stat-value">{{ moodEmoji_current }} {{ state.mood }}</div>
          <div class="stat-sub">剩余 {{ state.persist_count }} 轮</div>
          <button class="btn btn-secondary btn-sm mt-4" @click="resetMood">重置为 normal</button>
        </div>

        <!-- 本次会话 -->
        <div class="card">
          <div class="card-title">本次会话</div>
          <div class="stat-value">第 {{ state.turn }} 轮</div>
          <div class="stat-sub" :title="tokenTitle">
            累计 {{ formatTokens(totalTokens) }} Token
          </div>
          <div v-if="estimatedCostLabel" class="stat-sub">{{ estimatedCostLabel }}</div>
        </div>

        <!-- 记忆状态 -->
        <div class="card">
          <div class="card-title">记忆状态</div>
          <div class="stat-value">摘要 {{ state.memory_summary_count }} 条</div>
          <div class="stat-sub">事实 {{ state.memory_fact_count }} 项</div>
          <button class="btn btn-secondary btn-sm mt-4" @click="$router.push('/memories')">
            查看记忆
          </button>
        </div>

        <div class="card">
          <div class="card-title">关系状态</div>
          <div class="stat-value">{{ state.relationship?.relationship_type || 'friend' }}</div>
          <div class="stat-sub">
            信任 {{ state.relationship?.trust ?? 0 }} / 熟悉 {{ state.relationship?.familiarity ?? 0 }}
          </div>
          <button class="btn btn-secondary btn-sm mt-4" @click="$router.push('/relationship')">
            查看关系
          </button>
        </div>

        <!-- Sidecar 状态 -->
        <div class="card">
          <div class="card-title">Sidecar 状态</div>
          <div class="stat-value">
            <span :class="health?.sidecar?.status === 'ok' ? 'text-green' : 'text-red'">
              {{ health?.sidecar?.status === 'ok' ? '运行中' : '离线' }}
            </span>
          </div>
          <div class="stat-sub">Port: 18765</div>
        </div>

        <div class="card">
          <div class="card-title">LLM Provider</div>
          <div class="stat-value">
            <span :class="health?.llm?.configured ? 'text-green' : 'text-red'">
              {{ health?.llm?.provider || '未配置' }}
            </span>
          </div>
          <div class="stat-sub">{{ health?.llm?.model || '需要在设置页配置' }}</div>
          <button class="btn btn-secondary btn-sm mt-4" @click="$router.push('/settings')">
            打开设置
          </button>
        </div>

        <div class="card">
          <div class="card-title">角色资源</div>
          <div class="stat-value">
            <span :class="health?.character_resources?.configured ? 'text-green' : 'text-warn'">
              {{ health?.character_resources?.display_mode || 'placeholder' }}
            </span>
          </div>
          <div class="stat-sub">
            {{ health?.character_resources?.status === 'fallback' ? '使用占位降级' : '资源可用' }}
          </div>
        </div>

        <div class="card">
          <div class="card-title">TTS</div>
          <div class="stat-value">
            <span :class="health?.tts?.configured ? 'text-green' : 'text-red'">
              {{ health?.tts?.provider || 'edge-tts' }}
            </span>
          </div>
          <div class="stat-sub">{{ health?.tts?.voice || health?.tts?.message || '未启用' }}</div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, inject } from 'vue'
import { api } from '../api'

const showToast = inject<(msg: string, type?: any) => void>('showToast', () => {})

const state = ref<any>(null)
const health = ref<any>(null)
const pricing = ref<{ input: number | null, output: number | null }>({ input: null, output: null })
const loading = ref(false)
const error = ref('')
const lastRefresh = ref<Date | null>(null)
let timer: ReturnType<typeof setInterval> | null = null

const lastRefreshLabel = computed(() => {
  if (!lastRefresh.value) return ''
  return `上次刷新: ${lastRefresh.value.toLocaleTimeString()}`
})

const totalTokens = computed(() => {
  const t = state.value?.session_token_total
  if (!t) return 0
  return (t.input ?? 0) + (t.output ?? 0)
})

const tokenTitle = computed(() => {
  const t = state.value?.session_token_total
  if (!t) return ''
  return `Input: ${t.input ?? 0}  Output: ${t.output ?? 0}`
})

const estimatedCost = computed(() => {
  const totals = state.value?.session_token_total
  if (!totals) {
    return null
  }

  const inputPrice = pricing.value.input ?? 0
  const outputPrice = pricing.value.output ?? 0
  if (!inputPrice && !outputPrice) {
    return null
  }

  return ((totals.input ?? 0) * inputPrice + (totals.output ?? 0) * outputPrice) / 1_000_000
})

const estimatedCostLabel = computed(() => {
  if (estimatedCost.value === null) {
    return ''
  }
  return `≈ ¥${estimatedCost.value.toFixed(2)}`
})

function parsePrice(value: unknown): number | null {
  if (value === '' || value === null || value === undefined) {
    return null
  }

  const parsed = Number(value)
  if (!Number.isFinite(parsed) || parsed < 0) {
    return null
  }

  return parsed
}

function syncPricing(configData: any): void {
  const entries = Array.isArray(configData?.entries) ? configData.entries : []
  const inputEntry = entries.find((entry: any) => entry.key === 'PRICE_INPUT')
  const outputEntry = entries.find((entry: any) => entry.key === 'PRICE_OUTPUT')
  pricing.value = {
    input: parsePrice(inputEntry?.value),
    output: parsePrice(outputEntry?.value),
  }
}

function formatTokens(n: number) {
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`
  return String(n)
}

const moodEmoji: Record<string, string> = {
  normal: '😐',
  happy: '😊',
  angry: '😠',
  shy: '😳',
  cold: '🥶',
}

const moodEmoji_current = computed(() => {
  const m = state.value?.mood ?? 'normal'
  return moodEmoji[m] ?? '😐'
})

async function refresh() {
  loading.value = true
  error.value = ''
  try {
    const [nextState, nextHealth, configData] = await Promise.all([
      api.getState(),
      api.getHealth(),
      api.getConfig().catch(() => null),
    ])
    state.value = nextState
    health.value = nextHealth
    syncPricing(configData)
    lastRefresh.value = new Date()
  } catch (e: any) {
    error.value = `连接失败: ${e.message}`
  } finally {
    loading.value = false
  }
}

async function resetMood() {
  try {
    await api.injectEmotion('normal', 0)
    showToast('情绪已重置为 normal', 'success')
    await refresh()
  } catch (e: any) {
    showToast(`操作失败: ${e.message}`, 'error')
  }
}

onMounted(() => {
  refresh()
  timer = setInterval(refresh, 5000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<style scoped>
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
}

.page-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.last-refresh {
  font-size: 11px;
  color: #9ca3af;
}

.stat-value {
  font-size: 20px;
  font-weight: 600;
  color: #1a1a1a;
  margin: 4px 0;
}

.stat-sub {
  font-size: 12px;
  color: #6b7280;
}

.text-green { color: #15803d; }
.text-red { color: #b91c1c; }
.text-warn { color: #a16207; }
</style>
