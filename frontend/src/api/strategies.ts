import type { paths } from './generated/openapi'

export type StrategyListResponse =
  paths['/api/v1/strategies']['get']['responses'][200]['content']['application/json']
export type StrategyView = StrategyListResponse[number]

const STRATEGY_CATALOG_ENDPOINT = '/api/v1/strategies'
const LIFECYCLE_STATUSES = new Set([
  'IDEA',
  'OBSERVATION',
  'ONLINE',
  'REJECTED',
  'RETIRED',
])
const LOTTERY_TYPES = new Set(['DAILY_539', 'BIG_LOTTO', 'POWER_LOTTO'])

function isNonBlankString(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 0
}

function isStrategyView(value: unknown): value is StrategyView {
  if (typeof value !== 'object' || value === null) return false
  const record = value as Record<string, unknown>
  return (
    isNonBlankString(record.strategy_id) &&
    isNonBlankString(record.display_name) &&
    isNonBlankString(record.version) &&
    Array.isArray(record.supported_lottery_types) &&
    record.supported_lottery_types.length > 0 &&
    record.supported_lottery_types.every(
      (lotteryType) => typeof lotteryType === 'string' && LOTTERY_TYPES.has(lotteryType),
    ) &&
    typeof record.minimum_history === 'number' &&
    Number.isInteger(record.minimum_history) &&
    record.minimum_history >= 1 &&
    typeof record.lifecycle_status === 'string' &&
    LIFECYCLE_STATUSES.has(record.lifecycle_status) &&
    typeof record.executable === 'boolean'
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
