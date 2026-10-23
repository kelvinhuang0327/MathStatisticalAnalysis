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
import BestReplayOneToFiveOverview from './BestReplayOneToFiveOverview.vue'
import { compareNullableNumbers } from './sorting'
import {
  ALL_TICKET_COUNTS,
  B649_AVAILABLE_TICKET_COUNTS,
  CANONICAL_HORIZONS,
  P638_AVAILABLE_TICKET_COUNTS,
  PRIMARY_TICKET_COUNTS,
  T539_AVAILABLE_TICKET_COUNTS,
  type BestReplayItem,
  type BestReplayMatrixRow,
  type BestReplaySummary,
  type GameCode,
  type GameFilter,
  type HorizonKey,
  type PrimaryTicketCount,
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
const activeInspectStrategyVersion = ref<string | null>(null)
const activeInspectGame = ref<GameCode>('B649')
const activeInspectTicketCount = ref<TicketCount>(5)

// Async & Data States
const state = ref<LoadingState>('loading')
const errorMessage = ref('')
const rawItems = ref<BestReplayItem[]>([])
const allLoadedItems = ref<BestReplayItem[]>([])
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

interface ComparisonScope {
  key: string
  game: GameCode
  ticketCount: TicketCount
  horizon: HorizonKey
  dimensionLabel: string
  successDefinition: string
  sourceEvidence: string
  label: string
}

interface FilteredComparisonGroup {
  scope: ComparisonScope
  items: BestReplayItem[]
}

function getComparisonScope(item: BestReplayItem): ComparisonScope {
  const dimensionLabel = item.game === 'B649' ? 'Prefix count' : 'Ticket count'
  const successDefinition = item.game === 'B649'
    ? 'official_any_prize_rate (official any-prize event)'
    : 'winning_target_rate (winning-target rate)'
  const sourceEvidence = item.game === 'B649'
    ? 'official_rank / official_any_prize_rate · M3_PLUS criterion'
    : `${item.game} canonical run ranking · rank / winning_target_rate`
  const key = [item.game, item.ticketCount, item.horizon, successDefinition, sourceEvidence].join('|')
  return {
    key,
    game: item.game,
    ticketCount: item.ticketCount,
    horizon: item.horizon,
    dimensionLabel,
    successDefinition,
    sourceEvidence,
    label: `${item.game} · ${dimensionLabel} ${item.ticketCount} · ${item.horizon} · ${successDefinition} · ${sourceEvidence}`,
  }
}

function compareComparisonScopes(a: ComparisonScope, b: ComparisonScope): number {
  const gameOrder: Record<GameCode, number> = { B649: 0, P638: 1, T539: 2 }
  if (a.game !== b.game) return gameOrder[a.game] - gameOrder[b.game]
  if (a.ticketCount !== b.ticketCount) return a.ticketCount - b.ticketCount
  const horizonOrder = CANONICAL_HORIZONS.findIndex((horizon) => horizon.key === a.horizon)
    - CANONICAL_HORIZONS.findIndex((horizon) => horizon.key === b.horizon)
  if (horizonOrder !== 0) return horizonOrder
  return a.key.localeCompare(b.key)
}

function selectGame(game: GameFilter): void {
  if (selectedGame.value === game) return
  selectedGame.value = game
  if (game === 'B649') {
    selectedTicketCounts.value = [5]
    activeInspectTicketCount.value = 5
    isMultiSelectMode.value = false
  } else if (game === 'P638' || game === 'T539') {
    selectedTicketCounts.value = [1]
    activeInspectTicketCount.value = 1
    isMultiSelectMode.value = false
  }
  activeInspectStrategyId.value = null
  currentPage.value = 1
  resetSort()
}

function handleGameDropdownChange(event: Event): void {
  const target = event.currentTarget
  if (!(target instanceof HTMLSelectElement)) return
  selectGame(target.value as GameFilter)
}

// Quick Preset Handlers
function applyPreset(preset: '1' | '2' | '3' | '4' | '5' | '10' | '20' | 'all'): void {
  if (preset === 'all') {
    selectedTicketCounts.value = [...availableTicketCountsForGame.value]
    if (!selectedTicketCounts.value.length) selectedTicketCounts.value = [1]
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

function handleSelectTicketFromOverview(count: PrimaryTicketCount): void {
  selectedTicketCounts.value = [count]
  activeInspectTicketCount.value = count
  isMultiSelectMode.value = false
}

function resetSort(): void {
  sortField.value = 'rank'
  sortDirection.value = 'asc'
}

function resetToOfficialRank(): void {
  resetSort()
  searchQuery.value = ''
  selectedFamily.value = 'ALL'
  currentPage.value = 1
}

async function loadData(): Promise<void> {
  abortController?.abort()
  const controller = new AbortController()
  abortController = controller
  const generation = ++fetchGeneration

  state.value = 'loading'
  errorMessage.value = ''

  try {
    const activeGame = selectedGame.value
    const gameCode = (activeGame === 'ALL' ? 'B649' : activeGame) as GameCode

    // Load every supported dimension so the matrix and overview retain their full browsing scope.
    const countsToQuery = ALL_TICKET_COUNTS

    const promises: Promise<BestReplayItem[]>[] = []
    for (const horizon of CANONICAL_HORIZONS) {
      if (activeGame === 'B649' || activeGame === 'ALL') {
        promises.push(loadB649BestReplayData(countsToQuery, horizon.key, controller.signal))
      }
      if (activeGame === 'P638' || activeGame === 'ALL') {
        promises.push(loadP638BestReplayData(countsToQuery, horizon.key, controller.signal))
      }
      if (activeGame === 'T539' || activeGame === 'ALL') {
        promises.push(loadT539BestReplayData(countsToQuery, horizon.key, controller.signal))
      }
    }

    const results = await Promise.all(promises)
    if (generation !== fetchGeneration) return

    const fetchedItems = results.flat()
    allLoadedItems.value = fetchedItems

    // Filter items for the currently selected ticket counts
    const filteredBySelectedTickets = fetchedItems.filter((item) =>
      item.horizon === selectedHorizon.value &&
      selectedTicketCounts.value.includes(item.ticketCount) &&
      (activeGame === 'ALL' || item.game === activeGame),
    )

    // In ALL mode, retain an explicit unavailable row for each game/count pair without source evidence.
    const gamesToDisplay: GameCode[] = activeGame === 'ALL' ? ['B649', 'P638', 'T539'] : [activeGame]
    for (const count of selectedTicketCounts.value) {
      for (const game of gamesToDisplay) {
        const hasGroup = filteredBySelectedTickets.some(
          (item) => item.game === game && item.ticketCount === count,
        )
        if (!hasGroup) {
          filteredBySelectedTickets.push(
            createUnavailableItem(
              game,
              `no_canonical_data_${game.toLowerCase()}_t${count}`,
              null,
              'unsupported_dimension',
              count,
              selectedHorizon.value,
              'NO_CANONICAL_REPLAY_EVIDENCE',
              `No canonical replay evidence is recorded for ${game === 'B649' ? 'prefix count' : 'ticket count'} ${count}.`,
            ),
          )
        }
      }
    }

    rawItems.value = filteredBySelectedTickets
    state.value = filteredBySelectedTickets.length ? 'ready' : 'empty'

    // Set active inspection strategy
    if (!activeInspectStrategyId.value || !filteredBySelectedTickets.some((item) =>
      item.strategyId === activeInspectStrategyId.value &&
      item.strategyVersion === activeInspectStrategyVersion.value &&
      item.game === activeInspectGame.value &&
      item.ticketCount === activeInspectTicketCount.value,
    )) {
      const hasSingleSelectedScope = selectedGame.value !== 'ALL' && selectedTicketCounts.value.length === 1
      const topLeader = filteredBySelectedTickets.find((item) => item.isAvailable && item.rank === 1)
      const initialInspectItem = hasSingleSelectedScope
        ? topLeader || filteredBySelectedTickets.find((item) => item.isAvailable) || filteredBySelectedTickets[0] || null
        : null
      activeInspectStrategyId.value = initialInspectItem?.strategyId || null
      activeInspectStrategyVersion.value = initialInspectItem?.strategyVersion || null
      activeInspectGame.value = initialInspectItem?.game || gameCode
      activeInspectTicketCount.value = initialInspectItem?.ticketCount || selectedTicketCounts.value[0] || 1
    }
  } catch (err: unknown) {
    if (generation !== fetchGeneration) return
    if (err instanceof DOMException && err.name === 'AbortError') return
    rawItems.value = []
    allLoadedItems.value = []
    state.value = 'error'
    errorMessage.value = err instanceof Error ? err.message : 'Failed to load best replay records.'
  }
}

// 1–5 Overview items computation
const overviewItemsByGame = computed<Record<GameCode, Record<PrimaryTicketCount, BestReplayItem | null>>>(() => {
  const result = {} as Record<GameCode, Record<PrimaryTicketCount, BestReplayItem | null>>
  for (const game of ['B649', 'P638', 'T539'] as const) {
    const gameItems: Record<PrimaryTicketCount, BestReplayItem | null> = {
      1: null,
      2: null,
      3: null,
      4: null,
      5: null,
    }

    for (const count of PRIMARY_TICKET_COUNTS) {
      const groupItems = allLoadedItems.value.filter(
        (item) => item.game === game && item.ticketCount === count && item.horizon === selectedHorizon.value,
      )
      const rank1 = groupItems.find((item) => item.rank === 1)
      const sourceUnavailable = groupItems.find((item) => !item.isAvailable)
      const hasAvailableSource = groupItems.some((item) => item.isAvailable)
      const hasSourceRecords = groupItems.length > 0
      if (rank1) {
        gameItems[count] = rank1
        continue
      }
      if (sourceUnavailable && !hasAvailableSource && sourceUnavailable.rank === null) {
        gameItems[count] = sourceUnavailable
        continue
      }
      gameItems[count] = createUnavailableItem(
        game,
        `no_source_rank_one_${game.toLowerCase()}_t${count}`,
        null,
        `${game.toLowerCase()}_source_group`,
        count,
        selectedHorizon.value,
        hasSourceRecords ? 'SOURCE_RANK_ONE_UNAVAILABLE' : 'NO_CANONICAL_REPLAY_EVIDENCE',
        hasAvailableSource
          ? `No source Rank #1 is available for ${game} ${count}-count records in this horizon.`
          : hasSourceRecords
            ? `Source records exist, but no source Rank #1 with a usable rate is available for ${game} at ${count} ${game === 'B649' ? 'prefix count' : 'tickets'}.`
            : `No canonical replay evidence is recorded for ${game} at ${count} ${game === 'B649' ? 'prefix count' : 'tickets'}.`,
      )
    }
    result[game] = gameItems
  }
  return result
})

const overviewGames = computed<GameCode[]>(() =>
  selectedGame.value === 'ALL' ? ['B649', 'P638', 'T539'] : [selectedGame.value],
)

// Filtered and Sorted Records
const filteredGroups = computed<FilteredComparisonGroup[]>(() => {
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

  const groups = new Map<string, FilteredComparisonGroup>()
  for (const item of list) {
    const scope = getComparisonScope(item)
    const existing = groups.get(scope.key)
    if (existing) existing.items.push(item)
    else groups.set(scope.key, { scope, items: [item] })
  }

  const direction = sortDirection.value === 'asc' ? 1 : -1
  const compareWithinGroup = (a: BestReplayItem, b: BestReplayItem): number => {
    // Available items always sort before completely unavailable items unless sorting by ID/game
    if (a.isAvailable !== b.isAvailable) {
      return a.isAvailable ? -1 : 1
    }

    if (sortField.value === 'rank') {
      return compareNullableNumbers(a.rank, b.rank, direction)
    }
    if (sortField.value === 'hitRate') {
      return compareNullableNumbers(a.hitRate, b.hitRate, direction)
    }
    if (sortField.value === 'baselineDelta') {
      return compareNullableNumbers(a.baselineDelta, b.baselineDelta, direction)
    }
    if (sortField.value === 'ticketCount') {
      return (a.ticketCount - b.ticketCount) * direction
    }
    return a.strategyId.localeCompare(b.strategyId) * direction
  }

  return [...groups.values()]
    .sort((a, b) => compareComparisonScopes(a.scope, b.scope))
    .map((group) => ({
      ...group,
      items: [...group.items].sort(compareWithinGroup),
    }))
})

const filteredItems = computed<BestReplayItem[]>(() => filteredGroups.value.flatMap((group) => group.items))

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

// A single Rank #1 summary is meaningful only for one selected game/count scope.
const summary = computed<BestReplaySummary>(() => {
  const available = rawItems.value.filter((item) => item.isAvailable)
  const hasOneSelectedScope = selectedGame.value !== 'ALL' && selectedTicketCounts.value.length === 1
  const best = hasOneSelectedScope
    ? rawItems.value.find(
      (item) =>
        item.isAvailable &&
        item.rank === 1 &&
        item.game === selectedGame.value &&
        item.ticketCount === selectedTicketCounts.value[0],
    )
    : undefined
  const horizonDef = CANONICAL_HORIZONS.find((h) => h.key === selectedHorizon.value)
  const ticketCountDisplay = selectedGame.value === 'ALL'
    ? selectedTicketCounts.value.length === 1
      ? `${selectedTicketCounts.value[0]} count by game`
      : `${selectedTicketCounts.value.length} game-specific counts`
    : selectedGame.value === 'B649'
      ? selectedTicketCounts.value.length === 1
        ? `${selectedTicketCounts.value[0]} Prefix Count`
        : `Prefix Counts: ${selectedTicketCounts.value.join(', ')}`
      : selectedTicketCounts.value.length === 1
        ? `${selectedTicketCounts.value[0]} Tickets`
        : `Ticket Counts: ${selectedTicketCounts.value.join(', ')}`

  if (!best) {
    const mixedScope = !hasOneSelectedScope
    return {
      bestStrategyId: null,
      bestStrategyLabel: mixedScope
        ? 'No global leader'
        : available.length === 0
          ? 'Evidence Unavailable'
          : 'Source Rank #1 unavailable',
      ticketCount: ticketCountDisplay,
      horizon: horizonDef?.label || selectedHorizon.value,
      historicalHitRate: mixedScope ? 'See each group' : 'Unavailable',
      evaluatedTargets: null,
      baselineDelta: 'Unavailable',
      evidenceStatus: mixedScope ? 'HISTORICAL ONLY' : 'EVIDENCE UNAVAILABLE',
      totalAvailableRecords: available.length,
      game: selectedGame.value,
    }
  }

  return {
    bestStrategyId: best.strategyId,
    bestStrategyLabel: compactStrategyLabel(best.strategyId),
    ticketCount: `${best.ticketCount} ${best.game === 'B649' ? 'Prefix Count' : 'Tickets'}`,
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
  const targetGame = activeInspectGame.value
  const targetVersion = activeInspectStrategyVersion.value
  const targetCount = activeInspectTicketCount.value

  const byHorizon: Partial<Record<string, BestReplayItem | null>> = {}

  for (const h of CANONICAL_HORIZONS) {
    const match = allLoadedItems.value.find(
      (item) =>
        item.strategyId === targetId &&
        item.strategyVersion === targetVersion &&
        item.game === targetGame &&
        item.ticketCount === targetCount &&
        item.horizon === h.key,
    )
    if (match) {
      byHorizon[h.key] = match
    } else if (targetGame === 'P638' && targetCount === 1 && h.key !== 'FULL') {
      byHorizon[h.key] = createUnavailableItem(
        'P638',
        targetId,
        null,
        'p638_native',
        1,
        h.key,
        'NO_CANONICAL_WINDOW_EVIDENCE',
        `P638 canonical evidence does not publish an exact ${h.key} ranking window. Descriptive historical evidence only; does not infer future performance.`,
      )
    } else if (targetGame === 'T539' && targetCount === 1 && h.key !== 'FULL') {
      byHorizon[h.key] = createUnavailableItem(
        'T539',
        targetId,
        null,
        't539_native',
        1,
        h.key,
        'NO_CANONICAL_WINDOW_EVIDENCE',
        `T539 canonical evidence does not publish an exact ${h.key} ranking window. Descriptive historical evidence only; does not infer future performance.`,
      )
    } else {
      byHorizon[h.key] = null
    }
  }
  return byHorizon
})

// Matrix Rows Computation for 1..20 Grid
const matrixRows = computed<BestReplayMatrixRow[]>(() => {
  const strategyMap = new Map<string, { rowKey: string; strategyId: string; strategyVersion: string | null; methodFamily: string; game: GameCode }>()
  for (const item of allLoadedItems.value) {
    const rowKey = [item.game, item.strategyId, item.strategyVersion || 'VERSION_NOT_PROVIDED'].join('|')
    if (!strategyMap.has(rowKey)) {
      strategyMap.set(rowKey, {
        rowKey,
        strategyId: item.strategyId,
        strategyVersion: item.strategyVersion,
        methodFamily: item.methodFamily,
        game: item.game,
      })
    }
  }

  const rows: BestReplayMatrixRow[] = []

  for (const info of strategyMap.values()) {
    const cells: Partial<Record<TicketCount, BestReplayItem | null>> = {}

    for (const count of ALL_TICKET_COUNTS) {
      const match = allLoadedItems.value.find(
        (item) =>
          item.game === info.game &&
          item.strategyId === info.strategyId &&
          item.strategyVersion === info.strategyVersion &&
          item.ticketCount === count &&
          item.horizon === selectedHorizon.value,
      )
      cells[count] = match || null
    }

    rows.push({
      strategyId: info.rowKey,
      strategyLabel: `${info.strategyId} · ${info.strategyVersion || 'Version not provided'}`,
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
  activeInspectStrategyVersion.value = item.strategyVersion
  activeInspectGame.value = item.game
  activeInspectTicketCount.value = item.ticketCount
}

function handleMatrixCellSelect(rowKey: string, ticketCount: TicketCount): void {
  const item = matrixRows.value.find((row) => row.strategyId === rowKey)?.cells[ticketCount]
  if (!item || !item.isAvailable) return
  selectStrategyForInspection(item)
  selectedTicketCounts.value = [ticketCount]
  isMultiSelectMode.value = false
}

function isActiveInspection(item: BestReplayItem): boolean {
  return activeInspectStrategyId.value === item.strategyId &&
    activeInspectStrategyVersion.value === item.strategyVersion &&
    activeInspectGame.value === item.game &&
    activeInspectTicketCount.value === item.ticketCount
}

function getComparisonScopeStatus(item: BestReplayItem): string {
  const scopeKey = getComparisonScope(item).key
  const items = filteredGroups.value.find((group) => group.scope.key === scopeKey)?.items ?? []
  if (items.some((groupItem) => groupItem.isAvailable && groupItem.hitRate !== null)) {
    return 'Source rank and available rates are ordered only within this scope.'
  }
  if (items.some((groupItem) => groupItem.rank !== null)) {
    return 'Source rank is retained, but no usable rate is available in this scope.'
  }
  return 'No source rank or rate is available for this scope.'
}

const activeInspectMatrixRowId = computed<string | null>(() => {
  const row = matrixRows.value.find((candidate) => {
    const item = candidate.cells[activeInspectTicketCount.value]
    return item?.strategyId === activeInspectStrategyId.value &&
      item.strategyVersion === activeInspectStrategyVersion.value &&
      item.game === activeInspectGame.value
  })
  return row?.strategyId ?? null
})

// Watchers
watch([selectedGame, selectedHorizon, selectedTicketCounts], () => {
  currentPage.value = 1
  loadData()
})

watch([searchQuery, selectedFamily], () => {
  currentPage.value = 1
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
      description="Historical source rankings grouped by game, ticket or prefix count, and evaluation horizon."
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

    <!-- Game Switcher Bar (B649 / P638 / T539) -->
    <div class="game-switcher-panel" role="region" aria-label="Lottery Game Selection">
      <div class="game-switcher-label">
        <span class="game-label-text">Active Game:</span>
      </div>
      <div class="game-buttons-group" role="group" aria-label="Game Selector">
        <button
          type="button"
          class="game-nav-btn"
          :class="{ 'game-nav-btn--active': selectedGame === 'B649' }"
          :aria-pressed="selectedGame === 'B649'"
          data-testid="game-btn-b649"
          @click="selectGame('B649')"
        >
          <span class="game-code">B649</span>
          <span class="game-title">Big Lotto 6/49</span>
        </button>

        <button
          type="button"
          class="game-nav-btn"
          :class="{ 'game-nav-btn--active': selectedGame === 'P638' }"
          :aria-pressed="selectedGame === 'P638'"
          data-testid="game-btn-p638"
          @click="selectGame('P638')"
        >
          <span class="game-code">P638</span>
          <span class="game-title">Power Lotto 6/38</span>
        </button>

        <button
          type="button"
          class="game-nav-btn"
          :class="{ 'game-nav-btn--active': selectedGame === 'T539' }"
          :aria-pressed="selectedGame === 'T539'"
          data-testid="game-btn-t539"
          @click="selectGame('T539')"
        >
          <span class="game-code">T539</span>
          <span class="game-title">Daily Cash 5/39</span>
        </button>
      </div>
    </div>

    <!-- Main Summary Metrics Grid -->
    <div class="metrics-grid" data-testid="best-replay-metrics-grid">
      <MetricCard
        label="Best Strategy"
        :value="summary.bestStrategyLabel || 'None'"
        :subvalue="summary.bestStrategyId ? `Source Rank #1 · ${summary.game} · ${summary.ticketCount} (selected scope)` : 'No cross-group leader; use the scopes below'"
        variant="accent"
      />
      <MetricCard
        :label="selectedGame === 'B649' ? 'Prefix Count' : (selectedGame === 'ALL' ? 'Ticket / Prefix Counts' : 'Ticket Count')"
        :value="summary.ticketCount"
        :subvalue="isMultiSelectMode ? 'Multi-ticket selection active' : 'Single ticket dimension'"
      />
      <MetricCard
        label="Horizon"
        :value="summary.horizon"
        :subvalue="summary.evaluatedTargets !== null ? `${summary.evaluatedTargets.toLocaleString()} Historical Draws` : 'Sample count unknown'"
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
        subvalue="Deterministic historical replay evidence"
        :badge="summary.bestStrategyId ? `${summary.totalAvailableRecords} Records` : (summary.totalAvailableRecords > 0 ? 'Grouped Scope' : 'No Data')"
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

    <!-- Each overview remains inside one game's source-defined comparison scopes. -->
    <BestReplayOneToFiveOverview
      v-for="game in overviewGames"
      :key="game"
      :game="game"
      :horizon="selectedHorizon"
      :selected-ticket-count="selectedTicketCounts[0] || 1"
      :items-by-ticket-count="overviewItemsByGame[game]"
      @select-ticket="handleSelectTicketFromOverview"
    />

    <!-- High-Density Control & Query Filter Bar -->
    <FilterBar title="Evaluation Dimensions & Filters" :count="filteredItems.length" count-label="strategies">
      <div class="controls-form">
        <!-- Game Selector Dropdown (accessible fallback) -->
        <div class="control-group">
          <label for="game-select" class="control-label">Game</label>
          <select id="game-select" :value="selectedGame" class="select-input" data-testid="game-select" @change="handleGameDropdownChange">
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

      <!-- Ticket Count 1..5 Controls and Quick Presets -->
      <div class="ticket-control-row">
        <div class="ticket-header">
          <span class="control-label">Ticket Count / B649 Prefix Count (1–5 Primary, 1–20 Grid)</span>
          <div
            class="preset-buttons"
            role="group"
            :aria-label="selectedGame === 'B649' ? 'Prefix Count Presets' : (selectedGame === 'ALL' ? 'Game-Specific Count Presets' : 'Ticket Count Presets')"
          >
            <span class="preset-label">Quick Presets:</span>
            <button
              v-for="p in (['1', '2', '3', '4', '5', '10', '20', 'all'] as const)"
              :key="p"
              type="button"
              class="button button--sm"
              :class="{
                'button--primary': p === 'all' ? isMultiSelectMode : selectedTicketCounts.length === 1 && selectedTicketCounts[0] === Number(p),
                'button--quiet': !(p === 'all' ? isMultiSelectMode : selectedTicketCounts.length === 1 && selectedTicketCounts[0] === Number(p)),
              }"
              @click="applyPreset(p)"
            >
              {{ p === 'all' ? 'All Available' : `${p}${selectedGame === 'B649' ? ' Prefix' : (selectedGame === 'ALL' ? ' count' : 'T')}` }}
            </button>
            <button
              type="button"
              class="button button--sm button--quiet reset-rank-btn"
              data-testid="reset-rank-btn"
              title="Reset sorting to Official Rank order"
              @click="resetToOfficialRank"
            >
              Reset to Official Rank
            </button>
          </div>
        </div>

        <div
          class="ticket-buttons-grid"
          role="group"
          :aria-label="selectedGame === 'B649' ? 'Individual B649 Prefix Counts' : (selectedGame === 'ALL' ? 'Individual Game-Specific Counts' : 'Individual Ticket Counts')"
        >
          <button
            v-for="count in ALL_TICKET_COUNTS"
            :key="count"
            type="button"
            class="ticket-chip"
            :class="{
              'ticket-chip--selected': selectedTicketCounts.includes(count),
              'ticket-chip--available': availableTicketCountsForGame.includes(count),
              'ticket-chip--unavailable': !availableTicketCountsForGame.includes(count),
              'ticket-chip--primary': PRIMARY_TICKET_COUNTS.includes(count as PrimaryTicketCount),
            }"
            :aria-pressed="selectedTicketCounts.includes(count)"
            :data-testid="`ticket-btn-${count}`"
            :title="
              availableTicketCountsForGame.includes(count)
              ? `${selectedGame === 'B649' ? 'B649 prefix count' : (selectedGame === 'ALL' ? 'Game-specific count' : 'Ticket count')} ${count} (Canonical evidence available in ${selectedGame === 'ALL' ? 'at least one game' : selectedGame})`
                : `${selectedGame === 'B649' ? 'B649 prefix count' : (selectedGame === 'ALL' ? 'Game-specific count' : 'Ticket count')} ${count} (No canonical evidence recorded)`
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
      <button type="button" class="button button--primary" @click="resetToOfficialRank">
        Reset Filters
      </button>
    </EmptyState>

    <!-- Main Workspace Content by View Mode -->
    <template v-else>
      <!-- Mode 1: Ranking Table -->
      <div v-if="activeViewMode === 'table'" class="table-workspace">
        <div class="table-actions-header">
          <div class="table-title-meta">
            <span class="meta-label">Active Ordering:</span>
          <strong class="meta-val">{{ sortField === 'rank' ? 'Source Rank · within each scope' : `${sortField} ${sortDirection} · within each scope` }}</strong>
          </div>
          <button
            v-if="sortField !== 'rank' || sortDirection !== 'asc'"
            type="button"
            class="button button--sm button--quiet"
            @click="resetSort"
          >
            Reset to Official Rank
          </button>
        </div>

        <DataTable
          min-width="1100px"
          caption="Historical Strategy Records Grouped by Source Comparison Scope"
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
                Ticket / Prefix Count {{ sortField === 'ticketCount' ? (sortDirection === 'asc' ? '↑' : '↓') : '' }}
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

          <template v-for="(item, index) in paginatedItems" :key="item.id">
          <tr
            v-if="index === 0 || getComparisonScope(paginatedItems[index - 1]!).key !== getComparisonScope(item).key"
            class="comparison-scope-row"
            :data-testid="`comparison-group-${item.game}-${item.ticketCount}`"
          >
            <td colspan="12">
              <strong>{{ getComparisonScope(item).label }}</strong>
              <small>{{ getComparisonScopeStatus(item) }}</small>
            </td>
          </tr>
          <tr
            class="data-row"
            :class="{
              'data-row--active': isActiveInspection(item),
              'data-row--unavailable': !item.isAvailable,
            }"
            @click="selectStrategyForInspection(item)"
          >
            <td>
              <span v-if="item.rank !== null" class="rank-tag" :class="`rank-tag--${item.rank <= 3 ? 'top' : 'regular'}`">
                #{{ item.rank }}
                <small v-if="!item.isAvailable || item.hitRate === null">· Rate unavailable</small>
              </span>
              <span v-else class="text-muted">—</span>
            </td>
            <td>
              <div class="strategy-cell">
                <strong class="strategy-name">{{ item.strategyId }}</strong>
                <small class="strategy-sub">{{ item.methodFamily }} · {{ item.strategyVersion || 'Version not provided' }}</small>
              </div>
            </td>
            <td>
              <span class="game-tag">{{ item.game }}</span>
            </td>
            <td>
              <span class="ticket-tag">{{ item.game === 'B649' ? `${item.ticketCount} Prefix` : `${item.ticketCount}T` }}</span>
            </td>
            <td>
              <span class="horizon-tag">{{ item.horizonLabel }}</span>
            </td>
            <td class="font-mono">
              {{ item.evaluatedTargets !== null ? item.evaluatedTargets.toLocaleString() : 'Unknown' }}
            </td>
            <td class="font-mono">
              {{ item.winningTargets !== null ? item.winningTargets.toLocaleString() : 'Not provided' }}
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
          </template>

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
            description="Source records are shown by horizon. Each period is a separate scope; no rate or rank is selected across periods."
          />
          <BestReplayHorizonComparison
            :strategy-id="activeInspectStrategyId"
            :strategy-version="activeInspectStrategyVersion"
            :ticket-count="activeInspectTicketCount"
            :game="activeInspectGame"
            :items-by-horizon="inspectHorizonItems"
          />
        </div>
      </div>

      <!-- Mode 2: Horizon Comparison Dedicated View -->
      <div v-else-if="activeViewMode === 'comparison'" class="comparison-workspace">
        <div v-if="activeInspectStrategyId">
          <BestReplayHorizonComparison
            :strategy-id="activeInspectStrategyId"
            :strategy-version="activeInspectStrategyVersion"
            :ticket-count="activeInspectTicketCount"
            :game="activeInspectGame"
            :items-by-horizon="inspectHorizonItems"
          />
        </div>

        <article v-for="group in filteredGroups" :key="group.scope.key" class="panel comparison-scope-panel">
          <div class="panel__heading">
            <p class="step-label">One source-defined comparison scope</p>
            <h3>{{ group.scope.label }}</h3>
            <p>Select a strategy in this scope to inspect its source records by horizon.</p>
          </div>
          <div class="strategy-chips-list">
            <template v-for="item in group.items.slice(0, 30)" :key="item.id">
              <button
                type="button"
                class="strategy-chip"
                :class="{ 'strategy-chip--active': isActiveInspection(item) }"
                @click="selectStrategyForInspection(item)"
              >
                <span class="chip-rank">Source #{{ item.rank ?? '—' }}</span>
                <span class="chip-title">{{ item.strategyId }} · {{ item.strategyVersion || 'Version not provided' }}</span>
                <span class="chip-rate">{{ item.hitRateFormatted }}</span>
              </button>
            </template>
          </div>
        </article>
      </div>

      <!-- Mode 3: 1–20 Matrix Heatmap View -->
      <div v-else-if="activeViewMode === 'matrix'" class="matrix-workspace">
        <BestReplayMatrix
          :rows="matrixRows"
          :selected-ticket-count="activeInspectTicketCount"
          :selected-strategy-id="activeInspectMatrixRowId"
          @select-cell="handleMatrixCellSelect"
        />

        <div v-if="activeInspectStrategyId" class="drawer-section">
          <BestReplayHorizonComparison
            :strategy-id="activeInspectStrategyId"
            :strategy-version="activeInspectStrategyVersion"
            :ticket-count="activeInspectTicketCount"
            :game="activeInspectGame"
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

@media (max-width: 640px) {
  .view-mode-tabs {
    width: 100%;
    flex-wrap: wrap;
  }

  .view-mode-tabs > .button {
    flex: 1 1 140px;
    min-width: 0;
  }
}

.game-switcher-panel {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-top: 18px;
  margin-bottom: 18px;
  padding: 12px 16px;
  border-radius: var(--radius-md);
  background: rgba(15, 23, 42, 0.6);
  border: 1px solid var(--border-color);
  flex-wrap: wrap;
}

.game-switcher-label {
  font: 700 11px/1 var(--font-mono);
  color: var(--text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.game-buttons-group {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.game-nav-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-color);
  background: rgba(30, 41, 59, 0.7);
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.15s ease;
}

.game-nav-btn:hover {
  border-color: var(--border-hover);
  color: var(--text-primary);
  transform: translateY(-1px);
}

.game-nav-btn--active {
  border-color: var(--primary-color) !important;
  background: linear-gradient(135deg, rgba(124, 58, 237, 0.35) 0%, rgba(59, 130, 246, 0.25) 100%) !important;
  color: #fff !important;
  box-shadow: 0 0 12px rgba(124, 58, 237, 0.3);
}

.game-code {
  font: 800 12px/1 var(--font-mono);
  color: var(--text-accent);
}

.game-nav-btn--active .game-code {
  color: #fff;
}

.game-title {
  font-size: 12px;
  font-weight: 500;
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

.reset-rank-btn {
  margin-left: 8px;
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

.ticket-chip--primary {
  border-width: 1.5px;
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

.table-actions-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
  gap: 12px;
}

.table-title-meta {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
}

.meta-label {
  color: var(--text-tertiary);
}

.meta-val {
  color: var(--text-primary);
  font-family: var(--font-mono);
}

.comparison-scope-row td {
  padding: 10px 12px;
  background: rgba(56, 189, 248, 0.08);
  border-top: 2px solid var(--border-color);
}

.comparison-scope-row strong,
.comparison-scope-row small {
  display: block;
}

.comparison-scope-row strong {
  color: var(--text-primary);
  font-size: 11px;
}

.comparison-scope-row small {
  margin-top: 3px;
  color: var(--text-secondary);
  font-size: 10px;
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

.data-row--unavailable {
  opacity: 0.75;
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

.comparison-scope-panel {
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
</style>
