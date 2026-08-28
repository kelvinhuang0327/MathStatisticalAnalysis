// @vitest-environment jsdom

import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import B649ReplayPage from '../src/features/b649-replay/B649ReplayPage.vue'
import P638ReplayPage from '../src/features/p638-replay/P638ReplayPage.vue'
import T539ReplayPage from '../src/features/t539-replay/T539ReplayPage.vue'
import ReplayExplorer from '../src/features/replay-explorer/ReplayExplorer.vue'
import { b649Adapter } from '../src/features/replay-explorer/adapters/b649Adapter'
import { p638Adapter } from '../src/features/replay-explorer/adapters/p638Adapter'
import { t539Adapter } from '../src/features/replay-explorer/adapters/t539Adapter'
import ReplayCompareView from '../src/features/replay-explorer/components/ReplayCompareView.vue'
import ReplayDetailDrawer from '../src/features/replay-explorer/components/ReplayDetailDrawer.vue'
import ReplayMatrixView from '../src/features/replay-explorer/components/ReplayMatrixView.vue'
import ReplayTableView from '../src/features/replay-explorer/components/ReplayTableView.vue'
import ReplayTrendView from '../src/features/replay-explorer/components/ReplayTrendView.vue'
import {
  ALL_CANONICAL_TICKET_COUNTS,
  B649_AVAILABLE_TICKET_COUNTS,
  P638_AVAILABLE_TICKET_COUNTS,
  T539_AVAILABLE_TICKET_COUNTS,
  type ReplayExplorerItem,
} from '../src/features/replay-explorer/types'
import {
  B649_HISTORY_WINDOWS,
  B649_PREFIX_COUNTS,
  B649_REPRODUCTION_STATUSES,
  B649_RESEARCH_DISCLAIMER,
  B649_SUCCESS_CRITERIA,
} from '../src/api/b649MultiTicketRecords'

let fetchMock: ReturnType<typeof vi.fn<typeof fetch>>

function apiResponse(payload: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: vi.fn().mockResolvedValue(payload),
  } as unknown as Response
}

function mockB649Summary(recordsAvailable = true) {
  return {
    progress: {
      total_strategy_count: 135,
      reproduced_count: 135,
      backtested_count: 135,
      closed_count: 0,
      duplicate_alias_count: 0,
      owner_decision_required_count: 0,
      uncompleted_count: 0,
    },
    prefix_counts: [...B649_PREFIX_COUNTS],
    windows: [...B649_HISTORY_WINDOWS],
    success_criteria: [...B649_SUCCESS_CRITERIA],
    primary_ranking_criterion: 'OFFICIAL_ANY_PRIZE',
    method_families: ['frequency', 'statistical'],
    reproduction_statuses: [...B649_REPRODUCTION_STATUSES],
    catalog_sha256: 'a'.repeat(64),
    records_available: recordsAvailable,
    projection_sha256: recordsAvailable ? 'b'.repeat(64) : null,
    source_report_count: recordsAvailable ? 17 : null,
    research_disclaimer: B649_RESEARCH_DISCLAIMER,
  }
}

function mockB649Record(stratId: string, prefixCount: number, window: string) {
  return {
    strategy_id: stratId,
    strategy_version: 'v1.0',
    legacy_method_id: stratId,
    source_path: `fixture/${stratId}.json`,
    method_family: 'frequency',
    reproduction_status: 'BACKTESTED',
    duplicate_alias_target: null,
    prefix_count: prefixCount,
    window,
    criterion: 'M3_PLUS',
    rank: 1,
    official_rank: 1,
    official_any_prize_count: 540,
    official_any_prize_rate: '0.277065161621344279',
    official_random_baseline_probability: '0.269779736506368005',
    official_random_baseline_delta: '0.007285425114976274',
    unranked_reason: null,
    success_count: 540,
    effective_backtest_draw_count: 1949,
    successful_execution_count: 1949,
    historical_success_rate: '0.277065161621344279',
    random_baseline_success_rate: '0.269779736506368005',
    random_baseline_rate_difference: '0.007285425114976274',
    coverage: '1.000000000000000000',
    window_available_draws: 1949,
    window_requested_draws: 1949,
    window_complete: true,
    official_prize_counts: {
      first: 0,
      second: 1,
      third: 2,
      fourth: 10,
      fifth: 45,
      sixth: 120,
      seventh: 200,
      general: 162,
    },
    no_prize_count: 1409,
    report_sha256: 'c'.repeat(64),
    report_file_sha256: 'd'.repeat(64),
    catalog_sha256: 'a'.repeat(64),
  }
}

