import { computed, ref, shallowRef } from 'vue'

import { api } from '../api'

export interface RelationshipAdminResponse {
  character_id: string
  intimacy: number
  trust: number
  familiarity: number
  interaction_quality_recent: number
  preferred_addressing: string
  relationship_type: string
  boundaries_summary: string
  dependency_risk: number
  boundary_policy_summary: string
  updated_at: string
  change_reasons: string[]
}

export interface RelationshipUpdatePayload {
  relationship_type: string
  preferred_addressing: string
  boundaries_summary: string
}

interface CharacterSummary {
  id: string
  name: string
  is_active?: boolean
}

function defaultForm(): RelationshipUpdatePayload {
  return {
    relationship_type: 'friend',
    preferred_addressing: '',
    boundaries_summary: '',
  }
}

export function useRelationshipAdmin() {
  const characters = ref<CharacterSummary[]>([])
  const activeChar = shallowRef('')
  const relationship = ref<RelationshipAdminResponse | null>(null)
  const form = ref<RelationshipUpdatePayload>(defaultForm())
  const loading = shallowRef(false)
  const saving = shallowRef(false)
  const error = shallowRef('')

  const recentReasons = computed(() => relationship.value?.change_reasons ?? [])

  function syncForm(state: RelationshipAdminResponse | null): void {
    form.value = state
      ? {
          relationship_type: state.relationship_type,
          preferred_addressing: state.preferred_addressing,
          boundaries_summary: state.boundaries_summary,
        }
      : defaultForm()
  }

  async function loadCharacters(): Promise<void> {
    error.value = ''
    const result = await api.listCharacters()
    characters.value = result as CharacterSummary[]
    if (!characters.value.length) {
      activeChar.value = ''
      relationship.value = null
      syncForm(null)
      return
    }

    if (!activeChar.value || !characters.value.some((item) => item.id === activeChar.value)) {
      activeChar.value = characters.value.find((item) => item.is_active)?.id ?? characters.value[0].id
    }
    await loadRelationship(activeChar.value)
  }

  async function loadRelationship(characterId = activeChar.value): Promise<void> {
    if (!characterId) {
      relationship.value = null
      syncForm(null)
      return
    }

    loading.value = true
    error.value = ''
    try {
      relationship.value = await api.getRelationship(characterId) as RelationshipAdminResponse
      activeChar.value = characterId
      syncForm(relationship.value)
    } catch (err) {
      relationship.value = null
      syncForm(null)
      error.value = err instanceof Error ? err.message : '关系状态加载失败'
      throw err
    } finally {
      loading.value = false
    }
  }

  async function selectCharacter(characterId: string): Promise<void> {
    activeChar.value = characterId
    await loadRelationship(characterId)
  }

  async function saveProfile(): Promise<RelationshipAdminResponse> {
    if (!activeChar.value) {
      throw new Error('当前没有可用角色')
    }

    saving.value = true
    error.value = ''
    try {
      relationship.value = await api.updateRelationship(activeChar.value, form.value) as RelationshipAdminResponse
      syncForm(relationship.value)
      return relationship.value
    } catch (err) {
      error.value = err instanceof Error ? err.message : '关系状态保存失败'
      throw err
    } finally {
      saving.value = false
    }
  }

  async function resetRelationship(): Promise<RelationshipAdminResponse> {
    if (!activeChar.value) {
      throw new Error('当前没有可用角色')
    }

    saving.value = true
    error.value = ''
    try {
      relationship.value = await api.resetRelationship(activeChar.value) as RelationshipAdminResponse
      syncForm(relationship.value)
      return relationship.value
    } catch (err) {
      error.value = err instanceof Error ? err.message : '关系状态重置失败'
      throw err
    } finally {
      saving.value = false
    }
  }

  return {
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
  }
}
