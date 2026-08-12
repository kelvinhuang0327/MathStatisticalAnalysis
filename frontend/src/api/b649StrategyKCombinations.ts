import type { components, paths } from './generated/openapi'

export type B649StrategyKSummary =
  paths['/api/v1/b649-strategy-k-combinations/strategy-k/summary']['get']['responses'][200]['content']['application/json']
export type B649StrategyKPage =
  paths['/api/v1/b649-strategy-k-combinations/strategy-k']['get']['responses'][200]['content']['application/json']
export type B649StrategyKRecord = B649StrategyKPage['items'][number]
export type B649CombinationSummary =
  paths['/api/v1/b649-strategy-k-combinations/combinations/summary']['get']['responses'][200]['content']['application/json']
export type B649CombinationPage =
  paths['/api/v1/b649-strategy-k-combinations/combinations']['get']['responses'][200]['content']['application/json']
export type B649CombinationRecord = B649CombinationPage['items'][number]
export type B649EvidenceStatus =
  paths['/api/v1/b649-strategy-k-combinations/evidence-status']['get']['responses'][200]['content']['application/json']
export type B649StrategyKCriterion = components['schemas']['B649StrategyKCriterion']
export type B649StrategyKWindowKind = components['schemas']['B649StrategyKWindowKind']
export type B649StrategyKSort = components['schemas']['B649StrategyKSort']
export type B649CombinationCriterion = components['schemas']['B649CombinationCriterion']
export type B649CombinationWindow = components['schemas']['B649CombinationWindow']
export type B649CombinationProxyMode = components['schemas']['B649CombinationProxyMode']
export type B649CombinationSort = components['schemas']['B649CombinationSort']
export type B649StrategyAvailability = components['schemas']['B649StrategyAvailability']

export interface B649StrategyKQuery {
  requestedK: number
  windowKind: B649StrategyKWindowKind
  criterion: B649StrategyKCriterion
  q?: string
  sort: B649StrategyKSort
  limit: number
  offset: number
}

export interface B649CombinationQuery {
  proxyMode: B649CombinationProxyMode
  memberCount: 2 | 3
  window: B649CombinationWindow
  criterion: B649CombinationCriterion
  memberSearch?: string
  sort: B649CombinationSort
  limit: number
  offset: number
}

export type B649AnalyticsErrorKind =
  | 'UNAVAILABLE'
  | 'INVALID_REQUEST'
  | 'MALFORMED_RESPONSE'
  | 'NETWORK'

export class B649AnalyticsRequestError extends Error {
  readonly status: number
  readonly kind: B649AnalyticsErrorKind
  readonly errorCode: string | null

  constructor(
    message: string,
    status: number,
    kind: B649AnalyticsErrorKind,
    errorCode: string | null = null,
  ) {
    super(message)
    this.name = 'B649AnalyticsRequestError'
    this.status = status
    this.kind = kind
    this.errorCode = errorCode
  }
}

const ROOT = '/api/v1/b649-strategy-k-combinations'

export function fetchB649StrategyKSummary(signal?: AbortSignal): Promise<B649StrategyKSummary> {
  return requestJson(`${ROOT}/strategy-k/summary`, isStrategySummary, signal)
}

export function fetchB649StrategyK(
  query: B649StrategyKQuery,
  signal?: AbortSignal,
): Promise<B649StrategyKPage> {
  const parameters = new URLSearchParams({
    requested_k: String(query.requestedK),
    window_kind: query.windowKind,
    criterion: query.criterion,
    sort: query.sort,
    limit: String(query.limit),
    offset: String(query.offset),
  })
  if (query.q) parameters.set('q', query.q)
  return requestJson(`${ROOT}/strategy-k?${parameters}`, isStrategyPage, signal)
}

export function fetchB649CombinationSummary(
  signal?: AbortSignal,
): Promise<B649CombinationSummary> {
  return requestJson(`${ROOT}/combinations/summary`, isCombinationSummary, signal)
}

export function fetchB649Combinations(
  query: B649CombinationQuery,
  signal?: AbortSignal,
): Promise<B649CombinationPage> {
  const parameters = new URLSearchParams({
    proxy_mode: query.proxyMode,
    member_count: String(query.memberCount),
    window: query.window,
    criterion: query.criterion,
    sort: query.sort,
    limit: String(query.limit),
    offset: String(query.offset),
  })
  if (query.memberSearch) parameters.set('member_search', query.memberSearch)
  return requestJson(`${ROOT}/combinations?${parameters}`, isCombinationPage, signal)
}

