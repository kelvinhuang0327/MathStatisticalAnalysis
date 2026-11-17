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

const K30_GEOMETRY_ID = 'evolution_h12_k30_geometry_completion'
const K30_RANDOM_ID = 'evolution_h12_k30_matched_random_completion'
const K30_VERSION = 'v0.1'

function k30InventoryItem(strategyId: string, displayName: string, status: string) {
  return {
    lottery_type: 'BIG_LOTTO',
    strategy_id: strategyId,
    display_name: displayName,
    strategy_version: K30_VERSION,
    source_kind: 'REPLAY_BACKFILL_IMPORTED_RESULT',
    source_locator: `src/lottolab/application/replay_strategy_inventory.py#${strategyId}`,
    lifecycle_status: 'UNREGISTERED_IDENTIFIED',
    replay_data_status: 'NO_HISTORY',
    execution_capability: 'UNAVAILABLE',
    reconstructable: false,
    wrapper_callable: false,
    backfill_native_binding: false,
    backfill_runnable: false,
    execution_block_reason: 'NO_CURRENT_NATIVE_BINDING',
    reconstruction_reason: 'Static inventory test item',
    historical_data_count: 0,
    historical_execution_count: 0,
    source_statuses: [status],
  }
}

function k30StrategyCatalogItem(
  strategyId: string,
  displayName: string,
  dataStatus: string,
  availableTargetCount: number,
) {
  return {
    strategy_id: strategyId,
    strategy_version: K30_VERSION,
    display_name: displayName,
    lottery_type: 'BIG_LOTTO',
    lifecycle_status: 'UNREGISTERED_IDENTIFIED',
    data_status: dataStatus,
    source_kind: 'REPLAY_BACKFILL_IMPORTED_RESULT',
    executable: false,
    available_target_count: availableTargetCount,
    training_status: 'NOT_TRAINABLE',
    reconstructable: false,
    wrapper_callable: false,
    backfill_native_binding: false,
    backfill_runnable: false,
    execution_block_reason: 'NO_CURRENT_NATIVE_BINDING',
  }
}

function installApi(hasHistoryOverlay: boolean) {
  const inventoryItems = [
    k30InventoryItem(K30_GEOMETRY_ID, 'K30 Geometry (歷史研究策略)', 'RESEARCH_STRATEGY'),
    k30InventoryItem(K30_RANDOM_ID, 'K30 Matched Random (隨機補票對照組)', 'CONTROL_BASELINE'),
  ]

  const catalogItems = hasHistoryOverlay
    ? [
        k30StrategyCatalogItem(
          K30_GEOMETRY_ID,
          'K30 Geometry (歷史研究策略)',
          'HAS_HISTORY',
          730,
        ),
        k30StrategyCatalogItem(
          K30_RANDOM_ID,
          'K30 Matched Random (隨機補票對照組)',
          'HAS_HISTORY',
          730,
        ),
      ]
    : [
        k30StrategyCatalogItem(
          K30_GEOMETRY_ID,
          'K30 Geometry (歷史研究策略)',
          'NO_HISTORY',
          0,
        ),
        k30StrategyCatalogItem(
          K30_RANDOM_ID,
          'K30 Matched Random (隨機補票對照組)',
          'NO_HISTORY',
          0,
        ),
      ]

  const fetchMock = vi.fn<typeof fetch>().mockImplementation((input) => {
    const url = new URL(String(input), 'http://localhost')
    if (url.pathname === '/api/v1/replay-strategy-inventory') {
      return Promise.resolve(
        apiResponse({
          strategy_count: inventoryItems.length,
          strategies: inventoryItems,
        }),
      )
    }
    if (url.pathname === '/api/v1/replay-backfill/strategies') {
      return Promise.resolve(
        apiResponse({
          items: catalogItems,
          total_count: catalogItems.length,
          next_cursor: null,
        }),
      )
    }
    if (url.pathname === '/api/v1/replay-backfill/coverage') {
      return Promise.resolve(
        apiResponse({
          expected_strategy_count: 2,
          expected_target_count: hasHistoryOverlay ? 730 : 0,
          expected_cell_count: hasHistoryOverlay ? 1460 : 0,
          completed_cell_count: hasHistoryOverlay ? 1460 : 0,
          failed_cell_count: 0,
          closed_cell_count: 0,
          complete_coverage_percent: 100,
          missing_strategy_ids: [],
          run_id: 'k30-test-run',
        }),
      )
    }
    if (url.pathname === '/api/v1/replay-backfill/predictions') {
      return Promise.resolve(
        apiResponse({
          run_id: 'k30-test-run',
          total_count: 0,
          items: [],
          next_cursor: null,
        }),
      )
    }
    if (url.pathname === '/api/v1/historical-results/runs') {
      return Promise.resolve(
        apiResponse({ items: [], total_count: 0, limit: 50, offset: 0 }),
      )
    }
    throw new Error(`Unexpected fetch: ${url}`)
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

async function openBackfillTab() {
  const wrapper = mount(ReplayHistoryPage)
  await flushPromises()
  const buttons = wrapper.findAll('nav[aria-label="Replay history sections"] button')
  await buttons[2]?.trigger('click')
  await flushPromises()
  return wrapper
}

afterEach(() => {
  vi.restoreAllMocks()
})

describe('K30 Geometry and Matched Random Inventory UI Display', () => {
  it('displays both K30 strategies with distinct role labels and unavailable execution capability', async () => {
    installApi(false)
    const wrapper = await openBackfillTab()

    const text = wrapper.text()
    expect(text).toContain('K30 Geometry (歷史研究策略)')
    expect(text).toContain('K30 Matched Random (隨機補票對照組)')
    expect(text).toContain(K30_GEOMETRY_ID)
    expect(text).toContain(K30_RANDOM_ID)
    expect(text).toContain(K30_VERSION)

    // Verify execution capability is unavailable
    expect(text).toContain('目前沒有可用 Replay 執行器')
    expect(text).toContain('未證明可正式回填：沒有 Native binding')
  })

  it('displays HAS_HISTORY when DB overlay supplies 730 draws for both strategies', async () => {
    installApi(true)
    const wrapper = await openBackfillTab()

    const text = wrapper.text()
    expect(text).toContain('K30 Geometry (歷史研究策略)')
    expect(text).toContain('K30 Matched Random (隨機補票對照組)')
    expect(text).toContain('有歷史資料')
    expect(text).toContain('730')

    // Matched Random control role remains clearly visible
    expect(text).toContain('隨機補票對照組')
    // Research strategy role remains clearly visible
    expect(text).toContain('歷史研究策略')
  })

  it('filters and retains K30 strategies during search query without excluding control group', async () => {
    installApi(true)
    const wrapper = await openBackfillTab()

    const searchInput = wrapper.get('input[name="strategy_search"]')
    await searchInput.setValue('matched_random')
    await flushPromises()

    const text = wrapper.text()
    expect(text).toContain('K30 Matched Random (隨機補票對照組)')
    expect(text).not.toContain('K30 Geometry (歷史研究策略)')
  })
})
