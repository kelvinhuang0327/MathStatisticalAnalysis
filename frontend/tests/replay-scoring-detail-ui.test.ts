// @vitest-environment jsdom

import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'

import ReplayHistoryPage from '../src/features/replay-history/ReplayHistoryPage.vue'

const enteredHash = 'b'.repeat(64)
const sourceHash = 'a'.repeat(64)

function apiResponse(payload: unknown, status = 200): Response {
  return {
    ok: status < 400,
    status,
    json: vi.fn().mockResolvedValue(payload),
  } as unknown as Response
}

function rankingResponse(sourceScoringHash = sourceHash) {
  return {
    artifact_schema_version: 'v1',
    ranking_policy_id: 'FROZEN_POLICY_V1',
    source_scoring_artifact_payload_sha256: sourceScoringHash,
    source_replay_artifact_payload_sha256: 'c'.repeat(64),
    dataset_id: 'ranking-dataset',
    dataset_version: 'v3',
    lottery_type: 'BIG_LOTTO',
    target_count: 3,
    strategy_count: 1,
    top_k: 1,
    artifact_sha256: 'd'.repeat(64),
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
            target_count: 3,
            total_ticket_count: 3,
            scored_count: 1,
            history_closed_count: 1,
            prediction_closed_count: 1,
            target_outcome_not_found_count: 0,
            target_identity_mismatch_count: 0,
            first_prize_count: 0,
            second_prize_count: 0,
            third_prize_count: 0,
            fourth_prize_count: 0,
            fifth_prize_count: 0,
            sixth_prize_count: 1,
            seventh_prize_count: 0,
            general_prize_count: 0,
            no_prize_count: 0,
            winning_ticket_count: 1,
            candidate_sha256: 'e'.repeat(64),
          },
        ],
      },
    ],
  }
}

function scoringRun(hash: string, datasetId = 'detail-dataset') {
  return {
    scoring_artifact_schema_version: 'scoring-v1',
    scoring_artifact_payload_sha256: hash,
    source_replay_artifact_payload_sha256: 'f'.repeat(64),
    dataset_id: datasetId,
    dataset_version: 'detail-v7',
    lottery_type: 'BIG_LOTTO',
    target_count: 12,
    strategy_count: 1,
    scored_record_count: 8,
    overall_aggregate_sha256: '1'.repeat(64),
  }
}

function prediction(hash: string) {
  return {
    run_payload_sha256: hash,
    ordinal: 1,
    source_snapshot_result_sha256: '2'.repeat(64),
    scored_result_sha256: '3'.repeat(64),
    target_draw_number: '113000120',
    target_draw_date: '2026-10-01',
    strategy_id: 'strategy-alpha',
    strategy_version: null,
    source_history_status: 'HISTORY_CLOSED',
    source_history_reason_code: 'HISTORY_NOT_AVAILABLE',
    source_prediction_status: 'PREDICTION_CLOSED',
    source_prediction_reason_code: 'PREDICTION_NOT_AVAILABLE',
    scoring_status: 'IDENTITY_MISMATCH',
    scoring_reason_code: 'TARGET_IDENTITY_MISMATCH',
    predicted_main_numbers: null,
    target_outcome_sha256: null,
    main_number_hit_count: null,
    special_number_hit: null,
    prize_tier_id: null,
    prize_official_label: null,
    no_prize_result: null,
  }
}

function strategyAggregate(hash: string) {
  return {
    run_payload_sha256: hash,
    ordinal: 1,
    strategy_id: 'strategy-alpha',
    strategy_version: 'v1',
    source_snapshot_count: 12,
    scored_count: 8,
    history_closed_count: 2,
    prediction_closed_count: 3,
    target_outcome_not_found_count: 1,
    target_identity_mismatch_count: 1,
    first_prize_count: 1,
    second_prize_count: 2,
    third_prize_count: 3,
    fourth_prize_count: 4,
    fifth_prize_count: 5,
    sixth_prize_count: 6,
    seventh_prize_count: 7,
    general_prize_count: 8,
    no_prize_count: 9,
    aggregate_sha256: '4'.repeat(64),
  }
}

