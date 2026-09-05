<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import EmptyState from '../../components/EmptyState.vue'
import ErrorState from '../../components/ErrorState.vue'
import MetricCard from '../../components/MetricCard.vue'
import SectionHeader from '../../components/SectionHeader.vue'
import SkeletonLoader from '../../components/SkeletonLoader.vue'

import {
  CANONICAL_TICKET_COUNTS,
  LOTTERY_OPTIONS,
  WINDOW_OPTIONS,
  fetchCrossWindowData,
  fetchMultiTicketMatrix,
  fetchRankingData,
  type CrossWindowData,
  type LotteryType,
  type MatrixRow,
  type RankingRow,
  type RankingWindow,
  type TicketCount,
} from '../../api/rankingMatrix'
import CrossWindowChart from './components/CrossWindowChart.vue'
import MultiTicketMatrix from './components/MultiTicketMatrix.vue'
import RankingTable from './components/RankingTable.vue'
import type {
  PageLoadState,
  RankingFilterState,
  SortDirection,
  SortField,
  ViewMode,
} from './types'

// Primary Selection States (Defaults: Big Lotto, Ticket Count = 5, Window = RECENT_300 / 300)
const selectedLottery = ref<LotteryType>('BIG_LOTTO')
const selectedTicketCount = ref<TicketCount>(5)
const selectedWindow = ref<RankingWindow>('RECENT_300')
const activeViewMode = ref<ViewMode>('table')

// Sorting States
const sortField = ref<SortField>('officialRank')
const sortDirection = ref<SortDirection>('asc')
const isUserSorted = ref(false)

// Filter States
const filters = ref<RankingFilterState>({
  search: '',
  lifecycleStatus: 'ALL',
  comparabilityStatus: 'ALL',
  aboveBaseline: 'ALL',
  warningFilter: 'ALL',
  minCoverage: 0,
})

// Data & Inspection States
const rawRows = ref<RankingRow[]>([])
const matrixRows = ref<MatrixRow[]>([])
const selectedStrategyId = ref<string | null>(null)
const selectedStrategyDisplayName = ref<string>('')
const crossWindowData = ref<CrossWindowData | null>(null)

const pageState = ref<PageLoadState>('loading')
const errorMessage = ref('')
const chartLoading = ref(false)

let fetchController: AbortController | undefined
let chartController: AbortController | undefined
let fetchGeneration = 0

// Distinct lifecycle & comparability options from data
const lifecycleOptions = computed(() => {
  const set = new Set<string>()
  for (const r of rawRows.value) {
    if (r.lifecycleStatus) set.add(r.lifecycleStatus)
  }
  return ['ALL', ...Array.from(set).sort()]
})

const comparabilityOptions = computed(() => {
  const set = new Set<string>()
  for (const r of rawRows.value) {
    if (r.comparabilityStatus) set.add(r.comparabilityStatus)
  }
  return ['ALL', ...Array.from(set).sort()]
})

// Filtered table rows
const filteredRows = computed(() => {
  const q = filters.value.search.trim().toLowerCase()
  const lifecycle = filters.value.lifecycleStatus
  const comp = filters.value.comparabilityStatus
  const above = filters.value.aboveBaseline
  const warning = filters.value.warningFilter
  const minCov = filters.value.minCoverage / 100

  return rawRows.value.filter((row) => {
    // Strategy Search
    if (q) {
      const matchId = row.strategyId.toLowerCase().includes(q)
      const matchName = row.displayName.toLowerCase().includes(q)
      const matchFamily = row.methodFamily.toLowerCase().includes(q)
      if (!matchId && !matchName && !matchFamily) return false
    }

    // Lifecycle Status
    if (lifecycle !== 'ALL' && row.lifecycleStatus !== lifecycle) {
      return false
    }

    // Comparability Status
    if (comp !== 'ALL' && row.comparabilityStatus !== comp) {
      return false
    }

    // Above Baseline
    if (above === 'ABOVE') {
      if (row.baselineDelta === null || row.baselineDelta <= 0) return false
    } else if (above === 'AT_OR_BELOW') {
      if (row.baselineDelta === null || row.baselineDelta > 0) return false
    }

    // Warning Filter
    if (warning === 'HAS_WARNING') {
      if (row.warningCodes.length === 0) return false
    } else if (warning === 'NO_WARNING') {
      if (row.warningCodes.length > 0) return false
    }

    // Min Coverage Filter
    if (minCov > 0) {
      if (row.coverage === null || row.coverage < minCov) return false
    }

    return true
  })
})

