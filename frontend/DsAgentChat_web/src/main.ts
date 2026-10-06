import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'

import TDesign from 'tdesign-vue-next'
import 'tdesign-vue-next/es/style/index.css'
import TDesignChat from '@tdesign-vue-next/chat'
import '@tdesign-vue-next/chat/es/style/index.css'
import './styles/theme-accio.css'

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.use(TDesign)
app.use(TDesignChat)
app.mount('#app')
