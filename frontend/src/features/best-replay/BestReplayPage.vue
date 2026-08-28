<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import DataTable from '../../components/DataTable.vue'
import EmptyState from '../../components/EmptyState.vue'
import ErrorState from '../../components/ErrorState.vue'
import FilterBar from '../../components/FilterBar.vue'
import MetricCard from '../../components/MetricCard.vue'
import SectionHeader from '../../components/SectionHeader.vue'
import SkeletonLoader from '../../components/SkeletonLoader.vue'
import StatusBadge from '../../components/StatusBadge.vue'

import BestReplayHorizonComparison from './BestReplayHorizonComparison.vue'
import BestReplayMatrix from './BestReplayMatrix.vue'
import {
  ALL_TICKET_COUNTS,
  B649_AVAILABLE_TICKET_COUNTS,
  CANONICAL_HORIZONS,
  P638_AVAILABLE_TICKET_COUNTS,
  T539_AVAILABLE_TICKET_COUNTS,
  type BestReplayItem,
  type BestReplayMatrixRow,
  type BestReplaySummary,
  type GameCode,
  type GameFilter,
  type HorizonKey,
  type TicketCount,
} from './types'
import {
  createUnavailableItem,
  loadB649BestReplayData,
  loadP638BestReplayData,
  loadT539BestReplayData,
} from '../../api/bestReplay'

type ViewMode = 'table' | 'comparison' | 'matrix'
type LoadingState = 'loading' | 'ready' | 'empty' | 'error'

const PAGE_SIZE = 15

// Query & Filter States
const selectedGame = ref<GameFilter>('B649')
const selectedHorizon = ref<HorizonKey>('FULL')
const selectedTicketCounts = ref<TicketCount[]>([5])
const isMultiSelectMode = ref(false)
const searchQuery = ref('')
const selectedFamily = ref<string>('ALL')
const activeViewMode = ref<ViewMode>('table')
const currentPage = ref(1)
const sortField = ref<'rank' | 'hitRate' | 'baselineDelta' | 'ticketCount' | 'strategyId'>('rank')
const sortDirection = ref<'asc' | 'desc'>('asc')

// Inspection state for detail / comparison
const activeInspectStrategyId = ref<string | null>(null)
const activeInspectTicketCount = ref<TicketCount>(5)

// Async & Data States
const state = ref<LoadingState>('loading')
const errorMessage = ref('')
const rawItems = ref<BestReplayItem[]>([])
let abortController: AbortController | undefined
let fetchGeneration = 0

const availableTicketCountsForGame = computed<readonly TicketCount[]>(() => {
  if (selectedGame.value === 'B649') return B649_AVAILABLE_TICKET_COUNTS
  if (selectedGame.value === 'P638') return P638_AVAILABLE_TICKET_COUNTS
  if (selectedGame.value === 'T539') return T539_AVAILABLE_TICKET_COUNTS
  return [...new Set([...B649_AVAILABLE_TICKET_COUNTS, ...P638_AVAILABLE_TICKET_COUNTS, ...T539_AVAILABLE_TICKET_COUNTS])].sort((a, b) => a - b)
})

const availableFamilies = computed<string[]>(() => {
  const families = new Set<string>()
  for (const item of rawItems.value) {
    if (item.methodFamily) families.add(item.methodFamily)
  }
  return ['ALL', ...Array.from(families).sort()]
})

// Quick Preset Handlers
function applyPreset(preset: '1' | '2' | '3' | '5' | '10' | '20' | 'all'): void {
  if (preset === 'all') {
    selectedTicketCounts.value = [...availableTicketCountsForGame.value]
    if (!selectedTicketCounts.value.length) selectedTicketCounts.value = [5]
    isMultiSelectMode.value = true
  } else {
    const num = Number.parseInt(preset, 10) as TicketCount
    selectedTicketCounts.value = [num]
    activeInspectTicketCount.value = num
    isMultiSelectMode.value = false
  }
}

function toggleTicketCount(count: TicketCount): void {
  if (!isMultiSelectMode.value) {
    selectedTicketCounts.value = [count]
    activeInspectTicketCount.value = count
    return
  }
  const idx = selectedTicketCounts.value.indexOf(count)
  if (idx >= 0) {
    if (selectedTicketCounts.value.length > 1) {
      selectedTicketCounts.value = selectedTicketCounts.value.filter((c) => c !== count)
    }
  } else {
    selectedTicketCounts.value = [...selectedTicketCounts.value, count].sort((a, b) => a - b)
  }
}

