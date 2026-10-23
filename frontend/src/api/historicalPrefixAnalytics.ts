import type { components, paths } from './generated/openapi'

const RANKINGS_PATH = '/api/v1/historical-prefix-analytics/rankings'
const STRATEGIES_PATH = '/api/v1/historical-prefix-analytics/strategies'
const REPLAY_PATH =
  '/api/v1/historical-prefix-analytics/strategies/{strategy_id}/{strategy_version}/{replicate}/replay'

export type HistoricalPrefixAnalyticsRankingsResponse =
  paths[typeof RANKINGS_PATH]['get']['responses'][200]['content']['application/json']
export type HistoricalPrefixAnalyticsRankingGroup =
  HistoricalPrefixAnalyticsRankingsResponse['groups'][number]
export type HistoricalPrefixAnalyticsRankingCandidate =
  HistoricalPrefixAnalyticsRankingGroup['candidates'][number]
export type HistoricalPrefixAnalyticsOverviewResponse =
  paths[typeof STRATEGIES_PATH]['get']['responses'][200]['content']['application/json']
export type HistoricalPrefixAnalyticsStrategySummary =
  HistoricalPrefixAnalyticsOverviewResponse['summaries'][number]
export type HistoricalPrefixAnalyticsMetadata =
  HistoricalPrefixAnalyticsRankingsResponse['metadata']
export type HistoricalPrefixAnalyticsStrategyIdentity =
  components['schemas']['HistoricalPrefixStrategyIdentityView']
export type HistoricalPrefixAnalyticsExactRatio = components['schemas']['ExactRatioView']
export type HistoricalPrefixAnalyticsReplayResponse =
  paths[typeof REPLAY_PATH]['get']['responses'][200]['content']['application/json']
export type HistoricalPrefixAnalyticsReplayItem =
  HistoricalPrefixAnalyticsReplayResponse['items'][number]
export type HistoricalPrefixAnalyticsOverviewPrefixCount =
  paths[typeof STRATEGIES_PATH]['get']['parameters']['query']['prefix_count']
export type HistoricalPrefixAnalyticsReplayQuery =
  paths[typeof REPLAY_PATH]['get']['parameters']['query']
export type HistoricalPrefixAnalyticsReplayPrefixCount =
  HistoricalPrefixAnalyticsReplayQuery['prefix_count']

export const HISTORICAL_PREFIX_ANALYTICS_OVERVIEW_PREFIX_COUNTS = [
  10,
  15,
  20,
] as const satisfies readonly HistoricalPrefixAnalyticsOverviewPrefixCount[]

export const HISTORICAL_PREFIX_ANALYTICS_REPLAY_PREFIX_COUNTS = [
  1,
  2,
  3,
  4,
  5,
  10,
  15,
  20,
] as const satisfies readonly HistoricalPrefixAnalyticsReplayPrefixCount[]

export class HistoricalPrefixAnalyticsRequestError extends Error {
  readonly status: number
  readonly errorCode: string | null

  constructor(message: string, status: number, errorCode: string | null = null) {
    super(message)
    this.name = 'HistoricalPrefixAnalyticsRequestError'
    this.status = status
    this.errorCode = errorCode
  }
}

export interface HistoricalPrefixAnalyticsRankingsOptions {
  top_k?: paths[typeof RANKINGS_PATH]['get']['parameters']['query']['top_k']
}

export async function getHistoricalPrefixAnalyticsRankings(
  signal?: AbortSignal,
  options: HistoricalPrefixAnalyticsRankingsOptions = {},
): Promise<HistoricalPrefixAnalyticsRankingsResponse> {
  const query = new URLSearchParams()
  if (options.top_k !== undefined) query.set('top_k', String(options.top_k))
  const suffix = query.size > 0 ? `?${query.toString()}` : ''
  return requestJson(
    `${RANKINGS_PATH}${suffix}`,
    'Prefix rankings',
    isRankingsResponse,
    signal,
  )
}

export async function getHistoricalPrefixAnalyticsStrategies(
  prefixCount: HistoricalPrefixAnalyticsOverviewPrefixCount,
  signal?: AbortSignal,
): Promise<HistoricalPrefixAnalyticsOverviewResponse> {
  const query = new URLSearchParams({ prefix_count: String(prefixCount) })
  return requestJson(
    `${STRATEGIES_PATH}?${query.toString()}`,
    'Prefix strategy overview',
    isOverviewResponse,
    signal,
  )
}

