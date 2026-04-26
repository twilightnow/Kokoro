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

type TauriRuntimeWindow = Window & {
  __TAURI_INTERNALS__?: {
    invoke?: unknown
  }
}

function hasTauriInvoke(): boolean {
  if (typeof window === 'undefined') {
    return false
  }

  const tauriWindow = window as TauriRuntimeWindow
  return typeof tauriWindow.__TAURI_INTERNALS__?.invoke === 'function'
}

async function invokeTauriCommand(
  command: string,
  args?: Record<string, unknown>,
): Promise<boolean> {
  if (!hasTauriInvoke()) {
    return false
  }

  const { invoke } = await import('@tauri-apps/api/core')
  await invoke(command, args)
  return true
}

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
  if (!hasTauriInvoke()) {
    window.close()
    return
  }
  try {
    await invokeTauriCommand('close_admin_window')
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
    await invokeTauriCommand('set_main_always_on_top', { enabled: alwaysOnTop.value })
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
  { path: '/relationship', icon: '🤝', label: '关系状态' },
  { path: '/proactive', icon: '💬', label: '主动陪伴' },
  { path: '/perception', icon: '🛡', label: '感知隐私' },
  { path: '/reminders', icon: '⏰', label: '提醒管理' },
  { path: '/logs', icon: '📄', label: '对话日志' },
  { path: '/stats', icon: '📈', label: '情绪统计' },
]

const devNav = [
  { path: '/interaction', icon: '🎛', label: '交互设置' },
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
    await invokeTauriCommand('set_main_always_on_top', { enabled: alwaysOnTop.value })
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

/* ── 深色主题文本修复 ── */
.theme-dark .hint {
  color: #7f849c;
}

.theme-dark .muted {
  color: #7f849c;
}

.theme-dark .empty-state,
.theme-dark .empty {
  color: #6c7086;
}

.theme-dark .stat-value {
  color: #cdd6f4;
}

.theme-dark .stat-sub {
  color: #7f849c;
}

.theme-dark .settings-list label,
.theme-dark .compact-list label {
  color: #cdd6f4;
}

.theme-dark .detail-k {
  color: #a6adc8;
}

.theme-dark .detail-v {
  color: #cdd6f4;
}

.theme-dark .detail-rule {
  color: #cdd6f4;
}

.theme-dark .detail-section-title {
  color: #7f849c;
  border-bottom-color: #313244;
}

.theme-dark .detail-empty {
  color: #6c7086;
}

.theme-dark .log-item {
  background: rgba(30, 30, 46, 0.8);
  border-color: #313244;
}

.theme-dark .log-content {
  color: #cdd6f4;
}

.theme-dark .log-head strong {
  color: #cdd6f4;
}

/* ── 深色主题标签 ── */
.theme-dark .tag {
  background: #313244;
  color: #cdd6f4;
}

.theme-dark .tag-red { background: #3a1a1a; color: #f38ba8; }
.theme-dark .tag-blue { background: #1a2535; color: #89b4fa; }
.theme-dark .tag-purple { background: #261a35; color: #cba6f7; }
.theme-dark .tag-amber { background: #2a200a; color: #f9e2af; }

/* ── 深色主题徽章 ── */
.theme-dark .badge-green { background: #1a2e1a; color: #a6e3a1; }
.theme-dark .badge-yellow { background: #2a2008; color: #f9e2af; }
.theme-dark .badge-red { background: #2e0808; color: #f38ba8; }
.theme-dark .badge-blue { background: #08182e; color: #89b4fa; }
.theme-dark .badge-gray { background: #313244; color: #a6adc8; }

/* ── 深色主题卡片改善 ── */
.theme-dark .card {
  box-shadow: 0 1px 6px rgba(0, 0, 0, 0.3);
}

/* ── 深色主题按钮 ── */
.theme-dark .btn-primary {
  box-shadow: 0 1px 3px rgba(59, 130, 246, 0.15);
}

/* ── 深色主题表单 ── */
.theme-dark input[type='time'] {
  background: #181825;
  border-color: #45475a;
  color: #cdd6f4;
}

/* ── 深色主题分隔线 ── */
.theme-dark .divider {
  background: #313244;
}

/* ── 深色主题滚动条 ── */
.theme-dark ::-webkit-scrollbar {
  width: 6px;
}

.theme-dark ::-webkit-scrollbar-track {
  background: #181825;
}

.theme-dark ::-webkit-scrollbar-thumb {
  background: #45475a;
  border-radius: 3px;
}

.theme-dark ::-webkit-scrollbar-thumb:hover {
  background: #6c7086;
}

/* ── 浅色主题滚动条 ── */
::-webkit-scrollbar {
  width: 6px;
}

::-webkit-scrollbar-track {
  background: #f3f4f6;
}

::-webkit-scrollbar-thumb {
  background: #d1d5db;
  border-radius: 3px;
}

::-webkit-scrollbar-thumb:hover {
  background: #9ca3af;
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
  border-radius: 12px;
  padding: 18px 22px;
  border: 1px solid #e5e7eb;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04), 0 2px 8px rgba(0, 0, 0, 0.03);
}

.card-title {
  font-size: 11px;
  font-weight: 600;
  color: #9ca3af;
  text-transform: uppercase;
  letter-spacing: 0.8px;
  margin-bottom: 12px;
}

.page-title {
  font-size: 22px;
  font-weight: 700;
  color: #111827;
  margin-bottom: 24px;
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
  padding: 7px 16px;
  border-radius: 8px;
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
  box-shadow: 0 1px 3px rgba(59, 130, 246, 0.25);
}

.btn-primary:hover:not(:disabled) {
  background: #2563eb;
  box-shadow: 0 2px 6px rgba(59, 130, 246, 0.35);
}

.btn-secondary {
  background: #fff;
  color: #374151;
  border-color: #d1d5db;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
}

.btn-secondary:hover:not(:disabled) {
  background: #f3f4f6;
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
  padding: 5px 12px;
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