async function loadData(): Promise<void> {
  abortController?.abort()
  const controller = new AbortController()
  abortController = controller
  const generation = ++fetchGeneration

  state.value = 'loading'
  errorMessage.value = ''

  try {
    const promises: Promise<BestReplayItem[]>[] = []

    if (selectedGame.value === 'B649' || selectedGame.value === 'ALL') {
      promises.push(loadB649BestReplayData(selectedTicketCounts.value, selectedHorizon.value, controller.signal))
    }
    if (selectedGame.value === 'P638' || selectedGame.value === 'ALL') {
      promises.push(loadP638BestReplayData(selectedTicketCounts.value, selectedHorizon.value, controller.signal))
    }
    if (selectedGame.value === 'T539' || selectedGame.value === 'ALL') {
      promises.push(loadT539BestReplayData(selectedTicketCounts.value, selectedHorizon.value, controller.signal))
    }

    const results = await Promise.all(promises)
    if (generation !== fetchGeneration) return

    const combined = results.flat()

    // For any queried ticket counts where NO canonical evidence exists for the active game,
    // explicitly generate unavailable placeholder items so they are rendered as UNAVAILABLE rather than hidden/zero.
    for (const count of selectedTicketCounts.value) {
      const hasCount = combined.some((item) => item.ticketCount === count && (selectedGame.value === 'ALL' || item.game === selectedGame.value))
      if (!hasCount) {
        const gameCode = (selectedGame.value === 'ALL' ? 'B649' : selectedGame.value) as GameCode
        combined.push(
          createUnavailableItem(
            gameCode,
            `no_canonical_data_${gameCode.toLowerCase()}_t${count}`,
            'v1.0',
            'unsupported_dimension',
            count,
            selectedHorizon.value,
          ),
        )
      }
    }

    rawItems.value = combined
    state.value = combined.length ? 'ready' : 'empty'

    // Set active inspection strategy
    if (!activeInspectStrategyId.value || !combined.some((item) => item.strategyId === activeInspectStrategyId.value)) {
      const topLeader = combined.find((item) => item.isAvailable && item.rank === 1) || combined.find((item) => item.isAvailable)
      activeInspectStrategyId.value = topLeader ? topLeader.strategyId : combined[0]?.strategyId || null
    }
  } catch (err: unknown) {
    if (generation !== fetchGeneration) return
    if (err instanceof DOMException && err.name === 'AbortError') return
    rawItems.value = []
    state.value = 'error'
    errorMessage.value = err instanceof Error ? err.message : 'Failed to load best replay records.'
  }
}

// Filtered and Sorted Records
const filteredItems = computed<BestReplayItem[]>(() => {
  let list = rawItems.value

  if (searchQuery.value.trim()) {
    const q = searchQuery.value.toLowerCase().trim()
    list = list.filter(
      (item) =>
        item.strategyId.toLowerCase().includes(q) ||
        item.methodFamily.toLowerCase().includes(q) ||
        item.notes.toLowerCase().includes(q),
    )
  }

  if (selectedFamily.value !== 'ALL') {
    list = list.filter((item) => item.methodFamily === selectedFamily.value)
  }

  // Sort
  const direction = sortDirection.value === 'asc' ? 1 : -1
  return [...list].sort((a, b) => {
    // Available items always sort before completely unavailable items unless sorting by ID/game
    if (a.isAvailable !== b.isAvailable) {
      return a.isAvailable ? -1 : 1
    }

    if (sortField.value === 'rank') {
      const rA = a.rank ?? 999999
      const rB = b.rank ?? 999999
      return (rA - rB) * direction
    }
    if (sortField.value === 'hitRate') {
      const hA = a.hitRate ?? -1
      const hB = b.hitRate ?? -1
      return (hA - hB) * direction
    }
    if (sortField.value === 'baselineDelta') {
      const dA = a.baselineDelta ?? -999
      const dB = b.baselineDelta ?? -999
      return (dA - dB) * direction
    }
    if (sortField.value === 'ticketCount') {
      return (a.ticketCount - b.ticketCount) * direction
    }
    return a.strategyId.localeCompare(b.strategyId) * direction
  })
})

