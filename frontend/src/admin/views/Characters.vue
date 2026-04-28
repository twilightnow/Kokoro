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
              <template v-if="!editMode">
                <button class="btn btn-secondary btn-sm" @click="startFormEdit">表单编辑</button>
                <button class="btn btn-secondary btn-sm" @click="startYamlEdit">YAML 编辑</button>
              </template>
              <template v-else>
                <button class="btn btn-primary btn-sm" @click="saveEdit" :disabled="saving">
                  {{ saving ? '保存中…' : '保存' }}
                </button>
                <button class="btn btn-secondary btn-sm" @click="cancelEdit">取消</button>
              </template>
            </div>
          </div>

          <!-- 表单编辑模式 -->
          <div v-if="editMode === 'form'" class="form-editor">
            <div class="form-tabs">
              <button
                v-for="tab in formTabs"
                :key="tab.id"
                class="form-tab-btn"
                :class="{ 'form-tab-btn--active': activeEditTab === tab.id }"
                @click="activeEditTab = tab.id"
              >{{ tab.label }}</button>
            </div>

            <!-- 身份 / 人格 -->
            <div v-if="activeEditTab === 'identity'" class="form-panel">
              <div class="form-row">
                <label>角色名称</label>
                <input v-model="editForm.name" type="text" class="form-input" />
              </div>
              <div class="form-row">
                <label>版本号</label>
                <input v-model="editForm.version" type="text" class="form-input" placeholder="1.0.0" />
              </div>
              <div class="form-row">
                <label>角色描述</label>
                <textarea v-model="editForm.identity_description" rows="4" class="form-input" placeholder="角色的核心人设描述…" />
              </div>
              <div class="form-row">
                <label>场景设定</label>
                <textarea v-model="editForm.identity_scenario" rows="3" class="form-input" placeholder="对话发生的背景场景…" />
              </div>
              <div class="form-row">
                <label>核心恐惧</label>
                <input v-model="editForm.personality_core_fear" type="text" class="form-input" placeholder="角色最深处的恐惧或驱动力" />
              </div>
              <div class="form-row">
                <label>表层特质</label>
                <input v-model="editForm.personality_surface_trait" type="text" class="form-input" placeholder="外部可见的性格特征" />
              </div>
              <div class="form-row">
                <label>隐藏特质</label>
                <input v-model="editForm.personality_hidden_trait" type="text" class="form-input" placeholder="平时不轻易展露的一面" />
              </div>
            </div>

            <!-- 行为 / 对话 -->
            <div v-if="activeEditTab === 'behavior'" class="form-panel">
              <div class="form-row">
                <label>开场白</label>
                <textarea v-model="editForm.dialogue_first_message" rows="3" class="form-input" placeholder="角色主动发出的第一句话…" />
              </div>
              <div class="form-row">
                <label>后置指令</label>
                <textarea v-model="editForm.dialogue_post_history_instructions" rows="2" class="form-input" placeholder="放在历史消息之后的补充指令…" />
              </div>
              <div class="form-row">
                <label>
                  对话示例
                  <span class="form-hint">每行一条</span>
                </label>
                <textarea v-model="editForm.dialogue_examples_text" rows="5" class="form-input form-mono" placeholder="示例对话，每行一条…" />
              </div>
              <div class="form-row">
                <label>
                  行为规则
                  <span class="form-hint">每行一条</span>
                </label>
                <textarea v-model="editForm.behavior_rules_text" rows="5" class="form-input form-mono" placeholder="角色行为准则，每行一条…" />
              </div>
              <div class="form-row">
                <label>
                  口头禅
                  <span class="form-hint">每行一个</span>
                </label>
                <textarea v-model="editForm.verbal_habits_text" rows="3" class="form-input form-mono" placeholder="口头禅或习惯用语，每行一个…" />
              </div>
              <div class="form-row">
                <label>
                  禁用词
                  <span class="form-hint">每行一个</span>
                </label>
                <textarea v-model="editForm.forbidden_words_text" rows="3" class="form-input form-mono" placeholder="绝对禁止出现在回复中的词，每行一个…" />
              </div>
            </div>

            <!-- 模块 / 记忆 / 主动 -->
            <div v-if="activeEditTab === 'modules'" class="form-panel">
              <div class="form-section-title">LLM 模块</div>
              <div class="form-row">
                <label>Provider</label>
                <input v-model="editForm.llm_provider" type="text" class="form-input" placeholder="留空沿用全局配置（如 openai）" />
              </div>
              <div class="form-row">
                <label>Model</label>
                <input v-model="editForm.llm_model" type="text" class="form-input" placeholder="留空沿用全局配置（如 gpt-4o）" />
              </div>

              <div class="form-section-title" style="margin-top:16px">TTS 模块</div>
              <div class="form-row">
                <label>Provider</label>
                <input v-model="editForm.tts_provider" type="text" class="form-input" placeholder="留空沿用全局配置（如 edge）" />
              </div>
              <div class="form-row">
                <label>Voice</label>
                <input v-model="editForm.tts_voice" type="text" class="form-input" placeholder="如 zh-CN-XiaoyiNeural" />
              </div>

              <div class="form-section-title" style="margin-top:16px">Display 模块</div>
              <div class="form-row">
                <label>展示模式</label>
                <select v-model="editForm.display_mode" class="form-input form-select">
                  <option value="">沿用全局配置</option>
                  <option value="live2d">live2d</option>
                  <option value="model3d">model3d</option>
                  <option value="image">image</option>
                  <option value="placeholder">placeholder</option>
                </select>
              </div>

              <div class="form-section-title" style="margin-top:16px">记忆策略</div>
              <div class="form-row">
                <label>提取策略</label>
                <select v-model="editForm.memory_extraction_policy" class="form-input form-select">
                  <option value="">默认（保守）</option>
                  <option value="conservative">conservative（触发词触发）</option>
                  <option value="aggressive">aggressive（每轮都提取）</option>
                </select>
              </div>
              <div class="form-row">
                <label>召回风格</label>
                <select v-model="editForm.memory_recall_style" class="form-input form-select">
                  <option value="">默认（结构化）</option>
                  <option value="structured">structured（分类列表）</option>
                  <option value="narrative">narrative（自然语言叙述）</option>
                  <option value="minimal">minimal（仅边界和偏好）</option>
                </select>
              </div>

              <div class="form-section-title" style="margin-top:16px">主动风格</div>
              <div class="form-row">
                <label>闲置过久</label>
                <input v-model="editForm.proactive_idle" type="text" class="form-input" placeholder="用户长时间未互动时的主动话术" />
              </div>
              <div class="form-row">
                <label>深夜工作</label>
                <input v-model="editForm.proactive_working_late" type="text" class="form-input" placeholder="用户深夜还在工作时的关心话术" />
              </div>
              <div class="form-row">
                <label>游戏中</label>
                <input v-model="editForm.proactive_gaming" type="text" class="form-input" placeholder="用户正在游戏时的互动话术" />
              </div>
            </div>
          </div>

          <!-- YAML 编辑模式 -->
          <div v-else-if="editMode === 'yaml'">
            <textarea v-model="editYaml" rows="30" style="font-family: monospace; font-size:12px;width:100%;box-sizing:border-box" />
          </div>

          <!-- 只读展示模式 -->
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
              <div class="detail-section-title">身份设定</div>
              <div class="detail-kv">
                <div class="detail-k">角色描述</div>
                <div class="detail-v">{{ selectedChar.parsed?.identity?.description || '—' }}</div>
              </div>
              <div class="detail-kv">
                <div class="detail-k">场景</div>
                <div class="detail-v">{{ selectedChar.parsed?.identity?.scenario || '—' }}</div>
              </div>
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
              <div class="detail-section-title">对话设定</div>
              <div class="detail-kv">
                <div class="detail-k">开场白</div>
                <div class="detail-v">{{ selectedChar.parsed?.dialogue?.first_message || '—' }}</div>
              </div>
              <div class="detail-kv">
                <div class="detail-k">示例</div>
                <div class="detail-v detail-v--column">
                  <div v-for="(example, i) in dialogueExamples(selectedChar)" :key="`example-${i}`" class="detail-rule">{{ example }}</div>
                  <span v-if="!dialogueExamples(selectedChar).length" class="detail-empty">无</span>
                </div>
              </div>
              <div class="detail-kv">
                <div class="detail-k">后置指令</div>
                <div class="detail-v">{{ selectedChar.parsed?.dialogue?.post_history_instructions || '—' }}</div>
              </div>
            </div>

            <div class="detail-section">
              <div class="detail-section-title">模块绑定</div>
              <div class="detail-kv">
                <div class="detail-k">LLM</div>
                <div class="detail-v">{{ roleCardLlmLabel(selectedChar) }}</div>
              </div>
              <div class="detail-kv">
                <div class="detail-k">TTS</div>
                <div class="detail-v">{{ roleCardTtsLabel(selectedChar) }}</div>
              </div>
              <div class="detail-kv">
                <div class="detail-k">Display</div>
                <div class="detail-v">{{ roleCardDisplayMode(selectedChar) }}</div>
              </div>
            </div>

            <div class="detail-section">
              <div class="detail-section-title">记忆策略</div>
              <div class="detail-kv">
                <div class="detail-k">提取</div>
                <div class="detail-v">{{ selectedChar.parsed?.memory?.extraction_policy || '—' }}</div>
              </div>
              <div class="detail-kv">
                <div class="detail-k">召回</div>
                <div class="detail-v">{{ selectedChar.parsed?.memory?.recall_style || '—' }}</div>
              </div>
            </div>

            <div class="detail-section">
              <div class="detail-section-title">主动风格</div>
              <div class="detail-kv">
                <div class="detail-k">闲置过久</div>
                <div class="detail-v">{{ proactiveStyle(selectedChar).idle_too_long || '—' }}</div>
              </div>
              <div class="detail-kv">
                <div class="detail-k">深夜工作</div>
                <div class="detail-v">{{ proactiveStyle(selectedChar).user_working_late || '—' }}</div>
              </div>
              <div class="detail-kv">
                <div class="detail-k">游戏中</div>
                <div class="detail-v">{{ proactiveStyle(selectedChar).user_gaming || '—' }}</div>
              </div>
            </div>

            <div class="detail-section">
              <div class="detail-section-title">行为规则</div>
              <div v-if="!behaviorRules(selectedChar).length" class="detail-empty">无</div>
              <div v-for="(rule, i) in behaviorRules(selectedChar)" :key="i" class="detail-rule">
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
                <span v-for="w in forbiddenWords(selectedChar)" :key="w" class="tag tag-red">{{ w }}</span>
                <span v-if="!forbiddenWords(selectedChar).length" class="detail-empty">无</span>
              </div>
            </div>

            <div class="detail-section">
              <div class="detail-section-title">口头禅</div>
              <div class="detail-v">
                <span v-for="w in verbalHabits(selectedChar)" :key="w" class="tag tag-blue">{{ w }}</span>
                <span v-if="!verbalHabits(selectedChar).length" class="detail-empty">无</span>
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
/** null = 只读，'form' = 表单编辑，'yaml' = YAML 编辑 */
const editMode = ref<null | 'form' | 'yaml'>(null)
const editYaml = ref('')
const saving = ref(false)

