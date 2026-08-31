// @vitest-environment jsdom

import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import App from '../src/App.vue'
import ReplayOverviewPage from '../src/features/replay-overview/ReplayOverviewPage.vue'
import {
  fetchReplayOverviewData,
  fetchReplayOverviewMatrixData,
  formatCoverage,
  formatDeltaPercentage,
  formatRatePercentage,
  isDimensionAvailable,
} from '../src/api/replayOverview'

const SHA256_FIXTURE = 'a'.repeat(64)
const RESEARCH_DISCLAIMER =
  '歷史成功率、排名與隨機基準差異僅供描述性研究，不構成未來預測、推薦、上線決策或中獎保證。'

function makeMockSummary() {
  return {
    progress: {
      total_strategy_count: 12,
      reproduced_count: 10,
      backtested_count: 8,
      closed_count: 2,
      duplicate_alias_count: 2,
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
    method_families: ['statistical', 'ml', 'heuristic'],
    reproduction_statuses: ['BACKTESTED', 'CLOSED_UNEXECUTABLE', 'DUPLICATE_ALIAS'],
    catalog_sha256: SHA256_FIXTURE,
    records_available: true,
    projection_sha256: SHA256_FIXTURE,
    source_report_count: 100,
    primary_ranking_criterion: 'OFFICIAL_ANY_PRIZE',
    research_disclaimer: RESEARCH_DISCLAIMER,
  }
}

function makeMockRecords(prefixCount = 10, window = 'FULL') {
  const items = []
  for (let i = 1; i <= 12; i++) {
    const isBacktested = i <= 8
    const isClosed = i === 9 || i === 10
    const isAlias = i >= 11
    const status = isBacktested
      ? 'BACKTESTED'
      : isClosed
        ? 'CLOSED_UNEXECUTABLE'
        : 'DUPLICATE_ALIAS'

    items.push({
      strategy_id: `strategy_${i}`,
      strategy_version: 'v1.0',
      legacy_method_id: `tools/legacy_method_${i}.py`,
      source_path: `src/strategies/strategy_${i}.py`,
      method_family: i % 2 === 0 ? 'statistical' : 'ml',
      reproduction_status: status,
      duplicate_alias_target: isAlias ? 'strategy_1' : null,
      prefix_count: prefixCount,
      window,
      criterion: 'M3_PLUS',
      rank: isBacktested ? i : null,
      official_rank: isBacktested ? i : null,
      official_any_prize_count: isBacktested ? 180 - i * 5 : null,
      official_any_prize_rate: isBacktested ? (0.09 - i * 0.003).toFixed(4) : null,
      official_random_baseline_probability: isBacktested ? '0.0780' : null,
      official_random_baseline_delta: isBacktested
        ? (0.09 - i * 0.003 - 0.078).toFixed(4)
        : null,
      unranked_reason: isClosed ? 'INSUFFICIENT_HISTORY' : isAlias ? 'DUPLICATE_OF_STRATEGY_1' : null,
      success_count: isBacktested ? 180 - i * 5 : null,
      effective_backtest_draw_count: isBacktested ? 1949 : null,
      successful_execution_count: isBacktested ? 1949 : null,
      historical_success_rate: isBacktested ? (0.09 - i * 0.003).toFixed(4) : null,
      random_baseline_success_rate: isBacktested ? '0.0780' : null,
      random_baseline_rate_difference: isBacktested
        ? (0.09 - i * 0.003 - 0.078).toFixed(4)
        : null,
      coverage: isBacktested ? (0.99 - i * 0.01).toFixed(3) : null,
      window_available_draws: 1949,
      window_requested_draws: 1949,
      window_complete: true,
      official_prize_counts: isBacktested
        ? {
            first: i === 1 ? 1 : 0,
            second: 0,
            third: i,
            fourth: i * 2,
            fifth: i * 4,
            sixth: i * 8,
            seventh: i * 10,
            general: i * 15,
          }
        : null,
      no_prize_count: isBacktested ? 1769 + i * 5 : null,
      report_sha256: SHA256_FIXTURE,
      report_file_sha256: SHA256_FIXTURE,
      catalog_sha256: SHA256_FIXTURE,
    })
  }
  return items
}

function mockFetchHandler(input: RequestInfo | URL) {
  const url = String(input)

  if (url.includes('/api/v1/b649-multi-ticket-records/summary')) {
    return Promise.resolve({
      ok: true,
      status: 200,
      json: () => Promise.resolve(makeMockSummary()),
    } as Response)
  }

  if (url.includes('/api/v1/b649-multi-ticket-records')) {
    const urlObj = new URL(url, 'http://localhost')
    const prefixCount = Number(urlObj.searchParams.get('prefix_count') ?? 10)
    const window = urlObj.searchParams.get('window') ?? 'FULL'
    const limit = Number(urlObj.searchParams.get('limit') ?? 50)
    const offset = Number(urlObj.searchParams.get('offset') ?? 0)

    const allRecords = makeMockRecords(prefixCount, window)
    const paged = allRecords.slice(offset, offset + limit)

    return Promise.resolve({
      ok: true,
      status: 200,
      json: () =>
        Promise.resolve({
          items: paged,
          total: allRecords.length,
          limit,
          offset,
          prefix_count: prefixCount,
          window,
          criterion: 'M3_PLUS',
          research_disclaimer: RESEARCH_DISCLAIMER,
        }),
    } as Response)
  }

  return Promise.resolve({
    ok: true,
    status: 200,
    json: () => Promise.resolve({ items: [], total: 0 }),
  } as Response)
}

describe('Replay Overview UI & Data Contract', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn(mockFetchHandler))
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  // 1. B649 selector
  it('loads B649 by default and renders all strategy rows', async () => {
    const wrapper = mount(ReplayOverviewPage)
    await flushPromises()

    expect(wrapper.find('[data-testid="game-select-b649"]').classes()).toContain('pill-btn--active')
    expect(wrapper.text()).toContain('大樂透 B649')
    expect(wrapper.findAll('[data-testid^="table-row-strategy_"]').length).toBe(12)
  })

  // 2. P638 selector
  it('switches to P638 selector and renders EVIDENCE UNAVAILABLE state without 0%', async () => {
    const wrapper = mount(ReplayOverviewPage)
    await flushPromises()

    await wrapper.find('[data-testid="game-select-p638"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-testid="evidence-unavailable-state"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Evidence Unavailable for P638 (10 Tickets)')
    expect(wrapper.text()).toContain('EVIDENCE UNAVAILABLE')
    // Must NOT display 0.00% as fake result
    expect(wrapper.text()).not.toContain('0.00%')
  })

  // 3. T539 selector
  it('switches to T539 selector and renders EVIDENCE UNAVAILABLE state without 0%', async () => {
    const wrapper = mount(ReplayOverviewPage)
    await flushPromises()

    await wrapper.find('[data-testid="game-select-t539"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-testid="evidence-unavailable-state"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Evidence Unavailable for T539 (10 Tickets)')
    expect(wrapper.text()).toContain('EVIDENCE UNAVAILABLE')
    expect(wrapper.text()).not.toContain('0.00%')
  })

  // 4. 10 selector
  it('supports 10 ticket allocation selector', async () => {
    const wrapper = mount(ReplayOverviewPage)
    await flushPromises()

    const btn10 = wrapper.find('[data-testid="ticket-select-10"]')
    expect(btn10.classes()).toContain('pill-btn--active')
    expect(wrapper.find('[data-testid="summary-kpis"]').text()).toContain('10 Tickets')
  })

  // 5. 15 selector
  it('supports 15 ticket allocation selector', async () => {
    const wrapper = mount(ReplayOverviewPage)
    await flushPromises()

    await wrapper.find('[data-testid="ticket-select-15"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-testid="ticket-select-15"]').classes()).toContain('pill-btn--active')
    expect(wrapper.find('[data-testid="summary-kpis"]').text()).toContain('15 Tickets')
    expect(wrapper.findAll('[data-testid^="table-row-strategy_"]').length).toBe(12)
  })

  // 6. 20 selector
  it('supports 20 ticket allocation selector', async () => {
    const wrapper = mount(ReplayOverviewPage)
    await flushPromises()

    await wrapper.find('[data-testid="ticket-select-20"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-testid="ticket-select-20"]').classes()).toContain('pill-btn--active')
    expect(wrapper.find('[data-testid="summary-kpis"]').text()).toContain('20 Tickets')
    expect(wrapper.findAll('[data-testid^="table-row-strategy_"]').length).toBe(12)
  })

  // 7. FULL / 750 / 300 / 50 windows
  it('supports FULL, 750, 300, and 50 evaluation windows', async () => {
    const wrapper = mount(ReplayOverviewPage)
    await flushPromises()

    // 750
    await wrapper.find('[data-testid="window-select-750"]').trigger('click')
    await flushPromises()
    expect(wrapper.find('[data-testid="window-select-750"]').classes()).toContain('pill-btn--active')
    expect(wrapper.find('[data-testid="summary-kpis"]').text()).toContain('750')

    // 300
    await wrapper.find('[data-testid="window-select-300"]').trigger('click')
    await flushPromises()
    expect(wrapper.find('[data-testid="window-select-300"]').classes()).toContain('pill-btn--active')
    expect(wrapper.find('[data-testid="summary-kpis"]').text()).toContain('300')

    // 50
    await wrapper.find('[data-testid="window-select-50"]').trigger('click')
    await flushPromises()
    expect(wrapper.find('[data-testid="window-select-50"]').classes()).toContain('pill-btn--active')
    expect(wrapper.find('[data-testid="summary-kpis"]').text()).toContain('50')

    // FULL
    await wrapper.find('[data-testid="window-select-full"]').trigger('click')
    await flushPromises()
    expect(wrapper.find('[data-testid="window-select-full"]').classes()).toContain('pill-btn--active')
    expect(wrapper.find('[data-testid="summary-kpis"]').text()).toContain('FULL')
  })

  // 8. All-strategy rows not truncated by Top-N
  it('renders all 12 strategy rows without Top-5 truncation', async () => {
    const wrapper = mount(ReplayOverviewPage)
    await flushPromises()

    const rows = wrapper.findAll('[data-testid^="table-row-strategy_"]')
    expect(rows.length).toBe(12)
    // Check that lower ranked strategies like strategy_8, strategy_9, strategy_12 are present
    expect(wrapper.find('[data-testid="table-row-strategy_8"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="table-row-strategy_12"]').exists()).toBe(true)
  })

  // 9. Pagination retrieves complete universe of rows
  it('retrieves all pages from upstream canonical endpoint', async () => {
    const data = await fetchReplayOverviewData('B649', 10, 'FULL')
    expect(data.items.length).toBe(12)
    expect(data.summary.totalStrategies).toBe(12)
    expect(data.summary.rankedStrategies).toBe(8)
    expect(data.summary.fullUniverseStatus).toBe('COMPLETE')
  })

  // 10. Official Rank default order
  it('orders table rows by Official Rank by default with top 3 badges', async () => {
    const wrapper = mount(ReplayOverviewPage)
    await flushPromises()

    const rows = wrapper.findAll('[data-testid^="table-row-strategy_"]')
    expect(rows[0].text()).toContain('#1')
    expect(rows[0].text()).toContain('strategy_1')
    expect(rows[1].text()).toContain('#2')
    expect(rows[2].text()).toContain('#3')
  })

  // 11. User Sort
  it('allows presentation sorting by strategyId, hitRate, etc. while preserving Official Rank', async () => {
    const wrapper = mount(ReplayOverviewPage)
    await flushPromises()

    // Click strategyId column to sort alphabetically
    const thStrategy = wrapper.findAll('th').find((th) => th.text().includes('Strategy ID'))
    await thStrategy?.trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-testid="user-sort-active-badge"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="reset-sort-button"]').exists()).toBe(true)

    // Even sorted differently, strategy_1 still has official rank #1
    const row1 = wrapper.find('[data-testid="table-row-strategy_1"]')
    expect(row1.text()).toContain('#1')
  })

  // 12. Reset to Official Rank
  it('resets presentation sort back to Official Rank ascending', async () => {
    const wrapper = mount(ReplayOverviewPage)
    await flushPromises()

    const thStrategy = wrapper.findAll('th').find((th) => th.text().includes('Strategy ID'))
    await thStrategy?.trigger('click')
    await flushPromises()
    expect(wrapper.find('[data-testid="user-sort-active-badge"]').exists()).toBe(true)

    await wrapper.find('[data-testid="reset-sort-button"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-testid="user-sort-active-badge"]').exists()).toBe(false)
    const rows = wrapper.findAll('[data-testid^="table-row-strategy_"]')
    expect(rows[0].text()).toContain('#1')
  })

  // 13. Filter does not modify canonical rank
  it('filters rows without altering canonical rank values', async () => {
    const wrapper = mount(ReplayOverviewPage)
    await flushPromises()

    // Filter by search query "strategy_3"
    const searchInput = wrapper.find('[data-testid="search-input"]')
    await searchInput.setValue('strategy_3')
    await flushPromises()

    const rows = wrapper.findAll('[data-testid^="table-row-strategy_"]')
    expect(rows.length).toBe(1)
    // The single filtered row must still display its official rank #3 (not #1)
    expect(rows[0].text()).toContain('#3')
    expect(rows[0].text()).toContain('strategy_3')
  })

  // 14. Missing data != 0%
  it('formats missing data as Unavailable / - and never as 0%', async () => {
    expect(formatRatePercentage(null)).toBe('Unavailable')
    expect(formatDeltaPercentage(null)).toBe('Unavailable')
    expect(formatCoverage(null)).toBe('Unavailable')

    const wrapper = mount(ReplayOverviewPage)
    await flushPromises()

    // Closed / Unranked strategy rows (strategy_9) should display 'Unavailable' or '-'
    const unrankedRow = wrapper.find('[data-testid="table-row-strategy_9"]')
    expect(unrankedRow.text()).toContain('Unavailable')
    expect(unrankedRow.text()).toContain('--')
  })

  // 15. Entire-dimension unavailable presentation
  it('renders upstream gap reason when entire game dimension is unavailable', async () => {
    const wrapper = mount(ReplayOverviewPage)
    await flushPromises()

    await wrapper.find('[data-testid="game-select-p638"]').trigger('click')
    await flushPromises()

    const unavailableState = wrapper.find('[data-testid="evidence-unavailable-state"]')
    expect(unavailableState.exists()).toBe(true)
    expect(unavailableState.text()).toContain('P638')
    expect(unavailableState.text()).toContain('restricted to single-ticket')
  })

  // 16. 10/15/20 Matrix view
  it('switches to 10/15/20 Matrix view and renders cells', async () => {
    const wrapper = mount(ReplayOverviewPage)
    await flushPromises()

    await wrapper.find('[data-testid="view-mode-matrix"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-testid="replay-overview-matrix"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="matrix-row-strategy_1"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="matrix-row-strategy_1"]').text()).toContain('#1')
  })

  // 17. Cross-game query isolation
  it('isolates game query state completely', async () => {
    const wrapper = mount(ReplayOverviewPage)
    await flushPromises()

    // Select B649 15 tickets 300 window
    await wrapper.find('[data-testid="ticket-select-15"]').trigger('click')
    await wrapper.find('[data-testid="window-select-300"]').trigger('click')
    await flushPromises()
    expect(wrapper.find('[data-testid="summary-kpis"]').text()).toContain('B649 · 15 Tickets · 300')

    // Switch to P638
    await wrapper.find('[data-testid="game-select-p638"]').trigger('click')
    await flushPromises()
    expect(wrapper.find('[data-testid="evidence-unavailable-state"]').exists()).toBe(true)

    // Switch back to B649
    await wrapper.find('[data-testid="game-select-b649"]').trigger('click')
    await flushPromises()
    expect(wrapper.find('[data-testid="summary-kpis"]').text()).toContain('B649 · 15 Tickets · 300')
  })

  // 18. Existing replay routes unaffected & dimension availability helper
  it('correctly reports dimension availability helper', () => {
    expect(isDimensionAvailable('B649', 10)).toBe(true)
    expect(isDimensionAvailable('B649', 15)).toBe(true)
    expect(isDimensionAvailable('B649', 20)).toBe(true)

    expect(isDimensionAvailable('P638', 10)).toBe(false)
    expect(isDimensionAvailable('P638', 15)).toBe(false)
    expect(isDimensionAvailable('P638', 20)).toBe(false)

    expect(isDimensionAvailable('T539', 10)).toBe(false)
    expect(isDimensionAvailable('T539', 15)).toBe(false)
    expect(isDimensionAvailable('T539', 20)).toBe(false)
  })

  // Bounded Smoke Scenarios A to G
  describe('Bounded Smoke Verification Scenarios', () => {
    it('Smoke A: B649 -> 10 -> FULL', async () => {
      const res = await fetchReplayOverviewData('B649', 10, 'FULL')
      expect(res.summary.isDimensionAvailable).toBe(true)
      expect(res.items.length).toBe(12)
      expect(res.items[0].officialRank).toBe(1)
    })

    it('Smoke B: B649 -> 15 -> RECENT_300', async () => {
      const res = await fetchReplayOverviewData('B649', 15, 'RECENT_300')
      expect(res.summary.isDimensionAvailable).toBe(true)
      expect(res.items.length).toBe(12)
    })

    it('Smoke C: B649 -> 20 -> RECENT_50', async () => {
      const res = await fetchReplayOverviewData('B649', 20, 'RECENT_50')
      expect(res.summary.isDimensionAvailable).toBe(true)
      expect(res.items.length).toBe(12)
    })

    it('Smoke D: P638 -> 10 -> FULL (unavailable != 0%)', async () => {
      const res = await fetchReplayOverviewData('P638', 10, 'FULL')
      expect(res.summary.isDimensionAvailable).toBe(false)
      expect(res.summary.unavailableReason).toContain('P638')
      expect(res.items.length).toBe(0)
    })

    it('Smoke E: P638 -> 20 -> RECENT_300 (unavailable != 0%)', async () => {
      const res = await fetchReplayOverviewData('P638', 20, 'RECENT_300')
      expect(res.summary.isDimensionAvailable).toBe(false)
      expect(res.summary.unavailableReason).toContain('P638')
    })

    it('Smoke F: T539 -> 15 -> RECENT_750 (unavailable != 0%)', async () => {
      const res = await fetchReplayOverviewData('T539', 15, 'RECENT_750')
      expect(res.summary.isDimensionAvailable).toBe(false)
      expect(res.summary.unavailableReason).toContain('T539')
    })

    it('Smoke G: T539 -> 20 -> RECENT_50 (unavailable != 0%)', async () => {
      const res = await fetchReplayOverviewData('T539', 20, 'RECENT_50')
      expect(res.summary.isDimensionAvailable).toBe(false)
      expect(res.summary.unavailableReason).toContain('T539')
    })
  })
})