function mockP638Runs() {
  return {
    items: [
      {
        run_id: 'p638_wave1_reproduction',
        status: 'COMPLETE',
        lottery_type: 'P638',
        strategy_count: 10,
        draw_count: 1000,
        target_count: 1000,
        complete_target_count: 1000,
        ticket_count: 1000,
        failure_count: 0,
        first_draw_number: '100000001',
        first_draw_date: '2008-01-01',
        last_draw_number: '100001000',
        last_draw_date: '2015-12-31',
        is_idempotent_replay: true,
      },
    ],
    total_count: 1,
    limit: 25,
    offset: 0,
  }
}

function mockP638Strategies() {
  return {
    run_id: 'p638_wave1_reproduction',
    items: [
      {
        strategy_snapshot_id: 'snap1',
        run_id: 'p638_wave1_reproduction',
        strategy_id: 'p638_cold_pool_splicer',
        display_label: 'p638_cold_pool_splicer',
        strategy_version: 'v1.0',
        executable: true,
        adapter_path: null,
        native_ticket_count: 1,
        min_history: 50,
        zone1_contract: '6_OF_38',
        zone2_contract: '1_OF_8',
        lifecycle_status: 'ACTIVE',
        replay_status: 'COMPLETE',
        source_run_id: null,
        source_replay_sha256: null,
        source_paths: [],
        provenance: 'provenance_a',
        exclusion_reason: null,
        complete_target_count: 1000,
        excluded_target_count: 0,
        failed_target_count: 0,
        ticket_count: 1000,
        zone1_hit_distribution: [{ value: 0, count: 400 }, { value: 1, count: 350 }, { value: 2, count: 180 }, { value: 3, count: 60 }, { value: 4, count: 10 }],
        zone2_hit_distribution: [{ value: 0, count: 875 }, { value: 1, count: 125 }],
        first_draw_number: '100000001',
        first_draw_date: '2008-01-01',
        last_draw_number: '100001000',
        last_draw_date: '2015-12-31',
      },
    ],
    total_count: 1,
    limit: 200,
    offset: 0,
  }
}

function mockP638Rankings() {
  return {
    run_id: 'p638_wave1_reproduction',
    items: [
      {
        strategy_id: 'p638_cold_pool_splicer',
        rank: 1,
        winning_target_rate: 0.125,
        prize_tier_counts: [
          { prize_tier: 'first', count: 0 },
          { prize_tier: 'second', count: 0 },
          { prize_tier: 'third', count: 2 },
          { prize_tier: 'fourth', count: 15 },
          { prize_tier: 'fifth', count: 108 },
        ],
      },
    ],
  }
}

function mockT539Runs() {
  return {
    items: [
      {
        run_id: 't539_historical_wave1',
        schema_version: 'v1.0',
        lottery_type: 'T539',
        source_endpoint: '/api/v1/t539',
        source_sha256: 'e'.repeat(64),
        as_of_date: '2025-01-01',
        adapter_source_commit: 'f'.repeat(40),
        strategy_set_fingerprint: '1234',
        status: 'COMPLETE',
        strategy_count: 8,
        draw_count: 1200,
        eligible_target_count: 1200,
        ticket_count: 1200,
        failure_count: 0,
        first_draw_id: '096000001',
        first_draw_date: '2007-01-01',
        last_draw_id: '096001200',
        last_draw_date: '2011-12-31',
      },
    ],
    total_count: 1,
    limit: 25,
    offset: 0,
  }
}

