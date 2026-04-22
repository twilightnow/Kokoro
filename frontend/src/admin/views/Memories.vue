<template>
  <div>
    <h1 class="page-title">记忆浏览</h1>

    <!-- 角色选择 -->
    <div style="display:flex; align-items:center; gap:12px; margin-bottom:16px">
      <select v-model="activeChar" style="width:160px" @change="onCharChange">
        <option v-for="c in characters" :key="c.id" :value="c.id">{{ c.name }} ({{ c.id }})</option>
      </select>
    </div>

    <div v-if="error" class="banner-error">{{ error }}</div>

    <!-- Tabs -->
    <div class="tabs">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        class="tab-btn"
        :class="{ 'tab-btn--active': activeTab === tab.key }"
        @click="activeTab = tab.key"
      >{{ tab.label }}</button>
    </div>

    <!-- 长期事实 -->
    <div v-if="activeTab === 'facts'" class="card mt-4">
      <div style="display:flex; justify-content:space-between; margin-bottom:12px">
        <div class="card-title" style="margin:0">长期事实</div>
        <button class="btn btn-primary btn-sm" @click="showAddFact = true">+ 新增</button>
      </div>

      <!-- 新增表单 -->
      <div v-if="showAddFact" class="add-form">
        <input v-model="newKey" placeholder="Key（如 user_name）" style="width:140px" />
        <input v-model="newValue" placeholder="Value" style="flex:1" />
        <button class="btn btn-primary btn-sm" @click="addFact">确认</button>
        <button class="btn btn-secondary btn-sm" @click="showAddFact=false">取消</button>
      </div>

      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Key</th><th>Value</th><th>更新时间</th><th>状态</th><th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="!facts.length">
              <td colspan="5" class="empty">暂无事实记录</td>
            </tr>
            <template v-for="fact in facts" :key="fact.key">
              <tr>
                <td><code style="font-size:12px">{{ fact.key }}</code></td>
                <td>
                  <template v-if="editingFact === fact.key">
                    <input v-model="editFactValue" style="width:100%" />
                  </template>
                  <template v-else>{{ fact.value }}</template>
                </td>
                <td style="color:#9ca3af;font-size:12px">{{ fact.updated_at?.slice(0,10) }}</td>
                <td>
                  <span v-if="fact.pending_confirm" class="badge badge-yellow">⚠️ 待确认</span>
                  <span v-else class="badge badge-green">✅ 已确认</span>
                </td>
                <td>
                  <div style="display:flex; gap:4px">
                    <template v-if="editingFact === fact.key">
                      <button class="btn btn-primary btn-sm" @click="saveFact(fact.key)">保存</button>
                      <button class="btn btn-secondary btn-sm" @click="editingFact=null">取消</button>
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
                <td colspan="5" class="conflict-row">
                  旧值: <strong>{{ fact.value }}</strong>
                  → 新值: <strong>{{ fact.pending_value }}</strong>
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 摘要记忆 -->
    <div v-if="activeTab === 'summaries'" class="mt-4">
      <div v-if="loadingSummaries" class="loading">加载中…</div>
      <div v-else>
        <div v-if="!summaryData?.items?.length" class="empty">暂无摘要记录</div>
        <div v-for="item in summaryData?.items" :key="item.index" class="summary-card card mt-4">
          <div class="summary-meta">{{ item.created_at?.slice(0,10) }}</div>
          <div class="summary-text">{{ item.summary }}</div>
          <button class="btn btn-danger btn-sm" @click="deleteSummary(item.index)">删除</button>
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

    <!-- 危险操作 -->
    <div class="card mt-6" style="border-color:#fecaca">
      <div class="card-title" style="color:#b91c1c">危险操作</div>
      <button class="btn btn-danger" @click="confirmClear">清空此角色全部记忆</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, inject, onMounted, watch } from 'vue'
import { api } from '../api'

const showToast = inject<(msg: string, type?: any) => void>('showToast', () => {})

const characters = ref<any[]>([])
const activeChar = ref<string>('')
const activeTab = ref('facts')
const tabs = [
  { key: 'facts', label: '长期事实' },
  { key: 'summaries', label: '摘要记忆' },
]

const facts = ref<any[]>([])
const error = ref('')
const editingFact = ref<string | null>(null)
const editFactValue = ref('')
const showAddFact = ref(false)
const newKey = ref('')
const newValue = ref('')

const summaryData = ref<any>(null)
const summaryOffset = ref(0)
const summaryLimit = 20
const loadingSummaries = ref(false)

async function loadChars() {
  try {
    characters.value = await api.listCharacters()
    if (characters.value.length) {
      const active = characters.value.find((c) => c.is_active)
      activeChar.value = active?.id ?? characters.value[0].id
      await loadFacts()
    }
  } catch (e: any) {
    error.value = e.message
  }
}

async function onCharChange() {
  await loadFacts()
  summaryOffset.value = 0
  await loadSummaries()
}

async function loadFacts() {
  if (!activeChar.value) return
  try {
    facts.value = await api.listFacts(activeChar.value)
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

watch(activeTab, (t) => {
  if (t === 'summaries') loadSummaries()
})

function startEditFact(fact: any) {
  editingFact.value = fact.key
  editFactValue.value = fact.value
}

async function saveFact(key: string) {
  try {
    await api.updateFact(activeChar.value, key, editFactValue.value)
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
    await api.createFact(activeChar.value, newKey.value, newValue.value)
    showToast('已添加', 'success')
    showAddFact.value = false
    newKey.value = ''
    newValue.value = ''
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

async function confirmClear() {
  const input = prompt('此操作将清空该角色所有记忆文件。确认请输入 "DELETE"')
  if (input !== 'DELETE') return
  try {
    await api.clearMemories(activeChar.value)
    showToast('已清空', 'success')
    await loadFacts()
    await loadSummaries()
  } catch (e: any) {
    showToast(`失败: ${e.message}`, 'error')
  }
}

onMounted(loadChars)
</script>

<style scoped>
.tabs {
  display: flex;
  gap: 2px;
  border-bottom: 2px solid #e5e7eb;
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
</style>
