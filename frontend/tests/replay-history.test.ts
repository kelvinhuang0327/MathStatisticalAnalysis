// @vitest-environment jsdom

import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'

import ReplayHistoryPage from '../src/features/replay-history/ReplayHistoryPage.vue'

const historicalRun = {
  run_id: 'run-explicit-1',
  import_identity_sha256: 'a'.repeat(64),
  manifest_sha256: 'b'.repeat(64),
  contract_version: '1.0.0',
  source_kind: 'HISTORICAL_RESULTS',
  source_repository: 'kelvinhuang0327/MathStatisticalAnalysis',
  source_commit_oid: 'c'.repeat(40),
  source_artifact_sha256: 'd'.repeat(64),
  dataset_identity: 'historical-big-lotto-r1',
  dataset_sha256: 'e'.repeat(64),
  legacy_run_id: null,
  lottery_type: 'BIG_LOTTO',
  started_at: '2026-07-20T00:00:00Z',
  completed_at: '2026-07-20T01:00:00Z',
  status: 'COMPLETED',
  strategy_count: 1,
  draw_count: 40,
  portfolio_count: 1,
  is_idempotent_replay: false,
}

function runPage(): { items: unknown[]; total_count: number; limit: number; offset: number } {
  return { items: [historicalRun], total_count: 1, limit: 50, offset: 0 }
}

function apiResponse(payload: unknown, status = 200): Response {
  return {
    ok: status < 400,
    status,
    json: vi.fn().mockResolvedValue(payload),
  } as unknown as Response
}

const strategySummary = {
  strategy_snapshot_id: 'snap-1',
  strategy_id: 'biglotto_social_wisdom_anti_popularity',
  effective_strategy_id: 'biglotto_social_wisdom_anti_popularity',
  strategy_version: 'v1',
  replicate: 1,
  identity_kind: 'CANONICAL',
  governance_status: 'ONLINE',
  alias_of_strategy_id: null,
  equivalence_group: null,
  nested_prefix_supported: true,
  ticket_count: 10,
  evaluated_draws: 40,
  complete_portfolios: 40,
  m4plus_hit_count: 4,
}

const replayPortfolio = {
  portfolio_id: 'portfolio-1',
  run_id: 'run-explicit-1',
  strategy_snapshot_id: 'snap-1',
  strategy_id: 'biglotto_social_wisdom_anti_popularity',
  effective_strategy_id: 'biglotto_social_wisdom_anti_popularity',
  strategy_version: 'v1',
  replicate: 1,
  constructor_identifier: 'ORDERED_PREFIX',
  source_record_locator: null,
  portfolio_sha256: 'f'.repeat(64),
  prefix10_sha256: 'a'.repeat(64),
  prefix15_sha256: 'b'.repeat(64),
  target_draw: {
    draw_number: '113000060',
    draw_date: '2026-07-16',
    main_numbers: [1, 3, 9, 17, 24, 49],
    special_numbers: [7],
    draw_sha256: 'c'.repeat(64),
  },
  cutoff_draw: {
    draw_number: '113000059',
    draw_date: '2026-07-13',
    main_numbers: [2, 4, 6, 8, 10, 12],
    special_numbers: [5],
    draw_sha256: 'd'.repeat(64),
  },
  requested_ticket_count: 10,
  m4plus: true,
  tickets: [
    {
      portfolio_position: 1,
      main_numbers: [1, 3, 9, 17, 24, 49],
      special_numbers: [7],
      main_hit_count: 4,
      special_hit: true,
      ticket_sha256: 'e'.repeat(64),
      legacy_row_id: null,
      legacy_storage_bet_index: null,
    },
  ],
}

