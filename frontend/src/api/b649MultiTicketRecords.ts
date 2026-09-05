import type { components, paths } from './generated/openapi'

export type B649MultiTicketSummary =
  paths['/api/v1/b649-multi-ticket-records/summary']['get']['responses'][200]['content']['application/json']
export type B649MultiTicketRecordPage =
  paths['/api/v1/b649-multi-ticket-records']['get']['responses'][200]['content']['application/json']
export type B649MultiTicketRecord = B649MultiTicketRecordPage['items'][number]
export type B649ExactNativeRecordPage =
  paths['/api/v1/b649-exact-native-records']['get']['responses'][200]['content']['application/json']
export type B649ExactNativeRecord = B649ExactNativeRecordPage['items'][number]
export type B649PrefixCount = components['schemas']['B649PrefixCount']
export type B649ExactNativeTicketCount = components['schemas']['B649ExactNativeTicketCount']
export type B649HistoryWindow = components['schemas']['B649HistoryWindow']
export type B649SuccessCriterion = components['schemas']['B649SuccessCriterion']
export type B649PrimaryRankingCriterion = 'OFFICIAL_ANY_PRIZE'
export type B649ReproductionStatus =
  | 'BACKTESTED'
  | 'CLOSED_UNEXECUTABLE'
  | 'DUPLICATE_ALIAS'

export const B649_PREFIX_COUNTS = [5, 10, 15, 20] as const satisfies readonly B649PrefixCount[]
export const B649_EXACT_NATIVE_TICKET_COUNTS = [2, 3] as const satisfies readonly B649ExactNativeTicketCount[]
export const B649_HISTORY_WINDOWS = [
  'FULL',
  'RECENT_750',
  'RECENT_300',
  'RECENT_50',
] as const satisfies readonly B649HistoryWindow[]
export const B649_SUCCESS_CRITERIA = [
  'M3_PLUS',
  'M4_PLUS',
  'M5_PLUS',
  'M6',
  'M2_PLUS_SPECIAL',
  'M3_PLUS_SPECIAL',
  'M4_PLUS_SPECIAL',
  'M5_PLUS_SPECIAL',
] as const satisfies readonly B649SuccessCriterion[]
export const B649_PRIMARY_RANKING_CRITERION: B649PrimaryRankingCriterion =
  'OFFICIAL_ANY_PRIZE'
export const B649_REPRODUCTION_STATUSES = [
  'BACKTESTED',
  'CLOSED_UNEXECUTABLE',
  'DUPLICATE_ALIAS',
] as const satisfies readonly B649ReproductionStatus[]
export const B649_RESEARCH_DISCLAIMER =
  '歷史成功率、排名與隨機基準差異僅供描述性研究，不構成未來預測、推薦、上線決策或中獎保證。'

const SUMMARY_ENDPOINT = '/api/v1/b649-multi-ticket-records/summary'
const RECORDS_ENDPOINT = '/api/v1/b649-multi-ticket-records'
const EXACT_NATIVE_RECORDS_ENDPOINT = '/api/v1/b649-exact-native-records'
const SHA256_PATTERN = /^[0-9a-f]{64}$/

export interface B649MultiTicketRecordQuery {
  prefixCount: B649PrefixCount
  window: B649HistoryWindow
  criterion: B649SuccessCriterion
  q?: string
  methodFamily?: string
  reproductionStatus?: B649ReproductionStatus
  limit: number
  offset: number
}

export interface B649ExactNativeRecordQuery {
  ticketCount: B649ExactNativeTicketCount
  window: B649HistoryWindow
  q?: string
  methodFamily?: string
  reproductionStatus?: B649ReproductionStatus
  limit?: number
  offset?: number
}

export type B649RecordsErrorKind =
  | 'UNAVAILABLE'
  | 'INVALID_REQUEST'
  | 'MALFORMED_RESPONSE'
  | 'NETWORK'