export function fetchB649EvidenceStatus(signal?: AbortSignal): Promise<B649EvidenceStatus> {
  return requestJson(`${ROOT}/evidence-status`, isEvidenceStatus, signal)
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
    throw new B649AnalyticsRequestError('Network request failed.', 0, 'NETWORK')
  }
  let payload: unknown
  try {
    payload = await response.json()
  } catch {
    throw new B649AnalyticsRequestError(
      'The server returned invalid JSON.',
      response.status,
      'MALFORMED_RESPONSE',
    )
  }
  if (!response.ok) {
    const errorCode = isRecord(payload) && isString(payload.error_code) ? payload.error_code : null
    const message =
      isRecord(payload) && isString(payload.message) ? payload.message : 'The request failed.'
    throw new B649AnalyticsRequestError(
      message,
      response.status,
      response.status === 503 ? 'UNAVAILABLE' : 'INVALID_REQUEST',
      errorCode,
    )
  }
  if (!validate(payload)) {
    throw new B649AnalyticsRequestError(
      'The server response did not match the sealed B649 analytics contract.',
      response.status,
      'MALFORMED_RESPONSE',
    )
  }
  return payload
}

function isStrategySummary(value: unknown): value is B649StrategyKSummary {
  return (
    isRecord(value) &&
    isSha256(value.authority_task_tree) &&
    isSha256(value.authority_full_output_tree) &&
    isNonnegativeInteger(value.matrix_row_count) &&
    isPositiveIntegerArray(value.supported_k_values) &&
    isStringArray(value.supported_criteria) &&
    Array.isArray(value.windows) &&
    value.windows.every(isWindowOption) &&
    Array.isArray(value.strategies) &&
    value.strategies.every(isStrategyAvailability) &&
    isNonnegativeInteger(value.current_executable_strategy_count) &&
    isNonnegativeInteger(value.matrix_available_strategy_count) &&
    isNonnegativeInteger(value.matrix_unavailable_strategy_count) &&
    value.current_executable_strategy_count === value.strategies.length &&
    value.matrix_available_strategy_count + value.matrix_unavailable_strategy_count ===
      value.current_executable_strategy_count &&
    isNonnegativeInteger(value.historical_accounted_identity_count) &&
    value.measurement_mode === 'CANDIDATE_COVERAGE' &&
    isString(value.window_policy_version) &&
    isString(value.duplicate_handling_policy) &&
    value.nested_windows_independent === false &&
    value.predictive_advantage_claimed === false &&
    isString(value.research_disclaimer)
  )
}

function isStrategyPage(value: unknown): value is B649StrategyKPage {
  return (
    isRecord(value) &&
    Array.isArray(value.items) &&
    value.items.every(isStrategyRecord) &&
    isPage(value) &&
    isNonnegativeInteger(value.requested_k) &&
    isString(value.window_kind) &&
    isString(value.window_role) &&
    isString(value.criterion) &&
    isString(value.sort) &&
    isString(value.ranking_label) &&
    value.measurement_mode === 'CANDIDATE_COVERAGE' &&
    isString(value.research_disclaimer)
  )
}

function isStrategyRecord(value: unknown): boolean {
  return (
    isRecord(value) &&
    isString(value.strategy_id) &&
    isString(value.strategy_version) &&
    isNonnegativeInteger(value.requested_k) &&
    Array.isArray(value.effective_unique_k_counts) &&
    value.effective_unique_k_counts.every(
      (item) =>
        isRecord(item) &&
        isNonnegativeInteger(item.effective_unique_k) &&
        isNonnegativeInteger(item.observation_count),
    ) &&
    isString(value.criterion) &&
    isString(value.window_kind) &&
    isString(value.window_role) &&
    (value.requested_draw_count === null || isNonnegativeInteger(value.requested_draw_count)) &&
    isNonnegativeInteger(value.source_observation_count) &&
    isNonnegativeInteger(value.eligible_observation_count) &&
    isNonnegativeInteger(value.excluded_observation_count) &&
    isExactFraction(value.success_numerator, value.success_denominator) &&
    isExactFraction(value.random_baseline_numerator, value.random_baseline_denominator) &&
    isString(value.observed_minus_baseline) &&
    isString(value.first_target_draw) &&
    isString(value.last_target_draw) &&
    isString(value.evaluation_status) &&
    value.measurement_mode === 'CANDIDATE_COVERAGE' &&
    isString(value.window_policy_version) &&
    value.nested_windows_independent === false
  )
}

function isCombinationSummary(value: unknown): value is B649CombinationSummary {
  return (
    isRecord(value) &&
    isSha256(value.authority_task_tree) &&
    isNonnegativeInteger(value.sealed_top_candidate_count) &&
    Array.isArray(value.proxy_modes) &&
    value.proxy_modes.every(
      (item) => isRecord(item) && isString(item.proxy_mode) && isString(item.proxy_label),
    ) &&
    Array.isArray(value.member_counts) &&
    value.member_counts.every((item) => item === 2 || item === 3) &&
    Array.isArray(value.windows) &&
    value.windows.every(isWindowOption) &&
    isStringArray(value.supported_criteria) &&
    isString(value.source_scope) &&
    value.full_projection_sent_to_browser === false &&
    value.predictive_advantage_claimed === false &&
    isString(value.research_disclaimer)
  )
}

