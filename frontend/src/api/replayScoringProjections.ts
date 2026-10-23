import type { paths } from './generated/openapi'
import { isValidScoringArtifactSha256 } from './replayPortfolioRankings'

const ROOT_PATH = '/api/v1/replay-scoring/{scoring_artifact_payload_sha256}'
const PREDICTIONS_PATH = `${ROOT_PATH}/predictions`
const STRATEGY_AGGREGATES_PATH = `${ROOT_PATH}/strategy-aggregates`
const OVERALL_AGGREGATE_PATH = `${ROOT_PATH}/overall-aggregate`

export type ReplayScoringRunResponse =
  paths[typeof ROOT_PATH]['get']['responses'][200]['content']['application/json']
export type ReplayScoredPredictionView =
  paths[typeof PREDICTIONS_PATH]['get']['responses'][200]['content']['application/json'][number]
export type ReplayScoringPredictionsQuery =
  paths[typeof PREDICTIONS_PATH]['get']['parameters']['query']
export type ReplayStrategyAggregateView =
  paths[typeof STRATEGY_AGGREGATES_PATH]['get']['responses'][200]['content']['application/json'][number]
export type ReplayOverallAggregateResponse =
  paths[typeof OVERALL_AGGREGATE_PATH]['get']['responses'][200]['content']['application/json']

export class ReplayScoringProjectionsRequestError extends Error {
  readonly status: number
  readonly errorCode: string | undefined

  constructor(message: string, status: number, errorCode?: string) {
    super(message)
    this.name = 'ReplayScoringProjectionsRequestError'
    this.status = status
    this.errorCode = errorCode
  }
}

export function getReplayScoringRun(
  scoringArtifactSha256: string,
  signal?: AbortSignal,
): Promise<ReplayScoringRunResponse> {
  return requestJson(
    scoringArtifactSha256,
    '',
    isReplayScoringRunResponse,
    'Replay scoring artifact',
    signal,
  )
}

export function listReplayScoringPredictions(
  scoringArtifactSha256: string,
  query: ReplayScoringPredictionsQuery = {},
  signal?: AbortSignal,
): Promise<ReplayScoredPredictionView[]> {
  const parameters = new URLSearchParams()
  for (const key of ['target_draw', 'strategy_id', 'status', 'tier'] as const) {
    const value = query[key]
    if (typeof value === 'string' && value.length > 0) parameters.set(key, value)
  }
  const suffix = parameters.size ? `/predictions?${parameters.toString()}` : '/predictions'
  return requestJson(
    scoringArtifactSha256,
    suffix,
    isReplayScoredPredictions,
    'Replay scoring predictions',
    signal,
  )
}

export function listReplayScoringStrategyAggregates(
  scoringArtifactSha256: string,
  signal?: AbortSignal,
): Promise<ReplayStrategyAggregateView[]> {
  return requestJson(
    scoringArtifactSha256,
    '/strategy-aggregates',
    isReplayStrategyAggregates,
    'Replay strategy aggregates',
    signal,
  )
}

export function getReplayScoringOverallAggregate(
  scoringArtifactSha256: string,
  signal?: AbortSignal,
): Promise<ReplayOverallAggregateResponse> {
  return requestJson(
    scoringArtifactSha256,
    '/overall-aggregate',
    isReplayOverallAggregateResponse,
    'Replay overall aggregate',
    signal,
  )
}

