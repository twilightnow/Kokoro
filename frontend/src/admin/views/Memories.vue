<template>
  <div>
    <h1 class="page-title">记忆浏览</h1>

    <div class="toolbar">
      <select v-model="activeChar" style="width:160px" @change="onCharChange">
        <option v-for="c in characters" :key="c.id" :value="c.id">{{ c.name }} ({{ c.id }})</option>
      </select>
      <input v-model="searchText" class="search-input" placeholder="搜索 key、值或摘要" />
      <button class="btn btn-secondary btn-sm" @click="exportMemories">导出记忆</button>
    </div>

    <div v-if="error" class="banner-error">{{ error }}</div>

    <div class="tabs">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        class="tab-btn"
        :class="{ 'tab-btn--active': activeTab === tab.key }"
        @click="activeTab = tab.key"
      >{{ tab.label }}</button>
    </div>

    <div v-if="activeTab !== 'summaries'" class="card mt-4">
      <div style="display:flex; justify-content:space-between; margin-bottom:12px; gap:12px; flex-wrap:wrap">
        <div class="card-title" style="margin:0">{{ activeTabLabel }}</div>
        <button class="btn btn-primary btn-sm" @click="showAddFact = true">+ 新增</button>
      </div>

      <div v-if="showAddFact" class="add-form">
        <select v-model="newCategory" style="width:120px">
          <option v-for="option in factCategories" :key="option.key" :value="option.key">{{ option.label }}</option>
        </select>
        <input v-model="newKey" placeholder="Key（如 user_name）" style="width:160px" />
        <input v-model="newValue" placeholder="Value" style="flex:1" />
        <button class="btn btn-primary btn-sm" @click="addFact">确认</button>
        <button class="btn btn-secondary btn-sm" @click="showAddFact=false">取消</button>
      </div>

      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Key</th><th>类型</th><th>Value</th><th>重要性</th><th>更新时间</th><th>召回次数</th><th>状态</th><th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="!filteredFacts.length">
              <td colspan="8" class="empty">暂无记忆记录</td>
            </tr>
            <template v-for="fact in filteredFacts" :key="fact.key">
              <tr>
                <td><code style="font-size:12px">{{ fact.key }}</code></td>
                <td>
                  <template v-if="editingFact === fact.key">
                    <select v-model="editFactCategory" style="width:100px">
                      <option v-for="option in factCategories" :key="option.key" :value="option.key">{{ option.label }}</option>
                    </select>
                  </template>
                  <template v-else>
                    <span class="tag" :class="categoryClass(fact.category)">{{ categoryLabel(fact.category) }}</span>
                    <span v-if="fact.source === 'llm_extract'" class="badge badge-gray" style="margin-left:4px;font-size:10px">推断</span>
                  </template>
                </td>
                <td>
                  <template v-if="editingFact === fact.key">
                    <input v-model="editFactValue" style="width:100%" />
                  </template>
                  <template v-else>
                    {{ fact.value }}
                    <span v-if="fact.confidence !== null && fact.confidence !== undefined && fact.confidence < 0.75" style="color:#9ca3af;font-size:11px"> ({{ Math.round(fact.confidence * 100) }}%)</span>
                  </template>
                </td>
                <td style="min-width:90px">
                  <template v-if="editingImportance === fact.key">
                    <input
                      v-model.number="editImportanceValue"
                      type="range" min="0" max="1" step="0.05"
                      style="width:70px;vertical-align:middle"
                    />
                    <span style="font-size:11px;color:#6b7280">{{ editImportanceValue.toFixed(2) }}</span>
                  </template>
                  <template v-else>
                    <span
                      class="importance-pill"
                      :class="importanceClass(fact.importance)"
                      style="cursor:pointer"
                      :title="`重要性: ${fact.importance.toFixed(2)}，点击调整`"
                      @click="startEditImportance(fact)"
                    >{{ importanceLabel(fact.importance) }}</span>
                  </template>
                </td>
                <td style="color:#9ca3af;font-size:12px">{{ fact.updated_at?.slice(0,10) }}</td>
                <td style="color:#9ca3af;font-size:12px;text-align:center" :title="fact.last_accessed ? `最近召回: ${fact.last_accessed.slice(0,16)}` : '从未被召回'">
                  {{ fact.access_count }}
                </td>
                <td>
                  <span v-if="fact.pending_confirm" class="badge badge-yellow">⚠️ 待确认</span>
                  <span v-else class="badge badge-green">✅ 已确认</span>
                </td>
                <td>
                  <div style="display:flex; gap:4px; flex-wrap:wrap">
                    <template v-if="editingFact === fact.key">
                      <button class="btn btn-primary btn-sm" @click="saveFact(fact.key)">保存</button>
                      <button class="btn btn-secondary btn-sm" @click="editingFact=null">取消</button>
                    </template>
                    <template v-else-if="editingImportance === fact.key">
                      <button class="btn btn-primary btn-sm" @click="saveImportance(fact.key)">保存</button>
                      <button class="btn btn-secondary btn-sm" @click="editingImportance=null">取消</button>
                    </template>
                    <template v-else-if="fact.pending_confirm">
                      <button class="btn btn-primary btn-sm" @click="resolveConflict(fact.key, true)">采用新值</button>
                      <button class="btn btn-secondary btn-sm" @click="resolveConflict(fact.key, false)">保留旧值</button>
                    </template>
                    <template v-else>
                      <button class="btn btn-secondary btn-sm" @click="startEditFact(fact)">编辑</button>
                      <button class="btn btn-danger btn-sm" @click="deleteFact(fact.key)">删除</button>
                    </template>
                  </div>
                </td>
              </tr>
              <!-- 冲突详情行 -->
              <tr v-if="fact.pending_confirm">
                <td colspan="8" class="conflict-row">
                  旧值: <strong>{{ fact.value }}</strong>
                  → 新值: <strong>{{ fact.pending_value }}</strong>
                  <span v-if="fact.pending_category">（{{ categoryLabel(fact.pending_category) }}）</span>
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>
    </div>

    <div v-if="activeTab === 'summaries'" class="mt-4">
      <div v-if="loadingSummaries" class="loading">加载中…</div>
      <div v-else>
        <div v-if="!filteredSummaries.length" class="empty">暂无摘要记录</div>
        <div v-for="item in filteredSummaries" :key="item.index" class="summary-card card mt-4">
          <div class="summary-meta">{{ item.created_at?.slice(0,10) }}</div>
          <div class="summary-text">
            <textarea
              v-if="editingSummaryIndex === item.index"
              v-model="editSummaryText"
              rows="3"
            />
            <template v-else>{{ item.summary }}</template>
          </div>
          <div style="display:flex; gap:8px">
            <template v-if="editingSummaryIndex === item.index">
              <button class="btn btn-primary btn-sm" @click="saveSummary(item.index)">保存</button>
              <button class="btn btn-secondary btn-sm" @click="cancelSummaryEdit">取消</button>
            </template>
            <template v-else>
              <button class="btn btn-secondary btn-sm" @click="startEditSummary(item.index, item.summary)">编辑</button>
              <button class="btn btn-danger btn-sm" @click="deleteSummary(item.index)">删除</button>
            </template>
          </div>
        </div>
        <div class="pagination mt-4">
          <button
            class="btn btn-secondary btn-sm"
            :disabled="summaryOffset === 0"
            @click="summaryOffset = Math.max(0, summaryOffset - summaryLimit); loadSummaries()"
          >上一页</button>
          <span>第 {{ summaryOffset + 1 }}–{{ Math.min(summaryOffset + summaryLimit, summaryData?.total ?? 0) }} 条 / 共 {{ summaryData?.total ?? 0 }} 条</span>
          <button
            class="btn btn-secondary btn-sm"
            :disabled="summaryOffset + summaryLimit >= (summaryData?.total ?? 0)"
            @click="summaryOffset += summaryLimit; loadSummaries()"
          >下一页</button>
        </div>
      </div>
    </div>

    <div class="card mt-6" style="border-color:#fecaca">
      <div class="card-title" style="color:#b91c1c">危险操作</div>
      <div class="danger-controls">
        <select v-model="clearKind" style="width:160px">
          <option value="all">全部记忆</option>
          <option value="facts">长期事实</option>
          <option value="preferences">偏好记忆</option>
          <option value="boundaries">边界记忆</option>
          <option value="events">事件记忆</option>
          <option value="summaries">摘要记忆</option>
        </select>
        <button class="btn btn-danger" @click="confirmClear">清空所选记忆</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, inject, onMounted, ref, watch } from 'vue'
