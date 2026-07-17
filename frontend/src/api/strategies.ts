import type { components, paths } from './generated/openapi'

export type StrategyListResponse =
  paths['/api/v1/strategies']['get']['responses'][200]['content']['application/json']
export type StrategyView = StrategyListResponse[number]
export type StrategyOverviewResponse =
  paths['/api/v1/strategy-overview']['get']['responses'][200]['content']['application/json']
export type StrategyOverviewItem = StrategyOverviewResponse['items'][number]
export type LotteryType = components['schemas']['LotteryType']
export type LifecycleStatus = components['schemas']['LifecycleStatus']

export interface StrategyOverviewFilters {
  q?: string
  lottery_type?: LotteryType
  lifecycle_status?: LifecycleStatus
  executable?: boolean
}

const STRATEGY_CATALOG_ENDPOINT = '/api/v1/strategies'
const STRATEGY_OVERVIEW_ENDPOINT = '/api/v1/strategy-overview'
export const LIFECYCLE_STATUSES = [
  'IDEA',
  'OBSERVATION',
  'ONLINE',
  'REJECTED',
  'RETIRED',
] as const satisfies readonly LifecycleStatus[]
export const LOTTERY_TYPES = [
  'DAILY_539',
  'BIG_LOTTO',
  'POWER_LOTTO',
] as const satisfies readonly LotteryType[]
const LIFECYCLE_STATUS_SET = new Set<string>(LIFECYCLE_STATUSES)
const LOTTERY_TYPE_SET = new Set<string>(LOTTERY_TYPES)
const EVIDENCE_REASON = 'NO_CANONICAL_STRATEGY_EVALUATION_EVIDENCE'

function isNonBlankString(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 0
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isNonNegativeInteger(value: unknown): value is number {
  return typeof value === 'number' && Number.isInteger(value) && value >= 0
}

function isStrategyView(value: unknown): value is StrategyView {
  if (!isRecord(value)) return false
  const record = value
  return (
    isNonBlankString(record.strategy_id) &&
    isNonBlankString(record.display_name) &&
    isNonBlankString(record.version) &&
    Array.isArray(record.supported_lottery_types) &&
    record.supported_lottery_types.length > 0 &&
    record.supported_lottery_types.every(
      (lotteryType) => typeof lotteryType === 'string' && LOTTERY_TYPE_SET.has(lotteryType),
    ) &&
    typeof record.minimum_history === 'number' &&
    Number.isInteger(record.minimum_history) &&
    record.minimum_history >= 1 &&
    typeof record.lifecycle_status === 'string' &&
    LIFECYCLE_STATUS_SET.has(record.lifecycle_status) &&
    typeof record.executable === 'boolean'
  )
}

function isCountRecord(value: unknown, expectedKeys: readonly string[]): boolean {
  if (!isRecord(value)) return false
  const actualKeys = Object.keys(value)
  return (
    actualKeys.length === expectedKeys.length &&
    expectedKeys.every((key) => isNonNegativeInteger(value[key]))
  )
}

function isStrategyOverviewItem(value: unknown): value is StrategyOverviewItem {
  if (!isStrategyView(value)) return false
  const record = value as unknown as Record<string, unknown>
  return (
    Array.isArray(record.provenance) &&
    record.provenance.every(isNonBlankString) &&
    value.executable === (value.lifecycle_status === 'ONLINE')
  )
}

function hasValidSummary(
  value: unknown,
  items: readonly StrategyOverviewItem[],
): boolean {
  if (!isRecord(value)) return false
  if (
    !isNonNegativeInteger(value.total) ||
    !isNonNegativeInteger(value.executable_count) ||
    !isNonNegativeInteger(value.metadata_only_count) ||
    !isCountRecord(value.lifecycle_counts, LIFECYCLE_STATUSES) ||
    !isCountRecord(value.lottery_type_counts, LOTTERY_TYPES)
  ) {
    return false
  }

  const lifecycleCounts = value.lifecycle_counts as Record<string, number>
  const lotteryTypeCounts = value.lottery_type_counts as Record<string, number>
  const executableCount = items.filter((item) => item.executable).length
  return (
    value.total === items.length &&
    value.executable_count === executableCount &&
    value.metadata_only_count === items.length - executableCount &&
    LIFECYCLE_STATUSES.every(
      (status) =>
        lifecycleCounts[status] === items.filter((item) => item.lifecycle_status === status).length,
    ) &&
    LOTTERY_TYPES.every(
      (lotteryType) =>
        lotteryTypeCounts[lotteryType] ===
        items.filter((item) => item.supported_lottery_types.includes(lotteryType)).length,
    )
  )
}

function hasUnavailableEvidenceCapabilities(value: unknown): boolean {
  if (!isRecord(value)) return false
  return (
    value.evaluation_metrics_available === false &&
    value.d3_status_available === false &&
    value.best_strategy_ranking_available === false &&
    Array.isArray(value.unavailable_reason_codes) &&
    value.unavailable_reason_codes.length === 1 &&
    value.unavailable_reason_codes[0] === EVIDENCE_REASON
  )
}

function isStrategyOverviewResponse(value: unknown): value is StrategyOverviewResponse {
  if (!isRecord(value) || !Array.isArray(value.items)) return false
  if (!value.items.every(isStrategyOverviewItem)) return false
  return (
    hasValidSummary(value.summary, value.items) &&
    hasUnavailableEvidenceCapabilities(value.capabilities)
  )
}

export class StrategyCatalogRequestError extends Error {
  readonly status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'StrategyCatalogRequestError'
    this.status = status
  }
}

