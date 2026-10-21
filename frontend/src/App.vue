<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import DataOperationsPage from './features/data-operations/DataOperationsPage.vue'
import HistoryPage from './features/history/HistoryPage.vue'
import BestReplayPage from './features/best-replay/BestReplayPage.vue'
import ReplayOverviewPage from './features/replay-overview/ReplayOverviewPage.vue'
import StrategyIntelligencePage from './features/strategy-intelligence/StrategyIntelligencePage.vue'
import B649ReplayPage from './features/b649-replay/B649ReplayPage.vue'
import B649CurrentForecastPage from './features/b649-current-forecast/B649CurrentForecastPage.vue'
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

type Game = 'B649' | 'P638' | 'T539'
type GameSelection = Game | 'ALL'
type PrimarySection = 'data-operations' | 'forecast' | 'ranking' | 'backtest' | 'legacy'

const gameOptions: Array<{ code: Game; lotteryType: string }> = [
  { code: 'B649', lotteryType: 'BIG_LOTTO' },
  { code: 'P638', lotteryType: 'POWER_LOTTO' },
  { code: 'T539', lotteryType: 'DAILY_539' },
]

type Page =
  | 'data-operations'
  | 'data-center'
  | 'history'
  | 'draw-history'
  | 'best-replay'
  | 'replay-overview'
  | 'all-strategy-replay'
  | 'strategy-intelligence'
  | 'strategies'
  | 'strategy-evidence'
  | 'historical-success-windows'
  | 'b649-replay'
  | 'b649-current-forecast'
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
  | 'unavailable'

type RouteSnapshot = { path: string; params: URLSearchParams }

