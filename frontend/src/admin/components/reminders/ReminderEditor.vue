<script setup lang="ts">
interface CharacterSummary {
  id: string
  name: string
  is_active?: boolean
}

interface ReminderDraft {
  title: string
  note: string
  dueAtLocal: string
  repeatRule: 'once' | 'daily' | 'weekly'
}

const props = defineProps<{
  activeChar: string
  characters: CharacterSummary[]
  loading: boolean
  saving: boolean
  isEditing: boolean
}>()

const model = defineModel<ReminderDraft>({ required: true })

const emit = defineEmits<{
  selectCharacter: [characterId: string]
  submit: []
  reset: []
  refresh: []
}>()

function onCharacterChange(event: Event): void {
  const target = event.target as HTMLSelectElement | null
  emit('selectCharacter', target?.value ?? '')
}
</script>

<template>
  <div class="card editor-card">
    <div class="card-header">
      <div>
        <div class="card-title">提醒编辑器</div>
        <div class="card-subtitle">v1 仅支持一次性、每日和每周三种本地提醒。</div>
      </div>
      <button class="btn btn-secondary btn-sm" :disabled="loading" @click="emit('refresh')">刷新</button>
    </div>

    <div class="form-grid">
      <label class="form-field">
        <span class="form-label">角色</span>
        <select class="form-control" :value="props.activeChar" @change="onCharacterChange">
          <option v-for="character in props.characters" :key="character.id" :value="character.id">
            {{ character.name }} ({{ character.id }})
          </option>
        </select>
      </label>

      <label class="form-field">
        <span class="form-label">重复规则</span>
        <select v-model="model.repeatRule" class="form-control">
          <option value="once">一次</option>
          <option value="daily">每天</option>
          <option value="weekly">每周</option>
        </select>
      </label>
    </div>

    <label class="form-label" for="reminder-title">提醒标题</label>
    <input
      id="reminder-title"
      v-model="model.title"
      class="form-control"
      maxlength="120"
      placeholder="例如：吃午饭 / 去倒水 / 做眼保健操"
    >

    <label class="form-label" for="reminder-due-at">提醒时间</label>
    <input id="reminder-due-at" v-model="model.dueAtLocal" class="form-control" type="datetime-local">

    <label class="form-label" for="reminder-note">备注</label>
    <textarea
      id="reminder-note"
      v-model="model.note"
      class="form-control form-textarea"
      maxlength="400"
      placeholder="可选。建议写成简短上下文，不写隐私长文本。"
    />

    <div class="form-actions">
      <button class="btn btn-primary" :disabled="props.saving" @click="emit('submit')">
        {{ props.saving ? '保存中…' : props.isEditing ? '保存修改' : '创建提醒' }}
      </button>
      <button class="btn btn-secondary" :disabled="props.saving" @click="emit('reset')">
        {{ props.isEditing ? '取消编辑' : '重置表单' }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.editor-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form-control {
  width: 100%;
  border: 1px solid #d1d5db;
  border-radius: 10px;
  background: #fff;
  color: #111827;
  padding: 10px 12px;
  font-size: 13px;
}

.form-textarea {
  min-height: 96px;
  resize: vertical;
}

.form-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

@media (max-width: 720px) {
  .form-grid {
    grid-template-columns: 1fr;
  }
}
</style>