// Filtered Matrix rows
const filteredMatrixRows = computed(() => {
  const q = filters.value.search.trim().toLowerCase()
  const lifecycle = filters.value.lifecycleStatus

  return matrixRows.value.filter((row) => {
    if (q) {
      const matchId = row.strategyId.toLowerCase().includes(q)
      const matchName = row.displayName.toLowerCase().includes(q)
      const matchFamily = row.methodFamily.toLowerCase().includes(q)
      if (!matchId && !matchName && !matchFamily) return false
    }
    if (lifecycle !== 'ALL' && row.lifecycleStatus !== lifecycle) {
      return false
    }
    return true
  })
})

// Metric summary cards
const summaryMetrics = computed(() => {
  const total = rawRows.value.length
  const available = rawRows.value.filter((r) => r.isAvailable)
  let bestRate: number | null = null
  let bestStrategy: string | null = null
  let bestDelta: number | null = null

  for (const r of available) {
    if (r.officialAnyPrizeRate !== null && (bestRate === null || r.officialAnyPrizeRate > bestRate)) {
      bestRate = r.officialAnyPrizeRate
      bestStrategy = r.displayName
      bestDelta = r.baselineDelta
    }
  }

  return {
    totalLoaded: total,
    availableCount: available.length,
    bestRateFormatted: bestRate !== null ? `${(bestRate * 100).toFixed(2)}%` : 'Unavailable',
    bestStrategyLabel: bestStrategy || '—',
    bestDeltaFormatted: bestDelta !== null ? `${bestDelta > 0 ? '+' : ''}${(bestDelta * 100).toFixed(2)}%` : 'Unavailable',
  }
})

// Active Window label
const activeWindowLabel = computed(() => {
  return WINDOW_OPTIONS.find((w) => w.key === selectedWindow.value)?.label ?? selectedWindow.value
})

async function loadData(): Promise<void> {
  fetchController?.abort()
  fetchController = new AbortController()
  const gen = ++fetchGeneration

  pageState.value = 'loading'
  errorMessage.value = ''

  try {
    const [rankingResult, matrixResult] = await Promise.all([
      fetchRankingData(selectedLottery.value, selectedTicketCount.value, selectedWindow.value, fetchController.signal),
      fetchMultiTicketMatrix(selectedLottery.value, selectedWindow.value, fetchController.signal),
    ])

    if (gen !== fetchGeneration) return

    rawRows.value = rankingResult
    matrixRows.value = matrixResult

    // If a strategy was selected previously, update cross-window chart; otherwise select top ranked
    const topRow = rankingResult.find((r) => r.isAvailable && r.officialRank !== null) || rankingResult[0]
    if (selectedStrategyId.value) {
      const match = rankingResult.find((r) => r.strategyId === selectedStrategyId.value)
      if (match) {
        selectStrategy(match.strategyId, match.displayName)
      } else if (topRow) {
        selectStrategy(topRow.strategyId, topRow.displayName)
      }
    } else if (topRow) {
      selectStrategy(topRow.strategyId, topRow.displayName)
    }

    pageState.value = 'ready'
  } catch (err: unknown) {
    if (gen !== fetchGeneration) return
    pageState.value = 'error'
    errorMessage.value = err instanceof Error ? err.message : '載入策略排名資料失敗。'
  }
}

async function selectStrategy(strategyId: string, displayName: string): Promise<void> {
  selectedStrategyId.value = strategyId
  selectedStrategyDisplayName.value = displayName

  chartController?.abort()
  chartController = new AbortController()
  chartLoading.value = true

  try {
    const result = await fetchCrossWindowData(
      selectedLottery.value,
      selectedTicketCount.value,
      strategyId,
      displayName,
      chartController.signal,
    )
    crossWindowData.value = result
  } catch {
    // chart failure does not break the table
  } finally {
    chartLoading.value = false
  }
}

function handleTableStrategySelect(row: RankingRow): void {
  selectStrategy(row.strategyId, row.displayName)
}

function handleMatrixStrategySelect(strategyId: string, displayName: string): void {
  selectStrategy(strategyId, displayName)
}

