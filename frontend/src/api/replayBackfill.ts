import type { components } from './generated/openapi'

export const REPLAY_BACKFILL_LOTTERY_TYPES = [
  'BIG_LOTTO',
  'DAILY_539',
  'POWER_LOTTO',
] as const

export type ReplayBackfillLotteryType = components['schemas']['LotteryType']
export type ReplayBackfillPeriod = 50 | 300 | 750 | 'ALL'

export const REPLAY_BACKFILL_PERIODS: readonly ReplayBackfillPeriod[] = [50, 300, 750, 'ALL']

export type ReplayBackfillDataStatus = components['schemas']['ReplayDataStatus']

export type ReplayBackfillStrategyItem = components['schemas']['ReplayBackfillStrategyItemView']
export type ReplayBackfillStrategyPage = components['schemas']['ReplayBackfillStrategyPageResponse']

type InventoryItemView = components['schemas']['ReplayStrategyInventoryItemView']
type CapabilityKey = 'reconstructable' | 'wrapper_callable' | 'backfill_native_binding' |
  'backfill_runnable' | 'execution_block_reason'
type InventoryWireItem = Omit<InventoryItemView, CapabilityKey> & Partial<Pick<InventoryItemView, CapabilityKey>>
type InventoryWireResponse = Omit<components['schemas']['ReplayStrategyInventoryResponse'], 'strategies'> & {
  strategies: InventoryWireItem[]
}
export type ReplayStrategyInventoryItem = Omit<InventoryItemView, 'backfill_runnable'> & {
  backfill_runnable: boolean | null
}
export type ReplayStrategyInventoryResponse = Omit<InventoryWireResponse, 'strategies'> & {
  strategies: ReplayStrategyInventoryItem[]
}

export type ReplayBackfillTicket = components['schemas']['ReplayBackfillPredictedTicketView']
export type ReplayBackfillTraining = components['schemas']['ReplayBackfillTrainingView']
export type ReplayBackfillPredictionCutoffStatus = 'VERIFIED' | 'UNTRUSTED' | 'UNKNOWN'
export type ReplayBackfillPredictionCutoff = components['schemas']['ReplayBackfillPredictionCutoffView']
export type ReplayBackfillResearchPortfolioQualification =
  components['schemas']['ReplayBackfillResearchPortfolioQualificationView']
export type UniformEightReference = components['schemas']['ReplayUniformEightReferenceView']
export type UniformEightSummary = components['schemas']['ReplayUniformEightSummaryView']
export type MainThreeReference = components['schemas']['ReplayMainThreeReferenceView']
export type MainThreeSummary = components['schemas']['ReplayMainThreeSummaryView']
export const HEDGE_K3_STRATEGY_ID = 'research_biglotto__k3_hedge_official_reference_20261117'
export type ReplayBackfillPredictionItem = components['schemas']['ReplayBackfillPredictionItemView']
export type ReplayBackfillPredictionPage = components['schemas']['ReplayBackfillPredictionPageResponse']

export type ReplayBackfillStrategyRunItem =
  components['schemas']['ReplayBackfillStrategyRunItemResponse']
export type ReplayBackfillStrategyRunsPage =
  components['schemas']['ReplayBackfillStrategyRunsPageResponse']

export type ReplayBackfillCoverage = components['schemas']['ReplayBackfillCoverageResponse']

export type K3ComparisonStrategy = 'optimizer' | 'ecp'
export interface K3ComparisonRow {
  target_draw_number: string
  target_draw_date: string
  match_status: string
  source_segment: string | null
  original_source_run_id: string | null
  old_cell_identity: string | null
  old: ReplayBackfillPredictionItem | null
  new: ReplayBackfillPredictionItem
}
export interface K3Comparison {
  run_id: string
  strategy: K3ComparisonStrategy
  target_count: number
  paired_count: number
  unmatched_count: number
  old_wins: number
  new_wins: number
  old_only: number
  new_only: number
  fair_delta: number | null
  observed_minus_fair: number | null
  rows: K3ComparisonRow[]
}

export interface ReplayBackfillStrategyQuery {
  lotteryType: ReplayBackfillLotteryType
  runId?: string
  q?: string
  lifecycleStatus?: string
  dataStatus?: string
  limit?: number
  cursor?: string | null
}

export interface ReplayBackfillPredictionQuery {
  lotteryType: ReplayBackfillLotteryType
  runId?: string
  strategyId?: string
  strategyVersion?: string
  fromDate?: string
  toDate?: string
  period: ReplayBackfillPeriod
  limit?: number
  cursor?: string | null
}

export interface ReplayStrategyRunsQuery {
  lotteryType: ReplayBackfillLotteryType
  strategyId: string
  strategyVersion?: string
  limit?: number
  offset?: number
}

export class ReplayBackfillRequestError extends Error {
  readonly status: number
  readonly errorCode: string | undefined

