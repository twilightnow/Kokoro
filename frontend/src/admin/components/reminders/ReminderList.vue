<script setup lang="ts">
import { computed } from 'vue'

interface ReminderItem {
  id: string
  character_id: string
  title: string
  note: string
  due_at: string
  repeat_rule: 'once' | 'daily' | 'weekly'
  status: 'scheduled' | 'pending_ack' | 'completed'
  created_at: string
  updated_at: string
  completed_at: string | null
  source: string
  last_triggered_at: string | null
}

const props = defineProps<{
  items: ReminderItem[]
  loading: boolean
  busyReminderId: string
}>()

const emit = defineEmits<{
  edit: [reminder: ReminderItem]
  complete: [reminderId: string]
  snooze: [reminderId: string]
  delete: [reminderId: string]
}>()

const pendingItems = computed(() => props.items.filter((item) => item.status !== 'completed'))
const completedItems = computed(() => props.items.filter((item) => item.status === 'completed'))

function formatTime(value: string | null): string {
  if (!value) {
    return '暂无'
  }
  return new Date(value).toLocaleString()
}

function repeatLabel(value: ReminderItem['repeat_rule']): string {
  return {
    once: '一次',
    daily: '每天',
    weekly: '每周',
  }[value]
}

function statusLabel(value: ReminderItem['status']): string {
  return {
    scheduled: '待触发',
    pending_ack: '等待确认',
    completed: '已完成',
  }[value]
}
</script>

<template>
  <div class="list-grid">
    <section class="card list-card">
      <div class="card-header">
        <div>
          <div class="card-title">待处理提醒</div>
          <div class="card-subtitle">到期后会进入 proactive reminder 场景，并遵循当前主动策略。</div>
        </div>
        <span class="badge badge-blue">{{ pendingItems.length }}</span>
      </div>

      <div v-if="props.loading" class="loading">加载中…</div>
      <div v-else-if="!pendingItems.length" class="empty-state">当前没有待处理提醒。</div>
      <div v-else class="reminder-list">
        <article v-for="item in pendingItems" :key="item.id" class="reminder-item">
          <div class="item-head">
            <div>
              <div class="item-title">{{ item.title }}</div>
              <div class="item-meta">
                <span>{{ repeatLabel(item.repeat_rule) }}</span>
                <span>{{ formatTime(item.due_at) }}</span>
                <span>{{ statusLabel(item.status) }}</span>
              </div>
            </div>
            <span class="badge" :class="item.status === 'pending_ack' ? 'badge-amber' : 'badge-gray'">
              {{ statusLabel(item.status) }}
            </span>
          </div>

          <div v-if="item.note" class="item-note">{{ item.note }}</div>
          <div class="item-submeta">
            <span>最近触发: {{ formatTime(item.last_triggered_at) }}</span>
            <span>更新于: {{ formatTime(item.updated_at) }}</span>
          </div>

          <div class="item-actions">
            <button class="btn btn-secondary btn-sm" :disabled="props.busyReminderId === item.id" @click="emit('edit', item)">
              编辑
            </button>
            <button class="btn btn-primary btn-sm" :disabled="props.busyReminderId === item.id" @click="emit('complete', item.id)">
              完成
            </button>
            <button class="btn btn-secondary btn-sm" :disabled="props.busyReminderId === item.id" @click="emit('snooze', item.id)">
              稍后 30 分钟
            </button>
            <button class="btn btn-danger btn-sm" :disabled="props.busyReminderId === item.id" @click="emit('delete', item.id)">
              删除
            </button>
          </div>
        </article>
      </div>
    </section>

    <section class="card list-card">
      <div class="card-header">
        <div>
          <div class="card-title">已完成提醒</div>
          <div class="card-subtitle">只保留本地状态，不回写到 proactive 设置页。</div>
        </div>
        <span class="badge badge-gray">{{ completedItems.length }}</span>
      </div>

      <div v-if="props.loading" class="loading">加载中…</div>
      <div v-else-if="!completedItems.length" class="empty-state">还没有已完成提醒。</div>
      <div v-else class="reminder-list">
        <article v-for="item in completedItems" :key="item.id" class="reminder-item reminder-item--completed">
          <div class="item-head">
            <div>
              <div class="item-title">{{ item.title }}</div>
              <div class="item-meta">
                <span>{{ repeatLabel(item.repeat_rule) }}</span>
                <span>完成于 {{ formatTime(item.completed_at) }}</span>
              </div>
            </div>
            <span class="badge badge-green">已完成</span>
          </div>

          <div v-if="item.note" class="item-note">{{ item.note }}</div>
          <div class="item-actions">
            <button class="btn btn-danger btn-sm" :disabled="props.busyReminderId === item.id" @click="emit('delete', item.id)">
              删除
            </button>
          </div>
        </article>
      </div>
    </section>
  </div>
</template>

<style scoped>
.list-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.list-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.reminder-list {
  display: grid;
  gap: 12px;
}

.reminder-item {
  display: flex;
  flex-direction: column;
  gap: 10px;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.72);
  padding: 12px;
}

.reminder-item--completed {
  border-style: dashed;
}

.item-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.item-title {
  font-size: 15px;
  font-weight: 700;
  color: #111827;
}

.item-meta,
.item-submeta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  color: #6b7280;
  font-size: 12px;
}

.item-note {
  color: #374151;
  line-height: 1.6;
  white-space: pre-wrap;
}

.item-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

@media (max-width: 960px) {
  .list-grid {
    grid-template-columns: 1fr;
  }
}
</style>