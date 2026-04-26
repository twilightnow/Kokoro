<template>
  <div>
    <div class="page-header">
      <h1 class="page-title">主动陪伴</h1>
      <div class="page-actions">
        <button class="btn btn-secondary btn-sm" :disabled="loading" @click="refreshAll">刷新</button>
        <button class="btn btn-secondary btn-sm" :disabled="testing" @click="sendTest">
          {{ testing ? '触发中…' : '发送测试气泡' }}
        </button>
      </div>
    </div>

    <div v-if="loading && !settingsLoaded" class="loading">加载中…</div>

    <template v-else>
      <div class="grid-3">
        <div class="card">
          <div class="card-title">今日主动状态</div>
          <div class="stat-value">{{ status.today_count ?? 0 }} 次</div>
          <div class="stat-sub">冷却剩余 {{ Math.ceil((status.cooldown_remaining_seconds ?? 0) / 60) }} 分钟</div>
          <div class="stat-sub">最近原因: {{ status.last_reason || '暂无' }}</div>
        </div>

        <div class="card">
          <div class="card-title">当前模式</div>
          <div class="stat-value">{{ modeLabel(settings.mode) }}</div>
          <div class="stat-sub">运行中: {{ status.running ? '是' : '否' }}</div>
          <div class="stat-sub">最近场景: {{ status.last_scene || '暂无' }}</div>
        </div>

        <div class="card">
          <div class="card-title">开关</div>
          <div class="settings-list compact-list">
            <label><input type="checkbox" v-model="settings.enabled" /> 启用主动陪伴</label>
            <label><input type="checkbox" v-model="settings.dnd_enabled" /> 启用勿扰时间</label>
          </div>
        </div>
      </div>

      <div class="card mt-4">
        <div class="card-title">主动性策略</div>
        <div class="grid-2">
          <div class="form-group">
            <label class="form-label">主动性档位</label>
            <select v-model="settings.mode">
              <option value="off">关闭</option>
              <option value="low">低频</option>
              <option value="normal">普通</option>
              <option value="high">高频</option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">每日上限</label>
            <input type="number" v-model.number="maxPerDayValue" min="0" placeholder="留空则使用档位默认值" />
          </div>
        </div>
        <div class="grid-2 mt-4">
          <div class="form-group">
            <label class="form-label">勿扰开始</label>
            <input type="time" v-model="settings.dnd_start" />
          </div>
          <div class="form-group">
            <label class="form-label">勿扰结束</label>
            <input type="time" v-model="settings.dnd_end" />
          </div>
        </div>
      </div>

      <div class="card mt-4">
        <div class="card-title">场景偏好</div>
        <div class="grid-2">
          <div class="settings-list compact-list">
            <label><input type="checkbox" v-model="settings.allow_late_night" /> 深夜仍在使用电脑</label>
            <label><input type="checkbox" v-model="settings.allow_long_work" /> 长时间工作 / 久坐</label>
            <label><input type="checkbox" v-model="settings.allow_idle_return" /> 长时间空闲后回来</label>
          </div>
          <div class="settings-list compact-list">
            <label><input type="checkbox" v-model="settings.allow_window_switch" /> 频繁切换窗口</label>
            <label><input type="checkbox" v-model="settings.allow_gaming" /> 游戏中</label>
            <label><input type="checkbox" v-model="settings.allow_reminders" /> 约定提醒</label>
          </div>
        </div>

        <div class="form-group mt-4">
          <label class="form-label">游戏中行为</label>
          <select v-model="settings.gaming_level">
            <option value="silent">不打扰</option>
            <option value="expression">只切表情</option>
            <option value="short">短句</option>
            <option value="full">完整短句</option>
          </select>
        </div>
      </div>

      <div class="actions">
        <button class="btn btn-primary" :disabled="saving" @click="save">
          {{ saving ? '保存中…' : '保存主动陪伴设置' }}
        </button>
      </div>

      <div class="card mt-4">
        <div class="card-title">最近主动记录</div>
        <div v-if="!logs.length" class="empty-state">暂无记录。</div>
        <div v-else class="log-list">
          <div v-for="item in logs" :key="item.id" class="log-item">
            <div class="log-head">
              <strong>{{ item.scene }}</strong>
              <span class="badge">{{ item.level }}</span>
              <span class="muted">{{ formatTime(item.timestamp) }}</span>
            </div>
            <div class="muted">决策: {{ item.decision }} / 原因: {{ item.reason }}</div>
            <div v-if="item.content" class="log-content">{{ item.content }}</div>
            <div class="muted">回应: {{ item.user_responded ? item.feedback || '已回应' : '未回应' }}</div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { inject, onMounted, ref } from 'vue'
