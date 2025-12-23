/**
 * DaDude v2.0 - Main Entry Point
 * Vue.js 3 + Vuetify 3 + Pinia
 */
import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import router from './router'
import vuetify from './plugins/vuetify'

// Import global styles
import '@mdi/font/css/materialdesignicons.css'
import 'vuetify/styles'

const app = createApp(App)

// Install plugins
app.use(createPinia())
app.use(router)
app.use(vuetify)

// Mount app
app.mount('#app')
