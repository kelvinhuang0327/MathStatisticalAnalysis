// @vitest-environment jsdom

import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'

import ReplayHistoryPage from '../src/features/replay-history/ReplayHistoryPage.vue'
import { HEDGE_K3_STRATEGY_ID } from '../src/api/replayBackfill'

function apiResponse(payload: unknown, status = 200): Response {
  return {
    ok: status < 400,
    status,
    json: vi.fn().mockResolvedValue(payload),
  } as unknown as Response
}

function strategy(strategyId: string, dataStatus: string, overrides: Record<string, unknown> = {}) {
  return {
    strategy_id: strategyId,
    strategy_version: 'v1',
    display_name: strategyId,
    lottery_type: 'BIG_LOTTO',
    lifecycle_status: 'ONLINE',
    data_status: dataStatus,
    source_kind: 'TEST_FIXTURE',
    executable: true,
    available_target_count: 5,
    training_status: 'TRAINED',
    ...overrides,
  }
}

function strategyPage(
  items: unknown[] = [strategy('strategy-1', 'HAS_HISTORY')],
  totalCount = items.length,
  nextCursor: string | null = null,
) {
  return { items, total_count: totalCount, next_cursor: nextCursor }
}

function inventoryPage(items: unknown[] = [strategy('strategy-1', 'HAS_HISTORY')]) {
  return {
    lottery_type: 'BIG_LOTTO',
    strategy_count: items.length,
    strategies: items.map((val) => {
      const v = val as Record<string, unknown>
      return {
        lottery_type: v.lottery_type ?? 'BIG_LOTTO',
        strategy_id: v.strategy_id,
        display_name: v.display_name,
        strategy_version: v.strategy_version,
        source_kind: v.source_kind ?? 'TEST_FIXTURE',
        source_locator: `fixture:${String(v.strategy_id)}`,
        lifecycle_status: v.lifecycle_status ?? 'ONLINE',
        replay_data_status: v.data_status ?? 'HAS_HISTORY',
        execution_capability: 'EXECUTABLE',
        reconstructable: null,
        wrapper_callable: null,
        backfill_native_binding: true,
        backfill_runnable: true,
        execution_block_reason: null,
        reconstruction_reason: '',
        from_inventory: true,
        historical_data_count: 0,
        historical_execution_count: 0,
      }
    }),
  }
}

function coverage(runId: string | null = 'cov-run-1', overrides: Record<string, unknown> = {}) {
  return {
    expected_strategy_count: 10,
    expected_target_count: 50,
    expected_cell_count: 500,
    completed_cell_count: 450,
    failed_cell_count: 5,
    closed_cell_count: 0,
    complete_coverage_percent: 90.0,
    missing_strategy_ids: [],
    run_id: runId,
    ...overrides,
  }
}

function predictionPage(
  items: unknown[] = [],
  totalCount = items.length,
  nextCursor: string | null = null,
  runId: string | null = 'pred-run-1',
) {
  return {
    run_id: runId,
    total_count: totalCount,
    items,
    next_cursor: nextCursor,
  }
}

