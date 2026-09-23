import type { paths } from './generated/openapi'

export type NextDrawRecommendationResponse =
  paths['/api/v1/next-draw-recommendation']['get']['responses'][200]['content']['application/json']
export type RecommendationCandidateView = NextDrawRecommendationResponse['ranked'][number]
export type RecommendationExclusionView = NextDrawRecommendationResponse['excluded'][number]
export type RecommendationWindowMetricView = RecommendationCandidateView['windows'][number]

export const NATIVE_TICKET_COUNT_BUCKETS = [1, 2, 3, 5, 10, 20] as const
export type NativeTicketCount = (typeof NATIVE_TICKET_COUNT_BUCKETS)[number]

export class NextDrawRecommendationRequestError extends Error {
  readonly status: number
  readonly errorCode: string | undefined

  constructor(message: string, status: number, errorCode?: string) {
    super(message)
    this.name = 'NextDrawRecommendationRequestError'
    this.status = status
    this.errorCode = errorCode
  }
}

export async function getNextDrawRecommendation(
  nativeTicketCount: NativeTicketCount,
  signal?: AbortSignal,
): Promise<NextDrawRecommendationResponse> {
  const parameters = new URLSearchParams({ native_ticket_count: String(nativeTicketCount) })
  const response = await fetch(`/api/v1/next-draw-recommendation?${parameters.toString()}`, {
    method: 'GET',
    headers: { Accept: 'application/json' },
    signal,
  })
  const payload: unknown = await response.json()
  if (!response.ok) {
    const error = isRecord(payload) ? payload : {}
    throw new NextDrawRecommendationRequestError(
      typeof error.message === 'string'
        ? error.message
        : `Next-Draw Recommendation request failed with HTTP ${response.status}`,
      response.status,
      typeof error.error_code === 'string' ? error.error_code : undefined,
    )
  }
  if (!isNextDrawRecommendationResponse(payload)) {
    throw new NextDrawRecommendationRequestError(
      'Next-Draw Recommendation returned an invalid response contract',
      502,
    )
  }
  return payload
}

function isNextDrawRecommendationResponse(
  value: unknown,
): value is NextDrawRecommendationResponse {
  return (
    isRecord(value) &&
    typeof value.ranking_policy_id === 'string' &&
    typeof value.lottery_type === 'string' &&
    isNonNegativeInteger(value.native_ticket_count) &&
    typeof value.availability === 'string' &&
    isNonNegativeInteger(value.total_candidate_count) &&
    Array.isArray(value.ranked) &&
    Array.isArray(value.excluded) &&
    typeof value.evidence_computation_status === 'string' &&
    typeof value.evidence_artifact_sha256 === 'string'
  )
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function isNonNegativeInteger(value: unknown): value is number {
  return typeof value === 'number' && Number.isInteger(value) && value >= 0
}
