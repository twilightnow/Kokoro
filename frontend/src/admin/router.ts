import { createRouter, createWebHashHistory } from 'vue-router'
import Dashboard from './views/Dashboard.vue'
import Characters from './views/Characters.vue'
import Memories from './views/Memories.vue'
import Relationship from './views/Relationship.vue'
import Logs from './views/Logs.vue'
import EmotionStats from './views/EmotionStats.vue'
import Debug from './views/Debug.vue'
import Settings from './views/Settings.vue'
import Interaction from './views/Interaction.vue'
import Proactive from './views/Proactive.vue'
import Perception from './views/Perception.vue'
import Reminders from './views/Reminders.vue'

export const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', redirect: '/dashboard' },
    { path: '/dashboard', component: Dashboard, meta: { title: '状态总览' } },
    { path: '/characters', component: Characters, meta: { title: '角色管理' } },
    { path: '/memories', component: Memories, meta: { title: '记忆浏览' } },
    { path: '/relationship', component: Relationship, meta: { title: '关系状态' } },
    { path: '/proactive', component: Proactive, meta: { title: '主动陪伴' } },
    { path: '/perception', component: Perception, meta: { title: '感知隐私' } },
    { path: '/reminders', component: Reminders, meta: { title: '提醒管理' } },
    { path: '/logs', component: Logs, meta: { title: '对话日志' } },
    { path: '/stats', component: EmotionStats, meta: { title: '情绪统计' } },
    { path: '/interaction', component: Interaction, meta: { title: '交互设置' } },
    { path: '/debug', component: Debug, meta: { title: '调试工具' } },
    { path: '/settings', component: Settings, meta: { title: '配置设置' } },
  ],
})
