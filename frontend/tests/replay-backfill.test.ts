// @vitest-environment jsdom

import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { isValidReplayDateRange } from '../src/api/replayBackfill'
import ReplayHistoryPage from '../src/features/replay-history/ReplayHistoryPage.vue'

function apiResponse(payload: unknown, status = 200): Response {
  return {
    ok: status < 400,
    status,
    json: vi.fn().mockResolvedValue(payload),
  } as unknown as Response
}

function strategy(
  strategyId: string,
  dataStatus: string,
  overrides: Record<string, unknown> = {},
) {
  return {
    strategy_id: strategyId,
    strategy_version: 'v1',
    display_name: strategyId,
    lottery_type: 'BIG_LOTTO',
    lifecycle_status: 'DRAFT',
    data_status: dataStatus,
    source_kind: 'TEST_FIXTURE',
    executable: false,
    available_target_count: 0,
    training_status: 'NOT_RUN',
    ...overrides,
  }
}

const strategyItems = [
  strategy('strategy-history', 'HAS_HISTORY', {
    display_name: 'History Strategy',
    lifecycle_status: 'ONLINE',
    executable: true,
    available_target_count: 3,
  }),
  strategy('strategy-rebuild', 'REBUILDABLE', { available_target_count: 2, lifecycle_status: 'OFFLINE' }),
  strategy('strategy-none', 'NO_HISTORY'),
  strategy('strategy-artifact', 'ARTIFACT_ONLY', { training_status: 'HISTORICAL_ARTIFACT' }),
  strategy('strategy-code', 'CODE_ONLY', { training_status: 'NOT_TRAINABLE' }),
  strategy('strategy-rejected', 'REJECTED', { lifecycle_status: 'REJECTED' }),
  strategy('external-unregistered-id', 'UNREGISTERED_STATUS', {
    display_name: 'Unregistered but identifiable',
  }),
]

const coverage = {
  expected_strategy_count: 7,
  expected_target_count: 2,
  expected_cell_count: 14,
  completed_cell_count: 8,
  failed_cell_count: 1,
  closed_cell_count: 1,
  complete_coverage_percent: 57.1,
  missing_strategy_ids: ['strategy-code', 'external-unregistered-id'],
  run_id: 'backfill-run-1',
}

function prediction(
  drawNumber: string,
  overrides: Record<string, unknown> = {},
) {
  return {
    lottery_type: 'BIG_LOTTO',
    strategy_id: 'strategy-history',
    strategy_version: 'v1',
    target_draw_number: drawNumber,
    target_draw_date: '2026-10-20',
    prediction_status: 'COMPLETED',
    predicted_tickets: [
      {
        ticket_position: 2,
        main_numbers: [1, 3, 5, 7, 9, 11],
        special_numbers: [13],
        main_hit_count: 2,
        special_hit: true,
        prize_tier: 'SIXTH',
      },
      {
        ticket_position: 7,
        main_numbers: [2, 4, 6, 8, 10, 12],
        special_numbers: [14],
        main_hit_count: 1,
        special_hit: false,
        prize_tier: null,
      },
    ],
    actual_main_numbers: [1, 3, 17, 24, 35, 49],
    actual_special_numbers: [13],
    portfolio_any_prize: true,
    best_main_hits: 2,
    source_kind: 'PERSISTED_REPLAY',
    data_status: 'HAS_HISTORY',
    training: {
      training_status: 'TRAINED',
      model_version: 'model-4',
      training_cutoff: '2026-10-18T00:00:00Z',
      training_artifact_id: 'artifact-training-4',
    },
    ...overrides,
  }
}

function strategyPage(
  items: unknown[] = strategyItems,
  nextCursor: string | null = null,
  totalCount = items.length,
) {
  return { items, total_count: totalCount, next_cursor: nextCursor }
}