const rankingResponse = {
  artifact_schema_version: 'v1',
  ranking_policy_id: 'BIG_LOTTO_TIER_LEXICOGRAPHIC_COUNTS_V1',
  source_scoring_artifact_payload_sha256: 'a'.repeat(64),
  source_replay_artifact_payload_sha256: 'b'.repeat(64),
  dataset_id: 'historical-big-lotto-r1',
  dataset_version: 'v1',
  lottery_type: 'BIG_LOTTO',
  target_count: 40,
  strategy_count: 5,
  top_k: 10,
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
          members: [{ source_position: 1, strategy_id: 'biglotto_social_wisdom_anti_popularity', strategy_version: 'v1' }],
          target_count: 40,
          total_ticket_count: 40,
          scored_count: 40,
          history_closed_count: 40,
          prediction_closed_count: 40,
          target_outcome_not_found_count: 0,
          target_identity_mismatch_count: 0,
          first_prize_count: 0,
          second_prize_count: 0,
          third_prize_count: 0,
          fourth_prize_count: 4,
          fifth_prize_count: 6,
          sixth_prize_count: 10,
          seventh_prize_count: 8,
          general_prize_count: 0,
          no_prize_count: 12,
          winning_ticket_count: 28,
          candidate_sha256: 'f'.repeat(64),
        },
      ],
    },
  ],
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('ReplayHistoryPage overview replay', () => {
  it('loads runs, shows strategies with a screen-safe lottery label, and drills into replay', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockImplementation((input) => {
      const url = String(input)
      if (url.includes('/historical-results/runs/run-explicit-1/strategies')) {
        return Promise.resolve(
          apiResponse({ run_id: 'run-explicit-1', ticket_count: 10, items: [strategySummary] }),
        )
      }
      if (url.includes('/historical-results/runs/run-explicit-1/replay')) {
        return Promise.resolve(
          apiResponse({
            run_id: 'run-explicit-1',
            strategy_id: 'biglotto_social_wisdom_anti_popularity',
            ticket_count: 10,
            items: [replayPortfolio],
            total_count: 1,
            limit: 20,
            offset: 0,
          }),
        )
      }
      if (url.includes('/historical-results/runs')) {
        return Promise.resolve(apiResponse(runPage()))
      }
      throw new Error(`Unexpected fetch: ${url}`)
    })
    vi.stubGlobal('fetch', fetchMock)

    const wrapper = mount(ReplayHistoryPage)
    await flushPromises()

    expect(wrapper.text()).toContain('B649')
    expect(wrapper.text()).not.toContain('BIG_LOTTO')

    await wrapper.get('select[name="run_id"]').setValue('run-explicit-1')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.text()).toContain('biglotto_social_wisdom_anti_popularity')
    expect(wrapper.text()).toContain('10.0%')

    await wrapper.get('[data-testid="strategy-row-biglotto_social_wisdom_anti_popularity"] button').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('113000060')
    expect(wrapper.text()).toContain('YES')
    wrapper.unmount()
  })

  it('surfaces a load error without crashing', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      apiResponse({ error_code: 'HISTORICAL_RESULTS_UNAVAILABLE', message: 'unavailable' }, 503),
    )
    vi.stubGlobal('fetch', fetchMock)

    const wrapper = mount(ReplayHistoryPage)
    await flushPromises()

    expect(wrapper.text()).toContain('unavailable')
    wrapper.unmount()
  })
})

describe('ReplayHistoryPage optimal replay', () => {
  it('rejects a malformed sha256 without issuing a request', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(apiResponse(runPage()))
    vi.stubGlobal('fetch', fetchMock)

    const wrapper = mount(ReplayHistoryPage)
    await flushPromises()
    fetchMock.mockClear()

    await wrapper.findAll('nav[aria-label="Replay history sections"] button')[1]?.trigger('click')
    await wrapper.get('input[name="scoring_artifact_sha256"]').setValue('not-a-sha')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.text()).toContain('Enter an exact lowercase 64-character SHA-256')
    expect(fetchMock).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('loads and displays rank-ordered candidates for a valid sha256', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockImplementation((input) => {
      const url = String(input)
      if (url.includes('/replay-rankings/optimal')) {
        return Promise.resolve(apiResponse(rankingResponse))
      }
      return Promise.resolve(apiResponse(runPage()))
    })
    vi.stubGlobal('fetch', fetchMock)

    const wrapper = mount(ReplayHistoryPage)
    await flushPromises()

    await wrapper.findAll('nav[aria-label="Replay history sections"] button')[1]?.trigger('click')
    await wrapper.get('input[name="scoring_artifact_sha256"]').setValue('a'.repeat(64))
    await wrapper.get('input[name="top_k"]').setValue(10)
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.text()).toContain('B649')
    expect(wrapper.text()).toContain('BIG_LOTTO_TIER_LEXICOGRAPHIC_COUNTS_V1')
    expect(wrapper.text()).toContain('28 / 40')
    wrapper.unmount()
  })
})
