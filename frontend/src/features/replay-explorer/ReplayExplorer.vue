<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import ErrorState from '../../components/ErrorState.vue'
import MetricCard from '../../components/MetricCard.vue'
import SectionHeader from '../../components/SectionHeader.vue'
import SkeletonLoader from '../../components/SkeletonLoader.vue'

import ReplayCompareView from './components/ReplayCompareView.vue'
import ReplayDetailDrawer from './components/ReplayDetailDrawer.vue'
import ReplayMatrixView from './components/ReplayMatrixView.vue'
import ReplayTableView from './components/ReplayTableView.vue'
import ReplayTrendView from './components/ReplayTrendView.vue'
import type {
  GameCode,
  LoadingState,
  PeriodOption,
  ReplayExplorerAdapter,
  ReplayExplorerItem,
  ReplayQueryParams,
  StrategyOption,
  TicketCount,
  TrendSeries,
  ViewMode,
} from './types'
import { ALL_CANONICAL_TICKET_COUNTS } from './types'

const props = defineProps<{
  adapter: ReplayExplorerAdapter
}>()

// Navigation & Query States
const activeViewMode = ref<ViewMode>('table')
const searchQuery = ref('')
const selectedStrategyIds = ref<string[]>([])
const selectedTicketCounts = ref<TicketCount[]>([])
const isMultiTicketMode = ref(false)
const selectedPeriodKey = ref<string>('')
const selectedFamily = ref<string>('ALL')
const selectedStatus = ref<string>('ALL')
const isStrategyPickerOpen = ref(false)

// Data & Async States
const state = ref<LoadingState>('loading')
const errorMessage = ref('')
const strategiesList = ref<StrategyOption[]>([])
const periodOptions = ref<PeriodOption[]>([])
const familyOptions = ref<string[]>([])
const items = ref<ReplayExplorerItem[]>([])
const trendSeries = ref<TrendSeries[]>([])
const trendLoading = ref(false)

// Inspection & Comparison States
const isDrawerOpen = ref(false)
const activeInspectItem = ref<ReplayExplorerItem | null>(null)
const comparedStrategyIds = ref<string[]>([])

let fetchController: AbortController | undefined
let trendController: AbortController | undefined
let fetchGeneration = 0

// Game code computed
const currentGame = computed<GameCode>(() => props.adapter.game)

// Check if ticket count is available for the current adapter
function isTicketAvailable(count: TicketCount): boolean {
  return props.adapter.availableTicketCounts.includes(count)
}

// Active Period Option
const currentPeriodOption = computed<PeriodOption | undefined>(() => {
  return periodOptions.value.find((p) => p.key === selectedPeriodKey.value)
})

const activePeriodLabel = computed(() => {
  return currentPeriodOption.value?.subLabel || currentPeriodOption.value?.label || selectedPeriodKey.value
})

// Summary metrics
const summaryMetrics = computed(() => {
  const availableItems = items.value.filter((i) => i.isAvailable && i.hitRate !== null)
  let bestRate: number | null = null
  let bestRateLabel: string | null = null

  for (const it of availableItems) {
    if (it.hitRate !== null && (bestRate === null || it.hitRate > bestRate)) {
      bestRate = it.hitRate
      bestRateLabel = it.displayLabel
    }
  }

  return {
    totalLoaded: items.value.length,
    availableCount: availableItems.length,
    bestRateFormatted: bestRate !== null ? `${(bestRate * 100).toFixed(2)}%` : 'Unavailable',
    bestRateLabel: bestRateLabel || '—',
  }
})

// Filter strategies list by search
const filteredStrategyOptions = computed(() => {
  if (!searchQuery.value) return strategiesList.value
  const q = searchQuery.value.toLowerCase()
  return strategiesList.value.filter(
    (s) => s.id.toLowerCase().includes(q) || s.label.toLowerCase().includes(q),
  )
})

// Initialize adapter data
async function initialize(): Promise<void> {
  state.value = 'loading'
  errorMessage.value = ''
  try {
    const initData = await props.adapter.loadInitialState()
    strategiesList.value = initData.strategies
    periodOptions.value = initData.periods
    familyOptions.value = ['ALL', ...(initData.families || [])]
    selectedPeriodKey.value = initData.defaultPeriodKey
    selectedTicketCounts.value = [initData.defaultTicketCount]

    await loadData()
  } catch (err: unknown) {
    state.value = 'error'
    errorMessage.value = err instanceof Error ? err.message : 'Failed to initialize Replay Explorer.'
  }
}