async function requestJson<T>(
  scoringArtifactSha256: string,
  suffix: string,
  isResponse: (value: unknown) => value is T,
  label: string,
  signal?: AbortSignal,
): Promise<T> {
  if (!isValidScoringArtifactSha256(scoringArtifactSha256)) {
    throw new ReplayScoringProjectionsRequestError(
      'The source scoring artifact must be an exact lowercase 64-character SHA-256.',
      0,
    )
  }

  const response = await fetch(
    `/api/v1/replay-scoring/${scoringArtifactSha256}${suffix}`,
    {
      method: 'GET',
      headers: { Accept: 'application/json' },
      signal,
    },
  )
  let payload: unknown
  try {
    payload = await response.json()
  } catch {
    throw new ReplayScoringProjectionsRequestError(
      `${label} returned an unreadable response`,
      response.status,
    )
  }

  if (!response.ok) {
    const error = isRecord(payload) ? payload : {}
    throw new ReplayScoringProjectionsRequestError(
      typeof error.message === 'string'
        ? error.message
        : `${label} request failed with HTTP ${response.status}`,
      response.status,
      typeof error.error_code === 'string' ? error.error_code : undefined,
    )
  }
  if (!isResponse(payload)) {
    throw new ReplayScoringProjectionsRequestError(
      `${label} returned an invalid response contract`,
      502,
    )
  }
  return payload
}

function isReplayScoringRunResponse(value: unknown): value is ReplayScoringRunResponse {
  return (
    isRecord(value) &&
    typeof value.scoring_artifact_schema_version === 'string' &&
    typeof value.scoring_artifact_payload_sha256 === 'string' &&
    typeof value.source_replay_artifact_payload_sha256 === 'string' &&
    typeof value.dataset_id === 'string' &&
    typeof value.dataset_version === 'string' &&
    typeof value.lottery_type === 'string' &&
    hasCounts(value, ['target_count', 'strategy_count', 'scored_record_count']) &&
    typeof value.overall_aggregate_sha256 === 'string'
  )
}

function isReplayScoredPredictions(value: unknown): value is ReplayScoredPredictionView[] {
  return Array.isArray(value) && value.every(isReplayScoredPrediction)
}

function isReplayScoredPrediction(value: unknown): value is ReplayScoredPredictionView {
  return (
    isRecord(value) &&
    typeof value.run_payload_sha256 === 'string' &&
    Number.isInteger(value.ordinal) &&
    typeof value.source_snapshot_result_sha256 === 'string' &&
    typeof value.scored_result_sha256 === 'string' &&
    typeof value.target_draw_number === 'string' &&
    typeof value.target_draw_date === 'string' &&
    typeof value.strategy_id === 'string' &&
    typeof value.source_history_status === 'string' &&
    typeof value.scoring_status === 'string'
  )
}

function isReplayStrategyAggregates(value: unknown): value is ReplayStrategyAggregateView[] {
  return (
    Array.isArray(value) &&
    value.every(
      (item) =>
        isRecord(item) &&
        typeof item.run_payload_sha256 === 'string' &&
        Number.isInteger(item.ordinal) &&
        typeof item.strategy_id === 'string' &&
        hasCounts(item, AGGREGATE_COUNT_FIELDS) &&
        typeof item.aggregate_sha256 === 'string',
    )
  )
}

function isReplayOverallAggregateResponse(value: unknown): value is ReplayOverallAggregateResponse {
  return (
    isRecord(value) &&
    typeof value.run_payload_sha256 === 'string' &&
    hasCounts(value, AGGREGATE_COUNT_FIELDS) &&
    typeof value.aggregate_sha256 === 'string'
  )
}

const AGGREGATE_COUNT_FIELDS = [
  'source_snapshot_count',
  'scored_count',
  'history_closed_count',
  'prediction_closed_count',
  'target_outcome_not_found_count',
  'target_identity_mismatch_count',
  'first_prize_count',
  'second_prize_count',
  'third_prize_count',
  'fourth_prize_count',
  'fifth_prize_count',
  'sixth_prize_count',
  'seventh_prize_count',
  'general_prize_count',
  'no_prize_count',
] as const

function hasCounts(
  value: Record<string, unknown>,
  keys: readonly string[],
): boolean {
  return keys.every(
    (key) => typeof value[key] === 'number' && Number.isInteger(value[key]) && value[key] >= 0,
  )
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}
