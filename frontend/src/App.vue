<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'

import DataCenterPage from './features/data-center/DataCenterPage.vue'
import B649MultiTicketRecordsPage from './features/b649-multi-ticket-records/B649MultiTicketRecordsPage.vue'
import HistoryPage from './features/history/HistoryPage.vue'
import HistoricalSuccessWindowsPage from './features/historical-success-windows/HistoricalSuccessWindowsPage.vue'
import LiveZoneSplitBetsPage from './features/live-zone-split-bets/LiveZoneSplitBetsPage.vue'
import StrategyCatalogPage from './features/strategy-catalog/StrategyCatalogPage.vue'
import StrategyEvidencePage from './features/strategy-evidence/StrategyEvidencePage.vue'

type Page =
  | 'strategies'
  | 'historical-success-windows'
  | 'b649-multi-ticket-records'
  | 'data-center'
  | 'history'
  | 'strategy-evidence'
  | 'live-zone-split-bets'

const currentPage = ref<Page>(pageFromHash())

function pageFromHash(): Page {
  const route = window.location.hash.replace(/^#\/?/, '')
  if (route === 'historical-success-windows') return 'historical-success-windows'
  if (route === 'b649-multi-ticket-records') return 'b649-multi-ticket-records'
  if (route === 'data-center') return 'data-center'
  if (route === 'history' || route === 'draw-history') return 'history'
  if (route === 'strategy-evidence') return 'strategy-evidence'
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
        <a
          href="#/b649-multi-ticket-records"
          :aria-current="currentPage === 'b649-multi-ticket-records' ? 'page' : undefined"
        >
          B649 Records
        </a>
        <a href="#/data-center" :aria-current="currentPage === 'data-center' ? 'page' : undefined">
          Data Center
        </a>
        <a href="#/history" :aria-current="currentPage === 'history' ? 'page' : undefined">
          History
        </a>
        <a
          href="#/strategy-evidence"
          :aria-current="currentPage === 'strategy-evidence' ? 'page' : undefined"
        >
          Strategy Evidence
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
      <B649MultiTicketRecordsPage v-else-if="currentPage === 'b649-multi-ticket-records'" />
      <DataCenterPage v-else-if="currentPage === 'data-center'" />
      <HistoryPage v-else-if="currentPage === 'history'" />
      <StrategyEvidencePage v-else-if="currentPage === 'strategy-evidence'" />
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
      <template v-else-if="currentPage === 'b649-multi-ticket-records'">
        歷史成功率、排名與隨機基準差異僅供描述性研究，不構成未來預測、推薦、上線決策或中獎保證。
      </template>
      <template v-else-if="currentPage === 'live-zone-split-bets'">
        Target-contract-only view of the merged Live Zone Split API. Legacy LotteryNew consumer
        parity is not claimed or verified here.
      </template>
      <template v-else-if="currentPage === 'strategy-evidence'">
        Evidence availability comes only from committed registries and definitions; unavailable
        values are never inferred.
      </template>
      <template v-else>
        Local draw data stays outside Git. Import writes occur only after explicit confirmation.
      </template>
    </footer>
  </div>
</template>
