<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'

import { listHistoricalImportRuns, type HistoricalImportRunPage } from '../../api/historicalImports'
import {
  listHistoricalRunStrategies,
  listHistoricalRunReplayPortfolios,
  HistoricalResultsRequestError,
  type HistoricalReplayPageResponse,
  type HistoricalStrategySummaryListResponse,
  type HistoricalStrategySummaryView,
  type TicketCountFilter,
} from '../../api/historicalResults'
import {
  getOptimalReplayPortfolioRankings,
  isValidScoringArtifactSha256,
  ReplayPortfolioRankingsRequestError,
  type ReplayPortfolioRankingResponse,
} from '../../api/replayPortfolioRankings'
import {
  getReplayScoringOverallAggregate,
  getReplayScoringRun,
  listReplayScoringPredictions,
  listReplayScoringStrategyAggregates,
  ReplayScoringProjectionsRequestError,
  type ReplayOverallAggregateResponse,
  type ReplayScoredPredictionView,
  type ReplayScoringPredictionsQuery,
  type ReplayStrategyAggregateView,
} from '../../api/replayScoringProjections'
import type { LotteryType } from '../../api/strategies'
import {
  getReplayBackfillCoverage,
  isValidReplayDateRange,
  listReplayBackfillPredictions,
  listReplayBackfillStrategies,
  listReplayStrategyInventory,
  REPLAY_BACKFILL_LOTTERY_TYPES,
  REPLAY_BACKFILL_PERIODS,
  ReplayBackfillRequestError,
  type ReplayBackfillCoverage,
  type ReplayBackfillDataStatus,
  type ReplayBackfillLotteryType,
  type ReplayBackfillPeriod,
  type ReplayBackfillPredictionItem,
  type ReplayBackfillStrategyItem,
  type ReplayStrategyInventoryItem,
} from '../../api/replayBackfill'
import { lotteryTypeDisplayLabel } from '../../utils/lotteryDisplayLabel'
import LotteryNumberBall from '../../components/LotteryNumberBall.vue'
import {
  assessReplayScoreTrust,
  type ReplayScoreTrustAssessment,
} from './replayScoreTrust'

function lotteryLabel(value: string): string {
  return lotteryTypeDisplayLabel(value as LotteryType)
}

type Tab = 'overview' | 'optimal' | 'backfill'
type LoadState = 'idle' | 'loading' | 'ready' | 'empty' | 'error'
const TICKET_COUNTS: readonly TicketCountFilter[] = [10, 15, 20]

const activeTab = ref<Tab>('overview')

// --- Strategy-by-strategy historical replay (GET-only replay-backfill API) ---

const backfillInitialized = ref(false)
const backfillLotteryType = ref<ReplayBackfillLotteryType>('BIG_LOTTO')
const backfillStrategySearch = ref('')
const backfillStrategyId = ref('')
const backfillFromDate = ref('')
const backfillToDate = ref('')
const backfillPeriod = ref<ReplayBackfillPeriod>(50)
const backfillDateError = ref('')

const strategyCatalogState = ref<LoadState>('idle')
const strategyCatalogError = ref('')
const strategyCatalog = ref<ReplayBackfillStrategyItem[]>([])
const strategyCatalogCursor = ref<string | null>(null)
const strategyCatalogVisibleCount = ref(100)

const strategyInventoryState = ref<LoadState>('idle')
const strategyInventoryError = ref('')
const strategyInventory = ref<ReplayStrategyInventoryItem[]>([])

const coverageState = ref<LoadState>('idle')
const coverageError = ref('')
const coverage = ref<ReplayBackfillCoverage | null>(null)

const backfillPredictionsState = ref<LoadState>('idle')
const backfillPredictionsError = ref('')
const backfillPredictions = ref<ReplayBackfillPredictionItem[]>([])
const backfillPredictionRunId = ref('')
const backfillPredictionTotal = ref(0)
const backfillPredictionCursor = ref<string | null>(null)
const backfillPredictionHasQueried = ref(false)

const isPartialCoverage = computed(() => {
  if (!coverage.value) return false
  return (
    coverage.value.completed_cell_count < coverage.value.expected_cell_count ||
    coverage.value.failed_cell_count > 0 ||
    coverage.value.closed_cell_count > 0
  )
})

let backfillStrategyController: AbortController | undefined
let strategyInventoryController: AbortController | undefined
let backfillCoverageController: AbortController | undefined
let backfillPredictionsController: AbortController | undefined
let backfillStrategyGeneration = 0
let strategyInventoryGeneration = 0
let backfillCoverageGeneration = 0
let backfillPredictionsGeneration = 0

interface ReplayStrategyCatalogRow {
  strategy_id: string
  strategy_version: string | null
  display_name: string
  lottery_type: ReplayBackfillLotteryType
  lifecycle_status: string
  data_status: string
  source_kind: string
  executable: boolean
  reconstructable: boolean | null
  wrapper_callable: boolean | null
  backfill_native_binding: boolean | null
  backfill_runnable: boolean | null
  execution_block_reason: string | null
  available_target_count: number | null
  training_status: string
  execution_capability: string
  historical_data_count: number | null
  historical_execution_count: number | null
  reconstruction_reason: string
  from_inventory: boolean
}

const statusLabels: Record<ReplayBackfillDataStatus, string> = {
  HAS_HISTORY: '有歷史資料',
  REBUILDABLE: '可重建',
  NO_HISTORY: '無歷史資料',
  ARTIFACT_ONLY: '僅有研究產物',
  CODE_ONLY: '僅有程式',
  REJECTED: '已拒絕',
}

function dataStatusLabel(value: string): string {
  return Object.prototype.hasOwnProperty.call(statusLabels, value)
    ? statusLabels[value as ReplayBackfillDataStatus]
    : `未註冊或未辨識（${value}）`
}

function dataStatusReason(value: string): string {
  switch (value) {
    case 'HAS_HISTORY':
      return 'API 回報此策略有歷史資料。'
    case 'REBUILDABLE':
      return 'API 回報此策略可重建；可用回放期數另列，未提供數值不代表 0。'
    case 'NO_HISTORY':
      return 'API 回報此策略沒有歷史資料。'
    case 'ARTIFACT_ONLY':
      return '目前僅回報研究產物，未表示已部署或可即時預測。'
    case 'CODE_ONLY':
      return '目前僅回報程式資料，沒有可用歷史回放期數。'
    case 'REJECTED':
      return 'API 回報此策略資料狀態為已拒絕。'
    default:
      return 'API 回報了未註冊或未辨識的資料狀態；保留原始代碼供辨識。'
  }
}

function lifecycleLabel(value: string): string {
  return `生命週期：${value}`
}

function trainingStatusLabel(value: string): string {
  switch (value) {
    case 'NOT_TRAINABLE':
      return '此策略不需要模型訓練。'
    case 'NOT_RUN':
      return '尚未執行重新訓練。'
    case 'HISTORICAL_ARTIFACT':
      return '僅有封存研究結果。'
    case 'API_NOT_PROVIDED':
      return '策略清冊未提供訓練狀態。'
    default:
      return `訓練狀態：${value}`
  }
}

function strategyIdentityKey(
  strategy: Pick<ReplayBackfillStrategyItem, 'lottery_type' | 'strategy_id' | 'strategy_version'>,
): string {
  return `${strategy.lottery_type}\u0000${strategy.strategy_id}\u0000${strategy.strategy_version ?? ''}`
}

function predictionIdentityKey(item: ReplayBackfillPredictionItem): string {
  return [
    item.lottery_type,
    item.strategy_id,
    item.strategy_version,
    item.target_draw_number,
    item.target_draw_date,
  ].join('\u0000')
}

function inventoryStrategyRow(strategy: ReplayStrategyInventoryItem): ReplayStrategyCatalogRow {
  return {
    strategy_id: strategy.strategy_id,
    strategy_version: strategy.strategy_version,
    display_name: strategy.display_name,
    lottery_type: strategy.lottery_type,
    lifecycle_status: strategy.lifecycle_status,
    data_status: strategy.replay_data_status,
    source_kind: strategy.source_kind,
    executable: strategy.execution_capability === 'EXECUTABLE',
    reconstructable: strategy.reconstructable,
    wrapper_callable: strategy.wrapper_callable,
    backfill_native_binding: strategy.backfill_native_binding,
    backfill_runnable: strategy.backfill_runnable,
    execution_block_reason: strategy.execution_block_reason,
    available_target_count: null,
    training_status: 'API_NOT_PROVIDED',
    execution_capability: strategy.execution_capability,
    historical_data_count: strategy.historical_data_count,
    historical_execution_count: strategy.historical_execution_count,
    reconstruction_reason: strategy.reconstruction_reason,
    from_inventory: true,
  }
}

function backfillStrategyRow(strategy: ReplayBackfillStrategyItem): ReplayStrategyCatalogRow {
  return {
    ...strategy,
    execution_capability: strategy.executable ? 'EXECUTABLE' : 'UNAVAILABLE',
    reconstructable: null,
    wrapper_callable: null,
    backfill_native_binding: null,
    backfill_runnable: null,
    execution_block_reason: null,
    historical_data_count: null,
    historical_execution_count: null,
    reconstruction_reason: '',
    from_inventory: false,
  }
}