const paginatedItems = computed<BestReplayItem[]>(() => {
  const start = (currentPage.value - 1) * PAGE_SIZE
  return filteredItems.value.slice(start, start + PAGE_SIZE)
})

const totalPages = computed(() =>
  Math.max(1, Math.ceil(filteredItems.value.length / PAGE_SIZE)),
)

function compactStrategyLabel(strategyId: string): string {
  const parts = strategyId.split('__')
  if (parts.length >= 3) return parts.slice(1, -1).join(' · ')
  return strategyId.length > 30 ? `${strategyId.slice(0, 27)}…` : strategyId
}

// Main Summary Computation
const summary = computed<BestReplaySummary>(() => {
  const available = filteredItems.value.filter((item) => item.isAvailable)
  const best = available.find((item) => item.rank === 1) || available[0]
  const horizonDef = CANONICAL_HORIZONS.find((h) => h.key === selectedHorizon.value)

  if (!best) {
    return {
      bestStrategyId: null,
      bestStrategyLabel: 'Evidence Unavailable',
      ticketCount: selectedTicketCounts.value.join(', ') || 'None',
      horizon: horizonDef?.label || selectedHorizon.value,
      historicalHitRate: 'Unavailable',
      evaluatedTargets: 0,
      baselineDelta: 'Unavailable',
      evidenceStatus: 'EVIDENCE UNAVAILABLE',
      totalAvailableRecords: 0,
      game: selectedGame.value,
    }
  }

  return {
    bestStrategyId: best.strategyId,
    bestStrategyLabel: compactStrategyLabel(best.strategyId),
    ticketCount: best.ticketCount,
    horizon: best.horizonLabel,
    historicalHitRate: best.hitRateFormatted,
    evaluatedTargets: best.evaluatedTargets,
    baselineDelta: best.baselineDeltaFormatted,
    evidenceStatus: best.evidenceStatus,
    totalAvailableRecords: available.length,
    game: selectedGame.value,
  }
})

// Inspection data across all 4 horizons for active inspected strategy
const inspectHorizonItems = computed<Partial<Record<string, BestReplayItem | null>>>(() => {
  if (!activeInspectStrategyId.value) return {}
  const targetId = activeInspectStrategyId.value
  const targetCount = activeInspectTicketCount.value

  const byHorizon: Partial<Record<string, BestReplayItem | null>> = {}

  for (const h of CANONICAL_HORIZONS) {
    const match = rawItems.value.find(
      (item) =>
        item.strategyId === targetId &&
        item.ticketCount === targetCount &&
        item.horizon === h.key,
    )
    byHorizon[h.key] = match || null
  }
  return byHorizon
})

// Matrix Rows Computation for 1..20 Grid
const matrixRows = computed<BestReplayMatrixRow[]>(() => {
  // Extract distinct strategy IDs from raw items
  const strategyMap = new Map<string, { strategyId: string; methodFamily: string; game: GameCode }>()
  for (const item of rawItems.value) {
    if (!strategyMap.has(item.strategyId)) {
      strategyMap.set(item.strategyId, {
        strategyId: item.strategyId,
        methodFamily: item.methodFamily,
        game: item.game,
      })
    }
  }

  const rows: BestReplayMatrixRow[] = []

  for (const [sId, info] of strategyMap) {
    const cells: Partial<Record<TicketCount, BestReplayItem | null>> = {}

    for (const count of ALL_TICKET_COUNTS) {
      const match = rawItems.value.find(
        (item) =>
          item.strategyId === sId &&
          item.ticketCount === count &&
          item.horizon === selectedHorizon.value,
      )
      cells[count] = match || null
    }

    rows.push({
      strategyId: sId,
      strategyLabel: sId,
      methodFamily: info.methodFamily,
      game: info.game,
      cells: cells as Record<TicketCount, BestReplayItem | null>,
    })
  }

  return rows
})

function handleSort(field: 'rank' | 'hitRate' | 'baselineDelta' | 'ticketCount' | 'strategyId'): void {
  if (sortField.value === field) {
    sortDirection.value = sortDirection.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortField.value = field
    sortDirection.value = 'asc'
  }
}

function selectStrategyForInspection(item: BestReplayItem): void {
  activeInspectStrategyId.value = item.strategyId
  activeInspectTicketCount.value = item.ticketCount
}

function handleMatrixCellSelect(strategyId: string, ticketCount: TicketCount): void {
  activeInspectStrategyId.value = strategyId
  activeInspectTicketCount.value = ticketCount
  selectedTicketCounts.value = [ticketCount]
}

