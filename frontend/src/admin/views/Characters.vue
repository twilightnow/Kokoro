<template>
  <div>
    <h1 class="page-title">角色管理</h1>

    <div v-if="error" class="banner-error">{{ error }}</div>

    <div class="char-layout">
      <div class="char-list card">
        <div class="char-list-header">
          <span class="card-title" style="margin-bottom:0">可用角色</span>
        </div>
        <div v-if="loading" class="loading">加载中…</div>
        <div v-else>
          <div
            v-for="char in characters"
            :key="char.id"
            class="char-row"
            :class="{ 'char-row--active': char.id === selectedId }"
            @click="selectChar(char)"
          >
            <div class="char-row-info">
              <div class="char-row-name">
                {{ char.name }}
                <span v-if="char.is_active" class="badge badge-green" style="margin-left:6px">激活中</span>
                <span v-if="char.is_default_startup" class="badge badge-blue" style="margin-left:6px">启动默认</span>
              </div>
              <div class="char-row-id">{{ char.id }} · v{{ char.version || '?' }}</div>
            </div>
            <div class="char-row-actions">
              <button
                v-if="!char.is_default_startup"
                class="btn btn-sm btn-secondary"
                @click.stop="setDefaultStartup(char.id)"
              >
                设为启动默认
              </button>
              <button
                v-if="!char.is_active"
                class="btn btn-sm btn-secondary"
                @click.stop="activateChar(char.id)"
              >
                切换到此
              </button>
            </div>
          </div>
        </div>
      </div>

      <div class="char-detail" v-if="selectedChar">
        <div class="card">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:14px">
            <div>
              <div style="font-size:17px; font-weight:600">{{ selectedChar.parsed?.name }}</div>
              <div style="font-size:11px; color:#6b7280; margin-top:2px">
                v{{ selectedChar.parsed?.version || '?' }} · schema {{ selectedChar.parsed?.schema_version || '1' }}
              </div>
            </div>
            <div style="display:flex; gap:8px">
              <button v-if="!editing" class="btn btn-secondary btn-sm" @click="startEdit">编辑</button>
              <template v-else>
                <button class="btn btn-primary btn-sm" @click="saveEdit" :disabled="saving">
                  {{ saving ? '保存中…' : '保存' }}
                </button>
                <button class="btn btn-secondary btn-sm" @click="cancelEdit">取消</button>
              </template>
            </div>
          </div>

          <div v-if="editing">
            <textarea v-model="editYaml" rows="30" style="font-family: monospace; font-size:12px;" />
          </div>
          <template v-else>
            <div class="detail-section">
              <div class="detail-section-title">展示配置</div>
              <div class="detail-kv">
                <div class="detail-k">模式</div>
                <div class="detail-v">{{ selectedChar.manifest?.display?.mode || 'placeholder' }}</div>
              </div>
              <div class="detail-kv">
                <div class="detail-k">解析结果</div>
                <div class="detail-v">
                  <span class="tag tag-blue">请求 {{ selectedChar.validation?.requested_mode || 'placeholder' }}</span>
                  <span class="tag tag-purple">实际 {{ selectedChar.validation?.resolved_mode || 'placeholder' }}</span>
                </div>
              </div>
              <template v-if="selectedChar.manifest?.display?.model3d">
                <div class="detail-kv">
                  <div class="detail-k">默认皮肤</div>
                  <div class="detail-v">{{ selectedChar.manifest.display.model3d.default_skin || '—' }}</div>
                </div>
                <div class="detail-kv">
                  <div class="detail-k">自动切换</div>
                  <div class="detail-v">{{ selectedChar.manifest.display.model3d.auto_switch?.enabled ? '开启' : '关闭' }}</div>
                </div>
                <div class="detail-kv">
                  <div class="detail-k">皮肤列表</div>
                  <div class="detail-v">
                    <span
                      v-for="(skin, skinId) in selectedChar.manifest.display.model3d.skins"
                      :key="skinId"
                      class="tag tag-purple"
                    >
                      {{ skin.label || skinId }}
                    </span>
                  </div>
                </div>
                <div class="detail-kv">
                  <div class="detail-k">情绪映射</div>
                  <div class="detail-v">
                    <span
                      v-for="(skinId, mood) in selectedChar.manifest.display.model3d.auto_switch?.mood_skins"
                      :key="`${mood}-${skinId}`"
                      class="tag tag-amber"
                    >
                      {{ mood }} → {{ skinId }}
                    </span>
                    <span
                      v-if="!Object.keys(selectedChar.manifest.display.model3d.auto_switch?.mood_skins || {}).length"
                      class="detail-empty"
                    >
                      无
                    </span>
                  </div>
                </div>
              </template>
              <template v-else-if="selectedChar.manifest?.display?.live2d">
                <div class="detail-kv">
                  <div class="detail-k">模型</div>
                  <div class="detail-v">{{ selectedChar.manifest.display.live2d.model || '—' }}</div>
                </div>
              </template>
              <template v-else-if="selectedChar.manifest?.display?.image">
                <div class="detail-kv">
                  <div class="detail-k">静态图</div>
                  <div class="detail-v">{{ selectedChar.manifest.display.image.file || '—' }}</div>
                </div>
              </template>
              <div v-if="selectedChar.validation?.warnings?.length" class="detail-alert detail-alert--warning">
                <div v-for="warning in selectedChar.validation.warnings" :key="warning">{{ warning }}</div>
              </div>
              <div v-if="selectedChar.validation?.errors?.length" class="detail-alert detail-alert--error">
                <div v-for="issue in selectedChar.validation.errors" :key="issue">{{ issue }}</div>
              </div>
              <details v-if="selectedChar.raw_manifest" class="manifest-raw">
                <summary>查看 manifest.yaml</summary>
                <textarea :value="selectedChar.raw_manifest" rows="14" readonly />
              </details>
            </div>

            <div class="detail-section">
              <div class="detail-section-title">人格核心</div>
              <div class="detail-kv">
                <div class="detail-k">核心恐惧</div>
                <div class="detail-v">{{ selectedChar.parsed?.personality?.core_fear || '—' }}</div>
              </div>
              <div class="detail-kv">
                <div class="detail-k">表层特质</div>
                <div class="detail-v">{{ selectedChar.parsed?.personality?.surface_trait || '—' }}</div>
              </div>
              <div class="detail-kv">
                <div class="detail-k">隐藏特质</div>
                <div class="detail-v">{{ selectedChar.parsed?.personality?.hidden_trait || '—' }}</div>
              </div>
            </div>

            <div class="detail-section">
              <div class="detail-section-title">行为规则</div>
              <div v-if="!selectedChar.parsed?.behavior_rules?.length" class="detail-empty">无</div>
              <div v-for="(rule, i) in selectedChar.parsed?.behavior_rules" :key="i" class="detail-rule">
                {{ i + 1 }}. {{ rule }}
              </div>
            </div>

            <div class="detail-section">
              <div class="detail-section-title">情绪触发词</div>
              <div v-for="(words, emotion) in selectedChar.parsed?.emotion_triggers" :key="emotion" class="detail-kv">
                <div class="detail-k">{{ emotion }}</div>
                <div class="detail-v">
                  <span v-for="w in words" :key="w" class="tag">{{ w }}</span>
                </div>
              </div>
            </div>

            <div class="detail-section">
              <div class="detail-section-title">禁用词</div>
              <div class="detail-v">
                <span v-for="w in selectedChar.parsed?.forbidden_words" :key="w" class="tag tag-red">{{ w }}</span>
                <span v-if="!selectedChar.parsed?.forbidden_words?.length" class="detail-empty">无</span>
              </div>
            </div>

            <div class="detail-section">
              <div class="detail-section-title">口头禅</div>
              <div class="detail-v">
                <span v-for="w in selectedChar.parsed?.verbal_habits" :key="w" class="tag tag-blue">{{ w }}</span>
                <span v-if="!selectedChar.parsed?.verbal_habits?.length" class="detail-empty">无</span>
              </div>
            </div>
          </template>
        </div>
      </div>

      <div v-else class="char-detail-empty">
        <div class="empty">选择左侧角色查看详情</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { inject, onMounted, ref } from 'vue'