import { api } from '../api'

type ToastType = 'info' | 'success' | 'error'
type FactCategory = 'fact' | 'preference' | 'boundary' | 'event'
type MemoryTabKey = FactCategory | 'summaries'

interface CharacterSummary {
  id: string
  name: string
  is_active?: boolean
}

interface FactItem {
  record_id: string
  key: string
  value: string
  category: FactCategory
  source: string
  updated_at: string
  pending_confirm: boolean
  pending_value?: string | null
  pending_category?: string | null
  evidence?: string | null
  confidence?: number | null
  importance: number
  last_accessed?: string | null
  access_count: number
}

interface SummaryItem {
  index: number
  summary: string
  created_at: string
}

interface SummaryListResponse {
  items: SummaryItem[]
  total: number
}

const showToast = inject<(msg: string, type?: ToastType) => void>('showToast', () => {})

const characters = ref<CharacterSummary[]>([])
const activeChar = ref<string>('')
const activeTab = ref<MemoryTabKey>('fact')
const tabs: Array<{ key: MemoryTabKey; label: string }> = [
  { key: 'fact', label: '长期事实' },
  { key: 'preference', label: '偏好记忆' },
  { key: 'boundary', label: '边界记忆' },
  { key: 'event', label: '事件记忆' },
  { key: 'summaries', label: '摘要记忆' },
]
const factCategories = tabs.filter((tab) => tab.key !== 'summaries') as Array<{ key: FactCategory; label: string }>

