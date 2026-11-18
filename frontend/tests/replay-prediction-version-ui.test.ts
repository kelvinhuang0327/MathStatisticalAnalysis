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

function runItem(runId: string, strategyVersion: string) {
  return {
    run_id: runId,
    lottery_type: 'BIG_LOTTO',
    strategy_id: 'strategy-1',
    strategy_version: strategyVersion,
    run_created_at: '2026-11-16T08:00:00Z',
    inventory_present: true,
    associated_cell_count: 3,
    unique_target_draw_count: 2,
    execution_identity_count: 2,
    execution_status_counts: { COMPLETED: 2 },
    earliest_target_draw_date: '2026-11-01',
    latest_target_draw_date: '2026-11-15',
  }
}

function runPage(items: unknown[]) {
  return {
    total_run_version_matches: items.length,
    items,
    has_more: false,
    limit: 50,
    offset: 0,
  }
}

function prediction(
  targetDrawNumber: string,
  strategyVersion: string,
  executionVersion: string | null,
  datasetIdentity: string | null,
) {
  return {
    lottery_type: 'BIG_LOTTO',
    strategy_id: 'strategy-1',
    strategy_version: strategyVersion,
    target_draw_number: targetDrawNumber,
    target_draw_date: '2026-11-01',
    prediction_status: 'COMPLETE',
    source_history_provenance_status: 'UNVERIFIED',
    predicted_tickets: [],
    actual_main_numbers: [1, 2, 3, 4, 5, 6],
    actual_special_numbers: [7],
    source_kind: 'TEST_FIXTURE',
    data_status: 'HAS_HISTORY',
    training: {
      training_status: 'NOT_TRAINABLE',
      model_version: null,
      training_cutoff: null,
      training_artifact_id: null,
    },
    portfolio_any_prize: null,
    best_main_hits: null,
    execution_version: executionVersion,
    dataset_identity: datasetIdentity,
  }
}

function predictionPage(
  runId: string | null,
  items: unknown[],
  overrides: Record<string, unknown> = {},
) {
  return {
    run_id: runId,
    total_count: items.length,
    items,
    next_cursor: null,
    ...overrides,
  }
}

type ApiValue = unknown | Response | Promise<unknown | Response>

function asResponse(value: unknown, status = 200): Response {
  if (value && typeof value === 'object' && 'json' in value) return value as Response
  return apiResponse(value, status)
}