import { api } from '../api'

const showToast = inject<(msg: string, type?: any) => void>('showToast', () => {})

const characters = ref<any[]>([])
const selectedId = ref<string | null>(null)
const selectedChar = ref<any>(null)
const loading = ref(false)
const error = ref('')
const editing = ref(false)
const editYaml = ref('')
const saving = ref(false)

async function load() {
  loading.value = true
  error.value = ''
  try {
    characters.value = await api.listCharacters()
  } catch (e: any) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

async function selectChar(char: any) {
  selectedId.value = char.id
  editing.value = false
  try {
    selectedChar.value = await api.getCharacter(char.id)
  } catch (e: any) {
    showToast(`加载失败: ${e.message}`, 'error')
  }
}

async function activateChar(id: string) {
  try {
    await api.reloadCharacter(id)
    showToast(`已切换到 ${id}`, 'success')
    await load()
    if (selectedId.value === id) {
      const char = characters.value.find((c) => c.id === id)
      if (char) await selectChar(char)
    }
  } catch (e: any) {
    showToast(`切换失败: ${e.message}`, 'error')
  }
}

async function setDefaultStartup(id: string) {
  try {
    await api.setDefaultStartupCharacter(id)
    showToast(`已将 ${id} 设为启动默认角色，重启 sidecar 后生效`, 'success')
    await load()
  } catch (e: any) {
    showToast(`设置默认角色失败: ${e.message}`, 'error')
  }
}

function startEdit() {
  editing.value = true
  editYaml.value = selectedChar.value?.raw_yaml ?? ''
}

function cancelEdit() {
  editing.value = false
}

async function saveEdit() {
  saving.value = true
  try {
    await api.updateCharacter(selectedId.value!, editYaml.value)
    showToast('已保存，需重新加载角色才能生效', 'success')
    editing.value = false
    selectedChar.value = await api.getCharacter(selectedId.value!)
  } catch (e: any) {
    showToast(`保存失败: ${e.message}`, 'error')
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.char-layout {
  display: grid;
  grid-template-columns: minmax(320px, 380px) minmax(0, 1fr);
  gap: 16px;
  align-items: start;
}

.char-list {
  height: fit-content;
  max-height: calc(100vh - 120px);
  overflow-y: auto;
  padding: 0;
}

.char-list-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid #e5e7eb;
}

.char-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 16px;
  border-bottom: 1px solid #f3f4f6;
  cursor: pointer;
  transition: background 0.1s;
}

.char-row:hover { background: #f9fafb; }
.char-row--active { background: #eff6ff; }

.char-row-info {
  min-width: 0;
  flex: 1;
}

.char-row-name {
  font-size: 13px;
  font-weight: 500;
  color: #1a1a1a;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}

.char-row-id {
  font-size: 11px;
  color: #9ca3af;
  margin-top: 2px;
}

.char-row-actions {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-shrink: 0;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.char-row-actions .btn {
  max-width: 100%;
}

.char-detail-empty {
  display: flex;
  align-items: center;
  justify-content: center;
}

.detail-section {
  margin-bottom: 18px;
}

.detail-section-title {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: #9ca3af;
  margin-bottom: 8px;
  padding-bottom: 4px;
  border-bottom: 1px solid #f3f4f6;
}

.detail-kv {
  display: flex;
  gap: 12px;
  margin-bottom: 6px;
  font-size: 13px;
}

.detail-k {
  width: 90px;
  flex-shrink: 0;
  color: #6b7280;
  font-size: 12px;
}

.detail-v {
  flex: 1;
  color: #1a1a1a;
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.detail-rule {
  font-size: 13px;
  color: #374151;
  margin-bottom: 4px;
  line-height: 1.5;
}

.detail-empty {
  font-size: 12px;
  color: #9ca3af;
}

.tag {
  display: inline-flex;
  padding: 2px 8px;
  background: #f3f4f6;
  color: #374151;
  border-radius: 100px;
  font-size: 11px;
}

.tag-red { background: #fee2e2; color: #b91c1c; }
.tag-blue { background: #dbeafe; color: #1d4ed8; }
.tag-purple { background: #ede9fe; color: #6d28d9; }
.tag-amber { background: #fef3c7; color: #92400e; }

.detail-alert {
  margin-top: 10px;
  padding: 10px 12px;
  border-radius: 8px;
  font-size: 12px;
  line-height: 1.5;
}

.detail-alert--warning {
  background: #fffbeb;
  color: #92400e;
}

.detail-alert--error {
  background: #fef2f2;
  color: #b91c1c;
}

.manifest-raw {
  margin-top: 12px;
}

.manifest-raw summary {
  cursor: pointer;
  font-size: 12px;
  color: #6b7280;
}

.manifest-raw textarea {
  width: 100%;
  margin-top: 10px;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 10px;
  font-family: monospace;
  font-size: 12px;
  background: #f9fafb;
}

@media (max-width: 1100px) {
  .char-layout {
    grid-template-columns: 1fr;
  }

  .char-list {
    max-height: none;
  }
}

@media (max-width: 720px) {
  .char-row {
    flex-direction: column;
    align-items: flex-start;
  }

  .char-row-actions {
    width: 100%;
    justify-content: flex-start;
  }

  .detail-kv {
    flex-direction: column;
    gap: 4px;
  }

  .detail-k {
    width: auto;
  }
}
</style>