const facts = ref<FactItem[]>([])
const error = ref('')
const editingFact = ref<string | null>(null)
const editFactValue = ref('')
const editFactCategory = ref<FactCategory>('fact')
const showAddFact = ref(false)
const newKey = ref('')
const newValue = ref('')
const newCategory = ref<FactCategory>('fact')
const searchText = ref('')
const clearKind = ref('all')

const editingImportance = ref<string | null>(null)
const editImportanceValue = ref(0.5)

const summaryData = ref<SummaryListResponse | null>(null)
const summaryOffset = ref(0)
const summaryLimit = 20
const loadingSummaries = ref(false)
const editingSummaryIndex = ref<number | null>(null)
const editSummaryText = ref('')

const activeFactCategory = computed<FactCategory | null>(() => (
  activeTab.value === 'summaries' ? null : activeTab.value
))
const activeTabLabel = computed(() => (
  tabs.find((tab) => tab.key === activeTab.value)?.label ?? '记忆'
))
const filteredFacts = computed(() => {
  const search = searchText.value.trim().toLowerCase()
  if (!search) {
    return facts.value
  }
  return facts.value.filter((fact) => (
    fact.key.toLowerCase().includes(search)
    || fact.value.toLowerCase().includes(search)
    || categoryLabel(fact.category).includes(searchText.value.trim())
  ))
})
const filteredSummaries = computed(() => {
  const search = searchText.value.trim().toLowerCase()
  const items = summaryData.value?.items ?? []
  if (!search) {
    return items
  }
  return items.filter((item) => item.summary.toLowerCase().includes(search))
})

async function loadChars() {
  try {
    characters.value = await api.listCharacters()
    if (characters.value.length) {
      const active = characters.value.find((c) => c.is_active)
      activeChar.value = active?.id ?? characters.value[0].id
      await refreshActiveTab()
    }
  } catch (e: any) {
    error.value = e.message
  }
}

async function onCharChange() {
  summaryOffset.value = 0
  await refreshActiveTab()
}

async function loadFacts() {
  if (!activeChar.value || !activeFactCategory.value) return
  try {
    facts.value = await api.listFacts(activeChar.value, activeFactCategory.value)
  } catch (e: any) {
    error.value = e.message
  }
}

async function loadSummaries() {
  if (!activeChar.value) return
  loadingSummaries.value = true
  try {
    summaryData.value = await api.listSummaries(activeChar.value, summaryOffset.value, summaryLimit)
  } catch {
    // ignore
  } finally {
    loadingSummaries.value = false
  }
}

async function refreshActiveTab() {
  if (activeTab.value === 'summaries') {
    await loadSummaries()
    return
  }
  await loadFacts()
}

watch(activeTab, (t) => {
  if (t === 'summaries') {
    void loadSummaries()
    return
  }
  void loadFacts()
})

function categoryLabel(category: string | null | undefined): string {
  const found = factCategories.find((option) => option.key === category)
  return found?.label ?? '长期事实'
}

function categoryClass(category: string): string {
  return `tag-${category}`
}

function importanceLabel(importance: number): string {
  if (importance >= 0.8) return '核心'
  if (importance >= 0.5) return '普通'
  return '弱'
}

function importanceClass(importance: number): string {
  if (importance >= 0.8) return 'importance-high'
  if (importance >= 0.5) return 'importance-medium'
  return 'importance-low'
}

function startEditImportance(fact: FactItem) {
  editingImportance.value = fact.key
  editImportanceValue.value = fact.importance
}

async function saveImportance(key: string) {
  try {
    await api.updateFactImportance(activeChar.value, key, editImportanceValue.value)
    editingImportance.value = null
    showToast('重要性已更新', 'success')
    await loadFacts()
  } catch (e: any) {
    showToast(`失败: ${e.message}`, 'error')
  }
}

function startEditFact(fact: FactItem) {
  editingFact.value = fact.key
  editFactValue.value = fact.value
  editFactCategory.value = fact.category
}