export async function getHistoricalPrefixAnalyticsReplay(
  strategy: Pick<
    HistoricalPrefixAnalyticsStrategyIdentity,
    'strategy_id' | 'strategy_version' | 'replicate'
  >,
  query: HistoricalPrefixAnalyticsReplayQuery,
  signal?: AbortSignal,
): Promise<HistoricalPrefixAnalyticsReplayResponse> {
  const path = [
    '/api/v1/historical-prefix-analytics/strategies',
    encodeURIComponent(strategy.strategy_id),
    encodeURIComponent(strategy.strategy_version),
    String(strategy.replicate),
    'replay',
  ].join('/')
  const parameters = new URLSearchParams({ prefix_count: String(query.prefix_count) })
  if (query.limit !== undefined) parameters.set('limit', String(query.limit))
  if (query.offset !== undefined) parameters.set('offset', String(query.offset))
  return requestJson(
    `${path}?${parameters.toString()}`,
    'Prefix strategy replay',
    isReplayResponse,
    signal,
  )
}

async function requestJson<T>(
  url: string,
  label: string,
  validate: (value: unknown) => value is T,
  signal?: AbortSignal,
): Promise<T> {
  const response = await fetch(url, {
    method: 'GET',
    headers: { Accept: 'application/json' },
    signal,
  })

  let payload: unknown = null
  try {
    payload = await response.json()
  } catch {
    if (response.ok) {
      throw new HistoricalPrefixAnalyticsRequestError(
        `${label} returned invalid JSON`,
        502,
      )
    }
  }

  if (!response.ok) {
    const error = isRecord(payload) ? payload : {}
    throw new HistoricalPrefixAnalyticsRequestError(
      typeof error.message === 'string'
        ? error.message
        : `${label} request failed with HTTP ${response.status}`,
      response.status,
      typeof error.error_code === 'string' ? error.error_code : null,
    )
  }

  if (!validate(payload)) {
    throw new HistoricalPrefixAnalyticsRequestError(
      `${label} returned a response that does not match the OpenAPI contract`,
      502,
    )
  }
  return payload
}

function isRankingsResponse(value: unknown): value is HistoricalPrefixAnalyticsRankingsResponse {
  return (
    isRecord(value) &&
    isMetadata(value.metadata) &&
    isNonNegativeInteger(value.top_k) &&
    Array.isArray(value.groups) &&
    value.groups.every(
      (group) =>
        isRecord(group) &&
        isNonNegativeInteger(group.prefix_count) &&
        typeof group.status === 'string' &&
        isNonNegativeInteger(group.total_candidate_count) &&
        isNonNegativeInteger(group.requested_top_k) &&
        Array.isArray(group.candidates) &&
        group.candidates.every(
          (candidate) =>
            isRecord(candidate) &&
            isNonNegativeInteger(candidate.rank) &&
            isStrategyIdentity(candidate.identity) &&
            isStrategySummary(candidate.summary) &&
            Array.isArray(candidate.tie_break_provenance) &&
            candidate.tie_break_provenance.every((item) => typeof item === 'string'),
        ),
    )
  )
}

function isOverviewResponse(value: unknown): value is HistoricalPrefixAnalyticsOverviewResponse {
  return (
    isRecord(value) &&
    isMetadata(value.metadata) &&
    isOverviewPrefixCount(value.prefix_count) &&
    isNonNegativeInteger(value.total_count) &&
    Array.isArray(value.summaries) &&
    value.summaries.every(isStrategySummary)
  )
}

function isReplayResponse(value: unknown): value is HistoricalPrefixAnalyticsReplayResponse {
  return (
    isRecord(value) &&
    isMetadata(value.metadata) &&
    isStrategyIdentity(value.strategy) &&
    isReplayPrefixCount(value.prefix_count) &&
    isNonNegativeInteger(value.total_count) &&
    isNonNegativeInteger(value.limit) &&
    isNonNegativeInteger(value.offset) &&
    Array.isArray(value.items) &&
    value.items.every(isReplayItem)
  )
}

