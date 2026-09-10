import { createApp } from 'vue'
import './style.css'
import App from './App.vue'

export function shouldActivateThreeUiPilot(isDev: boolean, search: string): boolean {
  return isDev && new URLSearchParams(search).get('uiPilot') === 'threeui'
}

async function bootstrap(): Promise<void> {
  if (shouldActivateThreeUiPilot(import.meta.env.DEV, window.location.search)) {
    const { default: ThreeUiPagePilot } = await import('./features/ui-page-pilot/ThreeUiPagePilot.vue')
    createApp(ThreeUiPagePilot).mount('#app')
    return
  }
  createApp(App).mount('#app')
}

if (import.meta.env.MODE !== 'test') {
  bootstrap()
}
