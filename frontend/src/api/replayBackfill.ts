export const REPLAY_BACKFILL_LOTTERY_TYPES = [
  'BIG_LOTTO',
  'DAILY_539',
  'POWER_LOTTO',
] as const

export type ReplayBackfillLotteryType = (typeof REPLAY_BACKFILL_LOTTERY_TYPES)[number]
export type ReplayBackfillPeriod = 50 | 300 | 750 | 'ALL'

export const REPLAY_BACKFILL_PERIODS: readonly ReplayBackfillPeriod[] = [50, 300, 750, 'ALL']

export type ReplayBackfillDataStatus =
  | 'HAS_HISTORY'
  | 'REBUILDABLE'
  | 'NO_HISTORY'
  | 'ARTIFACT_ONLY'
  | 'CODE_ONLY'
  | 'REJECTED'

export interface ReplayBackfillStrategyItem {
  strategy_id: string
  strategy_version: string | null
  display_name: string
  lottery_type: ReplayBackfillLotteryType
  lifecycle_status: string
  data_status: string
  source_kind: string
  executable: boolean
  available_target_count: number
  training_status: string
}

export interface ReplayBackfillStrategyPage {
  items: ReplayBackfillStrategyItem[]
  total_count: number
  next_cursor: string | null
}

export interface ReplayStrategyInventoryItem {
  lottery_type: ReplayBackfillLotteryType
  strategy_id: string
  display_name: string
  strategy_version: string | null
  source_kind: string
  source_locator: string
  lifecycle_status: string
  replay_data_status: string
  execution_capability: string
  reconstructable: boolean | null
  wrapper_callable: boolean | null
  backfill_native_binding: boolean | null
  backfill_runnable: boolean
  execution_block_reason: string | null
  reconstruction_reason: string
  historical_data_count: number
  historical_execution_count: number
}

export interface ReplayStrategyInventoryResponse {
  strategy_count: number
  strategies: ReplayStrategyInventoryItem[]
}

export interface ReplayBackfillTicket {
  ticket_position: number
  main_numbers: number[]
  special_numbers: number[]
  main_hit_count: number | null
  special_hit: boolean | null
  prize_tier: string | null
}

export interface ReplayBackfillTraining {
  training_status: string
  model_version: string | null
  training_cutoff: string | null
  training_artifact_id: string | null
}

export interface ReplayBackfillPredictionItem {
  lottery_type: ReplayBackfillLotteryType
  strategy_id: string
  strategy_version: string
  lifecycle_status?: string
  target_draw_number: string
  target_draw_date: string
  prediction_status: string
  predicted_tickets: ReplayBackfillTicket[]
  actual_main_numbers: number[]
  actual_special_numbers: number[]
  portfolio_any_prize: boolean | null
  best_main_hits: number | null
  source_kind: string
  data_status: string
  prediction_cutoff?: ReplayBackfillPredictionCutoff | null
  training: ReplayBackfillTraining
}

export type ReplayBackfillPredictionCutoffStatus = 'VERIFIED' | 'UNTRUSTED' | 'UNKNOWN'

export interface ReplayBackfillPredictionCutoff {
  draw_date: string | null
  draw_number: string | null
  history_draw_count: number | null
  reason_code: string | null
  source_hash: string | null
  source_identity: string | null
  source_locator: string | null
  status: ReplayBackfillPredictionCutoffStatus
}

export interface ReplayBackfillPredictionPage {
  run_id: string | null
  total_count: number
  items: ReplayBackfillPredictionItem[]
  next_cursor: string | null
}

export interface ReplayBackfillCoverage {
  expected_strategy_count: number
  expected_target_count: number
  expected_cell_count: number
  completed_cell_count: number
  failed_cell_count: number
  closed_cell_count: number
  complete_coverage_percent: number
  missing_strategy_ids: string[]
  run_id: string | null
}

export interface ReplayBackfillStrategyQuery {
  lotteryType: ReplayBackfillLotteryType
  q?: string
  lifecycleStatus?: string
  dataStatus?: string
  limit?: number
  cursor?: string | null
}

