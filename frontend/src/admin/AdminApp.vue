<template>
  <div class="admin-layout" :class="{ 'theme-dark': darkTheme }">
    <!-- 侧边栏 -->
    <nav class="sidebar">
      <div class="sidebar-header">
        <span class="logo">🌸 Kokoro Admin</span>
        <button class="close-btn" title="关闭" @click="closeWindow">✕</button>
      </div>
      <div class="sidebar-section">
        <router-link
          v-for="item in mainNav"
          :key="item.path"
          :to="item.path"
          class="nav-item"
          active-class="nav-item--active"
        >
          <span class="nav-icon">{{ item.icon }}</span>
          <span>{{ item.label }}</span>
        </router-link>
      </div>
      <div class="sidebar-divider" />
      <div class="sidebar-section">
        <router-link
          v-for="item in devNav"
          :key="item.path"
          :to="item.path"
          class="nav-item"
          active-class="nav-item--active"
        >
          <span class="nav-icon">{{ item.icon }}</span>
          <span>{{ item.label }}</span>
        </router-link>
      </div>
      <div class="sidebar-footer">
        <div class="sidebar-controls">
          <button
            class="ctrl-btn"
            :class="{ 'ctrl-btn--active': passthroughLocked }"
            title="开关主窗口鼠标穿透"
            @click="togglePassthrough"
          >
            🖱 穿透{{ passthroughLocked ? ' ON' : ' OFF' }}
          </button>
          <button class="ctrl-btn" title="切换管理界面背景" @click="toggleTheme">
            {{ darkTheme ? '☀️ 浅色' : '🌙 深色' }}
          </button>
          <button
            class="ctrl-btn"
            :class="{ 'ctrl-btn--active': alwaysOnTop }"
            title="主窗口是否显示在最前面"
            @click="toggleAlwaysOnTop"
          >
            📌 主窗口置顶{{ alwaysOnTop ? ' ON' : ' OFF' }}
          </button>
        </div>
        <span class="sidebar-status" :class="online ? 'status--online' : 'status--offline'">
          {{ online ? '● 已连接' : '○ 离线' }}
        </span>
      </div>
    </nav>

    <!-- 主内容区 -->
    <main class="main-content">
      <router-view />
    </main>

    <!-- Toast 通知 -->
    <transition name="toast">
      <div v-if="toast.visible" class="toast" :class="`toast--${toast.type}`">
        {{ toast.message }}
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted, provide } from 'vue'
import { api } from './api'
import { errorDetails, reportClientLog } from '../shared/diagnostics'

/**
 * ウィンドウを閉じる。
 * Rust コマンド (close_admin_window) を第一手段とし、
 * 失敗した場合のみ JS ネイティブの window.close() にフォールバックする。
 */
async function closeWindow() {
  void reportClientLog({
    source: 'admin-window',
    event: 'admin-close-click',
    message: '管理界面关闭按钮被点击',
  })
  try {
    const { invoke } = await import('@tauri-apps/api/core')
    await invoke('close_admin_window')
    void reportClientLog({
      source: 'admin-window',
      event: 'admin-close-invoke-ok',
      message: 'close_admin_window invoke completed',
    })
  } catch (error) {
    void reportClientLog({
      source: 'admin-window',
      event: 'admin-close-invoke-error',
      level: 'error',
      message: 'close_admin_window invoke failed; falling back',
      details: errorDetails(error),
    })
    // core:window:allow-close 権限がある場合は JS API で閉じる
    try {
      const { getCurrentWindow } = await import('@tauri-apps/api/window')
      await getCurrentWindow().close()
    } catch (fallbackError) {
      void reportClientLog({
        source: 'admin-window',
        event: 'admin-close-fallback-error',
        level: 'error',
        message: 'fallback window close failed',
        details: errorDetails(fallbackError),
      })
      window.close()
    }
  }
}

const online = ref(false)
const passthroughLocked = ref(false)
const darkTheme = ref(false)
const alwaysOnTop = ref(false)

const PASSTHROUGH_KEY = 'kokoro-passthrough-lock'
const THEME_KEY = 'kokoro-admin-theme'
const MAIN_ALWAYS_ON_TOP_KEY = 'kokoro-main-always-on-top'

