// @vitest-environment jsdom

import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  fetchB649ResearchBacktestMethods,
  fetchB649ResearchBacktestRankings,
  fetchB649ResearchBacktestSummary,
  type B649ResearchBacktestMethod,
  type B649ResearchBacktestMethodsPage,
  type B649ResearchBacktestRanking,
  type B649ResearchBacktestRankingsPage,
  type B649ResearchBacktestSummary,
} from '../src/api/b649ResearchBacktests'
import V2BacktestResearchBoard from '../src/features/strategy-forecast-research/V2BacktestResearchBoard.vue'

const EXPECTED_SOURCE = {
  source_task_id: 'NUMBER2_D_LMS_HUMAN_BOARD_V2_INTEGRATION_20261102_R1',
  source_authority_commit: 'fe3aa81d3844ac11d4360447c243e90fe4a6613a',
  observed_checkout_head: 'b4e11ebd0981d549ce70055e70f8fbd0065cd2dd',
  source_manifest_sha256: 'aae584e9b4d991d549e1eacb378f5df7170c50ca3be804407cfaaed0f5125411',
}

afterEach(() => {
  vi.unstubAllGlobals()
})

function summary(overrides: Partial<B649ResearchBacktestSummary> = {}): B649ResearchBacktestSummary {
  return {
    ...EXPECTED_SOURCE,
    method_version_count: 305,
    inventory_count: 2968,
    ranking_count: 2818,
    metrics_availability_counts: { AVAILABLE: 2818, UNAVAILABLE: 60, NOT_APPLICABLE: 90 },
    research_status_counts: { COMPLETED: 2968 },
    unavailable_count: 60,
    not_applicable_count: 90,
    comparable_group_count: 224,
    duplicate_output_groups: 48,
    windows: ['FULL', 'RECENT_750', 'RECENT_300', 'RECENT_50'],
    K_values: [5],
    prize_metrics: ['OFFICIAL_ANY_PRIZE'],
    cohorts: ['COHORT_A'],
    comparison_group_count: 504,
    ...overrides,
  }
}

function method(index: number, overrides: Partial<B649ResearchBacktestMethod> = {}): B649ResearchBacktestMethod {
  const unavailable = index % 2 === 0
  return {
    method_id: `method-${index}`,
    method_version: 'v1',
    method_family: 'fixture-family',
    source_identity: { source_task_id: EXPECTED_SOURCE.source_task_id },
    task_id: EXPECTED_SOURCE.source_task_id,
    evaluation_cohort: 'COHORT_A',
    history_window: 'FULL',
    K: 5,
    official_prize_metric: 'OFFICIAL_ANY_PRIZE',
    successful_draws: null,
    eligible_draws: null,
    success_rate: null,
    baseline_identity: 'OFFICIAL_RANDOM_BASELINE',
    baseline_success_rate: null,
    paired_difference: null,
    research_status: 'COMPLETED',
    original_advance_decision: 'DO_NOT_ADVANCE',
    artifact_locator: 'fixture/artifact.json',
    artifact_sha256: 'a'.repeat(64),
    backtest_artifact_locator: 'fixture/backtest.json',
    backtest_artifact_sha256: 'b'.repeat(64),
    metrics_availability: unavailable ? 'UNAVAILABLE' : 'NOT_APPLICABLE',
    metrics_unavailable_reason: unavailable ? 'FIXTURE_METRIC_UNAVAILABLE' : 'FIXTURE_NOT_APPLICABLE',
    shared_output_identity: index === 0 ? 'shared-ticket-identity' : '',
    method_type: 'FIXTURE_METHOD',
    auxiliary_statistics_json: {},
    arm_identity: `arm-${index}`,
    lottery_type: 'BIG_LOTTO',
    window: 'FULL',
    prize_metric: 'OFFICIAL_ANY_PRIZE',
    wins: null,
    baseline_rate: null,
    delta_percentage_points: null,
    research_class: 'EXPLORATORY',
    target_draw_set_identity: 'draw-set-a',
    comparison_rank: null,
    comparison_group_id: 'group-a',
    comparison_status: 'UNAVAILABLE',
    original_board_metrics_availability: unavailable ? 'UNAVAILABLE' : 'NOT_APPLICABLE',
    original_board_metrics_unavailable_reason: 'FIXTURE_SOURCE_REASON',
    board_original_advance_decision: 'DO_NOT_ADVANCE',
    source_identity_chain: [{ source_task_id: EXPECTED_SOURCE.source_task_id }],
    source_shared_output_identities: index === 0 ? ['shared-ticket-identity'] : [],
    source_lineage: [{ source_file: 'fixture.csv', source_record_id: `record-${index}` }],
    source_record_id: `record-${index}`,
    source_inventory_json: {},
    owner_long_rank: '',
    owner_middle_rank: '',
    owner_short_rank: '',
    owner_selected: '',
    owner_reason: '',
    ...overrides,
  }
}