const strategyRows = computed<ReplayStrategyCatalogRow[]>(() => {
  const rows = new Map<string, ReplayStrategyCatalogRow>()
  for (const strategy of strategyInventory.value) {
    const row = inventoryStrategyRow(strategy)
    rows.set(strategyIdentityKey(row), row)
  }
  for (const strategy of strategyCatalog.value) {
    const row = backfillStrategyRow(strategy)
    const key = strategyIdentityKey(row)
    const inventoryRow = rows.get(key)
    if (!inventoryRow) {
      rows.set(key, row)
      continue
    }
    rows.set(key, {
      ...row,
      ...inventoryRow,
      available_target_count: strategy.available_target_count,
      training_status: strategy.training_status,
    })
  }
  return [...rows.values()]
})

const filteredStrategyRows = computed(() => {
  const query = backfillStrategySearch.value.trim().toLocaleLowerCase()
  return strategyRows.value.filter((strategy) => {
    if (strategy.lottery_type !== backfillLotteryType.value) return false
    if (!query) return true
    return `${strategy.strategy_id} ${strategy.strategy_version ?? ''} ${strategy.display_name}`
      .toLocaleLowerCase()
      .includes(query)
  })
})

const backfillStrategyQueryOptions = computed(() => {
  const byStrategyId = new Map<string, { displayNames: Set<string>; versions: Set<string> }>()
  for (const strategy of filteredStrategyRows.value) {
    const option = byStrategyId.get(strategy.strategy_id) ?? {
      displayNames: new Set<string>(),
      versions: new Set<string>(),
    }
    option.displayNames.add(strategy.display_name)
    option.versions.add(strategy.strategy_version ?? '版本未提供')
    byStrategyId.set(strategy.strategy_id, option)
  }
  return [...byStrategyId].map(([strategy_id, option]) => ({
    strategy_id,
    label: `${[...option.displayNames].join(' / ')} · ${strategy_id} · versions: ${[...option.versions].join(', ')}`,
  }))
})

const visibleStrategyRows = computed(() =>
  filteredStrategyRows.value.slice(0, strategyCatalogVisibleCount.value),
)

const hasMoreStrategyRows = computed(() =>
  filteredStrategyRows.value.length > strategyCatalogVisibleCount.value || Boolean(strategyCatalogCursor.value),
)

const strategyIdentityState = computed<LoadState>(() => {
  if (strategyRows.value.length) return 'ready'
  if (strategyInventoryState.value === 'loading' || strategyCatalogState.value === 'loading') return 'loading'
  if (strategyInventoryState.value === 'idle' && strategyCatalogState.value === 'idle') return 'idle'
  if (strategyInventoryState.value === 'empty' && strategyCatalogState.value === 'empty') return 'empty'
  return 'error'
})

const strategyIdentityError = computed(() => {
  const reasons = [
    strategyInventoryState.value === 'error' ? strategyInventoryError.value : '',
    strategyCatalogState.value === 'error' ? strategyCatalogError.value : '',
  ].filter(Boolean)
  return `資料取得失敗，無法確認策略清冊。${reasons.join('；')}`
})

function strategyDisplayName(item: ReplayBackfillPredictionItem): string {
  return strategyRows.value.find((strategy) =>
    strategy.lottery_type === item.lottery_type &&
    strategy.strategy_id === item.strategy_id &&
    strategy.strategy_version === item.strategy_version,
  )?.display_name ?? item.strategy_id
}

function executionCapabilityLabel(value: string): string {
  switch (value) {
    case 'EXECUTABLE':
      return '具有 Replay 執行能力'
    case 'UNAVAILABLE':
      return '目前沒有可用 Replay 執行器'
    case 'ARTIFACT_ONLY':
      return '僅有研究產物，沒有可用 Replay 執行器'
    default:
      return `執行能力：${value}`
  }
}

function wrapperCallableLabel(value: boolean | null): string {
  if (value === true) return 'Wrapper 可呼叫'
  if (value === false) return 'Wrapper 不可呼叫'
  return 'Wrapper 狀態未提供'
}

function nativeBackfillLabel(binding: boolean | null, runnable: boolean | null): string {
  const bindingValue = binding === null ? 'null' : String(binding)
  const runnableValue = runnable === null ? '未提供' : String(runnable)
  const rawState = `(binding=${bindingValue}, runnable=${runnableValue})`
  if (binding === false) return `未證明可正式回填：沒有 Native binding ${rawState}`
  if (binding === null) return `未證明可正式回填：Native binding 未知 ${rawState}`
  if (runnable === true) return `Native Backfill 可執行 ${rawState}`
  if (runnable === false) return `已有 Native binding，但目前不可執行 ${rawState}`
  return `Native runnable 狀態未提供 ${rawState}`
}

function predictionCutoffLabel(item: ReplayBackfillPredictionItem): string {
  const cutoff = item.prediction_cutoff
  if (!cutoff) return 'API未提供'
  return cutoff.reason_code ? `${cutoff.status} · ${cutoff.reason_code}` : cutoff.status
}

function clearPredictionResults(): void {
  backfillPredictionsController?.abort()
  backfillPredictionsGeneration += 1
  backfillPredictionsState.value = 'idle'
  backfillPredictionsError.value = ''
  backfillPredictions.value = []
  backfillPredictionRunId.value = ''
  backfillPredictionTotal.value = 0
  backfillPredictionCursor.value = null
  backfillPredictionHasQueried.value = false
}

watch(
  [backfillLotteryType, backfillStrategyId, backfillFromDate, backfillToDate, backfillPeriod],
  () => {
    clearPredictionResults()
  },
)

watch(backfillLotteryType, () => {
  backfillStrategyId.value = ''
  backfillStrategySearch.value = ''
  strategyCatalogVisibleCount.value = 100
  backfillInitialized.value = true
  void loadStrategyInventory()
  void loadStrategyCatalog(true)
  void loadCoverage()
})

function requestErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof ReplayBackfillRequestError && error.status === 503) {
    const status = error.message.includes('HTTP 503') ? '' : 'HTTP 503，'
    return `${error.message}（${status}服務暫不可用）`
  }
  return error instanceof Error ? error.message : fallback
}

async function loadStrategyCatalog(reset: boolean): Promise<void> {
  if (reset) {
    backfillStrategyController?.abort()
    strategyCatalog.value = []
    strategyCatalogCursor.value = null
    strategyCatalogVisibleCount.value = 100
  }
  const requestedCursor = reset ? null : strategyCatalogCursor.value
  if (!reset && !requestedCursor) return
  backfillStrategyController?.abort()
  const controller = new AbortController()
  backfillStrategyController = controller
  const generation = ++backfillStrategyGeneration
  strategyCatalogState.value = 'loading'
  strategyCatalogError.value = ''
  try {
    const page = await listReplayBackfillStrategies(
      {
        lotteryType: backfillLotteryType.value,
        q: backfillStrategySearch.value,
        limit: 100,
        cursor: requestedCursor,
      },
      controller.signal,
    )
    if (controller.signal.aborted || generation !== backfillStrategyGeneration) return
    if (!page.items.length && page.total_count > 0) {
      throw new Error('策略清單回傳空頁，但 API 仍回報有資料；清單狀態無法確認。')
    }
    const current = reset ? [] : strategyCatalog.value
    const known = new Set(current.map(strategyIdentityKey))
    const newItems = page.items.filter((item) => {
      const key = strategyIdentityKey(item)
      if (known.has(key)) return false
      known.add(key)
      return true
    })
    strategyCatalog.value = [...current, ...newItems]
    if (requestedCursor && page.next_cursor === requestedCursor) {
      throw new Error('策略清單分頁游標沒有前進，已停止載入以避免重複資料。')
    }
    strategyCatalogCursor.value = page.next_cursor
    strategyCatalogState.value = strategyCatalog.value.length ? 'ready' : 'empty'
  } catch (error) {
    if (controller.signal.aborted || generation !== backfillStrategyGeneration) return
    strategyCatalogError.value = requestErrorMessage(error, '無法載入策略清單')
    strategyCatalogState.value = 'error'
  }
}

async function loadStrategyInventory(): Promise<void> {
  strategyInventoryController?.abort()
  const controller = new AbortController()
  strategyInventoryController = controller
  const generation = ++strategyInventoryGeneration
  strategyInventoryState.value = 'loading'
  strategyInventoryError.value = ''
  strategyInventory.value = []
  try {
    const result = await listReplayStrategyInventory(backfillLotteryType.value, controller.signal)
    if (controller.signal.aborted || generation !== strategyInventoryGeneration) return
    strategyInventory.value = result.strategies
    strategyInventoryState.value = result.strategies.length ? 'ready' : 'empty'
  } catch (error) {
    if (controller.signal.aborted || generation !== strategyInventoryGeneration) return
    strategyInventoryError.value = requestErrorMessage(error, '無法載入正式策略 inventory')
    strategyInventoryState.value = 'error'
  }
}

async function loadCoverage(): Promise<void> {
  backfillCoverageController?.abort()
  const controller = new AbortController()
  backfillCoverageController = controller
  const generation = ++backfillCoverageGeneration
  coverageState.value = 'loading'
  coverageError.value = ''
  coverage.value = null
  try {
    const result = await getReplayBackfillCoverage(backfillLotteryType.value, controller.signal)
    if (controller.signal.aborted || generation !== backfillCoverageGeneration) return
    coverage.value = result
    coverageState.value = 'ready'
  } catch (error) {
    if (controller.signal.aborted || generation !== backfillCoverageGeneration) return
    coverageError.value = requestErrorMessage(error, '無法載入回放覆蓋資料')
    coverageState.value = 'error'
  }
}

