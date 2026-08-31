<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import DataOperationsPage from './features/data-operations/DataOperationsPage.vue'
import HistoryPage from './features/history/HistoryPage.vue'
import BestReplayPage from './features/best-replay/BestReplayPage.vue'
import StrategyIntelligencePage from './features/strategy-intelligence/StrategyIntelligencePage.vue'
import B649ReplayPage from './features/b649-replay/B649ReplayPage.vue'
import P638ReplayPage from './features/p638-replay/P638ReplayPage.vue'
import T539ReplayPage from './features/t539-replay/T539ReplayPage.vue'
import FutureModulesPage from './features/future-modules/FutureModulesPage.vue'

// Direct sub-page components for full backwards compatibility
import StrategyCatalogPage from './features/strategy-catalog/StrategyCatalogPage.vue'
import HistoricalSuccessWindowsPage from './features/historical-success-windows/HistoricalSuccessWindowsPage.vue'
import HistoricalBaseDataPage from './features/historical-base-data/HistoricalBaseDataPage.vue'
import B649MultiTicketRecordsPage from './features/b649-multi-ticket-records/B649MultiTicketRecordsPage.vue'
import B649OwnerRankingPage from './features/b649-owner-ranking/B649OwnerRankingPage.vue'
import StrategyEvidencePage from './features/strategy-evidence/StrategyEvidencePage.vue'
import LiveZoneSplitBetsPage from './features/live-zone-split-bets/LiveZoneSplitBetsPage.vue'
import P638HistoricalReplayPage from './features/p638-historical-replay/P638HistoricalReplayPage.vue'
import P638StrategyAnalysisPage from './features/p638-strategy-analysis/P638StrategyAnalysisPage.vue'
import T539StrategyAnalysisPage from './features/t539-strategy-analysis/T539StrategyAnalysisPage.vue'
import ReplayHistoryPage from './features/replay-history/ReplayHistoryPage.vue'
import RankingMatrixPage from './features/ranking-matrix/RankingMatrixPage.vue'

type Page =
  | 'data-operations'
  | 'data-center'
  | 'history'
  | 'draw-history'
  | 'best-replay'
  | 'strategy-intelligence'
  | 'strategies'
  | 'strategy-evidence'
  | 'historical-success-windows'
  | 'b649-replay'
  | 'b649-multi-ticket-records'
  | 'b649-owner-ranking'
  | 'p638-replay'
  | 'p638-historical-replay'
  | 'p638-strategy-analysis'
  | 't539-replay'
  | 't539-strategy-analysis'
  | 'future-modules'
  | 'historical-base-data'
  | 'live-zone-split-bets'
  | 'replay-history'
  | 'ranking-matrix'

const currentPage = ref<Page>(pageFromHash())