function ranking(
  index: number,
  group: 'A' | 'B' = 'A',
  overrides: Partial<B649ResearchBacktestRanking> = {},
): B649ResearchBacktestRanking {
  const drawSet = group === 'A' ? 'draw-set-a' : 'draw-set-b'
  const denominator = group === 'A' ? 10 : 20
  return {
    method_id: `ranked-method-${index}`,
    method_version: 'v1',
    arm_identity: `arm-${index}`,
    method_family: 'fixture-family',
    task_id: EXPECTED_SOURCE.source_task_id,
    source_identity: { source_task_id: EXPECTED_SOURCE.source_task_id },
    source_identity_chain: [{ source_task_id: EXPECTED_SOURCE.source_task_id }],
    lottery_type: 'BIG_LOTTO',
    evaluation_cohort: 'COHORT_A',
    target_draw_set_identity: drawSet,
    window: 'FULL',
    K: 5,
    prize_metric: 'OFFICIAL_ANY_PRIZE',
    wins: 2,
    eligible_draws: denominator,
    success_rate: '0.20',
    comparison_rank: 4,
    rank_basis_identity_count: 12,
    shared_output_identity: index === 0 ? 'shared-ticket-identity' : '',
    source_shared_output_identities: index === 0 ? ['shared-ticket-identity'] : [],
    baseline_identity: 'OFFICIAL_RANDOM_BASELINE',
    baseline_rate: '0.10',
    delta_percentage_points: '0.10',
    research_status: 'COMPLETED',
    research_class: 'EXPLORATORY',
    original_advance_decision: 'DO_NOT_ADVANCE',
    original_board_metrics_availability: 'AVAILABLE',
    original_board_metrics_unavailable_reason: '',
    board_original_advance_decision: 'DO_NOT_ADVANCE',
    comparison_status: 'COMPARABLE',
    comparison_notes: 'fixture note',
    artifact_locator: 'fixture/rank.json',
    artifact_sha256: 'c'.repeat(64),
    source_rank: 2,
    source_lineage: [{ source_file: 'rankings.csv', source_record_id: `rank-${index}` }],
    ...overrides,
  }
}

function methodsPage(
  items: B649ResearchBacktestMethod[],
  offset: number,
  total: number,
  limit = 50,
): B649ResearchBacktestMethodsPage {
  return { items, offset, total, limit }
}

function rankingsPage(
  items: B649ResearchBacktestRanking[],
  input: {
    cohort?: string
    K?: number
    window?: B649ResearchBacktestRanking['window']
    prize_metric?: string
    target_draw_set_identity?: string | null
    eligible_draws?: number | null
    total: number
    limit: number
    offset: number
    comparison_group_count: number
  },
): B649ResearchBacktestRankingsPage {
  return {
    items,
    cohort: input.cohort ?? 'COHORT_A',
    K: input.K ?? 5,
    window: input.window ?? 'FULL',
    prize_metric: input.prize_metric ?? 'OFFICIAL_ANY_PRIZE',
    target_draw_set_identity: input.target_draw_set_identity ?? null,
    eligible_draws: input.eligible_draws ?? null,
    total: input.total,
    limit: input.limit,
    offset: input.offset,
    comparison_group_count: input.comparison_group_count,
  }
}

function jsonResponse(payload: unknown, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => payload,
  }
}