  constructor(message: string, status: number, errorCode?: string) {
    super(message)
    this.name = 'ReplayBackfillRequestError'
    this.status = status
    this.errorCode = errorCode
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function hasExactKeys(value: Record<string, unknown>, expected: readonly string[]): boolean {
  const actual = Object.keys(value)
  return actual.length === expected.length && expected.every((key) => Object.hasOwn(value, key))
}

function isString(value: unknown): value is string {
  return typeof value === 'string'
}

function isNullableString(value: unknown): value is string | null {
  return value === null || isString(value)
}

function isNullableBoolean(value: unknown): value is boolean | null {
  return value === null || typeof value === 'boolean'
}

function isSafeInteger(value: unknown): value is number {
  return typeof value === 'number' && Number.isSafeInteger(value)
}

function isNullableSafeInteger(value: unknown): value is number | null {
  return value === null || isSafeInteger(value)
}

function isNonNegativeSafeInteger(value: unknown): value is number {
  return isSafeInteger(value) && value >= 0
}

function isNullableNonNegativeSafeInteger(value: unknown): value is number | null {
  return value === null || isNonNegativeSafeInteger(value)
}

function isNumberArray(value: unknown): value is number[] {
  return Array.isArray(value) && value.every(isSafeInteger)
}

function isLotteryType(value: unknown): value is ReplayBackfillLotteryType {
  return REPLAY_BACKFILL_LOTTERY_TYPES.includes(value as ReplayBackfillLotteryType)
}

function isStrategyItem(value: unknown): value is ReplayBackfillStrategyItem {
  return (
    isRecord(value) &&
    isString(value.strategy_id) &&
    isNullableString(value.strategy_version) &&
    isString(value.display_name) &&
    isLotteryType(value.lottery_type) &&
    isString(value.lifecycle_status) &&
    isString(value.data_status) &&
    isString(value.source_kind) &&
    typeof value.executable === 'boolean' &&
    isNonNegativeSafeInteger(value.available_target_count) &&
    isString(value.training_status)
  )
}

function isStrategyPage(value: unknown): value is ReplayBackfillStrategyPage {
  return (
    isRecord(value) &&
    Array.isArray(value.items) &&
    value.items.every(isStrategyItem) &&
    isNonNegativeSafeInteger(value.total_count) &&
    (value.next_cursor === null || isString(value.next_cursor))
  )
}

function isStrategyInventoryItem(value: unknown): value is InventoryWireItem {
  return (
    isRecord(value) &&
    isLotteryType(value.lottery_type) &&
    isString(value.strategy_id) &&
    isString(value.display_name) &&
    isNullableString(value.strategy_version) &&
    isString(value.source_kind) &&
    isString(value.source_locator) &&
    isString(value.lifecycle_status) &&
    isString(value.replay_data_status) &&
    isString(value.execution_capability) &&
    (value.reconstructable === undefined || isNullableBoolean(value.reconstructable)) &&
    (value.wrapper_callable === undefined || isNullableBoolean(value.wrapper_callable)) &&
    (value.backfill_native_binding === undefined || isNullableBoolean(value.backfill_native_binding)) &&
    (value.backfill_runnable === undefined || typeof value.backfill_runnable === 'boolean') &&
    (value.execution_block_reason === undefined || isNullableString(value.execution_block_reason)) &&
    isString(value.reconstruction_reason) &&
    isNonNegativeSafeInteger(value.historical_data_count) &&
    isNonNegativeSafeInteger(value.historical_execution_count)
  )
}

function isPredictionCutoff(value: unknown): value is ReplayBackfillPredictionCutoff {
  return (
    isRecord(value) &&
    isNullableString(value.draw_date) &&
    isNullableString(value.draw_number) &&
    isNullableNonNegativeSafeInteger(value.history_draw_count) &&
    isNullableString(value.reason_code) &&
    isNullableString(value.source_hash) &&
    isNullableString(value.source_identity) &&
    isNullableString(value.source_locator) &&
    ['VERIFIED', 'UNTRUSTED', 'UNKNOWN'].includes(String(value.status))
  )
}

function isStrategyInventoryResponse(value: unknown): value is InventoryWireResponse {
  return (
    isRecord(value) &&
    isNonNegativeSafeInteger(value.strategy_count) &&
    Array.isArray(value.strategies) &&
    value.strategies.every(isStrategyInventoryItem) &&
    value.strategy_count === value.strategies.length
  )
}

function isTicket(value: unknown): value is ReplayBackfillTicket {
  return (
    isRecord(value) &&
    isNullableSafeInteger(value.ticket_position) &&
    (value.main_numbers === null || isNumberArray(value.main_numbers)) &&
    isNumberArray(value.special_numbers) &&
    isNullableNonNegativeSafeInteger(value.main_hit_count) &&
    (value.special_hit === null || typeof value.special_hit === 'boolean') &&
    isNullableString(value.prize_tier)
  )
}

function isResearchPortfolioQualification(
  value: unknown,
): value is ReplayBackfillResearchPortfolioQualification {
  if (!isRecord(value)) return false
  const status = value.status
  return (
    (status === 'PASS' || status === 'FAIL' || status === 'UNKNOWN') &&
    (status === 'FAIL'
      ? value.import_qualification === 'NOT_QUALIFIED'
      : value.import_qualification === 'UNKNOWN') &&
    isNullableString(value.reason_code) &&
    Array.isArray(value.duplicate_groups) &&
    value.duplicate_groups.every(
      (group: unknown) =>
        isRecord(group) &&
        isNumberArray(group.main_numbers) &&
        isNumberArray(group.positions),
    )
  )
}

function isTraining(value: unknown): value is ReplayBackfillTraining {
  return (
    isRecord(value) &&
    isString(value.training_status) &&
    isNullableString(value.model_version) &&
    isNullableString(value.training_cutoff) &&
    isNullableString(value.training_artifact_id)
  )
}

function isPredictionItem(value: unknown): value is ReplayBackfillPredictionItem {
  return (
    isRecord(value) &&
    isLotteryType(value.lottery_type) &&
    isString(value.strategy_id) &&
    isString(value.strategy_version) &&
    (value.source_history_provenance_status === undefined ||
      ['VERIFIED', 'UNKNOWN', 'UNVERIFIED'].includes(String(value.source_history_provenance_status))) &&
    (value.dataset_identity === undefined || isNullableString(value.dataset_identity)) &&
    (value.execution_version === undefined || isNullableString(value.execution_version)) &&
    (value.lifecycle_status === undefined || isString(value.lifecycle_status)) &&
    isString(value.target_draw_number) &&
    isString(value.target_draw_date) &&
    isString(value.prediction_status) &&
    (value.research_portfolio_qualification === undefined ||
      value.research_portfolio_qualification === null ||
      isResearchPortfolioQualification(value.research_portfolio_qualification)) &&
    Array.isArray(value.predicted_tickets) &&
    value.predicted_tickets.every(isTicket) &&
    isNumberArray(value.actual_main_numbers) &&
    isNumberArray(value.actual_special_numbers) &&
    (value.portfolio_any_prize === null || typeof value.portfolio_any_prize === 'boolean') &&
    (value.uniform_eight_reference === undefined || value.uniform_eight_reference === null ||
      isUniformEightReference(value.uniform_eight_reference)) &&
    (value.research_main_three === undefined || value.research_main_three === null ||
      isMainThreeReference(value.research_main_three)) &&
    isNullableNonNegativeSafeInteger(value.best_main_hits) &&
    isString(value.source_kind) &&
    isString(value.data_status) &&
    (value.prediction_cutoff === undefined ||
      value.prediction_cutoff === null ||
      isPredictionCutoff(value.prediction_cutoff)) &&
    isTraining(value.training)
  )
}

function isMainThreeReference(value: unknown): value is MainThreeReference {
  return isRecord(value) && value.metric_id === 'MAIN_HITS_GE_3_ANY_OF_THREE' &&
    isNullableString(value.scorer_version) &&
    ((value.status === 'UNKNOWN' && value.success === null) ||
      (value.status === 'SCORABLE' && typeof value.success === 'boolean'))
}

function isMainThreeSummary(value: unknown): value is MainThreeSummary {
  return isRecord(value) && isString(value.run_id) && isString(value.strategy_id) &&
    value.metric_id === 'MAIN_HITS_GE_3_ANY_OF_THREE' &&
    isNonNegativeSafeInteger(value.unrelated_cells) && Array.isArray(value.groups) &&
    value.groups.every((group: unknown) => {
      if (!isRecord(group) || !isString(group.strategy_version) ||
          !isString(group.dataset_identity) || !isString(group.execution_version) ||
          !isNullableString(group.scorer_version) || !isNonNegativeSafeInteger(group.eligible_draws) ||
          !isNonNegativeSafeInteger(group.unknown_draws) || !isNonNegativeSafeInteger(group.successes) ||
          !isNonNegativeSafeInteger(group.unknown_provenance_draws) ||
          group.successes > group.eligible_draws ||
          group.unknown_provenance_draws > group.eligible_draws + group.unknown_draws) return false
      if (group.eligible_draws === 0) return group.success_rate_percent === null &&
        group.baseline_success_rate_percent === null && group.difference_from_baseline_pp === null
      return typeof group.scorer_version === 'string' && group.scorer_version.length > 0 &&
        typeof group.success_rate_percent === 'number' && Number.isFinite(group.success_rate_percent) &&
        typeof group.baseline_success_rate_percent === 'number' && Number.isFinite(group.baseline_success_rate_percent) &&
        group.baseline_success_rate_percent >= 0 && group.baseline_success_rate_percent <= 100 &&
        typeof group.difference_from_baseline_pp === 'number' && Number.isFinite(group.difference_from_baseline_pp) &&
        Math.abs(group.success_rate_percent - 100 * group.successes / group.eligible_draws) < 1e-8 &&
        Math.abs(group.difference_from_baseline_pp -
          (group.success_rate_percent - group.baseline_success_rate_percent)) < 1e-8
    })
}

function isUniformEightReference(value: unknown): value is UniformEightReference {
  return isRecord(value) && (value.status === 'SCORABLE' || value.status === 'UNKNOWN') &&
    isNullableNonNegativeSafeInteger(value.ticket_count) && isNullableBoolean(value.any_prize) &&
    ((value.status === 'UNKNOWN' && value.any_prize === null) ||
      (value.status === 'SCORABLE' && typeof value.any_prize === 'boolean'))
}

function isUniformEightSummary(value: unknown): value is UniformEightSummary {
  return isRecord(value) && isNullableString(value.run_id) && isString(value.strategy_id) &&
    value.metric_id === 'REFERENCE_FIXED_EIGHT_TIER_ANY_PRIZE' && Array.isArray(value.groups) &&
    value.groups.every((group: unknown) => isRecord(group) && isString(group.strategy_version) &&
      isNullableNonNegativeSafeInteger(group.ticket_count) &&
      isNonNegativeSafeInteger(group.scorable_draws) && isNonNegativeSafeInteger(group.unknown_draws) &&
      isNonNegativeSafeInteger(group.successes) && group.successes <= group.scorable_draws &&
      (group.success_rate_percent === null || (typeof group.success_rate_percent === 'number' &&
        Number.isFinite(group.success_rate_percent) && group.success_rate_percent >= 0 && group.success_rate_percent <= 100)) &&
      isNonNegativeSafeInteger(group.unknown_provenance_draws) &&
      (group.baseline_kind === 'UNKNOWN' || group.baseline_kind === 'UNIFORM_RANDOM_DISJOINT_K3') &&
      (group.baseline_kind === 'UNKNOWN'
        ? group.baseline_success_rate_percent === null && group.difference_from_baseline_pp === null
        : typeof group.baseline_success_rate_percent === 'number' && Number.isFinite(group.baseline_success_rate_percent) &&
          typeof group.difference_from_baseline_pp === 'number' && Number.isFinite(group.difference_from_baseline_pp)))
}

function isPredictionPage(
  value: unknown,
  query: {
    lotteryType: ReplayBackfillLotteryType
    strategyId?: string
    strategyVersion?: string
  },
): value is ReplayBackfillPredictionPage {
  return (
    isRecord(value) &&
    isNullableString(value.run_id) &&
    isNonNegativeSafeInteger(value.total_count) &&
    Array.isArray(value.items) &&
    value.items.every((item) =>
      isPredictionItem(item) &&
      item.lottery_type === query.lotteryType &&
      (!query.strategyId || item.strategy_id === query.strategyId) &&
      (!query.strategyVersion || item.strategy_version === query.strategyVersion),
    ) &&
    (value.next_cursor === null || isString(value.next_cursor))
  )
}

function isK3Comparison(value: unknown): value is K3Comparison {
  if (!isRecord(value) || !isString(value.run_id) ||
      (value.strategy !== 'optimizer' && value.strategy !== 'ecp') ||
      !isNonNegativeSafeInteger(value.target_count) ||
      !isNonNegativeSafeInteger(value.paired_count) ||
      !isNonNegativeSafeInteger(value.unmatched_count) ||
      !isNonNegativeSafeInteger(value.old_wins) || !isNonNegativeSafeInteger(value.new_wins) ||
      !isNonNegativeSafeInteger(value.old_only) || !isNonNegativeSafeInteger(value.new_only) ||
      !(value.fair_delta === null || (typeof value.fair_delta === 'number' && Number.isFinite(value.fair_delta))) ||
      !(value.observed_minus_fair === null || (typeof value.observed_minus_fair === 'number' && Number.isFinite(value.observed_minus_fair))) ||
      !Array.isArray(value.rows) || value.rows.length !== value.target_count ||
      value.paired_count + value.unmatched_count !== value.target_count ||
      value.old_wins > value.paired_count || value.new_wins > value.paired_count) return false
  const seen = new Set<string>()
  return value.rows.every((row: unknown) => {
    if (!isRecord(row) || !isString(row.target_draw_number) || seen.has(row.target_draw_number) ||
        !isString(row.target_draw_date) || !isString(row.match_status) ||
        !isNullableString(row.source_segment) || !isNullableString(row.original_source_run_id) ||
        !isNullableString(row.old_cell_identity) || !isPredictionItem(row.new) ||
        !(row.old === null || isPredictionItem(row.old))) return false
    seen.add(row.target_draw_number)
    return row.new.target_draw_number === row.target_draw_number &&
      (row.old === null || row.old.target_draw_number === row.target_draw_number)
  })
}

export async function getK3Comparison(
  strategy: K3ComparisonStrategy,
  signal?: AbortSignal,
): Promise<K3Comparison> {
  return getJson(
    `/api/v1/replay-backfill/k3-comparison?strategy=${strategy}`,
    signal,
    isK3Comparison,
    (response, status) => {
      if (response.strategy !== strategy) {
        throw new ReplayBackfillRequestError('Comparison strategy does not match the request.', status)
      }
    },
  )
}

function isCoverage(value: unknown): value is ReplayBackfillCoverage {
  return (
    isRecord(value) &&
    isNonNegativeSafeInteger(value.expected_strategy_count) &&
    isNonNegativeSafeInteger(value.expected_target_count) &&
    isNonNegativeSafeInteger(value.expected_cell_count) &&
    isNonNegativeSafeInteger(value.completed_cell_count) &&
    isNonNegativeSafeInteger(value.failed_cell_count) &&
    isNonNegativeSafeInteger(value.closed_cell_count) &&
    typeof value.complete_coverage_percent === 'number' &&
    Number.isFinite(value.complete_coverage_percent) &&
    value.complete_coverage_percent >= 0 &&
    value.complete_coverage_percent <= 100 &&
    Array.isArray(value.missing_strategy_ids) &&
    value.missing_strategy_ids.every(isString) &&
    isNullableString(value.run_id)
  )
}

const STRATEGY_RUN_ITEM_KEYS = [
  'run_id',
  'lottery_type',
  'strategy_id',
  'strategy_version',
  'run_created_at',
  'inventory_present',
  'associated_cell_count',
  'unique_target_draw_count',
  'execution_identity_count',
  'execution_status_counts',
  'earliest_target_draw_date',
  'latest_target_draw_date',
] as const

const STRATEGY_RUNS_PAGE_KEYS = [
  'total_run_version_matches',
  'items',
  'has_more',
  'limit',
  'offset',
] as const

function isNonEmptyString(value: unknown): value is string {
  return isString(value) && value.trim().length > 0
}

function isExecutionStatusCounts(value: unknown): value is Record<string, number> {
  return isRecord(value) && Object.values(value).every(isNonNegativeSafeInteger)
}

function isStrategyRunItem(
  value: unknown,
  query: { lotteryType: ReplayBackfillLotteryType; strategyId: string; strategyVersion?: string },
): value is ReplayBackfillStrategyRunItem {
  if (!isRecord(value) || !hasExactKeys(value, STRATEGY_RUN_ITEM_KEYS)) return false
  return (
    isNonEmptyString(value.run_id) &&
    value.lottery_type === query.lotteryType &&
    value.strategy_id === query.strategyId &&
    isNonEmptyString(value.strategy_version) &&
    (!query.strategyVersion || value.strategy_version === query.strategyVersion) &&
    isString(value.run_created_at) &&
    typeof value.inventory_present === 'boolean' &&
    isNonNegativeSafeInteger(value.associated_cell_count) &&
    isNonNegativeSafeInteger(value.unique_target_draw_count) &&
    isNonNegativeSafeInteger(value.execution_identity_count) &&
    isExecutionStatusCounts(value.execution_status_counts) &&
    isNullableString(value.earliest_target_draw_date) &&
    isNullableString(value.latest_target_draw_date)
  )
}

function isStrategyRunsPage(
  value: unknown,
  query: {
    lotteryType: ReplayBackfillLotteryType
    strategyId: string
    strategyVersion?: string
    limit: number
    offset: number
  },
): value is ReplayBackfillStrategyRunsPage {
  if (!isRecord(value) || !hasExactKeys(value, STRATEGY_RUNS_PAGE_KEYS)) return false
  if (
    !isNonNegativeSafeInteger(value.total_run_version_matches) ||
    typeof value.has_more !== 'boolean' ||
    value.limit !== query.limit ||
    value.offset !== query.offset ||
    !Array.isArray(value.items) ||
    value.items.length > query.limit ||
    !value.items.every((item) => isStrategyRunItem(item, query))
  ) {
    return false
  }
  const nextOffset = query.offset + value.items.length
  if (!Number.isSafeInteger(nextOffset)) return false
  return (
    (value.has_more ? value.items.length > 0 && nextOffset < value.total_run_version_matches
      : nextOffset >= value.total_run_version_matches)
  )
}

async function getJson<T>(
  path: string,
  signal: AbortSignal | undefined,
  validate: (value: unknown) => value is T,
  afterValidate?: (value: T, status: number) => void,
): Promise<T> {
  const response = await fetch(path, {
    method: 'GET',
    headers: { Accept: 'application/json' },
    signal,
  })
  let payload: unknown
  let payloadParsed = false
  try {
    payload = await response.json()
    payloadParsed = true
  } catch {
    payload = null
  }
  if (!response.ok) {
    const error = isRecord(payload) ? payload : {}
    const message = isString(error.message)
      ? error.message
      : `Replay backfill request failed with HTTP ${response.status}`
    throw new ReplayBackfillRequestError(message, response.status, isString(error.error_code) ? error.error_code : undefined)
  }
  if (!validate(payload)) {
    throw new ReplayBackfillRequestError(
      'Replay backfill returned an invalid response.',
      payloadParsed ? 502 : response.status,
    )
  }
  afterValidate?.(payload, response.status)
  return payload
}

function assertRequestedRunIdMatches(
  response: { run_id: string | null },
  requestedRunId: string | undefined,
  status: number,
): void {
  const requested = requestedRunId?.trim()
  if (requested && response.run_id !== null && response.run_id !== requested) {
    throw new ReplayBackfillRequestError(
      'Replay backfill returned a run ID that does not match the requested run ID.',
      status,
      'REPLAY_RUN_ID_MISMATCH',
    )
  }
}

function validateLimit(limit: number): void {
  if (!Number.isSafeInteger(limit) || limit < 1) {
    throw new RangeError('Replay backfill limit must be a positive safe integer')
  }
}

function validateStrategyRunsLimit(limit: number): void {
  if (!Number.isSafeInteger(limit) || limit < 1 || limit > 250) {
    throw new RangeError('Strategy-run discovery limit must be an integer from 1 to 250')
  }
}

function validateStrategyRunsOffset(offset: number): void {
  if (!isNonNegativeSafeInteger(offset)) {
    throw new RangeError('Strategy-run discovery offset must be a non-negative safe integer')
  }
}

export function isValidReplayDate(value: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false
  const date = new Date(`${value}T00:00:00Z`)
  return Number.isFinite(date.getTime()) && date.toISOString().slice(0, 10) === value
}

export function isValidReplayDateRange(fromDate: string, toDate: string): boolean {
  if (fromDate && !isValidReplayDate(fromDate)) return false
  if (toDate && !isValidReplayDate(toDate)) return false
  return !fromDate || !toDate || fromDate <= toDate
}

export async function listReplayBackfillStrategies(
  query: ReplayBackfillStrategyQuery,
  signal?: AbortSignal,
): Promise<ReplayBackfillStrategyPage> {
  const limit = query.limit ?? 100
  validateLimit(limit)
  const params = new URLSearchParams({ lottery_type: query.lotteryType, limit: String(limit) })
  if (query.runId?.trim()) params.set('run_id', query.runId.trim())
  const q = query.q?.trim()
  if (q) params.set('q', q)
  if (query.lifecycleStatus) params.set('lifecycle_status', query.lifecycleStatus)
  if (query.dataStatus) params.set('data_status', query.dataStatus)
  if (query.cursor) params.set('cursor', query.cursor)
  return getJson(
    `/api/v1/replay-backfill/strategies?${params.toString()}`,
    signal,
    isStrategyPage,
  )
}

export async function listReplayStrategyInventory(
  lotteryType: ReplayBackfillLotteryType,
  signal?: AbortSignal,
): Promise<ReplayStrategyInventoryResponse> {
  const params = new URLSearchParams({ lottery_type: lotteryType })
  const response = await getJson(
    `/api/v1/replay-strategy-inventory?${params.toString()}`,
    signal,
    isStrategyInventoryResponse,
  )
  return {
    ...response,
    strategies: response.strategies.map((item) => ({
      ...item,
      reconstructable: item.reconstructable ?? null,
      wrapper_callable: item.wrapper_callable ?? null,
      backfill_native_binding: item.backfill_native_binding ?? null,
      backfill_runnable: item.backfill_runnable ?? null,
      execution_block_reason: item.execution_block_reason ?? null,
    })),
  }
}

export async function listReplayStrategyRuns(
  query: ReplayStrategyRunsQuery,
  signal?: AbortSignal,
): Promise<ReplayBackfillStrategyRunsPage> {
  const strategyId = query.strategyId.trim()
  if (!strategyId) throw new RangeError('A complete strategy ID is required for run discovery')
  const strategyVersion = query.strategyVersion?.trim() || undefined
  const limit = query.limit ?? 50
  const offset = query.offset ?? 0
  validateStrategyRunsLimit(limit)
  validateStrategyRunsOffset(offset)
  const params = new URLSearchParams({
    lottery_type: query.lotteryType,
    strategy_id: strategyId,
    limit: String(limit),
    offset: String(offset),
  })
  if (strategyVersion) params.set('strategy_version', strategyVersion)
  const expected = {
    lotteryType: query.lotteryType,
    strategyId,
    ...(strategyVersion ? { strategyVersion } : {}),
    limit,
    offset,
  }
  return getJson(
    `/api/v1/replay-backfill/strategy-runs?${params.toString()}`,
    signal,
    (value): value is ReplayBackfillStrategyRunsPage => isStrategyRunsPage(value, expected),
  )
}

export async function listReplayBackfillPredictions(
  query: ReplayBackfillPredictionQuery,
  signal?: AbortSignal,
): Promise<ReplayBackfillPredictionPage> {
  const strategyId = query.strategyId?.trim() || undefined
  const strategyVersion = query.strategyVersion?.trim() || undefined
  if (strategyVersion && !strategyId) {
    throw new RangeError('A strategy version requires a complete strategy ID')
  }
  const limit = query.limit ?? 50
  validateLimit(limit)
  if (!REPLAY_BACKFILL_PERIODS.includes(query.period)) {
    throw new RangeError('Replay backfill period must be 50, 300, 750, or ALL')
  }
  if (!isValidReplayDateRange(query.fromDate ?? '', query.toDate ?? '')) {
    throw new RangeError('Replay backfill date range is invalid')
  }
  const params = new URLSearchParams({
    lottery_type: query.lotteryType,
    period: String(query.period),
    limit: String(limit),
  })
  if (query.runId?.trim()) params.set('run_id', query.runId.trim())
  if (strategyId) params.set('strategy_id', strategyId)
  if (strategyVersion) params.set('strategy_version', strategyVersion)
  if (query.fromDate) params.set('from_date', query.fromDate)
  if (query.toDate) params.set('to_date', query.toDate)
  if (query.cursor) params.set('cursor', query.cursor)
  return getJson(
    `/api/v1/replay-backfill/predictions?${params.toString()}`,
    signal,
    (value): value is ReplayBackfillPredictionPage =>
      isPredictionPage(value, {
        lotteryType: query.lotteryType,
        ...(strategyId ? { strategyId } : {}),
        ...(strategyVersion ? { strategyVersion } : {}),
      }),
    (response, status) => assertRequestedRunIdMatches(response, query.runId, status),
  )
}

export async function getUniformEightSummary(
  query: ReplayBackfillPredictionQuery & { strategyId: string },
  signal?: AbortSignal,
): Promise<UniformEightSummary> {
  const params = new URLSearchParams({ strategy_id: query.strategyId, period: String(query.period) })
  if (query.runId?.trim()) params.set('run_id', query.runId.trim())
  if (query.fromDate) params.set('from_date', query.fromDate)
  if (query.toDate) params.set('to_date', query.toDate)
  return getJson(`/api/v1/replay-backfill/uniform-eight-reference?${params.toString()}`,
    signal, isUniformEightSummary,
    (response, status) => assertRequestedRunIdMatches(response, query.runId, status))
}

export async function getMainThreeSummary(
  query: ReplayBackfillPredictionQuery & { strategyId: string; runId: string },
  signal?: AbortSignal,
): Promise<MainThreeSummary> {
  const params = new URLSearchParams({
    strategy_id: query.strategyId, run_id: query.runId, period: String(query.period),
  })
  if (query.strategyVersion) params.set('strategy_version', query.strategyVersion)
  if (query.fromDate) params.set('from_date', query.fromDate)
  if (query.toDate) params.set('to_date', query.toDate)
  return getJson(`/api/v1/replay-backfill/research-main-three-summary?${params.toString()}`,
    signal, isMainThreeSummary, (response, status) => {
      assertRequestedRunIdMatches(response, query.runId, status)
      if (response.strategy_id !== query.strategyId) {
        throw new ReplayBackfillRequestError('Research summary strategy changed.', status)
      }
      if (query.strategyVersion && response.groups.some(
        (group) => group.strategy_version !== query.strategyVersion,
      )) {
        throw new ReplayBackfillRequestError('Research summary version changed.', status)
      }
    })
}

export type HedgeK3ProvenanceStatus = 'VERIFIED' | 'UNKNOWN' | 'UNVERIFIED'

export interface HedgeK3StoredResult {
  run_id?: string
  target_draw_id: string
  strategy_id: string
  strategy_version: string
  execution_status: string
  source_history_provenance_status: HedgeK3ProvenanceStatus
  hedge_phase?: unknown
  reference_any_prize?: unknown
  combination_success?: unknown
}

export function normalizeHedgeK3ProvenanceStatus(value: unknown): HedgeK3ProvenanceStatus {
  if (value === 'VERIFIED') return 'VERIFIED'
  if (value === 'UNVERIFIED') return 'UNVERIFIED'
  return 'UNKNOWN'
}

export interface HedgeK3ProvenanceMetricSummary {
  verified_numerator: number
  verified_denominator: number
  verified_rate_display: string
  raw_true_count: number
  raw_total_count: number
  raw_flag_display: string
  verified_count: number
  unknown_count: number
  unverified_count: number
  missing_flag_count: number
  is_evaluatable: boolean
}

export function computeHedgeK3ProvenanceMetricSummary(
  scope: readonly HedgeK3StoredResult[],
  field: 'reference_any_prize' | 'combination_success',
): HedgeK3ProvenanceMetricSummary {
  const verifiedRows = scope.filter((row) => row.source_history_provenance_status === 'VERIFIED')
  const unknownCount = scope.filter((row) => row.source_history_provenance_status === 'UNKNOWN').length
  const unverifiedCount = scope.filter((row) => row.source_history_provenance_status === 'UNVERIFIED').length

  const validVerified = verifiedRows.filter((row) => typeof row[field] === 'boolean')
  const verifiedNumerator = validVerified.filter((row) => row[field] === true).length
  const verifiedDenominator = validVerified.length

  const rawValid = scope.filter((row) => typeof row[field] === 'boolean')
  const rawTrueCount = rawValid.filter((row) => row[field] === true).length
  const rawTotalCount = scope.length
  const missingFlagCount = scope.filter((row) => typeof row[field] !== 'boolean').length

  const isEvaluatable = verifiedDenominator > 0
  const verifiedRateDisplay = isEvaluatable ? `${verifiedNumerator}/${verifiedDenominator}` : '無法評估'
  const rawFlagDisplay = rawTotalCount > 0 ? `${rawTrueCount}/${rawTotalCount}` : '無可評估期數'

  return {
    verified_numerator: verifiedNumerator,
    verified_denominator: verifiedDenominator,
    verified_rate_display: verifiedRateDisplay,
    raw_true_count: rawTrueCount,
    raw_total_count: rawTotalCount,
    raw_flag_display: rawFlagDisplay,
    verified_count: verifiedRows.length,
    unknown_count: unknownCount,
    unverified_count: unverifiedCount,
    missing_flag_count: missingFlagCount,
    is_evaluatable: isEvaluatable,
  }
}

interface HedgeK3ResultsPage {
  items: Array<Record<string, unknown> & {
    target_draw_id: string
    strategy_id: string
    strategy_version: string
    execution_status: string
    run_id?: string
    source_history_provenance_status?: unknown
    hedge_phase?: unknown
    reference_any_prize?: unknown
    combination_success?: unknown
  }>
  total_count: number
  limit: number
  offset: number
}

function isHedgeK3ResultsPage(value: unknown): value is HedgeK3ResultsPage {
  return isRecord(value) &&
    isNonNegativeSafeInteger(value.total_count) &&
    isNonNegativeSafeInteger(value.limit) &&
    isNonNegativeSafeInteger(value.offset) &&
    Array.isArray(value.items) &&
    value.items.every((item: unknown) => isRecord(item) &&
      isString(item.target_draw_id) && isString(item.strategy_id) &&
      isString(item.strategy_version) && isString(item.execution_status))
}

export async function getHedgeK3StoredResults(
  runId: string,
  strategyVersion: string,
  signal: AbortSignal,
): Promise<HedgeK3StoredResult[]> {
  const limit = 200
  const rows = new Map<string, HedgeK3StoredResult>()
  let total: number | undefined
  for (let offset = 0; total === undefined || offset < total; offset += limit) {
    const params = new URLSearchParams({ run_id: runId, limit: String(limit), offset: String(offset) })
    const page = await getJson(
      `/api/v1/replay-backfill/results?${params.toString()}`,
      signal,
      isHedgeK3ResultsPage,
    )
    total ??= page.total_count
    if (
      page.total_count !== total || page.offset !== offset || page.limit !== limit ||
      page.items.length !== Math.min(limit, total - offset)
    ) {
      throw new Error('Replay API 的 Run 分頁不完整，請重新查詢。')
    }
    for (const rawRow of page.items) {
      const row = rawRow as Record<string, unknown>
      if (row.strategy_id !== HEDGE_K3_STRATEGY_ID || row.strategy_version !== strategyVersion) continue
      if (typeof row.run_id === 'string' && row.run_id !== runId) continue
      if (rows.has(row.target_draw_id as string) || row.execution_status !== 'COMPLETE') {
        throw new Error('K3 Hedge 有重複期號或未完成紀錄，無法確認成功期數。')
      }
      rows.set(row.target_draw_id as string, {
        target_draw_id: row.target_draw_id as string,
        strategy_id: row.strategy_id as string,
        strategy_version: row.strategy_version as string,
        execution_status: row.execution_status as string,
        run_id: typeof row.run_id === 'string' ? row.run_id : runId,
        source_history_provenance_status: normalizeHedgeK3ProvenanceStatus(row.source_history_provenance_status),
        hedge_phase: row.hedge_phase,
        reference_any_prize: row.reference_any_prize,
        combination_success: row.combination_success,
      })
    }
  }
  if (!rows.size) throw new Error('Replay API 未提供這個 Run 與版本的 K3 Hedge 紀錄。')
  return [...rows.values()]
}

export async function getReplayBackfillCoverage(
  lotteryType: ReplayBackfillLotteryType,
  signal?: AbortSignal,
  runId?: string,
): Promise<ReplayBackfillCoverage> {
  const params = new URLSearchParams({ lottery_type: lotteryType })
  if (runId?.trim()) params.set('run_id', runId.trim())
  return getJson(
    `/api/v1/replay-backfill/coverage?${params.toString()}`,
    signal,
    isCoverage,
    (response, status) => assertRequestedRunIdMatches(response, runId, status),
  )
}

export interface CoverageScanQuery {
  lotteryType: ReplayBackfillLotteryType
  startDate: string
  endDate: string
  strategies: { id: string; version: string }[]
  limit: number
  offset: number
}
export interface CoverageScan {
  lottery_type: ReplayBackfillLotteryType
  window_start_date: string
  window_end_date: string
  source_target_count: number
  expected_cell_count: number
  complete_cell_count: number
  incomplete_cell_count: number
  complete_coverage_percent: number
  status_counts: Record<string, number>
  strategy_counts: Record<string, { complete: number; incomplete: number; execution_versions: string[]; dataset_identities: string[] }>
  orphan_replay_row_count: number
  items: { target_draw_id: string; target_draw_date: string; strategy_id: string; strategy_version: string; status: string; reason: string | null; existing_records: unknown[] }[]
  total_count: number
  limit: number
  offset: number
  next_offset: number | null
}
export async function scanReplayCoverage(query: CoverageScanQuery, signal?: AbortSignal): Promise<CoverageScan> {
  const identities = query.strategies.map(({ id, version }) => ({ id: id.trim(), version: version.trim() }))
  if (!isLotteryType(query.lotteryType) || !query.startDate || !query.endDate ||
      !isValidReplayDateRange(query.startDate, query.endDate) || identities.length !== 5 ||
      identities.some(({ id, version }) => !id || !version || id.length > 200 || version.length > 200) ||
      new Set(identities.map(({ id }) => id)).size !== 5 ||
      !Number.isSafeInteger(query.limit) || query.limit < 1 || query.limit > 250 || !isNonNegativeSafeInteger(query.offset)) {
    throw new RangeError('請輸入有效日期及五組不同策略 ID／版本。')
  }
  const params = new URLSearchParams({ lottery_type: query.lotteryType, start_date: query.startDate, end_date: query.endDate, limit: String(query.limit), offset: String(query.offset) })
  identities.forEach(({ id }) => params.append('strategy_id', id))
  identities.forEach(({ version }) => params.append('strategy_version', version))
  return getJson(`/api/v1/replay-backfill/coverage/scan?${params}`, signal, (v): v is CoverageScan => {
    if (!isRecord(v) || v.lottery_type !== query.lotteryType || !isString(v.window_start_date) || !isString(v.window_end_date) ||
        !isNonNegativeSafeInteger(v.source_target_count) || !isNonNegativeSafeInteger(v.expected_cell_count) ||
        !isNonNegativeSafeInteger(v.complete_cell_count) || !isNonNegativeSafeInteger(v.incomplete_cell_count) ||
        v.expected_cell_count !== v.source_target_count * 5 || v.complete_cell_count + v.incomplete_cell_count !== v.expected_cell_count ||
        typeof v.complete_coverage_percent !== 'number' || !Number.isFinite(v.complete_coverage_percent) ||
        v.complete_coverage_percent < 0 || v.complete_coverage_percent > 100 || !isRecord(v.status_counts) ||
        !Object.values(v.status_counts).every(isNonNegativeSafeInteger) || !isRecord(v.strategy_counts) ||
        !isNonNegativeSafeInteger(v.orphan_replay_row_count) || !isNonNegativeSafeInteger(v.total_count) ||
        v.total_count !== v.incomplete_cell_count || v.limit !== query.limit || v.offset !== query.offset ||
        !(v.next_offset === null || (isNonNegativeSafeInteger(v.next_offset) && v.next_offset === query.offset + query.limit && v.next_offset < v.total_count)) ||
        !Array.isArray(v.items) || v.items.length !== Math.min(query.limit, Math.max(0, v.total_count - query.offset))) return false
    return identities.every(({ id, version }) => {
      const s = (v.strategy_counts as Record<string, unknown>)[`${id}@${version}`]
      return isRecord(s) && isNonNegativeSafeInteger(s.complete) && isNonNegativeSafeInteger(s.incomplete) &&
        s.complete + s.incomplete === v.source_target_count && Array.isArray(s.execution_versions) && s.execution_versions.every(isString) &&
        Array.isArray(s.dataset_identities) && s.dataset_identities.every(isString)
    }) && v.items.every((item: unknown) => isRecord(item) && isString(item.target_draw_id) && isString(item.target_draw_date) &&
      isString(item.strategy_id) && isString(item.strategy_version) && isString(item.status) && isNullableString(item.reason) && Array.isArray(item.existing_records) &&
      identities.some(({ id, version }) => id === item.strategy_id && version === item.strategy_version))
  })
}