export class B649RecordsRequestError extends Error {
  readonly status: number
  readonly kind: B649RecordsErrorKind
  readonly errorCode: string | null

  constructor(
    message: string,
    status: number,
    kind: B649RecordsErrorKind,
    errorCode: string | null = null,
  ) {
    super(message)
    this.name = 'B649RecordsRequestError'
    this.status = status
    this.kind = kind
    this.errorCode = errorCode
  }
}

export async function fetchB649MultiTicketSummary(
  signal?: AbortSignal,
): Promise<B649MultiTicketSummary> {
  return requestJson(SUMMARY_ENDPOINT, isSummary, signal)
}

export async function fetchB649MultiTicketRecords(
  query: B649MultiTicketRecordQuery,
  signal?: AbortSignal,
): Promise<B649MultiTicketRecordPage> {
  const parameters = new URLSearchParams({
    prefix_count: String(query.prefixCount),
    window: query.window,
    criterion: query.criterion,
    limit: String(query.limit),
    offset: String(query.offset),
  })
  if (query.q) parameters.set('q', query.q)
  if (query.methodFamily) parameters.set('method_family', query.methodFamily)
  if (query.reproductionStatus) {
    parameters.set('reproduction_status', query.reproductionStatus)
  }
  return requestJson(`${RECORDS_ENDPOINT}?${parameters}`, isRecordPage, signal)
}

export async function fetchB649ExactNativeRecords(
  query: B649ExactNativeRecordQuery,
  signal?: AbortSignal,
): Promise<B649ExactNativeRecordPage> {
  const parameters = new URLSearchParams({
    ticket_count: String(query.ticketCount),
    window: query.window,
  })
  if (query.limit !== undefined) parameters.set('limit', String(query.limit))
  if (query.offset !== undefined) parameters.set('offset', String(query.offset))
  if (query.q) parameters.set('q', query.q)
  if (query.methodFamily) parameters.set('method_family', query.methodFamily)
  if (query.reproductionStatus) {
    parameters.set('reproduction_status', query.reproductionStatus)
  }
  return requestJson(`${EXACT_NATIVE_RECORDS_ENDPOINT}?${parameters}`, isExactNativeRecordPage, signal)
}

async function requestJson<T>(
  url: string,
  validate: (value: unknown) => value is T,
  signal?: AbortSignal,
): Promise<T> {
  let response: Response
  try {
    response = await fetch(url, { signal })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new B649RecordsRequestError('Network request failed.', 0, 'NETWORK')
  }

  let payload: unknown
  try {
    payload = await response.json()
  } catch {
    throw new B649RecordsRequestError(
      'The server returned invalid JSON.',
      response.status,
      'MALFORMED_RESPONSE',
    )
  }
  if (!response.ok) {
    const errorCode =
      isRecord(payload) && typeof payload.error_code === 'string'
        ? payload.error_code
        : null
    const message =
      isRecord(payload) && typeof payload.message === 'string'
        ? payload.message
        : 'The request failed.'
    throw new B649RecordsRequestError(
      message,
      response.status,
      response.status === 503 ? 'UNAVAILABLE' : 'INVALID_REQUEST',
      errorCode,
    )
  }
  if (!validate(payload)) {
    throw new B649RecordsRequestError(
      'The server response did not match the pinned B649 contract.',
      response.status,
      'MALFORMED_RESPONSE',
    )
  }
  return payload
}

