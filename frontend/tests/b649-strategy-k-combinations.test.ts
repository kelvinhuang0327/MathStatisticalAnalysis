// @vitest-environment jsdom

import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  fetchB649Combinations,
  fetchB649StrategyK,
} from '../src/api/b649StrategyKCombinations'
import B649StrategyKCombinationsPage from '../src/features/b649-strategy-k-combinations/B649StrategyKCombinationsPage.vue'

let fetchMock: ReturnType<typeof vi.fn<typeof fetch>>

function apiResponse(payload: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: vi.fn().mockResolvedValue(payload),
  } as unknown as Response
}

function strategySummary() {
  return {
    authority_task_tree: 'a'.repeat(64),
    authority_full_output_tree: 'b'.repeat(64),
    matrix_row_count: 6624,
    supported_k_values: [1, 2, 3, 4, 5, 6],
    supported_criteria: [
      'M1_PLUS',
      'M2_PLUS',
      'M3_PLUS',
      'M4_PLUS',
      'M5_PLUS',
      'M6_PLUS',
      'SPECIAL_HIT',
      'M2_PLUS_SPECIAL',
      'M3_PLUS_SPECIAL',
      'M4_PLUS_SPECIAL',
      'M5_PLUS_SPECIAL',
      'M6_PLUS_SPECIAL',
    ],
    windows: [
      { window_kind: 'LONG', window_role: 'PRIMARY_EVIDENCE', requested_draw_count: 750, default_emphasis: true },
      { window_kind: 'MEDIUM', window_role: 'STABILITY_CONFIRMATION', requested_draw_count: 300, default_emphasis: false },
      { window_kind: 'SHORT', window_role: 'DEGRADATION_VETO', requested_draw_count: 50, default_emphasis: false },
      { window_kind: 'FULL_HISTORY', window_role: 'REFERENCE_ONLY', requested_draw_count: null, default_emphasis: false },
    ],
    strategies: [
      {
        strategy_id: 'strategy_available',
        strategy_version: 'v0.1',
        availability: 'MATRIX_AVAILABLE',
        availability_reason: 'one canonical producer-ordered strategy-level emission is available',
        response_shape: 'SINGLE_TICKET',
        native_ticket_count: 1,
      },
      {
        strategy_id: 'strategy_portfolio',
        strategy_version: 'v0.1',
        availability: 'PORTFOLIO_ORDER_AGGREGATION_NOT_DEFINED',
        availability_reason: 'repository exposes multiple native tickets and no canonical ordering',
        response_shape: 'PORTFOLIO',
        native_ticket_count: 5,
      },
    ],
    current_executable_strategy_count: 2,
    matrix_available_strategy_count: 1,
    matrix_unavailable_strategy_count: 1,
    historical_accounted_identity_count: 133,
    measurement_mode: 'CANDIDATE_COVERAGE',
    window_policy_version: 'STRATEGY_SUCCESS_WINDOWS_V1',
    duplicate_handling_policy: 'PRESERVE_FIRST_OCCURRENCE',
    nested_windows_independent: false,
    predictive_advantage_claimed: false,
    research_disclaimer: 'Historical candidate coverage only.',
  }
}

function strategyPage(items = [strategyRecord()]) {
  return {
    items,
    total: items.length,
    limit: 25,
    offset: 0,
    requested_k: 6,
    window_kind: 'LONG',
    window_role: 'PRIMARY_EVIDENCE',
    criterion: 'M2_PLUS',
    sort: 'OBSERVED_MINUS_BASELINE_DESC',
    ranking_label: 'Historical best under current filters',
    measurement_mode: 'CANDIDATE_COVERAGE',
    research_disclaimer: 'Historical candidate coverage only.',
  }
}

