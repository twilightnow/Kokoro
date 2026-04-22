/**
 * useWindowPosition — ウィンドウ位置永続化 composable。
 *
 * localStorage にウィンドウ位置を保存し、起動時に復元する。
 * ウィンドウ移動のたびに自動保存するトラッキングも提供する。
 */
import { invoke } from '@tauri-apps/api/core'
import { getCurrentWindow } from '@tauri-apps/api/window'
import { useUiStore } from '../stores/ui'

const STORAGE_KEY = 'kokoro-window-position'

interface WindowPos {
  x: number
  y: number
}

function isWindowPos(value: unknown): value is WindowPos {
  return (
    typeof value === 'object' &&
    value !== null &&
    typeof (value as Record<string, unknown>).x === 'number' &&
    typeof (value as Record<string, unknown>).y === 'number'
  )
}

export function useWindowPosition() {
  /** 現在位置を localStorage に保存する */
  async function savePosition(): Promise<void> {
    try {
      const pos = await invoke<[number, number]>('get_window_position')
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ x: pos[0], y: pos[1] }))
    } catch {
      // サイレントに無視
    }
  }

  /** 保存済み位置を復元する（なければ何もしない） */
  async function restorePosition(): Promise<void> {
    try {
      const raw = localStorage.getItem(STORAGE_KEY)
      if (!raw) return
      const pos: unknown = JSON.parse(raw)
      if (isWindowPos(pos)) {
        await invoke('set_window_position', { x: pos.x, y: pos.y })
      }
    } catch {
      // サイレントに無視
    }
  }

  /** ウィンドウ移動のたびに位置を自動保存するリスナーを登録する */
  async function startTracking(): Promise<void> {
    const win = getCurrentWindow()
    const uiStore = useUiStore()
    await win.onMoved((event) => {
      // スナップ中は off-screen 位置を保存しない
      if (uiStore.isSnapped) return
      const { x, y } = event.payload
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ x, y }))
    })
  }

  return { savePosition, restorePosition, startTracking }
}
