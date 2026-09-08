// @vitest-environment jsdom
import { readFileSync } from 'node:fs'
import type { B649K5Record, B649K5RecordPage, B649K10Record } from '../src/api/b649MultiTicketRecords'

const k5Projection = JSON.parse(readFileSync('../src/lottolab/strategies/data/biglotto_exact_native_k5_115000084_records_v1.json', 'utf8'))
const k5Packaged = k5Projection.records as B649K5Record[]
function k5Page(window: string, records = k5Packaged): B649K5RecordPage {
  const items = records.filter((r) => r.window === window)
  return {
    items, total: items.length, limit: 100, offset: 0, ticket_count: 5,
    window: window as B649K5RecordPage['window'], criterion: 'OFFICIAL_ANY_PRIZE',
    research_disclaimer: '歷史成功率、排名與隨機基準差異僅供描述性研究，不構成未來預測、推薦、上線決策或中獎保證。',
    projection_sha256: k5Projection.projection_sha256, provenance: k5Projection.provenance,
    window_boundary: k5Packaged.find((r) => r.window === window)!.window_boundary,
    ties: k5Projection.ties_by_window[window],
  }
}
const k10Packaged = JSON.parse(readFileSync('../src/lottolab/strategies/data/biglotto_exact_native_k10_115000084_records_v1.json', 'utf8')).records as B649K10Record[]
function k10Page(window: string, records = k10Packaged) {
  const items = records.filter((r) => r.window === window)
  return { items, total: items.length, limit: 100, offset: 0, ticket_count: 10, window, criterion: 'OFFICIAL_ANY_PRIZE', research_disclaimer: '歷史成功率、排名與隨機基準差異僅供描述性研究，不構成未來預測、推薦、上線決策或中獎保證。' }
}

import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import RankingMatrixPage from '../src/features/ranking-matrix/RankingMatrixPage.vue'
import { B649_RESEARCH_DISCLAIMER } from '../src/api/b649MultiTicketRecords'

let fetchMock: ReturnType<typeof vi.fn<typeof fetch>>

function apiResponse(payload: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: vi.fn().mockResolvedValue(payload),
  } as unknown as Response
}

const mockB649Summary = {
  progress: {
    total_strategy_count: 221,
    reproduced_count: 135,
    backtested_count: 135,
    closed_count: 74,
    duplicate_alias_count: 12,
    owner_decision_required_count: 0,
    uncompleted_count: 0,
  },
  prefix_counts: [5, 10, 15, 20],
  windows: ['FULL', 'RECENT_750', 'RECENT_300', 'RECENT_50'],
  success_criteria: [
    'M3_PLUS',
    'M4_PLUS',
    'M5_PLUS',
    'M6',
    'M2_PLUS_SPECIAL',
    'M3_PLUS_SPECIAL',
    'M4_PLUS_SPECIAL',
    'M5_PLUS_SPECIAL',
  ],
  method_families: ['coldpool', 'ewma', 'ml', 'orthogonal'],
  reproduction_statuses: ['BACKTESTED', 'CLOSED_UNEXECUTABLE', 'DUPLICATE_ALIAS'],
  catalog_sha256: 'a'.repeat(64),
  records_available: true,
  projection_sha256: 'b'.repeat(64),
  source_report_count: 221,
  metrics_available_strategy_count: 135,
  metrics_unavailable_strategy_count: 86,
  primary_ranking_criterion: 'OFFICIAL_ANY_PRIZE',
  research_disclaimer: B649_RESEARCH_DISCLAIMER,
}