export interface ReplayBackfillPredictionQuery {
  lotteryType: ReplayBackfillLotteryType
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

function isNumberArray(value: unknown): value is number[] {
  return Array.isArray(value) && value.every((entry) => Number.isInteger(entry))
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
    Number.isInteger(value.available_target_count) &&
    isString(value.training_status)
  )
}

function isStrategyPage(value: unknown): value is ReplayBackfillStrategyPage {
  return (
    isRecord(value) &&
    Array.isArray(value.items) &&
    value.items.every(isStrategyItem) &&
    Number.isInteger(value.total_count) &&
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
    typeof value.historical_data_count === 'number' &&
    Number.isInteger(value.historical_data_count) &&
    value.historical_data_count >= 0 &&
    typeof value.historical_execution_count === 'number' &&
    Number.isInteger(value.historical_execution_count) &&
    value.historical_execution_count >= 0
  )
}

function isPredictionCutoff(value: unknown): value is ReplayBackfillPredictionCutoff {
  return (
    isRecord(value) &&
    isNullableString(value.draw_date) &&
    isNullableString(value.draw_number) &&
    (value.history_draw_count === null || Number.isInteger(value.history_draw_count)) &&
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
    typeof value.strategy_count === 'number' &&
    Number.isInteger(value.strategy_count) &&
    value.strategy_count >= 0 &&
    Array.isArray(value.strategies) &&
    value.strategies.every(isStrategyInventoryItem) &&
    value.strategy_count === value.strategies.length
  )
}

function isTicket(value: unknown): value is ReplayBackfillTicket {
  return (
    isRecord(value) &&
    Number.isInteger(value.ticket_position) &&
    isNumberArray(value.main_numbers) &&
    isNumberArray(value.special_numbers) &&
    (value.main_hit_count === null || Number.isInteger(value.main_hit_count)) &&
    (value.special_hit === null || typeof value.special_hit === 'boolean') &&
    isNullableString(value.prize_tier)
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
    Array.isArray(value.predicted_tickets) &&
    value.predicted_tickets.every(isTicket) &&
    isNumberArray(value.actual_main_numbers) &&
    isNumberArray(value.actual_special_numbers) &&
    (value.portfolio_any_prize === null || typeof value.portfolio_any_prize === 'boolean') &&
    (value.best_main_hits === null || Number.isInteger(value.best_main_hits)) &&
    isString(value.source_kind) &&
    isString(value.data_status) &&
    (value.prediction_cutoff === undefined ||
      value.prediction_cutoff === null ||
      isPredictionCutoff(value.prediction_cutoff)) &&
    isTraining(value.training)
  )
}

function isPredictionPage(value: unknown): value is ReplayBackfillPredictionPage {
  return (
    isRecord(value) &&
    isNullableString(value.run_id) &&
    Number.isInteger(value.total_count) &&
    Array.isArray(value.items) &&
    value.items.every(isPredictionItem) &&
    (value.next_cursor === null || isString(value.next_cursor))
  )
}

function isCoverage(value: unknown): value is ReplayBackfillCoverage {
  return (
    isRecord(value) &&
    Number.isInteger(value.expected_strategy_count) &&
    Number.isInteger(value.expected_target_count) &&
    Number.isInteger(value.expected_cell_count) &&
    Number.isInteger(value.completed_cell_count) &&
    Number.isInteger(value.failed_cell_count) &&
    Number.isInteger(value.closed_cell_count) &&
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
  return payload
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
  if (query.strategyId) params.set('strategy_id', query.strategyId)
  if (query.fromDate) params.set('from_date', query.fromDate)
  if (query.toDate) params.set('to_date', query.toDate)
  if (query.cursor) params.set('cursor', query.cursor)
  return getJson(
    `/api/v1/replay-backfill/predictions?${params.toString()}`,
    signal,
    isPredictionPage,
  )
}

export async function getReplayBackfillCoverage(
  lotteryType: ReplayBackfillLotteryType,
  signal?: AbortSignal,
): Promise<ReplayBackfillCoverage> {
  const params = new URLSearchParams({ lottery_type: lotteryType })
  return getJson(`/api/v1/replay-backfill/coverage?${params.toString()}`, signal, isCoverage)
}