function strategyRecord() {
  return {
    strategy_id: 'strategy_available',
    strategy_version: 'v0.1',
    requested_k: 6,
    effective_unique_k_counts: [{ effective_unique_k: 6, observation_count: 750 }],
    criterion: 'M2_PLUS',
    window_kind: 'LONG',
    window_role: 'PRIMARY_EVIDENCE',
    requested_draw_count: 750,
    source_observation_count: 750,
    eligible_observation_count: 750,
    excluded_observation_count: 0,
    success_numerator: 123,
    success_denominator: 750,
    random_baseline_numerator: 150841,
    random_baseline_denominator: 998844,
    observed_minus_baseline: 'ABOVE_RANDOM',
    first_target_draw: '109000001',
    last_target_draw: '115000069',
    evaluation_status: 'COMPLETE',
    measurement_mode: 'CANDIDATE_COVERAGE',
    window_policy_version: 'STRATEGY_SUCCESS_WINDOWS_V1',
    nested_windows_independent: false,
  }
}

function combinationSummary() {
  return {
    authority_task_tree: 'c'.repeat(64),
    sealed_top_candidate_count: 3200,
    proxy_modes: [
      { proxy_mode: 'A', proxy_label: 'CURRENT_PORTFOLIO_VOTE_PROXY' },
      { proxy_mode: 'C', proxy_label: 'TRAILING_WINDOW_FREQUENCY_PROXY' },
    ],
    member_counts: [2, 3],
    windows: [
      { window_kind: 'LONG_750', window_role: 'PRIMARY_EVIDENCE', requested_draw_count: 750, default_emphasis: true },
      { window_kind: 'MID_300', window_role: 'STABILITY_CONFIRMATION', requested_draw_count: 300, default_emphasis: false },
      { window_kind: 'SHORT_50', window_role: 'DEGRADATION_VETO', requested_draw_count: 50, default_emphasis: false },
      { window_kind: 'FULL', window_role: 'REFERENCE_ONLY', requested_draw_count: null, default_emphasis: false },
    ],
    supported_criteria: [
      'M1_PLUS',
      'M2_PLUS',
      'M3_PLUS',
      'M4_PLUS',
      'M5_PLUS',
      'M6',
      'SPECIAL_HIT',
      'M1_PLUS_SPECIAL',
      'M2_PLUS_SPECIAL',
      'M3_PLUS_SPECIAL',
      'M4_PLUS_SPECIAL',
      'M5_PLUS_SPECIAL',
    ],
    source_scope: 'SEALED_TOP_20_PER_PROXY_MEMBER_COUNT_WINDOW_CRITERION',
    full_projection_sent_to_browser: false,
    predictive_advantage_claimed: false,
    research_disclaimer: 'Sealed historical Top 20 only.',
  }
}

function combinationPage(items = [combinationRecord()]) {
  return {
    items,
    total: items.length,
    limit: 25,
    offset: 0,
    proxy_mode: 'A',
    member_count: 2,
    window: 'LONG_750',
    window_role: 'PRIMARY_EVIDENCE',
    criterion: 'M2_PLUS',
    sort: 'SEALED_RANK_ASC',
    ranking_label: 'Sealed historical rank under current filters',
    source_scope: 'SEALED_TOP_20_PER_PROXY_MEMBER_COUNT_WINDOW_CRITERION',
    research_disclaimer: 'Sealed historical Top 20 only.',
  }
}