const mockB649Records5_300 = {
  total: 3,
  limit: 100,
  offset: 0,
  prefix_count: 5,
  window: 'RECENT_300',
  criterion: 'M3_PLUS',
  research_disclaimer: B649_RESEARCH_DISCLAIMER,
  items: [
    {
      strategy_id: 'backtest_biglotto_coldpool_15',
      strategy_version: 'v1.0',
      legacy_method_id: 'coldpool_15',
      source_path: 'strategies/coldpool_15.py',
      method_family: 'coldpool',
      reproduction_status: 'BACKTESTED',
      duplicate_alias_target: null,
      prefix_count: 5,
      window: 'RECENT_300',
      criterion: 'M3_PLUS',
      rank: 1,
      official_rank: 1,
      official_any_prize_count: 75,
      official_any_prize_rate: '0.250000000000000000',
      official_random_baseline_probability: '0.220000000000000000',
      official_random_baseline_delta: '0.030000000000000000',
      unranked_reason: null,
      success_count: 75,
      effective_backtest_draw_count: 300,
      successful_execution_count: 300,
      historical_success_rate: '0.250000000000000000',
      random_baseline_success_rate: '0.220000000000000000',
      random_baseline_rate_difference: '0.030000000000000000',
      coverage: '1.000000000000000000',
      window_available_draws: 300,
      window_requested_draws: 300,
      window_complete: true,
      official_prize_counts: { first: 1, second: 0, third: 2, fourth: 5, fifth: 10, sixth: 20, seventh: 37, general: 0 },
      no_prize_count: 225,
      report_sha256: 'c'.repeat(64),
      report_file_sha256: 'd'.repeat(64),
      catalog_sha256: 'a'.repeat(64),
      authority_mode: 'HISTORICAL_SEALED_EVIDENCE_V1',
      metrics_unavailable_reason: null,
    },
    {
      strategy_id: 'backtest_biglotto_6bet_ewma',
      strategy_version: 'v1.0',
      legacy_method_id: '6bet_ewma',
      source_path: 'strategies/6bet_ewma.py',
      method_family: 'ewma',
      reproduction_status: 'BACKTESTED',
      duplicate_alias_target: null,
      prefix_count: 5,
      window: 'RECENT_300',
      criterion: 'M3_PLUS',
      rank: 2,
      official_rank: 2,
      official_any_prize_count: 66,
      official_any_prize_rate: '0.220000000000000000',
      official_random_baseline_probability: '0.220000000000000000',
      official_random_baseline_delta: '-0.010000000000000000',
      unranked_reason: null,
      success_count: 66,
      effective_backtest_draw_count: 300,
      successful_execution_count: 300,
      historical_success_rate: '0.220000000000000000',
      random_baseline_success_rate: '0.220000000000000000',
      random_baseline_rate_difference: '-0.010000000000000000',
      coverage: '1.000000000000000000',
      window_available_draws: 300,
      window_requested_draws: 300,
      window_complete: true,
      official_prize_counts: { first: 0, second: 1, third: 1, fourth: 4, fifth: 10, sixth: 15, seventh: 35, general: 0 },
      no_prize_count: 234,
      report_sha256: 'c'.repeat(64),
      report_file_sha256: 'd'.repeat(64),
      catalog_sha256: 'a'.repeat(64),
      authority_mode: 'HISTORICAL_SEALED_EVIDENCE_V1',
      metrics_unavailable_reason: null,
    },
    {
      strategy_id: 'quick_ml_predict',
      strategy_version: 'v1.0',
      legacy_method_id: 'quick_ml_predict',
      source_path: 'strategies/quick_ml.py',
      method_family: 'ml',
      reproduction_status: 'BACKTESTED',
      duplicate_alias_target: null,
      prefix_count: 5,
      window: 'RECENT_300',
      criterion: 'M3_PLUS',
      rank: 3,
      official_rank: 3,
      official_any_prize_count: 1,
      official_any_prize_rate: '0.500000000000000000',
      official_random_baseline_probability: '0.220000000000000000',
      official_random_baseline_delta: '0.280000000000000000',
      unranked_reason: null,
      success_count: 1,
      effective_backtest_draw_count: 2,
      successful_execution_count: 2,
      historical_success_rate: '0.500000000000000000',
      random_baseline_success_rate: '0.220000000000000000',
      random_baseline_rate_difference: '0.280000000000000000',
      coverage: '0.006700000000000000',
      window_available_draws: 300,
      window_requested_draws: 300,
      window_complete: false,
      official_prize_counts: { first: 0, second: 0, third: 0, fourth: 0, fifth: 0, sixth: 1, seventh: 0, general: 0 },
      no_prize_count: 1,
      report_sha256: 'c'.repeat(64),
      report_file_sha256: 'd'.repeat(64),
      catalog_sha256: 'a'.repeat(64),
      authority_mode: 'HISTORICAL_SEALED_EVIDENCE_V1',
      metrics_unavailable_reason: null,
    },
  ],
}

