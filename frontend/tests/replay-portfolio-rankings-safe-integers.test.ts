import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  getOptimalReplayPortfolioRankings,
  ReplayPortfolioRankingsRequestError,
} from '../src/api/replayPortfolioRankings'

const SAFE_MAX = Number.MAX_SAFE_INTEGER
const UNSAFE = SAFE_MAX + 1
const SCORING_HASH = 'a'.repeat(64)

function rankingResponse() {
  return {
    artifact_schema_version: 'v1',
    ranking_policy_id: 'FROZEN_POLICY_V1',
    source_scoring_artifact_payload_sha256: SCORING_HASH,
    source_replay_artifact_payload_sha256: 'b'.repeat(64),
    dataset_id: 'ranking-dataset',
    dataset_version: 'v1',
    lottery_type: 'BIG_LOTTO',
    target_count: 1,
    strategy_count: 1,
    top_k: 1,
    artifact_sha256: 'c'.repeat(64),
    groups: [
      {
        ticket_count: 1,
        status: 'RANKED',
        total_candidate_count: 1,
        candidates: [
          {
            rank: 1,
            ticket_count: 1,
            members: [{ source_position: 1, strategy_id: 'strategy-alpha', strategy_version: 'v1' }],
            target_count: 1,
            total_ticket_count: 1,
            scored_count: 1,
            history_closed_count: 0,
            prediction_closed_count: 0,
            target_outcome_not_found_count: 0,
            target_identity_mismatch_count: 0,
            first_prize_count: 0,
            second_prize_count: 0,
            third_prize_count: 0,
            fourth_prize_count: 0,
            fifth_prize_count: 0,
            sixth_prize_count: 0,
            seventh_prize_count: 0,
            general_prize_count: 0,
            no_prize_count: 1,
            winning_ticket_count: 0,
            candidate_sha256: 'd'.repeat(64),
          },
        ],
      },
    ],
  }
}

function responseWith(field: string, value: number) {
  const payload = rankingResponse()
  if (field === 'strategy_count') payload.strategy_count = value
  if (field === 'top_k') payload.top_k = value
  if (field === 'ticket_count') payload.groups[0]!.ticket_count = value
  if (field === 'rank') payload.groups[0]!.candidates[0]!.rank = value
  return payload
}

function apiResponse(payload: unknown): Response {
  return {
    ok: true,
    status: 200,
    json: vi.fn().mockResolvedValue(payload),
  } as unknown as Response
}

function stubResponse(payload: unknown) {
  const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(apiResponse(payload))
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

async function expectInvalidResponse(payload: unknown): Promise<void> {
  stubResponse(payload)
  const error = await getOptimalReplayPortfolioRankings(SCORING_HASH, 1).then(
    () => undefined,
    (reason: unknown) => reason,
  )
  expect(error).toBeInstanceOf(ReplayPortfolioRankingsRequestError)
  expect(error).toMatchObject({
    name: 'ReplayPortfolioRankingsRequestError',
    status: 502,
    message: 'Replay portfolio ranking returned an invalid response contract',
  })
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('Replay portfolio ranking safe integers', () => {
  it.each(['strategy_count', 'top_k', 'ticket_count', 'rank'])(
    'rejects an unsafe %s in the API response',
    async (field) => {
      await expectInvalidResponse(responseWith(field, UNSAFE))
    },
  )

  it.each([0, SAFE_MAX])('accepts safe strategy_count %s', async (value) => {
    stubResponse(responseWith('strategy_count', value))
    await expect(getOptimalReplayPortfolioRankings(SCORING_HASH, 1)).resolves.toMatchObject({
      strategy_count: value,
    })
  })

  it.each([1, SAFE_MAX])('accepts safe top_k %s', async (value) => {
    stubResponse(responseWith('top_k', value))
    await expect(getOptimalReplayPortfolioRankings(SCORING_HASH, 1)).resolves.toMatchObject({
      top_k: value,
    })
  })

  it.each([0, SAFE_MAX])('accepts safe group ticket_count %s', async (value) => {
    stubResponse(responseWith('ticket_count', value))
    await expect(getOptimalReplayPortfolioRankings(SCORING_HASH, 1)).resolves.toMatchObject({
      groups: [expect.objectContaining({ ticket_count: value })],
    })
  })

  it.each([0, SAFE_MAX])('accepts safe candidate rank %s', async (value) => {
    stubResponse(responseWith('rank', value))
    await expect(getOptimalReplayPortfolioRankings(SCORING_HASH, 1)).resolves.toMatchObject({
      groups: [
        expect.objectContaining({
          candidates: [expect.objectContaining({ rank: value })],
        }),
      ],
    })
  })

  it.each(['strategy_count', 'top_k', 'ticket_count', 'rank'])(
    'continues to reject negative and fractional %s values',
    async (field) => {
      await expectInvalidResponse(responseWith(field, -1))
      await expectInvalidResponse(responseWith(field, 1.5))
    },
  )

  it('accepts a legal response with no ranking groups', async () => {
    const payload = rankingResponse()
    payload.groups = []
    stubResponse(payload)
    await expect(getOptimalReplayPortfolioRankings(SCORING_HASH, 1)).resolves.toBe(payload)
  })

  it.each([UNSAFE, Number.NaN, Number.POSITIVE_INFINITY, 1.5])(
    'rejects invalid topK=%s before issuing fetch',
    async (topK) => {
      const fetchMock = vi.fn<typeof fetch>()
      vi.stubGlobal('fetch', fetchMock)
      await expect(getOptimalReplayPortfolioRankings(SCORING_HASH, topK)).rejects.toBeInstanceOf(
        RangeError,
      )
      expect(fetchMock).not.toHaveBeenCalled()
    },
  )

  it.each([5, SAFE_MAX])('keeps valid topK=%s request URL and response', async (topK) => {
    const payload = rankingResponse()
    payload.top_k = topK
    const fetchMock = stubResponse(payload)
    await expect(getOptimalReplayPortfolioRankings(SCORING_HASH, topK)).resolves.toBe(payload)
    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [input, init] = fetchMock.mock.calls[0]!
    expect(String(input)).toBe(
      `/api/v1/replay-rankings/optimal?scoring_artifact_sha256=${SCORING_HASH}&top_k=${topK}`,
    )
    expect(init?.method).toBe('GET')
  })
})
