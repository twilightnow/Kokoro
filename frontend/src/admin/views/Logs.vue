<template>
  <div>
    <h1 class="page-title">对话日志</h1>

    <div class="logs-layout">
      <!-- 左：会话列表 -->
      <div class="logs-list card">
        <div class="logs-list-header">
          <span class="card-title" style="margin:0">会话列表</span>
          <button class="btn btn-danger btn-sm" @click="clearAllLogs">清空全部</button>
        </div>

        <div v-if="loadingList" class="loading">加载中…</div>
        <div v-else-if="!logList?.items?.length" class="empty">暂无日志</div>
        <div
          v-else
          v-for="item in logList.items"
          :key="item.filename"
          class="log-row"
          :class="{ 'log-row--active': selectedFile === item.filename }"
          @click="selectLog(item.filename)"
        >
          <div class="log-row-name">{{ formatLogName(item.filename) }}</div>
          <div class="log-row-meta">{{ item.turn_count }} 轮 · {{ formatSize(item.size) }}</div>
        </div>

        <div class="pagination">
          <button
            class="btn btn-secondary btn-sm"
            :disabled="logOffset === 0"
            @click="logOffset = Math.max(0, logOffset - 30); loadList()"
          >上一页</button>
          <span>{{ logOffset + 1 }}–{{ Math.min(logOffset + 30, logList?.total ?? 0) }} / {{ logList?.total ?? 0 }}</span>
          <button
            class="btn btn-secondary btn-sm"
            :disabled="logOffset + 30 >= (logList?.total ?? 0)"
            @click="logOffset += 30; loadList()"
          >下一页</button>
        </div>
      </div>

      <!-- 右：日志内容 -->
      <div class="log-detail">
        <div v-if="!selectedFile" class="empty" style="margin-top:60px">选择左侧会话查看详情</div>
        <div v-else-if="loadingDetail" class="loading">加载中…</div>
        <template v-else>
          <!-- 搜索栏 -->
          <div style="display:flex; gap:8px; margin-bottom:14px">
            <input v-model="searchQuery" placeholder="搜索关键词…" style="flex:1" />
            <label style="display:flex; align-items:center; gap:4px; font-size:12px; cursor:pointer">
              <input type="checkbox" v-model="showFlaggedOnly" />
              仅显示禁用词
            </label>
          </div>

          <div v-for="turn in filteredTurns" :key="turn.turn" class="turn-card">
            <div class="turn-header">
              Turn {{ turn.turn }}
              <span class="turn-time">{{ turn.timestamp?.slice(0, 19)?.replace('T', ' ') }}</span>
            </div>
            <div class="turn-body">
              <div class="turn-row">
                <span class="turn-label">用户</span>
                <span>{{ turn.user_input }}</span>
              </div>
              <div class="turn-row" v-if="turn.mood_before !== turn.mood_after">
                <span class="turn-label">情绪</span>
                <span class="mood-change">{{ turn.mood_before }} → {{ turn.mood_after }}</span>
              </div>
              <div class="turn-row">
                <span class="turn-label">回复</span>
                <span>{{ turn.reply }}</span>
              </div>
              <div class="turn-row" v-if="turn.usage">
                <span class="turn-label">Token</span>
                <span style="color:#6b7280; font-size:12px">
                  ↑{{ turn.usage.input_tokens }} ↓{{ turn.usage.output_tokens }}
                  · {{ turn.usage.provider }}/{{ turn.usage.model }}
                </span>
              </div>
              <div v-if="turn.flagged" class="flagged-warning">⚠️ 禁用词命中</div>
            </div>
          </div>

          <div v-if="!filteredTurns.length" class="empty">无匹配记录</div>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, inject, onMounted } from 'vue'
import { api } from '../api'

const showToast = inject<(msg: string, type?: any) => void>('showToast', () => {})