function combinationRecord() {
  return {
    proxy_mode: 'A',
    proxy_label: 'CURRENT_PORTFOLIO_VOTE_PROXY',
    member_count: 2,
    member_strategy_ids: ['strategy_a', 'strategy_b'],
    combination_id: 'PAIR_000001',
    evaluation_window: 'LONG_750',
    criterion: 'M2_PLUS',
    sealed_rank: 1,
    eligible_draws: 720,
    success_numerator: 100,
    success_denominator: 720,
    observed_rate: '0.138888888888888889',
    exact_random_baseline_numerator: 150841,
    exact_random_baseline_denominator: 998844,
    random_baseline_rate: '0.151015575005706599',
    descriptive_delta: '-0.012126686116817710',
    evaluation_status: 'EVALUABLE',
    evaluation_reason: 'PASS',
    long_delta_sign: 'NEGATIVE',
    mid_delta_sign: 'POSITIVE',
    short_delta_sign: 'POSITIVE',
    positive_window_count: 2,
    minimum_delta: '-0.012126686116817710',
    delta_range: '0.020000000000000000',
    cross_window_stable_positive: false,
    historical_search_only: true,
    predictive_advantage_claimed: false,
    prospective_validation_required: true,
    candidate_disposition: 'PROSPECTIVE_CANDIDATES_ONLY',
  }
}

function evidenceStatus() {
  return {
    observer_task_tree: 'd'.repeat(64),
    historical_evidence_status: 'AVAILABLE',
    pre_freeze_date_unseen_holdout_count: 6,
    post_freeze_date_prospective_count: 0,
    observation_count: 6,
    observation_start_draw: '115000070',
    latest_observed_draw: '115000075',
    checkpoints: [50, 100, 200],
    checkpoints_reached: [],
    primary_outcome: 'M2_PLUS',
    c_forward_status: 'C_PROXY_HORIZON_NOT_FROZEN',
    c_forward_reason: 'No single trailing horizon is frozen.',
    holdout_used_to_rerank_historical_results: false,
    predictive_advantage_claimed: false,
  }
}

