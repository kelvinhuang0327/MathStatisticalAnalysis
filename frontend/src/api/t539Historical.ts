import type { components, paths } from './generated/openapi'

export type T539Run = components['schemas']['T539RunView']
export type T539RunPage = paths['/api/v1/t539-historical/runs']['get']['responses'][200]['content']['application/json']
export type T539Draw = components['schemas']['T539DrawView']
export type T539DrawPage =
  paths['/api/v1/t539-historical/runs/{run_id}/draws']['get']['responses'][200]['content']['application/json']
export type T539Strategy = components['schemas']['T539StrategyView']
export type T539StrategyPage =
  paths['/api/v1/t539-historical/runs/{run_id}/strategies']['get']['responses'][200]['content']['application/json']
export type T539Replay = components['schemas']['T539ReplayView']
export type T539ReplayPage =
  paths['/api/v1/t539-historical/runs/{run_id}/replay']['get']['responses'][200]['content']['application/json']
export type T539Metrics = components['schemas']['T539MetricsResponse']
export type T539Ranking = components['schemas']['T539RankingView']
export type T539RankingPage =
  paths['/api/v1/t539-historical/runs/{run_id}/rankings']['get']['responses'][200]['content']['application/json']
export type T539CoverageExecuted = components['schemas']['T539CoverageExecutedView']
export type T539CoverageBlocked = components['schemas']['T539CoverageBlockedView']
export type T539CoverageLedger =
  paths['/api/v1/t539-historical/runs/{run_id}/coverage']['get']['responses'][200]['content']['application/json']

export type T539RequestErrorKind =
  | 'NOT_CONFIGURED'
  | 'UNAVAILABLE'
  | 'NOT_FOUND'
  | 'INVALID_REQUEST'
  | 'MALFORMED_RESPONSE'

export interface T539RunQuery {
  limit: number
  offset: number
}

export interface T539StrategyQuery {
  limit: number
  offset: number
}

export class T539HistoricalRequestError extends Error {
  readonly kind: T539RequestErrorKind
  readonly status: number

  constructor(kind: T539RequestErrorKind, message: string, status = 0) {
    super(message)
    this.name = 'T539HistoricalRequestError'
    this.kind = kind
    this.status = status
  }
}

const RUNS_ENDPOINT = '/api/v1/t539-historical/runs'

export async function listT539Runs(
  query: T539RunQuery,
  signal?: AbortSignal,
): Promise<T539RunPage> {
  const parameters = new URLSearchParams({
    limit: String(query.limit),
    offset: String(query.offset),
  })
  const payload = await requestJson(`${RUNS_ENDPOINT}?${parameters.toString()}`, signal)
  if (!isT539RunPage(payload)) throw malformedResponse()
  return payload
}

export async function listT539Strategies(
  runId: string,
  query: T539StrategyQuery,
  signal?: AbortSignal,
): Promise<T539StrategyPage> {
  const parameters = new URLSearchParams({
    limit: String(query.limit),
    offset: String(query.offset),
  })
  const payload = await requestJson(
    `${RUNS_ENDPOINT}/${encodeURIComponent(runId)}/strategies?${parameters.toString()}`,
    signal,
  )
  if (!isT539StrategyPage(payload)) throw malformedResponse()
  return payload
}

export async function listT539Draws(
  runId: string,
  query: T539RunQuery,
  signal?: AbortSignal,
): Promise<T539DrawPage> {
  const parameters = new URLSearchParams({
    limit: String(query.limit),
    offset: String(query.offset),
  })
  const payload = await requestJson(
    `${RUNS_ENDPOINT}/${encodeURIComponent(runId)}/draws?${parameters.toString()}`,
    signal,
  )
  if (!isT539DrawPage(payload)) throw malformedResponse()
  return payload
}

export async function getT539StrategyTarget(
  runId: string,
  strategyId: string,
  strategyVersion: string,
  drawId: string,
  signal?: AbortSignal,
): Promise<T539Replay> {
  const payload = await requestJson(
    `${RUNS_ENDPOINT}/${encodeURIComponent(runId)}/strategies/${encodeURIComponent(strategyId)}/${encodeURIComponent(strategyVersion)}/targets/${encodeURIComponent(drawId)}`,
    signal,
  )
  if (!isT539Replay(payload)) throw malformedResponse()
  return payload
}

export async function getT539Metrics(
  runId: string,
  strategyId: string | undefined,
  signal?: AbortSignal,
): Promise<T539Metrics> {
  const parameters = new URLSearchParams()
  if (strategyId) parameters.set('strategy_id', strategyId)
  const suffix = parameters.size ? `?${parameters.toString()}` : ''
  const payload = await requestJson(
    `${RUNS_ENDPOINT}/${encodeURIComponent(runId)}/metrics${suffix}`,
    signal,
  )
  if (!isT539Metrics(payload)) throw malformedResponse()
  return payload
}

export async function getT539Rankings(
  runId: string,
  signal?: AbortSignal,
): Promise<T539RankingPage> {
  const payload = await requestJson(`${RUNS_ENDPOINT}/${encodeURIComponent(runId)}/rankings`, signal)
  if (!isT539RankingPage(payload)) throw malformedResponse()
  return payload
}

export async function getT539Coverage(
  runId: string,
  signal?: AbortSignal,
): Promise<T539CoverageLedger> {
  const payload = await requestJson(`${RUNS_ENDPOINT}/${encodeURIComponent(runId)}/coverage`, signal)
  if (!isT539CoverageLedger(payload)) throw malformedResponse()
  return payload
}

