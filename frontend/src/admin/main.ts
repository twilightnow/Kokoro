import { createApp } from 'vue'
import { createPinia } from 'pinia'
import AdminApp from './AdminApp.vue'
import { router } from './router'
import { errorDetails, reportClientLog } from '../shared/diagnostics'

void reportClientLog({
  source: 'admin-window',
  event: 'admin-entry-loaded',
  message: 'admin main.ts loaded',
  details: {
    href: window.location.href,
    userAgent: navigator.userAgent,
  },
})

try {
  createApp(AdminApp).use(createPinia()).use(router).mount('#admin-app')
  void reportClientLog({
    source: 'admin-window',
    event: 'admin-app-mounted',
    message: 'Admin Vue app mounted',
  })
} catch (error) {
  void reportClientLog({
    source: 'admin-window',
    event: 'admin-app-mount-error',
    level: 'error',
    message: 'Admin Vue app failed to mount',
    details: errorDetails(error),
  })
  throw error
}