function activateBackfill(): void {
  activeTab.value = 'backfill'
  if (backfillInitialized.value) return
  backfillInitialized.value = true
  void loadStrategyInventory()
  void loadStrategyCatalog(true)
  void loadCoverage()
}

function searchBackfillStrategies(): void {
  backfillStrategyId.value = ''
  clearPredictionResults()
  void loadStrategyCatalog(true)
}

function loadMoreBackfillStrategies(): void {
  if (filteredStrategyRows.value.length > strategyCatalogVisibleCount.value) {
    strategyCatalogVisibleCount.value += 100
  }
  if (strategyCatalogCursor.value) void loadStrategyCatalog(false)
}

function validateBackfillDates(): boolean {
  if (!isValidReplayDateRange(backfillFromDate.value, backfillToDate.value)) {
    backfillDateError.value = '請輸入有效日期，且起始日期不可晚於結束日期。'
    return false
  }
  backfillDateError.value = ''
  return true
}

async function loadBackfillPredictionPage(loadMore: boolean): Promise<void> {
  if (!validateBackfillDates()) return
  const requestedCursor = loadMore ? backfillPredictionCursor.value : null
  if (loadMore && !requestedCursor) return
  const query = {
    lotteryType: backfillLotteryType.value,
    ...(backfillStrategyId.value ? { strategyId: backfillStrategyId.value } : {}),
    ...(backfillFromDate.value ? { fromDate: backfillFromDate.value } : {}),
    ...(backfillToDate.value ? { toDate: backfillToDate.value } : {}),
    period: backfillPeriod.value,
    limit: 50,
    cursor: requestedCursor,
  }
  backfillPredictionsController?.abort()
  const controller = new AbortController()
  backfillPredictionsController = controller
  const generation = ++backfillPredictionsGeneration
  backfillPredictionsState.value = 'loading'
  backfillPredictionsError.value = ''
  backfillPredictionHasQueried.value = true
  try {
    const page = await listReplayBackfillPredictions(query, controller.signal)
    if (controller.signal.aborted || generation !== backfillPredictionsGeneration) return
    if (loadMore && (page.run_id ?? '') !== backfillPredictionRunId.value) {
      throw new Error('Replay run changed during pagination; query again to avoid mixing runs.')
    }
    if (requestedCursor && page.next_cursor === requestedCursor) {
      throw new Error('預測清單分頁游標沒有前進，已停止載入以避免重複資料。')
    }
    if (!page.items.length && page.total_count > 0) {
      throw new Error('Replay API returned an empty page while reporting results; query again to avoid skipping data.')
    }
    const current = loadMore ? backfillPredictions.value : []
    const known = new Set(current.map(predictionIdentityKey))
    const newItems = page.items.filter((item) => {
      const key = predictionIdentityKey(item)
      if (known.has(key)) return false
      known.add(key)
      return true
    })
    backfillPredictions.value = [...current, ...newItems]
    backfillPredictionRunId.value = page.run_id ?? ''
    backfillPredictionTotal.value = page.total_count
    backfillPredictionCursor.value = page.next_cursor
    backfillPredictionsState.value = backfillPredictions.value.length ? 'ready' : 'empty'
  } catch (error) {
    if (controller.signal.aborted || generation !== backfillPredictionsGeneration) return
    backfillPredictionsError.value = requestErrorMessage(error, '無法查詢正式 Replay 資料')
    backfillPredictionsState.value = 'error'
  }
}

function queryBackfillPredictions(): void {
  clearPredictionResults()
  void loadBackfillPredictionPage(false)
}

function loadMoreBackfillPredictions(): void {
  void loadBackfillPredictionPage(true)
}

function actualSpecialLabel(lotteryType: ReplayBackfillLotteryType): string {
  if (lotteryType === 'BIG_LOTTO') return '官方特別號'
  if (lotteryType === 'POWER_LOTTO') return '官方第二區'
  return '特別號／第二區（539 不適用）'
}

function showNumbers(numbers: number[]): string {
  return numbers.length ? numbers.join('、') : '—'
}

function scoreTrust(item: ReplayBackfillPredictionItem): ReplayScoreTrustAssessment {
  return assessReplayScoreTrust(item)
}

function scoreTrustLabel(item: ReplayBackfillPredictionItem): string {
  switch (scoreTrust(item).status) {
    case 'VERIFIED':
      return '已評估結果'
    case 'NOT_COMPUTED':
      return '尚未計算'
    case 'UNVERIFIABLE':
      return '評估狀態未確認'
    case 'INCONSISTENT':
      return '資料核對不一致'
  }
  return '評估狀態未確認'
}

function bestMainHitsLabel(item: ReplayBackfillPredictionItem): string {
  const assessment = scoreTrust(item)
  if (assessment.status === 'INCONSISTENT') return '資料核對不一致'
  if (assessment.aggregate_status === 'VERIFIED' && item.best_main_hits !== null) {
    return String(item.best_main_hits)
  }
  if (assessment.aggregate_status === 'NOT_COMPUTED') return '尚未計算'
  if (item.best_main_hits !== null) return `${item.best_main_hits}（評估狀態未確認）`
  return '評估狀態未確認'
}

function ticketMainHitsLabel(item: ReplayBackfillPredictionItem, ticketIndex: number): string {
  const result = scoreTrust(item).tickets[ticketIndex]
  if (!result) return '評估狀態未確認'
  if (result.status === 'INCONSISTENT') {
    return `資料核對不一致（來源 ${result.source_hits}；集合交集 ${result.computed_hits}）`
  }
  if (result.status === 'VERIFIED') return String(result.computed_hits)
  if (result.status === 'NOT_COMPUTED') return '尚未計算'
  return '評估狀態未確認'
}

function specialHitLabel(item: ReplayBackfillPredictionItem, value: boolean | null): string {
  if (value === null) return '尚未計算'
  if (scoreTrust(item).status !== 'VERIFIED') return '評估狀態未確認'
  return value ? '命中' : '未命中'
}

function prizeTierLabel(item: ReplayBackfillPredictionItem, value: string | null): string {
  if (scoreTrust(item).status !== 'VERIFIED') return '評估狀態未確認'
  return value ?? '—'
}

function portfolioAnyPrizeLabel(
  value: boolean | null | undefined,
  item: ReplayBackfillPredictionItem,
): string {
  if (value === null) return '尚未計算'
  if (value === undefined) return 'API未提供'
  if (scoreTrust(item).status !== 'VERIFIED') return '評估狀態未確認'
  if (value === true) return '中獎'
  if (value === false) return '未命中'
  return 'API未提供'
}

// --- Overview replay (req #4): all strategies for one run + ticket count -----

const runsState = ref<LoadState>('loading')
const runsError = ref('')
const runs = ref<HistoricalImportRunPage['items']>([])
const selectedRunId = ref('')
const selectedTicketCount = ref<TicketCountFilter>(10)

const strategiesState = ref<LoadState>('idle')
const strategiesError = ref('')
const strategies = ref<HistoricalStrategySummaryView[]>([])
const selectedStrategyId = ref('')

const replayState = ref<LoadState>('idle')
const replayError = ref('')
const replayPage = ref<HistoricalReplayPageResponse | null>(null)
const m4plusOnly = ref(false)
const replayOffset = ref(0)
const REPLAY_PAGE_SIZE = 20

let runsController: AbortController | undefined
let strategiesController: AbortController | undefined
let replayController: AbortController | undefined

async function loadRuns(): Promise<void> {
  runsController?.abort()
  const controller = new AbortController()
  runsController = controller
  runsState.value = 'loading'
  runsError.value = ''
  try {
    const page = await listHistoricalImportRuns(controller.signal)
    if (controller.signal.aborted) return
    runs.value = page.items
    runsState.value = page.items.length ? 'ready' : 'empty'
  } catch (error) {
    if (controller.signal.aborted) return
    runsError.value = error instanceof Error ? error.message : 'Unable to load runs'
    runsState.value = 'error'
  }
}

function hitRate(summary: HistoricalStrategySummaryView): string {
  if (summary.evaluated_draws === 0) return '—'
  return `${((summary.m4plus_hit_count / summary.evaluated_draws) * 100).toFixed(1)}%`
}

async function loadStrategies(): Promise<void> {
  if (!selectedRunId.value) return
  strategiesController?.abort()
  const controller = new AbortController()
  strategiesController = controller
  strategiesState.value = 'loading'
  strategiesError.value = ''
  selectedStrategyId.value = ''
  replayPage.value = null
  replayState.value = 'idle'
  try {
    const response: HistoricalStrategySummaryListResponse = await listHistoricalRunStrategies(
      selectedRunId.value,
      selectedTicketCount.value,
      controller.signal,
    )
    if (controller.signal.aborted) return
    strategies.value = response.items
    strategiesState.value = response.items.length ? 'ready' : 'empty'
  } catch (error) {
    if (controller.signal.aborted) return
    strategiesError.value =
      error instanceof HistoricalResultsRequestError
        ? error.message
        : error instanceof Error
          ? error.message
          : 'Unable to load strategies'
    strategiesState.value = 'error'
  }
}