function readRoute(): RouteSnapshot {
  const route = window.location.hash.replace(/^#\/?/, '')
  const queryIndex = route.indexOf('?')
  const path = queryIndex < 0 ? route : route.slice(0, queryIndex)
  const query = queryIndex < 0 ? '' : route.slice(queryIndex + 1)
  return { path, params: new URLSearchParams(query) }
}

function pageFromRoute(route: string): Page {
  if (route === 'unavailable') return 'unavailable'
  if (route === 'data-operations' || route === 'data-center') return route as Page
  if (route === 'history' || route === 'draw-history') return route as Page
  if (route === 'best-replay') return 'best-replay'
  if (route === 'replay-overview' || route === 'all-strategy-replay') return 'replay-overview'
  if (route === 'strategy-intelligence') return 'strategy-intelligence'
  if (route === 'strategies') return 'strategies'
  if (route === 'strategy-evidence') return 'strategy-evidence'
  if (route === 'historical-success-windows') return 'historical-success-windows'
  if (route === 'b649-replay') return 'b649-replay'
  if (route === 'b649-current-forecast') return 'b649-current-forecast'
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

function isGame(value: string | null): value is Game {
  return value === 'B649' || value === 'P638' || value === 'T539'
}

function gameForRoute(route: string): Game {
  if (route.startsWith('p638-')) return 'P638'
  if (route.startsWith('t539-')) return 'T539'
  return 'B649'
}

function gameFromRoute(snapshot: RouteSnapshot): GameSelection {
  const selected = snapshot.params.get('game')
  if (
    (snapshot.path === 'data-operations' || snapshot.path === 'data-center' || snapshot.path === 'unavailable') &&
    isGame(selected)
  ) return selected
  return gameForRoute(snapshot.path)
}

const routeState = ref<RouteSnapshot>(readRoute())
const currentPage = computed(() => pageFromRoute(routeState.value.path))
const selectedGame = ref<GameSelection>(gameFromRoute(routeState.value))
const bestReplayResetToken = ref(0)

function sectionForRoute(route: string, snapshot = routeState.value): PrimarySection {
  if (route === '' || route === 'data-operations' || route === 'data-center') return 'data-operations'
  if (route === 'b649-current-forecast') return 'forecast'
  if (route === 'b649-owner-ranking' || route === 'ranking-matrix' || route === 'strategy-ranking' || route === 'ranking-matrix-results') return 'ranking'
  if (
    route === 'best-replay' ||
    route === 'b649-replay' ||
    route === 'p638-replay' ||
    route === 't539-replay' ||
    route === 'p638-strategy-analysis' ||
    route === 't539-strategy-analysis' ||
    route === 'replay-overview' ||
    route === 'all-strategy-replay' ||
    route === 'p638-historical-replay' ||
    route === 'replay-history'
  ) return 'backtest'
  if (route === 'unavailable') {
    const page = snapshot.params.get('page')
    if (page === 'data-operations' || page === 'forecast' || page === 'ranking' || page === 'backtest') return page
    return 'legacy'
  }
  return 'legacy'
}

function routeForUnavailable(page: PrimarySection, game: Game, legacyRoute = ''): string {
  const params = new URLSearchParams({ page, game })
  if (page === 'legacy' && legacyRoute) params.set('route', legacyRoute)
  return '#/unavailable?' + params.toString()
}

function routeForData(path: string, game: Game): string {
  const dataRoute = path === 'data-center' ? 'data-center' : 'data-operations'
  return '#/' + dataRoute + (game === 'B649' ? '' : '?game=' + game)
}

function routeForSection(section: PrimarySection, game: Game): string {
  if (section === 'data-operations') return routeForData('data-operations', game)
  if (section === 'forecast') {
    return game === 'B649' ? '#/b649-current-forecast' : routeForUnavailable('forecast', game)
  }
  if (section === 'ranking') {
    return game === 'B649' ? '#/b649-owner-ranking' : routeForUnavailable('ranking', game)
  }
  if (section === 'backtest') {
    if (game === 'B649') return '#/best-replay'
    return game === 'P638' ? '#/p638-replay' : '#/t539-replay'
  }
  return routeForUnavailable('legacy', game)
}

function synchronizePage(): void {
  routeState.value = readRoute()
  selectedGame.value = gameFromRoute(routeState.value)
}

function navigate(hash: string): void {
  if (window.location.hash === hash) return
  window.location.hash = hash
  synchronizePage()
}

function handleGameChange(event: Event): void {
  const target = event.target
  if (!(target instanceof HTMLSelectElement) || !isGame(target.value)) return

  const route = routeState.value.path
  const section = sectionForRoute(route)
  const previousGame = selectedGame.value
  selectedGame.value = target.value

  if (route === 'best-replay' && target.value === 'B649' && previousGame !== 'B649') {
    bestReplayResetToken.value += 1
  }

  if (section === 'data-operations') {
    navigate(routeForData(route, target.value))
    return
  }
  if (section !== 'legacy') {
    navigate(routeForSection(section, target.value))
    return
  }

  const legacyRoute = route === 'unavailable' ? routeState.value.params.get('route') ?? '' : route
  if (legacyRoute && target.value === gameForRoute(legacyRoute)) {
    navigate('#/' + legacyRoute)
  } else {
    navigate(routeForUnavailable('legacy', target.value, legacyRoute))
  }
}

function handleBestReplayGameChange(event: Event): void {
  const target = event.target
  if (!(target instanceof HTMLSelectElement) || target.id !== 'game-select') return
  selectBestReplayGame(target.value)
}

function handleBestReplayGameClick(event: MouseEvent): void {
  if (currentPage.value !== 'best-replay') return
  const target = event.target
  if (!(target instanceof HTMLElement)) return
  const button = target.closest<HTMLButtonElement>('[data-testid^="game-btn-"]')
  const game = button?.getAttribute('data-testid')?.replace('game-btn-', '').toUpperCase()
  if (game) selectBestReplayGame(game)
}

function selectBestReplayGame(game: string): void {
  if (game === 'ALL') {
    selectedGame.value = 'ALL'
    return
  }
  if (!isGame(game)) return
  selectedGame.value = game
  if (game !== 'B649') navigate(routeForSection('backtest', game))
}

const unavailableContext = computed(() => {
  const snapshot = routeState.value
  if (snapshot.path !== 'unavailable') return null
  const section = sectionForRoute(snapshot.path, snapshot)
  const titles: Record<PrimarySection, string> = {
    'data-operations': '資料管理',
    forecast: '本期預測',
    ranking: '策略排行榜',
    backtest: '歷史回測',
    legacy: '原頁面',
  }
  return {
    section,
    title: titles[section],
    legacyRoute: snapshot.params.get('route') ?? '',
  }
})

const activeNavSection = computed<PrimarySection | ''>(() => {
  if (currentPage.value === 'unavailable') return unavailableContext.value?.section ?? ''
  const section = sectionForRoute(routeState.value.path)
  return section === 'legacy' ? '' : section
})

const primaryNavigation = computed(() => {
  const game: Game = selectedGame.value === 'ALL' ? 'B649' : selectedGame.value
  return [
    { section: 'data-operations' as const, label: '資料管理', href: routeForData('data-operations', game) },
    { section: 'forecast' as const, label: '本期預測', href: routeForSection('forecast', game) },
    { section: 'ranking' as const, label: '策略排行榜', href: routeForSection('ranking', game) },
    { section: 'backtest' as const, label: '歷史回測', href: routeForSection('backtest', game) },
  ]
})

function synchronizeHash(): void {
  synchronizePage()
}

onMounted(() => window.addEventListener('hashchange', synchronizeHash))
onBeforeUnmount(() => window.removeEventListener('hashchange', synchronizeHash))
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
      <a class="brand" :href="primaryNavigation[0]?.href" aria-label="MathStatisticalAnalysis 首頁">
        <span class="brand__mark">MSA</span>
        <span>
          <strong>MathStatisticalAnalysis</strong>
          <small>統計分析平台</small>
        </span>
      </a>
      <nav class="primary-nav" aria-label="主要導覽">
        <a
          v-for="item in primaryNavigation"
          :key="item.section"
          :href="item.href"
          :aria-current="activeNavSection === item.section ? 'page' : undefined"
        >
          {{ item.label }}
        </a>
      </nav>
      <div class="game-switcher">
        <label for="global-game-switcher">遊戲</label>
        <select
          id="global-game-switcher"
          aria-label="切換遊戲"
          :value="selectedGame"
          @change="handleGameChange"
        >
          <option v-for="game in gameOptions" :key="game.code" :value="game.code">
            {{ game.code }} · {{ game.lotteryType }}
          </option>
          <option v-if="selectedGame === 'ALL'" value="ALL" disabled>多彩種</option>
        </select>
      </div>
    </header>

    <main @click.capture="handleBestReplayGameClick">
      <section v-if="unavailableContext" class="panel" role="status" data-testid="unavailable-page">
        <p class="section-header__eyebrow">{{ selectedGame }} · UNAVAILABLE</p>
        <h1>{{ unavailableContext.title }}目前無法使用</h1>
        <p>
          目前沒有 {{ selectedGame }} 對應的此頁資料或既有頁面。此組合不會載入其他遊戲的預測或排名資料。
        </p>
      </section>

      <!-- Canonical Pages -->
      <DataOperationsPage v-else-if="currentPage === 'data-operations' || currentPage === 'data-center'" />
      <HistoryPage v-else-if="currentPage === 'history' || currentPage === 'draw-history'" />
      <BestReplayPage
        v-else-if="currentPage === 'best-replay'"
        :key="bestReplayResetToken"
        @change="handleBestReplayGameChange"
      />
      <ReplayOverviewPage v-else-if="currentPage === 'replay-overview' || currentPage === 'all-strategy-replay'" />
      <StrategyIntelligencePage v-else-if="currentPage === 'strategy-intelligence'" />
      <B649ReplayPage v-else-if="currentPage === 'b649-replay'" />
      <B649CurrentForecastPage v-else-if="currentPage === 'b649-current-forecast'" />
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
        <template v-else-if="activeNavSection === 'forecast'">
          {{ selectedGame === 'B649'
            ? 'Current B649 ticket sets come from the existing scheduler authority and do not establish future performance.'
            : 'No current forecast is available for ' + selectedGame + '.' }}
        </template>
        <template v-else-if="activeNavSection === 'ranking'">
          Ranking results are descriptive research evidence and do not predict future outcomes.
        </template>
        <template v-else-if="activeNavSection === 'backtest'">
          Historical replay presents stored evidence only; it does not claim future performance.
        </template>
        <template v-else>
          Existing workspace pages remain available through their original hash links.
        </template>
      </div>
      <div>
        <span>MathStatisticalAnalysis · <code>B649 · P638 · T539</code></span>
      </div>
    </footer>
  </div>
</template>