const mockB649Records20_50 = {
  total: 2,
  limit: 100,
  offset: 0,
  prefix_count: 20,
  window: 'RECENT_50',
  criterion: 'M3_PLUS',
  research_disclaimer: B649_RESEARCH_DISCLAIMER,
  items: [
    {
      strategy_id: 'backtest_biglotto_coldpool_15',
      strategy_version: 'v1.0',
      legacy_method_id: 'coldpool_15',
      source_path: 'strategies/coldpool_15.py',
      method_family: 'coldpool',
      reproduction_status: 'BACKTESTED',
      duplicate_alias_target: null,
      prefix_count: 20,
      window: 'RECENT_50',
      criterion: 'M3_PLUS',
      rank: 1,
      official_rank: 1,
      official_any_prize_count: 24,
      official_any_prize_rate: '0.480000000000000000',
      official_random_baseline_probability: '0.466800000000000000',
      official_random_baseline_delta: '0.013200000000000000',
      unranked_reason: null,
      success_count: 24,
      effective_backtest_draw_count: 50,
      successful_execution_count: 50,
      historical_success_rate: '0.480000000000000000',
      random_baseline_success_rate: '0.466800000000000000',
      random_baseline_rate_difference: '0.013200000000000000',
      coverage: '1.000000000000000000',
      window_available_draws: 50,
      window_requested_draws: 50,
      window_complete: true,
      official_prize_counts: { first: 0, second: 0, third: 1, fourth: 2, fifth: 3, sixth: 8, seventh: 10, general: 0 },
      no_prize_count: 26,
      report_sha256: 'c'.repeat(64),
      report_file_sha256: 'd'.repeat(64),
      catalog_sha256: 'a'.repeat(64),
      authority_mode: 'HISTORICAL_SEALED_EVIDENCE_V1',
      metrics_unavailable_reason: null,
    },
    {
      strategy_id: 'backtest_biglotto_6bet_ewma',
      strategy_version: 'v1.0',
      legacy_method_id: '6bet_ewma',
      source_path: 'strategies/6bet_ewma.py',
      method_family: 'ewma',
      reproduction_status: 'BACKTESTED',
      duplicate_alias_target: null,
      prefix_count: 20,
      window: 'RECENT_50',
      criterion: 'M3_PLUS',
      rank: 2,
      official_rank: 2,
      official_any_prize_count: 23,
      official_any_prize_rate: '0.460000000000000000',
      official_random_baseline_probability: '0.466800000000000000',
      official_random_baseline_delta: '-0.006800000000000000',
      unranked_reason: null,
      success_count: 23,
      effective_backtest_draw_count: 50,
      successful_execution_count: 50,
      historical_success_rate: '0.460000000000000000',
      random_baseline_success_rate: '0.466800000000000000',
      random_baseline_rate_difference: '-0.006800000000000000',
      coverage: '1.000000000000000000',
      window_available_draws: 50,
      window_requested_draws: 50,
      window_complete: true,
      official_prize_counts: { first: 0, second: 0, third: 0, fourth: 1, fifth: 4, sixth: 7, seventh: 11, general: 0 },
      no_prize_count: 27,
      report_sha256: 'c'.repeat(64),
      report_file_sha256: 'd'.repeat(64),
      catalog_sha256: 'a'.repeat(64),
      authority_mode: 'HISTORICAL_SEALED_EVIDENCE_V1',
      metrics_unavailable_reason: null,
    },
  ],
}

