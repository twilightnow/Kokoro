import { createApp } from 'vue'
import { createPinia } from 'pinia'
import AdminApp from './AdminApp.vue'
import { router } from './router'

createApp(AdminApp).use(createPinia()).use(router).mount('#admin-app')