async function loadReplay(): Promise<void> {
  if (!selectedRunId.value || !selectedStrategyId.value) return
  replayController?.abort()
  const controller = new AbortController()
  replayController = controller
  replayState.value = 'loading'
  replayError.value = ''
  try {
    const page = await listHistoricalRunReplayPortfolios(
      selectedRunId.value,
      {
        strategyId: selectedStrategyId.value,
        ticketCount: selectedTicketCount.value,
        m4plusOnly: m4plusOnly.value,
        limit: REPLAY_PAGE_SIZE,
        offset: replayOffset.value,
      },
      controller.signal,
    )
    if (controller.signal.aborted) return
    replayPage.value = page
    replayState.value = page.items.length ? 'ready' : 'empty'
  } catch (error) {
    if (controller.signal.aborted) return
    replayError.value = error instanceof Error ? error.message : 'Unable to load replay portfolios'
    replayState.value = 'error'
  }
}

function chooseStrategy(strategyId: string): void {
  selectedStrategyId.value = strategyId
  replayOffset.value = 0
  void loadReplay()
}

function nextReplayPage(): void {
  if (!replayPage.value) return
  if (replayOffset.value + REPLAY_PAGE_SIZE >= replayPage.value.total_count) return
  replayOffset.value += REPLAY_PAGE_SIZE
  void loadReplay()
}

function previousReplayPage(): void {
  replayOffset.value = Math.max(0, replayOffset.value - REPLAY_PAGE_SIZE)
  void loadReplay()
}

void loadRuns()

// --- Optimal replay (req #3): rank-1 portfolios for one scoring artifact -----

const scoringArtifactSha256 = ref('')
const topK = ref(10)
const optimalState = ref<LoadState>('idle')
const optimalError = ref('')
const optimalResult = ref<ReplayPortfolioRankingResponse | null>(null)
let optimalController: AbortController | undefined

const shaInputInvalid = ref(false)
const scoringDetailVisible = ref(false)
const scoringDetailState = ref<LoadState>('idle')
const scoringDetailError = ref('')
const scoringDetailRun = ref<Awaited<ReturnType<typeof getReplayScoringRun>> | null>(null)
const scoringStrategyAggregates = ref<ReplayStrategyAggregateView[]>([])
const scoringOverallAggregate = ref<ReplayOverallAggregateResponse | null>(null)
const scoringPredictions = ref<ReplayScoredPredictionView[]>([])
const scoringPredictionsState = ref<LoadState>('idle')
const scoringPredictionsError = ref('')
const predictionFilters = ref({ targetDraw: '', strategyId: '', status: '', tier: '' })
let scoringDetailController: AbortController | undefined
let scoringPredictionsController: AbortController | undefined

const aggregateCountFields = [
  { key: 'source_snapshot_count', label: 'Source snapshots' },
  { key: 'scored_count', label: 'Scored' },
  { key: 'history_closed_count', label: 'History closed' },
  { key: 'prediction_closed_count', label: 'Prediction closed' },
  { key: 'target_outcome_not_found_count', label: 'Outcome not found' },
  { key: 'target_identity_mismatch_count', label: 'Identity mismatch' },
] as const

const prizeCountFields = [
  { key: 'first_prize_count', label: '1st prize' },
  { key: 'second_prize_count', label: '2nd prize' },
  { key: 'third_prize_count', label: '3rd prize' },
  { key: 'fourth_prize_count', label: '4th prize' },
  { key: 'fifth_prize_count', label: '5th prize' },
  { key: 'sixth_prize_count', label: '6th prize' },
  { key: 'seventh_prize_count', label: '7th prize' },
  { key: 'general_prize_count', label: 'General prize' },
  { key: 'no_prize_count', label: 'No prize' },
] as const

function clearScoringDetail(): void {
  scoringDetailController?.abort()
  scoringPredictionsController?.abort()
  scoringDetailVisible.value = false
  scoringDetailState.value = 'idle'
  scoringDetailError.value = ''
  scoringDetailRun.value = null
  scoringStrategyAggregates.value = []
  scoringOverallAggregate.value = null
  scoringPredictions.value = []
  scoringPredictionsState.value = 'idle'
  scoringPredictionsError.value = ''
}

function resetOptimalSelection(): void {
  optimalController?.abort()
  optimalResult.value = null
  optimalState.value = 'idle'
  optimalError.value = ''
  shaInputInvalid.value = false
  clearScoringDetail()
}

function apiFailureLabel(status: number, errorCode: string | undefined): string {
  if (errorCode?.toUpperCase().includes('NOT_CONFIGURED')) return 'SOURCE_NOT_CONFIGURED'
  if (status === 0 || status === 503) return 'API_UNAVAILABLE'
  return 'HTTP_ERROR'
}

function replayApiErrorMessage(error: unknown, label: string): string {
  if (
    error instanceof ReplayScoringProjectionsRequestError ||
    error instanceof ReplayPortfolioRankingsRequestError
  ) {
    const statusLabel = apiFailureLabel(error.status, error.errorCode)
    const status = error.status > 0 ? ' (HTTP ' + error.status + ')' : ''
    return statusLabel + status + ': ' + error.message
  }
  const detail = error instanceof Error ? error.message : 'Unknown API error.'
  return 'API_UNAVAILABLE: ' + label + ': ' + detail
}

function scoringErrorMessage(error: unknown): string {
  return replayApiErrorMessage(error, 'Scoring detail request failed')
}
function selectedPredictionFilters(): ReplayScoringPredictionsQuery {
  const filters = predictionFilters.value
  return {
    ...(filters.targetDraw ? { target_draw: filters.targetDraw.trim() } : {}),
    ...(filters.strategyId ? { strategy_id: filters.strategyId.trim() } : {}),
    ...(filters.status ? { status: filters.status.trim() } : {}),
    ...(filters.tier ? { tier: filters.tier.trim() } : {}),
  }
}

function isCurrentScoringArtifact(hash: string, signal: AbortSignal): boolean {
  return (
    !signal.aborted &&
    optimalResult.value?.source_scoring_artifact_payload_sha256 === hash
  )
}

async function loadScoringArtifactDetail(): Promise<void> {
  const hash = optimalResult.value?.source_scoring_artifact_payload_sha256 ?? ''
  scoringDetailVisible.value = true
  if (!isValidScoringArtifactSha256(hash)) {
    scoringDetailState.value = 'error'
    scoringDetailError.value =
      'The ranking response does not contain a valid source scoring artifact SHA-256.'
    scoringDetailRun.value = null
    scoringStrategyAggregates.value = []
    scoringOverallAggregate.value = null
    scoringPredictions.value = []
    scoringPredictionsState.value = 'idle'
    return
  }

  scoringDetailController?.abort()
  scoringPredictionsController?.abort()
  const controller = new AbortController()
  scoringDetailController = controller
  scoringDetailState.value = 'loading'
  scoringDetailError.value = ''
  scoringPredictionsState.value = 'loading'
  scoringPredictionsError.value = ''
  scoringDetailRun.value = null
  scoringStrategyAggregates.value = []
  scoringOverallAggregate.value = null
  scoringPredictions.value = []
  try {
    const [run, predictions, strategyAggregates, overallAggregate] = await Promise.all([
      getReplayScoringRun(hash, controller.signal),
      listReplayScoringPredictions(hash, selectedPredictionFilters(), controller.signal),
      listReplayScoringStrategyAggregates(hash, controller.signal),
      getReplayScoringOverallAggregate(hash, controller.signal),
    ])
    if (!isCurrentScoringArtifact(hash, controller.signal)) return
    if (run.scoring_artifact_payload_sha256 !== hash) {
      throw new ReplayScoringProjectionsRequestError(
        'The returned scoring artifact identity did not match the ranking source.',
        502,
      )
    }
    scoringDetailRun.value = run
    scoringPredictions.value = predictions
    scoringStrategyAggregates.value = strategyAggregates
    scoringOverallAggregate.value = overallAggregate
    scoringDetailState.value = 'ready'
    scoringPredictionsState.value = predictions.length ? 'ready' : 'empty'
  } catch (error) {
    if (!isCurrentScoringArtifact(hash, controller.signal)) return
    scoringDetailError.value = scoringErrorMessage(error)
    scoringDetailState.value = 'error'
    scoringPredictionsState.value = 'error'
  }
}

async function loadFilteredScoringPredictions(): Promise<void> {
  const hash = optimalResult.value?.source_scoring_artifact_payload_sha256 ?? ''
  if (!isValidScoringArtifactSha256(hash)) {
    scoringPredictionsState.value = 'error'
    scoringPredictionsError.value =
      'The ranking response does not contain a valid source scoring artifact SHA-256.'
    return
  }
  scoringPredictionsController?.abort()
  const controller = new AbortController()
  scoringPredictionsController = controller
  scoringPredictionsState.value = 'loading'
  scoringPredictionsError.value = ''
  scoringPredictions.value = []
  try {
    const predictions = await listReplayScoringPredictions(
      hash,
      selectedPredictionFilters(),
      controller.signal,
    )
    if (!isCurrentScoringArtifact(hash, controller.signal)) return
    scoringPredictions.value = predictions
    scoringPredictionsState.value = predictions.length ? 'ready' : 'empty'
  } catch (error) {
    if (!isCurrentScoringArtifact(hash, controller.signal)) return
    scoringPredictionsError.value = scoringErrorMessage(error)
    scoringPredictionsState.value = 'error'
  }
}


