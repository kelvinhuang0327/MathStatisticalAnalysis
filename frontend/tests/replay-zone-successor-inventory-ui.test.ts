// @vitest-environment jsdom

import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type {
  ReplayBackfillStrategyItem,
  ReplayStrategyInventoryItem,
} from '../src/api/replayBackfill'
import ReplayHistoryPage from '../src/features/replay-history/ReplayHistoryPage.vue'

const ZONE_STRATEGY_ID = 'research_biglotto__zone_momentum_complete_v1'
const ZONE_VERSION = 'v1'
const ZONE_LOTTERY = 'BIG_LOTTO'
const OTHER_LOTTERY = 'DAILY_539'
const ZONE_CURSOR = 'synthetic-zone-cursor-page-2'

interface SyntheticCatalogPlan {
  firstPage: SyntheticCatalogItem[]
  secondPage: SyntheticCatalogItem[]
  totalCount: number
  nextCursor: string | null
  otherLotteryItem?: SyntheticCatalogItem
  historyScope: {
    strategy_identity_source: string
    persisted_history_source: string
    run_selection_rule: string
    runs: Record<string, {
      run_id: string | null
      created_at: string | null
      dataset_identity: string | null
      execution_version: string | null
      source: {
        identity_status: string | null
        source_identity: string | null
        source_kind: string | null
        source_locator: string | null
        source_hash: string | null
        artifact_only: boolean | null
      } | null
    }>
  }
}

interface SyntheticHistoryCounts {
  expected_cell_count: number
  persisted_cell_count: number
  saved_prediction_cell_count: number
  saved_ticket_count: number
  pending_cell_count: number
  execution_status_counts: Record<string, number>
}

type SyntheticCatalogItem = ReplayBackfillStrategyItem & {
  inventory_lifecycle_status: string | null
  inventory_data_status: string | null
  inventory_source_kind: string | null
  inventory_source_locator: string | null
  strategy_source_identity: string | null
  reconstructable: boolean | null
  wrapper_callable: boolean | null
  backfill_native_binding: boolean | null
  backfill_native_binding_sources: []
  backfill_runnable: boolean | null
  execution_block_reason: string | null
  history_status: string | null
  history_statuses: string[]
  history_run_id: string | null
  history_scope: string | null
  history_source_identity_status: string | null
  history_counts: SyntheticHistoryCounts | null
}

const wrappers: VueWrapper[] = []

afterEach(() => {
  for (const wrapper of wrappers.splice(0)) wrapper.unmount()
  vi.unstubAllGlobals()
})

function catalogItem(
  overrides: Partial<ReplayBackfillStrategyItem> = {},
): SyntheticCatalogItem {
  const dataStatus = overrides.data_status ?? 'HAS_HISTORY'
  const hasHistory = dataStatus === 'HAS_HISTORY'
  return {
    strategy_id: ZONE_STRATEGY_ID,
    strategy_version: ZONE_VERSION,
    display_name: 'Zone Momentum Complete',
    lottery_type: ZONE_LOTTERY,
    lifecycle_status: 'UNREGISTERED_IDENTIFIED',
    data_status: 'HAS_HISTORY',
    source_kind: 'REPLAY_BACKFILL_IMPORTED_RESULT',
    executable: false,
    available_target_count: 3,
    training_status: 'NOT_REQUIRED',
    ...overrides,
    inventory_lifecycle_status: 'UNREGISTERED_IDENTIFIED',
    inventory_data_status: 'NO_HISTORY',
    inventory_source_kind: 'REPLAY_BACKFILL_IMPORTED_RESULT',
    inventory_source_locator: 'synthetic-zone-overlay-only',
    strategy_source_identity: null,
    reconstructable: false,
    wrapper_callable: false,
    backfill_native_binding: false,
    backfill_native_binding_sources: [],
    backfill_runnable: false,
    execution_block_reason: 'No exact native replay adapter is registered.',
    history_status: hasHistory ? 'HAS_HISTORY' : 'NO_HISTORY',
    history_statuses: [hasHistory ? 'HAS_HISTORY' : 'NO_HISTORY'],
    history_run_id: hasHistory ? 'synthetic-zone-overlay-only' : null,
    history_scope: 'LATEST_RUN_BY_CREATED_AT_PER_LOTTERY_TYPE',
    history_source_identity_status: 'UNKNOWN',
    history_counts: {
      expected_cell_count: hasHistory ? 3 : 0,
      persisted_cell_count: hasHistory ? 3 : 0,
      saved_prediction_cell_count: hasHistory ? 3 : 0,
      saved_ticket_count: hasHistory ? 6 : 0,
      pending_cell_count: 0,
      execution_status_counts: {
        COMPLETE: hasHistory ? 3 : 0,
        FAILED: 0,
        NOT_ELIGIBLE: 0,
        TYPED_CLOSURE: 0,
        MISSING: 0,
        PARTIAL: 0,
        ARTIFACT_ONLY: 0,
      },
    },
  }
}

