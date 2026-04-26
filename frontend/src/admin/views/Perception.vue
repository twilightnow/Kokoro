<template>
  <div>
    <div class="page-header">
      <h1 class="page-title">感知与隐私</h1>
      <div class="page-actions">
        <button class="btn btn-secondary btn-sm" :disabled="loading" @click="refreshAll">刷新</button>
      </div>
    </div>

    <div v-if="loading && !settingsLoaded" class="loading">加载中…</div>

    <template v-else>
      <div class="grid-3">
        <div class="card">
          <div class="card-title">采集状态</div>
          <div class="stat-value">{{ status.collector_available ? '可用' : '不可用' }}</div>
          <div class="stat-sub">最近窗口: {{ lastPerception.active_window_title || '无' }}</div>
          <div class="stat-sub">勿扰: {{ lastPerception.dnd_reason || '未命中' }}</div>
        </div>
        <div class="card">
          <div class="card-title">隐私过滤</div>
          <div class="settings-list compact-list">
            <label><input type="checkbox" v-model="settings.enabled" /> 启用隐私过滤</label>
            <label><input type="checkbox" v-model="settings.audit_enabled" /> 记录脱敏审计摘要</label>
          </div>
          <div class="stat-sub">关闭隐私过滤时不会写入感知审计。</div>
        </div>
        <div class="card">
          <div class="card-title">勿扰</div>
          <div class="settings-list compact-list">
            <label><input type="checkbox" v-model="settings.dnd_fullscreen" /> 全屏时完全静默</label>
          </div>
          <div class="stat-sub">命中勿扰时会抑制主动陪伴，不影响普通聊天。</div>
        </div>
      </div>

      <div class="card mt-4">
        <div class="card-title">采集与脱敏规则</div>
        <div class="grid-2">
          <div class="form-group">
            <label class="form-label">应用黑名单</label>
            <textarea v-model="blockedAppsText" placeholder="每行一个应用名或正则"></textarea>
          </div>
          <div class="form-group">
            <label class="form-label">窗口标题黑名单</label>
            <textarea v-model="blockedTitlesText" placeholder="每行一个标题关键词或正则"></textarea>
          </div>
        </div>
        <div class="grid-2 mt-4">
          <div class="form-group">
            <label class="form-label">敏感内容规则</label>
            <textarea v-model="sensitivePatternsText" placeholder="每行一个正则"></textarea>
          </div>
          <div class="form-group">
            <label class="form-label">标题最大长度</label>
            <input type="number" v-model.number="settings.max_title_length" min="1" max="200" />
          </div>
        </div>
      </div>

      <div class="card mt-4">
        <div class="card-title">勿扰规则</div>
        <div class="grid-3">
          <div class="form-group">
            <label class="form-label">勿扰应用</label>
            <textarea v-model="dndAppsText" placeholder="每行一个应用名或正则"></textarea>
          </div>
          <div class="form-group">
            <label class="form-label">勿扰标题</label>
            <textarea v-model="dndTitlesText" placeholder="每行一个标题关键词或正则"></textarea>
          </div>
          <div class="form-group">
            <label class="form-label">会议标题</label>
            <textarea v-model="dndMeetingText" placeholder="每行一个会议关键词或正则"></textarea>
          </div>
        </div>
      </div>

      <div class="actions">
        <button class="btn btn-primary" :disabled="saving" @click="save">
          {{ saving ? '保存中…' : '保存隐私设置' }}
        </button>
      </div>

      <div class="card mt-4">
        <div class="card-title">最近感知审计</div>
        <div v-if="!audit.length" class="empty-state">暂无审计记录。</div>
        <div v-else class="log-list">
          <div v-for="item in audit" :key="`${item.timestamp}-${item.active_window_title}`" class="log-item">
            <div class="log-head">
              <strong>{{ item.time_of_day || '未知时间段' }}</strong>
              <span class="badge">{{ item.is_user_active ? 'active' : 'idle' }}</span>
              <span class="muted">{{ formatTime(item.timestamp) }}</span>
            </div>
            <div class="muted">应用: {{ item.active_app_name || '未知' }}</div>
            <div class="muted">窗口: {{ item.active_window_title || '未记录' }}</div>
            <div class="muted">
              屏蔽: {{ item.blocked_reason || '无' }} / 勿扰: {{ item.dnd_reason || '无' }}
            </div>
            <div class="muted">脱敏: {{ Array.isArray(item.redactions) && item.redactions.length ? item.redactions.join(', ') : '无' }}</div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, inject, onMounted, ref } from 'vue'