// Load replay explorer items based on active query
async function loadData(): Promise<void> {
  fetchController?.abort()
  const controller = new AbortController()
  fetchController = controller
  const generation = ++fetchGeneration

  state.value = 'loading'
  errorMessage.value = ''

  const params: ReplayQueryParams = {
    game: currentGame.value,
    selectedStrategyIds: selectedStrategyIds.value,
    selectedTicketCounts: selectedTicketCounts.value,
    selectedPeriodKey: selectedPeriodKey.value,
    searchQuery: searchQuery.value,
    methodFamilyFilter: selectedFamily.value,
    statusFilter: selectedStatus.value,
  }

  try {
    const loadedItems = await props.adapter.loadItems(params, controller.signal)
    if (generation !== fetchGeneration) return

    items.value = loadedItems
    state.value = loadedItems.length > 0 ? 'ready' : 'empty'

    // If trend view is active, load trend data
    if (activeViewMode.value === 'trend' && props.adapter.supportsTrend && props.adapter.loadTrendData) {
      void loadTrend(params, loadedItems)
    }
  } catch (err: unknown) {
    if (err instanceof DOMException && err.name === 'AbortError') return
    if (generation !== fetchGeneration) return
    state.value = 'error'
    errorMessage.value = err instanceof Error ? err.message : 'Failed to load replay data.'
  }
}

async function loadTrend(params: ReplayQueryParams, currentItems: ReplayExplorerItem[]): Promise<void> {
  if (!props.adapter.loadTrendData) return
  trendController?.abort()
  const controller = new AbortController()
  trendController = controller

  trendLoading.value = true
  try {
    const series = await props.adapter.loadTrendData(params, currentItems, controller.signal)
    trendSeries.value = series
  } catch {
    trendSeries.value = []
  } finally {
    trendLoading.value = false
  }
}

// Watchers for reactive query update
watch([selectedPeriodKey, selectedFamily, selectedStatus], () => {
  void loadData()
})

watch(activeViewMode, (mode) => {
  if (mode === 'trend' && props.adapter.supportsTrend && props.adapter.loadTrendData && trendSeries.value.length === 0) {
    const params: ReplayQueryParams = {
      game: currentGame.value,
      selectedStrategyIds: selectedStrategyIds.value,
      selectedTicketCounts: selectedTicketCounts.value,
      selectedPeriodKey: selectedPeriodKey.value,
      searchQuery: searchQuery.value,
      methodFamilyFilter: selectedFamily.value,
      statusFilter: selectedStatus.value,
    }
    void loadTrend(params, items.value)
  }
})

// Ticket count controls
function toggleTicketCount(count: TicketCount): void {
  if (!isMultiTicketMode.value) {
    selectedTicketCounts.value = [count]
    void loadData()
    return
  }
  const idx = selectedTicketCounts.value.indexOf(count)
  if (idx >= 0) {
    if (selectedTicketCounts.value.length > 1) {
      selectedTicketCounts.value.splice(idx, 1)
      void loadData()
    }
  } else {
    selectedTicketCounts.value.push(count)
    void loadData()
  }
}

function selectAllAvailableTickets(): void {
  selectedTicketCounts.value = [...props.adapter.availableTicketCounts]
  isMultiTicketMode.value = true
  void loadData()
}

// Strategy multi-selection
function toggleStrategy(id: string): void {
  const idx = selectedStrategyIds.value.indexOf(id)
  if (idx >= 0) {
    selectedStrategyIds.value.splice(idx, 1)
  } else {
    selectedStrategyIds.value.push(id)
  }
  void loadData()
}

function isStrategySelected(id: string): boolean {
  return selectedStrategyIds.value.includes(id)
}

function selectAllAvailableStrategies(): void {
  selectedStrategyIds.value = strategiesList.value.map((s) => s.id)
  void loadData()
}

function clearStrategySelection(): void {
  selectedStrategyIds.value = []
  searchQuery.value = ''
  void loadData()
}

function resetAllFilters(): void {
  selectedStrategyIds.value = []
  searchQuery.value = ''
  selectedFamily.value = 'ALL'
  selectedStatus.value = 'ALL'
  isMultiTicketMode.value = false
  selectedTicketCounts.value = [props.adapter.availableTicketCounts[0] || 1]
  if (periodOptions.value.length > 0) {
    selectedPeriodKey.value = periodOptions.value[0]?.key || ''
  }
  isStrategyPickerOpen.value = false
  void loadData()
}