interface Toast {
  visible: boolean
  message: string
  type: 'info' | 'success' | 'error'
}
const toast = ref<Toast>({ visible: false, message: '', type: 'info' })
let toastTimer: ReturnType<typeof setTimeout> | null = null

function showToast(message: string, type: Toast['type'] = 'info') {
  if (toastTimer) clearTimeout(toastTimer)
  toast.value = { visible: true, message, type }
  toastTimer = setTimeout(() => {
    toast.value.visible = false
  }, 3000)
}

provide('showToast', showToast)

function togglePassthrough() {
  passthroughLocked.value = !passthroughLocked.value
  localStorage.setItem(PASSTHROUGH_KEY, passthroughLocked.value ? '1' : '0')
  showToast(
    passthroughLocked.value ? '主窗口穿透已开启' : '主窗口穿透已关闭',
    'info',
  )
}

function toggleTheme() {
  darkTheme.value = !darkTheme.value
  localStorage.setItem(THEME_KEY, darkTheme.value ? 'dark' : 'light')
}

async function toggleAlwaysOnTop() {
  alwaysOnTop.value = !alwaysOnTop.value
  localStorage.setItem(MAIN_ALWAYS_ON_TOP_KEY, alwaysOnTop.value ? '1' : '0')
  try {
    const { invoke } = await import('@tauri-apps/api/core')
    await invoke('set_main_always_on_top', { enabled: alwaysOnTop.value })
  } catch {
    // 非 Tauri 環境や権限不足の場合は無視
  }
  showToast(
    alwaysOnTop.value ? '已开启主窗口最前面显示' : '已关闭主窗口最前面显示',
    'info',
  )
}

watch(darkTheme, (dark) => {
  const bg = dark ? '#181825' : '#f5f5f5'
  document.body.style.background = bg
  document.documentElement.style.background = bg
  document.documentElement.style.colorScheme = dark ? 'dark' : 'light'
}, { immediate: false })

const mainNav = [
  { path: '/dashboard', icon: '📊', label: '状态总览' },
  { path: '/characters', icon: '👤', label: '角色管理' },
  { path: '/memories', icon: '🧠', label: '记忆浏览' },
  { path: '/logs', icon: '📄', label: '对话日志' },
  { path: '/stats', icon: '📈', label: '情绪统计' },
]

const devNav = [
  { path: '/settings', icon: '⚙️', label: '配置设置' },
  { path: '/debug', icon: '🔧', label: '调试工具' },
]

let pollTimer: ReturnType<typeof setInterval> | null = null

async function checkOnline() {
  try {
    await api.getHealth()
    online.value = true
  } catch {
    online.value = false
  }
}

onMounted(async () => {
  void reportClientLog({
    source: 'admin-window',
    event: 'admin-app-on-mounted',
    message: 'AdminApp onMounted started',
    details: {
      href: window.location.href,
      passthroughLocked: localStorage.getItem(PASSTHROUGH_KEY),
      darkTheme: localStorage.getItem(THEME_KEY),
      alwaysOnTop: localStorage.getItem(MAIN_ALWAYS_ON_TOP_KEY),
    },
  })
  passthroughLocked.value = localStorage.getItem(PASSTHROUGH_KEY) === '1'
  darkTheme.value = localStorage.getItem(THEME_KEY) === 'dark'
  alwaysOnTop.value = localStorage.getItem(MAIN_ALWAYS_ON_TOP_KEY) !== '0'

  // Apply theme to html/body immediately to prevent white flash on load
  const bg = darkTheme.value ? '#181825' : '#f5f5f5'
  document.body.style.background = bg
  document.documentElement.style.background = bg
  document.documentElement.style.colorScheme = darkTheme.value ? 'dark' : 'light'

  try {
    const { invoke } = await import('@tauri-apps/api/core')
    await invoke('set_main_always_on_top', { enabled: alwaysOnTop.value })
  } catch (error) {
    void reportClientLog({
      source: 'admin-window',
      event: 'main-window-restore-always-on-top-error',
      level: 'error',
      message: 'set_main_always_on_top restore failed',
      details: errorDetails(error),
    })
  }

  checkOnline()
  pollTimer = setInterval(checkOnline, 10000)
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
  if (toastTimer) clearTimeout(toastTimer)
})
</script>

