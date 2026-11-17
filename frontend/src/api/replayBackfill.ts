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

export type ReplayStrategyInventoryItem = components['schemas']['ReplayStrategyInventoryItemView']
export type ReplayStrategyInventoryResponse = components['schemas']['ReplayStrategyInventoryResponse']

export type ReplayBackfillTicket = components['schemas']['ReplayBackfillPredictedTicketView']
export type ReplayBackfillTraining = components['schemas']['ReplayBackfillTrainingView']
export type ReplayBackfillPredictionCutoffStatus = 'VERIFIED' | 'UNTRUSTED' | 'UNKNOWN'
export type ReplayBackfillPredictionCutoff = components['schemas']['ReplayBackfillPredictionCutoffView']
export type ReplayBackfillResearchPortfolioQualification =
  components['schemas']['ReplayBackfillResearchPortfolioQualificationView']
export type UniformEightReference = components['schemas']['ReplayUniformEightReferenceView']
export type UniformEightSummary = components['schemas']['ReplayUniformEightSummaryView']
export type ReplayBackfillPredictionItem = components['schemas']['ReplayBackfillPredictionItemView']
export type ReplayBackfillPredictionPage = components['schemas']['ReplayBackfillPredictionPageResponse']

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
  fromDate?: string
  toDate?: string
  period: ReplayBackfillPeriod
  limit?: number
  cursor?: string | null
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

function isStrategyInventoryItem(value: unknown): value is ReplayStrategyInventoryItem {
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
    isNullableBoolean(value.reconstructable) &&
    isNullableBoolean(value.wrapper_callable) &&
    isNullableBoolean(value.backfill_native_binding) &&
    typeof value.backfill_runnable === 'boolean' &&
    isNullableString(value.execution_block_reason) &&
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

function isStrategyInventoryResponse(value: unknown): value is ReplayStrategyInventoryResponse {
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
    isNullableNonNegativeSafeInteger(value.best_main_hits) &&
    isString(value.source_kind) &&
    isString(value.data_status) &&
    (value.prediction_cutoff === undefined ||
      value.prediction_cutoff === null ||
      isPredictionCutoff(value.prediction_cutoff)) &&
    isTraining(value.training)
  )
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

function isPredictionPage(value: unknown): value is ReplayBackfillPredictionPage {
  return (
    isRecord(value) &&
    isNullableString(value.run_id) &&
    isNonNegativeSafeInteger(value.total_count) &&
    Array.isArray(value.items) &&
    value.items.every(isPredictionItem) &&
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
    Array.isArray(value.missing_strategy_ids) &&
    value.missing_strategy_ids.every(isString) &&
    isNullableString(value.run_id)
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
  try {
    payload = await response.json()
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
    throw new ReplayBackfillRequestError('Replay backfill returned an invalid response.', response.status)
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
  if (!Number.isInteger(limit) || limit < 1) {
    throw new RangeError('Replay backfill limit must be a positive integer')
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
  return getJson(
    `/api/v1/replay-strategy-inventory?${params.toString()}`,
    signal,
    isStrategyInventoryResponse,
  )
}

export async function listReplayBackfillPredictions(
  query: ReplayBackfillPredictionQuery,
  signal?: AbortSignal,
): Promise<ReplayBackfillPredictionPage> {
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
  if (query.strategyId) params.set('strategy_id', query.strategyId)
  if (query.fromDate) params.set('from_date', query.fromDate)
  if (query.toDate) params.set('to_date', query.toDate)
  if (query.cursor) params.set('cursor', query.cursor)
  return getJson(
    `/api/v1/replay-backfill/predictions?${params.toString()}`,
    signal,
    isPredictionPage,
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