const logList = ref<any>(null)
const logOffset = ref(0)
const loadingList = ref(false)
const selectedFile = ref<string | null>(null)
const logDetail = ref<any[]>([])
const loadingDetail = ref(false)
const searchQuery = ref('')
const showFlaggedOnly = ref(false)

const filteredTurns = computed(() => {
  let items = logDetail.value
  if (showFlaggedOnly.value) items = items.filter((t) => t.flagged)
  if (searchQuery.value) {
    const q = searchQuery.value.toLowerCase()
    items = items.filter(
      (t) =>
        t.user_input?.toLowerCase().includes(q) || t.reply?.toLowerCase().includes(q),
    )
  }
  return items
})

async function loadList() {
  loadingList.value = true
  try {
    logList.value = await api.listLogs(logOffset.value, 30)
  } catch (e: any) {
    showToast(`加载失败: ${e.message}`, 'error')
  } finally {
    loadingList.value = false
  }
}

async function selectLog(filename: string) {
  selectedFile.value = filename
  loadingDetail.value = true
  try {
    logDetail.value = await api.getLog(filename)
  } catch (e: any) {
    showToast(`加载失败: ${e.message}`, 'error')
  } finally {
    loadingDetail.value = false
  }
}

async function clearAllLogs() {
  const input = prompt('此操作将删除所有会话日志文件。确认请输入 "DELETE"')
  if (input !== 'DELETE') return
  try {
    const r = await api.clearAllLogs()
    showToast(`已删除 ${r.deleted} 个文件`, 'success')
    selectedFile.value = null
    logDetail.value = []
    await loadList()
  } catch (e: any) {
    showToast(`失败: ${e.message}`, 'error')
  }
}

function formatLogName(filename: string) {
  // session_20260422_143000.jsonl → 今天 14:30
  const m = filename.match(/session_(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})/)
  if (!m) return filename
  const [, y, mo, d, h, mi] = m
  return `${y}-${mo}-${d} ${h}:${mi}`
}

function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes}B`
  return `${(bytes / 1024).toFixed(1)}KB`
}

onMounted(loadList)
</script>

<style scoped>
.logs-layout {
  display: grid;
  grid-template-columns: 240px 1fr;
  gap: 16px;
}

.logs-list {
  padding: 0;
  height: calc(100vh - 120px);
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}

.logs-list-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 14px;
  border-bottom: 1px solid #e5e7eb;
  flex-shrink: 0;
}

.log-row {
  padding: 9px 14px;
  border-bottom: 1px solid #f3f4f6;
  cursor: pointer;
  transition: background 0.1s;
}

.log-row:hover { background: #f9fafb; }
.log-row--active { background: #eff6ff; }

.log-row-name {
  font-size: 12px;
  font-weight: 500;
  color: #374151;
}

.log-row-meta {
  font-size: 11px;
  color: #9ca3af;
  margin-top: 1px;
}

.log-detail {
  height: calc(100vh - 120px);
  overflow-y: auto;
}

.turn-card {
  background: #fff;
  border-radius: 8px;
  border: 1px solid #e8e8e8;
  margin-bottom: 12px;
  overflow: hidden;
}

.turn-header {
  padding: 8px 14px;
  background: #f9fafb;
  border-bottom: 1px solid #e5e7eb;
  font-size: 12px;
  font-weight: 600;
  color: #374151;
  display: flex;
  align-items: center;
  gap: 10px;
}

.turn-time {
  font-weight: 400;
  color: #9ca3af;
}

.turn-body {
  padding: 10px 14px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.turn-row {
  display: flex;
  gap: 10px;
  font-size: 13px;
}

.turn-label {
  width: 36px;
  flex-shrink: 0;
  font-size: 11px;
  font-weight: 600;
  color: #9ca3af;
  text-transform: uppercase;
  padding-top: 2px;
}

.mood-change {
  color: #d97706;
  font-size: 12px;
}

.flagged-warning {
  font-size: 12px;
  color: #b91c1c;
  background: #fee2e2;
  border-radius: 4px;
  padding: 4px 8px;
  margin-top: 4px;
}
</style>