// Inspect & Compare handlers
function openInspect(item: ReplayExplorerItem): void {
  activeInspectItem.value = item
  isDrawerOpen.value = true
}

function closeInspect(): void {
  isDrawerOpen.value = false
  activeInspectItem.value = null
}

function toggleCompare(strategyId: string): void {
  const idx = comparedStrategyIds.value.indexOf(strategyId)
  if (idx >= 0) {
    comparedStrategyIds.value.splice(idx, 1)
  } else {
    if (comparedStrategyIds.value.length < 4) {
      comparedStrategyIds.value.push(strategyId)
    }
  }
}

function removeCompareStrategy(strategyId: string): void {
  const idx = comparedStrategyIds.value.indexOf(strategyId)
  if (idx >= 0) comparedStrategyIds.value.splice(idx, 1)
}

// Navigation between games
function navigateGame(game: GameCode): void {
  window.location.hash = `#/${game.toLowerCase()}-replay`
}

onMounted(() => {
  void initialize()
})

onBeforeUnmount(() => {
  fetchController?.abort()
  trendController?.abort()
})
</script>

<template>
  <section class="replay-explorer-workspace" :aria-labelledby="`${currentGame.toLowerCase()}-title`">
    <!-- Header Section -->
    <SectionHeader
      :id="`${currentGame.toLowerCase()}-title`"
      :title="adapter.gameTitle"
      :eyebrow="adapter.gameSubtitle"
      :description="adapter.gameDescription"
    >
      <template #actions>
        <!-- Game Switcher Navigation Chips -->
        <div class="game-switcher" role="group" aria-label="Game Switcher">
          <button
            type="button"
            class="button"
            :class="{ 'button--primary': currentGame === 'B649', 'button--quiet': currentGame !== 'B649' }"
            :aria-pressed="currentGame === 'B649'"
            @click="navigateGame('B649')"
          >
            B649
          </button>
          <button
            type="button"
            class="button"
            :class="{ 'button--primary': currentGame === 'P638', 'button--quiet': currentGame !== 'P638' }"
            :aria-pressed="currentGame === 'P638'"
            @click="navigateGame('P638')"
          >
            P638
          </button>
          <button
            type="button"
            class="button"
            :class="{ 'button--primary': currentGame === 'T539', 'button--quiet': currentGame !== 'T539' }"
            :aria-pressed="currentGame === 'T539'"
            @click="navigateGame('T539')"
          >
            T539
          </button>
        </div>
      </template>
    </SectionHeader>

    <!-- Top Summary Metric Cards -->
    <div class="metrics-overview">
      <MetricCard
        label="Strategies Evaluated"
        :value="summaryMetrics.totalLoaded"
        :subvalue="`${summaryMetrics.availableCount} with valid backtest evidence`"
      />
      <MetricCard
        label="Ticket Configuration"
        :value="`${selectedTicketCounts.join(', ')} Tickets`"
        :subvalue="isMultiTicketMode ? 'Multi-ticket mode active' : 'Single ticket slice'"
      />
      <MetricCard
        label="Active Horizon / Period"
        :value="activePeriodLabel"
        :subvalue="currentPeriodOption?.dateRange || 'Canonical historical window'"
      />
      <MetricCard
        label="Top Hit Rate (Observed)"
        :value="summaryMetrics.bestRateFormatted"
        :subvalue="summaryMetrics.bestRateLabel"
      />
    </div>

    <!-- Query & Filter Area -->
    <div class="query-panel">
      <!-- Strategy Selection Row -->
      <div class="filter-row">
        <div class="filter-group filter-group--search">
          <div class="filter-label-row">
            <label for="strategy-search-input" class="filter-label">Strategy Query / Filter:</label>
            <button
              type="button"
              class="text-link-btn"
              @click="isStrategyPickerOpen = !isStrategyPickerOpen"
            >
              {{ isStrategyPickerOpen ? 'Close Picker ▲' : 'Open Strategy List ▼' }}
            </button>
          </div>
          <div class="search-input-wrapper">
            <input
              id="strategy-search-input"
              v-model="searchQuery"
              type="text"
              class="input text-input"
              placeholder="Filter by strategy name or ID…"
              @input="loadData"
            />
            <button
              v-if="searchQuery"
              type="button"
              class="clear-input-btn"
              aria-label="Clear search"
              @click="searchQuery = ''; loadData()"
            >
              ✕
            </button>
          </div>

          <!-- Interactive Strategy Picker Dropdown -->
          <div v-if="isStrategyPickerOpen" class="strategy-dropdown-panel">
            <div class="dropdown-actions">
              <button
                type="button"
                class="button button--small button--quiet"
                @click="selectAllAvailableStrategies"
              >
                Select All Available
              </button>
              <button
                type="button"
                class="button button--small button--quiet"
                @click="clearStrategySelection"
              >
                Clear Selection
              </button>
            </div>
            <div class="strategy-checkbox-list">
              <label
                v-for="s in filteredStrategyOptions"
                :key="s.id"
                class="strategy-checkbox-item"
                :class="{ 'strategy-checkbox-item--selected': isStrategySelected(s.id) }"
              >
                <input
                  type="checkbox"
                  :checked="isStrategySelected(s.id)"
                  @change="toggleStrategy(s.id)"
                />
                <span class="strategy-opt-label">{{ s.label }}</span>
                <span v-if="s.family" class="strategy-opt-family text-muted">{{ s.family }}</span>
              </label>
            </div>
          </div>
        </div>

        <div v-if="familyOptions.length > 1" class="filter-group">
          <label for="family-filter-select" class="filter-label">Method Family:</label>
          <select id="family-filter-select" v-model="selectedFamily" class="select">
            <option v-for="f in familyOptions" :key="f" :value="f">
              {{ f }}
            </option>
          </select>
        </div>

        <div class="filter-group">
          <label for="period-filter-select" class="filter-label">
            {{ adapter.supportsTimeWindowHorizons ? 'Validation Horizon:' : 'Replay Run / Range:' }}
          </label>
          <select id="period-filter-select" v-model="selectedPeriodKey" class="select">
            <option v-for="p in periodOptions" :key="p.key" :value="p.key">
              {{ p.label }} {{ p.subLabel ? `(${p.subLabel})` : '' }}
            </option>
          </select>
        </div>
      </div>

      <!-- Ticket Count Selector Row -->
      <div class="filter-row ticket-count-row">
        <div class="ticket-selector-label-group">
          <span class="filter-label">Ticket Count (1..20):</span>
          <div class="ticket-mode-toggle">
            <label class="checkbox-label">
              <input v-model="isMultiTicketMode" type="checkbox" />
              <span>Multi-Select</span>
            </label>
          </div>
        </div>

        <div class="ticket-buttons-container" role="group" aria-label="Ticket counts 1 to 20">
          <button
            v-for="count in ALL_CANONICAL_TICKET_COUNTS"
            :key="count"
            type="button"
            class="ticket-btn"
            :class="{
              'ticket-btn--selected': selectedTicketCounts.includes(count),
              'ticket-btn--unavailable': !isTicketAvailable(count),
            }"
            :disabled="!isTicketAvailable(count)"
            :title="isTicketAvailable(count) ? `Select ${count} ticket(s)` : `Ticket count ${count} is not recorded in canonical ${currentGame} evidence`"
            @click="toggleTicketCount(count)"
          >
            <span>{{ count }}</span>
          </button>
          <button
            type="button"
            class="button button--small button--quiet preset-btn"
            @click="selectAllAvailableTickets"
          >
            All Available
          </button>
        </div>
      </div>

      <!-- Active Filter Chips & Actions -->
      <div class="active-filters-summary">
        <div class="chips-list">
          <span class="active-filters-title text-muted">Active Filters:</span>
          <span class="chip">
            Game: <strong>{{ currentGame }}</strong>
          </span>
          <span class="chip">
            Period: <strong>{{ activePeriodLabel }}</strong>
          </span>
          <span class="chip">
            Tickets: <strong>{{ selectedTicketCounts.join(', ') }}</strong>
          </span>
          <span v-if="selectedFamily !== 'ALL'" class="chip chip--removable">
            Family: {{ selectedFamily }}
            <button type="button" class="chip-remove-btn" @click="selectedFamily = 'ALL'">✕</button>
          </span>
          <span v-if="selectedStrategyIds.length > 0" class="chip chip--removable">
            {{ selectedStrategyIds.length }} Strategies Selected
            <button type="button" class="chip-remove-btn" @click="clearStrategySelection">✕</button>
          </span>
          <span v-if="searchQuery" class="chip chip--removable">
            Query: "{{ searchQuery }}"
            <button type="button" class="chip-remove-btn" @click="searchQuery = ''; loadData()">✕</button>
          </span>
        </div>

        <div class="filter-actions">
          <button
            type="button"
            class="button button--small button--quiet"
            @click="resetAllFilters"
          >
            Reset All
          </button>
        </div>
      </div>
    </div>

    <!-- View Mode Switcher -->
    <div class="view-mode-bar">
      <div class="tab-list" role="tablist" aria-label="Explorer View Modes">
        <button
          type="button"
          class="button"
          :class="{ 'button--primary': activeViewMode === 'table', 'button--quiet': activeViewMode !== 'table' }"
          :aria-pressed="activeViewMode === 'table'"
          @click="activeViewMode = 'table'"
        >
          Table
        </button>
        <button
          type="button"
          class="button"
          :class="{ 'button--primary': activeViewMode === 'matrix', 'button--quiet': activeViewMode !== 'matrix' }"
          :aria-pressed="activeViewMode === 'matrix'"
          @click="activeViewMode = 'matrix'"
        >
          Matrix
        </button>
        <button
          type="button"
          class="button"
          :class="{ 'button--primary': activeViewMode === 'trend', 'button--quiet': activeViewMode !== 'trend' }"
          :aria-pressed="activeViewMode === 'trend'"
          @click="activeViewMode = 'trend'"
        >
          Trend
        </button>
        <button
          type="button"
          class="button"
          :class="{ 'button--primary': activeViewMode === 'compare', 'button--quiet': activeViewMode !== 'compare' }"
          :aria-pressed="activeViewMode === 'compare'"
          @click="activeViewMode = 'compare'"
        >
          Compare ({{ comparedStrategyIds.length }}/4)
        </button>
      </div>
    </div>

    <!-- Result Views -->
    <div class="explorer-content-area">
      <!-- Loading Skeleton -->
      <div v-if="state === 'loading'" class="loading-state-wrapper">
        <SkeletonLoader :rows="8" />
      </div>

      <!-- Error State -->
      <ErrorState
        v-else-if="state === 'error'"
        title="Failed to Load Replay Evidence"
        :message="errorMessage"
      >
        <button type="button" class="button button--primary" @click="loadData">
          Retry Request
        </button>
      </ErrorState>

      <!-- Active View Modes -->
      <template v-else>
        <!-- TABLE VIEW -->
        <ReplayTableView
          v-if="activeViewMode === 'table'"
          :game="currentGame"
          :items="items"
          :loading="false"
          :selected-for-compare="comparedStrategyIds"
          @inspect="openInspect"
          @toggle-compare="toggleCompare"
        />

        <!-- MATRIX VIEW -->
        <ReplayMatrixView
          v-else-if="activeViewMode === 'matrix'"
          :game="currentGame"
          :items="items"
          :available-ticket-counts="adapter.availableTicketCounts"
          :period-label="activePeriodLabel"
          :loading="false"
          @inspect="openInspect"
        />

        <!-- TREND VIEW -->
        <ReplayTrendView
          v-else-if="activeViewMode === 'trend'"
          :game="currentGame"
          :series="trendSeries"
          :supports-trend="adapter.supportsTrend"
          :trend-unavailable-reason="adapter.trendUnavailableReason"
          :loading="trendLoading"
        />

        <!-- COMPARE VIEW -->
        <ReplayCompareView
          v-else-if="activeViewMode === 'compare'"
          :game="currentGame"
          :items="items"
          :selected-strategy-ids="comparedStrategyIds"
          :loading="false"
          @remove-strategy="removeCompareStrategy"
          @inspect="openInspect"
        />
      </template>
    </div>

    <!-- Strategy Detail Drawer -->
    <ReplayDetailDrawer
      :is-open="isDrawerOpen"
      :item="activeInspectItem"
      :game="currentGame"
      :adapter="adapter"
      @close="closeInspect"
    />
  </section>