function syntheticHistoryScope(
  hasHistory: boolean,
  lotteryType = ZONE_LOTTERY,
): SyntheticCatalogPlan['historyScope'] {
  return {
    strategy_identity_source: 'FIXED_BASE_STATIC_INVENTORY',
    persisted_history_source: 'SYNTHETIC_STORE_OVERLAY',
    run_selection_rule: 'LATEST_RUN_BY_CREATED_AT_PER_LOTTERY_TYPE',
    runs: {
      [lotteryType]: {
        run_id: hasHistory ? 'synthetic-zone-overlay-only' : null,
        created_at: hasHistory ? '2026-11-10T00:00:00+08:00' : null,
        dataset_identity: hasHistory ? 'synthetic-zone-dataset' : null,
        execution_version: hasHistory ? 'synthetic-zone-v1' : null,
        source: hasHistory
          ? {
              identity_status: 'UNKNOWN',
              source_identity: 'synthetic-zone-overlay-only',
              source_kind: 'REPLAY_BACKFILL_IMPORTED_RESULT',
              source_locator: 'synthetic-zone-overlay-only',
              source_hash: null,
              artifact_only: false,
            }
          : null,
      },
    },
  }
}

function inventoryItem(
  dataStatus: 'HAS_HISTORY' | 'NO_HISTORY',
  lotteryType: ReplayStrategyInventoryItem['lottery_type'] = ZONE_LOTTERY,
): ReplayStrategyInventoryItem {
  const historicalDataCount = dataStatus === 'HAS_HISTORY' ? 3 : 0
  return {
    lottery_type: lotteryType,
    strategy_id: ZONE_STRATEGY_ID,
    display_name: 'Zone Momentum Complete',
    strategy_version: ZONE_VERSION,
    source_kind: 'REPLAY_BACKFILL_IMPORTED_RESULT',
    source_locator: 'synthetic-zone-overlay-only',
    lifecycle_status: 'UNREGISTERED_IDENTIFIED',
    replay_data_status: dataStatus,
    execution_capability: 'UNAVAILABLE',
    reconstructable: false,
    wrapper_callable: false,
    backfill_native_binding: false,
    backfill_runnable: false,
    execution_block_reason: 'No exact native replay adapter is registered.',
    reconstruction_reason: 'Synthetic UI fixture; not a formal database readback.',
    historical_data_count: historicalDataCount,
    historical_execution_count: 0,
  }
}

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 400,
    status,
    headers: new Headers({ 'Content-Type': 'application/json' }),
    json: vi.fn().mockResolvedValue(body),
  } as unknown as Response
}

function installSyntheticFetch(
  inventory: ReplayStrategyInventoryItem[],
  catalog: SyntheticCatalogPlan,
) {
  const requests: URL[] = []
  const unexpectedRequests: string[] = []
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = new URL(String(input), 'http://testserver')
    requests.push(url)

    if (url.pathname === '/api/v1/historical-results/runs') {
      return jsonResponse({ items: [], total_count: 0, limit: 50, offset: 0 })
    }
    if (url.pathname === '/api/v1/replay-strategy-inventory') {
      const requestedLottery = url.searchParams.get('lottery_type')
      const strategies = inventory.filter((item) => item.lottery_type === requestedLottery)
      return jsonResponse({ strategy_count: strategies.length, strategies })
    }
    if (url.pathname === '/api/v1/replay-backfill/coverage') {
      return jsonResponse({
        expected_strategy_count: 0,
        expected_target_count: 0,
        expected_cell_count: 0,
        completed_cell_count: 0,
        failed_cell_count: 0,
        closed_cell_count: 0,
        complete_coverage_percent: 0,
        missing_strategy_ids: [],
        run_id: null,
      })
    }
    if (url.pathname === '/api/v1/replay-backfill/strategies') {
      const requestedLottery = url.searchParams.get('lottery_type')
      const isSecondPage = url.searchParams.has('cursor')
      const isZoneLottery = requestedLottery === ZONE_LOTTERY
      const otherLotteryItems = catalog.otherLotteryItem ? [catalog.otherLotteryItem] : []
      return jsonResponse({
        items: isZoneLottery
          ? isSecondPage ? catalog.secondPage : catalog.firstPage
          : otherLotteryItems,
        total_count: isZoneLottery ? catalog.totalCount : otherLotteryItems.length,
        history_scope: isZoneLottery
          ? catalog.historyScope
          : syntheticHistoryScope(false, requestedLottery ?? OTHER_LOTTERY),
        next_cursor: isZoneLottery && !isSecondPage ? catalog.nextCursor : null,
      })
    }

    unexpectedRequests.push(url.pathname + url.search)
    return jsonResponse({ detail: 'Unexpected synthetic UI request.' }, 404)
  })
  vi.stubGlobal('fetch', fetchMock)
  return { fetchMock, requests, unexpectedRequests }
}

