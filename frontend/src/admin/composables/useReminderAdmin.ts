import { computed, ref, shallowRef } from 'vue'

import { api } from '../api'

export interface ReminderItem {
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

export interface ReminderDraft {
  title: string
  note: string
  dueAtLocal: string
  repeatRule: 'once' | 'daily' | 'weekly'
}

interface CharacterSummary {
  id: string
  name: string
  is_active?: boolean
}

function defaultDraft(): ReminderDraft {
  const defaultDate = new Date()
  defaultDate.setMinutes(defaultDate.getMinutes() + 30)

  return {
    title: '',
    note: '',
    dueAtLocal: toDateTimeLocal(defaultDate),
    repeatRule: 'once',
  }
}

function toDateTimeLocal(value: Date): string {
  const year = value.getFullYear()
  const month = `${value.getMonth() + 1}`.padStart(2, '0')
  const day = `${value.getDate()}`.padStart(2, '0')
  const hour = `${value.getHours()}`.padStart(2, '0')
  const minute = `${value.getMinutes()}`.padStart(2, '0')
  return `${year}-${month}-${day}T${hour}:${minute}`
}

export function useReminderAdmin() {
  const characters = ref<CharacterSummary[]>([])
  const activeChar = shallowRef('')
  const reminders = ref<ReminderItem[]>([])
  const draft = ref<ReminderDraft>(defaultDraft())
  const editingId = shallowRef<string | null>(null)
  const includeCompleted = shallowRef(true)
  const loading = shallowRef(false)
  const saving = shallowRef(false)
  const busyReminderId = shallowRef('')
  const error = shallowRef('')

  const pendingReminders = computed(() =>
    reminders.value.filter((item) => item.status !== 'completed'),
  )
  const completedReminders = computed(() =>
    reminders.value.filter((item) => item.status === 'completed'),
  )
  const isEditing = computed(() => editingId.value !== null)

  function resetDraft(): void {
    editingId.value = null
    draft.value = defaultDraft()
  }

  function beginEdit(reminder: ReminderItem): void {
    editingId.value = reminder.id
    draft.value = {
      title: reminder.title,
      note: reminder.note,
      dueAtLocal: reminder.due_at.slice(0, 16),
      repeatRule: reminder.repeat_rule,
    }
  }

  async function loadCharacters(): Promise<void> {
    error.value = ''
    const result = await api.listCharacters()
    characters.value = result as CharacterSummary[]
    if (!characters.value.length) {
      activeChar.value = ''
      reminders.value = []
      resetDraft()
      return
    }

    if (!activeChar.value || !characters.value.some((item) => item.id === activeChar.value)) {
      activeChar.value = characters.value.find((item) => item.is_active)?.id ?? characters.value[0].id
    }
    await loadReminders(activeChar.value)
  }

  async function loadReminders(characterId = activeChar.value): Promise<void> {
    if (!characterId) {
      reminders.value = []
      resetDraft()
      return
    }

    loading.value = true
    error.value = ''
    try {
      const response = await api.listReminders(includeCompleted.value)
      reminders.value = response.items as ReminderItem[]
      activeChar.value = characterId
    } catch (err) {
      reminders.value = []
      error.value = err instanceof Error ? err.message : '提醒列表加载失败'
      throw err
    } finally {
      loading.value = false
    }
  }

  async function selectCharacter(characterId: string): Promise<void> {
    activeChar.value = characterId
    await loadReminders(characterId)
  }

  async function submitDraft(): Promise<void> {
    if (!activeChar.value) {
      throw new Error('当前没有可用角色')
    }
    if (!draft.value.title.trim()) {
      throw new Error('提醒标题不能为空')
    }
    if (!draft.value.dueAtLocal) {
      throw new Error('请选择提醒时间')
    }

    saving.value = true
    error.value = ''
    try {
      const payload = {
        title: draft.value.title.trim(),
        note: draft.value.note.trim(),
        due_at: draft.value.dueAtLocal,
        repeat_rule: draft.value.repeatRule,
      }
      if (editingId.value) {
        await api.updateReminder(editingId.value, payload)
      } else {
        await api.createReminder(payload)
      }
      await loadReminders(activeChar.value)
      resetDraft()
    } catch (err) {
      error.value = err instanceof Error ? err.message : '提醒保存失败'
      throw err
    } finally {
      saving.value = false
    }
  }

  async function completeReminder(reminderId: string): Promise<void> {
    busyReminderId.value = reminderId
    error.value = ''
    try {
      await api.completeReminder(reminderId)
      await loadReminders(activeChar.value)
    } catch (err) {
      error.value = err instanceof Error ? err.message : '提醒完成失败'
      throw err
    } finally {
      busyReminderId.value = ''
    }
  }

  async function snoozeReminder(reminderId: string): Promise<void> {
    busyReminderId.value = reminderId
    error.value = ''
    try {
      const until = new Date()
      until.setMinutes(until.getMinutes() + 30)
      await api.snoozeReminder(reminderId, toDateTimeLocal(until))
      await loadReminders(activeChar.value)
    } catch (err) {
      error.value = err instanceof Error ? err.message : '提醒改期失败'
      throw err
    } finally {
      busyReminderId.value = ''
    }
  }

  async function deleteReminder(reminderId: string): Promise<void> {
    busyReminderId.value = reminderId
    error.value = ''
    try {
      await api.deleteReminder(reminderId)
      if (editingId.value === reminderId) {
        resetDraft()
      }
      await loadReminders(activeChar.value)
    } catch (err) {
      error.value = err instanceof Error ? err.message : '提醒删除失败'
      throw err
    } finally {
      busyReminderId.value = ''
    }
  }

  async function toggleIncludeCompleted(value: boolean): Promise<void> {
    includeCompleted.value = value
    await loadReminders(activeChar.value)
  }

  return {
    activeChar,
    busyReminderId,
    characters,
    completedReminders,
    draft,
    editingId,
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
  }
}