const formTabs = [
  { id: 'identity', label: '身份 / 人格' },
  { id: 'behavior', label: '行为 / 对话' },
  { id: 'modules',  label: '模块 / 记忆' },
]
const activeEditTab = ref<string>('identity')

interface EditForm {
  name: string
  version: string
  identity_description: string
  identity_scenario: string
  personality_core_fear: string
  personality_surface_trait: string
  personality_hidden_trait: string
  dialogue_first_message: string
  dialogue_post_history_instructions: string
  dialogue_examples_text: string
  behavior_rules_text: string
  verbal_habits_text: string
  forbidden_words_text: string
  llm_provider: string
  llm_model: string
  tts_provider: string
  tts_voice: string
  display_mode: string
  memory_extraction_policy: string
  memory_recall_style: string
  proactive_idle: string
  proactive_working_late: string
  proactive_gaming: string
}

const editForm = ref<EditForm>({
  name: '', version: '',
  identity_description: '', identity_scenario: '',
  personality_core_fear: '', personality_surface_trait: '', personality_hidden_trait: '',
  dialogue_first_message: '', dialogue_post_history_instructions: '',
  dialogue_examples_text: '', behavior_rules_text: '', verbal_habits_text: '', forbidden_words_text: '',
  llm_provider: '', llm_model: '', tts_provider: '', tts_voice: '', display_mode: '',
  memory_extraction_policy: '', memory_recall_style: '',
  proactive_idle: '', proactive_working_late: '', proactive_gaming: '',
})