<style>
* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

html,
body,
#admin-app {
  width: 100%;
  height: 100%;
  min-height: 100%;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
  font-size: 13px;
  color: #1a1a1a;
  background: #f5f5f5;
}

.admin-layout {
  display: flex;
  width: 100%;
  height: 100%;
  min-height: 100%;
  background: #f5f5f5;
}

/* ── 深色主题 ── */
.theme-dark {
  background: #181825;
  color: #cdd6f4;
}

.theme-dark body {
  background: #181825;
  color: #cdd6f4;
}

.theme-dark .main-content {
  background: #181825;
}

.theme-dark .card {
  background: #1e1e2e;
  border-color: #313244;
  color: #cdd6f4;
}

.theme-dark .card-title {
  color: #a6adc8;
}

.theme-dark .page-title {
  color: #cdd6f4;
}

.theme-dark th {
  background: #181825;
  color: #a6adc8;
  border-color: #313244;
}

.theme-dark td {
  border-color: #313244;
}

.theme-dark tr:hover td {
  background: #1e1e2e;
}

.theme-dark input[type='text'],
.theme-dark input[type='number'],
.theme-dark input[type='password'],
.theme-dark select,
.theme-dark textarea {
  background: #181825;
  border-color: #45475a;
  color: #cdd6f4;
}

.theme-dark .btn-secondary {
  background: #313244;
  color: #cdd6f4;
  border-color: #45475a;
}

.theme-dark .btn-secondary:hover:not(:disabled) {
  background: #45475a;
}

.theme-dark .form-label {
  color: #a6adc8;
}

.theme-dark .banner-warn {
  background: #2d2a1a;
  border-color: #6b5e00;
  color: #f9e2af;
}

.theme-dark .banner-error {
  background: #2d1a1a;
  border-color: #6b0000;
  color: #f38ba8;
}

/* ── 侧边栏 ── */
.sidebar {
  width: 180px;
  flex-shrink: 0;
  background: #1e1e2e;
  color: #cdd6f4;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  min-height: 100%;
}