async function loadOptimalRankings(): Promise<void> {
  if (!isValidScoringArtifactSha256(scoringArtifactSha256.value)) {
    shaInputInvalid.value = true
    return
  }
  clearScoringDetail()
  shaInputInvalid.value = false
  optimalController?.abort()
  const controller = new AbortController()
  optimalController = controller
  optimalState.value = 'loading'
  optimalError.value = ''
  try {
    const result = await getOptimalReplayPortfolioRankings(
      scoringArtifactSha256.value,
      topK.value,
      controller.signal,
    )
    if (controller.signal.aborted) return
    optimalResult.value = result
    optimalState.value = result.groups.some((group) => group.candidates.length) ? 'ready' : 'empty'
  } catch (error) {
    if (controller.signal.aborted) return
    optimalError.value =
      error instanceof ReplayPortfolioRankingsRequestError
        ? error.message
        : error instanceof Error
          ? error.message
          : 'Unable to load optimal replay rankings'
    optimalState.value = 'error'
  }
}

onBeforeUnmount(() => {
  runsController?.abort()
  strategiesController?.abort()
  replayController?.abort()
  optimalController?.abort()
  scoringDetailController?.abort()
  scoringPredictionsController?.abort()
  backfillStrategyController?.abort()
  strategyInventoryController?.abort()
  backfillCoverageController?.abort()
  backfillPredictionsController?.abort()
})
function nullableText(value: string | null | undefined): string {
  return value ?? '—'
}

function predictedNumbers(value: number[] | null | undefined): string {
  return value?.join(', ') ?? '—'
}
</script>