function inventoryStrategy(value: Record<string, unknown>) {
  const dataStatus = String(value.data_status)
  if (!['HAS_HISTORY', 'REBUILDABLE', 'NO_HISTORY', 'ARTIFACT_ONLY', 'CODE_ONLY', 'REJECTED'].includes(dataStatus)) {
    return null
  }
  return {
    lottery_type: value.lottery_type,
    strategy_id: value.strategy_id,
    display_name: value.display_name,
    strategy_version: value.strategy_version,
    source_kind: value.source_kind,
    source_locator: `fixture:${String(value.strategy_id)}`,
    lifecycle_status: value.lifecycle_status,
    replay_data_status: dataStatus,
    execution_capability: value.executable ? 'EXECUTABLE' : dataStatus === 'ARTIFACT_ONLY' ? 'ARTIFACT_ONLY' : 'UNAVAILABLE',
    reconstructable: typeof value.reconstructable === 'boolean' ? value.reconstructable : null,
    wrapper_callable: typeof value.wrapper_callable === 'boolean' ? value.wrapper_callable : null,
    backfill_native_binding: typeof value.backfill_native_binding === 'boolean' || value.backfill_native_binding === null
      ? value.backfill_native_binding
      : null,
    backfill_runnable: typeof value.backfill_runnable === 'boolean' ? value.backfill_runnable : false,
    execution_block_reason: typeof value.execution_block_reason === 'string' ? value.execution_block_reason : null,
    reconstruction_reason: `inventory fixture for ${String(value.strategy_id)}`,
    historical_data_count: value.available_target_count,
    historical_execution_count: value.available_target_count,
  }
}

function inventoryPage(items: Record<string, unknown>[]) {
  const strategies = items.map(inventoryStrategy).filter((item) => item !== null)
  return { strategy_count: strategies.length, strategies }
}

function predictionPage(
  items: unknown[],
  totalCount = items.length,
  nextCursor: string | null = null,
  runId = 'prediction-run-1',
) {
  return { run_id: runId, total_count: totalCount, items, next_cursor: nextCursor }
}