async function activateBackfill(wrapper: VueWrapper): Promise<void> {
  const tabs = wrapper.findAll('nav[aria-label="Replay history sections"] button')
  expect(tabs.length).toBeGreaterThan(2)
  await tabs[2]!.trigger('click')
  await flushPromises()
}

function strategyIdentityTable(wrapper: VueWrapper) {
  const table = wrapper
    .get('[data-testid="strategy-backfill"]')
    .findAll('table')
    .find((candidate) => candidate.find('caption').exists() &&
      candidate.find('caption').text().startsWith('Strategy identities'))
  expect(table).toBeDefined()
  return table!
}

function exactIdentityRows(wrapper: VueWrapper, strategyId: string, version: string) {
  return strategyIdentityTable(wrapper).findAll('tbody tr').filter((row) => {
    const identityCell = row.find('td')
    return identityCell.find('code').text() === strategyId && identityCell.find('span').text() === version
  })
}

function syntheticDecoy(index: number): ReplayBackfillStrategyItem {
  return catalogItem({
    strategy_id: `synthetic-unrelated-strategy-${index}`,
    strategy_version: 'v1',
    display_name: `Synthetic unrelated strategy ${index}`,
    data_status: 'NO_HISTORY',
    source_kind: 'SYNTHETIC_UI_FIXTURE',
    available_target_count: 0,
  })
}

