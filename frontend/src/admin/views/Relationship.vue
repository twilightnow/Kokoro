<script setup lang="ts">
import { computed, inject, onMounted } from 'vue'

import { useRelationshipAdmin } from '../composables/useRelationshipAdmin'

const showToast = inject<(message: string, type?: 'info' | 'success' | 'error') => void>(
  'showToast',
  () => {},
)

const {
  activeChar,
  characters,
  error,
  form,
  loading,
  recentReasons,
  relationship,
  saving,
  loadCharacters,
  loadRelationship,
  resetRelationship,
  saveProfile,
  selectCharacter,
} = useRelationshipAdmin()

const metricCards = computed(() => {
  const state = relationship.value
  if (!state) {
    return []
  }

  return [
    { key: 'intimacy', label: '亲密度', value: state.intimacy, tone: 'rose' },
    { key: 'trust', label: '信任度', value: state.trust, tone: 'sky' },
    { key: 'familiarity', label: '熟悉度', value: state.familiarity, tone: 'emerald' },
    { key: 'dependency_risk', label: '依赖风险', value: state.dependency_risk, tone: 'amber' },
  ]
})

function meterStyle(value: number): { width: string } {
  const width = Math.max(6, Math.min(100, value))
  return { width: `${width}%` }
}

async function onCharacterChange(event: Event): Promise<void> {
  const target = event.target as HTMLSelectElement | null
  await selectCharacter(target?.value ?? '')
}

async function onSave(): Promise<void> {
  try {
    await saveProfile()
    showToast('关系状态已保存', 'success')
  } catch (err) {
    const message = err instanceof Error ? err.message : '关系状态保存失败'
    showToast(message, 'error')
  }
}

async function onReset(): Promise<void> {
  if (!window.confirm('确认将当前角色的关系状态重置为默认值吗？')) {
    return
  }

  try {
    await resetRelationship()
    showToast('关系状态已重置', 'success')
  } catch (err) {
    const message = err instanceof Error ? err.message : '关系状态重置失败'
    showToast(message, 'error')
  }
}

async function onRefresh(): Promise<void> {
  try {
    await loadRelationship()
    showToast('关系状态已刷新', 'info')
  } catch (err) {
    const message = err instanceof Error ? err.message : '关系状态刷新失败'
    showToast(message, 'error')
  }
}

onMounted(async () => {
  try {
    await loadCharacters()
  } catch (err) {
    const message = err instanceof Error ? err.message : '角色列表加载失败'
    showToast(message, 'error')
  }
})
</script>

<template>
  <div>
    <div class="page-header">
      <div>
        <h1 class="page-title">关系状态</h1>
        <p class="page-subtitle">把关系成长、边界偏好和近期变化作为可查看、可重置的运行时状态管理。</p>
      </div>
      <div class="page-actions">
        <select class="character-select" :value="activeChar" @change="onCharacterChange">
          <option v-for="character in characters" :key="character.id" :value="character.id">
            {{ character.name }} ({{ character.id }})
          </option>
        </select>
        <button class="btn btn-secondary btn-sm" :disabled="loading" @click="onRefresh">刷新</button>
      </div>
    </div>

    <div v-if="error" class="banner-error">{{ error }}</div>
    <div v-if="loading && !relationship" class="loading">加载中…</div>

    <template v-else-if="relationship">
      <div class="grid-4">
        <div v-for="metric in metricCards" :key="metric.key" class="card metric-card">
          <div class="card-title">{{ metric.label }}</div>
          <div class="metric-value">{{ metric.value }}</div>
          <div class="meter">
            <div class="meter-fill" :class="`meter-fill--${metric.tone}`" :style="meterStyle(metric.value)" />
          </div>
        </div>
      </div>

      <div class="layout-grid mt-4">
        <div class="card form-card">
          <div class="card-header">
            <div>
              <div class="card-title">关系资料</div>
              <div class="card-subtitle">这些字段直接影响 prompt 注入和管理端显示。</div>
            </div>
            <span class="badge badge-blue">{{ relationship.relationship_type }}</span>
          </div>

          <div class="kv-row">
            <span class="kv-label">近期互动质量</span>
            <span class="kv-value">{{ relationship.interaction_quality_recent }}/100</span>
          </div>
          <div class="kv-row">
            <span class="kv-label">最后更新</span>
            <span class="kv-value">{{ relationship.updated_at || '暂无' }}</span>
          </div>
          <div class="boundary-summary">
            {{ relationship.boundary_policy_summary }}
          </div>

          <label class="form-label" for="relationship-type">关系类型</label>
          <select id="relationship-type" v-model="form.relationship_type" class="form-control">
            <option value="friend">friend</option>
            <option value="partner">partner</option>
            <option value="family">family</option>
            <option value="mentor">mentor</option>
            <option value="coworker">coworker</option>
          </select>

          <label class="form-label" for="relationship-addressing">偏好称呼</label>
          <input
            id="relationship-addressing"
            v-model="form.preferred_addressing"
            class="form-control"
            maxlength="40"
            placeholder="例如：队长 / 搭档 / 老师"
          >

          <label class="form-label" for="relationship-boundaries">边界摘要</label>
          <textarea
            id="relationship-boundaries"
            v-model="form.boundaries_summary"
            class="form-control form-textarea"
            maxlength="240"
            placeholder="例如：工作时只允许低频提醒；不要在深夜主动追问情绪。"
          />

          <div class="form-actions">
            <button class="btn btn-primary" :disabled="saving" @click="onSave">保存关系资料</button>
            <button class="btn btn-danger" :disabled="saving" @click="onReset">重置状态</button>
          </div>
        </div>

        <div class="card history-card">
          <div class="card-header">
            <div>
              <div class="card-title">最近变化原因</div>
              <div class="card-subtitle">仅记录代码规则推导出的变化，不允许模型直接改数值。</div>
            </div>
            <span class="badge badge-gray">{{ recentReasons.length }} 条</span>
          </div>

          <ul v-if="recentReasons.length" class="reason-list">
            <li v-for="(reason, index) in recentReasons" :key="`${reason}-${index}`" class="reason-item">
              {{ reason }}
            </li>
          </ul>
          <div v-else class="empty-state">还没有记录到关系变化。</div>
        </div>
      </div>
    </template>
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
  max-width: 720px;
  margin-top: 6px;
  font-size: 12px;
  line-height: 1.6;
  color: #6b7280;
}