// Watchers
watch([selectedGame, selectedHorizon, selectedTicketCounts], () => {
  currentPage.value = 1
  loadData()
})

onMounted(() => {
  loadData()
})

onBeforeUnmount(() => {
  abortController?.abort()
})
</script>

<template>
  <section class="workspace-page" aria-labelledby="best-replay-title">
    <SectionHeader
      id="best-replay-title"
      title="Best Replay"
      eyebrow="Multi-ticket horizon ranking"
      description="Strategy ranking and ticket performance comparison across 1–20 tickets and short, medium, long, and full evaluation horizons."
    >
      <template #actions>
        <div class="view-mode-tabs" role="tablist" aria-label="View Mode Switcher">
          <button
            type="button"
            class="button"
            :class="{ 'button--primary': activeViewMode === 'table', 'button--quiet': activeViewMode !== 'table' }"
            :aria-pressed="activeViewMode === 'table'"
            @click="activeViewMode = 'table'"
          >
            Ranking Table
          </button>
          <button
            type="button"
            class="button"
            :class="{ 'button--primary': activeViewMode === 'comparison', 'button--quiet': activeViewMode !== 'comparison' }"
            :aria-pressed="activeViewMode === 'comparison'"
            @click="activeViewMode = 'comparison'"
          >
            Horizon Comparison
          </button>
          <button
            type="button"
            class="button"
            :class="{ 'button--primary': activeViewMode === 'matrix', 'button--quiet': activeViewMode !== 'matrix' }"
            :aria-pressed="activeViewMode === 'matrix'"
            @click="activeViewMode = 'matrix'"
          >
            1–20 Matrix
          </button>
        </div>
      </template>
    </SectionHeader>

    <!-- Main Summary Metrics Grid -->
    <div class="metrics-grid" data-testid="best-replay-metrics-grid">
      <MetricCard
        label="Best Strategy"
        :value="summary.bestStrategyLabel || 'None'"
        :subvalue="summary.bestStrategyId ? `Rank #1 · ${summary.game}` : 'No candidate evaluated'"
        variant="accent"
      />
      <MetricCard
        label="Ticket Count"
        :value="typeof summary.ticketCount === 'number' ? `${summary.ticketCount} Tickets` : summary.ticketCount"
        :subvalue="isMultiSelectMode ? 'Multi-ticket selection active' : 'Single ticket dimension'"
      />
      <MetricCard
        label="Horizon"
        :value="summary.horizon"
        :subvalue="summary.evaluatedTargets ? `${summary.evaluatedTargets.toLocaleString()} Historical Draws` : 'No draws evaluated'"
      />
      <MetricCard
        label="Historical Hit Rate"
        :value="summary.historicalHitRate"
        :subvalue="summary.baselineDelta !== 'Unavailable' ? `Delta vs baseline: ${summary.baselineDelta}` : 'Baseline delta unavailable'"
        variant="success"
      />
      <MetricCard
        label="Evidence Guard"
        :value="summary.evidenceStatus"
        subvalue="Deterministic out-of-sample audit"
        :badge="summary.totalAvailableRecords > 0 ? `${summary.totalAvailableRecords} Validated` : 'No Data'"
        badge-variant="accent"
      />
    </div>

    <!-- Quantitative Research Disclaimer Notice -->
    <div class="research-notice-banner" role="note">
      <span class="notice-icon" aria-hidden="true">🛡️</span>
      <div class="notice-text">
        <strong>Strict Evidence Protocol:</strong>
        Historical hit rates, ranks, and baseline lifts are descriptive quantitative records. All missing ticket counts are explicitly marked as unavailable rather than zero. No future predictive accuracy, monetary ROI, or winning guarantees are claimed.
      </div>
    </div>

    <!-- High-Density Control & Query Filter Bar -->
    <FilterBar title="Evaluation Dimensions & Filters" :count="filteredItems.length" count-label="strategies">
      <div class="controls-form">
        <!-- Game Selector -->
        <div class="control-group">
          <label for="game-select" class="control-label">Game</label>
          <select id="game-select" v-model="selectedGame" class="select-input">
            <option value="B649">B649 (Big Lotto 6/49)</option>
            <option value="P638">P638 (Power Lotto 6/38)</option>
            <option value="T539">T539 (Daily Cash 5/39)</option>
            <option value="ALL">All Available Games</option>
          </select>
        </div>

        <!-- Horizon Selector -->
        <div class="control-group">
          <label for="horizon-select" class="control-label">Evaluation Horizon</label>
          <select id="horizon-select" v-model="selectedHorizon" class="select-input">
            <option v-for="h in CANONICAL_HORIZONS" :key="h.key" :value="h.key">
              {{ h.label }} ({{ h.draws ? `${h.draws} draws` : 'Full history' }})
            </option>
          </select>
        </div>

        <!-- Method Family Filter -->
        <div class="control-group">
          <label for="family-select" class="control-label">Method Family</label>
          <select id="family-select" v-model="selectedFamily" class="select-input">
            <option v-for="fam in availableFamilies" :key="fam" :value="fam">
              {{ fam }}
            </option>
          </select>
        </div>

        <!-- Search Input -->
        <div class="control-group control-group--grow">
          <label for="search-input" class="control-label">Search Strategy</label>
          <input
            id="search-input"
            v-model="searchQuery"
            type="text"
            placeholder="Search by strategy ID or notes…"
            class="text-input"
          />
        </div>
      </div>

      <!-- Ticket Count 1..20 Controls and Quick Presets -->
      <div class="ticket-control-row">
        <div class="ticket-header">
          <span class="control-label">Ticket Count (1–20)</span>
          <div class="preset-buttons" role="group" aria-label="Ticket Count Presets">
            <span class="preset-label">Quick Presets:</span>
            <button
              v-for="p in (['1', '2', '3', '5', '10', '20', 'all'] as const)"
              :key="p"
              type="button"
              class="button button--sm"
              :class="{
                'button--primary': p === 'all' ? isMultiSelectMode : selectedTicketCounts.length === 1 && selectedTicketCounts[0] === Number(p),
                'button--quiet': !(p === 'all' ? isMultiSelectMode : selectedTicketCounts.length === 1 && selectedTicketCounts[0] === Number(p)),
              }"
              @click="applyPreset(p)"
            >
              {{ p === 'all' ? 'All Available' : `${p}T` }}
            </button>
          </div>
        </div>

        <div class="ticket-buttons-grid" role="group" aria-label="Individual Ticket Counts">
          <button
            v-for="count in ALL_TICKET_COUNTS"
            :key="count"
            type="button"
            class="ticket-chip"
            :class="{
              'ticket-chip--selected': selectedTicketCounts.includes(count),
              'ticket-chip--available': availableTicketCountsForGame.includes(count),
              'ticket-chip--unavailable': !availableTicketCountsForGame.includes(count),
            }"
            :aria-pressed="selectedTicketCounts.includes(count)"
            :title="
              availableTicketCountsForGame.includes(count)
                ? `Ticket Count ${count} (Canonical evidence available)`
                : `Ticket Count ${count} (No canonical evidence recorded)`
            "
            @click="toggleTicketCount(count)"
          >
            <span class="ticket-chip__number">{{ count }}</span>
            <span v-if="availableTicketCountsForGame.includes(count)" class="ticket-chip__dot" aria-hidden="true" />
            <span v-else class="ticket-chip__lock" aria-label="Unavailable">🔒</span>
          </button>
        </div>
      </div>
    </FilterBar>

    <!-- Error State -->
    <ErrorState
      v-if="state === 'error'"
      title="Failed to load best replay records"
      :message="errorMessage"
      @retry="loadData"
    />

    <!-- Loading State -->
    <SkeletonLoader
      v-else-if="state === 'loading'"
      type="table"
      :rows="8"
      height="48px"
    />

    <!-- Empty State -->
    <EmptyState
      v-else-if="state === 'empty' || filteredItems.length === 0"
      title="No matching strategy records"
      description="No strategies matched your active filters or ticket count selection."
    >
      <button type="button" class="button button--primary" @click="applyPreset('all')">
        Reset to All Available
      </button>
    </EmptyState>

    <!-- Main Workspace Content by View Mode -->
    <template v-else>
      <!-- Mode 1: Ranking Table -->
      <div v-if="activeViewMode === 'table'" class="table-workspace">
        <DataTable
          min-width="1100px"
          caption="Historical Strategy Performance and Horizon Ranking"
        >
          <template #head>
            <tr>
              <th class="cursor-pointer" @click="handleSort('rank')">
                Rank {{ sortField === 'rank' ? (sortDirection === 'asc' ? '↑' : '↓') : '' }}
              </th>
              <th class="cursor-pointer" @click="handleSort('strategyId')">
                Strategy {{ sortField === 'strategyId' ? (sortDirection === 'asc' ? '↑' : '↓') : '' }}
              </th>
              <th>Game</th>
              <th class="cursor-pointer" @click="handleSort('ticketCount')">
                Tickets {{ sortField === 'ticketCount' ? (sortDirection === 'asc' ? '↑' : '↓') : '' }}
              </th>
              <th>Horizon</th>
              <th>Evaluated</th>
              <th>Winning</th>
              <th class="cursor-pointer" @click="handleSort('hitRate')">
                Hit Rate {{ sortField === 'hitRate' ? (sortDirection === 'asc' ? '↑' : '↓') : '' }}
              </th>
              <th class="cursor-pointer" @click="handleSort('baselineDelta')">
                Baseline Delta {{ sortField === 'baselineDelta' ? (sortDirection === 'asc' ? '↑' : '↓') : '' }}
              </th>
              <th>Best Hit</th>
              <th>Evidence Status</th>
              <th>Notes</th>
            </tr>
          </template>

          <tr
            v-for="item in paginatedItems"
            :key="item.id"
            class="data-row"
            :class="{ 'data-row--active': activeInspectStrategyId === item.strategyId && activeInspectTicketCount === item.ticketCount }"
            @click="selectStrategyForInspection(item)"
          >
            <td>
              <span v-if="item.isAvailable && item.rank !== null" class="rank-tag" :class="`rank-tag--${item.rank <= 3 ? 'top' : 'regular'}`">
                #{{ item.rank }}
              </span>
              <span v-else class="text-muted">—</span>
            </td>
            <td>
              <div class="strategy-cell">
                <strong class="strategy-name">{{ item.strategyId }}</strong>
                <small class="strategy-sub">{{ item.methodFamily }} · {{ item.strategyVersion }}</small>
              </div>
            </td>
            <td>
              <span class="game-tag">{{ item.game }}</span>
            </td>
            <td>
              <span class="ticket-tag">{{ item.ticketCount }}T</span>
            </td>
            <td>
              <span class="horizon-tag">{{ item.horizonLabel }}</span>
            </td>
            <td class="font-mono">
              {{ item.evaluatedTargets > 0 ? item.evaluatedTargets.toLocaleString() : '—' }}
            </td>
            <td class="font-mono">
              {{ item.winningTargets !== null ? item.winningTargets.toLocaleString() : '—' }}
            </td>
            <td class="font-mono">
              <strong v-if="item.isAvailable" class="text-primary">{{ item.hitRateFormatted }}</strong>
              <span v-else class="text-muted">Unavailable</span>
            </td>
            <td class="font-mono">
              <span
                v-if="item.isAvailable && item.baselineDeltaFormatted !== 'Unavailable'"
                :class="{
                  'text-success': (item.baselineDelta || 0) > 0,
                  'text-danger': (item.baselineDelta || 0) < 0,
                }"
              >
                {{ item.baselineDeltaFormatted }}
              </span>
              <span v-else class="text-muted">Unavailable</span>
            </td>
            <td>
              <span v-if="item.isAvailable">{{ item.bestHit }}</span>
              <span v-else class="text-muted">Unavailable</span>
            </td>
            <td>
              <StatusBadge :status="item.evidenceStatus" size="sm" />
            </td>
            <td>
              <span class="notes-text" :title="item.notes">{{ item.notes }}</span>
            </td>
          </tr>

          <template #pagination>
            <div class="pagination-bar">
              <span class="pagination-info">
                Showing {{ (currentPage - 1) * PAGE_SIZE + 1 }} to
                {{ Math.min(currentPage * PAGE_SIZE, filteredItems.length) }} of
                {{ filteredItems.length }} records
              </span>
              <div class="pagination-buttons">
                <button
                  type="button"
                  class="button button--sm button--quiet"
                  :disabled="currentPage <= 1"
                  @click="currentPage--"
                >
                  Previous
                </button>
                <span class="page-number">Page {{ currentPage }} of {{ totalPages }}</span>
                <button
                  type="button"
                  class="button button--sm button--quiet"
                  :disabled="currentPage >= totalPages"
                  @click="currentPage++"
                >
                  Next
                </button>
              </div>
            </div>
          </template>
        </DataTable>

        <!-- Selected Strategy Horizon Drawer / Inspection Card -->
        <div v-if="activeInspectStrategyId" class="drawer-section">
          <SectionHeader
            title="Horizon Stability Breakdown"
            eyebrow="Selected Strategy Audit"
            description="Comparative multi-horizon performance comparison for the selected strategy across Short (50), Medium (300), Long (750), and Full evaluation windows."
          />
          <BestReplayHorizonComparison
            :strategy-id="activeInspectStrategyId"
            :ticket-count="activeInspectTicketCount"
            :game="selectedGame"
            :items-by-horizon="inspectHorizonItems"
          />
        </div>
      </div>

      <!-- Mode 2: Horizon Comparison Dedicated View -->
      <div v-else-if="activeViewMode === 'comparison'" class="comparison-workspace">
        <div v-if="activeInspectStrategyId">
          <BestReplayHorizonComparison
            :strategy-id="activeInspectStrategyId"
            :ticket-count="activeInspectTicketCount"
            :game="selectedGame"
            :items-by-horizon="inspectHorizonItems"
          />
        </div>

        <article class="panel">
          <div class="panel__heading">
            <p class="step-label">All Candidate Strategies</p>
            <h3>Select a strategy below to inspect its multi-horizon curve</h3>
          </div>
          <div class="strategy-chips-list">
            <button
              v-for="item in filteredItems.slice(0, 30)"
              :key="item.id"
              type="button"
              class="strategy-chip"
              :class="{ 'strategy-chip--active': activeInspectStrategyId === item.strategyId }"
              @click="selectStrategyForInspection(item)"
            >
              <span class="chip-rank">#{{ item.rank ?? '—' }}</span>
              <span class="chip-title">{{ item.strategyId }}</span>
              <span class="chip-rate">{{ item.hitRateFormatted }}</span>
            </button>
          </div>
        </article>
      </div>

      <!-- Mode 3: 1–20 Matrix Heatmap View -->
      <div v-else-if="activeViewMode === 'matrix'" class="matrix-workspace">
        <BestReplayMatrix
          :rows="matrixRows"
          :selected-ticket-count="activeInspectTicketCount"
          :selected-strategy-id="activeInspectStrategyId"
          @select-cell="handleMatrixCellSelect"
        />

        <div v-if="activeInspectStrategyId" class="drawer-section">
          <BestReplayHorizonComparison
            :strategy-id="activeInspectStrategyId"
            :ticket-count="activeInspectTicketCount"
            :game="selectedGame"
            :items-by-horizon="inspectHorizonItems"
          />
        </div>
      </div>
    </template>
  </section>