function roleCardDisplayMode(char: any): string {
  return char?.parsed?.modules?.display?.mode || char?.manifest?.display?.mode || 'placeholder'
}

function roleCardLlmLabel(char: any): string {
  const provider = char?.parsed?.modules?.llm?.provider || ''
  const model = char?.parsed?.modules?.llm?.model || ''
  if (!provider && !model) return '沿用全局配置'
  return [provider, model].filter(Boolean).join(' / ')
}

function roleCardTtsLabel(char: any): string {
  const provider = char?.parsed?.modules?.tts?.provider || ''
  const voice = char?.parsed?.modules?.tts?.voice || ''
  if (!provider && !voice) return '沿用全局配置'
  return [provider, voice].filter(Boolean).join(' / ')
}

function behaviorRules(char: any): string[] {
  return char?.parsed?.behavior?.rules || char?.parsed?.behavior_rules || []
}

function forbiddenWords(char: any): string[] {
  return char?.parsed?.behavior?.forbidden_words || char?.parsed?.forbidden_words || []
}

function verbalHabits(char: any): string[] {
  return char?.parsed?.behavior?.verbal_habits || char?.parsed?.verbal_habits || []
}

function dialogueExamples(char: any): string[] {
  return char?.parsed?.dialogue?.examples || []
}