.page-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.character-select,
.form-control {
  width: 100%;
  border: 1px solid #d1d5db;
  border-radius: 10px;
  background: #fff;
  color: #111827;
  padding: 10px 12px;
  font-size: 13px;
}

.character-select {
  width: 220px;
}

.form-textarea {
  min-height: 132px;
  resize: vertical;
}

.grid-4 {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.metric-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.metric-value {
  font-size: 24px;
  font-weight: 700;
  color: #111827;
}

.meter {
  height: 10px;
  overflow: hidden;
  border-radius: 999px;
  background: #e5e7eb;
}

.meter-fill {
  height: 100%;
  border-radius: inherit;
}

.meter-fill--rose {
  background: linear-gradient(90deg, #f97316, #fb7185);
}

.meter-fill--sky {
  background: linear-gradient(90deg, #2563eb, #38bdf8);
}

.meter-fill--emerald {
  background: linear-gradient(90deg, #059669, #34d399);
}

.meter-fill--amber {
  background: linear-gradient(90deg, #d97706, #f59e0b);
}

.layout-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(0, 0.85fr);
  gap: 14px;
}

.form-card,
.history-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.card-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.card-subtitle {
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.5;
  color: #6b7280;
}

.kv-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 0;
  border-bottom: 1px solid #e5e7eb;
}

.kv-label {
  font-size: 12px;
  color: #6b7280;
}

.kv-value {
  font-size: 13px;
  color: #111827;
}

.boundary-summary {
  padding: 10px 12px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #f8fafc;
  font-size: 12px;
  line-height: 1.6;
  color: #374151;
}

.form-label {
  font-size: 12px;
  font-weight: 600;
  color: #374151;
}

.form-actions {
  display: flex;
  gap: 10px;
  margin-top: 6px;
}

.reason-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  list-style: none;
}

.reason-item {
  padding: 10px 12px;
  border-radius: 10px;
  background: #f8fafc;
  font-size: 13px;
  line-height: 1.5;
  color: #374151;
}

.empty-state {
  padding: 14px;
  border: 1px dashed #d1d5db;
  border-radius: 10px;
  font-size: 12px;
  color: #6b7280;
}

.badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
}

.badge-blue {
  background: #dbeafe;
  color: #1d4ed8;
}

.badge-gray {
  background: #f3f4f6;
  color: #4b5563;
}

@media (max-width: 1120px) {
  .grid-4,
  .layout-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 760px) {
  .page-header,
  .page-actions,
  .grid-4,
  .layout-grid {
    grid-template-columns: 1fr;
    flex-direction: column;
  }

  .character-select {
    width: 100%;
  }
}
</style>
