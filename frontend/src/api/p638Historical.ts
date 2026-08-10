import type { components, paths } from './generated/openapi'

export type P638Run = components['schemas']['P638RunView']
export type P638RunPage = paths['/api/v1/p638-historical/runs']['get']['responses'][200]['content']['application/json']
export type P638Draw = components['schemas']['P638DrawView']
export type P638DrawPage =
  paths['/api/v1/p638-historical/runs/{run_id}/draws']['get']['responses'][200]['content']['application/json']
export type P638Strategy = components['schemas']['P638StrategyView']
export type P638StrategyPage = paths['/api/v1/p638-historical/runs/{run_id}/strategies']['get']['responses'][200]['content']['application/json']
export type P638Replay = components['schemas']['P638ReplayView']
export type P638ReplayPage = paths['/api/v1/p638-historical/runs/{run_id}/replay']['get']['responses'][200]['content']['application/json']
export type P638Metrics = components['schemas']['P638MetricsResponse']
export type P638Ranking = components['schemas']['P638RankingView']
export type P638RankingPage =
  paths['/api/v1/p638-historical/runs/{run_id}/rankings']['get']['responses'][200]['content']['application/json']
export type P638Status = 'COMPLETE' | 'EXCLUDED_INSUFFICIENT_HISTORY' | 'FAILED'
export type P638RequestErrorKind =
  | 'NOT_CONFIGURED'
  | 'UNAVAILABLE'
  | 'NOT_FOUND'
  | 'INVALID_REQUEST'
  | 'MALFORMED_RESPONSE'

export interface P638ReplayQuery {
  strategyId?: string
  dateFrom?: string
  dateTo?: string
  status?: P638Status
  limit: number
  offset: number
}

export interface P638RunQuery {
  limit: number
  offset: number
}

export class P638HistoricalRequestError extends Error {
  readonly kind: P638RequestErrorKind
  readonly status: number

  constructor(kind: P638RequestErrorKind, message: string, status = 0) {
    super(message)
    this.name = 'P638HistoricalRequestError'
    this.kind = kind
    this.status = status
  }
}

const RUNS_ENDPOINT = '/api/v1/p638-historical/runs'

export async function listP638Runs(
  query: P638RunQuery,
  signal?: AbortSignal,
): Promise<P638RunPage> {
  const parameters = new URLSearchParams({
    limit: String(query.limit),
    offset: String(query.offset),
  })
  const payload = await requestJson(`${RUNS_ENDPOINT}?${parameters.toString()}`, signal)
  if (!isP638RunPage(payload)) throw malformedResponse()
  return payload
}

export async function listP638Strategies(
  runId: string,
  query: P638RunQuery,
  signal?: AbortSignal,
): Promise<P638StrategyPage> {
  const parameters = new URLSearchParams({
    limit: String(query.limit),
    offset: String(query.offset),
  })
  const payload = await requestJson(
    `${RUNS_ENDPOINT}/${encodeURIComponent(runId)}/strategies?${parameters.toString()}`,
    signal,
  )
  if (!isP638StrategyPage(payload)) throw malformedResponse()
  return payload
}

export async function listP638Draws(
  runId: string,
  query: P638RunQuery,
  signal?: AbortSignal,
): Promise<P638DrawPage> {
  const parameters = new URLSearchParams({
    limit: String(query.limit),
    offset: String(query.offset),
  })
  const payload = await requestJson(
    `${RUNS_ENDPOINT}/${encodeURIComponent(runId)}/draws?${parameters.toString()}`,
    signal,
  )
  if (!isP638DrawPage(payload)) throw malformedResponse()
  return payload
}

export async function listP638Replay(
  runId: string,
  query: P638ReplayQuery,
  signal?: AbortSignal,
): Promise<P638ReplayPage> {
  const parameters = new URLSearchParams({
    limit: String(query.limit),
    offset: String(query.offset),
  })
  if (query.strategyId) parameters.set('strategy_id', query.strategyId)
  if (query.dateFrom) parameters.set('date_from', query.dateFrom)
  if (query.dateTo) parameters.set('date_to', query.dateTo)
  if (query.status) parameters.set('status', query.status)
  const payload = await requestJson(
    `${RUNS_ENDPOINT}/${encodeURIComponent(runId)}/replay?${parameters.toString()}`,
    signal,
  )
  if (!isP638ReplayPage(payload)) throw malformedResponse()
  return payload
}

export async function getP638Metrics(
  runId: string,
  strategyId: string | undefined,
  signal?: AbortSignal,
): Promise<P638Metrics> {
  const parameters = new URLSearchParams()
  if (strategyId) parameters.set('strategy_id', strategyId)
  const suffix = parameters.size ? `?${parameters.toString()}` : ''
  const payload = await requestJson(
    `${RUNS_ENDPOINT}/${encodeURIComponent(runId)}/metrics${suffix}`,
    signal,
  )
  if (!isP638Metrics(payload)) throw malformedResponse()
  return payload
}

