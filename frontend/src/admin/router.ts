import { createRouter, createWebHashHistory } from 'vue-router'
import Dashboard from './views/Dashboard.vue'
import Characters from './views/Characters.vue'
import Memories from './views/Memories.vue'
import Logs from './views/Logs.vue'
import EmotionStats from './views/EmotionStats.vue'
import Debug from './views/Debug.vue'
import Settings from './views/Settings.vue'

export const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', redirect: '/dashboard' },
    { path: '/dashboard', component: Dashboard, meta: { title: '状态总览' } },
    { path: '/characters', component: Characters, meta: { title: '角色管理' } },
    { path: '/memories', component: Memories, meta: { title: '记忆浏览' } },
    { path: '/logs', component: Logs, meta: { title: '对话日志' } },
    { path: '/stats', component: EmotionStats, meta: { title: '情绪统计' } },
    { path: '/debug', component: Debug, meta: { title: '调试工具' } },
    { path: '/settings', component: Settings, meta: { title: '配置设置' } },
  ],
})
