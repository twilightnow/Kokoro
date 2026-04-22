import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

type SnapEdge = 'left' | 'right' | 'bottom' | null

export const useUiStore = defineStore('ui', () => {
  const snapEdge = ref<SnapEdge>(null)
  const isSnapped = computed(() => snapEdge.value !== null)

  function setSnap(edge: 'left' | 'right' | 'bottom'): void {
    snapEdge.value = edge
  }

  function clearSnap(): void {
    snapEdge.value = null
  }

  return { snapEdge, isSnapped, setSnap, clearSnap }
})
