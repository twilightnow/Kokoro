<script setup lang="ts">
import { inject, onMounted } from 'vue'

import ReminderEditor from '../components/reminders/ReminderEditor.vue'
import ReminderList from '../components/reminders/ReminderList.vue'
import { useReminderAdmin, type ReminderItem } from '../composables/useReminderAdmin'

const showToast = inject<(message: string, type?: 'info' | 'success' | 'error') => void>(
  'showToast',
  () => {},
)

const {
  activeChar,
  busyReminderId,
  characters,
  completedReminders,
  draft,
  error,
  includeCompleted,
  isEditing,
  loading,
  pendingReminders,
  reminders,
  saving,
  beginEdit,
  completeReminder,
  deleteReminder,
  loadCharacters,
  loadReminders,
  resetDraft,
  selectCharacter,
  snoozeReminder,
  submitDraft,
  toggleIncludeCompleted,
} = useReminderAdmin()

async function onRefresh(): Promise<void> {
  try {
    await loadReminders()
    showToast('提醒列表已刷新', 'info')
  } catch (err) {
    const message = err instanceof Error ? err.message : '提醒列表刷新失败'
    showToast(message, 'error')
  }
}

async function onSubmit(): Promise<void> {
  try {
    await submitDraft()
    showToast(isEditing.value ? '提醒已更新' : '提醒已创建', 'success')
  } catch (err) {
    const message = err instanceof Error ? err.message : '提醒保存失败'
    showToast(message, 'error')
  }
}

async function onComplete(reminderId: string): Promise<void> {
  try {
    await completeReminder(reminderId)
    showToast('提醒已标记为完成', 'success')
  } catch (err) {
    const message = err instanceof Error ? err.message : '提醒完成失败'
    showToast(message, 'error')
  }
}

async function onSnooze(reminderId: string): Promise<void> {
  try {
    await snoozeReminder(reminderId)
    showToast('提醒已顺延 30 分钟', 'success')
  } catch (err) {
    const message = err instanceof Error ? err.message : '提醒顺延失败'
    showToast(message, 'error')
  }
}

async function onDelete(reminderId: string): Promise<void> {
  if (!window.confirm('确认删除这条提醒吗？')) {
    return
  }
  try {
    await deleteReminder(reminderId)
    showToast('提醒已删除', 'success')
  } catch (err) {
    const message = err instanceof Error ? err.message : '提醒删除失败'
    showToast(message, 'error')
  }
}

function onEdit(reminder: ReminderItem): void {
  beginEdit(reminder)
  showToast(`正在编辑提醒：${reminder.title}`, 'info')
}

async function onToggleIncludeCompleted(event: Event): Promise<void> {
  const target = event.target as HTMLInputElement | null
  try {
    await toggleIncludeCompleted(target?.checked ?? true)
  } catch (err) {
    const message = err instanceof Error ? err.message : '提醒过滤切换失败'
    showToast(message, 'error')
  }
}

onMounted(async () => {
  try {
    await loadCharacters()
  } catch (err) {
    const message = err instanceof Error ? err.message : '提醒页面初始化失败'
    showToast(message, 'error')
  }
})
</script>

<template>
  <div>
    <div class="page-header">
      <div>
        <h1 class="page-title">提醒管理</h1>
        <p class="page-subtitle">创建、改期、完成和删除本地约定提醒；Proactive 页只保留 reminder 场景开关。</p>
      </div>
      <label class="toggle-chip">
        <input :checked="includeCompleted" type="checkbox" @change="onToggleIncludeCompleted">
        <span>显示已完成</span>
      </label>
    </div>

    <div v-if="error" class="banner-error">{{ error }}</div>

    <div class="layout-grid">
      <ReminderEditor
        v-model="draft"
        :active-char="activeChar"
        :characters="characters"
        :loading="loading"
        :saving="saving"
        :is-editing="isEditing"
        @refresh="onRefresh"
        @reset="resetDraft"
        @select-character="selectCharacter"
        @submit="onSubmit"
      />

      <div class="card summary-card">
        <div class="card-title">运行时摘要</div>
        <div class="summary-stat">待处理 {{ pendingReminders.length }} 条</div>
        <div class="summary-stat">已完成 {{ completedReminders.length }} 条</div>
        <div class="summary-copy">当前角色: {{ activeChar || '暂无' }}</div>
        <div class="summary-copy">总数: {{ reminders.length }} 条</div>
        <div class="summary-copy">反馈“知道了”会完成 reminder；“稍后提醒”会顺延 30 分钟。</div>
      </div>
    </div>

    <div class="mt-4">
      <ReminderList
        :busy-reminder-id="busyReminderId"
        :items="reminders"
        :loading="loading"
        @complete="onComplete"
        @delete="onDelete"
        @edit="onEdit"
        @snooze="onSnooze"
      />
    </div>
  </div>
</template>

<style scoped>
.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 20px;
}

.page-subtitle {
  max-width: 760px;
  margin-top: 6px;
  color: #6b7280;
  font-size: 12px;
  line-height: 1.6;
}

.toggle-chip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border: 1px solid #d1d5db;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.78);
  color: #111827;
  padding: 8px 12px;
  font-size: 12px;
}

.layout-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) minmax(280px, 0.8fr);
  gap: 16px;
}

.summary-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.summary-stat {
  font-size: 22px;
  font-weight: 700;
  color: #111827;
}

.summary-copy {
  color: #6b7280;
  font-size: 13px;
  line-height: 1.6;
}

@media (max-width: 960px) {
  .page-header {
    flex-direction: column;
  }

  .layout-grid {
    grid-template-columns: 1fr;
  }
}
</style>