function mockT539Strategies() {
  return {
    run_id: 't539_historical_wave1',
    items: [
      {
        run_id: 't539_historical_wave1',
        strategy_id: 't539_frequency_hot',
        strategy_version: 'v1.0',
        native_ticket_count: 1,
        min_history: 30,
        first_eligible_target_draw_id: '096000001',
        expected_target_draw_count: 1200,
        processed_target_draw_count: 1200,
        successful_target_draw_count: 1200,
        failed_target_draw_count: 0,
        status: 'COMPLETE',
        ticket_count: 1200,
        hit_distribution: [
          { value: 0, count: 500 },
          { value: 1, count: 420 },
          { value: 2, count: 210 },
          { value: 3, count: 65 },
          { value: 4, count: 5 },
        ],
      },
    ],
    total_count: 1,
    limit: 200,
    offset: 0,
  }
}

function mockT539Rankings() {
  return {
    run_id: 't539_historical_wave1',
    items: [
      {
        run_id: 't539_historical_wave1',
        rank: 1,
        strategy_id: 't539_frequency_hot',
        strategy_version: 'v1.0',
        native_ticket_count: 1,
        eligible_target_count: 1200,
        winning_target_count: 70,
        winning_target_rate: 0.0583,
        total_ticket_count: 1200,
        winning_ticket_count: 70,
        ticket_winning_rate: 0.0583,
        prize_tier_counts: [
          { prize_tier: 'first', count: 0 },
          { prize_tier: 'second', count: 5 },
          { prize_tier: 'third', count: 65 },
        ],
        highest_prize_tier_achieved: 'second',
        first_eligible_draw: '096000001',
        last_eligible_draw: '096001200',
        prize_rule_version: 'v1.0',
        prize_rule_provenance: 'canonical',
      },
    ],
  }
}

