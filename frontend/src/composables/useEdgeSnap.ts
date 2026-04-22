/**
 * useEdgeSnap — ウィンドウ端スナップ composable。
 *
 * 職責：
 *   - ウィンドウ移動を監視し、画面端から SNAP_THRESHOLD 内に来たらスナップ
 *   - スナップ後は SNAP_HIDE_PX 分だけウィンドウを画面に残して隠す
 *   - unsnap() でフル表示に戻す
 */
import { invoke } from '@tauri-apps/api/core'
import { getCurrentWindow } from '@tauri-apps/api/window'
import { useUiStore } from '../stores/ui'

// ── 定数 ──────────────────────────────────────────────────────────────────────
const SNAP_THRESHOLD = 30  // 物理px：この距離以内で端スナップ発動
const SNAP_HIDE_PX = 40    // 物理px：スナップ後に残す幅

// ウィンドウサイズ（tauri.conf.json と揃える）
const WIN_W_CSS = 320
const WIN_H_CSS = 520

export function useEdgeSnap() {
  const uiStore = useUiStore()
  // プログラム移動によるフィードバックループを防ぐフラグ
  let isProgrammaticMove = false

  /** アプリ起動時に一度だけ呼ぶ */
  async function setup(): Promise<void> {
    const win = getCurrentWindow()
    await win.onMoved(async (event) => {
      // プログラム移動によるイベントはスキップ
      if (isProgrammaticMove) {
        isProgrammaticMove = false
        return
      }

      const { x, y } = event.payload
      const dpr = window.devicePixelRatio
      const physW = Math.round(window.screen.width * dpr)
      const physH = Math.round(window.screen.height * dpr)
      const winW = Math.round(WIN_W_CSS * dpr)
      const winH = Math.round(WIN_H_CSS * dpr)

      if (x + winW > physW - SNAP_THRESHOLD) {
        uiStore.setSnap('right')
        isProgrammaticMove = true
        await invoke('set_window_position', { x: physW - SNAP_HIDE_PX, y })
      } else if (x < SNAP_THRESHOLD) {
        uiStore.setSnap('left')
        isProgrammaticMove = true
        await invoke('set_window_position', { x: SNAP_HIDE_PX - winW, y })
      } else if (y + winH > physH - SNAP_THRESHOLD) {
        uiStore.setSnap('bottom')
        isProgrammaticMove = true
        await invoke('set_window_position', { x, y: physH - SNAP_HIDE_PX })
      } else {
        if (uiStore.isSnapped) uiStore.clearSnap()
      }
    })
  }

  /** マウスがウィンドウに入ったときに呼ぶ — スナップ解除してフル表示に戻す */
  async function unsnap(): Promise<void> {
    if (!uiStore.isSnapped) return
    const dpr = window.devicePixelRatio
    const physW = Math.round(window.screen.width * dpr)
    const physH = Math.round(window.screen.height * dpr)
    const winW = Math.round(WIN_W_CSS * dpr)
    const winH = Math.round(WIN_H_CSS * dpr)

    let x = 0
    let y = 0
    switch (uiStore.snapEdge) {
      case 'right':
        x = physW - winW - 20
        y = Math.round((physH - winH) / 2)
        break
      case 'left':
        x = 20
        y = Math.round((physH - winH) / 2)
        break
      case 'bottom':
        x = Math.round((physW - winW) / 2)
        y = physH - winH - 20
        break
      default:
        return
    }

    uiStore.clearSnap()
    await invoke('set_window_position', { x, y })
  }

  return { setup, unsnap }
}