function installApi(overrides: {
  discovery?: (url: URL) => ApiValue
  predictions?: (url: URL) => ApiValue
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
      return Promise.resolve(apiResponse({
        expected_strategy_count: 0,
        expected_target_count: 0,
        expected_cell_count: 0,
        completed_cell_count: 0,
        failed_cell_count: 0,
        closed_cell_count: 0,
        complete_coverage_percent: 0,
        missing_strategy_ids: [],
        run_id: url.searchParams.get('run_id'),
      }))
    }
    if (url.pathname === '/api/v1/replay-backfill/strategy-runs') {
      const value = overrides.discovery?.(url) ?? runPage([])
      return Promise.resolve(value).then((resolved) => asResponse(resolved))
    }
    if (url.pathname === '/api/v1/replay-backfill/predictions') {
      const value = overrides.predictions?.(url) ?? predictionPage(url.searchParams.get('run_id'), [])
      return Promise.resolve(value).then((resolved) => asResponse(resolved))
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

async function selectDiscoveredRunVersion(
  wrapper: ReturnType<typeof mount>,
  runId: string,
  version: string,
) {
  await wrapper.get(`[data-testid="strategy-run-discovery-apply-${runId}-${version}"]`).trigger('click')
  await flushPromises()
}

async function queryHistory(wrapper: ReturnType<typeof mount>) {
  await wrapper.get('section[aria-labelledby="backfill-query-title"] form').trigger('submit')
  await flushPromises()
}

function predictionRequests(fetchMock: ReturnType<typeof installApi>): URL[] {
  return fetchMock.mock.calls
    .map(([input]) => new URL(String(input), 'http://localhost'))
    .filter((url) => url.pathname === '/api/v1/replay-backfill/predictions')
}

afterEach(() => {
  vi.unstubAllGlobals()
  window.history.replaceState(null, '', '/')
})

describe('Replay History Run×version prediction view', () => {
  it('applies the selected Run×version, clears prior results, and keeps versions separate', async () => {
    const fetchMock = installApi({
      discovery: () => runPage([
        runItem('R1', 'v1'),
        runItem('R1', 'v2'),
        runItem('R2', 'v2'),
      ]),
      predictions: (url) => {
        const runId = url.searchParams.get('run_id')
        const version = url.searchParams.get('strategy_version')
        if (version === 'v1') {
          return predictionPage(runId, [
            prediction('101', 'v1', 'EV1', 'DS1'),
            prediction('102', 'v1', 'EV1', 'DS1'),
            prediction('103', 'v1', 'EV2', 'DS2'),
          ])
        }
        if (version === 'v2') {
          return predictionPage(runId, [
            prediction('201', 'v2', 'EV1', 'DS1'),
            prediction('202', 'v2', 'EV2', 'DS2'),
          ])
        }
        return predictionPage(runId, [])
      },
    })
    const wrapper = await openBackfillPage()

    await wrapper.get('[data-testid="strategy-run-discovery-id"]').setValue('strategy-1')
    await wrapper.get('[data-testid="strategy-run-discovery-submit"]').trigger('click')
    await flushPromises()

    await selectDiscoveredRunVersion(wrapper, 'R1', 'v1')
    expect((wrapper.get('[name="replay_run_id"]').element as HTMLInputElement).value).toBe('R1')
    expect((wrapper.get('[name="strategy_id"]').element as HTMLSelectElement).value).toBe('strategy-1')
    expect(wrapper.get('[data-testid="backfill-version-selection"]').text()).toContain('R1 / strategy-1 / v1')
    expect(wrapper.get('[data-testid="backfill-version-selection"]').text()).toContain('尚未查詢')
    await queryHistory(wrapper)

    let requests = predictionRequests(fetchMock)
    expect(Object.fromEntries(requests[0]?.searchParams ?? [])).toMatchObject({
      lottery_type: 'BIG_LOTTO',
      run_id: 'R1',
      strategy_id: 'strategy-1',
      strategy_version: 'v1',
    })
    expect(wrapper.findAll('tbody tr[data-testid^="backfill-row-"]')).toHaveLength(3)
    expect(wrapper.get('[data-testid="backfill-coverage-version-scope"]').text())
      .toContain('不會因 Strategy version 篩選而變成版本專屬 coverage')

    await selectDiscoveredRunVersion(wrapper, 'R1', 'v2')
    expect(wrapper.findAll('tbody tr[data-testid^="backfill-row-"]')).toHaveLength(0)
    expect(wrapper.find('[data-testid="backfill-prediction-count"]').exists()).toBe(false)
    expect(wrapper.get('[data-testid="backfill-version-selection"]').text()).toContain('R1 / strategy-1 / v2')
    expect(wrapper.get('[data-testid="backfill-version-selection"]').text()).toContain('尚未查詢')
    await queryHistory(wrapper)

    requests = predictionRequests(fetchMock)
    expect(requests[1]?.searchParams.get('strategy_version')).toBe('v2')
    expect(wrapper.findAll('tbody tr[data-testid^="backfill-row-"]')).toHaveLength(2)
    expect(wrapper.findAll('tbody tr[data-testid^="backfill-row-"]')
      .every((row) => row.text().includes('v2'))).toBe(true)

    await selectDiscoveredRunVersion(wrapper, 'R2', 'v2')
    expect(wrapper.findAll('tbody tr[data-testid^="backfill-row-"]')).toHaveLength(0)
    await queryHistory(wrapper)
    requests = predictionRequests(fetchMock)
    expect(Object.fromEntries(requests[2]?.searchParams ?? [])).toMatchObject({
      run_id: 'R2',
      strategy_id: 'strategy-1',
      strategy_version: 'v2',
    })
    expect(wrapper.findAll('tbody tr[data-testid^="backfill-row-"]')).toHaveLength(2)
    wrapper.unmount()
  })

  it('drops an invalid later page and does not reuse a version cursor after changing the Run', async () => {
    const fetchMock = installApi({
      discovery: () => runPage([runItem('R1', 'v1')]),
      predictions: (url) => {
        if (url.searchParams.has('cursor')) return apiResponse({ message: 'page unavailable' }, 503)
        return predictionPage('R1', [prediction('101', 'v1', 'EV1', 'DS1')], {
          total_count: 2,
          next_cursor: 'cursor-v1',
        })
      },
    })
    const wrapper = await openBackfillPage()
    await wrapper.get('[data-testid="strategy-run-discovery-id"]').setValue('strategy-1')
    await wrapper.get('[data-testid="strategy-run-discovery-submit"]').trigger('click')
    await flushPromises()
    await selectDiscoveredRunVersion(wrapper, 'R1', 'v1')
    await queryHistory(wrapper)

    expect(wrapper.findAll('tbody tr[data-testid^="backfill-row-"]')).toHaveLength(1)
    await wrapper.get('section[aria-labelledby="backfill-results-title"] button').trigger('click')
    await flushPromises()

    const requests = predictionRequests(fetchMock)
    expect(requests[1]?.searchParams.get('strategy_version')).toBe('v1')
    expect(requests[1]?.searchParams.get('cursor')).toBe('cursor-v1')
    expect(wrapper.findAll('tbody tr[data-testid^="backfill-row-"]')).toHaveLength(0)
    expect(wrapper.get('[data-testid="backfill-predictions-error"]').text()).toContain('page unavailable')
    expect(wrapper.get('[data-testid="backfill-prediction-count"]').text()).toContain('0 列')

    await wrapper.get('[name="replay_run_id"]').setValue('R2')
    expect(wrapper.findAll('tbody tr[data-testid^="backfill-row-"]')).toHaveLength(0)
    expect(wrapper.get('[data-testid="backfill-version-selection"]').text()).toContain('未選定版本')
    await queryHistory(wrapper)
    const latestRequest = predictionRequests(fetchMock)[2]
    expect(latestRequest?.searchParams.get('run_id')).toBe('R2')
    expect(latestRequest?.searchParams.get('strategy_id')).toBe('strategy-1')
    expect(latestRequest?.searchParams.has('strategy_version')).toBe(false)
    expect(latestRequest?.searchParams.has('cursor')).toBe(false)
    wrapper.unmount()
  })

  it('ignores a late old-version response and renders both same-draw executions', async () => {
    let resolveOldResponse: (response: Response) => void = () => {}
    const oldResponse = new Promise<Response>((resolve) => {
      resolveOldResponse = resolve
    })
    const fetchMock = installApi({
      discovery: () => runPage([runItem('R1', 'v1'), runItem('R2', 'v2')]),
      predictions: (url) => {
        if (url.searchParams.get('run_id') === 'R1') return oldResponse
        return predictionPage('R2', [
          prediction('101', 'v2', 'EV1', 'DS1'),
          prediction('101', 'v2', 'EV2', 'DS2'),
          prediction('102', 'v2', null, null),
          prediction('102', 'v2', null, null),
        ])
      },
    })
    const wrapper = await openBackfillPage()
    await wrapper.get('[data-testid="strategy-run-discovery-id"]').setValue('strategy-1')
    await wrapper.get('[data-testid="strategy-run-discovery-submit"]').trigger('click')
    await flushPromises()
    await selectDiscoveredRunVersion(wrapper, 'R1', 'v1')
    const queryForm = wrapper.get('section[aria-labelledby="backfill-query-title"] form')
    await queryForm.trigger('submit')

    const oldRequest = predictionRequests(fetchMock)[0]
    expect(oldRequest?.searchParams.get('strategy_version')).toBe('v1')
    await selectDiscoveredRunVersion(wrapper, 'R2', 'v2')
    resolveOldResponse(apiResponse(predictionPage('R1', [
      prediction('100', 'v1', 'EV1', 'DS1'),
    ])))
    await flushPromises()
    expect(wrapper.findAll('tbody tr[data-testid^="backfill-row-"]')).toHaveLength(0)

    await queryHistory(wrapper)
    const rows = wrapper.findAll('tbody tr[data-testid^="backfill-row-"]')
    expect(rows).toHaveLength(4)
    expect(rows.map((row) => row.text()).join('\n')).toContain('Execution EV1 · Dataset DS1')
    expect(rows.map((row) => row.text()).join('\n')).toContain('Execution EV2 · Dataset DS2')
    expect(rows.every((row) => row.text().includes('v2'))).toBe(true)
    expect(rows.slice(2).every((row) => row.text().includes('Execution 未提供 · Dataset 未提供'))).toBe(true)
    expect(new Set(rows.slice(2).map((row) => row.attributes('data-testid'))).size).toBe(2)
    expect(predictionRequests(fetchMock)[1]?.searchParams.get('strategy_version')).toBe('v2')
    wrapper.unmount()
  })
})
