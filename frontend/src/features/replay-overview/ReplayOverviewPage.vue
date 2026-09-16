<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import DataTable from '../../components/DataTable.vue'
import EmptyState from '../../components/EmptyState.vue'
import ErrorState from '../../components/ErrorState.vue'
import MetricCard from '../../components/MetricCard.vue'
import SectionHeader from '../../components/SectionHeader.vue'
import SkeletonLoader from '../../components/SkeletonLoader.vue'
import StatusBadge from '../../components/StatusBadge.vue'

import ReplayOverviewMatrix from './ReplayOverviewMatrix.vue'
import {
  REPLAY_OVERVIEW_TICKET_COUNTS,
  REPLAY_OVERVIEW_WINDOWS,
  type ReplayOverviewGame,
  type ReplayOverviewMatrixRow,
  type ReplayOverviewStrategyItem,
  type ReplayOverviewSummary,
  type ReplayOverviewTicketCount,
  type ReplayOverviewWindow,
  type SortDirection,
  type SortField,
} from './types'
import {
  fetchReplayOverviewData,
  fetchReplayOverviewMatrixData,
  isDimensionAvailable,
} from '../../api/replayOverview'

type ViewMode = 'table' | 'matrix'
type LoadingState = 'loading' | 'ready' | 'empty' | 'error' | 'unavailable'

// Dimension selections
const selectedGame = ref<ReplayOverviewGame>('B649')
const selectedTicketCount = ref<ReplayOverviewTicketCount>(10)
const selectedWindow = ref<ReplayOverviewWindow>('FULL')
const activeViewMode = ref<ViewMode>('table')

// Filter states
const searchQuery = ref('')
const selectedStatusFilter = ref<string>('ALL')
const selectedComparabilityFilter = ref<'ALL' | 'ABOVE_BASELINE' | 'RANKED_ONLY'>('ALL')
const selectedCoverageFilter = ref<'ALL' | '90' | '95' | '100'>('ALL')

// Sorting states
const sortField = ref<SortField>('officialRank')
const sortDirection = ref<SortDirection>('asc')

// Async data states
const state = ref<LoadingState>('loading')
const errorMessage = ref('')
const rawItems = ref<ReplayOverviewStrategyItem[]>([])
const matrixRows = ref<ReplayOverviewMatrixRow[]>([])
const summary = ref<ReplayOverviewSummary | null>(null)
let abortController: AbortController | undefined
let fetchGeneration = 0

const isCurrentDimensionAvailable = computed(() => {
  return isDimensionAvailable(selectedGame.value, selectedTicketCount.value)
})

const isUserSortActive = computed(() => {
  return sortField.value !== 'officialRank' || sortDirection.value !== 'asc'
})

const activeWindowDef = computed(() => {
  return REPLAY_OVERVIEW_WINDOWS.find((w) => w.key === selectedWindow.value) ?? REPLAY_OVERVIEW_WINDOWS[0]
})