function isCombinationPage(value: unknown): value is B649CombinationPage {
  return (
    isRecord(value) &&
    Array.isArray(value.items) &&
    value.items.every(isCombinationRecord) &&
    isPage(value) &&
    isString(value.proxy_mode) &&
    (value.member_count === 2 || value.member_count === 3) &&
    isString(value.window) &&
    isString(value.window_role) &&
    isString(value.criterion) &&
    isString(value.sort) &&
    isString(value.ranking_label) &&
    isString(value.source_scope) &&
    isString(value.research_disclaimer)
  )
}

function isCombinationRecord(value: unknown): boolean {
  const nullableString = (item: unknown) => item === null || isString(item)
  return (
    isRecord(value) &&
    isString(value.proxy_mode) &&
    isString(value.proxy_label) &&
    (value.member_count === 2 || value.member_count === 3) &&
    isStringArray(value.member_strategy_ids) &&
    value.member_strategy_ids.length === value.member_count &&
    isString(value.combination_id) &&
    isString(value.evaluation_window) &&
    isString(value.criterion) &&
    isNonnegativeInteger(value.sealed_rank) &&
    isNonnegativeInteger(value.eligible_draws) &&
    isExactFraction(value.success_numerator, value.success_denominator) &&
    isExactFraction(
      value.exact_random_baseline_numerator,
      value.exact_random_baseline_denominator,
    ) &&
    isDecimal(value.observed_rate) &&
    isDecimal(value.random_baseline_rate) &&
    isDecimal(value.descriptive_delta) &&
    isString(value.evaluation_status) &&
    isString(value.evaluation_reason) &&
    nullableString(value.long_delta_sign) &&
    nullableString(value.mid_delta_sign) &&
    nullableString(value.short_delta_sign) &&
    isNonnegativeInteger(value.positive_window_count) &&
    nullableString(value.minimum_delta) &&
    nullableString(value.delta_range) &&
    typeof value.cross_window_stable_positive === 'boolean' &&
    value.historical_search_only === true &&
    value.predictive_advantage_claimed === false &&
    value.prospective_validation_required === true &&
    isString(value.candidate_disposition)
  )
}

function isEvidenceStatus(value: unknown): value is B649EvidenceStatus {
  return (
    isRecord(value) &&
    isSha256(value.observer_task_tree) &&
    value.historical_evidence_status === 'AVAILABLE' &&
    isNonnegativeInteger(value.pre_freeze_date_unseen_holdout_count) &&
    isNonnegativeInteger(value.post_freeze_date_prospective_count) &&
    isNonnegativeInteger(value.observation_count) &&
    isString(value.observation_start_draw) &&
    (value.latest_observed_draw === null || isString(value.latest_observed_draw)) &&
    isPositiveIntegerArray(value.checkpoints) &&
    isPositiveIntegerArray(value.checkpoints_reached) &&
    isString(value.primary_outcome) &&
    isString(value.c_forward_status) &&
    isString(value.c_forward_reason) &&
    value.holdout_used_to_rerank_historical_results === false &&
    value.predictive_advantage_claimed === false
  )
}

function isStrategyAvailability(value: unknown): boolean {
  return (
    isRecord(value) &&
    isString(value.strategy_id) &&
    isString(value.strategy_version) &&
    (value.availability === 'MATRIX_AVAILABLE' ||
      value.availability === 'PORTFOLIO_ORDER_AGGREGATION_NOT_DEFINED') &&
    isString(value.availability_reason) &&
    isString(value.response_shape) &&
    isNonnegativeInteger(value.native_ticket_count)
  )
}

function isWindowOption(value: unknown): boolean {
  return (
    isRecord(value) &&
    isString(value.window_kind) &&
    isString(value.window_role) &&
    (value.requested_draw_count === null || isNonnegativeInteger(value.requested_draw_count)) &&
    typeof value.default_emphasis === 'boolean'
  )
}

function isPage(value: Record<string, unknown>): boolean {
  return (
    isNonnegativeInteger(value.total) &&
    isNonnegativeInteger(value.limit) &&
    isNonnegativeInteger(value.offset)
  )
}

function isExactFraction(numerator: unknown, denominator: unknown): boolean {
  return (
    isNonnegativeInteger(numerator) &&
    isNonnegativeInteger(denominator) &&
    denominator > 0 &&
    numerator <= denominator
  )
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isString(value: unknown): value is string {
  return typeof value === 'string' && value.length > 0
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every(isString)
}

function isNonnegativeInteger(value: unknown): value is number {
  return Number.isInteger(value) && Number(value) >= 0
}

function isPositiveIntegerArray(value: unknown): value is number[] {
  return Array.isArray(value) && value.every((item) => isNonnegativeInteger(item) && item > 0)
}

function isSha256(value: unknown): value is string {
  return typeof value === 'string' && /^[0-9a-f]{64}$/.test(value)
}

function isDecimal(value: unknown): value is string {
  return typeof value === 'string' && /^-?[0-9]+\.[0-9]+$/.test(value)
}
