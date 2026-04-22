import { invoke } from '@tauri-apps/api/core'
import { getCurrentWindow } from '@tauri-apps/api/window'
import { useUiStore } from '../stores/ui'

const SNAP_THRESHOLD = 30
const SNAP_HIDE_PX = 40
const SNAP_HOVER_MS = 140

interface MonitorBounds {
  x: number
  y: number
  width: number
  height: number
}

interface WindowMetrics {
  width: number
  height: number
  monitor: MonitorBounds
}

type SnapEdge = 'left' | 'right' | 'bottom'

export function useEdgeSnap() {
  const uiStore = useUiStore()
  let isProgrammaticMove = false
  let snapTimer: ReturnType<typeof setTimeout> | null = null
  let pendingEdge: SnapEdge | null = null
  let pendingMonitorKey: string | null = null

  function clearPendingSnap(): void {
    if (snapTimer) {
      clearTimeout(snapTimer)
      snapTimer = null
    }
    pendingEdge = null
    pendingMonitorKey = null
  }

  async function getWindowMetrics(): Promise<WindowMetrics> {
    return invoke<WindowMetrics>('get_window_metrics')
  }

  function getMonitorKey(monitor: MonitorBounds): string {
    return `${monitor.x},${monitor.y},${monitor.width},${monitor.height}`
  }

  async function setup(): Promise<void> {
    const win = getCurrentWindow()
    await win.onMoved(async (event) => {
      if (isProgrammaticMove) {
        isProgrammaticMove = false
        return
      }

      const { x, y } = event.payload
      const metrics = await getWindowMetrics()
      const winW = metrics.width
      const winH = metrics.height
      const monitor = metrics.monitor
      const monitorLeft = monitor.x
      const monitorRight = monitor.x + monitor.width
      const monitorBottom = monitor.y + monitor.height
      const monitorKey = getMonitorKey(monitor)

      let edge: SnapEdge | null = null
      if (x + winW > monitorRight - SNAP_THRESHOLD) {
        edge = 'right'
      } else if (x < monitorLeft + SNAP_THRESHOLD) {
        edge = 'left'
      } else if (y + winH > monitorBottom - SNAP_THRESHOLD) {
        edge = 'bottom'
      } else {
        clearPendingSnap()
        if (uiStore.isSnapped) uiStore.clearSnap()
        return
      }

      if (pendingEdge === edge && pendingMonitorKey === monitorKey) {
        return
      }

      clearPendingSnap()
      pendingEdge = edge
      pendingMonitorKey = monitorKey
      snapTimer = setTimeout(async () => {
        try {
          const latestMetrics = await getWindowMetrics()
          const latestMonitor = latestMetrics.monitor
          if (getMonitorKey(latestMonitor) !== monitorKey || pendingEdge !== edge) return

          const [latestX, latestY] = await invoke<[number, number]>('get_window_position')
          const latestW = latestMetrics.width
          const latestH = latestMetrics.height
          const latestRight = latestMonitor.x + latestMonitor.width
          const latestBottom = latestMonitor.y + latestMonitor.height

          let targetX = latestX
          let targetY = latestY

          if (edge === 'right' && latestX + latestW > latestRight - SNAP_THRESHOLD) {
            targetX = latestRight - SNAP_HIDE_PX
          } else if (edge === 'left' && latestX < latestMonitor.x + SNAP_THRESHOLD) {
            targetX = latestMonitor.x + SNAP_HIDE_PX - latestW
          } else if (edge === 'bottom' && latestY + latestH > latestBottom - SNAP_THRESHOLD) {
            targetY = latestBottom - SNAP_HIDE_PX
          } else {
            return
          }

          uiStore.setSnap(edge)
          isProgrammaticMove = true
          await invoke('set_window_position', { x: targetX, y: targetY })
        } finally {
          clearPendingSnap()
        }
      }, SNAP_HOVER_MS)
    })
  }

  async function unsnap(): Promise<void> {
    if (!uiStore.isSnapped) return

    clearPendingSnap()
    const metrics = await getWindowMetrics()
    const winW = metrics.width
    const winH = metrics.height
    const monitor = metrics.monitor
    const monitorLeft = monitor.x
    const monitorTop = monitor.y
    const monitorRight = monitor.x + monitor.width
    const monitorBottom = monitor.y + monitor.height

    let x = 0
    let y = 0
    switch (uiStore.snapEdge) {
      case 'right':
        x = monitorRight - winW - 20
        y = Math.round(monitorTop + (monitor.height - winH) / 2)
        break
      case 'left':
        x = monitorLeft + 20
        y = Math.round(monitorTop + (monitor.height - winH) / 2)
        break
      case 'bottom':
        x = Math.round(monitorLeft + (monitor.width - winW) / 2)
        y = monitorBottom - winH - 20
        break
      default:
        uiStore.clearSnap()
        return
    }

    uiStore.clearSnap()
    await invoke('set_window_position', { x, y })
  }

  return { setup, unsnap }
}