</template>

<style scoped>
.replay-explorer-workspace {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
  width: 100%;
  max-width: 100%;
  min-width: 0;
}

.game-switcher {
  display: inline-flex;
  gap: 0.35rem;
  background: rgba(18, 14, 36, 0.92);
  padding: 0.3rem;
  border-radius: var(--radius-lg, 14px);
  border: 1px solid var(--border-color);
  box-shadow: var(--shadow-sm);
}

.game-switcher .button--primary {
  background: var(--gradient-amber);
  box-shadow: var(--shadow-glow-amber);
}

.metrics-overview {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 1rem;
  min-width: 0;
}

.query-panel {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-xl, 20px);
  padding: 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
  min-width: 0;
  box-shadow: var(--shadow-md);
}

.filter-row {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
  align-items: flex-end;
  min-width: 0;
}

.filter-group {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  min-width: 0;
}

.filter-group--search {
  flex: 1 1 320px;
  min-width: min(260px, 100%);
  position: relative;
}

.filter-label-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.filter-label {
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--text-secondary);
}

.text-link-btn {
  background: none;
  border: none;
  color: var(--text-accent);
  font-size: 0.75rem;
  cursor: pointer;
  padding: 0;
}

.text-link-btn:hover {
  text-decoration: underline;
}

.search-input-wrapper {
  position: relative;
  width: 100%;
}