function handleSort(field: SortField): void {
  if (sortField.value === field) {
    sortDirection.value = sortDirection.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortField.value = field
    sortDirection.value = field === 'officialRank' ? 'asc' : 'desc'
  }
  isUserSorted.value = field !== 'officialRank' || sortDirection.value !== 'asc'
}

function resetSort(): void {
  sortField.value = 'officialRank'
  sortDirection.value = 'asc'
  isUserSorted.value = false
}

function clearFilters(): void {
  filters.value = {
    search: '',
    lifecycleStatus: 'ALL',
    comparabilityStatus: 'ALL',
    aboveBaseline: 'ALL',
    warningFilter: 'ALL',
    minCoverage: 0,
  }
}

// Watch selection changes
watch([selectedLottery, selectedTicketCount, selectedWindow], () => {
  loadData()
})

onMounted(() => {
  loadData()
})

onBeforeUnmount(() => {
  fetchController?.abort()
  chartController?.abort()
})
</script>

<template>
  <main class="ranking-matrix-page" data-testid="ranking-matrix-page">
    <!-- Header Section -->
    <SectionHeader
      title="策略排名／多注數矩陣 (Strategy Ranking & Multi-Ticket Matrix)"
      subtitle="基於官方正規回測紀錄之策略排名、多注數矩陣比較與跨窗口穩定度分析。嚴格遵循上游資料規範，不重算正式排名與成功率。"
    >
      <template #actions>
        <div class="view-mode-toggle" role="group" aria-label="檢視模式切換">
          <button
            type="button"
            class="toggle-btn"
            :class="{ 'toggle-btn--active': activeViewMode === 'table' }"
            data-testid="view-table-btn"
            @click="activeViewMode = 'table'"
          >
            📋 排名表 (Ranking Table)
          </button>
          <button
            type="button"
            class="toggle-btn"
            :class="{ 'toggle-btn--active': activeViewMode === 'matrix' }"
            data-testid="view-matrix-btn"
            @click="activeViewMode = 'matrix'"
          >
            ⊞ 多注數矩陣 (Multi-Ticket Matrix)
          </button>
        </div>
      </template>
    </SectionHeader>

    <!-- Global Selectors Bar (Lottery, Ticket Count 2/3/5/10/20, Window FULL/750/300/50) -->
    <section class="selectors-bar" aria-label="資料維度選擇器" data-testid="selectors-bar">
      <!-- Lottery Selector -->
      <div class="selector-group">
        <label for="lottery-select" class="selector-label">彩種選擇 (Lottery)</label>
        <select
          id="lottery-select"
          v-model="selectedLottery"
          class="selector-input"
          data-testid="lottery-selector"
        >
          <option
            v-for="opt in LOTTERY_OPTIONS"
            :key="opt.key"
            :value="opt.key"
          >
            {{ opt.label }}
          </option>
        </select>
      </div>

      <!-- Ticket Count Selector (2 / 3 / 5 / 10 / 20) -->
      <div class="selector-group">
        <label class="selector-label">注數規模 (Ticket Count)</label>
        <div class="pill-selector" role="radiogroup" aria-label="注數選擇">
          <button
            v-for="tc in CANONICAL_TICKET_COUNTS"
            :key="tc"
            type="button"
            class="pill-btn"
            :class="{ 'pill-btn--active': selectedTicketCount === tc }"
            :data-testid="`ticket-btn-${tc}`"
            :aria-checked="selectedTicketCount === tc"
            role="radio"
            @click="selectedTicketCount = tc"
          >
            {{ tc }} 注
          </button>
        </div>
      </div>

      <!-- Window Selector (FULL / 750 / 300 / 50) -->
      <div class="selector-group">
        <label class="selector-label">時間窗口 (History Window)</label>
        <div class="pill-selector" role="radiogroup" aria-label="窗口選擇">
          <button
            v-for="w in WINDOW_OPTIONS"
            :key="w.key"
            type="button"
            class="pill-btn"
            :class="{ 'pill-btn--active': selectedWindow === w.key }"
            :data-testid="`window-btn-${w.label}`"
            :aria-checked="selectedWindow === w.key"
            role="radio"
            :title="w.subLabel"
            @click="selectedWindow = w.key"
          >
            {{ w.label }}
          </button>
        </div>
      </div>
    </section>

    <!-- Metrics Overview Cards -->
    <section class="metrics-grid" aria-label="指標概覽">
      <MetricCard
        label="策略總數"
        :value="summaryMetrics.totalLoaded"
        hint="當前彩種已登記策略"
        data-testid="metric-total-strategies"
      />
      <MetricCard
        label="有效回測樣本"
        :value="summaryMetrics.availableCount"
        :hint="`${selectedTicketCount} 注 / ${activeWindowLabel} 窗口`"
        data-testid="metric-available-samples"
      />
      <MetricCard
        label="窗口最高成功率"
        :value="summaryMetrics.bestRateFormatted"
        :hint="summaryMetrics.bestStrategyLabel"
        data-testid="metric-best-rate"
      />
      <MetricCard
        label="最高基準差異 (Lift)"
        :value="summaryMetrics.bestDeltaFormatted"
        hint="超越隨機均勻基準"
        data-testid="metric-best-delta"
      />
    </section>

    <!-- Filters Bar -->
    <section class="filter-panel" aria-label="篩選工具列" data-testid="filter-panel">
      <div class="filter-row">
        <!-- Search Input -->
        <div class="filter-item filter-item--search">
          <label for="search-input" class="filter-label">搜尋策略 (Search)</label>
          <input
            id="search-input"
            v-model="filters.search"
            type="search"
            class="filter-control"
            placeholder="輸入策略 ID、名稱或家族關鍵字…"
            data-testid="filter-search-input"
          >
        </div>

        <!-- Lifecycle Status Filter -->
        <div class="filter-item">
          <label for="lifecycle-select" class="filter-label">生命週期 (Lifecycle)</label>
          <select
            id="lifecycle-select"
            v-model="filters.lifecycleStatus"
            class="filter-control"
            data-testid="filter-lifecycle-select"
          >
            <option v-for="opt in lifecycleOptions" :key="opt" :value="opt">
              {{ opt === 'ALL' ? '全部狀態 (All)' : opt }}
            </option>
          </select>
        </div>

        <!-- Comparability Filter -->
        <div class="filter-item">
          <label for="comparability-select" class="filter-label">可比較性 (Comparability)</label>
          <select
            id="comparability-select"
            v-model="filters.comparabilityStatus"
            class="filter-control"
            data-testid="filter-comparability-select"
          >
            <option v-for="opt in comparabilityOptions" :key="opt" :value="opt">
              {{ opt === 'ALL' ? '全部 (All)' : opt }}
            </option>
          </select>
        </div>

        <!-- Above Baseline Filter -->
        <div class="filter-item">
          <label for="baseline-select" class="filter-label">基準差異 (Baseline)</label>
          <select
            id="baseline-select"
            v-model="filters.aboveBaseline"
            class="filter-control"
            data-testid="filter-baseline-select"
          >
            <option value="ALL">全部 (All)</option>
            <option value="ABOVE">高於基準 (Delta &gt; 0)</option>
            <option value="AT_OR_BELOW">不高於基準 (Delta ≤ 0)</option>
          </select>
        </div>

        <!-- Warning Filter -->
        <div class="filter-item">
          <label for="warning-select" class="filter-label">警示狀態 (Warnings)</label>
          <select
            id="warning-select"
            v-model="filters.warningFilter"
            class="filter-control"
            data-testid="filter-warning-select"
          >
            <option value="ALL">全部 (All)</option>
            <option value="HAS_WARNING">含警示標籤 (Has Warnings)</option>
            <option value="NO_WARNING">無警示 (Clean Only)</option>
          </select>
        </div>

        <!-- Min Coverage Filter -->
        <div class="filter-item filter-item--coverage">
          <label for="min-coverage" class="filter-label">最低覆蓋率：{{ filters.minCoverage }}%</label>
          <input
            id="min-coverage"
            v-model.number="filters.minCoverage"
            type="range"
            min="0"
            max="100"
            step="5"
            class="filter-slider"
            data-testid="filter-coverage-slider"
          >
        </div>

        <!-- Reset Button -->
        <div class="filter-actions">
          <button
            type="button"
            class="filter-clear-btn"
            data-testid="clear-filters-btn"
            @click="clearFilters"
          >
            清除篩選
          </button>
        </div>
      </div>
    </section>

    <!-- Main Results View -->
    <div v-if="pageState === 'loading'" class="loading-state-wrap">
      <SkeletonLoader :lines="6" data-testid="page-loading-skeleton" />
    </div>

    <div v-else-if="pageState === 'error'" class="error-state-wrap">
      <ErrorState
        title="無法載入排名資料"
        :message="errorMessage"
        data-testid="page-error-state"
        @retry="loadData"
      />
    </div>

    <!-- Unavailable Ticket Count Alert (e.g. 2 or 3 tickets in B649) -->
    <div
      v-else-if="rawRows.length === 0 && (selectedTicketCount === 2 || selectedTicketCount === 3)"
      class="unavailable-notice-card"
      data-testid="unavailable-ticket-notice"
    >
      <div class="notice-icon">ℹ</div>
      <div class="notice-body">
        <h4>{{ selectedTicketCount }} 注規模回測未提供</h4>
        <p>
          在目前 {{ LOTTERY_OPTIONS.find(l => l.key === selectedLottery)?.label }} 官方正規回測資料庫中，主要提供 5、10、15、20 注規模回測數據。
          系統嚴格避免將無數據判定為 0% 成功率。請切換至 <strong>5、10 或 20 注</strong> 檢視正式回測結果，或切換至 <strong>多注數矩陣</strong> 視圖查看完整注數分佈。
        </p>
      </div>
    </div>

    <!-- Empty Filtered Results -->
    <div
      v-else-if="filteredRows.length === 0 && activeViewMode === 'table'"
      class="empty-filter-wrap"
      data-testid="empty-filter-state"
    >
      <EmptyState
        title="查無符合篩選條件之策略"
        message="請嘗試調整搜尋關鍵字、放寬覆蓋率或清除篩選條件。"
      >
        <template #actions>
          <button type="button" class="btn-primary" @click="clearFilters">
            重設所有篩選條件
          </button>
        </template>
      </EmptyState>
    </div>

    <!-- Content: Table or Matrix View -->
    <div v-else class="results-content-wrap">
      <!-- Table View -->
      <section v-if="activeViewMode === 'table'" class="table-section">
        <div
          v-if="selectedLottery === 'BIG_LOTTO' && (selectedTicketCount === 2 || selectedTicketCount === 3) && rawRows.length > 0"
          class="canonical-exact-native-banner"
          data-testid="canonical-exact-native-banner"
        >
          <div class="banner-icon">ℹ</div>
          <div class="banner-body">
            <strong>正規 {{ selectedTicketCount }} 注指標可用；官方正式排名尚未發布</strong>
            <p>
              本頁面顯示之 {{ selectedTicketCount }} 注指標直接讀取自官方已鎖定之正規回測記錄（無重算），保留精確小數率、基準差異與覆蓋率。由於官方正式排名尚未發布，策略不指派官方名次（以「—」表示），不可將表格排序視為官方排名。
            </p>
          </div>
        </div>
        <RankingTable
          :rows="filteredRows"
          :selected-strategy-id="selectedStrategyId"
          :sort-field="sortField"
          :sort-direction="sortDirection"
          :is-user-sorted="isUserSorted"
          @select-strategy="handleTableStrategySelect"
          @sort="handleSort"
          @reset-sort="resetSort"
        />
      </section>

      <!-- Matrix View -->
      <section v-else class="matrix-section">
        <MultiTicketMatrix
          :rows="filteredMatrixRows"
          :selected-strategy-id="selectedStrategyId"
          :active-window="activeWindowLabel"
          @select-strategy="handleMatrixStrategySelect"
        />
      </section>

      <!-- Cross-Window Trend Chart -->
      <section class="chart-section" aria-label="跨窗口趨勢分析">
        <CrossWindowChart
          :data="crossWindowData"
          :loading="chartLoading"
        />
      </section>
    </div>

    <!-- Warning Legend & Scientific Governance Disclaimers -->
    <footer class="research-disclaimer-panel" aria-label="研究聲明與警示說明">
      <div class="disclaimer-title">
        <span class="disclaimer-icon">🛡</span>
        <strong>量化研究免責與資料口徑聲明 (Quantitative Research Governance)</strong>
      </div>
      <p class="disclaimer-text">
        本平台所列歷史成功率、排名、中獎期數與隨機基準差異（Baseline Delta）均為回溯性描述統計證據，絕非對未來開獎結果之預測或保證。
        系統嚴禁包含任何「推薦下注」、「穩賺保證」或「最佳投注」之未驗證文案。低覆蓋率、樣本數不足或時間窗口過短之策略均已標註警示代碼。
      </p>
      <div class="warning-definitions-grid">
        <div class="warning-def-item">
          <strong>HIGH_RANK_LOW_COVERAGE</strong>
          <span>排名前列但覆蓋率低於 10%，受少數抽樣影響顯著。</span>
        </div>
        <div class="warning-def-item">
          <strong>NO_RECENT_OBSERVATIONS</strong>
          <span>近期時間窗口（50/300 期）內無成功觀察樣本。</span>
        </div>
        <div class="warning-def-item">
          <strong>NOT_HISTORICALLY_COMPARABLE</strong>
          <span>因已封存或別名關係，不可作為標準排名比較對象。</span>
        </div>
        <div class="warning-def-item">
          <strong>INSUFFICIENT_WINDOW</strong>
          <span>該時間窗口內樣本數低於 50 期，統計檢定力有限。</span>
        </div>
      </div>
    </footer>
  </main>