function proactiveStyle(char: any): { idle_too_long?: string; user_working_late?: string; user_gaming?: string } {
  return char?.parsed?.proactive?.style || char?.parsed?.proactive_style || {}
}

// ── YAML builder ──────────────────────────────────────────────────────────────

function yamlStr(value: string): string {
  if (!value) return "''"
  if (/[:#\n|>{}\[\],&*!?@`%"']/.test(value) || value.trimStart() !== value || value.trimEnd() !== value) {
    return '"' + value.replace(/\\/g, '\\\\').replace(/"/g, '\\"').replace(/\n/g, '\\n') + '"'
  }
  return value
}

function yamlList(text: string, indent: string): string {
  const items = text.split('\n').map((s) => s.trim()).filter(Boolean)
  if (!items.length) return '[]\n'
  // Items must be indented MORE than the key to be valid YAML block sequences.
  const itemIndent = indent + '  '
  return '\n' + items.map((item) => `${itemIndent}- ${yamlStr(item)}`).join('\n') + '\n'
}

function yamlBlock(value: string, indent: string): string {
  if (!value) return "''\n"
  if (!value.includes('\n')) return yamlStr(value) + '\n'
  return '|-\n' + value.split('\n').map((line) => `${indent}  ${line}`).join('\n') + '\n'
}

function extractPreservedBlocks(rawYaml: string): string {
  const topLevelKeys = ['emotion_triggers', 'mood_expressions', 'emotion_profiles']
  const lines = rawYaml.split('\n')
  const result: string[] = []
  let inBlock = false

  for (const line of lines) {
    const topMatch = line.match(/^([a-zA-Z_][a-zA-Z0-9_]*):/)
    if (topMatch) {
      inBlock = topLevelKeys.includes(topMatch[1])
    }
    if (inBlock) result.push(line)
  }
  return result.join('\n').trimEnd()
}

function formToYaml(form: EditForm, baseRawYaml: string): string {
  const preserved = extractPreservedBlocks(baseRawYaml)
  const lines: string[] = []
  lines.push(`name: ${yamlStr(form.name)}`)
  lines.push(`version: ${yamlStr(form.version)}`)
  lines.push(`schema_version: 2`)
  lines.push(``)
  lines.push(`identity:`)
  lines.push(`  description: ${yamlBlock(form.identity_description, '  ')}`)
  lines.push(`  scenario: ${yamlBlock(form.identity_scenario, '  ')}`)
  lines.push(``)
  lines.push(`personality:`)
  lines.push(`  core_fear: ${yamlStr(form.personality_core_fear)}`)
  lines.push(`  surface_trait: ${yamlStr(form.personality_surface_trait)}`)
  lines.push(`  hidden_trait: ${yamlStr(form.personality_hidden_trait)}`)
  lines.push(``)
  lines.push(`behavior:`)
  lines.push(`  rules: ${yamlList(form.behavior_rules_text, '  ')}`)
  lines.push(`  verbal_habits: ${yamlList(form.verbal_habits_text, '  ')}`)
  lines.push(`  forbidden_words: ${yamlList(form.forbidden_words_text, '  ')}`)
  lines.push(``)
  lines.push(`dialogue:`)
  lines.push(`  first_message: ${yamlBlock(form.dialogue_first_message, '  ')}`)
  lines.push(`  post_history_instructions: ${yamlBlock(form.dialogue_post_history_instructions, '  ')}`)
  lines.push(`  examples: ${yamlList(form.dialogue_examples_text, '  ')}`)
  lines.push(``)
  lines.push(`modules:`)
  lines.push(`  llm:`)
  lines.push(`    provider: ${yamlStr(form.llm_provider)}`)
  lines.push(`    model: ${yamlStr(form.llm_model)}`)
  lines.push(`  tts:`)
  lines.push(`    provider: ${yamlStr(form.tts_provider)}`)
  lines.push(`    voice: ${yamlStr(form.tts_voice)}`)
  lines.push(`  display:`)
  lines.push(`    mode: ${yamlStr(form.display_mode)}`)
  lines.push(``)
  lines.push(`memory:`)
  lines.push(`  extraction_policy: ${yamlStr(form.memory_extraction_policy)}`)
  lines.push(`  recall_style: ${yamlStr(form.memory_recall_style)}`)
  lines.push(``)
  lines.push(`proactive:`)
  lines.push(`  style:`)
  lines.push(`    idle_too_long: ${yamlStr(form.proactive_idle)}`)
  lines.push(`    user_working_late: ${yamlStr(form.proactive_working_late)}`)
  lines.push(`    user_gaming: ${yamlStr(form.proactive_gaming)}`)
  if (preserved) {
    lines.push(``)
    lines.push(preserved)
  }
  return lines.join('\n') + '\n'
}

function initFormFromChar(char: any): void {
  const p = char?.parsed || {}
  editForm.value = {
    name: p.name || '',
    version: p.version || '',
    identity_description: p.identity?.description || '',
    identity_scenario: p.identity?.scenario || '',
    personality_core_fear: p.personality?.core_fear || '',
    personality_surface_trait: p.personality?.surface_trait || '',
    personality_hidden_trait: p.personality?.hidden_trait || '',
    dialogue_first_message: p.dialogue?.first_message || '',
    dialogue_post_history_instructions: p.dialogue?.post_history_instructions || '',
    dialogue_examples_text: (p.dialogue?.examples || []).join('\n'),
    behavior_rules_text: (p.behavior?.rules || p.behavior_rules || []).join('\n'),
    verbal_habits_text: (p.behavior?.verbal_habits || p.verbal_habits || []).join('\n'),
    forbidden_words_text: (p.behavior?.forbidden_words || p.forbidden_words || []).join('\n'),
    llm_provider: p.modules?.llm?.provider || '',
    llm_model: p.modules?.llm?.model || '',
    tts_provider: p.modules?.tts?.provider || '',
    tts_voice: p.modules?.tts?.voice || '',
    display_mode: p.modules?.display?.mode || '',
    memory_extraction_policy: p.memory?.extraction_policy || '',
    memory_recall_style: p.memory?.recall_style || '',
    proactive_idle: (p.proactive?.style || p.proactive_style || {}).idle_too_long || '',
    proactive_working_late: (p.proactive?.style || p.proactive_style || {}).user_working_late || '',
    proactive_gaming: (p.proactive?.style || p.proactive_style || {}).user_gaming || '',
  }
}

// ── Action handlers ────────────────────────────────────────────────────────────

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
  editMode.value = null
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

function startFormEdit() {
  initFormFromChar(selectedChar.value)
  activeEditTab.value = 'identity'
  editMode.value = 'form'
}

function startYamlEdit() {
  editYaml.value = selectedChar.value?.raw_yaml ?? ''
  editMode.value = 'yaml'
}

function cancelEdit() {
  editMode.value = null
}

async function saveEdit() {
  saving.value = true
  try {
    const yaml = editMode.value === 'form'
      ? formToYaml(editForm.value, selectedChar.value?.raw_yaml ?? '')
      : editYaml.value
    await api.updateCharacter(selectedId.value!, yaml)
    showToast('已保存，需重新加载角色才能生效', 'success')
    editMode.value = null
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

.detail-v--column {
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
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

/* ── Form editor ──────────────────────────────────────────────────────────── */
.form-editor {
  margin-top: 4px;
}

.form-tabs {
  display: flex;
  gap: 4px;
  margin-bottom: 16px;
  border-bottom: 1px solid #e5e7eb;
  padding-bottom: 0;
}

.form-tab-btn {
  padding: 6px 14px;
  border: none;
  background: none;
  font-size: 13px;
  color: #6b7280;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
  transition: color 0.15s, border-color 0.15s;
}
.form-tab-btn:hover { color: #374151; }
.form-tab-btn--active { color: #2563eb; border-bottom-color: #2563eb; font-weight: 500; }

.form-panel {
  padding-top: 4px;
}

.form-row {
  display: flex;
  flex-direction: column;
  gap: 5px;
  margin-bottom: 14px;
}

.form-row label {
  font-size: 12px;
  font-weight: 500;
  color: #374151;
  display: flex;
  align-items: center;
  gap: 6px;
}

.form-hint {
  font-size: 11px;
  color: #9ca3af;
  font-weight: 400;
}

.form-input {
  width: 100%;
  box-sizing: border-box;
  padding: 7px 10px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  font-size: 13px;
  color: #1a1a1a;
  background: #fff;
  transition: border-color 0.15s;
  resize: vertical;
}
.form-input:focus {
  outline: none;
  border-color: #93c5fd;
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.15);
}

.form-mono {
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
  font-size: 12px;
}

.form-select {
  appearance: none;
  -webkit-appearance: none;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%236b7280' stroke-width='2'%3E%3Cpolyline points='6 9 12 15 18 9'%3E%3C/polyline%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 10px center;
  padding-right: 30px;
  cursor: pointer;
}

.form-section-title {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: #9ca3af;
  margin-bottom: 10px;
  padding-bottom: 4px;
  border-bottom: 1px solid #f3f4f6;
}
</style>