export class StrategyOverviewRequestError extends Error {
  readonly status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'StrategyOverviewRequestError'
    this.status = status
  }
}

function strategyOverviewUrl(filters: StrategyOverviewFilters): string {
  const parameters = new URLSearchParams()
  const query = filters.q?.trim()
  if (query) parameters.set('q', query)
  if (filters.lottery_type) parameters.set('lottery_type', filters.lottery_type)
  if (filters.lifecycle_status) parameters.set('lifecycle_status', filters.lifecycle_status)
  if (filters.executable !== undefined) {
    parameters.set('executable', String(filters.executable))
  }
  const queryString = parameters.toString()
  return queryString ? `${STRATEGY_OVERVIEW_ENDPOINT}?${queryString}` : STRATEGY_OVERVIEW_ENDPOINT
}

export async function queryStrategyOverview(
  filters: StrategyOverviewFilters = {},
  signal?: AbortSignal,
): Promise<StrategyOverviewResponse> {
  const response = await fetch(strategyOverviewUrl(filters), {
    method: 'GET',
    headers: { Accept: 'application/json' },
    signal,
  })
  if (!response.ok) {
    throw new StrategyOverviewRequestError(
      `Strategy Overview request failed with HTTP ${response.status}`,
      response.status,
    )
  }
  const payload: unknown = await response.json()
  if (!isStrategyOverviewResponse(payload)) {
    throw new StrategyOverviewRequestError(
      'Strategy Overview returned an invalid response contract',
      502,
    )
  }
  return payload
}

export async function listStrategies(signal?: AbortSignal): Promise<StrategyListResponse> {
  const response = await fetch(STRATEGY_CATALOG_ENDPOINT, {
    method: 'GET',
    headers: { Accept: 'application/json' },
    signal,
  })
  if (!response.ok) {
    throw new StrategyCatalogRequestError(
      `Strategy Catalog request failed with HTTP ${response.status}`,
      response.status,
    )
  }
  const payload: unknown = await response.json()
  if (!Array.isArray(payload)) {
    throw new StrategyCatalogRequestError('Strategy Catalog returned a non-list payload', 502)
  }
  const invalidIndex = payload.findIndex((strategy) => !isStrategyView(strategy))
  if (invalidIndex !== -1) {
    throw new StrategyCatalogRequestError(
      `Strategy Catalog returned an invalid record at index ${invalidIndex}`,
      502,
    )
  }
  return payload as StrategyListResponse
}