export async function getP638Target(
  runId: string,
  targetId: string,
  signal?: AbortSignal,
): Promise<P638Replay> {
  const payload = await requestJson(
    `${RUNS_ENDPOINT}/${encodeURIComponent(runId)}/targets/${encodeURIComponent(targetId)}`,
    signal,
  )
  if (!isP638Replay(payload)) throw malformedResponse()
  return payload
}

export async function getP638StrategyTarget(
  runId: string,
  strategyId: string,
  strategyVersion: string,
  drawNumber: string,
  signal?: AbortSignal,
): Promise<P638Replay> {
  const payload = await requestJson(
    `${RUNS_ENDPOINT}/${encodeURIComponent(runId)}/strategies/${encodeURIComponent(strategyId)}/${encodeURIComponent(strategyVersion)}/targets/${encodeURIComponent(drawNumber)}`,
    signal,
  )
  if (!isP638Replay(payload)) throw malformedResponse()
  return payload
}

export async function getP638Rankings(runId: string, signal?: AbortSignal): Promise<P638RankingPage> {
  const payload = await requestJson(`${RUNS_ENDPOINT}/${encodeURIComponent(runId)}/rankings`, signal)
  if (!isP638RankingPage(payload)) throw malformedResponse()
  return payload
}

async function requestJson(url: string, signal?: AbortSignal): Promise<unknown> {
  let response: Response
  try {
    response = await fetch(url, { signal })
  } catch (error: unknown) {
    if (isAbort(error)) throw error
    throw new P638HistoricalRequestError('UNAVAILABLE', 'P638 Historical Results could not load.')
  }
  const payload: unknown = await response.json().catch(() => null)
  if (!response.ok) throw requestError(response.status, payload)
  return payload
}

function requestError(status: number, payload: unknown): P638HistoricalRequestError {
  const message =
    isRecord(payload) && typeof payload.message === 'string'
      ? payload.message
      : 'P638 Historical Results request failed.'
  if (status === 404) return new P638HistoricalRequestError('NOT_FOUND', message, status)
  if (status === 422) return new P638HistoricalRequestError('INVALID_REQUEST', message, status)
  if (status === 503 && isRecord(payload) && payload.error_code === 'P638_HISTORICAL_NOT_CONFIGURED') {
    return new P638HistoricalRequestError('NOT_CONFIGURED', message, status)
  }
  if (status === 503) return new P638HistoricalRequestError('UNAVAILABLE', message, status)
  return new P638HistoricalRequestError('UNAVAILABLE', message, status)
}

function malformedResponse(): P638HistoricalRequestError {
  return new P638HistoricalRequestError(
    'MALFORMED_RESPONSE',
    'P638 Historical Results returned an unexpected response.',
  )
}

function isP638RunPage(value: unknown): value is P638RunPage {
  return isPage(value) && value.items.every(isP638Run)
}

function isP638StrategyPage(value: unknown): value is P638StrategyPage {
  return isPage(value) && isRecord(value) && typeof value.run_id === 'string' && value.items.every(isP638Strategy)
}

function isP638DrawPage(value: unknown): value is P638DrawPage {
  return isPage(value) && isRecord(value) && typeof value.run_id === 'string' && value.items.every(isP638Draw)
}

function isP638Draw(value: unknown): value is P638Draw {
  return (
    isRecord(value) &&
    typeof value.draw_number === 'string' &&
    typeof value.draw_date === 'string' &&
    Array.isArray(value.winning_zone1_numbers) &&
    typeof value.winning_zone2_number === 'number'
  )
}

function isP638ReplayPage(value: unknown): value is P638ReplayPage {
  return isPage(value) && isRecord(value) && typeof value.run_id === 'string' && value.items.every(isP638Replay)
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

function isP638Run(value: unknown): value is P638Run {
  return isRecord(value) && typeof value.run_id === 'string' && typeof value.status === 'string'
}

function isP638Strategy(value: unknown): value is P638Strategy {
  return isRecord(value) && typeof value.strategy_id === 'string' && typeof value.replay_status === 'string'
}

function isP638Replay(value: unknown): value is P638Replay {
  return (
    isRecord(value) &&
    typeof value.target_id === 'string' &&
    typeof value.strategy_id === 'string' &&
    Array.isArray(value.tickets)
  )
}

function isP638Metrics(value: unknown): value is P638Metrics {
  return (
    isRecord(value) &&
    typeof value.run_id === 'string' &&
    typeof value.target_count === 'number' &&
    Array.isArray(value.zone1_hit_distribution) &&
    Array.isArray(value.zone2_hit_distribution)
  )
}

function isP638RankingPage(value: unknown): value is P638RankingPage {
  return (
    isRecord(value) &&
    typeof value.run_id === 'string' &&
    Array.isArray(value.items) &&
    value.items.every(isP638Ranking)
  )
}

function isP638Ranking(value: unknown): value is P638Ranking {
  return (
    isRecord(value) &&
    typeof value.strategy_id === 'string' &&
    typeof value.rank === 'number' &&
    typeof value.winning_target_rate === 'number' &&
    Array.isArray(value.prize_tier_counts)
  )
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isAbort(error: unknown): boolean {
  return (error instanceof DOMException || error instanceof Error) && error.name === 'AbortError'
}