function isStrategySummary(value: unknown): value is HistoricalPrefixAnalyticsStrategySummary {
  return (
    isRecord(value) &&
    isStrategyIdentity(value.identity) &&
    isNonNegativeInteger(value.prefix_count) &&
    typeof value.status === 'string' &&
    isNonNegativeInteger(value.distinct_draw_count) &&
    isNonNegativeInteger(value.replay_ticket_count) &&
    isNonNegativeInteger(value.portfolio_success_count) &&
    isExactRatio(value.portfolio_success_rate) &&
    typeof value.ranking_eligible === 'boolean' &&
    (value.ranking_exclusion_reason === null ||
      typeof value.ranking_exclusion_reason === 'string')
  )
}

function isReplayItem(value: unknown): value is HistoricalPrefixAnalyticsReplayItem {
  return (
    isRecord(value) &&
    isStrategyIdentity(value.identity) &&
    isReplayPrefixCount(value.prefix_count) &&
    isNonNegativeInteger(value.prefix_ticket_count) &&
    Array.isArray(value.included_ticket_positions) &&
    value.included_ticket_positions.every(isNonNegativeInteger) &&
    isNonNegativeInteger(value.best_single_main_hit_count) &&
    isNonNegativeInteger(value.best_single_ticket_position) &&
    isNonNegativeInteger(value.total_main_hit_count) &&
    typeof value.portfolio_success === 'boolean' &&
    typeof value.m3plus === 'boolean' &&
    typeof value.m4plus === 'boolean' &&
    typeof value.m5plus === 'boolean' &&
    typeof value.m6 === 'boolean' &&
    typeof value.special_hit === 'boolean' &&
    isDrawIdentity(value.target) &&
    isDrawIdentity(value.cutoff)
  )
}

function isMetadata(value: unknown): value is HistoricalPrefixAnalyticsMetadata {
  return (
    isRecord(value) &&
    typeof value.result_schema_version === 'string' &&
    typeof value.source_import_identity_sha256 === 'string' &&
    typeof value.source_manifest_sha256 === 'string' &&
    typeof value.source_artifact_sha256 === 'string' &&
    typeof value.dataset_identity === 'string' &&
    typeof value.dataset_sha256 === 'string' &&
    typeof value.lottery_type === 'string' &&
    typeof value.ranking_policy_id === 'string' &&
    typeof value.historical_only_disclaimer_id === 'string'
  )
}

function isStrategyIdentity(value: unknown): value is HistoricalPrefixAnalyticsStrategyIdentity {
  return (
    isRecord(value) &&
    typeof value.strategy_id === 'string' &&
    typeof value.effective_strategy_id === 'string' &&
    typeof value.strategy_version === 'string' &&
    isNonNegativeInteger(value.replicate) &&
    typeof value.identity_kind === 'string' &&
    typeof value.governance_status === 'string' &&
    (value.alias_of_strategy_id === null || typeof value.alias_of_strategy_id === 'string') &&
    (value.equivalence_group === null || typeof value.equivalence_group === 'string') &&
    typeof value.nested_prefix_supported === 'boolean'
  )
}

function isExactRatio(value: unknown): value is HistoricalPrefixAnalyticsExactRatio {
  return (
    isRecord(value) &&
    isNonNegativeInteger(value.numerator) &&
    isNonNegativeInteger(value.denominator) &&
    typeof value.is_available === 'boolean'
  )
}

function isDrawIdentity(value: unknown): boolean {
  return (
    isRecord(value) &&
    isNonNegativeInteger(value.draw_number) &&
    typeof value.draw_date === 'string' &&
    typeof value.draw_sha256 === 'string'
  )
}

function isOverviewPrefixCount(value: unknown): value is HistoricalPrefixAnalyticsOverviewPrefixCount {
  return HISTORICAL_PREFIX_ANALYTICS_OVERVIEW_PREFIX_COUNTS.some((count) => count === value)
}

function isReplayPrefixCount(value: unknown): value is HistoricalPrefixAnalyticsReplayPrefixCount {
  return HISTORICAL_PREFIX_ANALYTICS_REPLAY_PREFIX_COUNTS.some((count) => count === value)
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isNonNegativeInteger(value: unknown): value is number {
  return typeof value === 'number' && Number.isInteger(value) && value >= 0
}