// Filtered and Sorted items
const filteredAndSortedItems = computed(() => {
  let result = [...rawItems.value]

  // 1. Text Search Filter
  const q = searchQuery.value.trim().toLowerCase()
  if (q) {
    result = result.filter(
      (item) =>
        item.strategyId.toLowerCase().includes(q) ||
        item.legacyMethodId.toLowerCase().includes(q) ||
        item.methodFamily.toLowerCase().includes(q),
    )
  }

  // 2. Reproduction Status Filter
  if (selectedStatusFilter.value !== 'ALL') {
    result = result.filter((item) => item.reproductionStatus === selectedStatusFilter.value)
  }

  // 3. Comparability Filter
  if (selectedComparabilityFilter.value === 'ABOVE_BASELINE') {
    result = result.filter(
      (item) =>
        item.officialRandomBaselineDelta !== null && item.officialRandomBaselineDelta > 0,
    )
  } else if (selectedComparabilityFilter.value === 'RANKED_ONLY') {
    result = result.filter((item) => item.officialRank !== null)
  }

  // 4. Coverage Filter
  if (selectedCoverageFilter.value === '90') {
    result = result.filter((item) => item.coverage !== null && item.coverage >= 0.9)
  } else if (selectedCoverageFilter.value === '95') {
    result = result.filter((item) => item.coverage !== null && item.coverage >= 0.95)
  } else if (selectedCoverageFilter.value === '100') {
    result = result.filter((item) => item.coverage !== null && item.coverage >= 0.999)
  }

  // 5. User Presentation Sorting (Does NOT alter officialRank field)
  result.sort((a, b) => {
    let comparison = 0

    if (sortField.value === 'officialRank') {
      const rankA = a.officialRank ?? 999999
      const rankB = b.officialRank ?? 999999
      comparison = rankA - rankB
    } else if (sortField.value === 'hitRate') {
      const rateA = a.officialAnyPrizeRate ?? -1
      const rateB = b.officialAnyPrizeRate ?? -1
      comparison = rateA - rateB
    } else if (sortField.value === 'successes') {
      const succA = a.officialAnyPrizeCount ?? -1
      const succB = b.officialAnyPrizeCount ?? -1
      comparison = succA - succB
    } else if (sortField.value === 'observations') {
      const obsA = a.effectiveBacktestDrawCount ?? -1
      const obsB = b.effectiveBacktestDrawCount ?? -1
      comparison = obsA - obsB
    } else if (sortField.value === 'coverage') {
      const covA = a.coverage ?? -1
      const covB = b.coverage ?? -1
      comparison = covA - covB
    } else if (sortField.value === 'baselineDelta') {
      const delA = a.officialRandomBaselineDelta ?? -999
      const delB = b.officialRandomBaselineDelta ?? -999
      comparison = delA - delB
    } else if (sortField.value === 'strategyId') {
      comparison = a.strategyId.localeCompare(b.strategyId)
    }

    return sortDirection.value === 'asc' ? comparison : -comparison
  })

  return result
})

function handleSort(field: SortField): void {
  if (sortField.value === field) {
    sortDirection.value = sortDirection.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortField.value = field
    sortDirection.value = field === 'officialRank' ? 'asc' : 'desc'
  }
}

function resetToOfficialRank(): void {
  sortField.value = 'officialRank'
  sortDirection.value = 'asc'
}

function resetFilters(): void {
  searchQuery.value = ''
  selectedStatusFilter.value = 'ALL'
  selectedComparabilityFilter.value = 'ALL'
  selectedCoverageFilter.value = 'ALL'
}

async function loadData(): Promise<void> {
  abortController?.abort()
  const controller = new AbortController()
  abortController = controller
  const generation = ++fetchGeneration

  state.value = 'loading'
  errorMessage.value = ''

  try {
    if (activeViewMode.value === 'matrix') {
      const matrixResult = await fetchReplayOverviewMatrixData(
        selectedGame.value,
        selectedWindow.value,
        controller.signal,
      )
      if (generation !== fetchGeneration) return

      matrixRows.value = matrixResult.rows
      if (!matrixResult.isDimensionAvailable) {
        state.value = 'unavailable'
      } else {
        state.value = 'ready'
      }
    } else {
      const dataResult = await fetchReplayOverviewData(
        selectedGame.value,
        selectedTicketCount.value,
        selectedWindow.value,
        controller.signal,
      )
      if (generation !== fetchGeneration) return

      rawItems.value = dataResult.items
      summary.value = dataResult.summary

      if (!dataResult.summary.isDimensionAvailable) {
        state.value = 'unavailable'
      } else if (dataResult.items.length === 0) {
        state.value = 'empty'
      } else {
        state.value = 'ready'
      }
    }
  } catch (err: unknown) {
    if (generation !== fetchGeneration) return
    if (err instanceof DOMException && err.name === 'AbortError') return
    state.value = 'error'
    errorMessage.value = err instanceof Error ? err.message : 'Failed to load Replay Overview data.'
  }
}

watch(
  [selectedGame, selectedTicketCount, selectedWindow, activeViewMode],
  () => {
    loadData()
  },
  { immediate: true },
)

onMounted(() => {
  // Initial load triggered by watcher
})

onBeforeUnmount(() => {
  abortController?.abort()
})
</script>