.text-input {
  width: 100%;
  padding-right: 2rem;
}

.clear-input-btn {
  position: absolute;
  right: 0.5rem;
  top: 50%;
  transform: translateY(-50%);
  background: none;
  border: none;
  color: var(--text-secondary);
  cursor: pointer;
}

.strategy-dropdown-panel {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  right: 0;
  background: var(--bg-tertiary);
  border: 1px solid var(--border-hover);
  border-radius: var(--radius-lg, 14px);
  box-shadow: var(--shadow-lg), var(--shadow-glow);
  z-index: 100;
  padding: 0.75rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.dropdown-actions {
  display: flex;
  justify-content: space-between;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.strategy-checkbox-list {
  max-height: 220px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.strategy-checkbox-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.35rem 0.5rem;
  border-radius: var(--radius-sm, 6px);
  font-size: 0.85rem;
  cursor: pointer;
  transition: background 0.15s ease;
}

.strategy-checkbox-item:hover {
  background: rgba(255, 255, 255, 0.05);
}

.strategy-checkbox-item--selected {
  background: rgba(168, 85, 247, 0.18);
  box-shadow: inset 3px 0 0 var(--primary-color);
}

.strategy-opt-label {
  color: var(--text-primary);
  flex-grow: 1;
}

.strategy-opt-family {
  font-size: 0.75rem;
}

.ticket-count-row {
  flex-direction: column;
  align-items: flex-start;
  gap: 0.5rem;
  padding-top: 0.5rem;
  border-top: 1px solid var(--border-subtle);
}

.ticket-selector-label-group {
  display: flex;
  justify-content: space-between;
  width: 100%;
  align-items: center;
}

.checkbox-label {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.8rem;
  color: var(--text-secondary);
  cursor: pointer;
}

.ticket-buttons-container {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  align-items: center;
}

.ticket-btn {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-sm, 6px);
  background: rgba(25, 20, 50, 0.78);
  border: 1px solid var(--border-color);
  color: var(--text-secondary);
  font-size: 0.85rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s ease;
}

.ticket-btn:hover:not(:disabled) {
  background: rgba(168, 85, 247, 0.2);
  border-color: var(--border-hover);
  color: var(--text-primary);
}

.ticket-btn--selected {
  background: var(--gradient-primary) !important;
  color: #ffffff !important;
  border-color: transparent !important;
  box-shadow: 0 0 14px rgba(168, 85, 247, 0.42);
  font-weight: 700;
}

.ticket-btn--unavailable {
  opacity: 0.3;
  cursor: not-allowed;
  background: rgba(9, 7, 20, 0.45);
  border-color: var(--border-subtle);
}

.preset-btn {
  margin-left: 0.5rem;
}

.active-filters-summary {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 0.75rem;
  border-top: 1px solid var(--border-subtle);
  flex-wrap: wrap;
  gap: 0.75rem;
}

.chips-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  align-items: center;
}

.active-filters-title {
  font-size: 0.8rem;
  margin-right: 0.25rem;
}

.chip {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: var(--radius-sm, 6px);
  padding: 0.15rem 0.5rem;
  font-size: 0.75rem;
  color: var(--text-secondary);
}

.chip-remove-btn {
  background: none;
  border: none;
  color: var(--text-secondary);
  cursor: pointer;
  padding: 0;
  margin-left: 0.2rem;
}

.chip-remove-btn:hover {
  color: var(--accent-color);
}

.view-mode-bar {
  display: flex;
  justify-content: flex-start;
}

.explorer-content-area {
  width: 100%;
  min-width: 0;
}

.loading-state-wrapper {
  padding: 2rem 0;
}

.text-muted {
  color: var(--text-secondary);
}
</style>