</template>

<style scoped>
.workspace-page {
  padding-bottom: 48px;
}

.view-mode-tabs {
  display: flex;
  align-items: center;
  gap: 6px;
  background: rgba(13, 17, 27, 0.7);
  padding: 4px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-color);
}

.research-notice-banner {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 14px 18px;
  border-radius: var(--radius-md);
  background: linear-gradient(135deg, rgba(30, 20, 50, 0.7) 0%, rgba(13, 17, 28, 0.7) 100%);
  border: 1px solid rgba(139, 92, 246, 0.25);
  margin-top: 20px;
  margin-bottom: 20px;
  font-size: 12.5px;
  color: var(--text-secondary);
  line-height: 1.5;
}

.notice-icon {
  font-size: 18px;
  flex-shrink: 0;
  margin-top: 1px;
}

.notice-text strong {
  color: var(--text-accent);
}

.controls-form {
  display: flex;
  align-items: flex-end;
  gap: 16px;
  flex-wrap: wrap;
  width: 100%;
}

.control-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 170px;
}

.control-group--grow {
  flex: 1;
  min-width: 220px;
}

.control-label {
  font: 700 11px/1 var(--font-mono);
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.select-input,
.text-input {
  padding: 8px 12px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-color);
  background: var(--bg-input);
  color: var(--text-primary);
  font-size: 13px;
  outline: none;
  transition: border-color 0.2s ease;
}

