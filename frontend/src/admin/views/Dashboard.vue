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

        <!-- Sidecar 状态 -->
        <div class="card">
          <div class="card-title">Sidecar 状态</div>
          <div class="stat-value">
            <span :class="health?.status === 'ok' ? 'text-green' : 'text-red'">
              {{ health?.status === 'ok' ? '✅ 运行中' : '❌ 离线' }}
            </span>
          </div>
          <div class="stat-sub">Port: 18765</div>
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
    ;[state.value, health.value] = await Promise.all([api.getState(), api.getHealth()])
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
</style>