function isSummary(value: unknown): value is B649MultiTicketSummary {
  if (!isRecord(value) || !isRecord(value.progress)) return false
  const progress = value.progress
  return (
    isInteger(progress.total_strategy_count) &&
    isInteger(progress.reproduced_count) &&
    isInteger(progress.backtested_count) &&
    isInteger(progress.closed_count) &&
    isInteger(progress.duplicate_alias_count) &&
    isInteger(progress.owner_decision_required_count) &&
    isInteger(progress.uncompleted_count) &&
    isExactNumberArray(value.prefix_counts, B649_PREFIX_COUNTS) &&
    isExactStringArray(value.windows, B649_HISTORY_WINDOWS) &&
    isExactStringArray(value.success_criteria, B649_SUCCESS_CRITERIA) &&
    value.primary_ranking_criterion === B649_PRIMARY_RANKING_CRITERION &&
    Array.isArray(value.method_families) &&
    value.method_families.every(isString) &&
    isExactStringArray(value.reproduction_statuses, B649_REPRODUCTION_STATUSES) &&
    isSha256(value.catalog_sha256) &&
    typeof value.records_available === 'boolean' &&
    (value.projection_sha256 === null || isSha256(value.projection_sha256)) &&
    (value.source_report_count === null || isInteger(value.source_report_count)) &&
    value.research_disclaimer === B649_RESEARCH_DISCLAIMER
  )
}

function isRecordPage(value: unknown): value is B649MultiTicketRecordPage {
  return (
    isRecord(value) &&
    Array.isArray(value.items) &&
    value.items.every(isMultiTicketRecord) &&
    isInteger(value.total) &&
    isInteger(value.limit) &&
    isInteger(value.offset) &&
    B649_PREFIX_COUNTS.includes(value.prefix_count as B649PrefixCount) &&
    B649_HISTORY_WINDOWS.includes(value.window as B649HistoryWindow) &&
    B649_SUCCESS_CRITERIA.includes(value.criterion as B649SuccessCriterion) &&
    value.research_disclaimer === B649_RESEARCH_DISCLAIMER
  )
}

function isMultiTicketRecord(value: unknown): value is B649MultiTicketRecord {
  if (!isRecord(value)) return false
  const nullableInteger = (item: unknown) => item === null || isInteger(item)
  const nullableString = (item: unknown) => item === null || typeof item === 'string'
  const nullableBoolean = (item: unknown) => item === null || typeof item === 'boolean'
  return (
    isString(value.strategy_id) &&
    isString(value.strategy_version) &&
    isString(value.legacy_method_id) &&
    isString(value.source_path) &&
    isString(value.method_family) &&
    B649_REPRODUCTION_STATUSES.includes(
      value.reproduction_status as B649ReproductionStatus,
    ) &&
    nullableString(value.duplicate_alias_target) &&
    B649_PREFIX_COUNTS.includes(value.prefix_count as B649PrefixCount) &&
    B649_HISTORY_WINDOWS.includes(value.window as B649HistoryWindow) &&
    B649_SUCCESS_CRITERIA.includes(value.criterion as B649SuccessCriterion) &&
    nullableInteger(value.rank) &&
    nullableInteger(value.official_rank) &&
    nullableInteger(value.official_any_prize_count) &&
    nullableString(value.official_any_prize_rate) &&
    nullableString(value.official_random_baseline_probability) &&
    nullableString(value.official_random_baseline_delta) &&
    nullableString(value.unranked_reason) &&
    nullableInteger(value.success_count) &&
    nullableInteger(value.effective_backtest_draw_count) &&
    nullableInteger(value.successful_execution_count) &&
    nullableString(value.historical_success_rate) &&
    nullableString(value.random_baseline_success_rate) &&
    nullableString(value.random_baseline_rate_difference) &&
    nullableString(value.coverage) &&
    nullableInteger(value.window_available_draws) &&
    nullableInteger(value.window_requested_draws) &&
    nullableBoolean(value.window_complete) &&
    (value.official_prize_counts === null ||
      isOfficialPrizeCounts(value.official_prize_counts)) &&
    nullableInteger(value.no_prize_count) &&
    (value.report_sha256 === null || isSha256(value.report_sha256)) &&
    (value.report_file_sha256 === null || isSha256(value.report_file_sha256)) &&
    isSha256(value.catalog_sha256)
  )
}