.select-input:focus,
.text-input:focus {
  border-color: var(--border-focus);
}

.ticket-control-row {
  margin-top: 18px;
  padding-top: 16px;
  border-top: 1px solid var(--border-subtle);
  width: 100%;
}

.ticket-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.preset-buttons {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.preset-label {
  font-size: 11px;
  color: var(--text-tertiary);
  margin-right: 4px;
}

.ticket-buttons-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(48px, 1fr));
  gap: 8px;
}

.ticket-chip {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 42px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-color);
  background: rgba(14, 19, 32, 0.7);
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.15s ease;
  padding: 2px 4px;
}

.ticket-chip:hover {
  border-color: var(--border-hover);
  color: var(--text-primary);
}

.ticket-chip--selected {
  border-color: var(--primary-color) !important;
  background: linear-gradient(135deg, rgba(124, 58, 237, 0.35) 0%, rgba(219, 39, 119, 0.2) 100%) !important;
  color: #fff !important;
  box-shadow: 0 0 12px rgba(124, 58, 237, 0.3);
}

.ticket-chip--unavailable {
  opacity: 0.45;
  background: rgba(0, 0, 0, 0.2);
  border-style: dashed;
}

.ticket-chip__number {
  font: 700 12px/1 var(--font-mono);
}

.ticket-chip__dot {
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: var(--color-success);
  margin-top: 3px;
}