<template>
  <section class="workspace-page" aria-labelledby="replay-history-title">
    <header class="page-heading">
      <div>
        <p class="eyebrow">Descriptive research only</p>
        <h1 id="replay-history-title">Replay History</h1>
        <p class="page-intro">
          Historical success rates, rankings, and random-baseline differences are descriptive
          research only — not a prediction, recommendation, go-live decision, or winning
          guarantee.
        </p>
      </div>
    </header>

    <nav class="tab-list" aria-label="Replay history sections">
      <button
        class="button"
        type="button"
        :aria-pressed="activeTab === 'overview'"
        @click="activeTab = 'overview'"
      >
        Overview Replay
      </button>
      <button
        class="button"
        type="button"
        :aria-pressed="activeTab === 'optimal'"
        @click="activeTab = 'optimal'"
      >
        Optimal Replay
      </button>
      <button
        class="button"
        type="button"
        :aria-pressed="activeTab === 'backfill'"
        @click="activateBackfill"
      >
        Strategy history replay
      </button>
    </nav>

    <section v-if="activeTab === 'overview'" aria-labelledby="overview-replay-title">
      <h2 id="overview-replay-title">Overview replay</h2>

      <form class="panel filter-panel" @submit.prevent="loadStrategies">
        <div class="filter-grid">
          <label>
            <span>Run</span>
            <select v-model="selectedRunId" name="run_id" :disabled="runsState !== 'ready'">
              <option value="">Select a completed run</option>
              <option v-for="run in runs" :key="run.run_id" :value="run.run_id">
                {{ run.run_id }} · {{ lotteryLabel(run.lottery_type) }} · {{ run.completed_at }}
              </option>
            </select>
          </label>
          <label>
            <span>Ticket count</span>
            <select v-model.number="selectedTicketCount" name="ticket_count">
              <option v-for="count in TICKET_COUNTS" :key="count" :value="count">{{ count }}</option>
            </select>
          </label>
        </div>
        <div class="filter-actions">
          <button class="button button--primary" type="submit" :disabled="!selectedRunId">
            Load strategies
          </button>
        </div>
      </form>

      <p v-if="runsState === 'loading'" class="state-panel">Loading runs…</p>
      <p v-else-if="runsState === 'empty'" class="state-panel">No completed runs are available.</p>
      <p v-else-if="runsState === 'error'" class="state-panel state-panel--error">{{ runsError }}</p>

      <p v-if="strategiesState === 'loading'" class="state-panel">Loading strategies…</p>
      <p v-else-if="strategiesState === 'empty'" class="state-panel">
        No strategies match this run and ticket count.
      </p>
      <p v-else-if="strategiesState === 'error'" class="state-panel state-panel--error">
        {{ strategiesError }}
      </p>

      <div v-if="strategiesState === 'ready'" class="table-wrap">
        <table>
          <caption>All strategies for this run and ticket count</caption>
          <thead>
            <tr>
              <th scope="col">Strategy</th>
              <th scope="col">Governance</th>
              <th scope="col">Evaluated draws</th>
              <th scope="col">Complete portfolios</th>
              <th scope="col">M4+ hit rate</th>
              <th scope="col"></th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="summary in strategies"
              :key="summary.strategy_snapshot_id"
              :data-testid="`strategy-row-${summary.strategy_id}`"
              :aria-current="selectedStrategyId === summary.strategy_id ? 'true' : undefined"
            >
              <td>{{ summary.effective_strategy_id }}</td>
              <td>{{ summary.governance_status }}</td>
              <td>{{ summary.evaluated_draws }}</td>
              <td>{{ summary.complete_portfolios }}</td>
              <td>{{ hitRate(summary) }} ({{ summary.m4plus_hit_count }}/{{ summary.evaluated_draws }})</td>
              <td>
                <button
                  class="button button--quiet"
                  type="button"
                  @click="chooseStrategy(summary.strategy_id)"
                >
                  View replay
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <p v-if="replayState === 'loading'" class="state-panel">Loading replay portfolios…</p>
      <p v-else-if="replayState === 'empty'" class="state-panel">
        No replay portfolios match this selection.
      </p>
      <p v-else-if="replayState === 'error'" class="state-panel state-panel--error">
        {{ replayError }}
      </p>

      <section v-if="replayPage" aria-labelledby="replay-portfolios-title">
        <h3 id="replay-portfolios-title">Replay portfolios — {{ replayPage.strategy_id }}</h3>
        <label class="confirmation">
          <input v-model="m4plusOnly" type="checkbox" name="m4plus_only" @change="chooseStrategy(selectedStrategyId)" />
          <span>M4+ only</span>
        </label>
        <div class="table-wrap">
          <table>
            <caption>Per-draw replay portfolios (descriptive; no prediction or recommendation)</caption>
            <thead>
              <tr>
                <th scope="col">Target draw</th>
                <th scope="col">Cutoff draw</th>
                <th scope="col">M4+</th>
                <th scope="col">Tickets</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="portfolio in replayPage.items" :key="portfolio.portfolio_id">
                <td>{{ portfolio.target_draw.draw_number }} · {{ portfolio.target_draw.draw_date }}</td>
                <td>{{ portfolio.cutoff_draw.draw_number }} · {{ portfolio.cutoff_draw.draw_date }}</td>
                <td>{{ portfolio.m4plus ? 'YES' : 'NO' }}</td>
                <td>
                  <details>
                    <summary>{{ portfolio.tickets.length }} tickets</summary>
                    <ul class="ticket-list">
                      <li v-for="ticket in portfolio.tickets" :key="ticket.ticket_sha256">
                        <span class="number-chips">
                          <LotteryNumberBall
                            v-for="num in ticket.main_numbers"
                            :key="num"
                            :value="num"
                            variant="main"
                            size="sm"
                          />
                          <LotteryNumberBall
                            v-for="snum in ticket.special_numbers"
                            :key="snum"
                            :value="snum"
                            variant="special"
                            size="sm"
                          />
                        </span>
                        — {{ ticket.main_hit_count }} hit(s){{ ticket.special_hit ? ' + special' : '' }}
                      </li>
                    </ul>
                  </details>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="filter-actions">
          <button class="button" type="button" :disabled="replayOffset === 0" @click="previousReplayPage">
            Previous
          </button>
          <button
            class="button"
            type="button"
            :disabled="replayOffset + REPLAY_PAGE_SIZE >= replayPage.total_count"
            @click="nextReplayPage"
          >
            Next
          </button>
          <span>{{ replayPage.total_count }} total</span>
        </div>
      </section>
    </section>

    <section v-else-if="activeTab === 'optimal'" aria-labelledby="optimal-replay-title">
      <h2 id="optimal-replay-title">Optimal replay</h2>
      <p class="page-intro">
        Ranks 1–5-strategy portfolios drawn from one already-validated Replay-scoring artifact.
        "Optimal" means rank 1 under a frozen descriptive policy only — this carries no payout,
        probability, EV, ROI, recommendation, or future-performance claim.
      </p>

      <form class="panel filter-panel" @submit.prevent="loadOptimalRankings">
        <div class="filter-grid">
          <label>
            <span>Scoring artifact SHA-256</span>
            <input
              v-model.trim="scoringArtifactSha256"
              name="scoring_artifact_sha256"
              placeholder="64 hex characters"
              autocomplete="off"
            />
          </label>
          <label>
            <span>Top K</span>
            <input v-model.number="topK" type="number" name="top_k" min="1" max="50" @input="resetOptimalSelection" />
          </label>
        </div>
        <p v-if="shaInputInvalid" class="state-panel state-panel--error">
          Enter an exact lowercase 64-character SHA-256.
        </p>
        <div class="filter-actions">
          <button class="button button--primary" type="submit">Load rankings</button>
        </div>
      </form>

      <p v-if="optimalState === 'loading'" class="state-panel">Loading rankings…</p>
      <p v-else-if="optimalState === 'empty'" class="state-panel">No candidates were found.</p>
      <p v-else-if="optimalState === 'error'" class="state-panel state-panel--error">
        {{ optimalError }}
      </p>

      <template v-if="optimalResult && optimalState === 'ready'">
        <p class="table-note" data-testid="optimal-ranking-success">
          API query: SUCCESS_WITH_DATA · rankings and positions below are returned by the API.
        </p>
        <p class="panel__note">
          OFFICIAL_ANY_PRIZE means at least one ticket receives an official prize. Prize tiers and
          rank order come from the API; this page does not recalculate them.
        </p>
        <dl class="source-facts">
          <div>
            <dt>Source scoring artifact</dt>
            <dd><code>{{ optimalResult.source_scoring_artifact_payload_sha256 }}</code></dd>
          </div>
          <div>
            <dt>Source replay artifact</dt>
            <dd><code>{{ optimalResult.source_replay_artifact_payload_sha256 }}</code></dd>
          </div>
          <div>
            <dt>Ranking artifact SHA-256</dt>
            <dd><code>{{ optimalResult.artifact_sha256 }}</code></dd>
          </div>
          <div><dt>Lottery</dt><dd>{{ lotteryLabel(optimalResult.lottery_type) }}</dd></div>
          <div><dt>Dataset</dt><dd>{{ optimalResult.dataset_id }} · {{ optimalResult.dataset_version }}</dd></div>
          <div><dt>Ranking policy</dt><dd>{{ optimalResult.ranking_policy_id }}</dd></div>
          <div><dt>Strategy count</dt><dd>{{ optimalResult.strategy_count }}</dd></div>
        </dl>
        <div class="filter-actions">
          <button class="button button--primary" type="button" @click="loadScoringArtifactDetail">
            Scoring Artifact Detail
          </button>
        </div>

        <section v-if="scoringDetailVisible" aria-labelledby="scoring-artifact-detail-title">
          <h3 id="scoring-artifact-detail-title">Scoring Artifact Detail</h3>
          <p v-if="scoringDetailState === 'loading'" class="state-panel">
            Loading scoring artifact, predictions, and aggregates…
          </p>
          <div v-else-if="scoringDetailState === 'error'" class="state-panel state-panel--error" role="alert">
            <p>{{ scoringDetailError }}</p>
            <button class="button button--quiet" type="button" @click="loadScoringArtifactDetail">
              Retry scoring detail
            </button>
          </div>

          <template v-else-if="scoringDetailState === 'ready' && scoringDetailRun && scoringOverallAggregate">
            <p class="table-note" data-testid="scoring-detail-query-success">
              API query: SUCCESS_WITH_DATA · scoring artifact, aggregates, and prediction rows are read-only API results.
            </p>
            <dl class="source-facts">
              <div>
                <dt>Scoring artifact SHA-256</dt>
                <dd><code>{{ scoringDetailRun.scoring_artifact_payload_sha256 }}</code></dd>
              </div>
              <div>
                <dt>Dataset</dt>
                <dd>{{ scoringDetailRun.dataset_id }} · {{ scoringDetailRun.dataset_version }}</dd>
              </div>
              <div><dt>Lottery</dt><dd>{{ lotteryLabel(scoringDetailRun.lottery_type) }}</dd></div>
              <div><dt>Target count</dt><dd>{{ scoringDetailRun.target_count }}</dd></div>
              <div><dt>Strategy count</dt><dd>{{ scoringDetailRun.strategy_count }}</dd></div>
              <div><dt>Scored record count</dt><dd>{{ scoringDetailRun.scored_record_count }}</dd></div>
              <div>
                <dt>Source replay artifact</dt>
                <dd><code>{{ scoringDetailRun.source_replay_artifact_payload_sha256 }}</code></dd>
              </div>
            </dl>

            <section aria-labelledby="strategy-scoring-aggregates-title">
              <h4 id="strategy-scoring-aggregates-title">Strategy aggregates</h4>
              <div v-if="scoringStrategyAggregates.length" class="table-wrap">
                <table>
                  <caption>Raw per-strategy source, status, and prize counts</caption>
                  <thead>
                    <tr>
                      <th scope="col">Strategy</th>
                      <th scope="col">Version</th>
                      <th v-for="field in aggregateCountFields" :key="field.key" scope="col">
                        {{ field.label }}
                      </th>
                      <th v-for="field in prizeCountFields" :key="field.key" scope="col">
                        {{ field.label }}
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="aggregate in scoringStrategyAggregates" :key="aggregate.aggregate_sha256">
                      <th scope="row">{{ aggregate.strategy_id }}</th>
                      <td>{{ nullableText(aggregate.strategy_version) }}</td>
                      <td v-for="field in aggregateCountFields" :key="field.key">
                        {{ aggregate[field.key] }}
                      </td>
                      <td v-for="field in prizeCountFields" :key="field.key">
                        {{ aggregate[field.key] }}
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <p v-else class="state-panel">
                Strategy aggregates API: SUCCESS_EMPTY · No strategy aggregate rows are available.
              </p>
            </section>

            <section aria-labelledby="overall-scoring-aggregate-title">
              <h4 id="overall-scoring-aggregate-title">Overall aggregate</h4>
              <dl class="source-facts">
                <div v-for="field in aggregateCountFields" :key="field.key">
                  <dt>{{ field.label }}</dt>
                  <dd>{{ scoringOverallAggregate[field.key] }}</dd>
                </div>
                <div v-for="field in prizeCountFields" :key="field.key">
                  <dt>{{ field.label }}</dt>
                  <dd>{{ scoringOverallAggregate[field.key] }}</dd>
                </div>
              </dl>
            </section>

            <section aria-labelledby="scored-predictions-title">
              <h4 id="scored-predictions-title">Scored predictions</h4>
              <form class="panel filter-panel" @submit.prevent="loadFilteredScoringPredictions">
                <div class="filter-grid">
                  <label>
                    <span>Target draw</span>
                    <input v-model.trim="predictionFilters.targetDraw" name="target_draw" />
                  </label>
                  <label>
                    <span>Strategy ID</span>
                    <input v-model.trim="predictionFilters.strategyId" name="strategy_id" />
                  </label>
                  <label>
                    <span>Status</span>
                    <input v-model.trim="predictionFilters.status" name="status" />
                  </label>
                  <label>
                    <span>Prize tier</span>
                    <input v-model.trim="predictionFilters.tier" name="tier" />
                  </label>
                </div>
                <div class="filter-actions">
                  <button class="button button--primary" type="submit">
                    Apply prediction filters
                  </button>
                </div>
              </form>

              <p v-if="scoringPredictionsState === 'loading'" class="state-panel">
                Loading predictions…
              </p>
              <div v-else-if="scoringPredictionsState === 'error'" class="state-panel state-panel--error" role="alert">
                <p>{{ scoringPredictionsError }}</p>
                <button class="button button--quiet" type="button" @click="loadFilteredScoringPredictions">
                  Retry predictions
                </button>
              </div>
              <p v-else-if="scoringPredictionsState === 'empty'" class="state-panel">
                Predictions API: SUCCESS_EMPTY · No predictions match these filters.
              </p>
              <p v-else-if="scoringPredictionsState === 'ready'" class="table-note">
                Predictions API: SUCCESS_WITH_DATA · {{ scoringPredictions.length }} rows returned.
              </p>
              <div v-if="scoringPredictionsState === 'ready'" class="table-wrap">
                <table>
                  <caption>Prediction status fields and scoring results are shown independently</caption>
                  <thead>
                    <tr>
                      <th scope="col">Target draw</th>
                      <th scope="col">Strategy</th>
                      <th scope="col">History status / reason</th>
                      <th scope="col">Prediction status / reason</th>
                      <th scope="col">Scoring status / reason</th>
                      <th scope="col">Predicted numbers</th>
                      <th scope="col">Main hits</th>
                      <th scope="col">Special hit</th>
                      <th scope="col">Prize tier</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr
                      v-for="prediction in scoringPredictions"
                      :key="`${prediction.run_payload_sha256}-${prediction.ordinal}`"
                    >
                      <td>{{ prediction.target_draw_number }} · {{ prediction.target_draw_date }}</td>
                      <td>{{ prediction.strategy_id }}</td>
                      <td>
                        {{ prediction.source_history_status }} / {{ nullableText(prediction.source_history_reason_code) }}
                      </td>
                      <td>
                        {{ nullableText(prediction.source_prediction_status) }} /
                        {{ nullableText(prediction.source_prediction_reason_code) }}
                      </td>
                      <td>{{ prediction.scoring_status }} / {{ nullableText(prediction.scoring_reason_code) }}</td>
                      <td>{{ predictedNumbers(prediction.predicted_main_numbers) }}</td>
                      <td>{{ prediction.main_number_hit_count ?? '—' }}</td>
                      <td>
                        {{ prediction.special_number_hit === null || prediction.special_number_hit === undefined
                          ? '—'
                          : prediction.special_number_hit ? 'Yes' : 'No' }}
                      </td>
                      <td>
                        {{ nullableText(prediction.prize_tier_id) }}
                        <span v-if="prediction.prize_official_label">· {{ prediction.prize_official_label }}</span>
                        <span v-if="prediction.no_prize_result">· {{ prediction.no_prize_result }}</span>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </section>
          </template>
        </section>

        <section v-for="group in optimalResult.groups" :key="group.ticket_count">
          <h3>{{ group.ticket_count }}-ticket portfolios — {{ group.status }}</h3>
          <div v-if="group.candidates.length" class="table-wrap">
            <table>
              <caption>Rank-ordered {{ group.ticket_count }}-ticket portfolio candidates</caption>
              <thead>
                <tr>
                  <th scope="col">Rank</th>
                  <th scope="col">Strategies</th>
                  <th scope="col">Winning tickets</th>
                  <th scope="col">No-prize tickets</th>
                  <th scope="col">Scored</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="candidate in group.candidates" :key="candidate.candidate_sha256">
                  <td>{{ candidate.rank }}</td>
                  <td>{{ candidate.members.map((member) => member.strategy_id).join(', ') }}</td>
                  <td>{{ candidate.winning_ticket_count }} / {{ candidate.total_ticket_count }}</td>
                  <td>{{ candidate.no_prize_count }}</td>
                  <td>{{ candidate.scored_count }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p v-else class="state-panel">No candidates in this group.</p>
        </section>
      </template>
    </section>

    <section v-else aria-labelledby="strategy-backfill-title" data-testid="strategy-backfill">
      <h2 id="strategy-backfill-title">Strategy history replay</h2>
      <p class="page-intro">
        Read-only, per-draw historical results returned by the Replay Backfill API. This view does
        not run strategies, rebuild data, or retrain models.
      </p>

      <section class="panel replay-backfill-section" aria-labelledby="backfill-query-title">
        <h3 id="backfill-query-title">1. Query conditions</h3>
        <form class="filter-panel" @submit.prevent="queryBackfillPredictions">
          <div class="filter-grid replay-backfill-filters">
            <label>
              <span>Lottery</span>
              <select
                v-model="backfillLotteryType"
                name="lottery_type"
              >
                <option v-for="lotteryType in REPLAY_BACKFILL_LOTTERY_TYPES" :key="lotteryType" :value="lotteryType">
                  {{ lotteryLabel(lotteryType) }}
                </option>
              </select>
            </label>
            <label>
              <span>Search strategy ID or name</span>
              <input
                v-model="backfillStrategySearch"
                name="strategy_search"
                autocomplete="off"
                placeholder="Search the API strategy list"
              />
            </label>
            <label>
              <span>Strategy ID (all versions)</span>
              <select v-model="backfillStrategyId" name="strategy_id">
                <option value="">All strategies</option>
                <option
                  v-for="option in backfillStrategyQueryOptions"
                  :key="option.strategy_id"
                  :value="option.strategy_id"
                >
                  {{ option.label }}
                </option>
              </select>
            </label>
            <label>
              <span>From date</span>
              <input v-model="backfillFromDate" type="date" name="from_date" />
            </label>
            <label>
              <span>To date</span>
              <input v-model="backfillToDate" type="date" name="to_date" />
            </label>
            <label>
              <span>Replay periods</span>
              <select v-model="backfillPeriod" name="period">
                <option v-for="period in REPLAY_BACKFILL_PERIODS" :key="period" :value="period">
                  {{ period }}
                </option>
              </select>
            </label>
          </div>
          <p v-if="backfillDateError" class="state-panel state-panel--error" role="alert">
            {{ backfillDateError }}
          </p>
          <div class="filter-actions">
            <button
              class="button"
              type="button"
              :disabled="strategyCatalogState === 'loading' || strategyInventoryState === 'loading'"
              @click="searchBackfillStrategies"
            >
              Search strategies
            </button>
            <button class="button button--primary" type="submit" :disabled="backfillPredictionsState === 'loading'">
              Query history
            </button>
          </div>
        </form>

        <p v-if="strategyInventoryState === 'error' && strategyCatalog.length" class="state-panel" data-testid="backfill-inventory-fallback">
          正式策略 inventory 暫時無法取得；目前保留顯示 Replay 策略 API 已回傳的身份。
          {{ strategyInventoryError }}
        </p>
        <p v-if="strategyCatalogState === 'error' && strategyInventory.length" class="state-panel" data-testid="backfill-strategy-metadata-error">
          策略補充資料暫時無法取得；正式 inventory 身份仍保留顯示。
          {{ strategyCatalogError }}
        </p>
        <p v-if="strategyIdentityState === 'loading'" class="state-panel" data-testid="backfill-strategies-loading">
          Loading strategies…
        </p>
        <p v-else-if="strategyIdentityState === 'empty'" class="state-panel" data-testid="backfill-strategies-empty">
          策略 inventory 與 Replay 策略 API 均未回傳策略身份。
        </p>
        <div v-else-if="strategyIdentityState === 'error'" class="state-panel state-panel--error" role="alert" data-testid="backfill-strategies-error">
          {{ strategyIdentityError }}
        </div>
        <p v-else-if="strategyIdentityState === 'ready' && !filteredStrategyRows.length" class="state-panel" data-testid="backfill-strategies-no-match">
          No strategies match this search. The loaded strategy identities remain unchanged.
        </p>
        <div v-else-if="strategyIdentityState === 'ready'" class="table-wrap">
          <p
            v-if="strategyCatalogState === 'error' && strategyCatalogError"
            class="state-panel state-panel--error"
            role="alert"
            data-testid="backfill-strategies-pagination-error"
          >
            策略清單分頁或補充資料載入失敗：{{ strategyCatalogError }}
          </p>
          <table>
            <caption>Strategy identities ({{ visibleStrategyRows.length }} shown / {{ filteredStrategyRows.length }} matching)</caption>
            <thead>
              <tr>
                <th scope="col">Name / ID / version</th>
                <th scope="col">Lottery</th>
                <th scope="col">Lifecycle</th>
                <th scope="col">Data status</th>
                <th scope="col">Available periods</th>
                <th scope="col">Historical data / executions</th>
                <th scope="col">Execution capability</th>
                <th scope="col">Wrapper callable</th>
                <th scope="col">Native Backfill</th>
                <th scope="col">Training status</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="strategy in visibleStrategyRows" :key="strategyIdentityKey(strategy)">
                <td>
                  <strong>{{ strategy.display_name }}</strong><br />
                  <code>{{ strategy.strategy_id }}</code><br />
                  <span>{{ strategy.strategy_version ?? '版本未提供' }}</span>
                  <p class="replay-backfill-reason">
                    {{ strategy.from_inventory ? '身份來源：正式 inventory' : '身份來源：Replay 策略 API' }}
                  </p>
                </td>
                <td>{{ lotteryLabel(strategy.lottery_type) }}</td>
                <td>{{ lifecycleLabel(strategy.lifecycle_status) }}</td>
                <td>
                  <strong>{{ dataStatusLabel(strategy.data_status) }}</strong>
                  <p class="replay-backfill-reason">{{ dataStatusReason(strategy.data_status) }}</p>
                </td>
                <td>{{ strategy.available_target_count === null ? 'API未提供' : strategy.available_target_count }}</td>
                <td>
                  {{ strategy.historical_data_count === null ? 'API未提供' : strategy.historical_data_count }} /
                  {{ strategy.historical_execution_count === null ? 'API未提供' : strategy.historical_execution_count }}
                </td>
                <td>{{ executionCapabilityLabel(strategy.execution_capability) }}</td>
                <td>{{ wrapperCallableLabel(strategy.wrapper_callable) }}</td>
                <td>
                  {{ nativeBackfillLabel(strategy.backfill_native_binding, strategy.backfill_runnable) }}
                  <p v-if="strategy.execution_block_reason" class="replay-backfill-reason">
                    {{ strategy.execution_block_reason }}
                  </p>
                </td>
                <td>{{ trainingStatusLabel(strategy.training_status) }}</td>
              </tr>
            </tbody>
          </table>
          <div v-if="hasMoreStrategyRows" class="filter-actions">
            <button
              class="button"
              type="button"
              :disabled="strategyCatalogState === 'loading'"
              @click="loadMoreBackfillStrategies"
            >
              Load more strategies
            </button>
          </div>
        </div>
        <p
          v-if="strategyIdentityState === 'error' && backfillPredictionsState === 'error' && backfillPredictionHasQueried"
          class="state-panel state-panel--error"
          data-testid="backfill-data-unavailable"
        >
          資料取得失敗：策略清冊與預測服務均無法取得，無法判定策略身份或預測結果。
        </p>
      </section>

      <section class="panel replay-backfill-section" aria-labelledby="backfill-coverage-title">
        <h3 id="backfill-coverage-title">2. Coverage and data status</h3>
        <p v-if="coverageState === 'loading'" class="state-panel" data-testid="backfill-coverage-loading">
          Loading replay coverage…
        </p>
        <div v-else-if="coverageState === 'error'" class="state-panel state-panel--error" role="alert" data-testid="backfill-coverage-error">
          {{ coverageError }}
        </div>
        <template v-else-if="coverageState === 'ready' && coverage">
          <div v-if="coverage.completed_cell_count === 0 && backfillPredictions.length === 0 && backfillPredictionsState !== 'error'" class="state-panel" data-testid="backfill-no-formal-data">
            尚無可查詢的正式Replay資料。
          </div>
          <p v-if="isPartialCoverage" class="state-panel" data-testid="backfill-partial-coverage">
            Partial coverage: some expected cells are missing, failed, or closed. Counts below come
            from the coverage API.
          </p>
          <dl class="source-facts replay-backfill-coverage-facts">
            <div>
              <dt title="Expected strategy count minus the strategy IDs returned by the coverage API as missing">Completed strategies</dt>
              <dd>{{ Math.max(0, coverage.expected_strategy_count - coverage.missing_strategy_ids.length) }} / {{ coverage.expected_strategy_count }}</dd>
            </div>
            <div><dt>Completed replay cells (strategy × draw)</dt><dd>{{ coverage.completed_cell_count }} / {{ coverage.expected_cell_count }}</dd></div>
            <div><dt>Expected draw periods</dt><dd>{{ coverage.expected_target_count }}</dd></div>
            <div><dt>Missing cells</dt><dd>{{ Math.max(0, coverage.expected_cell_count - coverage.completed_cell_count - coverage.failed_cell_count - coverage.closed_cell_count) }}</dd></div>
            <div><dt>Failed cells</dt><dd>{{ coverage.failed_cell_count }}</dd></div>
            <div><dt>Closed cells</dt><dd>{{ coverage.closed_cell_count }}</dd></div>
            <div><dt>Complete coverage</dt><dd>{{ coverage.complete_coverage_percent.toFixed(1) }}%</dd></div>
            <div><dt>Coverage run</dt><dd><code>{{ coverage.run_id ?? '尚無回放' }}</code></dd></div>
          </dl>
          <p v-if="coverage.missing_strategy_ids.length" class="replay-backfill-reason">
            Missing strategy IDs: {{ coverage.missing_strategy_ids.join(', ') }}
          </p>
        </template>
        <p class="state-panel" data-testid="backfill-query-status">
          Last query status:
          <strong>{{ backfillPredictionsState === 'idle' ? (backfillPredictionHasQueried ? 'idle' : 'not queried') : backfillPredictionsState }}</strong>
          <span v-if="backfillPredictionRunId"> · run {{ backfillPredictionRunId }}</span>
        </p>
      </section>

      <section class="panel replay-backfill-section" aria-labelledby="backfill-results-title">
        <h3 id="backfill-results-title">3. Historical prediction list</h3>
        <p v-if="backfillPredictionsState === 'loading'" class="state-panel" data-testid="backfill-predictions-loading">
          Loading replay results…
        </p>
        <div v-else-if="backfillPredictionsState === 'error'" class="state-panel state-panel--error" role="alert" data-testid="backfill-predictions-error">
          {{ backfillPredictionsError }}
        </div>
        <p v-else-if="backfillPredictionsState === 'empty'" class="state-panel" data-testid="backfill-predictions-empty">
          {{ coverage?.completed_cell_count === 0 ? '尚無可查詢的正式Replay資料。' : 'No replay records match the selected filters.' }}
        </p>
        <div v-if="backfillPredictions.length" class="table-wrap">
          <table>
            <caption>Per-draw replay predictions — {{ backfillPredictionTotal }} total</caption>
            <thead>
              <tr>
                <th scope="col">Lottery</th>
                <th scope="col">Draw</th>
                <th scope="col">Date</th>
                <th scope="col">Strategy</th>
                <th scope="col">Original predictions</th>
                <th scope="col">Official main numbers</th>
                <th scope="col">{{ actualSpecialLabel(backfillLotteryType) }}</th>
                <th scope="col">Ticket hits</th>
                <th scope="col">Portfolio any prize</th>
                <th scope="col">Strategy data status</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in backfillPredictions" :key="predictionIdentityKey(item)" :data-testid="`backfill-row-${item.target_draw_number}-${item.strategy_id}`">
                <td>{{ lotteryLabel(item.lottery_type) }}</td>
                <td>{{ item.target_draw_number }}</td>
                <td>{{ item.target_draw_date }}</td>
                <td>
                  <strong>{{ strategyDisplayName(item) }}</strong><br />
                  <code>{{ item.strategy_id }}</code><br />
                  <span>{{ item.strategy_version }}</span><br />
                  <span>生命週期：{{ item.lifecycle_status ?? 'API未提供' }}</span>
                </td>
                <td>
                  <ul v-if="item.predicted_tickets.length" class="replay-backfill-ticket-list">
                    <li v-for="ticket in item.predicted_tickets" :key="ticket.ticket_position">
                      #{{ ticket.ticket_position }} · {{ showNumbers(ticket.main_numbers) }}<template v-if="ticket.special_numbers.length"> + {{ showNumbers(ticket.special_numbers) }}</template>
                    </li>
                  </ul>
                  <span v-else>API returned no ticket rows</span>
                </td>
                <td>{{ showNumbers(item.actual_main_numbers) }}</td>
                <td>{{ item.actual_special_numbers.length ? showNumbers(item.actual_special_numbers) : '不適用' }}</td>
                <td>
                  <div>
                    Best main hits: {{ bestMainHitsLabel(item) }}
                    <span class="replay-score-trust-status" :data-testid="`score-trust-${item.target_draw_number}-${item.strategy_id}`">
                      {{ scoreTrustLabel(item) }}
                    </span>
                  </div>
                  <details v-if="item.predicted_tickets.length">
                    <summary>Per-ticket detail ({{ item.predicted_tickets.length }})</summary>
                    <table>
                      <thead><tr><th>Position</th><th>Main numbers</th><th>Special / second zone</th><th>Main hits</th><th>Special hit</th><th>Prize tier</th></tr></thead>
                      <tbody>
                        <tr v-for="(ticket, ticketIndex) in item.predicted_tickets" :key="`detail-${ticket.ticket_position}`">
                          <td>{{ ticket.ticket_position }}</td>
                          <td>{{ showNumbers(ticket.main_numbers) }}</td>
                          <td>{{ ticket.special_numbers.length ? showNumbers(ticket.special_numbers) : '不適用' }}</td>
                          <td>{{ ticketMainHitsLabel(item, ticketIndex) }}</td>
                          <td>{{ specialHitLabel(item, ticket.special_hit) }}</td>
                          <td>{{ prizeTierLabel(item, ticket.prize_tier) }}</td>
                        </tr>
                      </tbody>
                    </table>
                  </details>
                  <details>
                    <summary>Training and provenance</summary>
                    <p>{{ trainingStatusLabel(item.training.training_status) }}</p>
                    <dl>
                      <div><dt>Model version</dt><dd>{{ item.training.model_version ?? 'API未提供' }}</dd></div>
                      <div><dt>Training cutoff</dt><dd>{{ item.training.training_cutoff ?? 'API未提供' }}</dd></div>
                      <div><dt>Training artifact</dt><dd><code>{{ item.training.training_artifact_id ?? 'API未提供' }}</code></dd></div>
                      <div><dt>Prediction status</dt><dd>{{ item.prediction_status }}</dd></div>
                      <div><dt>Prediction cutoff</dt><dd>{{ predictionCutoffLabel(item) }}</dd></div>
                      <div><dt>Cutoff draw</dt><dd>{{ item.prediction_cutoff?.draw_number ?? 'API未提供' }} / {{ item.prediction_cutoff?.draw_date ?? 'API未提供' }}</dd></div>
                      <div><dt>Cutoff history count</dt><dd>{{ item.prediction_cutoff?.history_draw_count ?? 'API未提供' }}</dd></div>
                      <div><dt>Cutoff source identity</dt><dd>{{ item.prediction_cutoff?.source_identity ?? 'API未提供' }}</dd></div>
                      <div><dt>Source kind</dt><dd>{{ item.source_kind }}</dd></div>
                    </dl>
                  </details>
                </td>
                <td>{{ portfolioAnyPrizeLabel(item.portfolio_any_prize, item) }}</td>
                <td>
                  <strong>{{ dataStatusLabel(item.data_status) }}</strong>
                  <p class="replay-backfill-reason">{{ dataStatusReason(item.data_status) }}</p>
                </td>
              </tr>
            </tbody>
          </table>
          <div class="filter-actions">
            <span>Showing {{ backfillPredictions.length }} / {{ backfillPredictionTotal }}</span>
            <button
              v-if="backfillPredictionCursor"
              class="button"
              type="button"
              :disabled="backfillPredictionsState === 'loading'"
              @click="loadMoreBackfillPredictions"
            >
              Load more
            </button>
          </div>
        </div>
      </section>
    </section>
  </section>
</template>

<style scoped>
.replay-backfill-section {
  margin-top: 22px;
  padding: 18px;
}

.replay-backfill-section h3 {
  margin-top: 0;
}

.replay-backfill-filters {
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
}

.replay-backfill-reason {
  margin: 5px 0 0;
  color: var(--muted);
  font-size: 0.9em;
}

.replay-backfill-ticket-list {
  margin: 0;
  padding-left: 18px;
  min-width: 150px;
}

.replay-backfill-coverage-facts {
  grid-template-columns: repeat(auto-fit, minmax(145px, 1fr));
}

.replay-backfill-section details {
  margin-top: 8px;
}

.replay-backfill-section details table {
  margin-top: 8px;
}
</style>
