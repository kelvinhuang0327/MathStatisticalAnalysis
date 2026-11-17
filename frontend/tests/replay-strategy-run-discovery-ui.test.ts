// @vitest-environment jsdom

import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'

import ReplayHistoryPage from '../src/features/replay-history/ReplayHistoryPage.vue'

function apiResponse(payload: unknown, status = 200): Response {
  return {
    ok: status < 400,
    status,
    json: vi.fn().mockResolvedValue(payload),
  } as unknown as Response
}

function runItem(overrides: Record<string, unknown> = {}) {
  return {
    run_id: 'RUN-1',
    lottery_type: 'BIG_LOTTO',
    strategy_id: 'strategy-1',
    strategy_version: 'v1',
    run_created_at: '2026-11-16T08:00:00Z',
    inventory_present: true,
    associated_cell_count: 3,
    unique_target_draw_count: 2,
    execution_identity_count: 1,
    execution_status_counts: { COMPLETED: 1 },
    earliest_target_draw_date: '2026-11-01',
    latest_target_draw_date: '2026-11-15',
    ...overrides,
  }
}

function runPage(
  items: unknown[] = [],
  overrides: Record<string, unknown> = {},
) {
  return {
    total_run_version_matches: items.length,
    items,
    has_more: false,
    limit: 50,
    offset: 0,
    ...overrides,
  }
}

function coverage(runId: string | null = null) {
  return {
    expected_strategy_count: 0,
    expected_target_count: 0,
    expected_cell_count: 0,
    completed_cell_count: 0,
    failed_cell_count: 0,
    closed_cell_count: 0,
    complete_coverage_percent: 0,
    missing_strategy_ids: [],
    run_id: runId,
  }
}