.ticket-chip__lock {
  font-size: 9px;
  margin-top: 2px;
}

.data-row {
  cursor: pointer;
  transition: background 0.15s ease;
}

.data-row:hover {
  background: rgba(255, 255, 255, 0.04);
}

.data-row--active {
  background: rgba(124, 58, 237, 0.12) !important;
  border-left: 3px solid var(--primary-color);
}

.rank-tag {
  display: inline-block;
  padding: 3px 7px;
  border-radius: var(--radius-full);
  font: 800 11px/1 var(--font-mono);
}

.rank-tag--top {
  background: var(--gradient-primary);
  color: #fff;
  box-shadow: 0 2px 8px rgba(124, 58, 237, 0.35);
}

.rank-tag--regular {
  background: rgba(255, 255, 255, 0.06);
  color: var(--text-secondary);
}

.strategy-cell {
  display: flex;
  flex-direction: column;
}

.strategy-name {
  font-family: var(--font-mono);
  font-size: 12.5px;
  color: var(--text-primary);
}

.strategy-sub {
  font-size: 10.5px;
  color: var(--text-tertiary);
  margin-top: 2px;
}

.game-tag {
  padding: 2px 6px;
  border-radius: var(--radius-sm);
  background: rgba(56, 189, 248, 0.15);
  color: var(--mint);
  font: 700 10px/1 var(--font-mono);
}