function installDefaultApi(overrides: {
  strategies?: (url: URL) => unknown
  strategyStatus?: number
  inventory?: (url: URL) => unknown
  inventoryStatus?: number
  coverage?: (url: URL) => unknown
  coverageStatus?: number
  predictions?: (url: URL) => unknown
  predictionStatus?: number
} = {}) {
  const fetchMock = vi.fn<typeof fetch>().mockImplementation((input) => {
    const url = new URL(String(input), 'http://localhost')
    if (url.pathname === '/api/v1/historical-results/runs') {
      return Promise.resolve(apiResponse({ items: [], total_count: 0, limit: 50, offset: 0 }))
    }
    if (url.pathname === '/api/v1/replay-strategy-inventory') {
      return Promise.resolve(apiResponse(
        overrides.inventory?.(url) ?? inventoryPage(),
        overrides.inventoryStatus ?? 200,
      ))
    }
    if (url.pathname === '/api/v1/replay-backfill/strategies') {
      return Promise.resolve(apiResponse(
        overrides.strategies?.(url) ?? strategyPage(),
        overrides.strategyStatus ?? 200,
      ))
    }
    if (url.pathname === '/api/v1/replay-backfill/coverage') {
      return Promise.resolve(apiResponse(
        overrides.coverage?.(url) ?? coverage(),
        overrides.coverageStatus ?? 200,
      ))
    }
    if (url.pathname === '/api/v1/replay-backfill/predictions') {
      const predResult = overrides.predictions ? overrides.predictions(url) : predictionPage([])
      if (predResult && typeof (predResult as Promise<unknown>).then === 'function') {
        return (predResult as Promise<unknown>).then((resolved) => {
          if (resolved && typeof (resolved as { json?: unknown }).json === 'function') {
            return resolved as Response
          }
          return apiResponse(resolved, overrides.predictionStatus ?? 200)
        })
      }
      if (predResult && typeof (predResult as { json?: unknown }).json === 'function') {
        return Promise.resolve(predResult as Response)
      }
      return Promise.resolve(apiResponse(predResult, overrides.predictionStatus ?? 200))
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

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('Replay history scope display and empty results (AC1 - AC7)', () => {
  it('AC1: displays specified run and lottery, without claiming confirmed response before arrival', async () => {
    let resolvePredictions: (res: Response) => void = () => {}
    const predictionPendingPromise = new Promise<Response>((resolve) => {
      resolvePredictions = resolve
    })

    installDefaultApi({
      predictions: () => predictionPendingPromise,
    })

    const wrapper = await openBackfillPage()
    await wrapper.get('input[name="replay_run_id"]').setValue('RUN-SPECIFIED-42')
    await flushPromises()

    const scopePanel = wrapper.get('[data-testid="backfill-run-scope"]')
    expect(scopePanel.text()).toContain('RUN-SPECIFIED-42')
    expect(scopePanel.text()).toContain('B649')
    // Before predictions resolve, it must not claim RUN-SPECIFIED-42 is the confirmed predictions response run
    expect(wrapper.get('[data-testid="backfill-confirmed-prediction-run"]').text()).not.toContain('RUN-SPECIFIED-42')

    // Submit and let predictions resolve
    await wrapper.get('form').trigger('submit')
    resolvePredictions(apiResponse(predictionPage([], 0, null, 'RUN-SPECIFIED-42')))
    await flushPromises()

    expect(wrapper.get('[data-testid="backfill-confirmed-prediction-run"]').text()).toContain('RUN-SPECIFIED-42')
    wrapper.unmount()
  })

  it('AC1: displays "由API選取最新Run" when run ID is empty, and never displays "全部Run"', async () => {
    installDefaultApi()
    const wrapper = await openBackfillPage()
    await wrapper.get('input[name="replay_run_id"]').setValue('')
    await flushPromises()

    const scopePanel = wrapper.get('[data-testid="backfill-run-scope"]')
    expect(scopePanel.text()).toContain('由API選取最新Run')
    expect(scopePanel.text()).not.toContain('全部Run')
    wrapper.unmount()
  })

  it('AC2: shows mismatch warning when predictions run and coverage run differ, without mixing them', async () => {
    installDefaultApi({
      coverage: () => coverage('RUN-COV-AAA'),
      predictions: () => predictionPage([], 0, null, 'RUN-PRED-BBB'),
    })
    const wrapper = await openBackfillPage()
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    const mismatchAlert = wrapper.get('[data-testid="backfill-run-mismatch"]')
    expect(mismatchAlert.text()).toContain('來源尚未對齊')
    expect(mismatchAlert.text()).toContain('RUN-PRED-BBB')
    expect(mismatchAlert.text()).toContain('RUN-COV-AAA')
    expect(wrapper.get('[data-testid="backfill-confirmed-prediction-run"]').text()).toContain('RUN-PRED-BBB')
    expect(wrapper.get('[data-testid="backfill-coverage-run"]').text()).toContain('RUN-COV-AAA')
    wrapper.unmount()
  })

  it('AC2: marks strategy catalog request scope without inventing a resolved run', async () => {
    installDefaultApi({
      strategies: () => strategyPage([strategy('strat-1', 'HAS_HISTORY')]),
    })
    const wrapper = await openBackfillPage()
    const catalogScope = wrapper.get('[data-testid="backfill-catalog-scope"]')
    expect(catalogScope.text()).toContain('請求範圍')
    expect(catalogScope.text()).toContain('API未提供已確認Run欄位')
    wrapper.unmount()
  })

  it('shows saved records for the confirmed Run and exact version ahead of inventory counts', async () => {
    installDefaultApi({
      inventory: () => inventoryPage([
        strategy(HEDGE_K3_STRATEGY_ID, 'NO_HISTORY'),
        strategy(HEDGE_K3_STRATEGY_ID, 'NO_HISTORY', { strategy_version: 'v2' }),
      ]),
      strategies: (url) => {
        const runId = url.searchParams.get('run_id') || 'latest-run'
        return {
          ...strategyPage([strategy(HEDGE_K3_STRATEGY_ID, 'NO_HISTORY', {
            history_run_id: runId === 'wrong-run' ? 'other-run' : runId,
            history_status: 'HAS_HISTORY',
            history_counts: { saved_prediction_cell_count: 7, persisted_cell_count: 9 },
          })]),
          history_scope: { runs: { BIG_LOTTO: { run_id: runId } } },
        }
      },
    })
    const wrapper = await openBackfillPage()
    const catalogRows = () => wrapper.get('[data-testid="backfill-catalog-scope"]').element
      .parentElement?.querySelectorAll('tbody tr')
    const catalogCells = (index: number) => Array.from(catalogRows()?.[index]?.cells ?? [])
      .map((cell) => cell.textContent?.trim())

    expect(wrapper.get('[data-testid="backfill-catalog-scope"]').text()).toContain('latest-run')
    expect(catalogCells(0)[3]).toContain('有歷史資料')
    expect(catalogCells(0)[5]).toBe('已保存預測 7 筆')
    expect(catalogCells(1)[3]).toBe('本 Run 的歷史狀態待確認')
    expect(catalogCells(1)[5]).toBe('API未提供')

    await wrapper.get('input[name="replay_run_id"]').setValue('wrong-run')
    await flushPromises()
    expect(catalogCells(0)[3]).toBe('本 Run 的歷史狀態待確認')
    expect(catalogCells(0)[5]).toBe('API未提供')
    wrapper.unmount()
  })

  it('AC3: clearly separates inventory count, catalog loaded/total count, predictions count, and coverage cells vs expected periods', async () => {
    installDefaultApi({
      inventory: () => inventoryPage([
        strategy('strat-1', 'HAS_HISTORY'),
        strategy('strat-2', 'HAS_HISTORY'),
      ]),
      strategies: () => strategyPage(
        [strategy('strat-1', 'HAS_HISTORY')],
        15, // total 15
        'cursor-token-next',
      ),
      coverage: () => coverage('cov-run', {
        expected_target_count: 50,
        expected_cell_count: 500,
        completed_cell_count: 300,
      }),
      predictions: () => predictionPage([], 0),
    })

    const wrapper = await openBackfillPage()
    await flushPromises()

    // 1. Static inventory count
    expect(wrapper.get('[data-testid="backfill-inventory-count"]').text()).toContain('2')

    // 2. Catalog loaded vs total count, indicating incomplete roster
    const catalogCountElem = wrapper.get('[data-testid="backfill-catalog-count"]')
    expect(catalogCountElem.text()).toContain('1')
    expect(catalogCountElem.text()).toContain('15')
    expect(catalogCountElem.text()).toContain('清單尚未載完，不可視為完整名冊')

    // 3. Prediction count
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(wrapper.get('[data-testid="backfill-prediction-count"]').text()).toContain('0')

    // 4. Coverage counts: cell count is distinct from expected draw periods, not called unique observation periods
    const coverageCounts = wrapper.get('[data-testid="backfill-coverage-counts"]')
    expect(coverageCounts.text()).toContain('預期期數')
    expect(coverageCounts.text()).toContain('50')
    expect(coverageCounts.text()).toContain('預期期數，非實際已有資料期數')
    expect(coverageCounts.text()).toContain('預期 cell 總數')
    expect(coverageCounts.text()).toContain('500')
    expect(coverageCounts.text()).not.toContain('唯一觀察期')
    wrapper.unmount()
  })

  it('AC4: displays "目前Run／篩選條件沒有符合結果" on successful total_count=0, stating other runs not queried', async () => {
    installDefaultApi({
      predictions: () => predictionPage([], 0, null, 'RUN-EMPTY-1'),
    })
    const wrapper = await openBackfillPage()
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    const emptyPanel = wrapper.get('[data-testid="backfill-predictions-empty"]')
    expect(emptyPanel.text()).toContain('目前Run／篩選條件沒有符合結果')
    expect(emptyPanel.text()).toContain('尚未查詢其他Run')
    expect(emptyPanel.text()).not.toContain('此策略從未研究')
    wrapper.unmount()
  })

  it('AC4: treats HTTP 503 as query failure (error state), not as zero-result empty success', async () => {
    installDefaultApi({
      predictions: () => ({ message: 'Replay service temporarily unavailable', error_code: 'SERVICE_UNAVAILABLE' }),
      predictionStatus: 503,
    })
    const wrapper = await openBackfillPage()
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.findAll('[data-testid="backfill-predictions-error"]')).toHaveLength(1)
    expect(wrapper.get('[data-testid="backfill-predictions-error"]').text()).toContain('HTTP 503')
    expect(wrapper.findAll('[data-testid="backfill-predictions-empty"]')).toHaveLength(0)
    wrapper.unmount()
  })

  it('AC4: leaves unprovided fields as "API未提供", never converting them to 0 or false', async () => {
    installDefaultApi({
      inventory: () => ({
        lottery_type: 'BIG_LOTTO',
        total_count: 1,
        strategies: [{
          lottery_type: 'BIG_LOTTO',
          strategy_id: 'strat-null-fields',
          display_name: 'Null Fields Strategy',
          strategy_version: null,
          source_kind: 'TEST',
          source_locator: 'test',
          lifecycle_status: 'DRAFT',
          replay_data_status: 'HAS_HISTORY',
          execution_capability: 'EXECUTABLE',
          reconstructable: null,
          wrapper_callable: null,
          backfill_native_binding: null,
          backfill_runnable: null,
          execution_block_reason: null,
          reconstruction_reason: '',
          from_inventory: true,
          historical_data_count: 0,
          historical_execution_count: 0,
        }],
      }),
      strategies: () => strategyPage([{
        strategy_id: 'strat-null-fields',
        strategy_version: null,
        display_name: 'Null Fields Strategy',
        lottery_type: 'BIG_LOTTO',
        lifecycle_status: 'DRAFT',
        data_status: 'HAS_HISTORY',
        source_kind: 'TEST',
        executable: true,
        available_target_count: 5,
        historical_data_count: null,
        historical_execution_count: null,
        training_status: 'UNKNOWN',
      }]),
    })

    const wrapper = await openBackfillPage()
    await flushPromises()

    expect(wrapper.text()).toContain('API未提供')
    wrapper.unmount()
  })

  it('AC5: clears results on run switch so Run A data is not attached to Run B, and late response from A is ignored', async () => {
    let resolveA: (res: Response) => void = () => {}
    const promiseA = new Promise<Response>((resolve) => {
      resolveA = resolve
    })

    const fetchMock = vi.fn<typeof fetch>().mockImplementation((input) => {
      const url = new URL(String(input), 'http://localhost')
      if (url.pathname === '/api/v1/historical-results/runs') {
        return Promise.resolve(apiResponse({ items: [], total_count: 0, limit: 50, offset: 0 }))
      }
      if (url.pathname === '/api/v1/replay-strategy-inventory') {
        return Promise.resolve(apiResponse(inventoryPage()))
      }
      if (url.pathname === '/api/v1/replay-backfill/strategies') {
        return Promise.resolve(apiResponse(strategyPage()))
      }
      if (url.pathname === '/api/v1/replay-backfill/coverage') {
        return Promise.resolve(apiResponse(coverage(url.searchParams.get('run_id') ?? 'cov-default')))
      }
      if (url.pathname === '/api/v1/replay-backfill/predictions') {
        const runId = url.searchParams.get('run_id')
        if (runId === 'RUN-A') {
          return promiseA
        }
        return Promise.resolve(apiResponse(predictionPage([], 0, null, runId)))
      }
      throw new Error(`Unexpected fetch: ${url}`)
    })
    vi.stubGlobal('fetch', fetchMock)

    const wrapper = await openBackfillPage()
    await wrapper.get('input[name="replay_run_id"]').setValue('RUN-A')
    await flushPromises()
    await wrapper.get('form').trigger('submit')

    // Switch to RUN-B before A responds
    await wrapper.get('input[name="replay_run_id"]').setValue('RUN-B')
    await flushPromises()

    // Results must be idle / cleared, not showing RUN-A
    expect(wrapper.get('[data-testid="backfill-run-scope"]').text()).toContain('RUN-B')
    expect(wrapper.get('[data-testid="backfill-confirmed-prediction-run"]').text()).not.toContain('RUN-A')

    // Now resolve late response A
    resolveA(apiResponse(predictionPage([], 999, null, 'RUN-A')))
    await flushPromises()

    // Response A must NOT have attached to RUN-B
    expect(wrapper.get('[data-testid="backfill-confirmed-prediction-run"]').text()).not.toContain('RUN-A')
    expect(wrapper.findAll('[data-testid="backfill-prediction-count"]')).toHaveLength(0) // not queried for B yet
    wrapper.unmount()
  })
})