beforeEach(() => {
  fetchMock = vi.fn<typeof fetch>()
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => vi.unstubAllGlobals())

function installPageFetch(options: { observerUnavailable?: boolean } = {}): void {
  fetchMock.mockImplementation((input) => {
    const url = String(input)
    if (url.endsWith('/strategy-k/summary')) return Promise.resolve(apiResponse(strategySummary()))
    if (url.includes('/strategy-k?')) return Promise.resolve(apiResponse(strategyPage()))
    if (url.endsWith('/combinations/summary')) return Promise.resolve(apiResponse(combinationSummary()))
    if (url.includes('/combinations?')) return Promise.resolve(apiResponse(combinationPage()))
    if (url.endsWith('/evidence-status')) {
      return Promise.resolve(
        options.observerUnavailable
          ? apiResponse({ error_code: 'B649_OBSERVER_AUTHORITY_UNAVAILABLE', message: 'observer absent' }, 503)
          : apiResponse(evidenceStatus()),
      )
    }
    throw new Error(`Unexpected URL: ${url}`)
  })
}

describe('B649 Strategy-K and combination API', () => {
  it('serializes fixed comparable filters and bounded pagination parameters', async () => {
    fetchMock
      .mockResolvedValueOnce(apiResponse(strategyPage()))
      .mockResolvedValueOnce(apiResponse(combinationPage()))

    await fetchB649StrategyK({
      requestedK: 6,
      windowKind: 'LONG',
      criterion: 'M2_PLUS',
      q: 'strategy_a',
      sort: 'OBSERVED_MINUS_BASELINE_DESC',
      limit: 25,
      offset: 0,
    })
    await fetchB649Combinations({
      proxyMode: 'C',
      memberCount: 3,
      window: 'MID_300',
      criterion: 'M3_PLUS',
      memberSearch: 'strategy_b',
      sort: 'COMBINATION_ID_ASC',
      limit: 20,
      offset: 5,
    })

    const strategyUrl = new URL(String(fetchMock.mock.calls[0]?.[0]), 'http://localhost')
    expect(Object.fromEntries(strategyUrl.searchParams)).toEqual({
      requested_k: '6',
      window_kind: 'LONG',
      criterion: 'M2_PLUS',
      q: 'strategy_a',
      sort: 'OBSERVED_MINUS_BASELINE_DESC',
      limit: '25',
      offset: '0',
    })
    const combinationUrl = new URL(String(fetchMock.mock.calls[1]?.[0]), 'http://localhost')
    expect(Object.fromEntries(combinationUrl.searchParams)).toEqual({
      proxy_mode: 'C',
      member_count: '3',
      window: 'MID_300',
      criterion: 'M3_PLUS',
      member_search: 'strategy_b',
      sort: 'COMBINATION_ID_ASC',
      limit: '20',
      offset: '5',
    })
  })
})

describe('B649StrategyKCombinationsPage', () => {
  it('shows authority-driven availability and keeps observer failure isolated', async () => {
    installPageFetch({ observerUnavailable: true })
    const wrapper = mount(B649StrategyKCombinationsPage)
    await flushPromises()

    expect(wrapper.get('[data-testid="strategy-k-summary"]').text()).toContain('6624')
    expect(wrapper.text()).toContain('PORTFOLIO_ORDER_AGGREGATION_NOT_DEFINED')
    await wrapper.get('.availability-section select').setValue('MATRIX_AVAILABLE')
    expect(wrapper.text()).toContain('1 / 2')
    await wrapper.findAll('[role="tab"]')[2]?.trigger('click')
    expect(wrapper.text()).toContain('Observer evidence 目前不可用')
    expect(wrapper.text()).toContain('Strategy-K 與組合歷史 views 仍可獨立使用')
    wrapper.unmount()
  })

  it('queries Strategy-K only after fixed filters and renders canonical fractions', async () => {
    installPageFetch()
    const wrapper = mount(B649StrategyKCombinationsPage)
    await flushPromises()

    const selects = wrapper.get('[data-testid="strategy-k-form"]').findAll('select')
    await selects[0]?.setValue('6')
    await selects[2]?.setValue('M2_PLUS')
    await selects[3]?.setValue('OBSERVED_MINUS_BASELINE_DESC')
    await wrapper.get('[data-testid="strategy-k-form"]').trigger('submit')
    await flushPromises()

    const request = fetchMock.mock.calls
      .map((call) => String(call[0]))
      .find((url) => url.includes('/strategy-k?'))
    expect(request).toContain('requested_k=6')
    expect(request).toContain('window_kind=LONG')
    expect(request).toContain('criterion=M2_PLUS')
    expect(wrapper.text()).toContain('123 / 750')
    expect(wrapper.text()).toContain('150841 / 998844')
    expect(wrapper.text()).toContain('K6 × 750')
    expect(wrapper.text()).toContain('Historical best under current filters')
    wrapper.unmount()
  })

  it('queries only the sealed pair pool and displays evidence status honestly', async () => {
    installPageFetch()
    const wrapper = mount(B649StrategyKCombinationsPage)
    await flushPromises()

    await wrapper.findAll('[role="tab"]')[1]?.trigger('click')
    const form = wrapper.get('[data-testid="combination-form"]')
    const selects = form.findAll('select')
    await selects[0]?.setValue('A')
    await selects[1]?.setValue('2')
    await selects[3]?.setValue('M2_PLUS')
    await form.trigger('submit')
    await flushPromises()

    const request = fetchMock.mock.calls
      .map((call) => String(call[0]))
      .find((url) => url.includes('/combinations?'))
    expect(request).toContain('proxy_mode=A')
    expect(request).toContain('member_count=2')
    expect(request).toContain('window=LONG_750')
    expect(wrapper.text()).toContain('PAIR_000001')
    expect(wrapper.text()).toContain('150841 / 998844')

    await wrapper.findAll('[role="tab"]')[2]?.trigger('click')
    expect(wrapper.get('[data-testid="evidence-summary"]').text()).toContain('6')
    expect(wrapper.get('[data-testid="evidence-summary"]').text()).toContain('0')
    expect(wrapper.text()).toContain('C_PROXY_HORIZON_NOT_FROZEN')
    expect(wrapper.text()).toContain('PREDICTIVE_ADVANTAGE_CLAIMED = NO')
    wrapper.unmount()
  })
})