function installDefaultApi(overrides: {
  strategies?: (url: URL) => unknown
  strategyStatus?: number | ((url: URL) => number)
  inventory?: (url: URL) => unknown
  inventoryStatus?: number
  coverage?: (url: URL) => unknown
  predictions?: (url: URL) => unknown
  predictionStatus?: number
} = {}) {
  const fetchMock = vi.fn<typeof fetch>().mockImplementation((input) => {
    const url = new URL(String(input), 'http://localhost')
    if (url.pathname === '/api/v1/historical-results/runs') {
      return Promise.resolve(apiResponse({ items: [], total_count: 0, limit: 50, offset: 0 }))
    }
    if (url.pathname === '/api/v1/replay-strategy-inventory') {
      const page = overrides.strategies?.(url) ?? strategyPage()
      const items = Array.isArray((page as { items?: unknown[] }).items)
        ? (page as { items: Record<string, unknown>[] }).items
        : []
      return Promise.resolve(apiResponse(
        overrides.inventory?.(url) ?? inventoryPage(items),
        overrides.inventoryStatus,
      ))
    }
    if (url.pathname === '/api/v1/replay-backfill/strategies') {
      const status = typeof overrides.strategyStatus === 'function'
        ? overrides.strategyStatus(url)
        : overrides.strategyStatus
      return Promise.resolve(apiResponse(overrides.strategies?.(url) ?? strategyPage(), status))
    }
    if (url.pathname === '/api/v1/replay-backfill/coverage') {
      return Promise.resolve(apiResponse(overrides.coverage?.(url) ?? coverage))
    }
    if (url.pathname === '/api/v1/replay-backfill/predictions') {
      return Promise.resolve(apiResponse(overrides.predictions?.(url) ?? predictionPage([]), overrides.predictionStatus))
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

describe('Replay Backfill API UI', () => {
  it('shows API strategies across all data statuses and keeps lifecycle separate', async () => {
    const fetchMock = installDefaultApi()
    const wrapper = await openBackfillPage()

    for (const label of ['有歷史資料', '可重建', '無歷史資料', '僅有研究產物', '僅有程式', '已拒絕']) {
      expect(wrapper.text()).toContain(label)
    }
    expect(wrapper.text()).toContain('external-unregistered-id')
    expect(wrapper.text()).toContain('未註冊或未辨識（UNREGISTERED_STATUS）')
    expect(wrapper.text()).toContain('生命週期：REJECTED')
    expect(wrapper.text()).toContain('具有 Replay 執行能力')
    expect(wrapper.text()).toContain('身份來源：正式 inventory')
    expect(wrapper.text()).toContain('目前僅回報研究產物，未表示已部署或可即時預測。')
    expect(wrapper.text()).toContain('此策略不需要模型訓練。')
    expect(wrapper.text()).toContain('尚未執行重新訓練。')
    expect(wrapper.text()).toContain('僅有封存研究結果。')
    expect(wrapper.text()).toContain('Partial coverage')
    expect(fetchMock.mock.calls
      .filter(([input]) => String(input).includes('/api/v1/replay-backfill/'))
      .every(([, init]) => init?.method === 'GET')).toBe(true)
    const rejectedRow = wrapper.findAll('tbody tr').find((row) => row.text().includes('strategy-rejected'))
    expect(rejectedRow?.text()).toContain('生命週期：REJECTED')
    expect(rejectedRow?.text()).toContain('已拒絕')
    const offlineRow = wrapper.findAll('tbody tr').find((row) => row.text().includes('strategy-rebuild'))
    expect(offlineRow?.text()).toContain('生命週期：OFFLINE')
    expect(offlineRow?.text()).toContain('可重建')
    wrapper.unmount()
  })

  it('keeps P638 Wave 2 wrapper execution separate from native Backfill eligibility', async () => {
    // Synthetic inventory fixture using the B-verified identity and state contract.
    const wave2Identities = [
      ['lag_reversion_2bet', 'v0.1-p638-wave2'],
      ['power_apriori_ext_4bet', 'v0.2-p638-wave2'],
      ['power_fourier_gap_rebound_2bet', 'v0.1-p638-wave2'],
      ['power_momentum_2bet', 'v0.1-p638-wave2'],
    ] as const
    const inventoryRows = wave2Identities
      .map(([strategyId, strategyVersion]) => inventoryStrategy(strategy(strategyId, 'REBUILDABLE', {
        lottery_type: 'POWER_LOTTO',
        strategy_version: strategyVersion,
        lifecycle_status: 'UNREGISTERED_IDENTIFIED',
        executable: true,
        wrapper_callable: true,
        backfill_native_binding: false,
        backfill_runnable: false,
        execution_block_reason: 'NO_CURRENT_NATIVE_BINDING',
      })))
      .filter((item) => item !== null)
    installDefaultApi({
      inventory: () => ({ strategy_count: inventoryRows.length, strategies: inventoryRows }),
    })
    const wrapper = await openBackfillPage()
    await wrapper.get('select[name="lottery_type"]').setValue('POWER_LOTTO')
    await flushPromises()

    const strategyTable = wrapper.findAll('table').find((table) =>
      table.find('caption').text().startsWith('Strategy identities'),
    )
    const rows = strategyTable?.findAll('tbody tr') ?? []
    expect(rows).toHaveLength(wave2Identities.length)
    for (const [strategyId, strategyVersion] of wave2Identities) {
      const row = rows.find((candidate) => candidate.text().includes(strategyId))
      expect(row?.text()).toContain(strategyVersion)
      expect(row?.text()).toContain('UNREGISTERED_IDENTIFIED')
      expect(row?.text()).toContain('可重建')
      expect(row?.text()).toContain('具有 Replay 執行能力')
      expect(row?.text()).toContain('Wrapper 可呼叫')
      expect(row?.text()).toContain('binding=false, runnable=false')
      expect(row?.text()).toContain('NO_CURRENT_NATIVE_BINDING')
      expect(row?.text()).not.toContain('Native Backfill 可執行')
    }
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(wrapper.findAll('[data-testid^="backfill-row-"]')).toHaveLength(0)
    expect(wrapper.text()).not.toContain('0%')
    wrapper.unmount()
  })

  it('keeps known inventory identities visible when the prediction result set is empty', async () => {
    const fetchMock = installDefaultApi({ predictions: () => predictionPage([]) })
    const wrapper = await openBackfillPage()
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.text()).toContain('strategy-history')
    expect(wrapper.text()).toContain('strategy-none')
    expect(wrapper.get('[data-testid="backfill-predictions-empty"]').text()).toContain('No replay records match')
    expect(wrapper.findAll('[data-testid="backfill-strategies-empty"]')).toHaveLength(0)
    const inventoryRequest = fetchMock.mock.calls
      .map(([input]) => new URL(String(input), 'http://localhost'))
      .find((url) => url.pathname === '/api/v1/replay-strategy-inventory')
    expect(inventoryRequest?.searchParams.get('lottery_type')).toBe('BIG_LOTTO')
    wrapper.unmount()
  })

  it('keeps inventory identities visible and reports prediction service unavailability on HTTP 503', async () => {
    const fetchMock = installDefaultApi({
      predictions: () => predictionPage([]),
      strategyStatus: 503,
      predictionStatus: 503,
    })
    const wrapper = await openBackfillPage()
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.get('[data-testid="backfill-predictions-error"]').text()).toContain('服務暫不可用')
    expect(wrapper.text()).toContain('strategy-history')
    expect(wrapper.findAll('[data-testid="backfill-strategies-empty"]')).toHaveLength(0)
    expect(wrapper.text()).not.toContain('0%')
    expect(fetchMock.mock.calls.some(([input]) =>
      String(input).includes('/api/v1/replay-backfill/predictions'),
    )).toBe(true)
    wrapper.unmount()
  })

  it('reports data retrieval failure when inventory and prediction services are unavailable', async () => {
    installDefaultApi({
      inventoryStatus: 503,
      strategyStatus: 503,
      predictionStatus: 503,
    })
    const wrapper = await openBackfillPage()
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.get('[data-testid="backfill-strategies-error"]').text()).toContain('資料取得失敗')
    expect(wrapper.get('[data-testid="backfill-data-unavailable"]').text()).toContain('無法判定策略身份或預測結果')
    expect(wrapper.findAll('[data-testid="backfill-strategies-empty"]')).toHaveLength(0)
    expect(wrapper.text()).not.toContain('0%')
    wrapper.unmount()
  })

  it('sends a searched strategy ID, valid date range, and selected period to the predictions API', async () => {
    const predictionItem = prediction('113000200')
    const oneHitTicket = predictionItem.predicted_tickets[1]
    oneHitTicket.main_numbers = [2, 4, 6, 8, 10, 49]
    expect(oneHitTicket.main_hit_count).toBe(
      oneHitTicket.main_numbers.filter((number) => predictionItem.actual_main_numbers.includes(number)).length,
    )
    const fetchMock = installDefaultApi({
      predictions: () => predictionPage([predictionItem]),
    })
    const wrapper = await openBackfillPage()
    await wrapper.get('select[name="strategy_id"]').setValue('strategy-history')
    await wrapper.get('input[name="from_date"]').setValue('2026-10-01')
    await wrapper.get('input[name="to_date"]').setValue('2026-10-25')
    await wrapper.get('select[name="period"]').setValue('300')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    const request = fetchMock.mock.calls
      .map(([input]) => new URL(String(input), 'http://localhost'))
      .find((url) => url.pathname === '/api/v1/replay-backfill/predictions')
    expect(request?.searchParams.get('lottery_type')).toBe('BIG_LOTTO')
    expect(request?.searchParams.get('strategy_id')).toBe('strategy-history')
    expect(request?.searchParams.get('from_date')).toBe('2026-10-01')
    expect(request?.searchParams.get('to_date')).toBe('2026-10-25')
    expect(request?.searchParams.get('period')).toBe('300')
    expect(request?.searchParams.get('limit')).toBe('50')
    expect(fetchMock.mock.calls.some(([input, init]) =>
      String(input).includes('/api/v1/replay-backfill/predictions') && init?.method === 'GET',
    )).toBe(true)
    expect(wrapper.text()).toContain('SIXTH')
    expect(wrapper.text()).toContain('2')
    expect(wrapper.text()).toContain('artifact-training-4')
    expect(wrapper.text()).toContain('Training cutoff')
    expect(wrapper.text()).toContain('官方特別號')
    wrapper.unmount()
  })

  it('shows missing training evidence explicitly when the API reports NOT_RUN', async () => {
    installDefaultApi({
      predictions: () => predictionPage([
        prediction('113000201', {
          training: {
            training_status: 'NOT_RUN',
            model_version: null,
            training_cutoff: null,
            training_artifact_id: null,
          },
        }),
      ]),
    })
    const wrapper = await openBackfillPage()
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.text()).toContain('尚未執行重新訓練。')
    expect(wrapper.text()).toContain('API未提供')
    expect(wrapper.text()).not.toContain('model-4')
    expect(wrapper.text()).not.toContain('artifact-training-4')
    wrapper.unmount()
  })

  it('sends all four periods and omits strategy_id for all strategies', async () => {
    const fetchMock = installDefaultApi({
      coverage: () => ({
        ...coverage,
        expected_strategy_count: 0,
        expected_target_count: 0,
        expected_cell_count: 0,
        completed_cell_count: 0,
        failed_cell_count: 0,
        closed_cell_count: 0,
        complete_coverage_percent: 0,
        missing_strategy_ids: [],
      }),
      predictions: () => predictionPage([]),
    })
    const wrapper = await openBackfillPage()

    for (const period of ['50', '300', '750', 'ALL']) {
      await wrapper.get('select[name="period"]').setValue(period)
      await wrapper.get('form').trigger('submit')
      await flushPromises()
    }

    const requests = fetchMock.mock.calls
      .map(([input]) => new URL(String(input), 'http://localhost'))
      .filter((url) => url.pathname === '/api/v1/replay-backfill/predictions')
    expect(requests.map((url) => url.searchParams.get('period'))).toEqual(['50', '300', '750', 'ALL'])
    expect(requests.every((url) => !url.searchParams.has('strategy_id'))).toBe(true)
    expect(requests.every((url) => !url.searchParams.has('cursor'))).toBe(true)
    expect(wrapper.text()).toContain('尚無可查詢的正式Replay資料。')
    wrapper.unmount()
  })

  it('validates real calendar dates and rejects a reversed range before calling predictions', async () => {
    expect(isValidReplayDateRange('2026-02-30', '2026-03-01')).toBe(false)
    expect(isValidReplayDateRange('2026-10-26', '2026-10-25')).toBe(false)
    const fetchMock = installDefaultApi()
    const wrapper = await openBackfillPage()
    await wrapper.get('input[name="from_date"]').setValue('2026-10-26')
    await wrapper.get('input[name="to_date"]').setValue('2026-10-25')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.text()).toContain('起始日期不可晚於結束日期')
    expect(fetchMock.mock.calls.some(([input]) => String(input).includes('/api/v1/replay-backfill/predictions'))).toBe(false)
    wrapper.unmount()
  })

  it('switches lottery type and reloads both strategy and coverage queries', async () => {
    const fetchMock = installDefaultApi({
      strategies: (url) => strategyPage([
        strategy(`strategy-${url.searchParams.get('lottery_type')}`, 'NO_HISTORY', {
          lottery_type: url.searchParams.get('lottery_type'),
        }),
      ]),
      predictions: () => predictionPage([
        prediction('p638-target-1', {
          lottery_type: 'POWER_LOTTO',
          strategy_id: 'strategy-POWER_LOTTO',
          actual_special_numbers: [3],
        }),
      ]),
    })
    const wrapper = await openBackfillPage()
    expect(wrapper.findAll('select[name="lottery_type"] option').map((option) => option.element.value)).toEqual([
      'BIG_LOTTO',
      'DAILY_539',
      'POWER_LOTTO',
    ])
    await wrapper.get('select[name="lottery_type"]').setValue('DAILY_539')
    await flushPromises()

    const strategyRequest = fetchMock.mock.calls
      .map(([input]) => new URL(String(input), 'http://localhost'))
      .filter((url) => url.pathname === '/api/v1/replay-backfill/strategies')
      .at(-1)
    const coverageRequest = fetchMock.mock.calls
      .map(([input]) => new URL(String(input), 'http://localhost'))
      .filter((url) => url.pathname === '/api/v1/replay-backfill/coverage')
      .at(-1)
    expect(strategyRequest?.searchParams.get('lottery_type')).toBe('DAILY_539')
    expect(coverageRequest?.searchParams.get('lottery_type')).toBe('DAILY_539')
    expect(wrapper.text()).toContain('strategy-DAILY_539')

    await wrapper.get('select[name="lottery_type"]').setValue('POWER_LOTTO')
    await flushPromises()
    const powerStrategyRequest = fetchMock.mock.calls
      .map(([input]) => new URL(String(input), 'http://localhost'))
      .filter((url) => url.pathname === '/api/v1/replay-backfill/strategies')
      .at(-1)
    expect(powerStrategyRequest?.searchParams.get('lottery_type')).toBe('POWER_LOTTO')
    expect(wrapper.text()).toContain('strategy-POWER_LOTTO')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(wrapper.text()).toContain('官方第二區')
    expect(wrapper.text()).toContain('p638-target-1')
    expect(wrapper.text()).toContain('3')
    wrapper.unmount()
  })

  it('searches strategy names through the API query and supports strategy pagination', async () => {
    const fetchMock = installDefaultApi({
      strategies: (url) =>
        url.searchParams.get('cursor')
          ? strategyPage([strategy('strategy-page-two', 'CODE_ONLY', { display_name: 'History Name two' })])
          : strategyPage([strategy('strategy-page-one', 'HAS_HISTORY', { display_name: 'History Name one' })], 'strategy-cursor-2'),
    })
    const wrapper = await openBackfillPage()
    await wrapper.get('input[name="strategy_search"]').setValue('History Name')
    await wrapper.findAll('button').find((button) => button.text() === 'Search strategies')?.trigger('click')
    await flushPromises()

    let strategyRequests = fetchMock.mock.calls
      .map(([input]) => new URL(String(input), 'http://localhost'))
      .filter((url) => url.pathname === '/api/v1/replay-backfill/strategies')
    expect(strategyRequests.at(-1)?.searchParams.get('q')).toBe('History Name')
    expect(strategyRequests.at(-1)?.searchParams.get('limit')).toBe('100')

    await wrapper.findAll('button').find((button) => button.text() === 'Load more strategies')?.trigger('click')
    await flushPromises()
    strategyRequests = fetchMock.mock.calls
      .map(([input]) => new URL(String(input), 'http://localhost'))
      .filter((url) => url.pathname === '/api/v1/replay-backfill/strategies')
    expect(strategyRequests.at(-1)?.searchParams.get('cursor')).toBe('strategy-cursor-2')
    expect(wrapper.text()).toContain('strategy-page-one')
    expect(wrapper.text()).toContain('strategy-page-two')
    wrapper.unmount()
  })

  it('keeps versioned identities and no-history rows through fallback strategy pages', async () => {
    const firstPage = [
      strategy('shared-id', 'HAS_HISTORY', { strategy_version: 'legacy', display_name: 'Legacy display' }),
      strategy('strategy-page-one', 'HAS_HISTORY', { display_name: 'First page' }),
    ]
    const duplicateAndNextPage = [
      strategy('shared-id', 'HAS_HISTORY', { strategy_version: 'legacy', display_name: 'Legacy display' }),
      strategy('shared-id', 'REBUILDABLE', { strategy_version: 'v1', display_name: 'Current display' }),
      strategy('strategy-no-history', 'NO_HISTORY', { display_name: 'No history page' }),
    ]
    const fetchMock = installDefaultApi({
      inventoryStatus: 503,
      strategies: (url) => url.searchParams.get('cursor')
        ? strategyPage(duplicateAndNextPage, null, 4)
        : strategyPage(firstPage, 'strategy-cursor-2', 4),
    })
    const wrapper = await openBackfillPage()

    expect(wrapper.text()).toContain('Legacy display')
    await wrapper.findAll('button').find((button) => button.text() === 'Load more strategies')?.trigger('click')
    await flushPromises()

    const strategyTable = wrapper.findAll('table').find((table) =>
      table.find('caption').text().startsWith('Strategy identities'),
    )
    const rows = strategyTable?.findAll('tbody tr') ?? []
    const rowTexts = rows.map((row) => row.text())
    expect(rows).toHaveLength(4)
    expect(rowTexts.filter((row) => row.includes('Legacy display'))).toHaveLength(1)
    expect(rowTexts.some((row) => row.includes('Current display') && row.includes('v1'))).toBe(true)
    expect(rowTexts.some((row) => row.includes('No history page') && row.includes('無歷史資料'))).toBe(true)
    const sharedIdOptions = wrapper.findAll('select[name="strategy_id"] option')
      .filter((option) => option.element.value === 'shared-id')
    expect(sharedIdOptions).toHaveLength(1)
    expect(sharedIdOptions[0]?.text()).toContain('legacy')
    expect(sharedIdOptions[0]?.text()).toContain('v1')
    const requests = fetchMock.mock.calls
      .map(([input]) => new URL(String(input), 'http://localhost'))
      .filter((url) => url.pathname === '/api/v1/replay-backfill/strategies')
    expect(requests.at(-1)?.searchParams.get('cursor')).toBe('strategy-cursor-2')
    wrapper.unmount()
  })

  it('reports a later strategy-page failure while keeping previously loaded identities visible', async () => {
    const fetchMock = installDefaultApi({
      inventoryStatus: 503,
      strategyStatus: (url) => url.searchParams.has('cursor') ? 503 : 200,
      strategies: (url) => url.searchParams.has('cursor')
        ? strategyPage([], null, 2)
        : strategyPage([strategy('strategy-page-one', 'HAS_HISTORY')], 'strategy-cursor-2', 2),
    })
    const wrapper = await openBackfillPage()
    await wrapper.findAll('button').find((button) => button.text() === 'Load more strategies')?.trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-testid="backfill-strategies-pagination-error"]').text()).toContain('503')
    expect(wrapper.text()).toContain('strategy-page-one')
    expect(wrapper.findAll('[data-testid="backfill-strategies-empty"]')).toHaveLength(0)
    expect(fetchMock.mock.calls
      .map(([input]) => new URL(String(input), 'http://localhost'))
      .some((url) => url.pathname === '/api/v1/replay-backfill/strategies' && url.searchParams.get('cursor') === 'strategy-cursor-2')).toBe(true)
    wrapper.unmount()
  })

  it('keeps VERIFIED, UNTRUSTED, and UNKNOWN prediction cutoffs distinct', async () => {
    // Synthetic API contract fixtures only; these rows are not historical replay results.
    const cutoff = (status: 'VERIFIED' | 'UNTRUSTED' | 'UNKNOWN', reason_code: string | null) => ({
      draw_date: status === 'VERIFIED' ? '2025-12-31' : null,
      draw_number: status === 'VERIFIED' ? '202512999' : null,
      history_draw_count: status === 'VERIFIED' ? 0 : null,
      reason_code,
      source_hash: status === 'VERIFIED' ? 'fixture-source-hash' : null,
      source_identity: status === 'VERIFIED' ? 'causal-history:fixture-cell-0' : null,
      source_locator: status === 'VERIFIED' ? 'replay-input://fixture-cell-0' : null,
      status,
    })
    const wrapper = await openBackfillPage()
    installDefaultApi({
      predictions: () => predictionPage([
        prediction('cutoff-verified', { prediction_cutoff: cutoff('VERIFIED', null) }),
        prediction('cutoff-untrusted', {
          prediction_cutoff: cutoff('UNTRUSTED', 'CUTOFF_NOT_BEFORE_TARGET'),
        }),
        prediction('cutoff-unknown', {
          prediction_cutoff: cutoff('UNKNOWN', 'PREDICTION_INPUT_NOT_RECORDED'),
        }),
      ]),
    })
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    const verifiedRow = wrapper.get('[data-testid="backfill-row-cutoff-verified-strategy-history"]')
    const untrustedRow = wrapper.get('[data-testid="backfill-row-cutoff-untrusted-strategy-history"]')
    const unknownRow = wrapper.get('[data-testid="backfill-row-cutoff-unknown-strategy-history"]')
    expect(verifiedRow.text()).toContain('VERIFIED')
    expect(verifiedRow.text()).toContain('Cutoff history count0')
    expect(verifiedRow.text()).not.toContain('UNTRUSTED')
    expect(untrustedRow.text()).toContain('UNTRUSTED · CUTOFF_NOT_BEFORE_TARGET')
    expect(untrustedRow.text()).not.toContain('VERIFIED')
    expect(unknownRow.text()).toContain('UNKNOWN · PREDICTION_INPUT_NOT_RECORDED')
    expect(unknownRow.text()).not.toContain('UNTRUSTED')
    wrapper.unmount()
  })

  it('loads more prediction pages without repeating rows and preserves original ticket positions', async () => {
    const first = prediction('113000201')
    const second = prediction('113000202', { target_draw_date: '2026-10-21' })
    for (const item of [first, second]) {
      const oneHitTicket = item.predicted_tickets[1]
      oneHitTicket.main_numbers = [2, 4, 6, 8, 10, 49]
      expect(oneHitTicket.main_hit_count).toBe(
        oneHitTicket.main_numbers.filter((number) => item.actual_main_numbers.includes(number)).length,
      )
    }
    const fetchMock = installDefaultApi({
      predictions: (url) =>
        url.searchParams.get('cursor')
          ? predictionPage([first, second], 2, null)
          : predictionPage([first], 2, 'prediction-cursor-2'),
    })
    const wrapper = await openBackfillPage()
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    await wrapper.findAll('button').find((button) => button.text() === 'Load more')?.trigger('click')
    await flushPromises()

    const predictionRequests = fetchMock.mock.calls
      .map(([input]) => new URL(String(input), 'http://localhost'))
      .filter((url) => url.pathname === '/api/v1/replay-backfill/predictions')
    expect(predictionRequests[1]?.searchParams.get('cursor')).toBe('prediction-cursor-2')
    expect(wrapper.findAll('[data-testid^="backfill-row-"]')).toHaveLength(2)
    expect(wrapper.text()).toContain('#2 · 1、3、5、7、9、11 + 13')
    expect(wrapper.text()).toContain('13')
    expect(wrapper.text()).toContain('SIXTH')
    expect(wrapper.text()).toContain('命中')
    wrapper.unmount()
  })

  it('shows an explicit 503 error rather than treating it as an empty result', async () => {
    const fetchMock = installDefaultApi()
    fetchMock.mockImplementation((input) => {
      const url = new URL(String(input), 'http://localhost')
      if (url.pathname === '/api/v1/replay-backfill/predictions') {
        return Promise.resolve(apiResponse({ message: '正式 Replay 服務尚未設定' }, 503))
      }
      if (url.pathname === '/api/v1/historical-results/runs') {
        return Promise.resolve(apiResponse({ items: [], total_count: 0, limit: 50, offset: 0 }))
      }
      if (url.pathname === '/api/v1/replay-strategy-inventory') {
        return Promise.resolve(apiResponse(inventoryPage(strategyItems)))
      }
      if (url.pathname === '/api/v1/replay-backfill/strategies') return Promise.resolve(apiResponse(strategyPage()))
      if (url.pathname === '/api/v1/replay-backfill/coverage') return Promise.resolve(apiResponse(coverage))
      throw new Error(`Unexpected fetch: ${url}`)
    })
    const wrapper = await openBackfillPage()
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.get('[data-testid="backfill-predictions-error"]').text()).toContain('HTTP 503')
    expect(wrapper.text()).not.toContain('No replay predictions match')
    wrapper.unmount()
  })

  it('does not let a stale response for an old lottery overwrite the latest query', async () => {
    let resolveBig: ((response: Response) => void) | undefined
    let resolveDaily: ((response: Response) => void) | undefined
    const fetchMock = installDefaultApi()
    fetchMock.mockImplementation((input) => {
      const url = new URL(String(input), 'http://localhost')
      if (url.pathname === '/api/v1/historical-results/runs') {
        return Promise.resolve(apiResponse({ items: [], total_count: 0, limit: 50, offset: 0 }))
      }
      if (url.pathname === '/api/v1/replay-strategy-inventory') return Promise.resolve(apiResponse(inventoryPage(strategyItems)))
      if (url.pathname === '/api/v1/replay-backfill/strategies') return Promise.resolve(apiResponse(strategyPage()))
      if (url.pathname === '/api/v1/replay-backfill/coverage') return Promise.resolve(apiResponse(coverage))
      if (url.pathname === '/api/v1/replay-backfill/predictions') {
        if (url.searchParams.get('lottery_type') === 'BIG_LOTTO') {
          return new Promise((resolve) => { resolveBig = resolve })
        }
        return new Promise((resolve) => { resolveDaily = resolve })
      }
      throw new Error(`Unexpected fetch: ${url}`)
    })
    const wrapper = await openBackfillPage()
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(wrapper.get('[data-testid="backfill-predictions-loading"]').text()).toContain('Loading')
    await wrapper.get('select[name="lottery_type"]').setValue('DAILY_539')
    await flushPromises()
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    resolveDaily?.(apiResponse(predictionPage([
      prediction('539000001', {
        lottery_type: 'DAILY_539',
        strategy_id: 'strategy-daily',
        actual_special_numbers: [],
        predicted_tickets: [],
      }),
    ])))
    await flushPromises()
    resolveBig?.(apiResponse(predictionPage([prediction('113000999')])))
    await flushPromises()

    expect(wrapper.text()).toContain('539000001')
    expect(wrapper.text()).toContain('特別號／第二區（539 不適用）')
    expect(wrapper.text()).toContain('不適用')
    expect(wrapper.text()).not.toContain('113000999')
    wrapper.unmount()
  })
})