function overallAggregate(hash: string) {
  return {
    run_payload_sha256: hash,
    source_snapshot_count: 12,
    scored_count: 8,
    history_closed_count: 2,
    prediction_closed_count: 3,
    target_outcome_not_found_count: 1,
    target_identity_mismatch_count: 1,
    first_prize_count: 1,
    second_prize_count: 2,
    third_prize_count: 3,
    fourth_prize_count: 4,
    fifth_prize_count: 5,
    sixth_prize_count: 6,
    seventh_prize_count: 7,
    general_prize_count: 8,
    no_prize_count: 9,
    aggregate_sha256: '5'.repeat(64),
  }
}

function detailPayload(url: URL, hash: string, datasetId?: string): unknown {
  if (url.pathname === `/api/v1/replay-scoring/${hash}`) return scoringRun(hash, datasetId)
  if (url.pathname.endsWith('/predictions')) return [prediction(hash)]
  if (url.pathname.endsWith('/strategy-aggregates')) return [strategyAggregate(hash)]
  if (url.pathname.endsWith('/overall-aggregate')) return overallAggregate(hash)
  throw new Error(`Unexpected scoring detail request: ${url.pathname}`)
}

async function selectOptimalAndLoadRankings(
  wrapper: ReturnType<typeof mount<typeof ReplayHistoryPage>>,
  scoringHash = enteredHash,
): Promise<void> {
  await wrapper.findAll('nav[aria-label="Replay history sections"] button')[1]?.trigger('click')
  await wrapper.get('input[name="scoring_artifact_sha256"]').setValue(scoringHash)
  await wrapper.findAll('form')[0]?.trigger('submit')
  await flushPromises()
}