import { api } from '../api'

const showToast = inject<(msg: string, type?: any) => void>('showToast', () => {})

const loading = ref(false)
const saving = ref(false)
const testing = ref(false)
const settingsLoaded = ref(false)
const logs = ref<any[]>([])
const status = ref<Record<string, any>>({})
const settings = ref({
  enabled: true,
  mode: 'normal',
  dnd_enabled: true,
  dnd_start: '23:30',
  dnd_end: '08:00',
  allow_late_night: true,
  allow_long_work: true,
  allow_idle_return: true,
  allow_window_switch: true,
  allow_gaming: true,
  allow_reminders: true,
  gaming_level: 'expression',
  max_per_day: null as number | null,
})
const maxPerDayValue = ref<number | null>(null)

function modeLabel(mode: string): string {
  return {
    off: '关闭',
    low: '低频',
    normal: '普通',
    high: '高频',
  }[mode] ?? mode
}

function formatTime(value: string): string {
  if (!value) return ''
  return new Date(value).toLocaleString()
}

async function loadSettings(): Promise<void> {
  const response = await api.getProactiveSettings()
  settings.value = {
    ...settings.value,
    ...response.settings,
  }
  maxPerDayValue.value = response.settings.max_per_day ?? null
  settingsLoaded.value = true
}

async function loadStatusAndLogs(): Promise<void> {
  const [statusResponse, logsResponse] = await Promise.all([
    api.getProactiveStatus(),
    api.getProactiveLogs(20),
  ])
  status.value = statusResponse
  logs.value = logsResponse.items ?? []
}

async function refreshAll(): Promise<void> {
  loading.value = true
  try {
    await Promise.all([loadSettings(), loadStatusAndLogs()])
  } catch (error: any) {
    showToast(`加载主动陪伴失败: ${error.message}`, 'error')
  } finally {
    loading.value = false
  }
}

async function save(): Promise<void> {
  saving.value = true
  try {
    const payload = {
      ...settings.value,
      max_per_day: maxPerDayValue.value === null || Number.isNaN(maxPerDayValue.value)
        ? null
        : maxPerDayValue.value,
    }
    await api.updateProactiveSettings(payload)
    await loadStatusAndLogs()
    showToast('主动陪伴设置已保存', 'success')
  } catch (error: any) {
    showToast(`保存失败: ${error.message}`, 'error')
  } finally {
    saving.value = false
  }
}

async function sendTest(): Promise<void> {
  testing.value = true
  try {
    await api.testProactive()
    await loadStatusAndLogs()
    showToast('已发送测试主动气泡', 'success')
  } catch (error: any) {
    showToast(`触发测试失败: ${error.message}`, 'error')
  } finally {
    testing.value = false
  }
}

onMounted(refreshAll)
</script>

<style scoped>
.compact-list {
  gap: 10px;
}

.actions {
  display: flex;
  gap: 8px;
  margin-top: 16px;
}

.log-list {
  display: grid;
  gap: 12px;
}

.log-item {
  border: 1px solid var(--card-border, #e5e7eb);
  border-radius: 12px;
  padding: 12px;
  background: rgba(255, 255, 255, 0.72);
}

.log-head {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
  margin-bottom: 6px;
}

.muted {
  color: #6b7280;
  font-size: 12px;
}

.log-content {
  margin: 8px 0;
  line-height: 1.6;
}

.empty-state {
  color: #6b7280;
  font-size: 13px;
}
</style>