const mockB649ExactNativeRecords2_300 = {
  total: 3,
  limit: 100,
  offset: 0,
  ticket_count: 2,
  window: 'RECENT_300',
  criterion: 'OFFICIAL_ANY_PRIZE',
  research_disclaimer: B649_RESEARCH_DISCLAIMER,
  items: [
    {
      strategy_id: 'backtest_biglotto_coldpool_15',
      strategy_version: 'v1.0',
      legacy_method_id: 'coldpool_15',
      source_path: 'strategies/coldpool_15.py',
      method_family: 'coldpool',
      reproduction_status: 'BACKTESTED',
      duplicate_alias_target: null,
      ticket_count: 2,
      window: 'RECENT_300',
      criterion: 'OFFICIAL_ANY_PRIZE',
      metric_status: 'AVAILABLE',
      rankable: true,
      unavailable_reason: null,
      metrics_unavailable_reason: null,
      unranked_reason: 'RANKED_BACKTEST_EVIDENCE_AVAILABLE',
      official_any_prize_count: 18,
      official_any_prize_rate: '0.060000000000000000',
      official_random_baseline_probability: '0.060945547814818275',
      official_random_baseline_delta: '-0.000945547814818275',
      coverage: '1.000000000000000000',
      official_prize_counts: { first: 0, second: 0, third: 0, fourth: 0, fifth: 0, sixth: 0, seventh: 5, general: 13 },
      no_prize_count: 282,
      available_observation_count: 300,
      effective_backtest_draw_count: 300,
      successful_observation_count: 18,
      window_available_draws: 300,
      window_requested_draws: 300,
      window_complete: true,
      native_ticket_count_classification: 'FIXED_EXACT_NATIVE_TICKET_COUNT',
      authority_mode: 'FRESH_CURRENT_CATALOG_REPRODUCTION_V1',
      catalog_sha256: 'a'.repeat(64),
      official_rank: null,
    },
    {
      strategy_id: 'backtest_biglotto_6bet_ewma',
      strategy_version: 'v1.0',
      legacy_method_id: '6bet_ewma',
      source_path: 'strategies/6bet_ewma.py',
      method_family: 'ewma',
      reproduction_status: 'BACKTESTED',
      duplicate_alias_target: null,
      ticket_count: 2,
      window: 'RECENT_300',
      criterion: 'OFFICIAL_ANY_PRIZE',
      metric_status: 'AVAILABLE',
      rankable: true,
      unavailable_reason: null,
      metrics_unavailable_reason: null,
      unranked_reason: 'RANKED_BACKTEST_EVIDENCE_AVAILABLE',
      official_any_prize_count: 21,
      official_any_prize_rate: '0.070000000000000000',
      official_random_baseline_probability: '0.060945547814818275',
      official_random_baseline_delta: '0.009054452185181725',
      coverage: '1.000000000000000000',
      official_prize_counts: { first: 0, second: 0, third: 0, fourth: 0, fifth: 1, sixth: 2, seventh: 6, general: 12 },
      no_prize_count: 279,
      available_observation_count: 300,
      effective_backtest_draw_count: 300,
      successful_observation_count: 21,
      window_available_draws: 300,
      window_requested_draws: 300,
      window_complete: true,
      native_ticket_count_classification: 'FIXED_EXACT_NATIVE_TICKET_COUNT',
      authority_mode: 'FRESH_CURRENT_CATALOG_REPRODUCTION_V1',
      catalog_sha256: 'a'.repeat(64),
      official_rank: null,
    },
    {
      strategy_id: 'quick_ml_predict',
      strategy_version: 'v1.0',
      legacy_method_id: 'quick_ml_predict',
      source_path: 'strategies/quick_ml.py',
      method_family: 'ml',
      reproduction_status: 'BACKTESTED',
      duplicate_alias_target: null,
      ticket_count: 2,
      window: 'RECENT_300',
      criterion: 'OFFICIAL_ANY_PRIZE',
      metric_status: 'UNAVAILABLE',
      rankable: false,
      unavailable_reason: 'NATIVE_TICKET_COUNT_NOT_SUPPORTED',
      metrics_unavailable_reason: null,
      unranked_reason: 'RANKED_BACKTEST_EVIDENCE_AVAILABLE',
      official_any_prize_count: null,
      official_any_prize_rate: null,
      official_random_baseline_probability: null,
      official_random_baseline_delta: null,
      coverage: null,
      official_prize_counts: null,
      no_prize_count: null,
      available_observation_count: null,
      effective_backtest_draw_count: null,
      successful_observation_count: null,
      window_available_draws: 300,
      window_requested_draws: 300,
      window_complete: true,
      native_ticket_count_classification: 'NATIVE_TICKET_COUNT_NOT_SUPPORTED',
      authority_mode: 'FRESH_CURRENT_CATALOG_REPRODUCTION_V1',
      catalog_sha256: 'a'.repeat(64),
      official_rank: null,
    },
  ],
}

const mockCatalog = [
  {
    strategy_id: 'backtest_biglotto_coldpool_15',
    display_name: '冷門池 15 注策略 (Coldpool 15)',
    version: 'v1.0',
    supported_lottery_types: ['BIG_LOTTO'],
    minimum_history: 30,
    lifecycle_status: 'ONLINE',
    executable: true,
    provenance: ['catalog:b649'],
  },
  {
    strategy_id: 'backtest_biglotto_6bet_ewma',
    display_name: '指數移動加權 (6bet EWMA)',
    version: 'v1.0',
    supported_lottery_types: ['BIG_LOTTO'],
    minimum_history: 30,
    lifecycle_status: 'OBSERVATION',
    executable: true,
    provenance: ['catalog:b649'],
  },
  {
    strategy_id: 'quick_ml_predict',
    display_name: '快速機器學習預測 (Quick ML)',
    version: 'v1.0',
    supported_lottery_types: ['BIG_LOTTO'],
    minimum_history: 30,
    lifecycle_status: 'RETIRED',
    executable: false,
    provenance: ['catalog:b649'],
  },
]