function installBoardFetch(options: { empty?: boolean; invalidRanking?: boolean } = {}) {
  const allRankings = options.empty
    ? []
    : [
        ...Array.from({ length: 100 }, (_, index) => ranking(index, 'A')),
        ranking(100, 'B'),
      ]
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = new URL(String(input), 'http://localhost')
    const path = url.pathname
    if (path.endsWith('/summary')) return jsonResponse(summary())
    if (path.endsWith('/methods')) {
      const offset = Number(url.searchParams.get('offset') ?? '0')
      const limit = Number(url.searchParams.get('limit') ?? '50')
      const methodId = url.searchParams.get('method_id')
      const researchStatus = url.searchParams.get('research_status')
      if (methodId === 'missing-method') return jsonResponse(methodsPage([], 0, 0, limit))
      if (researchStatus && researchStatus !== 'COMPLETED') return jsonResponse(methodsPage([], 0, 0, limit))
      const total = 2968
      const items = Array.from({ length: Math.min(limit, total - offset) }, (_, index) => method(offset + index))
      return jsonResponse(methodsPage(items, offset, total, limit))
    }
    if (path.endsWith('/rankings')) {
      if (options.invalidRanking) {
        return jsonResponse({ error_code: 'INVALID_QUERY', message: 'cohort/K/window combination is invalid' }, 422)
      }
      const limit = Number(url.searchParams.get('limit') ?? '50')
      const offset = Number(url.searchParams.get('offset') ?? '0')
      const requestedWindow = url.searchParams.get('window') ?? 'FULL'
      const allForWindow = allRankings.map((row) => ({ ...row, window: requestedWindow as B649ResearchBacktestRanking['window'] }))
      const targetDrawSet = url.searchParams.get('target_draw_set_identity')
      const eligibleDraws = url.searchParams.get('eligible_draws')
      const selected = targetDrawSet === null
        ? allForWindow
        : allForWindow.filter((row) =>
            row.target_draw_set_identity === targetDrawSet &&
            row.eligible_draws === Number(eligibleDraws),
          )
      const pageItems = selected.slice(offset, offset + limit)
      const selectedGroups = new Set(selected.map((row) => `${row.target_draw_set_identity}:${row.eligible_draws}`))
      return jsonResponse(rankingsPage(pageItems, {
        cohort: url.searchParams.get('cohort') ?? 'COHORT_A',
        K: Number(url.searchParams.get('K') ?? '5'),
        window: requestedWindow as B649ResearchBacktestRanking['window'],
        prize_metric: url.searchParams.get('prize_metric') ?? 'OFFICIAL_ANY_PRIZE',
        target_draw_set_identity: targetDrawSet,
        eligible_draws: eligibleDraws === null ? null : Number(eligibleDraws),
        total: selected.length,
        limit,
        offset,
        comparison_group_count: selectedGroups.size,
      }))
    }
    throw new Error(`Unexpected request: ${url}`)
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

describe('B649 research backtest API client', () => {
  it('uses the generated summary, methods, and rankings contracts with paired comparison selectors', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse(summary()))
      .mockResolvedValueOnce(jsonResponse(methodsPage([], 0, 0)))
      .mockResolvedValueOnce(jsonResponse(rankingsPage([], {
        total: 0,
        limit: 50,
        offset: 0,
        comparison_group_count: 0,
        target_draw_set_identity: 'draw set/a',
        eligible_draws: 10,
      })))
    vi.stubGlobal('fetch', fetchMock)

    await fetchB649ResearchBacktestSummary()
    await fetchB649ResearchBacktestMethods({ limit: 50, offset: 0, method_id: 'method/a', research_status: 'COMPLETE' })
    await fetchB649ResearchBacktestRankings({
      cohort: 'COHORT_A',
      K: 5,
      window: 'RECENT_50',
      prize_metric: 'OFFICIAL_ANY_PRIZE',
      target_draw_set_identity: 'draw set/a',
      eligible_draws: 10,
      limit: 50,
      offset: 50,
    })

    expect(String(fetchMock.mock.calls[0]?.[0])).toBe('/api/v1/b649-research-backtests/summary')
    expect(new URL(String(fetchMock.mock.calls[1]?.[0]), 'http://localhost').searchParams.toString())
      .toBe('limit=50&offset=0&method_id=method%2Fa&research_status=COMPLETE')
    const rankingUrl = new URL(String(fetchMock.mock.calls[2]?.[0]), 'http://localhost')
    expect(rankingUrl.pathname).toBe('/api/v1/b649-research-backtests/rankings')
    expect(Object.fromEntries(rankingUrl.searchParams)).toEqual({
      cohort: 'COHORT_A',
      K: '5',
      window: 'RECENT_50',
      prize_metric: 'OFFICIAL_ANY_PRIZE',
      target_draw_set_identity: 'draw set/a',
      eligible_draws: '10',
      limit: '50',
      offset: '50',
    })

    await expect(fetchB649ResearchBacktestRankings({
      cohort: 'COHORT_A',
      K: 5,
      window: 'FULL',
      prize_metric: 'OFFICIAL_ANY_PRIZE',
      target_draw_set_identity: 'draw-set-a',
    })).rejects.toMatchObject({ kind: 'INVALID_REQUEST', errorCode: 'INCOMPLETE_COMPARISON_GROUP' })
    expect(fetchMock).toHaveBeenCalledTimes(3)
  })

  it('distinguishes 503, network, and malformed responses', async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(
      jsonResponse({ error_code: 'B649_RESEARCH_BOARD_V2_NOT_CONFIGURED', message: 'not configured' }, 503),
    )
    vi.stubGlobal('fetch', fetchMock)
    await expect(fetchB649ResearchBacktestSummary()).rejects.toMatchObject({
      status: 503,
      kind: 'UNAVAILABLE',
      errorCode: 'B649_RESEARCH_BOARD_V2_NOT_CONFIGURED',
    })

    fetchMock.mockRejectedValueOnce(new Error('offline'))
    await expect(fetchB649ResearchBacktestSummary()).rejects.toMatchObject({ status: 0, kind: 'NETWORK' })

    fetchMock.mockResolvedValueOnce(jsonResponse({ nope: true }))
    await expect(fetchB649ResearchBacktestSummary()).rejects.toMatchObject({ kind: 'MALFORMED_RESPONSE' })
  })
})