async function saveFact(key: string) {
  try {
    await api.updateFact(activeChar.value, key, editFactValue.value, editFactCategory.value)
    editingFact.value = null
    showToast('已保存', 'success')
    await loadFacts()
  } catch (e: any) {
    showToast(`失败: ${e.message}`, 'error')
  }
}

async function addFact() {
  if (!newKey.value) return
  try {
    await api.createFact(activeChar.value, newKey.value, newValue.value, newCategory.value)
    showToast('已添加', 'success')
    showAddFact.value = false
    newKey.value = ''
    newValue.value = ''
    newCategory.value = activeFactCategory.value ?? 'fact'
    await loadFacts()
  } catch (e: any) {
    showToast(`失败: ${e.message}`, 'error')
  }
}

async function deleteFact(key: string) {
  if (!confirm(`确认删除事实 "${key}"？`)) return
  try {
    await api.deleteFact(activeChar.value, key)
    showToast('已删除', 'success')
    await loadFacts()
  } catch (e: any) {
    showToast(`失败: ${e.message}`, 'error')
  }
}

async function resolveConflict(key: string, adoptNew: boolean) {
  try {
    await api.resolveConflict(activeChar.value, key, adoptNew)
    showToast(adoptNew ? '已采用新值' : '已保留旧值', 'success')
    await loadFacts()
  } catch (e: any) {
    showToast(`失败: ${e.message}`, 'error')
  }
}

async function deleteSummary(index: number) {
  if (!confirm('确认删除此条摘要？此操作不可恢复。')) return
  try {
    await api.deleteSummary(activeChar.value, index)
    showToast('已删除', 'success')
    await loadSummaries()
  } catch (e: any) {
    showToast(`失败: ${e.message}`, 'error')
  }
}

function startEditSummary(index: number, summary: string) {
  editingSummaryIndex.value = index
  editSummaryText.value = summary
}

function cancelSummaryEdit() {
  editingSummaryIndex.value = null
  editSummaryText.value = ''
}

async function saveSummary(index: number) {
  try {
    await api.updateSummary(activeChar.value, index, editSummaryText.value)
    showToast('摘要已保存', 'success')
    cancelSummaryEdit()
    await loadSummaries()
  } catch (e: any) {
    showToast(`失败: ${e.message}`, 'error')
  }
}

async function exportMemories() {
  try {
    const data = await api.exportMemories(activeChar.value)
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${activeChar.value}-memories-${new Date().toISOString().replace(/[:.]/g, '-')}.json`
    a.click()
    URL.revokeObjectURL(url)
  } catch (e: any) {
    showToast(`导出失败: ${e.message}`, 'error')
  }
}

async function confirmClear() {
  const input = prompt(`此操作将清空 ${clearKind.value}。确认请输入 "DELETE"`)
  if (input !== 'DELETE') return
  try {
    await api.clearMemories(activeChar.value, clearKind.value)
    showToast('已清空', 'success')
    await refreshActiveTab()
  } catch (e: any) {
    showToast(`失败: ${e.message}`, 'error')
  }
}

onMounted(async () => {
  await loadChars()
  newCategory.value = activeFactCategory.value ?? 'fact'
})
</script>

<style scoped>
.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.search-input {
  min-width: 260px;
  flex: 1;
}

.tabs {
  display: flex;
  gap: 2px;
  border-bottom: 2px solid #e5e7eb;
  flex-wrap: wrap;
}

.tab-btn {
  padding: 8px 16px;
  font-size: 13px;
  border: none;
  background: none;
  color: #6b7280;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
  transition: all 0.15s;
}

.tab-btn--active {
  color: #3b82f6;
  border-bottom-color: #3b82f6;
  font-weight: 500;
}

.add-form {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 12px;
  padding: 10px;
  background: #f9fafb;
  border-radius: 6px;
}

.conflict-row {
  background: #fffbeb;
  font-size: 12px;
  color: #92400e;
}

.importance-pill {
  display: inline-block;
  padding: 1px 7px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 500;
}

.importance-high {
  background: #fee2e2;
  color: #b91c1c;
}

.importance-medium {
  background: #e0f2fe;
  color: #0369a1;
}

.importance-low {
  background: #f3f4f6;
  color: #6b7280;
}

.summary-card {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.summary-meta {
  font-size: 11px;
  color: #9ca3af;
  white-space: nowrap;
  margin-top: 2px;
}

.summary-text {
  flex: 1;
  font-size: 13px;
  color: #374151;
  line-height: 1.5;
}

.danger-controls {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.tag-fact { background: #f3f4f6; color: #374151; }
.tag-preference { background: #dbeafe; color: #1d4ed8; }
.tag-boundary { background: #fee2e2; color: #b91c1c; }
.tag-event { background: #ede9fe; color: #6d28d9; }
</style>