beforeEach(() => {
  fetchMock = vi.fn()
  globalThis.fetch = fetchMock
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('Shared Replay Explorer R2 Architecture', () => {
  it('verifies canonical ticket count constraints per game', () => {
    expect(B649_AVAILABLE_TICKET_COUNTS).toEqual([5, 10, 15, 20])
    expect(P638_AVAILABLE_TICKET_COUNTS).toEqual([1])
    expect(T539_AVAILABLE_TICKET_COUNTS).toEqual([1])
    expect(ALL_CANONICAL_TICKET_COUNTS).toHaveLength(20)
  })

  it('renders B649 Replay Page with shared engine and handles Table view', async () => {
    fetchMock.mockImplementation((url: string | URL | Request) => {
      const u = String(url)
      if (u.includes('/b649-multi-ticket-records/summary')) {
        return Promise.resolve(apiResponse(mockB649Summary()))
      }
      if (u.includes('/b649-multi-ticket-records')) {
        return Promise.resolve(
          apiResponse({
            items: [mockB649Record('backtest_biglotto_coldpool_15', 5, 'FULL')],
            total: 1,
            limit: 100,
            offset: 0,
            prefix_count: 5,
            window: 'FULL',
            criterion: 'M3_PLUS',
            research_disclaimer: B649_RESEARCH_DISCLAIMER,
          }),
        )
      }
      return Promise.reject(new Error(`Unhandled URL: ${u}`))
    })

    const wrapper = mount(B649ReplayPage)
    await flushPromises()

    expect(wrapper.text()).toContain('B649 Replay')
    expect(wrapper.text()).toContain('backtest_biglotto_coldpool_15')
    expect(wrapper.text()).toContain('27.71%')
    expect(wrapper.text()).toContain('+0.73%')
    expect(wrapper.text()).toContain('DESCRIPTIVE LEADER')

    // Check table component presence
    expect(wrapper.findComponent(ReplayTableView).exists()).toBe(true)
  })

  it('renders P638 Replay Page with shared engine and exposes Run/Date Range without false 50/300/750 relabeling', async () => {
    fetchMock.mockImplementation((url: string | URL | Request) => {
      const u = String(url)
      if (u.includes('/p638-historical/runs') && !u.includes('/strategies') && !u.includes('/rankings')) {
        return Promise.resolve(apiResponse(mockP638Runs()))
      }
      if (u.includes('/p638-historical/runs/p638_wave1_reproduction/strategies')) {
        return Promise.resolve(apiResponse(mockP638Strategies()))
      }
      if (u.includes('/p638-historical/runs/p638_wave1_reproduction/rankings')) {
        return Promise.resolve(apiResponse(mockP638Rankings()))
      }
      return Promise.reject(new Error(`Unhandled URL: ${u}`))
    })

    const wrapper = mount(P638ReplayPage)
    await flushPromises()

    expect(wrapper.text()).toContain('P638 Replay')
    expect(wrapper.text()).toContain('p638_cold_pool_splicer')
    expect(wrapper.text()).toContain('12.50%')
    expect(wrapper.text()).toContain('Run: p638_wave1_reproduction')
    // Ensure no false 50/300/750 horizon text is applied
    expect(wrapper.text()).not.toContain('Short Horizon · 50')
  })

  it('renders T539 Replay Page with shared engine and exposes Run/Draw Range', async () => {
    fetchMock.mockImplementation((url: string | URL | Request) => {
      const u = String(url)
      if (u.includes('/t539-historical/runs') && !u.includes('/strategies') && !u.includes('/rankings')) {
        return Promise.resolve(apiResponse(mockT539Runs()))
      }
      if (u.includes('/t539-historical/runs/t539_historical_wave1/strategies')) {
        return Promise.resolve(apiResponse(mockT539Strategies()))
      }
      if (u.includes('/t539-historical/runs/t539_historical_wave1/rankings')) {
        return Promise.resolve(apiResponse(mockT539Rankings()))
      }
      return Promise.reject(new Error(`Unhandled URL: ${u}`))
    })

    const wrapper = mount(T539ReplayPage)
    await flushPromises()

    expect(wrapper.text()).toContain('T539 Replay')
    expect(wrapper.text()).toContain('t539_frequency_hot')
    expect(wrapper.text()).toContain('5.83%')
    expect(wrapper.text()).toContain('Run: t539_historical_wave1')
  })

  it('switches between Table, Matrix, Trend, and Compare view modes', async () => {
    fetchMock.mockImplementation((url: string | URL | Request) => {
      const u = String(url)
      if (u.includes('/b649-multi-ticket-records/summary')) {
        return Promise.resolve(apiResponse(mockB649Summary()))
      }
      if (u.includes('/b649-multi-ticket-records')) {
        return Promise.resolve(
          apiResponse({
            items: [mockB649Record('backtest_biglotto_coldpool_15', 5, 'FULL')],
            total: 1,
            limit: 100,
            offset: 0,
            prefix_count: 5,
            window: 'FULL',
            criterion: 'M3_PLUS',
            research_disclaimer: B649_RESEARCH_DISCLAIMER,
          }),
        )
      }
      return Promise.reject(new Error(`Unhandled URL: ${u}`))
    })

    const wrapper = mount(ReplayExplorer, {
      props: { adapter: b649Adapter },
    })
    await flushPromises()

    // 1. Initial view is Table
    expect(wrapper.findComponent(ReplayTableView).exists()).toBe(true)

    // 2. Switch to Matrix
    const buttons = wrapper.findAll('.view-mode-bar button')
    const matrixBtn = buttons.find((b) => b.text().includes('Matrix'))
    expect(matrixBtn).toBeDefined()
    await matrixBtn!.trigger('click')
    await flushPromises()
    expect(wrapper.findComponent(ReplayMatrixView).exists()).toBe(true)

    // 3. Switch to Trend
    const trendBtn = buttons.find((b) => b.text().includes('Trend'))
    expect(trendBtn).toBeDefined()
    await trendBtn!.trigger('click')
    await flushPromises()
    expect(wrapper.findComponent(ReplayTrendView).exists()).toBe(true)

    // 4. Switch to Compare
    const compareBtn = buttons.find((b) => b.text().includes('Compare'))
    expect(compareBtn).toBeDefined()
    await compareBtn!.trigger('click')
    await flushPromises()
    expect(wrapper.findComponent(ReplayCompareView).exists()).toBe(true)
  })

  it('opens and closes keyboard-accessible Detail Drawer on inspection', async () => {
    fetchMock.mockImplementation((url: string | URL | Request) => {
      const u = String(url)
      if (u.includes('/b649-multi-ticket-records/summary')) {
        return Promise.resolve(apiResponse(mockB649Summary()))
      }
      if (u.includes('/b649-multi-ticket-records')) {
        return Promise.resolve(
          apiResponse({
            items: [mockB649Record('backtest_biglotto_coldpool_15', 5, 'FULL')],
            total: 1,
            limit: 100,
            offset: 0,
            prefix_count: 5,
            window: 'FULL',
            criterion: 'M3_PLUS',
            research_disclaimer: B649_RESEARCH_DISCLAIMER,
          }),
        )
      }
      return Promise.reject(new Error(`Unhandled URL: ${u}`))
    })

    const wrapper = mount(ReplayExplorer, {
      props: { adapter: b649Adapter },
    })
    await flushPromises()

    // Inspect button in Table view
    const inspectBtn = wrapper.find('.cell--actions button.button--primary')
    expect(inspectBtn.exists()).toBe(true)
    await inspectBtn.trigger('click')
    await flushPromises()

    const drawer = wrapper.findComponent(ReplayDetailDrawer)
    expect(drawer.exists()).toBe(true)
    expect(drawer.props('isOpen')).toBe(true)
    expect(wrapper.text()).toContain('Prize Tier Breakdown')

    // Close via close button
    const closeBtn = drawer.find('.close-button')
    expect(closeBtn.exists()).toBe(true)
    await closeBtn.trigger('click')
    await flushPromises()
    expect(drawer.props('isOpen')).toBe(false)
  })

  it('preserves unavailable ticket counts as unavailable rather than converting to zero', async () => {
    fetchMock.mockImplementation((url: string | URL | Request) => {
      const u = String(url)
      if (u.includes('/b649-multi-ticket-records/summary')) {
        return Promise.resolve(apiResponse(mockB649Summary()))
      }
      if (u.includes('/b649-multi-ticket-records')) {
        return Promise.resolve(
          apiResponse({
            items: [mockB649Record('backtest_biglotto_coldpool_15', 5, 'FULL')],
            total: 1,
            limit: 100,
            offset: 0,
            prefix_count: 5,
            window: 'FULL',
            criterion: 'M3_PLUS',
            research_disclaimer: B649_RESEARCH_DISCLAIMER,
          }),
        )
      }
      return Promise.reject(new Error(`Unhandled URL: ${u}`))
    })

    // Load items for B649 with ticket counts [5, 1, 2]
    const items = await b649Adapter.loadItems({
      game: 'B649',
      selectedStrategyIds: [],
      selectedTicketCounts: [5, 1, 2],
      selectedPeriodKey: 'FULL',
      searchQuery: '',
    })

    const count5Item = items.find((i) => i.ticketCount === 5)
    const count1Item = items.find((i) => i.ticketCount === 1)

    expect(count5Item?.isAvailable).toBe(true)
    expect(count5Item?.hitRate).not.toBeNull()

    // Unavailable counts must be explicitly false with null hitRate
    expect(count1Item?.isAvailable).toBe(false)
    expect(count1Item?.hitRate).toBeNull()
    expect(count1Item?.hitRateFormatted).toBe('Unavailable')
    expect(count1Item?.evaluatedTargets).toBeNull()
    expect(count1Item?.winningTargets).toBeNull()
    expect(count1Item?.baselineDelta).toBeNull()
  })

  it('audits user-visible copy for zero Chinese characters across replay explorer', async () => {
    const rawFiles = [
      b649Adapter.gameDescription,
      b649Adapter.gameTitle,
      p638Adapter.gameDescription,
      p638Adapter.gameTitle,
      t539Adapter.gameDescription,
      t539Adapter.gameTitle,
    ]

    const cjkRegex = /[\u4e00-\u9fff\u3400-\u4dbf]/
    for (const text of rawFiles) {
      expect(cjkRegex.test(text)).toBe(false)
    }
  })

  it('supports interactive strategy picker multi-selection, select all, and clear', async () => {
    fetchMock.mockImplementation((url: string | URL | Request) => {
      const u = String(url)
      if (u.includes('/b649-multi-ticket-records/summary')) {
        return Promise.resolve(apiResponse(mockB649Summary()))
      }
      if (u.includes('/b649-multi-ticket-records')) {
        return Promise.resolve(
          apiResponse({
            items: [
              mockB649Record('backtest_biglotto_coldpool_15', 5, 'FULL'),
              mockB649Record('backtest_biglotto_6bet_ewma', 5, 'FULL'),
            ],
            total: 2,
            limit: 100,
            offset: 0,
            prefix_count: 5,
            window: 'FULL',
            criterion: 'M3_PLUS',
            research_disclaimer: B649_RESEARCH_DISCLAIMER,
          }),
        )
      }
      return Promise.reject(new Error(`Unhandled URL: ${u}`))
    })

    const wrapper = mount(ReplayExplorer, {
      props: { adapter: b649Adapter },
    })
    await flushPromises()

    // 1. Open picker
    const togglePickerBtn = wrapper.find('.text-link-btn')
    expect(togglePickerBtn.exists()).toBe(true)
    await togglePickerBtn.trigger('click')
    await flushPromises()

    const dropdown = wrapper.find('.strategy-dropdown-panel')
    expect(dropdown.exists()).toBe(true)

    // 2. Click Select All Available
    const selectAllBtn = dropdown.findAll('button').find((b) => b.text().includes('Select All Available'))
    expect(selectAllBtn).toBeDefined()
    await selectAllBtn!.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('Strategies Selected')

    // 3. Click Clear Selection
    const clearBtn = dropdown.findAll('button').find((b) => b.text().includes('Clear Selection'))
    expect(clearBtn).toBeDefined()
    await clearBtn!.trigger('click')
    await flushPromises()

    expect(wrapper.text()).not.toContain('Strategies Selected')
  })

  it('supports compare view with up to 4 strategies and strategy removal', async () => {
    fetchMock.mockImplementation((url: string | URL | Request) => {
      const u = String(url)
      if (u.includes('/b649-multi-ticket-records/summary')) {
        return Promise.resolve(apiResponse(mockB649Summary()))
      }
      if (u.includes('/b649-multi-ticket-records')) {
        return Promise.resolve(
          apiResponse({
            items: [
              mockB649Record('backtest_biglotto_coldpool_15', 5, 'FULL'),
              mockB649Record('backtest_biglotto_6bet_ewma', 5, 'FULL'),
            ],
            total: 2,
            limit: 100,
            offset: 0,
            prefix_count: 5,
            window: 'FULL',
            criterion: 'M3_PLUS',
            research_disclaimer: B649_RESEARCH_DISCLAIMER,
          }),
        )
      }
      return Promise.reject(new Error(`Unhandled URL: ${u}`))
    })

    const wrapper = mount(ReplayExplorer, {
      props: { adapter: b649Adapter },
    })
    await flushPromises()

    // Click compare button on first row
    const compareActionBtns = wrapper.findAll('.cell--actions button.button--quiet')
    expect(compareActionBtns.length).toBeGreaterThan(0)
    await compareActionBtns[0]!.trigger('click')
    await flushPromises()

    // Switch to compare view
    const compareViewTab = wrapper.findAll('.view-mode-bar button').find((b) => b.text().includes('Compare'))
    await compareViewTab!.trigger('click')
    await flushPromises()

    const compareView = wrapper.findComponent(ReplayCompareView)
    expect(compareView.exists()).toBe(true)
    expect(compareView.text()).toContain('backtest_biglotto_coldpool_15')

    // Remove strategy from comparison
    const removeBtn = compareView.find('.remove-btn')
    expect(removeBtn.exists()).toBe(true)
    await removeBtn.trigger('click')
    await flushPromises()

    expect(compareView.text()).toContain('No Strategies Selected for Comparison')
  })

  it('closes detail drawer on Escape keydown event', async () => {
    fetchMock.mockImplementation((url: string | URL | Request) => {
      const u = String(url)
      if (u.includes('/b649-multi-ticket-records/summary')) {
        return Promise.resolve(apiResponse(mockB649Summary()))
      }
      if (u.includes('/b649-multi-ticket-records')) {
        return Promise.resolve(
          apiResponse({
            items: [mockB649Record('backtest_biglotto_coldpool_15', 5, 'FULL')],
            total: 1,
            limit: 100,
            offset: 0,
            prefix_count: 5,
            window: 'FULL',
            criterion: 'M3_PLUS',
            research_disclaimer: B649_RESEARCH_DISCLAIMER,
          }),
        )
      }
      return Promise.reject(new Error(`Unhandled URL: ${u}`))
    })

    const wrapper = mount(ReplayExplorer, {
      props: { adapter: b649Adapter },
      attachTo: document.body,
    })
    await flushPromises()

    // Open drawer
    const inspectBtn = wrapper.find('.cell--actions button.button--primary')
    await inspectBtn.trigger('click')
    await flushPromises()

    const drawer = wrapper.findComponent(ReplayDetailDrawer)
    expect(drawer.props('isOpen')).toBe(true)

    // Press Escape
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    await flushPromises()

    expect(drawer.props('isOpen')).toBe(false)
    wrapper.unmount()
  })

  it('verifies game switcher buttons exist and switch between B649, P638, and T539', async () => {
    fetchMock.mockImplementation((url: string | URL | Request) => {
      const u = String(url)
      if (u.includes('/b649-multi-ticket-records/summary')) {
        return Promise.resolve(apiResponse(mockB649Summary()))
      }
      if (u.includes('/b649-multi-ticket-records')) {
        return Promise.resolve(
          apiResponse({
            items: [mockB649Record('backtest_biglotto_coldpool_15', 5, 'FULL')],
            total: 1,
            limit: 100,
            offset: 0,
            prefix_count: 5,
            window: 'FULL',
            criterion: 'M3_PLUS',
            research_disclaimer: B649_RESEARCH_DISCLAIMER,
          }),
        )
      }
      return Promise.reject(new Error(`Unhandled URL: ${u}`))
    })

    const wrapper = mount(B649ReplayPage)
    await flushPromises()

    const switcher = wrapper.find('.game-switcher')
    expect(switcher.exists()).toBe(true)

    const buttons = switcher.findAll('button')
    expect(buttons).toHaveLength(3)
    expect(buttons[0]?.text()).toBe('B649')
    expect(buttons[1]?.text()).toBe('P638')
    expect(buttons[2]?.text()).toBe('T539')

    expect(buttons[0]?.attributes('aria-pressed')).toBe('true')
    expect(buttons[1]?.attributes('aria-pressed')).toBe('false')
  })
})