<template>
  <div class="replay-overview-page" data-testid="replay-overview-page">
    <!-- Header Section -->
    <SectionHeader
      id="replay-overview-title"
      title="Replay Overview · 縱覽歷史回放"
      description="Full canonical multi-ticket ranking table across 10, 15, and 20 ticket allocations. Examines performance and baseline superiority for the complete strategy universe."
    >
      <template #actions>
        <div class="view-mode-tabs" role="tablist" aria-label="View Mode">
          <button
            type="button"
            role="tab"
            class="tab-btn"
            :class="{ 'tab-btn--active': activeViewMode === 'table' }"
            :aria-selected="activeViewMode === 'table'"
            data-testid="view-mode-table"
            @click="activeViewMode = 'table'"
          >
            All-Strategy Table
          </button>
          <button
            type="button"
            role="tab"
            class="tab-btn"
            :class="{ 'tab-btn--active': activeViewMode === 'matrix' }"
            :aria-selected="activeViewMode === 'matrix'"
            data-testid="view-mode-matrix"
            @click="activeViewMode = 'matrix'"
          >
            10 / 15 / 20 Matrix
          </button>
        </div>
      </template>
    </SectionHeader>

    <!-- Research Disclaimer Banner -->
    <div class="disclaimer-card" role="note" data-testid="disclaimer-card">
      <div class="disclaimer-card__icon" aria-hidden="true">🔬</div>
      <div class="disclaimer-card__content">
        <strong>Research Audit Notice:</strong>
        <span>歷史成功率、排名與隨機基準差異僅供描述性研究，不構成未來預測、推薦、上線決策或中獎保證。</span>
      </div>
    </div>

    <!-- Main Dimension Selectors Control Panel -->
    <div class="dimension-selectors-card">
      <!-- Game Selector -->
      <div class="selector-group">
        <label class="selector-group__label">Game / 彩種</label>
        <div class="pill-segmented-control" role="group" aria-label="Game selector">
          <button
            type="button"
            class="pill-btn"
            :class="{ 'pill-btn--active': selectedGame === 'B649' }"
            data-testid="game-select-b649"
            @click="selectedGame = 'B649'"
          >
            大樂透 B649
          </button>
          <button
            type="button"
            class="pill-btn"
            :class="{ 'pill-btn--active': selectedGame === 'P638' }"
            data-testid="game-select-p638"
            @click="selectedGame = 'P638'"
          >
            威力彩 P638
          </button>
          <button
            type="button"
            class="pill-btn"
            :class="{ 'pill-btn--active': selectedGame === 'T539' }"
            data-testid="game-select-t539"
            @click="selectedGame = 'T539'"
          >
            今彩539 T539
          </button>
        </div>
      </div>

      <!-- Ticket Count Selector (Table View Mode) -->
      <div v-if="activeViewMode === 'table'" class="selector-group">
        <label class="selector-group__label">Ticket Allocation / 注數</label>
        <div class="pill-segmented-control" role="group" aria-label="Ticket count selector">
          <button
            v-for="count in REPLAY_OVERVIEW_TICKET_COUNTS"
            :key="count"
            type="button"
            class="pill-btn"
            :class="{ 'pill-btn--active': selectedTicketCount === count }"
            :data-testid="`ticket-select-${count}`"
            @click="selectedTicketCount = count"
          >
            {{ count }} 注
          </button>
        </div>
      </div>

      <!-- Window Selector -->
      <div class="selector-group">
        <label class="selector-group__label">Evaluation Window / 回放窗口</label>
        <div class="pill-segmented-control" role="group" aria-label="Evaluation window selector">
          <button
            type="button"
            class="pill-btn"
            :class="{ 'pill-btn--active': selectedWindow === 'FULL' }"
            data-testid="window-select-full"
            @click="selectedWindow = 'FULL'"
          >
            FULL
          </button>
          <button
            type="button"
            class="pill-btn"
            :class="{ 'pill-btn--active': selectedWindow === 'RECENT_750' }"
            data-testid="window-select-750"
            @click="selectedWindow = 'RECENT_750'"
          >
            750
          </button>
          <button
            type="button"
            class="pill-btn"
            :class="{ 'pill-btn--active': selectedWindow === 'RECENT_300' }"
            data-testid="window-select-300"
            @click="selectedWindow = 'RECENT_300'"
          >
            300
          </button>
          <button
            type="button"
            class="pill-btn"
            :class="{ 'pill-btn--active': selectedWindow === 'RECENT_50' }"
            data-testid="window-select-50"
            @click="selectedWindow = 'RECENT_50'"
          >
            50
          </button>
        </div>
      </div>
    </div>

    <!-- Summary KPI Cards -->
    <div v-if="state === 'ready' && summary" class="kpi-grid" data-testid="summary-kpis">
      <MetricCard
        label="Dimension"
        :value="`${summary.game} · ${summary.ticketCount} Tickets · ${activeWindowDef.shortLabel}`"
        variant="accent"
      />
      <MetricCard
        label="Strategies Available"
        :value="summary.totalStrategies"
        helper="Total strategy universe in catalog"
      />
      <MetricCard
        label="Strategies Ranked"
        :value="summary.rankedStrategies"
        helper="With official canonical ranking"
      />
      <MetricCard
        label="Average Coverage"
        :value="summary.observationCoverageRate !== null ? `${(summary.observationCoverageRate * 100).toFixed(1)}%` : 'Unavailable'"
        helper="Historical draw observation coverage"
      />
      <MetricCard
        v-if="summary.topStrategy"
        label="Rank #1 Leader"
        :value="summary.topStrategy.strategyId"
        :helper="`Hit Rate: ${summary.topStrategy.hitRateFormatted}`"
        variant="success"
      />
    </div>

    <!-- Unavailable Evidence State for Unsupported Dimension -->
    <div
      v-if="state === 'unavailable' || (!isCurrentDimensionAvailable && activeViewMode === 'table')"
      class="evidence-unavailable-state"
      data-testid="evidence-unavailable-state"
      role="alert"
    >
      <div class="unavailable-card">
        <div class="unavailable-card__badge-row">
          <StatusBadge status="EVIDENCE UNAVAILABLE" variant="danger" size="md" />
          <span class="unavailable-card__source">Canonical Source: <code>{{ summary?.canonicalSource ?? 'Upstream API' }}</code></span>
        </div>
        <h3 class="unavailable-card__title">
          Evidence Unavailable for {{ selectedGame }} ({{ selectedTicketCount }} Tickets)
        </h3>
        <p class="unavailable-card__reason">
          {{ summary?.unavailableReason ?? `No canonical ${selectedTicketCount}-ticket backtest evidence is recorded in ${selectedGame} upstream authority.` }}
        </p>
        <div class="unavailable-card__notes">
          <ul>
            <li><strong>Upstream Status:</strong> Multi-ticket replay records are only pinned and generated for B649 in the current canonical authority.</li>
            <li><strong>No Synthetic Data:</strong> UI strictly presents upstream authority values only; missing multi-ticket backtest rows are not fabricated.</li>
            <li><strong>Value Invariant:</strong> Missing data is presented as <code>EVIDENCE UNAVAILABLE</code> (never represented as 0% or Rank 0).</li>
          </ul>
        </div>
      </div>
    </div>

    <!-- Error State -->
    <ErrorState
      v-else-if="state === 'error'"
      title="Failed to Load Replay Overview"
      :message="errorMessage"
      data-testid="error-state"
      @retry="loadData"
    />

    <!-- Loading State -->
    <div v-else-if="state === 'loading'" class="loading-container" data-testid="loading-state">
      <SkeletonLoader variant="card" height="120px" />
      <SkeletonLoader variant="table" :rows="8" />
    </div>

    <!-- Matrix View Mode -->
    <div v-else-if="activeViewMode === 'matrix'">
      <!-- Search Filter for Matrix -->
      <div class="matrix-filter-bar">
        <input
          v-model="searchQuery"
          type="search"
          placeholder="Filter strategies by ID or family…"
          class="search-input"
          data-testid="matrix-search-input"
        />
        <button
          v-if="searchQuery"
          type="button"
          class="button button--ghost"
          @click="searchQuery = ''"
        >
          Clear
        </button>
      </div>

      <ReplayOverviewMatrix
        :rows="matrixRows"
        :window="selectedWindow"
        :loading="false"
        :is-dimension-available="isDimensionAvailable(selectedGame, 10)"
        :unavailable-reason="summary?.unavailableReason"
        :search-query="searchQuery"
      />
    </div>

    <!-- Table View Mode Content -->
    <div v-else-if="state === 'ready'">
      <!-- Filter Bar & Presentation Sort Controls -->
      <div class="controls-panel">
        <div class="filters-row">
          <!-- Text Search -->
          <div class="filter-item filter-item--grow">
            <input
              v-model="searchQuery"
              type="search"
              placeholder="Search strategy ID, method, or family…"
              class="search-input"
              data-testid="search-input"
            />
          </div>

          <!-- Status Filter -->
          <div class="filter-item">
            <label class="filter-label">Status</label>
            <select
              v-model="selectedStatusFilter"
              class="select-control"
              data-testid="reproduction-status-filter"
            >
              <option value="ALL">All Statuses (全部)</option>
              <option value="BACKTESTED">BACKTESTED (已回放)</option>
              <option value="CLOSED_UNEXECUTABLE">CLOSED_UNEXECUTABLE (排除)</option>
              <option value="DUPLICATE_ALIAS">DUPLICATE_ALIAS (重複別名)</option>
            </select>
          </div>

          <!-- Comparability Filter -->
          <div class="filter-item">
            <label class="filter-label">Comparability</label>
            <select
              v-model="selectedComparabilityFilter"
              class="select-control"
              data-testid="comparability-filter"
            >
              <option value="ALL">All Rows (全部)</option>
              <option value="ABOVE_BASELINE">Above Baseline Only (優於基準)</option>
              <option value="RANKED_ONLY">Ranked Only (僅顯示排名)</option>
            </select>
          </div>

          <!-- Coverage Filter -->
          <div class="filter-item">
            <label class="filter-label">Min Coverage</label>
            <select
              v-model="selectedCoverageFilter"
              class="select-control"
              data-testid="coverage-filter"
            >
              <option value="ALL">All Coverage</option>
              <option value="90">≥ 90%</option>
              <option value="95">≥ 95%</option>
              <option value="100">100% Complete</option>
            </select>
          </div>

          <!-- Reset Filters Button -->
          <button
            v-if="searchQuery || selectedStatusFilter !== 'ALL' || selectedComparabilityFilter !== 'ALL' || selectedCoverageFilter !== 'ALL'"
            type="button"
            class="button button--ghost"
            data-testid="reset-filters-button"
            @click="resetFilters"
          >
            Reset Filters
          </button>
        </div>

        <!-- Sorting & Presentation State Notice -->
        <div class="sort-status-bar">
          <div class="sort-status-info">
            <span class="row-count-badge">
              Showing <strong>{{ filteredAndSortedItems.length }}</strong> of <strong>{{ rawItems.length }}</strong> strategies
            </span>
            <span
              v-if="isUserSortActive"
              class="user-sort-badge"
              data-testid="user-sort-active-badge"
            >
              Presentation Sort: <code>{{ sortField }} ({{ sortDirection.toUpperCase() }})</code> — Official Ranks Preserved
            </span>
            <span v-else class="canonical-sort-badge">
              ✓ Canonical Official Rank Order
            </span>
          </div>

          <button
            v-if="isUserSortActive"
            type="button"
            class="button button--secondary button--sm"
            data-testid="reset-sort-button"
            @click="resetToOfficialRank"
          >
            Reset to Official Rank
          </button>
        </div>
      </div>

      <!-- Empty State if Filters eliminate all rows -->
      <div v-if="filteredAndSortedItems.length === 0" class="no-rows-container">
        <EmptyState
          title="No Strategies Match Filters"
          description="None of the upstream canonical rows match your active search and filter criteria."
          data-testid="empty-filtered-state"
        >
          <button type="button" class="button button--primary" @click="resetFilters">
            Clear All Filters
          </button>
        </EmptyState>
      </div>

      <!-- All-Strategy Ranking Table -->
      <DataTable
        v-else
        caption="All-Strategy Historical Replay Ranking Table"
        min-width="960px"
      >
        <template #head>
          <tr>
            <th
              scope="col"
              style="width: 90px; cursor: pointer;"
              @click="handleSort('officialRank')"
            >
              Official Rank
              <span v-if="sortField === 'officialRank'">{{ sortDirection === 'asc' ? '↑' : '↓' }}</span>
            </th>
            <th
              scope="col"
              style="min-width: 240px; cursor: pointer;"
              @click="handleSort('strategyId')"
            >
              Strategy ID & Family
              <span v-if="sortField === 'strategyId'">{{ sortDirection === 'asc' ? '↑' : '↓' }}</span>
            </th>
            <th
              scope="col"
              style="min-width: 110px; text-align: right; cursor: pointer;"
              @click="handleSort('hitRate')"
            >
              Historical Hit Rate
              <span v-if="sortField === 'hitRate'">{{ sortDirection === 'asc' ? '↑' : '↓' }}</span>
            </th>
            <th
              scope="col"
              style="min-width: 120px; text-align: right; cursor: pointer;"
              @click="handleSort('successes')"
            >
              Success / Obs
              <span v-if="sortField === 'successes'">{{ sortDirection === 'asc' ? '↑' : '↓' }}</span>
            </th>
            <th
              scope="col"
              style="min-width: 90px; text-align: right; cursor: pointer;"
              @click="handleSort('coverage')"
            >
              Coverage
              <span v-if="sortField === 'coverage'">{{ sortDirection === 'asc' ? '↑' : '↓' }}</span>
            </th>
            <th scope="col" style="min-width: 100px; text-align: right;">
              Baseline Rate
            </th>
            <th
              scope="col"
              style="min-width: 110px; text-align: right; cursor: pointer;"
              @click="handleSort('baselineDelta')"
            >
              Baseline Delta
              <span v-if="sortField === 'baselineDelta'">{{ sortDirection === 'asc' ? '↑' : '↓' }}</span>
            </th>
            <th scope="col" style="min-width: 120px;">
              Best Hit
            </th>
            <th scope="col" style="min-width: 130px;">
              Status
            </th>
          </tr>
        </template>

        <template #default>
          <tr
            v-for="item in filteredAndSortedItems"
            :key="item.id"
            :data-testid="`table-row-${item.strategyId}`"
            :class="{ 'row--top3': item.officialRank !== null && item.officialRank <= 3 }"
          >
            <!-- Official Rank Column -->
            <td class="cell--rank">
              <span
                v-if="item.officialRank !== null"
                class="rank-badge"
                :class="{
                  'rank-badge--1': item.officialRank === 1,
                  'rank-badge--2': item.officialRank === 2,
                  'rank-badge--3': item.officialRank === 3,
                }"
              >
                #{{ item.officialRank }}
              </span>
              <span v-else class="rank-badge--unranked">--</span>
            </td>

            <!-- Strategy ID Column -->
            <td>
              <div class="strategy-ident">
                <span class="strategy-ident__id" :title="item.strategyId">{{ item.strategyId }}</span>
                <div class="strategy-ident__sub">
                  <span class="strategy-ident__family">{{ item.methodFamily }}</span>
                  <span v-if="item.legacyMethodId" class="strategy-ident__method" :title="item.legacyMethodId">
                    {{ item.legacyMethodId }}
                  </span>
                </div>
              </div>
            </td>

            <!-- Hit Rate Column -->
            <td class="cell--number">
              <span
                v-if="item.isAvailable"
                class="value-mono font-bold"
                data-testid="row-hit-rate"
              >
                {{ item.officialAnyPrizeRateFormatted }}
              </span>
              <span v-else class="text-muted">Unavailable</span>
            </td>

            <!-- Successes / Observations Column -->
            <td class="cell--number">
              <span v-if="item.isAvailable" class="value-mono">
                {{ item.officialAnyPrizeCount ?? item.successCount ?? '-' }} / {{ item.effectiveBacktestDrawCount ?? '-' }}
              </span>
              <span v-else class="text-muted">-</span>
            </td>

            <!-- Coverage Column -->
            <td class="cell--number">
              <span v-if="item.isAvailable" class="value-mono">
                {{ item.coverageFormatted }}
              </span>
              <span v-else class="text-muted">-</span>
            </td>

            <!-- Baseline Rate Column -->
            <td class="cell--number">
              <span v-if="item.isAvailable" class="value-mono text-muted">
                {{ item.officialRandomBaselineProbabilityFormatted }}
              </span>
              <span v-else class="text-muted">-</span>
            </td>

            <!-- Baseline Delta Column -->
            <td class="cell--number">
              <span
                v-if="item.isAvailable"
                class="value-mono font-bold"
                :class="{
                  'text-success': item.officialRandomBaselineDelta !== null && item.officialRandomBaselineDelta > 0,
                  'text-danger': item.officialRandomBaselineDelta !== null && item.officialRandomBaselineDelta < 0,
                  'text-muted': item.officialRandomBaselineDelta === 0,
                }"
              >
                {{ item.officialRandomBaselineDeltaFormatted }}
              </span>
              <span v-else class="text-muted">-</span>
            </td>

            <!-- Best Hit Column -->
            <td>
              <span v-if="item.isAvailable" class="best-hit-tag">
                {{ item.bestHit }}
              </span>
              <span v-else class="text-muted">-</span>
            </td>

            <!-- Evidence Status Column -->
            <td>
              <StatusBadge :status="item.evidenceStatus" size="sm" />
            </td>
          </tr>
        </template>
      </DataTable>
    </div>
  </div>