.ticket-tag {
  font: 700 11px/1 var(--font-mono);
  color: var(--text-accent);
}

.horizon-tag {
  font-size: 11px;
  color: var(--text-secondary);
}

.notes-text {
  font-size: 11px;
  color: var(--text-secondary);
  display: block;
  max-width: 280px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.cursor-pointer {
  cursor: pointer;
}

.cursor-pointer:hover {
  color: var(--text-primary);
}

.font-mono {
  font-family: var(--font-mono);
}

.text-muted {
  color: var(--text-tertiary);
}

.text-success {
  color: var(--color-success) !important;
}

.text-danger {
  color: var(--color-danger) !important;
}

.pagination-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  gap: 16px;
  flex-wrap: wrap;
  width: 100%;
}

.pagination-info {
  font-size: 12px;
  color: var(--text-secondary);
}

.pagination-buttons {
  display: flex;
  align-items: center;
  gap: 10px;
}

.page-number {
  font-size: 12px;
  color: var(--text-secondary);
  font-family: var(--font-mono);
}

.drawer-section {
  margin-top: 32px;
  border-top: 1px solid var(--border-color);
  padding-top: 24px;
}

.strategy-chips-list {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 16px;
}

.strategy-chip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-color);
  background: rgba(14, 19, 32, 0.7);
  color: var(--text-primary);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.strategy-chip:hover {
  border-color: var(--border-hover);
  transform: translateY(-1px);
}

.strategy-chip--active {
  border-color: var(--primary-color);
  background: rgba(124, 58, 237, 0.2);
}

.chip-rank {
  font: 700 10px/1 var(--font-mono);
  color: var(--text-accent);
}

.chip-title {
  font-family: var(--font-mono);
}

.chip-rate {
  font: 700 11px/1 var(--font-mono);
  color: var(--color-success);
}

.view-mode-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  max-width: 100%;
}
</style>