describe('Zone successor Replay History inventory UI', () => {
  it('keeps the exact Zone/v1 history identity through catalog pagination without advertising execution', async () => {
    const zoneV2 = catalogItem({
      strategy_version: 'v2',
      display_name: 'Zone Momentum Complete v2',
      data_status: 'NO_HISTORY',
      source_kind: 'SYNTHETIC_UI_FIXTURE',
      available_target_count: 0,
    })
    const { fetchMock, requests, unexpectedRequests } = installSyntheticFetch(
      [inventoryItem('HAS_HISTORY'), inventoryItem('NO_HISTORY', OTHER_LOTTERY)],
      {
        firstPage: [zoneV2, ...Array.from({ length: 99 }, (_, index) => syntheticDecoy(index))],
        secondPage: [catalogItem()],
        totalCount: 101,
        nextCursor: ZONE_CURSOR,
        otherLotteryItem: catalogItem({
          lottery_type: OTHER_LOTTERY,
          data_status: 'NO_HISTORY',
          source_kind: 'SYNTHETIC_UI_FIXTURE',
          available_target_count: 0,
        }),
        historyScope: syntheticHistoryScope(true),
      },
    )
    const wrapper = mount(ReplayHistoryPage)
    wrappers.push(wrapper)
    await flushPromises()
    await activateBackfill(wrapper)

    const initialV1Rows = exactIdentityRows(wrapper, ZONE_STRATEGY_ID, ZONE_VERSION)
    const initialV2Rows = exactIdentityRows(wrapper, ZONE_STRATEGY_ID, 'v2')
    expect(initialV1Rows).toHaveLength(1)
    expect(initialV2Rows).toHaveLength(1)
    expect(initialV1Rows[0]!.text()).toContain(ZONE_STRATEGY_ID)
    expect(initialV1Rows[0]!.text()).toContain('有歷史資料')
    expect(initialV1Rows[0]!.text()).toContain('目前沒有可用 Replay 執行器')
    expect(initialV1Rows[0]!.text()).toContain('沒有 Native binding (binding=false, runnable=false)')
    expect(initialV1Rows[0]!.text()).not.toContain('Native Backfill 可執行')
    expect(initialV1Rows[0]!.findAll('td')[1]!.text()).toBe('B649')
    expect(initialV1Rows[0]!.findAll('td')[5]!.text()).toBe('3 / 0')
    expect(initialV2Rows[0]!.findAll('td')[3]!.find('strong').text()).toBe('無歷史資料')

    const backfill = wrapper.get('[data-testid="strategy-backfill"]')
    const loadMore = backfill.findAll('button').find((button) => button.text().trim() === 'Load more strategies')
    expect(loadMore).toBeDefined()
    await loadMore!.trigger('click')
    await flushPromises()

    expect(exactIdentityRows(wrapper, ZONE_STRATEGY_ID, ZONE_VERSION)).toHaveLength(1)
    expect(exactIdentityRows(wrapper, ZONE_STRATEGY_ID, 'v2')).toHaveLength(1)
    expect(exactIdentityRows(wrapper, ZONE_STRATEGY_ID, ZONE_VERSION)[0]!.text()).toContain('有歷史資料')
    expect(exactIdentityRows(wrapper, ZONE_STRATEGY_ID, ZONE_VERSION)[0]!.findAll('td')[4]!.text()).toBe('3')

    const strategyRequests = requests.filter((url) => url.pathname === '/api/v1/replay-backfill/strategies')
    expect(strategyRequests).toHaveLength(2)
    expect(strategyRequests[0]!.searchParams.get('lottery_type')).toBe(ZONE_LOTTERY)
    expect(strategyRequests[0]!.searchParams.get('limit')).toBe('100')
    expect(strategyRequests[0]!.searchParams.has('cursor')).toBe(false)
    expect(strategyRequests[1]!.searchParams.get('cursor')).toBe(ZONE_CURSOR)

    await wrapper.get('select[name="lottery_type"]').setValue(OTHER_LOTTERY)
    await flushPromises()
    const otherLotteryRows = exactIdentityRows(wrapper, ZONE_STRATEGY_ID, ZONE_VERSION)
    expect(otherLotteryRows).toHaveLength(1)
    expect(otherLotteryRows[0]!.findAll('td')[1]!.text()).toBe('T539')
    expect(otherLotteryRows[0]!.findAll('td')[3]!.find('strong').text()).toBe('無歷史資料')
    expect(otherLotteryRows[0]!.findAll('td')[4]!.text()).toBe('0')
    expect(otherLotteryRows[0]!.findAll('td')[5]!.text()).toBe('0 / 0')
    const otherLotteryRequest = requests
      .filter((url) => url.pathname === '/api/v1/replay-backfill/strategies')
      .at(-1)
    expect(otherLotteryRequest?.searchParams.get('lottery_type')).toBe(OTHER_LOTTERY)
    expect(fetchMock).toHaveBeenCalled()
    expect(unexpectedRequests).toEqual([])
  })

  it('shows NO_HISTORY with zero counts when the exact Zone/v1 key has no stored overlay row', async () => {
    const { unexpectedRequests } = installSyntheticFetch(
      [inventoryItem('NO_HISTORY')],
      {
        firstPage: [catalogItem({
          data_status: 'NO_HISTORY',
          source_kind: 'SYNTHETIC_UI_FIXTURE',
          available_target_count: 0,
        })],
        secondPage: [],
        totalCount: 1,
        nextCursor: null,
        historyScope: syntheticHistoryScope(false),
      },
    )
    const wrapper = mount(ReplayHistoryPage)
    wrappers.push(wrapper)
    await flushPromises()
    await activateBackfill(wrapper)

    const rows = exactIdentityRows(wrapper, ZONE_STRATEGY_ID, ZONE_VERSION)
    expect(rows).toHaveLength(1)
    expect(rows[0]!.text()).toContain('無歷史資料')
    expect(rows[0]!.text()).not.toContain('581')
    expect(rows[0]!.findAll('td')[4]!.text()).toBe('0')
    expect(rows[0]!.findAll('td')[5]!.text()).toBe('0 / 0')
    expect(unexpectedRequests).toEqual([])
  })
})