.sidebar-header {
  padding: 18px 16px 14px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.close-btn {
  background: none;
  border: none;
  color: #6c7086;
  font-size: 14px;
  cursor: pointer;
  padding: 2px 6px;
  border-radius: 4px;
  line-height: 1;
  transition: background 0.15s, color 0.15s;
}

.close-btn:hover {
  background: rgba(243, 139, 168, 0.2);
  color: #f38ba8;
}

.logo {
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.3px;
}

.sidebar-section {
  padding: 8px 0;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  color: #a6adc8;
  text-decoration: none;
  font-size: 13px;
  transition: background 0.15s, color 0.15s;
  cursor: pointer;
}

.nav-item:hover {
  background: rgba(255, 255, 255, 0.06);
  color: #cdd6f4;
}

.nav-item--active {
  background: rgba(137, 180, 250, 0.15);
  color: #89b4fa;
}

.nav-icon {
  font-size: 14px;
  width: 18px;
  text-align: center;
}

.sidebar-divider {
  height: 1px;
  background: rgba(255, 255, 255, 0.08);
  margin: 4px 0;
}

.sidebar-footer {
  margin-top: auto;
  padding: 10px 12px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.sidebar-controls {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.ctrl-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 8px;
  border-radius: 5px;
  font-size: 11px;
  font-weight: 500;
  cursor: pointer;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(255, 255, 255, 0.05);
  color: #a6adc8;
  transition: background 0.15s, color 0.15s;
  width: 100%;
  text-align: left;
}

.ctrl-btn:hover {
  background: rgba(255, 255, 255, 0.1);
  color: #cdd6f4;
}

.ctrl-btn--active {
  background: rgba(137, 180, 250, 0.2);
  color: #89b4fa;
  border-color: rgba(137, 180, 250, 0.3);
}

.sidebar-status {
  font-size: 11px;
}

.status--online {
  color: #a6e3a1;
}

.status--offline {
  color: #f38ba8;
}

/* ── 主内容区 ── */
.main-content {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  background: #f5f5f5;
  min-height: 100%;
}

/* ── 通用卡片 ── */
.card {
  background: #fff;
  border-radius: 8px;
  padding: 16px 20px;
  border: 1px solid #e8e8e8;
}

.card-title {
  font-size: 13px;
  font-weight: 600;
  color: #666;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 8px;
}

.page-title {
  font-size: 20px;
  font-weight: 600;
  color: #1a1a1a;
  margin-bottom: 20px;
}

.grid-2 {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}

.grid-3 {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

.mt-4 { margin-top: 16px; }
.mt-6 { margin-top: 24px; }

/* ── 按钮 ── */
.btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 6px 14px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  border: 1px solid transparent;
  transition: all 0.15s;
  white-space: nowrap;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-primary {
  background: #3b82f6;
  color: #fff;
  border-color: #3b82f6;
}

.btn-primary:hover:not(:disabled) {
  background: #2563eb;
}

.btn-secondary {
  background: #fff;
  color: #374151;
  border-color: #d1d5db;
}

.btn-secondary:hover:not(:disabled) {
  background: #f9fafb;
}

.btn-danger {
  background: #fff;
  color: #dc2626;
  border-color: #fca5a5;
}

.btn-danger:hover:not(:disabled) {
  background: #fef2f2;
}

.btn-sm {
  padding: 4px 10px;
  font-size: 11px;
}

/* ── 表格 ── */
.table-wrap {
  overflow-x: auto;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

th {
  text-align: left;
  padding: 8px 12px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.4px;
  color: #6b7280;
  border-bottom: 1px solid #e5e7eb;
  background: #f9fafb;
}

td {
  padding: 9px 12px;
  border-bottom: 1px solid #f3f4f6;
  vertical-align: top;
}

tr:hover td {
  background: #fafafa;
}

/* ── 标签 ── */
.badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 100px;
  font-size: 11px;
  font-weight: 500;
}

.badge-green { background: #dcfce7; color: #15803d; }
.badge-yellow { background: #fef9c3; color: #a16207; }
.badge-red { background: #fee2e2; color: #b91c1c; }
.badge-blue { background: #dbeafe; color: #1d4ed8; }
.badge-gray { background: #f3f4f6; color: #6b7280; }

/* ── 表单 ── */
.form-group {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 12px;
}

.form-label {
  font-size: 12px;
  font-weight: 500;
  color: #374151;
}

input[type='text'],
input[type='number'],
input[type='password'],
select,
textarea {
  width: 100%;
  padding: 7px 10px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  font-size: 13px;
  color: #1a1a1a;
  background: #fff;
  outline: none;
  transition: border-color 0.15s;
  font-family: inherit;
}

input:focus,
select:focus,
textarea:focus {
  border-color: #3b82f6;
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.15);
}

textarea {
  resize: vertical;
  min-height: 80px;
}

/* ── Toast ── */
.toast {
  position: fixed;
  bottom: 24px;
  left: 50%;
  transform: translateX(-50%);
  padding: 10px 20px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
  z-index: 9999;
  pointer-events: none;
  white-space: nowrap;
}

.toast--info { background: #1e1e2e; color: #cdd6f4; }
.toast--success { background: #1e3a2e; color: #a6e3a1; }
.toast--error { background: #3a1e1e; color: #f38ba8; }

.toast-enter-active,
.toast-leave-active {
  transition: opacity 0.25s, transform 0.25s;
}

.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(8px);
}

/* ── 分页 ── */
.pagination {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
  font-size: 12px;
  color: #6b7280;
}

/* ── 加载中 ── */
.loading {
  padding: 40px;
  text-align: center;
  color: #9ca3af;
  font-size: 13px;
}

/* ── 空状态 ── */
.empty {
  padding: 40px;
  text-align: center;
  color: #9ca3af;
}

/* ── 分隔线 ── */
.divider {
  height: 1px;
  background: #e5e7eb;
  margin: 16px 0;
}

/* ── 警告横幅 ── */
.banner-warn {
  background: #fffbeb;
  border: 1px solid #fde68a;
  border-radius: 6px;
  padding: 10px 14px;
  font-size: 12px;
  color: #92400e;
  margin-bottom: 16px;
}

.banner-error {
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 6px;
  padding: 10px 14px;
  font-size: 12px;
  color: #991b1b;
  margin-bottom: 16px;
}
</style>