import { api } from '../api'

const showToast = inject<(msg: string, type?: any) => void>('showToast', () => {})

const loading = ref(false)
const saving = ref(false)
const settingsLoaded = ref(false)
const status = ref<Record<string, any>>({})
const audit = ref<any[]>([])
const settings = ref({
  enabled: true,
  blocked_apps: [] as string[],
  blocked_title_patterns: [] as string[],
  sensitive_patterns: [] as string[],
  max_title_length: 40,
  audit_enabled: true,
  dnd_app_patterns: [] as string[],
  dnd_title_patterns: [] as string[],
  dnd_fullscreen: false,
  dnd_meeting_patterns: [] as string[],
})

const lastPerception = computed(() => status.value.last_perception ?? {})

function linesToText(value: string[] | undefined): string {
  return Array.isArray(value) ? value.join('\n') : ''
}

function textToLines(value: string): string[] {
  return value.split(/\r?\n/).map((line) => line.trim()).filter(Boolean)
}

const blockedAppsText = ref('')
const blockedTitlesText = ref('')
const sensitivePatternsText = ref('')
const dndAppsText = ref('')
const dndTitlesText = ref('')
const dndMeetingText = ref('')

function syncTextFields(): void {
  blockedAppsText.value = linesToText(settings.value.blocked_apps)
  blockedTitlesText.value = linesToText(settings.value.blocked_title_patterns)
  sensitivePatternsText.value = linesToText(settings.value.sensitive_patterns)
  dndAppsText.value = linesToText(settings.value.dnd_app_patterns)
  dndTitlesText.value = linesToText(settings.value.dnd_title_patterns)
  dndMeetingText.value = linesToText(settings.value.dnd_meeting_patterns)
}

function formatTime(value: string): string {
  if (!value) return ''
  return new Date(value).toLocaleString()
}

async function loadSettings(): Promise<void> {
  const response = await api.getPerceptionSettings()
  settings.value = {
    ...settings.value,
    ...response.settings,
  }
  syncTextFields()
  settingsLoaded.value = true
}

async function loadStatusAndAudit(): Promise<void> {
  const [statusResponse, auditResponse] = await Promise.all([
    api.getPerceptionStatus(),
    api.getPerceptionAudit(30),
  ])
  status.value = statusResponse
  audit.value = auditResponse.items ?? []
}

async function refreshAll(): Promise<void> {
  loading.value = true
  try {
    await Promise.all([loadSettings(), loadStatusAndAudit()])
  } catch (error: any) {
    showToast(`加载感知隐私失败: ${error.message}`, 'error')
  } finally {
    loading.value = false
  }
}

async function save(): Promise<void> {
  saving.value = true
  try {
    const payload = {
      ...settings.value,
      blocked_apps: textToLines(blockedAppsText.value),
      blocked_title_patterns: textToLines(blockedTitlesText.value),
      sensitive_patterns: textToLines(sensitivePatternsText.value),
      dnd_app_patterns: textToLines(dndAppsText.value),
      dnd_title_patterns: textToLines(dndTitlesText.value),
      dnd_meeting_patterns: textToLines(dndMeetingText.value),
    }
    const response = await api.updatePerceptionSettings(payload)
    settings.value = {
      ...settings.value,
      ...response.settings,
    }
    syncTextFields()
    await loadStatusAndAudit()
    showToast('感知隐私设置已保存', 'success')
  } catch (error: any) {
    showToast(`保存失败: ${error.message}`, 'error')
  } finally {
    saving.value = false
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

.stat-value {
  font-size: 22px;
  font-weight: 700;
  line-height: 1.4;
}

.stat-sub,
.muted {
  color: #6b7280;
  font-size: 12px;
  line-height: 1.5;
}

.log-list {
  display: grid;
  gap: 12px;
}

.log-item {
  border: 1px solid var(--card-border, #e5e7eb);
  border-radius: 8px;
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

.empty-state {
  color: #6b7280;
  font-size: 13px;
}

:global(.theme-dark) .log-item {
  border-color: #313244;
  background: #181825;
}

:global(.theme-dark) .muted,
:global(.theme-dark) .stat-sub,
:global(.theme-dark) .empty-state {
  color: #a6adc8;
}
</style>
