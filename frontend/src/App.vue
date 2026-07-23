<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'

import DataCenterPage from './features/data-center/DataCenterPage.vue'
import DrawHistoryPage from './features/draw-history/DrawHistoryPage.vue'
import HistoricalSuccessWindowsPage from './features/historical-success-windows/HistoricalSuccessWindowsPage.vue'
import LiveZoneSplitBetsPage from './features/live-zone-split-bets/LiveZoneSplitBetsPage.vue'
import StrategyCatalogPage from './features/strategy-catalog/StrategyCatalogPage.vue'

type Page =
  | 'strategies'
  | 'historical-success-windows'
  | 'data-center'
  | 'draw-history'
  | 'live-zone-split-bets'

const currentPage = ref<Page>(pageFromHash())

function pageFromHash(): Page {
  const route = window.location.hash.replace(/^#\/?/, '')
  if (route === 'historical-success-windows') return 'historical-success-windows'
  if (route === 'data-center') return 'data-center'
  if (route === 'draw-history') return 'draw-history'
  if (route === 'live-zone-split-bets') return 'live-zone-split-bets'
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
          Strategy Overview
        </a>
        <a
          href="#/historical-success-windows"
          :aria-current="currentPage === 'historical-success-windows' ? 'page' : undefined"
        >
          Success Windows
        </a>
        <a href="#/data-center" :aria-current="currentPage === 'data-center' ? 'page' : undefined">
          Data Center
        </a>
        <a href="#/draw-history" :aria-current="currentPage === 'draw-history' ? 'page' : undefined">
          Draw History
        </a>
        <a
          href="#/live-zone-split-bets"
          :aria-current="currentPage === 'live-zone-split-bets' ? 'page' : undefined"
        >
          Live Zone Split Bets
        </a>
      </nav>
      <span class="environment-badge">Local workspace</span>
    </header>

    <main>
      <StrategyCatalogPage v-if="currentPage === 'strategies'" />
      <HistoricalSuccessWindowsPage v-else-if="currentPage === 'historical-success-windows'" />
      <DataCenterPage v-else-if="currentPage === 'data-center'" />
      <DrawHistoryPage v-else-if="currentPage === 'draw-history'" />
      <LiveZoneSplitBetsPage v-else />
    </main>

    <footer class="app-footer">
      <template v-if="currentPage === 'strategies'">
        Strategy Overview remains a DB-free metadata request path with explicit evidence gaps.
      </template>
      <template v-else-if="currentPage === 'historical-success-windows'">
        Historical Success Windows are descriptive, exact-source research evidence—not rankings,
        promotion decisions, or predictions.
      </template>
      <template v-else-if="currentPage === 'live-zone-split-bets'">
        Target-contract-only view of the merged Live Zone Split API. Legacy LotteryNew consumer
        parity is not claimed or verified here.
      </template>
      <template v-else>
        Local draw data stays outside Git. Import writes occur only after explicit confirmation.
      </template>
    </footer>
  </div>
</template>
