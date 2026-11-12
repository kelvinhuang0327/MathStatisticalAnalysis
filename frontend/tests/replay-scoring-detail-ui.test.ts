// @vitest-environment jsdom

import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'

import ReplayHistoryPage from '../src/features/replay-history/ReplayHistoryPage.vue'

const scoringArtifactSha256 = 'a'.repeat(64)

function apiResponse(payload: unknown, status = 200): Response {
  return {
    ok: status < 400,
    status,
    json: vi.fn().mockResolvedValue(payload),
  } as unknown as Response
}

function importRunsResponse() {
  return { items: [], total_count: 0, limit: 50, offset: 0 }
}

function rankingResponse() {
  return {
    artifact_schema_version: 'v1',
    ranking_policy_id: 'FIXED_SOURCE_DESCRIPTIVE_POLICY_V1',
    source_scoring_artifact_payload_sha256: scoringArtifactSha256,
    source_replay_artifact_payload_sha256: 'b'.repeat(64),
    dataset_id: 'fixed-source-fixture',
    dataset_version: 'v1',
    lottery_type: 'BIG_LOTTO',
    target_count: 10,
    strategy_count: 2,
    top_k: 3,
    artifact_sha256: 'c'.repeat(64),
    groups: [
      {
        ticket_count: 2,
        status: 'RANKED',
        total_candidate_count: 2,
        candidates: [
          {
            rank: 1,
            ticket_count: 2,
            members: [{ source_position: 1, strategy_id: 'strategy-alpha', strategy_version: 'v1' }],
            target_count: 10,
            total_ticket_count: 10,
            scored_count: 10,
            history_closed_count: 0,
            prediction_closed_count: 0,
            target_outcome_not_found_count: 0,
            target_identity_mismatch_count: 0,
            first_prize_count: 0,
            second_prize_count: 0,
            third_prize_count: 0,
            fourth_prize_count: 1,
            fifth_prize_count: 2,
            sixth_prize_count: 3,
            seventh_prize_count: 0,
            general_prize_count: 0,
            no_prize_count: 4,
            winning_ticket_count: 6,
            candidate_sha256: 'd'.repeat(64),
          },
          {
            rank: 2,
            ticket_count: 2,
            members: [{ source_position: 2, strategy_id: 'strategy-beta', strategy_version: 'v2' }],
            target_count: 10,
            total_ticket_count: 10,
            scored_count: 9,
            history_closed_count: 1,
            prediction_closed_count: 0,
            target_outcome_not_found_count: 0,
            target_identity_mismatch_count: 0,
            first_prize_count: 0,
            second_prize_count: 0,
            third_prize_count: 1,
            fourth_prize_count: 1,
            fifth_prize_count: 2,
            sixth_prize_count: 1,
            seventh_prize_count: 0,
            general_prize_count: 0,
            no_prize_count: 4,
            winning_ticket_count: 5,
            candidate_sha256: 'e'.repeat(64),
          },
        ],
      },
    ],
  }
}

async function openOptimalReplay(wrapper: ReturnType<typeof mount>): Promise<void> {
  await wrapper.findAll('nav[aria-label="Replay history sections"] button')[1]?.trigger('click')
  await flushPromises()
}

async function submitRankingQuery(
  wrapper: ReturnType<typeof mount>,
  topK: number,
): Promise<void> {
  await wrapper.get('input[name="scoring_artifact_sha256"]').setValue(scoringArtifactSha256)
  await wrapper.get('input[name="top_k"]').setValue(topK)
  await wrapper.get('form').trigger('submit')
  await flushPromises()
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('Replay scoring artifact UI for the fixed source', () => {
  it('requests the selected artifact and top K, then renders candidates in rank order', async () => {
    const rankingRequests: URL[] = []
    const fetchMock = vi.fn<typeof fetch>().mockImplementation((input) => {
      const url = new URL(String(input), 'http://localhost')
      if (url.pathname === '/api/v1/historical-results/runs') {
        return Promise.resolve(apiResponse(importRunsResponse()))
      }
      if (url.pathname === '/api/v1/replay-rankings/optimal') {
        rankingRequests.push(url)
        return Promise.resolve(apiResponse(rankingResponse()))
      }
      throw new Error(`Unexpected fetch: ${url.pathname}`)
    })
    vi.stubGlobal('fetch', fetchMock)

    const wrapper = mount(ReplayHistoryPage)
    await flushPromises()
    await openOptimalReplay(wrapper)
    await submitRankingQuery(wrapper, 3)

    expect(rankingRequests).toHaveLength(1)
    expect(rankingRequests[0]?.searchParams.get('scoring_artifact_sha256')).toBe(scoringArtifactSha256)
    expect(rankingRequests[0]?.searchParams.get('top_k')).toBe('3')
    expect(wrapper.text()).toContain('B649')
    expect(wrapper.text()).toContain('FIXED_SOURCE_DESCRIPTIVE_POLICY_V1')
    expect(wrapper.findAll('tbody tr').map((row) => row.findAll('td').map((cell) => cell.text()))).toEqual([
      ['1', 'strategy-alpha', '6 / 10', '4', '10'],
      ['2', 'strategy-beta', '5 / 10', '4', '9'],
    ])
    wrapper.unmount()
  })

  it('shows a ranking API error without rendering stale candidate rows', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockImplementation((input) => {
      const url = new URL(String(input), 'http://localhost')
      if (url.pathname === '/api/v1/historical-results/runs') {
        return Promise.resolve(apiResponse(importRunsResponse()))
      }
      if (url.pathname === '/api/v1/replay-rankings/optimal') {
        return Promise.resolve(
          apiResponse({ error_code: 'RANKING_UNAVAILABLE', message: 'ranking service unavailable' }, 503),
        )
      }
      throw new Error(`Unexpected fetch: ${url.pathname}`)
    })
    vi.stubGlobal('fetch', fetchMock)

    const wrapper = mount(ReplayHistoryPage)
    await flushPromises()
    await openOptimalReplay(wrapper)
    await submitRankingQuery(wrapper, 3)

    expect(wrapper.text()).toContain('ranking service unavailable')
    expect(wrapper.findAll('tbody tr')).toHaveLength(0)
    wrapper.unmount()
  })
})