function isExactNativeRecordPage(value: unknown): value is B649ExactNativeRecordPage {
  return (
    isRecord(value) &&
    Array.isArray(value.items) &&
    value.items.every(isExactNativeRecord) &&
    isInteger(value.total) &&
    isInteger(value.limit) &&
    isInteger(value.offset) &&
    B649_EXACT_NATIVE_TICKET_COUNTS.includes(value.ticket_count as B649ExactNativeTicketCount) &&
    B649_HISTORY_WINDOWS.includes(value.window as B649HistoryWindow) &&
    isString(value.criterion) &&
    value.research_disclaimer === B649_RESEARCH_DISCLAIMER
  )
}

function isExactNativeRecord(value: unknown): value is B649ExactNativeRecord {
  if (!isRecord(value)) return false
  const nullableInteger = (item: unknown) => item === null || isInteger(item)
  const nullableString = (item: unknown) => item === null || typeof item === 'string'
  const nullableBoolean = (item: unknown) => item === null || typeof item === 'boolean'
  return (
    isString(value.strategy_id) &&
    isString(value.strategy_version) &&
    isString(value.legacy_method_id) &&
    isString(value.source_path) &&
    isString(value.method_family) &&
    B649_REPRODUCTION_STATUSES.includes(
      value.reproduction_status as B649ReproductionStatus,
    ) &&
    nullableString(value.duplicate_alias_target) &&
    B649_EXACT_NATIVE_TICKET_COUNTS.includes(value.ticket_count as B649ExactNativeTicketCount) &&
    B649_HISTORY_WINDOWS.includes(value.window as B649HistoryWindow) &&
    isString(value.criterion) &&
    (value.metric_status === 'AVAILABLE' || value.metric_status === 'UNAVAILABLE') &&
    typeof value.rankable === 'boolean' &&
    nullableString(value.unavailable_reason) &&
    nullableString(value.metrics_unavailable_reason) &&
    nullableString(value.unranked_reason) &&
    nullableInteger(value.official_any_prize_count) &&
    nullableString(value.official_any_prize_rate) &&
    nullableString(value.official_random_baseline_probability) &&
    nullableString(value.official_random_baseline_delta) &&
    nullableString(value.coverage) &&
    (value.official_prize_counts === null ||
      isOfficialPrizeCounts(value.official_prize_counts)) &&
    nullableInteger(value.no_prize_count) &&
    nullableInteger(value.available_observation_count) &&
    nullableInteger(value.effective_backtest_draw_count) &&
    nullableInteger(value.successful_observation_count) &&
    nullableInteger(value.window_available_draws) &&
    nullableInteger(value.window_requested_draws) &&
    nullableBoolean(value.window_complete) &&
    nullableString(value.native_ticket_count_classification) &&
    nullableString(value.authority_mode) &&
    isSha256(value.catalog_sha256) &&
    (value.official_rank === undefined || value.official_rank === null)
  )
}

function isOfficialPrizeCounts(value: unknown): boolean {
  return (
    isRecord(value) &&
    isInteger(value.first) &&
    isInteger(value.second) &&
    isInteger(value.third) &&
    isInteger(value.fourth) &&
    isInteger(value.fifth) &&
    isInteger(value.sixth) &&
    isInteger(value.seventh) &&
    isInteger(value.general)
  )
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isInteger(value: unknown): value is number {
  return Number.isInteger(value) && Number(value) >= 0
}

function isString(value: unknown): value is string {
  return typeof value === 'string'
}

function isSha256(value: unknown): value is string {
  return typeof value === 'string' && SHA256_PATTERN.test(value)
}

function isExactNumberArray(
  value: unknown,
  expected: readonly number[],
): boolean {
  return (
    Array.isArray(value) &&
    value.length === expected.length &&
    expected.every((item, index) => value[index] === item)
  )
}

function isExactStringArray(
  value: unknown,
  expected: readonly string[],
): boolean {
  return (
    Array.isArray(value) &&
    value.length === expected.length &&
    expected.every((item, index) => value[index] === item)
  )
}