describe('V2 backtest research board', () => {
  it('requires a single comparison group and preserves source ranking, metrics, and Owner fields', async () => {
    const fetchMock = installBoardFetch()
    const wrapper = mount(V2BacktestResearchBoard)
    await flushPromises()
    await flushPromises()

    expect(wrapper.text()).toContain(EXPECTED_SOURCE.source_task_id)
    expect(wrapper.text()).toContain('來源身份已核對')
    const windows = wrapper.get('select[aria-label="V2 歷史窗口"]')
    expect(windows.findAll('option').map((option) => option.element.getAttribute('value')))
      .toEqual(['FULL', 'RECENT_750', 'RECENT_300', 'RECENT_50'])
    expect(wrapper.get('[role="status"]').text()).toContain('找到 2 個不同比較群組')
    expect(fetchMock.mock.calls.some(([input]) =>
      new URL(String(input), 'http://localhost').searchParams.has('target_draw_set_identity'),
    )).toBe(false)

    await wrapper.get('#v2-methods-tab').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('2968')
    expect(wrapper.text()).toContain('DO_NOT_ADVANCE（仍保留檢視）')
    expect(wrapper.text()).toContain('探索性研究 · EXPLORATORY')
    expect(wrapper.text()).toContain('共享輸出 · 非獨立研究')
    expect(wrapper.text()).toContain('UNAVAILABLE')
    expect(wrapper.text()).toContain('NOT_APPLICABLE')
    expect(wrapper.text()).toContain('長名次：（空白）')
    expect(wrapper.text()).toContain('中名次：（空白）')
    expect(wrapper.text()).toContain('短名次：（空白）')
    expect(wrapper.text()).toContain('已選擇：（空白）')
    expect(wrapper.text()).toContain('Owner 原因：（空白）')
    expect(wrapper.text()).not.toContain('0.00%')
    await wrapper.get('[aria-label="methods 分頁"] .v2-button:last-child').trigger('click')
    await flushPromises()
    expect(fetchMock.mock.calls.some(([input]) =>
      new URL(String(input), 'http://localhost').searchParams.get('offset') === '50' &&
      new URL(String(input), 'http://localhost').pathname.endsWith('/methods'),
    )).toBe(true)

    await wrapper.get('#v2-rankings-tab').trigger('click')
    const groupSelect = wrapper.get('select[aria-label="V2 必要比較群組"]')
    await groupSelect.setValue(JSON.stringify(['draw-set-a', 10]))
    await flushPromises()
    await flushPromises()
    const rows = wrapper.findAll('.v2-ranking-table tbody tr')
    expect(rows).toHaveLength(50)
    expect(rows[0]?.text()).toContain('ranked-method-0')
    expect(rows[1]?.text()).toContain('ranked-method-1')
    expect(rows[0]?.text()).toContain('4')
    expect(rows[1]?.text()).toContain('4')
    expect(rows[0]?.text()).toContain('2 / 10')
    expect(rows[0]?.text()).toContain('20.00%')
    expect(rows[0]?.text()).toContain('共享輸出 · 非獨立研究')

    await wrapper.get('[aria-label="rankings 分頁"] .v2-button:last-child').trigger('click')
    await flushPromises()
    const groupRequests = fetchMock.mock.calls
      .map(([input]) => new URL(String(input), 'http://localhost'))
      .filter((url) => url.pathname.endsWith('/rankings') && url.searchParams.has('target_draw_set_identity'))
    expect(groupRequests.some((url) =>
      url.searchParams.get('target_draw_set_identity') === 'draw-set-a' &&
      url.searchParams.get('eligible_draws') === '10' &&
      url.searchParams.get('offset') === '50',
    )).toBe(true)
    expect(groupRequests.every((url) => url.searchParams.get('eligible_draws') === '10')).toBe(true)
    wrapper.unmount()
  })

  it('shows loading, empty, invalid-query, and HTTP 503 states explicitly', async () => {
    let resolveSummary!: (value: ReturnType<typeof jsonResponse>) => void
    const delayedFetch = vi.fn(() => new Promise((resolve) => { resolveSummary = resolve }))
    vi.stubGlobal('fetch', delayedFetch)
    const loadingWrapper = mount(V2BacktestResearchBoard)
    expect(loadingWrapper.get('[role="status"]').text()).toContain('正在讀取並核對 V2 來源身份')
    loadingWrapper.unmount()
    resolveSummary?.(jsonResponse(summary()))

    installBoardFetch({ empty: true })
    const emptyWrapper = mount(V2BacktestResearchBoard)
    await flushPromises()
    await flushPromises()
    expect(emptyWrapper.text()).toContain('沒有可比較群組')
    await emptyWrapper.get('#v2-methods-tab').trigger('click')
    await emptyWrapper.get('input[aria-label="V2 方法 ID 篩選"]').setValue('missing-method')
    await flushPromises()
    expect(emptyWrapper.text()).toContain('沒有資料')
    emptyWrapper.unmount()

    installBoardFetch({ invalidRanking: true })
    const invalidWrapper = mount(V2BacktestResearchBoard)
    await flushPromises()
    await flushPromises()
    expect(invalidWrapper.text()).toContain('查詢條件不合法')
    expect(invalidWrapper.text()).not.toContain('沒有可比較群組')
    invalidWrapper.unmount()

    const unavailableFetch = vi.fn().mockResolvedValue(
      jsonResponse({ error_code: 'B649_RESEARCH_BOARD_V2_NOT_CONFIGURED', message: 'not configured' }, 503),
    )
    vi.stubGlobal('fetch', unavailableFetch)
    const unavailableWrapper = mount(V2BacktestResearchBoard)
    await flushPromises()
    expect(unavailableWrapper.get('[aria-live="assertive"]').text()).toContain('服務不可用（HTTP 503）')
    expect(unavailableWrapper.get('[aria-live="assertive"]').text()).toContain('not configured')
    unavailableWrapper.unmount()
  })
})
