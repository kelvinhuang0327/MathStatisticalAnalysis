<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'

import DataCenterPage from './features/data-center/DataCenterPage.vue'
import DrawHistoryPage from './features/draw-history/DrawHistoryPage.vue'
import StrategyCatalogPage from './features/strategy-catalog/StrategyCatalogPage.vue'

type Page = 'strategies' | 'data-center' | 'draw-history'

const currentPage = ref<Page>(pageFromHash())

function pageFromHash(): Page {
  const route = window.location.hash.replace(/^#\/?/, '')
  if (route === 'data-center') return 'data-center'
  if (route === 'draw-history') return 'draw-history'
  return 'strategies'
}

function synchronizePage(): void {
  currentPage.value = pageFromHash()
}

onMounted(() => window.addEventListener('hashchange', synchronizePage))
onBeforeUnmount(() => window.removeEventListener('hashchange', synchronizePage))
</script>

<template>
  <div class="app-shell">
    <header class="app-header">
      <a class="brand" href="#/strategies" aria-label="LottoLab home">
        <span class="brand__mark">LL</span>
        <span>
          <strong>LottoLab</strong>
          <small>Statistical Analysis</small>
        </span>
      </a>
      <nav class="primary-nav" aria-label="Primary navigation">
        <a href="#/strategies" :aria-current="currentPage === 'strategies' ? 'page' : undefined">
          Strategy Catalog
        </a>
        <a href="#/data-center" :aria-current="currentPage === 'data-center' ? 'page' : undefined">
          Data Center
        </a>
        <a href="#/draw-history" :aria-current="currentPage === 'draw-history' ? 'page' : undefined">
          Draw History
        </a>
      </nav>
      <span class="environment-badge">Local workspace</span>
    </header>

    <main>
      <StrategyCatalogPage v-if="currentPage === 'strategies'" />
      <DataCenterPage v-else-if="currentPage === 'data-center'" />
      <DrawHistoryPage v-else />
    </main>

    <footer class="app-footer">
      <template v-if="currentPage === 'strategies'">
        Strategy Catalog remains a DB-free metadata request path.
      </template>
      <template v-else>
        Local draw data stays outside Git. Import writes occur only after explicit confirmation.
      </template>
    </footer>
  </div>
</template>