beforeEach(() => {
  fetchMock = vi.fn<typeof fetch>().mockImplementation((input) => {
    const url = String(input)
    if (url.includes('/api/v1/b649-multi-ticket-records/summary')) {
      return Promise.resolve(apiResponse(mockB649Summary))
    }
    if (url.includes('/api/v1/strategies')) {
      return Promise.resolve(apiResponse(mockCatalog))
    }
    if (url.includes('/api/v1/b649-exact-native-records')) {
      const urlObj = new URL(url, 'http://localhost')
      const tc = Number(urlObj.searchParams.get('ticket_count') || 2)
      const win = urlObj.searchParams.get('window') || 'RECENT_300'
      if (tc === 5) return Promise.resolve(apiResponse(k5Page(win)))
      if (tc === 10) return Promise.resolve(apiResponse(k10Page(win)))
      const items = mockB649ExactNativeRecords2_300.items.map((it) => ({
        ...it,
        ticket_count: tc,
        window: win,
      }))
      return Promise.resolve(apiResponse({
        ...mockB649ExactNativeRecords2_300,
        ticket_count: tc,
        window: win,
        items,
      }))
    }
    if (url.includes('/api/v1/b649-multi-ticket-records')) {
      if (url.includes('prefix_count=20') && url.includes('window=RECENT_50')) {
        return Promise.resolve(apiResponse(mockB649Records20_50))
      }
      return Promise.resolve(apiResponse(mockB649Records5_300))
    }
    return Promise.resolve(apiResponse({ items: [], total: 0 }))
  })
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('RankingMatrixPage component', () => {
  it('mounts properly and executes bounded 8-step smoke check successfully', async () => {
    const wrapper = mount(RankingMatrixPage)
    await flushPromises()
    await flushPromises()

    // Step 1: Open Ranking Page and verify default selections (Big Lotto, 5 tickets, 300 window)
    expect(wrapper.find('[data-testid="ranking-matrix-page"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="lottery-selector"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="ticket-btn-5"]').classes()).toContain('pill-btn--active')
    expect(wrapper.find('[data-testid="window-btn-300"]').classes()).toContain('pill-btn--active')

    // The default K5 table uses the producer publication.
    expect(wrapper.findAll('.ranking-row')).toHaveLength(5)
    expect(wrapper.text()).toContain('大樂透 Orthogonal 5-Bet 正交 5注')
    expect(wrapper.text()).toContain('15.67%')
    expect(wrapper.text()).toContain('14.55%')

    // Step 2: Switch 2 -> 20 tickets
    // First switch to 2 tickets (canonical exact-native records loaded, banner displayed, formal rank unavailable)
    await wrapper.find('[data-testid="ticket-btn-2"]').trigger('click')
    await flushPromises()
    await flushPromises()
    expect(wrapper.find('[data-testid="canonical-exact-native-banner"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="badge-formal-rank-unavailable"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('正規 2 注指標可用；官方正式排名尚未發布')
    expect(wrapper.findAll('.ranking-row').length).toBe(3)
    expect(wrapper.text()).toContain('6.00%')
    const unavailRow = wrapper.find('[data-testid="ranking-row-quick_ml_predict"]')
    expect(unavailRow.exists()).toBe(true)
    expect(unavailRow.find('.td-rate').text()).toContain('Unavailable')
    expect(unavailRow.find('.td-rate').text()).not.toContain('0%')

    // Switch to 20 tickets
    await wrapper.find('[data-testid="ticket-btn-20"]').trigger('click')
    await flushPromises()
    await flushPromises()

    // Step 3: Switch 300 -> 50 window
    await wrapper.find('[data-testid="window-btn-50"]').trigger('click')
    await flushPromises()
    await flushPromises()

    expect(wrapper.findAll('.ranking-row').length).toBe(2)
    expect(wrapper.text()).toContain('48.00%')

    // Step 4: Filter strategy by search text
    // Exercise the unchanged legacy K20 filters in the 300 window
    await wrapper.find('[data-testid="ticket-btn-20"]').trigger('click')
    await wrapper.find('[data-testid="window-btn-300"]').trigger('click')
    await flushPromises()
    await flushPromises()

    const searchInput = wrapper.get('[data-testid="filter-search-input"]')
    await searchInput.setValue('coldpool')
    await flushPromises()
    expect(wrapper.findAll('.ranking-row').length).toBe(1)
    expect(wrapper.text()).toContain('冷門池 15 注策略')

    // Clear search
    await wrapper.get('[data-testid="clear-filters-btn"]').trigger('click')
    await flushPromises()
    expect(wrapper.findAll('.ranking-row').length).toBe(3)

    // Test Above Baseline filter
    await wrapper.get('[data-testid="filter-baseline-select"]').setValue('ABOVE')
    await flushPromises()
    // Coldpool (+3.00%) and Quick ML (+28.00%) are above baseline
    expect(wrapper.findAll('.ranking-row').length).toBe(2)

    // Reset filters
    await wrapper.get('[data-testid="clear-filters-btn"]').trigger('click')
    await flushPromises()

    // Test Warning Filter
    await wrapper.get('[data-testid="filter-warning-select"]').setValue('HAS_WARNING')
    await flushPromises()
    // Quick ML has HIGH_RANK_LOW_COVERAGE warning
    expect(wrapper.find('[data-testid="warning-chip-HIGH_RANK_LOW_COVERAGE"]').exists()).toBe(true)

    await wrapper.get('[data-testid="clear-filters-btn"]').trigger('click')
    await flushPromises()

    // Step 5: Sort by baseline delta
    expect(wrapper.find('[data-testid="sort-status-bar"]').text()).toContain('官方正式排名')
    await wrapper.get('[data-testid="th-baseline-delta"]').trigger('click')
    await flushPromises()

    // Sort status bar should indicate custom user sort
    expect(wrapper.find('[data-testid="sort-status-bar"]').text()).toContain('自訂排序')
    expect(wrapper.find('[data-testid="reset-official-rank-btn"]').exists()).toBe(true)

    // Step 6: Reset to Official Rank
    await wrapper.get('[data-testid="reset-official-rank-btn"]').trigger('click')
    await flushPromises()
    expect(wrapper.find('[data-testid="sort-status-bar"]').text()).toContain('官方正式排名')

    // Step 7: Switch to Multi-Ticket Matrix View
    await wrapper.get('[data-testid="view-matrix-btn"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-testid="multi-ticket-matrix"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="th-ticket-2"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="th-ticket-20"]').exists()).toBe(true)

    // Verify 2-ticket cell for coldpool 15 shows canonical rate 6.00% and unranked '—', NOT 0%
    const cell2Coldpool = wrapper.find('[data-testid="matrix-cell-backtest_biglotto_coldpool_15-2"]')
    expect(cell2Coldpool.exists()).toBe(true)
    expect(cell2Coldpool.text()).toContain('6.00%')
    expect(cell2Coldpool.text()).not.toContain('0.00%')

    // Verify 2-ticket cell for quick_ml_predict shows explicit unavailable state, NOT 0%
    const cell2QuickMl = wrapper.find('[data-testid="matrix-cell-quick_ml_predict-2"]')
    expect(cell2QuickMl.exists()).toBe(true)
    expect(cell2QuickMl.text()).toContain('不可比較 / 無資料')
    expect(cell2QuickMl.text()).not.toContain('0%')

    // Step 8: Select strategy and see Cross-Window Chart updated
    const matrixRow = wrapper.get('[data-testid="matrix-row-backtest_biglotto_coldpool_15"]')
    await matrixRow.trigger('click')
    await flushPromises()
    await flushPromises()

    const chart = wrapper.find('[data-testid="cross-window-chart"]')
    expect(chart.exists()).toBe(true)
    expect(chart.text()).toContain('冷門池 15 注策略 (Coldpool 15)')
    expect(chart.find('svg').exists()).toBe(true)

    wrapper.unmount()
  })

  it('renders loading skeleton and error state properly', async () => {
    fetchMock.mockRejectedValueOnce(new Error('Network disconnected'))
    const wrapper = mount(RankingMatrixPage)
    await flushPromises()

    expect(wrapper.find('[data-testid="page-error-state"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('無法載入排名資料')

    // Test retry button
    fetchMock.mockResolvedValueOnce(apiResponse(mockB649Summary))
    await wrapper.get('.error-state__actions button').trigger('click')
    await flushPromises()
    await flushPromises()

    expect(wrapper.find('[data-testid="ranking-matrix-page"]').exists()).toBe(true)
    wrapper.unmount()
  })
})


describe('K10 canonical Ranking Matrix consumer', () => {
  it('shows both producer strategies in all windows when legacy requests fail', async () => {
    fetchMock.mockImplementation(async (input) => {
      const url = new URL(String(input), 'http://localhost')
      if (url.pathname.endsWith('b649-exact-native-records') && url.searchParams.get('ticket_count') === '10') return apiResponse(k10Page(url.searchParams.get('window')!))
      return apiResponse({}, 503)
    })
    const wrapper = mount(RankingMatrixPage)
    await flushPromises()
    await wrapper.get('[data-testid="ticket-btn-10"]').trigger('click')
    for (const [label, window] of [['FULL', 'FULL'], ['750', 'RECENT_750'], ['300', 'RECENT_300'], ['50', 'RECENT_50']]) {
      await wrapper.get(`[data-testid="window-btn-${label}"]`).trigger('click')
      await flushPromises(); await flushPromises()
      const rows = wrapper.findAll('.ranking-row')
      const expected = k10Packaged.filter((r) => r.window === window)
      expect(rows).toHaveLength(2)
      expect(rows.map((r) => r.attributes('data-testid'))).toEqual(expected.map((r) => `ranking-row-${r.strategy_id}`))
      expect(rows[0]!.text()).toContain('#1')
      expect(rows[0]!.text()).toContain(expected[0]!.display_name)
      expect(rows[0]!.text()).toContain('26.98%')
      expect(rows[0]!.find('[data-testid="evaluated-requested-draws"]').text()).toContain(`${expected[0]!.evaluated_draws} / ${expected[0]!.requested_draws}`)
    }
    wrapper.unmount()
  })
  it('restores publication order after user sort even when producer ranks are null', async () => {
    const records = k10Packaged.map((r) => ({ ...r, rank: null, official_rank: null, unranked_reason: 'PRODUCER_UNRANKED' }))
    fetchMock.mockImplementation(async (input) => {
      const url = new URL(String(input), 'http://localhost')
      if (url.pathname.endsWith('b649-exact-native-records') && url.searchParams.get('ticket_count') === '10') return apiResponse(k10Page(url.searchParams.get('window')!, records))
      return apiResponse({}, 503)
    })
    const wrapper = mount(RankingMatrixPage)
    await flushPromises()
    await wrapper.get('[data-testid="ticket-btn-10"]').trigger('click')
    await flushPromises(); await flushPromises()
    const order = () => wrapper.findAll('.ranking-row').map((r) => r.attributes('data-testid'))
    const published = records.filter((r) => r.window === 'RECENT_300').map((r) => `ranking-row-${r.strategy_id}`)
    expect(order()).toEqual(published)
    await wrapper.get('[data-testid="th-baseline-delta"]').trigger('click')
    await wrapper.get('[data-testid="th-baseline-delta"]').trigger('click')
    expect(wrapper.get('[data-testid="sort-status-bar"]').text()).toContain('User Sort')
    expect(order()).toEqual([...published].reverse())
    await wrapper.get('[data-testid="reset-official-rank-btn"]').trigger('click')
    expect(order()).toEqual(published)
    expect(wrapper.findAll('.rank-badge--unranked')).toHaveLength(2)
    wrapper.unmount()
  })
})


describe('K5 canonical Ranking Matrix consumer', () => {
  it('shows all windows despite unrelated failures and preserves producer leaders and details', async () => {
    fetchMock.mockImplementation(async (input) => {
      const url = new URL(String(input), 'http://localhost')
      if (url.pathname.endsWith('b649-exact-native-records') && url.searchParams.get('ticket_count') === '5') return apiResponse(k5Page(url.searchParams.get('window')!))
      return apiResponse({}, 503)
    })
    const wrapper = mount(RankingMatrixPage)
    await flushPromises(); await flushPromises()
    expect(String(fetchMock.mock.calls[0]?.[0])).toContain('ticket_count=5')
    for (const [label, window] of [['FULL', 'FULL'], ['750', 'RECENT_750'], ['300', 'RECENT_300'], ['50', 'RECENT_50']]) {
      await wrapper.get(`[data-testid="window-btn-${label}"]`).trigger('click')
      await flushPromises(); await flushPromises()
      const expected = k5Packaged.filter((r) => r.window === window)
      const rows = wrapper.findAll('.ranking-row')
      expect(rows.map((r) => r.attributes('data-testid'))).toEqual(expected.map((r) => `ranking-row-${r.strategy_id}`))
      expect(rows.map((r) => r.find('.rank-badge').text())).toEqual(expected.map((r) => `#${r.rank}`))
      expect(wrapper.find('[data-testid="page-error-state"]').exists()).toBe(false)
      const leaderCard = wrapper.findAllComponents({ name: 'MetricCard' }).find((c) => c.text().includes(expected[0]!.display_name))
      expect(leaderCard).toBeDefined()
      await rows[0]!.trigger('click')
      await flushPromises()
      const details = wrapper.get('[data-testid="k5-producer-details"]')
      expect(details.text()).toContain(expected[0]!.official_any_prize_rate!)
      expect(details.text()).toContain(`${expected[0]!.official_any_prize_numerator} / ${expected[0]!.official_any_prize_denominator}`)
      expect(details.get('[data-testid="k5-producer-ties"]').text()).toContain(JSON.stringify(k5Projection.ties_by_window[window!]))
    }
    expect(fetchMock.mock.calls.every(([url]) => !String(url).includes('prefix_count=5'))).toBe(true)
    wrapper.unmount()
  })
  it('restores source order after user sorting and retains ties after filtering', async () => {
    const wrapper = mount(RankingMatrixPage)
    await flushPromises(); await flushPromises()
    await wrapper.get('[data-testid="window-btn-50"]').trigger('click')
    await flushPromises(); await flushPromises()
    const order = () => wrapper.findAll('.ranking-row').map((r) => r.attributes('data-testid'))
    const records = k5Packaged.filter((r) => r.window === 'RECENT_50')
    const expected = records.map((r) => `ranking-row-${r.strategy_id}`)
    expect(order()).toEqual(expected)
    await wrapper.get('[data-testid="th-baseline-delta"]').trigger('click')
    await wrapper.get('[data-testid="th-baseline-delta"]').trigger('click')
    expect(order()).not.toEqual(expected)
    await wrapper.get('[data-testid="reset-official-rank-btn"]').trigger('click')
    expect(order()).toEqual(expected)
    expect(wrapper.findAll('.rank-badge').map((r) => r.text())).toEqual(['#1', '#2', '#2', '#2', '#5'])
    await wrapper.get('[data-testid="filter-search-input"]').setValue('legacy_composite__')
    expect(wrapper.findAll('.ranking-row')).toHaveLength(1)
    expect(wrapper.find('.ranking-row').text()).toContain('#2')
    await wrapper.find('.ranking-row').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="k5-producer-details"]').text()).toContain('producer position 4')
    expect(wrapper.get('[data-testid="k5-producer-ties"]').text()).toContain(JSON.stringify(k5Projection.ties_by_window.RECENT_50))
    await wrapper.get('[data-testid="clear-filters-btn"]').trigger('click')
    await wrapper.get('[data-testid="view-matrix-btn"]').trigger('click')
    for (const record of records) {
      const cell = wrapper.get(`[data-testid="matrix-cell-${record.strategy_id}-5"]`)
      expect(cell.text()).toContain(`${(Number(record.official_any_prize_rate) * 100).toFixed(2)}%`)
    }
    wrapper.unmount()
  })
  it('shows authoritative zero and unavailable metrics while keeping the producer leader', async () => {
    const records = k5Packaged.map((r): B649K5Record => r.source_order === 1
      ? { ...r, official_any_prize_numerator: 0, official_any_prize_rate: '0.000000000000000000' }
      : r.source_order === 2
        ? { ...r, rank: null, official_rank: null, metric_status: 'UNAVAILABLE', metric_unavailable_reason: 'EXECUTION_FAILURE', official_any_prize_rate: null, official_any_prize_numerator: null, official_any_prize_denominator: null, official_random_baseline: null, baseline_delta: null, coverage: null, best_prize_counts: null }
        : r)
    fetchMock.mockImplementation(async (input) => {
      const url = new URL(String(input), 'http://localhost')
      if (url.searchParams.get('ticket_count') === '5') return apiResponse(k5Page(url.searchParams.get('window')!, records))
      return apiResponse({}, 503)
    })
    const wrapper = mount(RankingMatrixPage)
    await flushPromises(); await flushPromises()
    const rows = wrapper.findAll('.ranking-row')
    expect(rows[0]!.get('.td-rate').text()).toContain('0.00%')
    expect(rows[1]!.get('.td-rate').text()).toContain('Unavailable')
    const leader = records.find((r) => r.window === 'RECENT_300' && r.source_order === 1)!
    const card = wrapper.findAllComponents({ name: 'MetricCard' }).find((c) => c.text().includes(leader.display_name))!
    expect(card.text()).toContain('0.00%')
    await rows[1]!.trigger('click'); await flushPromises()
    expect(wrapper.get('[data-testid="k5-producer-details"]').text()).toContain('EXECUTION_FAILURE')
    wrapper.unmount()
  })
  it('keeps the selected K5 table ready while the legacy summary never resolves', async () => {
    fetchMock.mockImplementation((input) => {
      const url = new URL(String(input), 'http://localhost')
      if (url.searchParams.get('ticket_count') === '5') return Promise.resolve(apiResponse(k5Page(url.searchParams.get('window')!)))
      return new Promise<Response>(() => {})
    })
    const wrapper = mount(RankingMatrixPage)
    await flushPromises(); await flushPromises()
    expect(wrapper.findAll('.ranking-row')).toHaveLength(5)
    expect(wrapper.find('[data-testid="page-loading-skeleton"]').exists()).toBe(false)
    wrapper.unmount()
  })
})