function pageFromHash(): Page {
  const route = window.location.hash.replace(/^#\/?/, '')
  if (route === 'data-operations' || route === 'data-center') return route as Page
  if (route === 'history' || route === 'draw-history') return route as Page
  if (route === 'best-replay') return 'best-replay'
  if (route === 'strategy-intelligence') return 'strategy-intelligence'
  if (route === 'strategies') return 'strategies'
  if (route === 'strategy-evidence') return 'strategy-evidence'
  if (route === 'historical-success-windows') return 'historical-success-windows'
  if (route === 'b649-replay') return 'b649-replay'
  if (route === 'b649-multi-ticket-records') return 'b649-multi-ticket-records'
  if (route === 'b649-owner-ranking') return 'b649-owner-ranking'
  if (route === 'p638-replay') return 'p638-replay'
  if (route === 'p638-historical-replay') return 'p638-historical-replay'
  if (route === 'p638-strategy-analysis') return 'p638-strategy-analysis'
  if (route === 't539-replay') return 't539-replay'
  if (route === 't539-strategy-analysis') return 't539-strategy-analysis'
  if (route === 'future-modules') return 'future-modules'
  if (route === 'historical-base-data') return 'historical-base-data'
  if (route === 'live-zone-split-bets') return 'live-zone-split-bets'
  if (route === 'replay-history') return 'replay-history'
  if (route === 'ranking-matrix' || route === 'strategy-ranking' || route === 'ranking-matrix-results') return 'ranking-matrix'
  return 'data-operations'
}

const activeNavSection = computed(() => {
  const p = currentPage.value
  if (p === 'data-operations' || p === 'data-center') return 'data-operations'
  if (p === 'history' || p === 'draw-history') return 'history'
  if (p === 'best-replay' || p === 'ranking-matrix') return 'best-replay'
  if (p === 'strategy-intelligence' || p === 'strategies' || p === 'strategy-evidence' || p === 'historical-success-windows') return 'strategy-intelligence'
  if (p === 'b649-replay' || p === 'b649-multi-ticket-records' || p === 'b649-owner-ranking') return 'b649-replay'
  if (p === 'p638-replay' || p === 'p638-historical-replay' || p === 'p638-strategy-analysis') return 'p638-replay'
  if (p === 't539-replay' || p === 't539-strategy-analysis') return 't539-replay'
  if (p === 'future-modules' || p === 'historical-base-data' || p === 'live-zone-split-bets' || p === 'replay-history') return 'future-modules'
  return 'data-operations'
})

function synchronizePage(): void {
  currentPage.value = pageFromHash()
}

onMounted(() => window.addEventListener('hashchange', synchronizePage))
onBeforeUnmount(() => window.removeEventListener('hashchange', synchronizePage))
</script>

<template>
  <div class="app-shell">
    <!-- Ambient Background Animation Orbs -->
    <div class="ambient-orbs" aria-hidden="true">
      <div class="orb orb-1" />
      <div class="orb orb-2" />
      <div class="orb orb-3" />
    </div>

    <header class="app-header">
      <a class="brand" href="#/data-operations" aria-label="LottoLab home">
        <span class="brand__mark">LL</span>
        <span>
          <strong>LottoLab</strong>
          <small>Statistical Analysis</small>
        </span>
      </a>
      <nav class="primary-nav" aria-label="Primary navigation">
        <a
          href="#/data-operations"
          :aria-current="activeNavSection === 'data-operations' ? 'page' : undefined"
        >
          Data Operations
        </a>
        <a
          href="#/history"
          :aria-current="activeNavSection === 'history' ? 'page' : undefined"
        >
          History
        </a>
        <a
          href="#/best-replay"
          :aria-current="activeNavSection === 'best-replay' ? 'page' : undefined"
        >
          Best Replay
        </a>
        <a
          href="#/strategy-intelligence"
          :aria-current="activeNavSection === 'strategy-intelligence' ? 'page' : undefined"
        >
          Strategy Intelligence
        </a>
        <a
          href="#/b649-replay"
          :aria-current="activeNavSection === 'b649-replay' ? 'page' : undefined"
        >
          B649 Replay
        </a>
        <a
          href="#/p638-replay"
          :aria-current="activeNavSection === 'p638-replay' ? 'page' : undefined"
        >
          P638 Replay
        </a>
        <a
          href="#/t539-replay"
          :aria-current="activeNavSection === 't539-replay' ? 'page' : undefined"
        >
          T539 Replay
        </a>
        <a
          href="#/future-modules"
          :aria-current="activeNavSection === 'future-modules' ? 'page' : undefined"
        >
          Future Modules
        </a>
      </nav>
      <span class="environment-badge">Audited Research</span>
    </header>

    <main>
      <!-- Canonical Pages -->
      <DataOperationsPage v-if="currentPage === 'data-operations' || currentPage === 'data-center'" />
      <HistoryPage v-else-if="currentPage === 'history' || currentPage === 'draw-history'" />
      <BestReplayPage v-else-if="currentPage === 'best-replay'" />
      <StrategyIntelligencePage v-else-if="currentPage === 'strategy-intelligence'" />
      <B649ReplayPage v-else-if="currentPage === 'b649-replay'" />
      <P638ReplayPage v-else-if="currentPage === 'p638-replay'" />
      <T539ReplayPage v-else-if="currentPage === 't539-replay'" />
      <FutureModulesPage v-else-if="currentPage === 'future-modules'" />

      <!-- Deep Link / Legacy Route Direct Support -->
      <RankingMatrixPage v-else-if="currentPage === 'ranking-matrix'" />
      <StrategyCatalogPage v-else-if="currentPage === 'strategies'" />
      <HistoricalSuccessWindowsPage v-else-if="currentPage === 'historical-success-windows'" />
      <HistoricalBaseDataPage v-else-if="currentPage === 'historical-base-data'" />
      <B649MultiTicketRecordsPage v-else-if="currentPage === 'b649-multi-ticket-records'" />
      <B649OwnerRankingPage v-else-if="currentPage === 'b649-owner-ranking'" />
      <StrategyEvidencePage v-else-if="currentPage === 'strategy-evidence'" />
      <LiveZoneSplitBetsPage v-else-if="currentPage === 'live-zone-split-bets'" />
      <P638HistoricalReplayPage v-else-if="currentPage === 'p638-historical-replay'" />
      <P638StrategyAnalysisPage v-else-if="currentPage === 'p638-strategy-analysis'" />
      <T539StrategyAnalysisPage v-else-if="currentPage === 't539-strategy-analysis'" />
      <ReplayHistoryPage v-else-if="currentPage === 'replay-history'" />
      <DataOperationsPage v-else />
    </main>

    <footer class="app-footer">
      <div>
        <template v-if="activeNavSection === 'data-operations'">
          Local draw data stays outside Git. Import writes occur only after explicit confirmation.
        </template>
        <template v-else-if="activeNavSection === 'strategy-intelligence'">
          Strategy Intelligence presents descriptive quantitative metadata and evidence verification gates without prediction claims.
        </template>
        <template v-else-if="activeNavSection === 'b649-replay'">
          B649 historical records and rankings are descriptive research evidence only.
        </template>
        <template v-else-if="activeNavSection === 'p638-replay'">
          P638 replay is read-only historical evidence; no ticket generation or predictive edge is claimed.
        </template>
        <template v-else-if="activeNavSection === 't539-replay'">
          T539 rankings and coverage are descriptive historical evidence drawn from stored replay results.
        </template>
        <template v-else-if="activeNavSection === 'best-replay'">
          Best Replay evaluates multi-ticket performance across structured historical horizons.
        </template>
        <template v-else-if="activeNavSection === 'future-modules'">
          Future modules follow strict statistical validation and reproducibility gates before deployment.
        </template>
        <template v-else>
          Draw history and ingestion logs are append-only historical audit records.
        </template>
      </div>
      <div>
        <span>LottoLab Quant Engine · <code>B649 · P638 · T539</code></span>
      </div>
    </footer>
  </div>
</template>