</template>

<style scoped>
.ranking-matrix-page {
  display: flex;
  flex-direction: column;
  gap: var(--space-4, 16px);
  width: 100%;
  max-width: 1400px;
  margin: 0 auto;
  padding-bottom: 40px;
}

.view-mode-toggle {
  display: inline-flex;
  background: var(--bg-secondary, #0d111b);
  border: 1px solid var(--border-color, rgba(255, 255, 255, 0.09));
  border-radius: var(--radius-md, 10px);
  padding: 3px;
  gap: 2px;
}

.toggle-btn {
  background: transparent;
  border: none;
  color: var(--text-secondary, #94a3b8);
  padding: 6px 14px;
  border-radius: var(--radius-sm, 6px);
  font-size: 0.85rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s ease;
}

.toggle-btn:hover {
  color: var(--text-primary, #f8fafc);
}

.toggle-btn--active {
  background: var(--primary-color, #8b5cf6);
  color: #ffffff;
  font-weight: 600;
  box-shadow: var(--shadow-sm, 0 2px 8px rgba(0, 0, 0, 0.4));
}

.selectors-bar {
  display: flex;
  align-items: center;
  gap: 24px;
  flex-wrap: wrap;
  background: var(--bg-card, rgba(18, 24, 38, 0.72));
  border: 1px solid var(--border-color, rgba(255, 255, 255, 0.09));
  border-radius: var(--radius-md, 10px);
  padding: 14px 18px;
}

.selector-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.selector-label {
  font-size: 0.78rem;
  font-weight: 600;
  color: var(--text-tertiary, #64748b);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.selector-input {
  background: var(--bg-input, rgba(12, 17, 28, 0.85));
  border: 1px solid var(--border-color, rgba(255, 255, 255, 0.09));
  color: var(--text-primary, #f8fafc);
  padding: 6px 12px;
  border-radius: var(--radius-sm, 6px);
  font-size: 0.88rem;
  outline: none;
  cursor: pointer;
}

.selector-input:focus {
  border-color: var(--border-focus, #8b5cf6);
}

.pill-selector {
  display: inline-flex;
  background: var(--bg-input, rgba(12, 17, 28, 0.85));
  border: 1px solid var(--border-color, rgba(255, 255, 255, 0.09));
  border-radius: var(--radius-sm, 6px);
  padding: 2px;
  gap: 2px;
}

.pill-btn {
  background: transparent;
  border: none;
  color: var(--text-secondary, #94a3b8);
  padding: 5px 12px;
  border-radius: 4px;
  font-size: 0.85rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s ease;
}

.pill-btn:hover {
  color: var(--text-primary, #f8fafc);
}

.pill-btn--active {
  background: rgba(99, 102, 241, 0.25);
  color: #38bdf8;
  font-weight: 600;
  border: 1px solid rgba(56, 189, 248, 0.4);
}

.metrics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: var(--space-3, 12px);
}

.filter-panel {
  background: var(--bg-card, rgba(18, 24, 38, 0.72));
  border: 1px solid var(--border-color, rgba(255, 255, 255, 0.09));
  border-radius: var(--radius-md, 10px);
  padding: 14px 18px;
}

.filter-row {
  display: flex;
  align-items: flex-end;
  gap: 16px;
  flex-wrap: wrap;
}

.filter-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.filter-item--search {
  flex: 1 1 240px;
}

.filter-item--coverage {
  min-width: 140px;
}

.filter-label {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-secondary, #94a3b8);
}

.filter-control {
  background: var(--bg-input, rgba(12, 17, 28, 0.85));
  border: 1px solid var(--border-color, rgba(255, 255, 255, 0.09));
  color: var(--text-primary, #f8fafc);
  padding: 6px 10px;
  border-radius: var(--radius-sm, 6px);
  font-size: 0.85rem;
  outline: none;
}

.filter-control:focus {
  border-color: var(--border-focus, #8b5cf6);
}

.filter-slider {
  accent-color: var(--primary-color, #8b5cf6);
  cursor: pointer;
  height: 6px;
}

.filter-actions {
  display: flex;
  align-items: center;
}

.filter-clear-btn {
  background: rgba(255, 255, 255, 0.06);
  color: var(--text-secondary, #94a3b8);
  border: 1px solid var(--border-color, rgba(255, 255, 255, 0.09));
  padding: 6px 12px;
  border-radius: var(--radius-sm, 6px);
  font-size: 0.82rem;
  cursor: pointer;
  transition: all 0.15s ease;
}

.filter-clear-btn:hover {
  background: rgba(255, 255, 255, 0.12);
  color: var(--text-primary, #f8fafc);
}

.results-content-wrap {
  display: flex;
  flex-direction: column;
  gap: var(--space-4, 16px);
}

.canonical-exact-native-banner {
  display: flex;
  gap: 14px;
  background: rgba(56, 189, 248, 0.08);
  border: 1px solid rgba(56, 189, 248, 0.25);
  border-radius: var(--radius-md, 10px);
  padding: 14px 18px;
  align-items: flex-start;
  margin-bottom: var(--space-3, 12px);
}

.banner-icon {
  font-size: 1.3rem;
  color: #38bdf8;
  flex-shrink: 0;
}

.banner-body strong {
  display: block;
  margin-bottom: 4px;
  color: var(--text-primary, #f8fafc);
  font-size: 0.9rem;
}

.banner-body p {
  margin: 0;
  font-size: 0.82rem;
  color: var(--text-secondary, #94a3b8);
  line-height: 1.45;
}

.unavailable-notice-card {
  display: flex;
  gap: 14px;
  background: rgba(99, 102, 241, 0.08);
  border: 1px solid rgba(99, 102, 241, 0.25);
  border-radius: var(--radius-md, 10px);
  padding: 18px 22px;
  align-items: flex-start;
}

.notice-icon {
  font-size: 1.5rem;
  color: #38bdf8;
}

.notice-body h4 {
  margin: 0 0 6px 0;
  color: var(--text-primary, #f8fafc);
  font-size: 0.95rem;
}

.notice-body p {
  margin: 0;
  font-size: 0.85rem;
  color: var(--text-secondary, #94a3b8);
  line-height: 1.5;
}

.empty-filter-wrap,
.loading-state-wrap,
.error-state-wrap {
  padding: 20px 0;
}

.btn-primary {
  background: var(--primary-color, #8b5cf6);
  color: #ffffff;
  border: none;
  padding: 8px 16px;
  border-radius: var(--radius-sm, 6px);
  font-weight: 600;
  cursor: pointer;
}

.research-disclaimer-panel {
  background: var(--bg-tertiary, #131927);
  border: 1px solid var(--border-subtle, rgba(255, 255, 255, 0.05));
  border-radius: var(--radius-md, 10px);
  padding: 16px 20px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  font-size: 0.8rem;
}

.disclaimer-title {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #a78bfa;
}

.disclaimer-text {
  color: var(--text-tertiary, #64748b);
  margin: 0;
  line-height: 1.4;
}

.warning-definitions-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 10px;
  margin-top: 6px;
  padding-top: 8px;
  border-top: 1px solid rgba(255, 255, 255, 0.05);
}

.warning-def-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-size: 0.75rem;
}

.warning-def-item strong {
  font-family: var(--font-mono, monospace);
  color: #fbbf24;
}

.warning-def-item span {
  color: var(--text-tertiary, #64748b);
}
</style>
