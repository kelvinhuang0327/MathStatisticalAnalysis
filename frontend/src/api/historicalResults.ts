import type { paths } from './generated/openapi'

export type TicketCountFilter = 10 | 15 | 20

export type HistoricalStrategySummaryListResponse =
  paths['/api/v1/historical-results/runs/{run_id}/strategies']['get']['responses'][200]['content']['application/json']
export type HistoricalStrategySummaryView = HistoricalStrategySummaryListResponse['items'][number]

export type HistoricalReplayPageResponse =
  paths['/api/v1/historical-results/runs/{run_id}/replay']['get']['responses'][200]['content']['application/json']
export type HistoricalPortfolioView = HistoricalReplayPageResponse['items'][number]

export interface HistoricalReplayQuery {
  strategyId: string
  ticketCount: TicketCountFilter
  m4plusOnly?: boolean
  limit?: number
  offset?: number
}

export class HistoricalResultsRequestError extends Error {
  readonly status: number
  readonly errorCode: string | undefined

  constructor(message: string, status: number, errorCode?: string) {
    super(message)
    this.name = 'HistoricalResultsRequestError'
    this.status = status
    this.errorCode = errorCode
  }
}

export async function listHistoricalRunStrategies(
  runId: string,
  ticketCount: TicketCountFilter,
  signal?: AbortSignal,
): Promise<HistoricalStrategySummaryListResponse> {
  const parameters = new URLSearchParams({ ticket_count: String(ticketCount) })
  const response = await fetch(
    `/api/v1/historical-results/runs/${encodeURIComponent(runId)}/strategies?${parameters.toString()}`,
    { method: 'GET', headers: { Accept: 'application/json' }, signal },
  )
  return parseResponse(response, isHistoricalStrategySummaryListResponse, 'strategies')
}

export async function listHistoricalRunReplayPortfolios(
  runId: string,
  query: HistoricalReplayQuery,
  signal?: AbortSignal,
): Promise<HistoricalReplayPageResponse> {
  const parameters = new URLSearchParams({
    strategy_id: query.strategyId,
    ticket_count: String(query.ticketCount),
  })
  if (query.m4plusOnly) parameters.set('m4plus_only', 'true')
  if (query.limit !== undefined) parameters.set('limit', String(query.limit))
  if (query.offset !== undefined) parameters.set('offset', String(query.offset))
  const response = await fetch(
    `/api/v1/historical-results/runs/${encodeURIComponent(runId)}/replay?${parameters.toString()}`,
    { method: 'GET', headers: { Accept: 'application/json' }, signal },
  )
  return parseResponse(response, isHistoricalReplayPageResponse, 'replay portfolios')
}

async function parseResponse<T>(
  response: Response,
  isValid: (value: unknown) => value is T,
  label: string,
): Promise<T> {
  const payload: unknown = await response.json()
  if (!response.ok) {
    const error = isRecord(payload) ? payload : {}
    throw new HistoricalResultsRequestError(
      typeof error.message === 'string'
        ? error.message
        : `Historical ${label} request failed with HTTP ${response.status}`,
      response.status,
      typeof error.error_code === 'string' ? error.error_code : undefined,
    )
  }
  if (!isValid(payload)) {
    throw new HistoricalResultsRequestError(
      `Historical ${label} returned an invalid response contract`,
      502,
    )
  }
  return payload
}

function isHistoricalStrategySummaryListResponse(
  value: unknown,
): value is HistoricalStrategySummaryListResponse {
  return (
    isRecord(value) &&
    typeof value.run_id === 'string' &&
    isNonNegativeInteger(value.ticket_count) &&
    Array.isArray(value.items) &&
    value.items.every(
      (item) =>
        isRecord(item) &&
        typeof item.strategy_id === 'string' &&
        typeof item.effective_strategy_id === 'string' &&
        typeof item.strategy_version === 'string' &&
        isNonNegativeInteger(item.replicate) &&
        typeof item.governance_status === 'string' &&
        isNonNegativeInteger(item.evaluated_draws) &&
        isNonNegativeInteger(item.complete_portfolios) &&
        isNonNegativeInteger(item.m4plus_hit_count),
    )
  )
}

function isHistoricalReplayPageResponse(value: unknown): value is HistoricalReplayPageResponse {
  return (
    isRecord(value) &&
    typeof value.run_id === 'string' &&
    typeof value.strategy_id === 'string' &&
    isNonNegativeInteger(value.total_count) &&
    isNonNegativeInteger(value.limit) &&
    isNonNegativeInteger(value.offset) &&
    Array.isArray(value.items) &&
    value.items.every(
      (item) =>
        isRecord(item) &&
        typeof item.portfolio_id === 'string' &&
        typeof item.strategy_id === 'string' &&
        typeof item.m4plus === 'boolean' &&
        Array.isArray(item.tickets),
    )
  )
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function isNonNegativeInteger(value: unknown): value is number {
  return typeof value === 'number' && Number.isInteger(value) && value >= 0
}