</template>

<style scoped>
.replay-overview-page {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
  padding: 1.5rem;
  max-width: 1400px;
  margin: 0 auto;
}

.view-mode-tabs {
  display: inline-flex;
  background: var(--color-surface-sunken, rgba(255, 255, 255, 0.04));
  border: 1px solid var(--color-border-subtle, rgba(255, 255, 255, 0.1));
  border-radius: 8px;
  padding: 0.25rem;
  gap: 0.25rem;
}

.tab-btn {
  padding: 0.5rem 1rem;
  border-radius: 6px;
  border: none;
  background: transparent;
  color: var(--color-text-muted, #94a3b8);
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s ease;
}

.tab-btn:hover {
  color: var(--color-text-primary, #f8fafc);
}

.tab-btn--active {
  background: var(--color-surface-raised, rgba(255, 255, 255, 0.12));
  color: var(--color-text-primary, #f8fafc);
  font-weight: 600;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
}

.disclaimer-card {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem 1.25rem;
  background: rgba(56, 189, 248, 0.06);
  border: 1px solid rgba(56, 189, 248, 0.2);
  border-radius: 8px;
  font-size: 0.825rem;
  color: var(--color-text-secondary, #cbd5e1);
}

.disclaimer-card__icon {
  font-size: 1.1rem;
}

.dimension-selectors-card {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 1.5rem;
  padding: 1.25rem;
  background: var(--color-surface-raised, rgba(255, 255, 255, 0.03));
  border: 1px solid var(--color-border-subtle, rgba(255, 255, 255, 0.08));
  border-radius: 12px;
}

.selector-group {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.selector-group__label {
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--color-text-muted, #94a3b8);
}

.pill-segmented-control {
  display: inline-flex;
  background: var(--color-surface-sunken, rgba(0, 0, 0, 0.25));
  border: 1px solid var(--color-border-subtle, rgba(255, 255, 255, 0.1));
  border-radius: 8px;
  padding: 0.2rem;
  gap: 0.2rem;
}

.pill-btn {
  padding: 0.4rem 0.85rem;
  border-radius: 6px;
  border: none;
  background: transparent;
  color: var(--color-text-muted, #94a3b8);
  font-size: 0.85rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s ease;
}

.pill-btn:hover {
  color: var(--color-text-primary, #f8fafc);
}

.pill-btn--active {
  background: var(--color-accent, #38bdf8);
  color: #0f172a;
  font-weight: 700;
}

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1rem;
}

.evidence-unavailable-state {
  margin-top: 1rem;
}

.unavailable-card {
  padding: 2rem;
  background: var(--color-surface-sunken, rgba(255, 255, 255, 0.02));
  border: 1px solid var(--color-border-subtle, rgba(255, 255, 255, 0.1));
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.unavailable-card__badge-row {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.unavailable-card__source {
  font-size: 0.8rem;
  color: var(--color-text-muted, #94a3b8);
}

.unavailable-card__title {
  margin: 0;
  font-size: 1.25rem;
  color: var(--color-text-primary, #f8fafc);
}

.unavailable-card__reason {
  margin: 0;
  font-size: 0.95rem;
  color: var(--color-text-secondary, #cbd5e1);
  line-height: 1.5;
}

.unavailable-card__notes {
  margin-top: 0.5rem;
  padding: 1rem;
  background: var(--color-surface-raised, rgba(255, 255, 255, 0.03));
  border-radius: 8px;
  font-size: 0.85rem;
  color: var(--color-text-muted, #94a3b8);
}

.unavailable-card__notes ul {
  margin: 0;
  padding-left: 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.controls-panel {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  background: var(--color-surface-raised, rgba(255, 255, 255, 0.02));
  border: 1px solid var(--color-border-subtle, rgba(255, 255, 255, 0.06));
  border-radius: 10px;
  padding: 1rem;
}

.filters-row {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 1rem;
}

.filter-item {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.filter-item--grow {
  flex: 1 1 240px;
}

.filter-label {
  font-size: 0.75rem;
  font-weight: 500;
  color: var(--color-text-muted, #94a3b8);
}

.search-input {
  width: 100%;
  padding: 0.5rem 0.75rem;
  background: var(--color-surface-sunken, rgba(0, 0, 0, 0.2));
  border: 1px solid var(--color-border-subtle, rgba(255, 255, 255, 0.15));
  border-radius: 6px;
  color: var(--color-text-primary, #f8fafc);
  font-size: 0.875rem;
}

.select-control {
  padding: 0.5rem 0.75rem;
  background: var(--color-surface-sunken, rgba(0, 0, 0, 0.2));
  border: 1px solid var(--color-border-subtle, rgba(255, 255, 255, 0.15));
  border-radius: 6px;
  color: var(--color-text-primary, #f8fafc);
  font-size: 0.875rem;
  min-width: 160px;
}

.sort-status-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding-top: 0.5rem;
  border-top: 1px solid var(--color-border-subtle, rgba(255, 255, 255, 0.05));
}

.sort-status-info {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.row-count-badge {
  font-size: 0.825rem;
  color: var(--color-text-muted, #94a3b8);
}

.user-sort-badge {
  font-size: 0.8rem;
  color: #f59e0b;
  background: rgba(245, 158, 11, 0.1);
  padding: 0.2rem 0.6rem;
  border-radius: 4px;
  border: 1px solid rgba(245, 158, 11, 0.2);
}

.canonical-sort-badge {
  font-size: 0.8rem;
  color: var(--color-success, #4ade80);
}

.cell--rank {
  text-align: center;
  vertical-align: middle;
}

.rank-badge {
  display: inline-block;
  font-size: 0.85rem;
  font-weight: 700;
  padding: 0.15rem 0.5rem;
  border-radius: 6px;
  color: var(--color-text-primary, #f8fafc);
  background: var(--color-surface-raised, rgba(255, 255, 255, 0.08));
}

.rank-badge--1 {
  background: linear-gradient(135deg, #fbbf24, #d97706);
  color: #0f172a;
}

.rank-badge--2 {
  background: linear-gradient(135deg, #cbd5e1, #94a3b8);
  color: #0f172a;
}

.rank-badge--3 {
  background: linear-gradient(135deg, #d97706, #b45309);
  color: #ffffff;
}

.rank-badge--unranked {
  color: var(--color-text-muted, #64748b);
  font-size: 0.85rem;
}

.strategy-ident {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.strategy-ident__id {
  font-family: var(--font-mono, monospace);
  font-weight: 600;
  font-size: 0.85rem;
  color: var(--color-text-primary, #f8fafc);
  max-width: 320px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.strategy-ident__sub {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.75rem;
  color: var(--color-text-muted, #94a3b8);
}

.strategy-ident__family {
  background: var(--color-surface-raised, rgba(255, 255, 255, 0.05));
  padding: 0.05rem 0.35rem;
  border-radius: 4px;
}

.strategy-ident__method {
  max-width: 180px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.cell--number {
  text-align: right;
  vertical-align: middle;
}

.value-mono {
  font-family: var(--font-mono, monospace);
  font-size: 0.875rem;
}

.font-bold {
  font-weight: 700;
}

.text-success {
  color: var(--color-success, #4ade80);
}

.text-danger {
  color: var(--color-danger, #f87171);
}

.text-muted {
  color: var(--color-text-muted, #64748b);
}

.best-hit-tag {
  font-size: 0.8rem;
  background: var(--color-surface-raised, rgba(255, 255, 255, 0.05));
  padding: 0.15rem 0.45rem;
  border-radius: 4px;
  color: var(--color-text-secondary, #cbd5e1);
}

.row--top3 {
  background: rgba(56, 189, 248, 0.02);
}

.matrix-filter-bar {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-bottom: 1rem;
  max-width: 400px;
}
</style>