function detailButton(wrapper: ReturnType<typeof mount<typeof ReplayHistoryPage>>) {
  return wrapper.findAll('button').find((button) => button.text().includes('Scoring Artifact Detail'))
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('Replay scoring artifact detail', () => {
  it('loads all four read-only views from the ranking response source hash and applies prediction filters', async () => {
    const requests: Array<{ url: URL; method: string }> = []
    const fetchMock = vi.fn<typeof fetch>().mockImplementation((input, init) => {
      const url = new URL(String(input), 'http://localhost')
      const method = init?.method ?? 'GET'
      requests.push({ url, method })
      if (url.pathname.includes('/replay-rankings/optimal')) {
        return Promise.resolve(apiResponse(rankingResponse(sourceHash)))
      }
      if (url.pathname.includes('/replay-scoring/')) {
        return Promise.resolve(apiResponse(detailPayload(url, sourceHash)))
      }
      return Promise.resolve(apiResponse({ items: [], total_count: 0, limit: 50, offset: 0 }))
    })
    vi.stubGlobal('fetch', fetchMock)

    const wrapper = mount(ReplayHistoryPage)
    await flushPromises()
    await selectOptimalAndLoadRankings(wrapper)
    await detailButton(wrapper)?.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain(sourceHash)
    expect(wrapper.text()).toContain('detail-dataset · detail-v7')
    expect(wrapper.text()).toContain('HISTORY_CLOSED / HISTORY_NOT_AVAILABLE')
    expect(wrapper.text()).toContain('PREDICTION_CLOSED / PREDICTION_NOT_AVAILABLE')
    expect(wrapper.text()).toContain('IDENTITY_MISMATCH / TARGET_IDENTITY_MISMATCH')
    expect(wrapper.text()).toContain('Outcome not found')
    expect(wrapper.text()).toContain('Identity mismatch')
    expect(wrapper.text()).toContain('12')
    expect(wrapper.text()).toContain('API query: SUCCESS_WITH_DATA')
    expect(wrapper.text()).toContain(
      'Prize tiers and rank order come from the API; this page does not recalculate them.',
    )

    const initialDetailRequests = requests.filter(({ url }) => url.pathname.includes('/replay-scoring/'))
    expect(initialDetailRequests.map(({ url }) => url.pathname)).toEqual(
      expect.arrayContaining([
        `/api/v1/replay-scoring/${sourceHash}`,
        `/api/v1/replay-scoring/${sourceHash}/predictions`,
        `/api/v1/replay-scoring/${sourceHash}/strategy-aggregates`,
        `/api/v1/replay-scoring/${sourceHash}/overall-aggregate`,
      ]),
    )
    expect(initialDetailRequests).toHaveLength(4)
    expect(initialDetailRequests.every(({ method }) => method === 'GET')).toBe(true)

    await wrapper.get('input[name="target_draw"]').setValue('113000120')
    await wrapper.get('input[name="strategy_id"]').setValue('strategy-alpha')
    await wrapper.get('input[name="status"]').setValue('IDENTITY_MISMATCH')
    await wrapper.get('input[name="tier"]').setValue('TIER_6')
    await wrapper.findAll('form').at(-1)?.trigger('submit')
    await flushPromises()

    const filteredRequest = requests.find(
      ({ url }) => url.pathname === `/api/v1/replay-scoring/${sourceHash}/predictions` && url.search,
    )
    expect(filteredRequest?.url.searchParams.get('target_draw')).toBe('113000120')
    expect(filteredRequest?.url.searchParams.get('strategy_id')).toBe('strategy-alpha')
    expect(filteredRequest?.url.searchParams.get('status')).toBe('IDENTITY_MISMATCH')
    expect(filteredRequest?.url.searchParams.get('tier')).toBe('TIER_6')
    expect(requests.every(({ method }) => method === 'GET')).toBe(true)
    wrapper.unmount()
  })

  it('rejects an invalid source hash in the ranking response without issuing detail requests', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockImplementation((input) => {
      const url = new URL(String(input), 'http://localhost')
      if (url.pathname.includes('/replay-rankings/optimal')) {
        return Promise.resolve(apiResponse(rankingResponse('invalid-hash')))
      }
      return Promise.resolve(apiResponse({ items: [], total_count: 0, limit: 50, offset: 0 }))
    })
    vi.stubGlobal('fetch', fetchMock)

    const wrapper = mount(ReplayHistoryPage)
    await flushPromises()
    await selectOptimalAndLoadRankings(wrapper)
    fetchMock.mockClear()
    await detailButton(wrapper)?.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('does not contain a valid source scoring artifact SHA-256')
    expect(fetchMock).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('shows empty predictions and aggregate rows without inventing values', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockImplementation((input) => {
      const url = new URL(String(input), 'http://localhost')
      if (url.pathname.includes('/replay-rankings/optimal')) {
        return Promise.resolve(apiResponse(rankingResponse(sourceHash)))
      }
      if (url.pathname.endsWith('/predictions') || url.pathname.endsWith('/strategy-aggregates')) {
        return Promise.resolve(apiResponse([]))
      }
      if (url.pathname.includes('/replay-scoring/')) {
        return Promise.resolve(apiResponse(detailPayload(url, sourceHash)))
      }
      return Promise.resolve(apiResponse({ items: [], total_count: 0, limit: 50, offset: 0 }))
    })
    vi.stubGlobal('fetch', fetchMock)

    const wrapper = mount(ReplayHistoryPage)
    await flushPromises()
    await selectOptimalAndLoadRankings(wrapper)
    await detailButton(wrapper)?.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('No strategy aggregate rows are available.')
    expect(wrapper.text()).toContain('Strategy aggregates API: SUCCESS_EMPTY')
    expect(wrapper.text()).toContain('No predictions match these filters.')
    expect(wrapper.text()).toContain('Predictions API: SUCCESS_EMPTY')
    expect(wrapper.text()).not.toContain('Scored predictions: 0%')
    wrapper.unmount()
  })

  it.each([404, 422, 503])('shows HTTP %i and retries the same artifact detail request', async (status) => {
    let rootAttempts = 0
    const fetchMock = vi.fn<typeof fetch>().mockImplementation((input) => {
      const url = new URL(String(input), 'http://localhost')
      if (url.pathname.includes('/replay-rankings/optimal')) {
        return Promise.resolve(apiResponse(rankingResponse(sourceHash)))
      }
      if (url.pathname === `/api/v1/replay-scoring/${sourceHash}` && rootAttempts++ === 0) {
        return Promise.resolve(apiResponse({ error_code: 'SCORING_ERROR', message: 'mocked failure' }, status))
      }
      if (url.pathname.includes('/replay-scoring/')) {
        return Promise.resolve(apiResponse(detailPayload(url, sourceHash)))
      }
      return Promise.resolve(apiResponse({ items: [], total_count: 0, limit: 50, offset: 0 }))
    })
    vi.stubGlobal('fetch', fetchMock)

    const wrapper = mount(ReplayHistoryPage)
    await flushPromises()
    await selectOptimalAndLoadRankings(wrapper)
    await detailButton(wrapper)?.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain(`${status}`)
    expect(wrapper.text()).toContain(status === 503 ? 'API_UNAVAILABLE' : 'HTTP_ERROR')
    expect(wrapper.text()).toContain('mocked failure')
    await wrapper.findAll('button').find((button) => button.text() === 'Retry scoring detail')?.trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('detail-dataset · detail-v7')
    expect(wrapper.text()).not.toContain('Retry scoring detail')
    wrapper.unmount()
  })

  it('distinguishes an unconfigured scoring provider from an unavailable service', async () => {
    let rootAttempts = 0
    const fetchMock = vi.fn<typeof fetch>().mockImplementation((input) => {
      const url = new URL(String(input), 'http://localhost')
      if (url.pathname.includes('/replay-rankings/optimal')) {
        return Promise.resolve(apiResponse(rankingResponse(sourceHash)))
      }
      if (url.pathname === '/api/v1/replay-scoring/' + sourceHash && rootAttempts++ === 0) {
        return Promise.resolve(
          apiResponse(
            { error_code: 'REPLAY_SCORING_NOT_CONFIGURED', message: 'No scoring projection reader.' },
            503,
          ),
        )
      }
      if (url.pathname.includes('/replay-scoring/')) {
        return Promise.resolve(apiResponse(detailPayload(url, sourceHash)))
      }
      return Promise.resolve(apiResponse({ items: [], total_count: 0, limit: 50, offset: 0 }))
    })
    vi.stubGlobal('fetch', fetchMock)

    const wrapper = mount(ReplayHistoryPage)
    await flushPromises()
    await selectOptimalAndLoadRankings(wrapper)
    await detailButton(wrapper)?.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('SOURCE_NOT_CONFIGURED')
    expect(wrapper.text()).toContain('No scoring projection reader.')
    wrapper.unmount()
  })

  it('drops a delayed old artifact response after the ranking source changes', async () => {
    const firstHash = 'a'.repeat(64)
    const secondHash = 'b'.repeat(64)
    const delayedFirstResponses: Array<() => void> = []
    const fetchMock = vi.fn<typeof fetch>().mockImplementation((input) => {
      const url = new URL(String(input), 'http://localhost')
      if (url.pathname.includes('/replay-rankings/optimal')) {
        const requestedHash = url.searchParams.get('scoring_artifact_sha256') ?? firstHash
        return Promise.resolve(apiResponse(rankingResponse(requestedHash)))
      }
      if (url.pathname.includes('/replay-scoring/')) {
        const requestedHash = url.pathname.split('/')[4] ?? firstHash
        if (requestedHash === firstHash) {
          return new Promise<Response>((resolve) => {
            delayedFirstResponses.push(() => resolve(apiResponse(detailPayload(url, firstHash, 'old-dataset'))))
          })
        }
        return Promise.resolve(apiResponse(detailPayload(url, secondHash, 'new-dataset')))
      }
      return Promise.resolve(apiResponse({ items: [], total_count: 0, limit: 50, offset: 0 }))
    })
    vi.stubGlobal('fetch', fetchMock)

    const wrapper = mount(ReplayHistoryPage)
    await flushPromises()
    await selectOptimalAndLoadRankings(wrapper, firstHash)
    await detailButton(wrapper)?.trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('Loading scoring artifact, predictions, and aggregates…')
    expect(delayedFirstResponses).toHaveLength(4)

    await wrapper.get('input[name="scoring_artifact_sha256"]').setValue(secondHash)
    await wrapper.findAll('form')[0]?.trigger('submit')
    await flushPromises()
    await detailButton(wrapper)?.trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('new-dataset · detail-v7')

    for (const resolve of delayedFirstResponses) resolve()
    await flushPromises()
    expect(wrapper.text()).toContain('new-dataset · detail-v7')
    expect(wrapper.text()).not.toContain('old-dataset')
    wrapper.unmount()
  })
})