function installDefaultApi(overrides: {
  discovery?: (url: URL) => unknown | Response | Promise<unknown | Response>
  discoveryStatus?: number
  predictionsRunId?: (url: URL) => string | null
  coverageRunId?: (url: URL) => string | null
} = {}) {
  const fetchMock = vi.fn<typeof fetch>().mockImplementation((input) => {
    const url = new URL(String(input), 'http://localhost')
    if (url.pathname === '/api/v1/historical-results/runs') {
      return Promise.resolve(apiResponse({ items: [], total_count: 0, limit: 50, offset: 0 }))
    }
    if (url.pathname === '/api/v1/replay-strategy-inventory') {
      return Promise.resolve(apiResponse({ lottery_type: 'BIG_LOTTO', strategy_count: 0, strategies: [] }))
    }
    if (url.pathname === '/api/v1/replay-backfill/strategies') {
      return Promise.resolve(apiResponse({ items: [], total_count: 0, next_cursor: null }))
    }
    if (url.pathname === '/api/v1/replay-backfill/coverage') {
      return Promise.resolve(apiResponse(coverage(overrides.coverageRunId?.(url) ?? null)))
    }
    if (url.pathname === '/api/v1/replay-backfill/predictions') {
      return Promise.resolve(apiResponse({
        run_id: overrides.predictionsRunId?.(url) ?? null,
        total_count: 0,
        items: [],
        next_cursor: null,
      }))
    }
    if (url.pathname === '/api/v1/replay-backfill/strategy-runs') {
      if (overrides.discovery) return Promise.resolve(overrides.discovery(url)).then((result) => {
        if (result && typeof result === 'object' && 'json' in result) return result as Response
        return apiResponse(result, overrides.discoveryStatus ?? 200)
      })
      return Promise.resolve(apiResponse(runPage(), overrides.discoveryStatus ?? 200))
    }
    throw new Error(`Unexpected fetch: ${url}`)
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

async function openBackfillPage() {
  const wrapper = mount(ReplayHistoryPage)
  await flushPromises()
  await wrapper.findAll('nav[aria-label="Replay history sections"] button')[2]?.trigger('click')
  await flushPromises()
  return wrapper
}

function discoveryRequests(fetchMock: ReturnType<typeof installDefaultApi>) {
  return fetchMock.mock.calls
    .map(([input]) => new URL(String(input), 'http://localhost'))
    .filter((url) => url.pathname === '/api/v1/replay-backfill/strategy-runs')
}

afterEach(() => {
  vi.unstubAllGlobals()
  window.history.replaceState(null, '', '/')
})

describe('Replay History strategy-run discovery', () => {
  it('waits for an explicit full strategy ID and keeps each Run×version row separate', async () => {
    const fetchMock = installDefaultApi({
      discovery: () => runPage([
        runItem({ run_id: 'R1', strategy_version: 'v1', associated_cell_count: 4 }),
        runItem({ run_id: 'R2', strategy_version: 'v2', associated_cell_count: 1 }),
        runItem({ run_id: 'R3', strategy_version: 'v1', associated_cell_count: 0, unique_target_draw_count: 0, execution_identity_count: 0, execution_status_counts: {}, inventory_present: true, earliest_target_draw_date: null, latest_target_draw_date: null }),
        runItem({ run_id: 'R3', strategy_version: 'v2' }),
      ]),
    })
    const wrapper = await openBackfillPage()

    expect(discoveryRequests(fetchMock)).toHaveLength(0)
    const submit = wrapper.get('[data-testid="strategy-run-discovery-submit"]')
    expect((submit.element as HTMLButtonElement).disabled).toBe(true)
    await wrapper.get('[data-testid="strategy-run-discovery-id"]').setValue('strategy-1')
    expect((submit.element as HTMLButtonElement).disabled).toBe(false)
    await submit.trigger('click')
    await flushPromises()

    const request = discoveryRequests(fetchMock)[0]
    expect(Object.fromEntries(request?.searchParams ?? [])).toEqual({
      lottery_type: 'BIG_LOTTO',
      strategy_id: 'strategy-1',
      limit: '50',
      offset: '0',
    })
    expect(wrapper.findAll('[data-testid^="strategy-run-discovery-row-"]')).toHaveLength(4)
    expect(wrapper.get('[data-testid="strategy-run-discovery-count"]').text())
      .toContain('4 個 Run×版本匹配（不是唯一 Run 數）')
    expect(wrapper.get('[data-testid="strategy-run-discovery-row-R3-v1"]').text())
      .toContain('已登記於該Run，沒有對應Cell')
    expect(wrapper.get('[data-testid="strategy-run-discovery-row-R3-v1"]').text())
      .toContain('未提供 – 未提供')
    expect(wrapper.get('[data-testid="strategy-run-discovery-table"]').text())
      .toContain('不是成功次數或命中率分母')
    wrapper.unmount()
  })

  it('sends the optional exact version and displays only its Run matches', async () => {
    const fetchMock = installDefaultApi({
      discovery: (url) => runPage([
        runItem({ run_id: 'R1', strategy_version: url.searchParams.get('strategy_version') }),
      ]),
    })
    const wrapper = await openBackfillPage()
    await wrapper.get('[data-testid="strategy-run-discovery-id"]').setValue('strategy-1')
    await wrapper.get('[data-testid="strategy-run-discovery-version"]').setValue('v1')
    await wrapper.get('[data-testid="strategy-run-discovery-submit"]').trigger('click')
    await flushPromises()

    expect(discoveryRequests(fetchMock)[0]?.searchParams.get('strategy_version')).toBe('v1')
    expect(wrapper.findAll('[data-testid^="strategy-run-discovery-row-"]')).toHaveLength(1)
    expect(wrapper.get('[data-testid="strategy-run-discovery-row-R1-v1"]').text()).toContain('v1')
    wrapper.unmount()
  })

  it.each([422, 503])('shows HTTP %i as an error, not a valid empty result', async (status) => {
    const wrapper = await openBackfillPage()
    installDefaultApi({ discoveryStatus: status, discovery: () => ({ message: `HTTP ${status} failed` }) })
    await wrapper.get('[data-testid="strategy-run-discovery-id"]').setValue('strategy-1')
    await wrapper.get('[data-testid="strategy-run-discovery-submit"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-testid="strategy-run-discovery-error"]').text()).toContain(`HTTP ${status} failed`)
    expect(wrapper.find('[data-testid="strategy-run-discovery-empty"]').exists()).toBe(false)
    wrapper.unmount()
  })

  it('retains the identity across pages and hides earlier rows if a later page fails', async () => {
    const fetchMock = installDefaultApi({
      discovery: (url) => url.searchParams.get('offset') === '0'
        ? runPage([runItem({ run_id: 'R1' })], { total_run_version_matches: 2, has_more: true })
        : apiResponse({ message: 'page unavailable' }, 503),
    })
    const wrapper = await openBackfillPage()
    await wrapper.get('[data-testid="strategy-run-discovery-id"]').setValue('strategy-1')
    await wrapper.get('[data-testid="strategy-run-discovery-version"]').setValue('v1')
    await wrapper.get('[data-testid="strategy-run-discovery-submit"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="strategy-run-discovery-row-R1-v1"]').exists()).toBe(true)

    await wrapper.get('[data-testid="strategy-run-discovery-load-more"]').trigger('click')
    await flushPromises()

    const requests = discoveryRequests(fetchMock)
    expect(requests.map((url) => ({
      lottery_type: url.searchParams.get('lottery_type'),
      strategy_id: url.searchParams.get('strategy_id'),
      strategy_version: url.searchParams.get('strategy_version'),
    }))).toEqual([
      { lottery_type: 'BIG_LOTTO', strategy_id: 'strategy-1', strategy_version: 'v1' },
      { lottery_type: 'BIG_LOTTO', strategy_id: 'strategy-1', strategy_version: 'v1' },
    ])
    expect(requests[1]?.searchParams.get('offset')).toBe('1')
    expect(wrapper.get('[data-testid="strategy-run-discovery-error"]').text()).toContain('page unavailable')
    expect(wrapper.find('[data-testid="strategy-run-discovery-table"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="strategy-run-discovery-empty"]').exists()).toBe(false)
    wrapper.unmount()
  })

  it('discards a stale response when the strategy identity changes during a request', async () => {
    let resolveStale: (response: Response) => void = () => {}
    const staleResponse = new Promise<Response>((resolve) => {
      resolveStale = resolve
    })
    const fetchMock = installDefaultApi({
      discovery: (url) => url.searchParams.get('strategy_id') === 'strategy-old'
        ? staleResponse
        : runPage([runItem({ run_id: 'NEW-RUN', strategy_id: 'strategy-new' })]),
    })
    const wrapper = await openBackfillPage()

    const strategyInput = wrapper.get('[data-testid="strategy-run-discovery-id"]')
    await strategyInput.setValue('strategy-old')
    await wrapper.get('[data-testid="strategy-run-discovery-submit"]').trigger('click')
    await flushPromises()
    await strategyInput.setValue('strategy-new')
    await wrapper.get('[data-testid="strategy-run-discovery-submit"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="strategy-run-discovery-row-NEW-RUN-v1"]').exists()).toBe(true)

    resolveStale(apiResponse(runPage([runItem({ run_id: 'OLD-RUN', strategy_id: 'strategy-old' })])))
    await flushPromises()

    expect(wrapper.get('[data-testid="strategy-run-discovery-row-NEW-RUN-v1"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="strategy-run-discovery-row-OLD-RUN-v1"]').exists()).toBe(false)
    expect(discoveryRequests(fetchMock)).toHaveLength(2)
    wrapper.unmount()
  })

  it('discards a stale response when the lottery changes during a request', async () => {
    let resolveStale: (response: Response) => void = () => {}
    const staleResponse = new Promise<Response>((resolve) => {
      resolveStale = resolve
    })
    const fetchMock = installDefaultApi({
      discovery: (url) => url.searchParams.get('lottery_type') === 'BIG_LOTTO'
        ? staleResponse
        : runPage([runItem({ run_id: 'POWER-RUN', lottery_type: 'POWER_LOTTO' })]),
    })
    const wrapper = await openBackfillPage()
    await wrapper.get('[data-testid="strategy-run-discovery-id"]').setValue('strategy-1')
    await wrapper.get('[data-testid="strategy-run-discovery-submit"]').trigger('click')
    await flushPromises()

    await wrapper.get('select[name="lottery_type"]').setValue('POWER_LOTTO')
    await wrapper.get('[data-testid="strategy-run-discovery-submit"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="strategy-run-discovery-row-POWER-RUN-v1"]').exists()).toBe(true)

    resolveStale(apiResponse(runPage([runItem({ run_id: 'STALE-RUN' })])))
    await flushPromises()

    expect(wrapper.get('[data-testid="strategy-run-discovery-row-POWER-RUN-v1"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="strategy-run-discovery-row-STALE-RUN-v1"]').exists()).toBe(false)
    expect(discoveryRequests(fetchMock).map((url) => url.searchParams.get('lottery_type')))
      .toEqual(['BIG_LOTTO', 'POWER_LOTTO'])
    wrapper.unmount()
  })

  it('applies a named Run to the single-run field and clears the prior predictions identity', async () => {
    window.history.replaceState(null, '', '?replay_run_id=R2')
    const fetchMock = installDefaultApi({
      discovery: () => runPage([runItem({ run_id: 'R1' })]),
      predictionsRunId: (url) => url.searchParams.get('run_id'),
      coverageRunId: (url) => url.searchParams.get('run_id'),
    })
    const wrapper = await openBackfillPage()
    await wrapper.get('[aria-labelledby="backfill-query-title"] form').trigger('submit')
    await flushPromises()
    expect(wrapper.get('[data-testid="backfill-confirmed-prediction-run"]').text()).toContain('R2')

    await wrapper.get('[data-testid="strategy-run-discovery-id"]').setValue('strategy-1')
    await wrapper.get('[data-testid="strategy-run-discovery-submit"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="strategy-run-discovery-apply-R1-v1"]').trigger('click')
    await flushPromises()

    expect((wrapper.get('input[name="replay_run_id"]').element as HTMLInputElement).value).toBe('R1')
    expect(wrapper.get('[data-testid="backfill-confirmed-prediction-run"]').text()).toContain('尚未查詢')
    expect(wrapper.get('[data-testid="backfill-coverage-run"]').text()).toContain('R1')
    expect(wrapper.find('[data-testid="backfill-predictions-empty"]').exists()).toBe(false)
    expect(fetchMock.mock.calls.filter(([input]) =>
      new URL(String(input), 'http://localhost').pathname === '/api/v1/replay-backfill/predictions',
    )).toHaveLength(1)
    expect(wrapper.get('[data-testid="strategy-run-discovery-version-limit"]').text())
      .toContain('尚無正式 strategy_version 篩選')
    wrapper.unmount()
  })
})