async function requestJson(url: string, signal?: AbortSignal): Promise<unknown> {
  let response: Response
  try {
    response = await fetch(url, { signal })
  } catch (error: unknown) {
    if (isAbort(error)) throw error
    throw new T539HistoricalRequestError('UNAVAILABLE', 'T539 Historical Results could not load.')
  }
  const payload: unknown = await response.json().catch(() => null)
  if (!response.ok) throw requestError(response.status, payload)
  return payload
}

function requestError(status: number, payload: unknown): T539HistoricalRequestError {
  const message =
    isRecord(payload) && typeof payload.message === 'string'
      ? payload.message
      : 'T539 Historical Results request failed.'
  if (status === 404) return new T539HistoricalRequestError('NOT_FOUND', message, status)
  if (status === 422) return new T539HistoricalRequestError('INVALID_REQUEST', message, status)
  if (status === 503 && isRecord(payload) && payload.error_code === 'T539_HISTORICAL_NOT_CONFIGURED') {
    return new T539HistoricalRequestError('NOT_CONFIGURED', message, status)
  }
  if (status === 503) return new T539HistoricalRequestError('UNAVAILABLE', message, status)
  return new T539HistoricalRequestError('UNAVAILABLE', message, status)
}

function malformedResponse(): T539HistoricalRequestError {
  return new T539HistoricalRequestError(
    'MALFORMED_RESPONSE',
    'T539 Historical Results returned an unexpected response.',
  )
}

function isT539RunPage(value: unknown): value is T539RunPage {
  return isPage(value) && value.items.every(isT539Run)
}

function isT539StrategyPage(value: unknown): value is T539StrategyPage {
  return (
    isPage(value) &&
    isRecord(value) &&
    typeof value.run_id === 'string' &&
    value.items.every(isT539Strategy)
  )
}

function isT539DrawPage(value: unknown): value is T539DrawPage {
  return isPage(value) && isRecord(value) && typeof value.run_id === 'string' && value.items.every(isT539Draw)
}

function isT539Draw(value: unknown): value is T539Draw {
  return (
    isRecord(value) &&
    typeof value.draw_id === 'string' &&
    typeof value.draw_date === 'string' &&
    Array.isArray(value.winning_numbers)
  )
}

function isT539Replay(value: unknown): value is T539Replay {
  return (
    isRecord(value) &&
    typeof value.target_id === 'string' &&
    typeof value.strategy_id === 'string' &&
    Array.isArray(value.tickets)
  )
}

function isT539CoverageLedger(value: unknown): value is T539CoverageLedger {
  return (
    isRecord(value) &&
    typeof value.run_id === 'string' &&
    typeof value.coverage_complete === 'boolean' &&
    Array.isArray(value.executed) &&
    value.executed.every(isT539CoverageExecuted) &&
    Array.isArray(value.blocked) &&
    value.blocked.every(isT539CoverageBlocked)
  )
}

type PagePayload = {
  items: unknown[]
  total_count: number
  limit: number
  offset: number
  [key: string]: unknown
}

function isPage(value: unknown): value is PagePayload {
  return (
    isRecord(value) &&
    Array.isArray(value.items) &&
    typeof value.total_count === 'number' &&
    typeof value.limit === 'number' &&
    typeof value.offset === 'number'
  )
}

function isT539Run(value: unknown): value is T539Run {
  return (
    isRecord(value) &&
    typeof value.run_id === 'string' &&
    typeof value.status === 'string' &&
    typeof value.lottery_type === 'string'
  )
}

function isT539Strategy(value: unknown): value is T539Strategy {
  return (
    isRecord(value) &&
    typeof value.strategy_id === 'string' &&
    typeof value.status === 'string' &&
    Array.isArray(value.hit_distribution)
  )
}

function isT539Metrics(value: unknown): value is T539Metrics {
  return (
    isRecord(value) &&
    typeof value.run_id === 'string' &&
    typeof value.target_count === 'number' &&
    Array.isArray(value.hit_distribution) &&
    Array.isArray(value.prize_tier_counts)
  )
}

function isT539RankingPage(value: unknown): value is T539RankingPage {
  return (
    isRecord(value) &&
    typeof value.run_id === 'string' &&
    Array.isArray(value.items) &&
    value.items.every(isT539Ranking)
  )
}

function isT539Ranking(value: unknown): value is T539Ranking {
  return (
    isRecord(value) &&
    typeof value.strategy_id === 'string' &&
    typeof value.rank === 'number' &&
    typeof value.winning_target_rate === 'number' &&
    typeof value.ticket_winning_rate === 'number' &&
    Array.isArray(value.prize_tier_counts)
  )
}

function isT539CoverageExecuted(value: unknown): value is T539CoverageExecuted {
  return (
    isRecord(value) &&
    typeof value.strategy_id === 'string' &&
    typeof value.strategy_version === 'string' &&
    typeof value.selection_reason === 'string'
  )
}

function isT539CoverageBlocked(value: unknown): value is T539CoverageBlocked {
  return (
    isRecord(value) &&
    typeof value.strategy_id === 'string' &&
    typeof value.reason_code === 'string' &&
    typeof value.reason === 'string'
  )
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isAbort(error: unknown): boolean {
  return (error instanceof DOMException || error instanceof Error) && error.name === 'AbortError'
}
