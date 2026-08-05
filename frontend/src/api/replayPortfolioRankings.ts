import type { paths } from './generated/openapi'

export type ReplayPortfolioRankingResponse =
  paths['/api/v1/replay-rankings/optimal']['get']['responses'][200]['content']['application/json']
export type ReplayPortfolioRankingGroupView = ReplayPortfolioRankingResponse['groups'][number]
export type ReplayPortfolioRankingCandidateView =
  ReplayPortfolioRankingGroupView['candidates'][number]

const SHA256_PATTERN = /^[0-9a-f]{64}$/

export class ReplayPortfolioRankingsRequestError extends Error {
  readonly status: number
  readonly errorCode: string | undefined

  constructor(message: string, status: number, errorCode?: string) {
    super(message)
    this.name = 'ReplayPortfolioRankingsRequestError'
    this.status = status
    this.errorCode = errorCode
  }
}

export function isValidScoringArtifactSha256(value: string): boolean {
  return SHA256_PATTERN.test(value)
}

export async function getOptimalReplayPortfolioRankings(
  scoringArtifactSha256: string,
  topK: number,
  signal?: AbortSignal,
): Promise<ReplayPortfolioRankingResponse> {
  const parameters = new URLSearchParams({
    scoring_artifact_sha256: scoringArtifactSha256,
    top_k: String(topK),
  })
  const response = await fetch(`/api/v1/replay-rankings/optimal?${parameters.toString()}`, {
    method: 'GET',
    headers: { Accept: 'application/json' },
    signal,
  })
  const payload: unknown = await response.json()
  if (!response.ok) {
    const error = isRecord(payload) ? payload : {}
    throw new ReplayPortfolioRankingsRequestError(
      typeof error.message === 'string'
        ? error.message
        : `Replay portfolio ranking request failed with HTTP ${response.status}`,
      response.status,
      typeof error.error_code === 'string' ? error.error_code : undefined,
    )
  }
  if (!isReplayPortfolioRankingResponse(payload)) {
    throw new ReplayPortfolioRankingsRequestError(
      'Replay portfolio ranking returned an invalid response contract',
      502,
    )
  }
  return payload
}

function isReplayPortfolioRankingResponse(
  value: unknown,
): value is ReplayPortfolioRankingResponse {
  return (
    isRecord(value) &&
    typeof value.ranking_policy_id === 'string' &&
    typeof value.lottery_type === 'string' &&
    isNonNegativeInteger(value.strategy_count) &&
    isNonNegativeInteger(value.top_k) &&
    Array.isArray(value.groups) &&
    value.groups.every(
      (group) =>
        isRecord(group) &&
        isNonNegativeInteger(group.ticket_count) &&
        typeof group.status === 'string' &&
        Array.isArray(group.candidates) &&
        group.candidates.every(
          (candidate) =>
            isRecord(candidate) &&
            isNonNegativeInteger(candidate.rank) &&
            Array.isArray(candidate.members) &&
            typeof candidate.candidate_sha256 === 'string',
        ),
    )
  )
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function isNonNegativeInteger(value: unknown): value is number {
  return typeof value === 'number' && Number.isInteger(value) && value >= 0
}
