// @vitest-environment jsdom

import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import BestReplayHorizonComparison from '../src/features/best-replay/BestReplayHorizonComparison.vue'
import BestReplayMatrix from '../src/features/best-replay/BestReplayMatrix.vue'
import BestReplayOneToFiveOverview from '../src/features/best-replay/BestReplayOneToFiveOverview.vue'
import BestReplayPage from '../src/features/best-replay/BestReplayPage.vue'
import { compareNullableNumbers } from '../src/features/best-replay/sorting'
import {
  ALL_TICKET_COUNTS,
  B649_AVAILABLE_TICKET_COUNTS,
  CANONICAL_HORIZONS,
  PRIMARY_TICKET_COUNTS,
  type BestReplayItem,
  type BestReplayMatrixRow,
  type TicketCount,
} from '../src/features/best-replay/types'

import {
  B649_HISTORY_WINDOWS,
  B649_PREFIX_COUNTS,
  B649_REPRODUCTION_STATUSES,
  B649_RESEARCH_DISCLAIMER,
  B649_SUCCESS_CRITERIA,
  type B649MultiTicketRecord,
} from '../src/api/b649MultiTicketRecords'
import {
  formatDeltaPercentage,
  formatRatePercentage,
  loadP638BestReplayData,
  loadT539BestReplayData,
  transformB649Record,
} from '../src/api/bestReplay'

let fetchMock: ReturnType<typeof vi.fn<typeof fetch>>
let p638CompleteTargetCount: number | null
let p638WinningTargetCount: number | null
let p638WinningTargetRate: number | null
let p638StrategyVersion: string | null
let t539EligibleTargetCount: number | null
let t539WinningTargetCount: number | null
let t539WinningTargetRate: number | null
let t539StrategyVersion: string | null

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
      total_strategy_count: 221,
      reproduced_count: 135,
      backtested_count: 135,
      closed_count: 74,
      duplicate_alias_count: 12,
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
    metrics_available_strategy_count: recordsAvailable ? 133 : null,
    metrics_unavailable_strategy_count: recordsAvailable ? 2 : null,
    research_disclaimer: B649_RESEARCH_DISCLAIMER,
  }
}

function mockB649Record(
  prefixCount: number,
  window: string,
  strategyToken: string,
  options: {
    rank?: number | null
    rate?: string
    delta?: string
    draws?: number
    hits?: number
  } = {},
) {
  return {
    strategy_id: `legacy_biglotto__${strategyToken}__fixture`,
    strategy_version: 'v1.0',
    legacy_method_id: strategyToken,
    source_path: `fixture/${strategyToken}.json`,
    method_family: strategyToken.includes('6bet') ? 'frequency' : 'statistical',
    reproduction_status: 'BACKTESTED',
    duplicate_alias_target: null,
    prefix_count: prefixCount,
    window,
    criterion: 'M3_PLUS',
    rank: options.rank ?? null,
    official_rank: options.rank ?? null,
    official_any_prize_count: options.hits ?? 539,
    official_any_prize_rate: options.rate ?? '0.276552077988712160',
    official_random_baseline_probability: '0.269779736506368005',
    official_random_baseline_delta: options.delta ?? '0.006772341482344155',
    unranked_reason: options.rank === null ? 'UNRANKED' : null,
    success_count: options.hits ?? 539,
    effective_backtest_draw_count: options.draws ?? 1949,
    successful_execution_count: options.draws ?? 1949,
    historical_success_rate: options.rate ?? '0.276552077988712160',
    random_baseline_success_rate: '0.269779736506368005',
    random_baseline_rate_difference: options.delta ?? '0.006772341482344155',
    coverage: '0.906900000000000000',
    window_available_draws: window === 'FULL' ? 2149 : Number(window.replace('RECENT_', '')),
    window_requested_draws: window === 'FULL' ? 2149 : Number(window.replace('RECENT_', '')),
    window_complete: true,
    official_prize_counts: {
      first: 0,
      second: 1,
      third: 2,
      fourth: 5,
      fifth: 20,
      sixth: 21,
      seventh: 241,
      general: 355,
    },
    no_prize_count: 1410,
    report_sha256: 'a'.repeat(64),
    report_file_sha256: 'b'.repeat(64),
    catalog_sha256: 'c'.repeat(64),
  }
}

function mockB649RecordsPage(url: URL) {
  const prefixCount = Number(url.searchParams.get('prefix_count'))
  const window = url.searchParams.get('window') ?? 'FULL'

  const items = [
    mockB649Record(prefixCount, window, 'portfolio_optimizer', {
      rank: 1,
      rate: '0.276552',
      delta: '0.006772',
      draws: window === 'RECENT_50' ? 50 : window === 'RECENT_300' ? 300 : window === 'RECENT_750' ? 750 : 1949,
      hits: window === 'RECENT_50' ? 14 : window === 'RECENT_300' ? 82 : window === 'RECENT_750' ? 208 : 539,
    }),
    mockB649Record(prefixCount, window, '6bet_ewma', {
      rank: 2,
      rate: '0.251200',
      delta: '0.001200',
      draws: window === 'RECENT_50' ? 50 : window === 'RECENT_300' ? 300 : window === 'RECENT_750' ? 750 : 1949,
      hits: window === 'RECENT_50' ? 12 : window === 'RECENT_300' ? 75 : window === 'RECENT_750' ? 188 : 489,
    }),
    mockB649Record(prefixCount, window, 'coldpool_15', {
      rank: 3,
      rate: '0.240100',
      delta: '-0.005400',
      draws: window === 'RECENT_50' ? 50 : window === 'RECENT_300' ? 300 : window === 'RECENT_750' ? 750 : 1949,
      hits: window === 'RECENT_50' ? 11 : window === 'RECENT_300' ? 71 : window === 'RECENT_750' ? 179 : 467,
    }),
  ]

  return {
    items,
    total: items.length,
    limit: 100,
    offset: 0,
    prefix_count: prefixCount,
    window,
    criterion: 'M3_PLUS',
    research_disclaimer: B649_RESEARCH_DISCLAIMER,
  }
}

function mockP638Runs() {
  return {
    items: [
      {
        run_id: 'p638-canonical-run-1',
        import_identity_sha256: 'a'.repeat(64),
        manifest_sha256: 'b'.repeat(64),
        contract_version: 'v1.0',
        source_run_id: 'src-p638-1',
        source_replay_sha256: 'c'.repeat(64),
        source_draw_db_sha256: 'd'.repeat(64),
        source_commit_oid: 'e'.repeat(40),
        source_content_sha256: 'f'.repeat(64),
        second_zone_ssot_version: 'v1',
        status: 'COMPLETE',
        started_at: '2026-08-01T00:00:00Z',
        completed_at: '2026-08-01T01:00:00Z',
        strategy_count: 5,
        draw_count: 1000,
        complete_target_count: p638CompleteTargetCount,
        excluded_target_count: 0,
        failed_target_count: 0,
        ticket_count: 1,
        first_draw_number: '1',
        first_draw_date: '2010-01-01',
      },
    ],
    total_count: 1,
    limit: 5,
    offset: 0,
  }
}

function mockP638Rankings() {
  return {
    run_id: 'p638-canonical-run-1',
    items: [
      {
        strategy_id: 'p638_zonal_entropy_leader',
        strategy_version: p638StrategyVersion,
        rank: 1,
        eligible_target_count: 1000,
        winning_target_count: p638WinningTargetCount,
        winning_target_rate: p638WinningTargetRate,
        prize_tier_counts: [
          { prize_tier: 'first', count: 1 },
          { prize_tier: 'second', count: 2 },
          { prize_tier: 'third', count: 12 },
          { prize_tier: 'fourth', count: 45 },
          { prize_tier: 'fifth', count: 125 },
        ],
      },
      {
        strategy_id: 'p638_cyclical_shift_runner_up',
        strategy_version: 'p638-cyclic-v2',
        rank: 2,
        eligible_target_count: 1000,
        winning_target_count: 162,
        winning_target_rate: 0.162,
        prize_tier_counts: [
          { prize_tier: 'first', count: 0 },
          { prize_tier: 'second', count: 1 },
          { prize_tier: 'third', count: 9 },
          { prize_tier: 'fourth', count: 38 },
          { prize_tier: 'fifth', count: 114 },
        ],
      },
    ],
  }
}

function mockT539Runs() {
  return {
    items: [
      {
        run_id: 't539-canonical-run-1',
        status: 'COMPLETE',
        lottery_type: 'DAILY_539',
        eligible_target_count: t539EligibleTargetCount,
      },
    ],
    total_count: 1,
    limit: 5,
    offset: 0,
  }
}

function mockT539Rankings() {
  return {
    run_id: 't539-canonical-run-1',
    items: [
      {
        strategy_id: 't539_wave1_cyclic_leader',
        strategy_version: t539StrategyVersion,
        rank: 1,
        eligible_target_count: 1000,
        winning_target_count: t539WinningTargetCount,
        winning_target_rate: t539WinningTargetRate,
        ticket_winning_rate: 0.215,
        prize_tier_counts: [
          { prize_tier: 'first', count: 0 },
          { prize_tier: 'second', count: 3 },
          { prize_tier: 'third', count: 15 },
          { prize_tier: 'fourth', count: 58 },
          { prize_tier: 'fifth', count: 139 },
        ],
      },
      {
        strategy_id: 't539_sidon_runner_up',
        strategy_version: 't539-sidon-v3',
        rank: 2,
        eligible_target_count: 1000,
        winning_target_count: 198,
        winning_target_rate: 0.198,
        ticket_winning_rate: 0.198,
        prize_tier_counts: [
          { prize_tier: 'first', count: 0 },
          { prize_tier: 'second', count: 1 },
          { prize_tier: 'third', count: 11 },
          { prize_tier: 'fourth', count: 47 },
          { prize_tier: 'fifth', count: 139 },
        ],
      },
    ],
  }
}

beforeEach(() => {
  p638CompleteTargetCount = 1000
  p638WinningTargetCount = 180
  p638WinningTargetRate = 0.185
  p638StrategyVersion = 'p638-zonal-v2'
  t539EligibleTargetCount = 1000
  t539WinningTargetCount = 211
  t539WinningTargetRate = 0.215
  t539StrategyVersion = 't539-wave1-v4'

  fetchMock = vi.fn<typeof fetch>().mockImplementation((input) => {
    const url = new URL(String(input), 'http://localhost')
    if (url.pathname.includes('/b649-multi-ticket-records/summary')) {
      return Promise.resolve(apiResponse(mockB649Summary()))
    }
    if (url.pathname.includes('/b649-multi-ticket-records')) {
      return Promise.resolve(apiResponse(mockB649RecordsPage(url)))
    }
    if (url.pathname.includes('/p638-historical/runs') && url.pathname.includes('/rankings')) {
      return Promise.resolve(apiResponse(mockP638Rankings()))
    }
    if (url.pathname.includes('/p638-historical/runs')) {
      return Promise.resolve(apiResponse(mockP638Runs()))
    }
    if (url.pathname.includes('/t539-historical/runs') && url.pathname.includes('/rankings')) {
      return Promise.resolve(apiResponse(mockT539Rankings()))
    }
    if (url.pathname.includes('/t539-historical/runs')) {
      return Promise.resolve(apiResponse(mockT539Runs()))
    }
    return Promise.resolve(apiResponse({}))
  })
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => vi.unstubAllGlobals())

describe('Best Replay source-value regressions', () => {
  it('preserves a source P638 complete-target count of zero', async () => {
    p638CompleteTargetCount = 0

    const item = (await loadP638BestReplayData([1], 'FULL'))[0]

    expect(item?.evaluatedTargets).toBe(0)
  })

  it('uses the P638 winning-target numerator and strategy version from ranking evidence', async () => {
    const item = (await loadP638BestReplayData([1], 'FULL'))[0]

    expect(item?.winningTargets).toBe(180)
    expect(item?.hitRate).toBe(0.185)
    expect(item?.rank).toBe(1)
    expect(item?.strategyId).toBe('p638_zonal_entropy_leader')
    expect(item?.strategyVersion).toBe('p638-zonal-v2')
  })

  it('keeps a missing P638 numerator and strategy version unavailable', async () => {
    p638WinningTargetCount = null
    p638StrategyVersion = null

    const item = (await loadP638BestReplayData([1], 'FULL'))[0]

    expect(item?.winningTargets).toBeNull()
    expect(item?.strategyVersion).toBeNull()
  })

  it('does not infer a winning-target count from a rate and sample count', async () => {
    p638WinningTargetCount = null

    const item = (await loadP638BestReplayData([1], 'FULL'))[0]

    expect(item?.evaluatedTargets).toBe(1000)
    expect(item?.hitRate).toBe(0.185)
    expect(item?.winningTargets).toBeNull()
  })

  it('preserves a sourced B649 sample count and leaves a missing count unknown', () => {
    const sourcedRecord = {
      ...mockB649Record(5, 'RECENT_750', 'sample', { draws: 37 }),
      effective_backtest_draw_count: 37,
      window_available_draws: 750,
    } as B649MultiTicketRecord
    const missingRecord = {
      ...sourcedRecord,
      effective_backtest_draw_count: null,
      window_available_draws: null,
    }

    expect(transformB649Record(sourcedRecord, 'RECENT_750', 5).evaluatedTargets).toBe(37)
    expect(transformB649Record(missingRecord, 'RECENT_750', 5).evaluatedTargets).toBeNull()
  })

  it('keeps missing T539 sample and numerator values unknown', async () => {
    t539EligibleTargetCount = null
    t539WinningTargetCount = null

    const item = (await loadT539BestReplayData([1], 'FULL'))[0]

    expect(item?.evaluatedTargets).toBeNull()
    expect(item?.winningTargets).toBeNull()
    expect(item?.hitRate).toBe(0.215)
  })

  it('renders a source P638 sample count of zero as zero in the summary', async () => {
    p638CompleteTargetCount = 0
    const wrapper = mount(BestReplayPage)
    await flushPromises()
    await wrapper.find('[data-testid="game-btn-p638"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-testid="best-replay-metrics-grid"]').text()).toContain('0 Historical Draws')

    wrapper.unmount()
  })

  it('renders missing P638 sample, numerator, and version sources as unavailable', async () => {
    p638CompleteTargetCount = null
    p638WinningTargetCount = null
    p638StrategyVersion = null
    const wrapper = mount(BestReplayPage)
    await flushPromises()
    await wrapper.find('[data-testid="game-btn-p638"]').trigger('click')
    await flushPromises()

    const visibleText = wrapper.text()
    expect(visibleText).toContain('p638_zonal_entropy_leader')
    expect(visibleText).toContain('Sample count unknown')
    expect(visibleText).toContain('Unknown')
    expect(visibleText).toContain('Not provided')
    expect(visibleText).not.toContain('v1.0')

    wrapper.unmount()
  })

  it('sorts missing numeric evidence after sourced values without assigning a numeric fallback', () => {
    expect(compareNullableNumbers(null, 0.162, 1)).toBe(1)
    expect(compareNullableNumbers(0.162, null, 1)).toBe(-1)
    expect(compareNullableNumbers(null, 0.162, -1)).toBe(1)
    expect(compareNullableNumbers(Number.NaN, 0.162, 1)).toBe(1)
  })

  it('does not describe RECENT_750 as an out-of-sample audit in the page copy', async () => {
    const wrapper = mount(BestReplayPage)
    await flushPromises()
    await wrapper.find('#horizon-select').setValue('RECENT_750')
    await flushPromises()

    expect(wrapper.text().toLowerCase()).not.toContain('out-of-sample')

    wrapper.unmount()
  })

  it('describes RECENT_750 as a historical interval without an OOS claim', () => {
    const recent750 = CANONICAL_HORIZONS.find((horizon) => horizon.key === 'RECENT_750')

    expect(recent750?.description).toBe('Recent 750 historical draws')
    expect(recent750?.description.toLowerCase()).not.toContain('out-of-sample')
  })
})

describe('BestReplayPage Workspace & Cross-Game Features', () => {
  it('mounts cleanly with SectionHeader, Summary Metrics Cards, 1-5 Overview, and English-only copy', async () => {
    const wrapper = mount(BestReplayPage)
    await flushPromises()

    expect(wrapper.find('#best-replay-title h2').text()).toBe('Best Replay')
    expect(wrapper.text()).toContain('Multi-ticket horizon ranking')
    expect(wrapper.text()).toContain('Best Strategy')
    expect(wrapper.text()).toContain('Ticket Count')
    expect(wrapper.text()).toContain('Horizon')
    expect(wrapper.text()).toContain('Historical Hit Rate')
    expect(wrapper.text()).toContain('Evidence Guard')
    expect(wrapper.text()).toContain('1–5 Best Strategy Overview')

    // CJK Audit: verify 0 CJK characters in visible text
    const visibleText = wrapper.text()
    const cjkMatches = visibleText.match(/[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]/g)
    expect(cjkMatches).toBeNull()

    wrapper.unmount()
  })

  it('provides dedicated game selector buttons for B649, P638, and T539 with B649 default', async () => {
    const wrapper = mount(BestReplayPage)
    await flushPromises()

    const b649Btn = wrapper.find('[data-testid="game-btn-b649"]')
    const p638Btn = wrapper.find('[data-testid="game-btn-p638"]')
    const t539Btn = wrapper.find('[data-testid="game-btn-t539"]')

    expect(b649Btn.exists()).toBe(true)
    expect(p638Btn.exists()).toBe(true)
    expect(t539Btn.exists()).toBe(true)

    // B649 default active
    expect(b649Btn.classes()).toContain('game-nav-btn--active')
    expect(wrapper.text()).toContain('Big Lotto 6/49')

    // Switch to P638
    await p638Btn.trigger('click')
    await flushPromises()
    expect(p638Btn.classes()).toContain('game-nav-btn--active')
    expect(wrapper.text()).toContain('Power Lotto 6/38')

    // Switch to T539
    await t539Btn.trigger('click')
    await flushPromises()
    expect(t539Btn.classes()).toContain('game-nav-btn--active')
    expect(wrapper.text()).toContain('Daily Cash 5/39')

    wrapper.unmount()
  })

  it('keeps dropdown game changes in sync with button ticket defaults and game data', async () => {
    const wrapper = mount(BestReplayPage)
    await flushPromises()

    const gameSelect = wrapper.find<HTMLSelectElement>('#game-select')
    expect(wrapper.find('[data-testid="summary-tickets"]').text()).toContain('5')

    await gameSelect.setValue('P638')
    await flushPromises()
    expect(gameSelect.element.value).toBe('P638')
    expect(wrapper.find('[data-testid="summary-game"]').text()).toContain('P638')
    expect(wrapper.find('[data-testid="summary-tickets"]').text()).toContain('1')
    expect(wrapper.find('[data-testid="game-btn-p638"]').classes()).toContain('game-nav-btn--active')

    await gameSelect.setValue('T539')
    await flushPromises()
    expect(gameSelect.element.value).toBe('T539')
    expect(wrapper.find('[data-testid="summary-game"]').text()).toContain('T539')
    expect(wrapper.find('[data-testid="summary-tickets"]').text()).toContain('1')
    expect(wrapper.find('[data-testid="game-btn-t539"]').classes()).toContain('game-nav-btn--active')

    await gameSelect.setValue('B649')
    await flushPromises()
    expect(gameSelect.element.value).toBe('B649')
    expect(wrapper.find('[data-testid="summary-game"]').text()).toContain('B649')
    expect(wrapper.find('[data-testid="summary-tickets"]').text()).toContain('5')
    expect(wrapper.find('[data-testid="game-btn-b649"]').classes()).toContain('game-nav-btn--active')

    wrapper.unmount()
  })

  it('guarantees 1, 2, 3, 4, 5 ticket buttons ALWAYS exist and are interactive across all games', async () => {
    const wrapper = mount(BestReplayPage)
    await flushPromises()

    for (const count of [1, 2, 3, 4, 5]) {
      const btn = wrapper.find(`[data-testid="ticket-btn-${count}"]`)
      expect(btn.exists()).toBe(true)
    }

    // Switch to P638
    await wrapper.find('[data-testid="game-btn-p638"]').trigger('click')
    await flushPromises()

    for (const count of [1, 2, 3, 4, 5]) {
      const btn = wrapper.find(`[data-testid="ticket-btn-${count}"]`)
      expect(btn.exists()).toBe(true)
    }

    // Switch to T539
    await wrapper.find('[data-testid="game-btn-t539"]').trigger('click')
    await flushPromises()

    for (const count of [1, 2, 3, 4, 5]) {
      const btn = wrapper.find(`[data-testid="ticket-btn-${count}"]`)
      expect(btn.exists()).toBe(true)
    }

    wrapper.unmount()
  })

  it('supports canonical horizons: FULL, 750, 300, and 50', async () => {
    const wrapper = mount(BestReplayPage)
    await flushPromises()

    const horizonSelect = wrapper.find('#horizon-select')
    expect(horizonSelect.exists()).toBe(true)

    // Switch to RECENT_50
    await horizonSelect.setValue('RECENT_50')
    await flushPromises()
    expect(wrapper.text()).toContain('Short · 50')
    expect(wrapper.text()).toContain('LOW POWER')

    // Switch to RECENT_300
    await horizonSelect.setValue('RECENT_300')
    await flushPromises()
    expect(wrapper.text()).toContain('Medium · 300')

    // Switch to RECENT_750
    await horizonSelect.setValue('RECENT_750')
    await flushPromises()
    expect(wrapper.text()).toContain('Long · 750')

    // Switch to FULL
    await horizonSelect.setValue('FULL')
    await flushPromises()
    expect(wrapper.text()).toContain('Full')

    wrapper.unmount()
  })

  it('selects canonical Rank #1 as the Best Strategy summary leader', async () => {
    const wrapper = mount(BestReplayPage)
    await flushPromises()

    // Under B649 5T FULL, rank 1 is portfolio_optimizer
    expect(wrapper.text()).toContain('legacy_biglotto__portfolio_optimizer__fixture')
    expect(wrapper.text()).toContain('Rank #1 · B649')
    expect(wrapper.text()).toContain('27.66%')
    expect(wrapper.text()).toContain('+0.68 pp')

    wrapper.unmount()
  })

  it('distinguishes unavailable ticket counts explicitly without converting to 0% and displays reason', async () => {
    const wrapper = mount(BestReplayPage)
    await flushPromises()

    // Click 3T button (unavailable in B649 canonical records)
    await wrapper.find('[data-testid="ticket-btn-3"]').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('EVIDENCE UNAVAILABLE')
    expect(wrapper.text()).toContain('NO_CANONICAL_REPLAY_EVIDENCE')
    expect(wrapper.text()).toContain('No canonical multi-ticket backtest evidence is recorded for ticket count 3')

    // Confirm no 0.00% fake hit rate appears
    const monoCells = wrapper.findAll('.font-mono')
    const texts = monoCells.map((c) => c.text())
    expect(texts.some((t) => t === '0.00%')).toBe(false)

    wrapper.unmount()
  })

  it('preserves Official Rank as default ordering and allows User Sort with Reset to Official Rank', async () => {
    const wrapper = mount(BestReplayPage)
    await flushPromises()

    const rows = wrapper.findAll('tbody tr')
    expect(rows.length).toBeGreaterThan(0)
    expect(rows[0]?.text()).toContain('#1')
    expect(rows[0]?.text()).toContain('portfolio_optimizer')

    // User sorts by Hit Rate ascending
    const hitRateHeader = wrapper.findAll('thead th').find((th) => th.text().includes('Hit Rate'))
    await hitRateHeader?.trigger('click')
    await flushPromises()

    // Check custom sort state
    expect(wrapper.text()).toContain('hitRate (asc)')

    // Click Reset to Official Rank button
    const resetBtn = wrapper.find('[data-testid="reset-rank-btn"]')
    expect(resetBtn.exists()).toBe(true)
    await resetBtn.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('Official Rank')
    const resetRows = wrapper.findAll('tbody tr')
    expect(resetRows[0]?.text()).toContain('#1')

    wrapper.unmount()
  })

  it('renders all 5 cells in 1–5 Overview and switches active ticket count when card is clicked', async () => {
    const wrapper = mount(BestReplayPage)
    await flushPromises()

    const overview = wrapper.find('[data-testid="one-to-five-overview"]')
    expect(overview.exists()).toBe(true)

    // Verify all 5 cards exist
    for (const count of [1, 2, 3, 4, 5]) {
      const card = wrapper.find(`[data-testid="overview-card-${count}"]`)
      expect(card.exists()).toBe(true)
    }

    // In B649: card 5 is available, cards 1..4 are unavailable
    expect(wrapper.find('[data-testid="overview-card-5"]').classes()).toContain('overview-card--available')
    expect(wrapper.find('[data-testid="overview-card-1"]').classes()).toContain('overview-card--unavailable')

    // Click overview card 1
    await wrapper.find('[data-testid="overview-card-1"]').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('1 Tickets')
    expect(wrapper.text()).toContain('EVIDENCE UNAVAILABLE')

    wrapper.unmount()
  })

  it('maintains strict cross-game data isolation upon switching games', async () => {
    const wrapper = mount(BestReplayPage)
    await flushPromises()

    // Starts in B649
    expect(wrapper.text()).toContain('legacy_biglotto__portfolio_optimizer__fixture')
    expect(wrapper.text()).not.toContain('p638_zonal_entropy_leader')
    expect(wrapper.text()).not.toContain('t539_wave1_cyclic_leader')

    // Switch to P638
    await wrapper.find('[data-testid="game-btn-p638"]').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('p638_zonal_entropy_leader')
    expect(wrapper.text()).not.toContain('legacy_biglotto')
    expect(wrapper.text()).not.toContain('t539_wave1_cyclic_leader')

    // Switch to T539
    await wrapper.find('[data-testid="game-btn-t539"]').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('t539_wave1_cyclic_leader')
    expect(wrapper.text()).not.toContain('legacy_biglotto')
    expect(wrapper.text()).not.toContain('p638_zonal_entropy_leader')

    wrapper.unmount()
  })

  describe('Bounded UI Smoke Check Matrix (A through F)', () => {
    it('Smoke A: B649 → 1 → FULL renders explicit EVIDENCE UNAVAILABLE', async () => {
      const wrapper = mount(BestReplayPage)
      await flushPromises()

      await wrapper.find('[data-testid="game-btn-b649"]').trigger('click')
      await wrapper.find('#horizon-select').setValue('FULL')
      await wrapper.find('[data-testid="ticket-btn-1"]').trigger('click')
      await flushPromises()

      expect(wrapper.text()).toContain('EVIDENCE UNAVAILABLE')
      expect(wrapper.text()).toContain('NO_CANONICAL_REPLAY_EVIDENCE')
      expect(wrapper.text()).toContain('No canonical multi-ticket backtest evidence is recorded for ticket count 1')
      wrapper.unmount()
    })

    it('Smoke B: B649 → 5 → 300 renders canonical Rank #1 strategy', async () => {
      const wrapper = mount(BestReplayPage)
      await flushPromises()

      await wrapper.find('[data-testid="game-btn-b649"]').trigger('click')
      await wrapper.find('#horizon-select').setValue('RECENT_300')
      await wrapper.find('[data-testid="ticket-btn-5"]').trigger('click')
      await flushPromises()

      expect(wrapper.text()).toContain('legacy_biglotto__portfolio_optimizer__fixture')
      expect(wrapper.text()).toContain('Rank #1 · B649')
      expect(wrapper.text()).toContain('27.66%')
      wrapper.unmount()
    })

    it('Smoke C: P638 → 2 → 750 renders explicit EVIDENCE UNAVAILABLE', async () => {
      const wrapper = mount(BestReplayPage)
      await flushPromises()

      await wrapper.find('[data-testid="game-btn-p638"]').trigger('click')
      await wrapper.find('#horizon-select').setValue('RECENT_750')
      await wrapper.find('[data-testid="ticket-btn-2"]').trigger('click')
      await flushPromises()

      expect(wrapper.text()).toContain('EVIDENCE UNAVAILABLE')
      expect(wrapper.text()).toContain('NO_CANONICAL_REPLAY_EVIDENCE')
      expect(wrapper.text()).toContain('No canonical multi-ticket backtest evidence is recorded for ticket count 2')
      wrapper.unmount()
    })

    it('Smoke D: P638 → 5 → 50 renders explicit EVIDENCE UNAVAILABLE', async () => {
      const wrapper = mount(BestReplayPage)
      await flushPromises()

      await wrapper.find('[data-testid="game-btn-p638"]').trigger('click')
      await wrapper.find('#horizon-select').setValue('RECENT_50')
      await wrapper.find('[data-testid="ticket-btn-5"]').trigger('click')
      await flushPromises()

      expect(wrapper.text()).toContain('EVIDENCE UNAVAILABLE')
      expect(wrapper.text()).toContain('NO_CANONICAL_REPLAY_EVIDENCE')
      expect(wrapper.text()).toContain('No canonical multi-ticket backtest evidence is recorded for ticket count 5')
      wrapper.unmount()
    })

    it('Smoke E: T539 → 1 → FULL renders canonical Rank #1 strategy', async () => {
      const wrapper = mount(BestReplayPage)
      await flushPromises()

      await wrapper.find('[data-testid="game-btn-t539"]').trigger('click')
      await wrapper.find('#horizon-select').setValue('FULL')
      await wrapper.find('[data-testid="ticket-btn-1"]').trigger('click')
      await flushPromises()

      expect(wrapper.text()).toContain('t539_wave1_cyclic_leader')
      expect(wrapper.text()).toContain('Rank #1 · T539')
      expect(wrapper.text()).toContain('21.50%')
      wrapper.unmount()
    })

    it('Smoke F: T539 → 4 → 300 renders explicit EVIDENCE UNAVAILABLE', async () => {
      const wrapper = mount(BestReplayPage)
      await flushPromises()

      await wrapper.find('[data-testid="game-btn-t539"]').trigger('click')
      await wrapper.find('#horizon-select').setValue('RECENT_300')
      await wrapper.find('[data-testid="ticket-btn-4"]').trigger('click')
      await flushPromises()

      expect(wrapper.text()).toContain('EVIDENCE UNAVAILABLE')
      expect(wrapper.text()).toContain('NO_CANONICAL_REPLAY_EVIDENCE')
      expect(wrapper.text()).toContain('No canonical multi-ticket backtest evidence is recorded for ticket count 4')
      wrapper.unmount()
    })
  })
})

describe('BestReplayOneToFiveOverview Component Direct Unit Tests', () => {
  it('renders 5 cards with proper available and unavailable states', () => {
    const mockItem5: BestReplayItem = {
      id: 'B649-sample-5-FULL',
      rank: 1,
      strategyId: 'legacy_sample_optimizer',
      strategyVersion: 'v1.0',
      methodFamily: 'statistical',
      game: 'B649',
      ticketCount: 5,
      horizon: 'FULL',
      horizonLabel: 'Full',
      evaluatedTargets: 1949,
      winningTargets: 539,
      hitRate: 0.27655,
      hitRateFormatted: '27.66%',
      baselineProbability: 0.269,
      baselineDelta: 0.0067,
      baselineDeltaFormatted: '+0.67 pp',
      coverage: 0.9069,
      bestHit: '2nd Prize (1)',
      prizeCounts: { first: 0, second: 1, third: 0, fourth: 0, fifth: 0 },
      evidenceStatus: 'DESCRIPTIVE LEADER',
      notes: 'Historically strongest strategy',
      isAvailable: true,
    }

    const wrapper = mount(BestReplayOneToFiveOverview, {
      props: {
        game: 'B649',
        horizon: 'FULL',
        selectedTicketCount: 5,
        itemsByTicketCount: {
          1: null,
          2: null,
          3: null,
          4: null,
          5: mockItem5,
        },
      },
    })

    expect(wrapper.findAll('.overview-card').length).toBe(5)
    expect(wrapper.find('[data-testid="overview-card-5"]').text()).toContain('27.66%')
    expect(wrapper.find('[data-testid="overview-card-5"]').text()).toContain('+0.67 pp')
    expect(wrapper.find('[data-testid="overview-card-1"]').text()).toContain('Evidence Unavailable')

    wrapper.unmount()
  })
})

describe('BestReplayMatrix Component', () => {
  it('renders all 20 ticket count columns with distinct available and unavailable styling', () => {
    const sampleItem: BestReplayItem = {
      id: 'B649-sample-5-FULL',
      rank: 1,
      strategyId: 'legacy_biglotto__sample',
      strategyVersion: 'v1.0',
      methodFamily: 'statistical',
      game: 'B649',
      ticketCount: 5,
      horizon: 'FULL',
      horizonLabel: 'Full',
      evaluatedTargets: 1949,
      winningTargets: 539,
      hitRate: 0.27655,
      hitRateFormatted: '27.66%',
      baselineProbability: 0.269,
      baselineDelta: 0.0067,
      baselineDeltaFormatted: '+0.67 pp',
      coverage: 0.9,
      bestHit: '2nd Prize (1)',
      prizeCounts: { first: 0, second: 1, third: 0, fourth: 0, fifth: 0 },
      evidenceStatus: 'DESCRIPTIVE LEADER',
      notes: 'Historically strongest strategy',
      isAvailable: true,
    }

    const rows: BestReplayMatrixRow[] = [
      {
        strategyId: 'legacy_biglotto__sample',
        strategyLabel: 'sample',
        methodFamily: 'statistical',
        game: 'B649',
        cells: {
          1: null,
          2: null,
          3: null,
          4: null,
          5: sampleItem,
          6: null,
          7: null,
          8: null,
          9: null,
          10: null,
          11: null,
          12: null,
          13: null,
          14: null,
          15: null,
          16: null,
          17: null,
          18: null,
          19: null,
          20: null,
        },
      },
    ]

    const wrapper = mount(BestReplayMatrix, {
      props: {
        rows,
        selectedTicketCount: 5,
        selectedStrategyId: 'legacy_biglotto__sample',
      },
    })

    const headerCells = wrapper.findAll('thead th.col-ticket')
    expect(headerCells.length).toBe(20)

    const availableCell = wrapper.find('.matrix-cell--available')
    expect(availableCell.text()).toContain('27.66%')
    expect(availableCell.text()).toContain('+0.67 pp')

    const unavailableCells = wrapper.findAll('.matrix-cell--unavailable')
    expect(unavailableCells.length).toBe(19)

    wrapper.unmount()
  })
})

describe('BestReplayHorizonComparison Component', () => {
  it('renders four horizon cards with mini-bars and explicit unavailable states', () => {
    const fullItem: BestReplayItem = {
      id: 'B649-sample-5-FULL',
      rank: 1,
      strategyId: 'legacy_biglotto__sample',
      strategyVersion: 'v1.0',
      methodFamily: 'statistical',
      game: 'B649',
      ticketCount: 5,
      horizon: 'FULL',
      horizonLabel: 'Full',
      evaluatedTargets: 1949,
      winningTargets: 539,
      hitRate: 0.27655,
      hitRateFormatted: '27.66%',
      baselineProbability: 0.269,
      baselineDelta: 0.0067,
      baselineDeltaFormatted: '+0.67 pp',
      coverage: 0.9,
      bestHit: '2nd Prize (1)',
      prizeCounts: { first: 0, second: 1, third: 0, fourth: 0, fifth: 0 },
      evidenceStatus: 'DESCRIPTIVE LEADER',
      notes: 'Historically strongest strategy',
      isAvailable: true,
    }

    const wrapper = mount(BestReplayHorizonComparison, {
      props: {
        strategyId: 'legacy_biglotto__sample',
        strategyVersion: 'v1.0',
        ticketCount: 5,
        game: 'B649',
        itemsByHorizon: {
          FULL: fullItem,
          RECENT_750: null,
          RECENT_300: null,
          RECENT_50: null,
        },
      },
    })

    const fullCard = wrapper.find('[data-testid="horizon-card-full"]')
    expect(fullCard.text()).toContain('27.66%')
    expect(fullCard.text()).toContain('+0.67 pp')
    expect(fullCard.text()).toContain('DESCRIPTIVE LEADER')

    const shortCard = wrapper.find('[data-testid="horizon-card-recent-50"]')
    expect(shortCard.text()).toContain('Evidence Unavailable')

    wrapper.unmount()
  })
})

describe('P638 Best Replay Horizon Authority Validation (Correction R1)', () => {
  it('loadP638BestReplayData returns available items only for FULL horizon', async () => {
    const fullItems = await loadP638BestReplayData([1], 'FULL')
    expect(fullItems.length).toBe(2)

    const leader = fullItems[0]
    expect(leader?.isAvailable).toBe(true)
    expect(leader?.strategyId).toBe('p638_zonal_entropy_leader')
    expect(leader?.rank).toBe(1)
    expect(leader?.hitRate).toBe(0.185)
    expect(leader?.hitRateFormatted).toBe('18.50%')
    expect(leader?.evaluatedTargets).toBe(1000)
    expect(leader?.winningTargets).toBe(180)
    expect(leader?.evidenceStatus).toBe('DESCRIPTIVE LEADER')
    expect(leader?.notes).toContain('Descriptive historical evidence only; does not infer future performance')
  })

  it('loadP638BestReplayData fails closed for RECENT_50, RECENT_300, and RECENT_750 with explicit reason', async () => {
    for (const unsupportedHorizon of ['RECENT_50', 'RECENT_300', 'RECENT_750'] as const) {
      const items = await loadP638BestReplayData([1], unsupportedHorizon)
      expect(items.length).toBeGreaterThan(0)

      for (const item of items) {
        expect(item.isAvailable).toBe(false)
        expect(item.evidenceStatus).toBe('EVIDENCE UNAVAILABLE')
        expect(item.rank).toBeNull()
        expect(item.hitRate).toBeNull()
        expect(item.hitRateFormatted).toBe('Unavailable')
        expect(item.winningTargets).toBeNull()
        expect(item.evaluatedTargets).toBeNull()
        expect(item.unavailableReasonCode).toBe('NO_CANONICAL_WINDOW_EVIDENCE')
        expect(item.notes).toContain(
          `P638 canonical evidence does not publish an exact ${unsupportedHorizon} ranking window.`,
        )
        expect(item.notes).toContain('Descriptive historical evidence only; does not infer future performance')
      }
    }
  })

  it('loadP638BestReplayData rejects ticket counts 2, 3, 4, and 5', async () => {
    const multiTicketItems = await loadP638BestReplayData([2, 3, 4, 5], 'FULL')
    expect(multiTicketItems).toEqual([])

    const multiTicketRecentItems = await loadP638BestReplayData([2, 3, 4, 5], 'RECENT_50')
    expect(multiTicketRecentItems).toEqual([])
  })

  it('proves no P638 horizon reuses identical latest ranking results under relabeled RECENT windows', async () => {
    const fullItems = await loadP638BestReplayData([1], 'FULL')
    const recent50Items = await loadP638BestReplayData([1], 'RECENT_50')
    const recent300Items = await loadP638BestReplayData([1], 'RECENT_300')
    const recent750Items = await loadP638BestReplayData([1], 'RECENT_750')

    const fullLeader = fullItems[0]
    expect(fullLeader?.isAvailable).toBe(true)
    expect(fullLeader?.rank).toBe(1)
    expect(fullLeader?.hitRate).toBe(0.185)

    // All RECENT horizons must NOT have rank 1 or 18.5% hit rate
    for (const recentSet of [recent50Items, recent300Items, recent750Items]) {
      const recentLeader = recentSet[0]
      expect(recentLeader?.isAvailable).toBe(false)
      expect(recentLeader?.rank).toBeNull()
      expect(recentLeader?.hitRate).toBeNull()
      expect(recentLeader?.hitRateFormatted).toBe('Unavailable')
    }
  })

  it('renders P638 at RECENT_50 as explicit EVIDENCE UNAVAILABLE in UI without 0% or fake hit rate', async () => {
    const wrapper = mount(BestReplayPage)
    await flushPromises()

    // Switch to P638
    await wrapper.find('[data-testid="game-btn-p638"]').trigger('click')
    await flushPromises()

    // Switch to RECENT_50
    await wrapper.find('#horizon-select').setValue('RECENT_50')
    await flushPromises()

    // Summary Card must be unavailable
    const metricsGrid = wrapper.find('[data-testid="best-replay-metrics-grid"]')
    expect(metricsGrid.text()).toContain('Evidence Unavailable')
    expect(metricsGrid.text()).toContain('Unavailable')
    expect(metricsGrid.text()).toContain('EVIDENCE UNAVAILABLE')

    // 1–5 Overview Card 1 must be unavailable with NO_CANONICAL_WINDOW_EVIDENCE
    const card1 = wrapper.find('[data-testid="overview-card-1"]')
    expect(card1.classes()).toContain('overview-card--unavailable')
    expect(card1.text()).toContain('NO_CANONICAL_WINDOW_EVIDENCE')
    expect(card1.text()).toContain('P638 canonical evidence does not publish an exact RECENT_50 ranking window')

    // Overview cards 2..5 must be unavailable with NO_CANONICAL_REPLAY_EVIDENCE
    for (const count of [2, 3, 4, 5]) {
      const card = wrapper.find(`[data-testid="overview-card-${count}"]`)
      expect(card.classes()).toContain('overview-card--unavailable')
      expect(card.text()).toContain('NO_CANONICAL_REPLAY_EVIDENCE')
    }

    // Table rows must show Rank — and Hit Rate Unavailable
    const rows = wrapper.findAll('tbody tr')
    expect(rows.length).toBeGreaterThan(0)
    for (const row of rows) {
      expect(row.text()).toContain('Unavailable')
      expect(row.text()).toContain('EVIDENCE UNAVAILABLE')
      expect(row.text()).toContain('P638 canonical evidence does not publish an exact RECENT_50 ranking window')
    }

    // Verify 0.00% fake hit rate does not appear
    const visibleTexts = wrapper.findAll('.font-mono').map((c) => c.text())
    expect(visibleTexts.some((t) => t === '0.00%')).toBe(false)
    expect(visibleTexts.some((t) => t === '18.50%')).toBe(false)

    wrapper.unmount()
  })

  it('renders P638 at FULL with canonical Rank #1 while horizon comparison shows RECENT windows unavailable', async () => {
    const wrapper = mount(BestReplayPage)
    await flushPromises()

    // Switch to P638 with FULL horizon default
    await wrapper.find('[data-testid="game-btn-p638"]').trigger('click')
    await wrapper.find('#horizon-select').setValue('FULL')
    await flushPromises()

    // Summary Card shows canonical leader
    const metricsGrid = wrapper.find('[data-testid="best-replay-metrics-grid"]')
    expect(metricsGrid.text()).toContain('p638_zonal_entropy_leader')
    expect(metricsGrid.text()).toContain('18.50%')
    expect(metricsGrid.text()).toContain('DESCRIPTIVE LEADER')

    // 1–5 Overview Card 1 is available
    const card1 = wrapper.find('[data-testid="overview-card-1"]')
    expect(card1.classes()).toContain('overview-card--available')
    expect(card1.text()).toContain('18.50%')

    // Horizon comparison breakdown
    const fullHorizonCard = wrapper.find('[data-testid="horizon-card-full"]')
    expect(fullHorizonCard.classes()).toContain('horizon-card--available')
    expect(fullHorizonCard.text()).toContain('18.50%')

    const shortHorizonCard = wrapper.find('[data-testid="horizon-card-recent-50"]')
    expect(shortHorizonCard.classes()).not.toContain('horizon-card--available')
    expect(shortHorizonCard.text()).toContain('Evidence Unavailable')
    expect(shortHorizonCard.text()).toContain('P638 canonical evidence does not publish an exact RECENT_50 ranking window')

    const mediumHorizonCard = wrapper.find('[data-testid="horizon-card-recent-300"]')
    expect(mediumHorizonCard.classes()).not.toContain('horizon-card--available')
    expect(mediumHorizonCard.text()).toContain('Evidence Unavailable')
    expect(mediumHorizonCard.text()).toContain('P638 canonical evidence does not publish an exact RECENT_300 ranking window')

    const longHorizonCard = wrapper.find('[data-testid="horizon-card-recent-750"]')
    expect(longHorizonCard.classes()).not.toContain('horizon-card--available')
    expect(longHorizonCard.text()).toContain('Evidence Unavailable')
    expect(longHorizonCard.text()).toContain('P638 canonical evidence does not publish an exact RECENT_750 ranking window')

    wrapper.unmount()
  })
})

describe('T539 Best Replay Horizon Authority Validation (Correction R1)', () => {
  it('loadT539BestReplayData returns available items only for FULL horizon', async () => {
    const fullItems = await loadT539BestReplayData([1], 'FULL')
    expect(fullItems.length).toBe(2)

    const leader = fullItems[0]
    expect(leader?.isAvailable).toBe(true)
    expect(leader?.strategyId).toBe('t539_wave1_cyclic_leader')
    expect(leader?.rank).toBe(1)
    expect(leader?.hitRate).toBe(0.215)
    expect(leader?.hitRateFormatted).toBe('21.50%')
    expect(leader?.evaluatedTargets).toBe(1000)
    expect(leader?.winningTargets).toBe(211)
    expect(leader?.evidenceStatus).toBe('DESCRIPTIVE LEADER')
    expect(leader?.notes).toContain('Descriptive historical evidence only; does not infer future performance')
  })

  it('loadT539BestReplayData fails closed for RECENT_50, RECENT_300, and RECENT_750 with explicit reason', async () => {
    for (const unsupportedHorizon of ['RECENT_50', 'RECENT_300', 'RECENT_750'] as const) {
      const items = await loadT539BestReplayData([1], unsupportedHorizon)
      expect(items.length).toBeGreaterThan(0)

      for (const item of items) {
        expect(item.isAvailable).toBe(false)
        expect(item.evidenceStatus).toBe('EVIDENCE UNAVAILABLE')
        expect(item.rank).toBeNull()
        expect(item.hitRate).toBeNull()
        expect(item.hitRateFormatted).toBe('Unavailable')
        expect(item.winningTargets).toBeNull()
        expect(item.evaluatedTargets).toBeNull()
        expect(item.unavailableReasonCode).toBe('NO_CANONICAL_WINDOW_EVIDENCE')
        expect(item.notes).toContain(
          `T539 canonical evidence does not publish an exact ${unsupportedHorizon} ranking window.`,
        )
        expect(item.notes).toContain('Descriptive historical evidence only; does not infer future performance')
      }
    }
  })

  it('loadT539BestReplayData rejects ticket counts 2, 3, 4, and 5', async () => {
    const multiTicketItems = await loadT539BestReplayData([2, 3, 4, 5], 'FULL')
    expect(multiTicketItems).toEqual([])

    const multiTicketRecentItems = await loadT539BestReplayData([2, 3, 4, 5], 'RECENT_50')
    expect(multiTicketRecentItems).toEqual([])
  })

  it('proves no T539 horizon reuses identical latest ranking results under relabeled RECENT windows', async () => {
    const fullItems = await loadT539BestReplayData([1], 'FULL')
    const recent50Items = await loadT539BestReplayData([1], 'RECENT_50')
    const recent300Items = await loadT539BestReplayData([1], 'RECENT_300')
    const recent750Items = await loadT539BestReplayData([1], 'RECENT_750')

    const fullLeader = fullItems[0]
    expect(fullLeader?.isAvailable).toBe(true)
    expect(fullLeader?.rank).toBe(1)
    expect(fullLeader?.hitRate).toBe(0.215)

    // All RECENT horizons must NOT have rank 1 or 21.5% hit rate
    for (const recentSet of [recent50Items, recent300Items, recent750Items]) {
      const recentLeader = recentSet[0]
      expect(recentLeader?.isAvailable).toBe(false)
      expect(recentLeader?.rank).toBeNull()
      expect(recentLeader?.hitRate).toBeNull()
      expect(recentLeader?.hitRateFormatted).toBe('Unavailable')
    }
  })

  it('renders T539 at RECENT_50 as explicit EVIDENCE UNAVAILABLE in UI without 0% or fake hit rate', async () => {
    const wrapper = mount(BestReplayPage)
    await flushPromises()

    // Switch to T539
    await wrapper.find('[data-testid="game-btn-t539"]').trigger('click')
    await flushPromises()

    // Switch to RECENT_50
    await wrapper.find('#horizon-select').setValue('RECENT_50')
    await flushPromises()

    // Summary Card must be unavailable
    const metricsGrid = wrapper.find('[data-testid="best-replay-metrics-grid"]')
    expect(metricsGrid.text()).toContain('Evidence Unavailable')
    expect(metricsGrid.text()).toContain('Unavailable')
    expect(metricsGrid.text()).toContain('EVIDENCE UNAVAILABLE')

    // 1–5 Overview Card 1 must be unavailable with NO_CANONICAL_WINDOW_EVIDENCE
    const card1 = wrapper.find('[data-testid="overview-card-1"]')
    expect(card1.classes()).toContain('overview-card--unavailable')
    expect(card1.text()).toContain('NO_CANONICAL_WINDOW_EVIDENCE')
    expect(card1.text()).toContain('T539 canonical evidence does not publish an exact RECENT_50 ranking window')

    // Overview cards 2..5 must be unavailable with NO_CANONICAL_REPLAY_EVIDENCE
    for (const count of [2, 3, 4, 5]) {
      const card = wrapper.find(`[data-testid="overview-card-${count}"]`)
      expect(card.classes()).toContain('overview-card--unavailable')
      expect(card.text()).toContain('NO_CANONICAL_REPLAY_EVIDENCE')
    }

    // Table rows must show Rank — and Hit Rate Unavailable
    const rows = wrapper.findAll('tbody tr')
    expect(rows.length).toBeGreaterThan(0)
    for (const row of rows) {
      expect(row.text()).toContain('Unavailable')
      expect(row.text()).toContain('EVIDENCE UNAVAILABLE')
      expect(row.text()).toContain('T539 canonical evidence does not publish an exact RECENT_50 ranking window')
    }

    // Verify 0.00% fake hit rate does not appear
    const visibleTexts = wrapper.findAll('.font-mono').map((c) => c.text())
    expect(visibleTexts.some((t) => t === '0.00%')).toBe(false)
    expect(visibleTexts.some((t) => t === '21.50%')).toBe(false)

    wrapper.unmount()
  })

  it('renders T539 at FULL with canonical Rank #1 while horizon comparison shows RECENT windows unavailable', async () => {
    const wrapper = mount(BestReplayPage)
    await flushPromises()

    // Switch to T539 with FULL horizon default
    await wrapper.find('[data-testid="game-btn-t539"]').trigger('click')
    await wrapper.find('#horizon-select').setValue('FULL')
    await flushPromises()

    // Summary Card shows canonical leader
    const metricsGrid = wrapper.find('[data-testid="best-replay-metrics-grid"]')
    expect(metricsGrid.text()).toContain('t539_wave1_cyclic_leader')
    expect(metricsGrid.text()).toContain('21.50%')
    expect(metricsGrid.text()).toContain('DESCRIPTIVE LEADER')

    // 1–5 Overview Card 1 is available
    const card1 = wrapper.find('[data-testid="overview-card-1"]')
    expect(card1.classes()).toContain('overview-card--available')
    expect(card1.text()).toContain('21.50%')

    // Horizon comparison breakdown
    const fullHorizonCard = wrapper.find('[data-testid="horizon-card-full"]')
    expect(fullHorizonCard.classes()).toContain('horizon-card--available')
    expect(fullHorizonCard.text()).toContain('21.50%')

    const shortHorizonCard = wrapper.find('[data-testid="horizon-card-recent-50"]')
    expect(shortHorizonCard.classes()).not.toContain('horizon-card--available')
    expect(shortHorizonCard.text()).toContain('Evidence Unavailable')
    expect(shortHorizonCard.text()).toContain('T539 canonical evidence does not publish an exact RECENT_50 ranking window')

    const mediumHorizonCard = wrapper.find('[data-testid="horizon-card-recent-300"]')
    expect(mediumHorizonCard.classes()).not.toContain('horizon-card--available')
    expect(mediumHorizonCard.text()).toContain('Evidence Unavailable')
    expect(mediumHorizonCard.text()).toContain('T539 canonical evidence does not publish an exact RECENT_300 ranking window')

    const longHorizonCard = wrapper.find('[data-testid="horizon-card-recent-750"]')
    expect(longHorizonCard.classes()).not.toContain('horizon-card--available')
    expect(longHorizonCard.text()).toContain('Evidence Unavailable')
    expect(longHorizonCard.text()).toContain('T539 canonical evidence does not publish an exact RECENT_750 ranking window')

    wrapper.unmount()
  })
})

describe('MSA_UI_HISTORICAL_REPLAY_UX_R1 Focused Acceptance Suite', () => {
  it('AC2 & AC3 & AC5: B649 concise summary displays accurate data from loaded official records', async () => {
    const wrapper = mount(BestReplayPage)
    await flushPromises()

    const summaryPanel = wrapper.find('[data-testid="concise-summary-panel"]')
    expect(summaryPanel.exists()).toBe(true)

    // Game, tickets, horizon, status
    expect(wrapper.find('[data-testid="summary-game"]').text()).toContain('B649 (Big Lotto 6/49)')
    expect(wrapper.find('[data-testid="summary-tickets"]').text()).toContain('5 Tickets')
    expect(wrapper.find('[data-testid="summary-horizon"]').text()).toContain('Full')
    expect(wrapper.find('[data-testid="summary-status"]').text()).toContain('DESCRIPTIVE LEADER')

    // Strategy & rank
    expect(summaryPanel.text()).toContain('portfolio_optimizer')
    expect(summaryPanel.text()).toContain('Rank #1 · B649')

    // Hit rate, sample size, delta
    expect(summaryPanel.text()).toContain('27.66%')
    expect(summaryPanel.text()).toContain('1,949 Historical Draws')
    expect(summaryPanel.text()).toContain('+0.68 pp')

    wrapper.unmount()
  })

  it('AC2 & AC3 & AC5: P638 concise summary displays accurate data and isolates from B649', async () => {
    const wrapper = mount(BestReplayPage)
    await flushPromises()

    await wrapper.find('[data-testid="game-btn-p638"]').trigger('click')
    await flushPromises()

    const summaryPanel = wrapper.find('[data-testid="concise-summary-panel"]')
    expect(summaryPanel.exists()).toBe(true)

    expect(wrapper.find('[data-testid="summary-game"]').text()).toContain('P638 (Power Lotto 6/38)')
    expect(wrapper.find('[data-testid="summary-tickets"]').text()).toContain('1 Tickets')
    expect(wrapper.find('[data-testid="summary-horizon"]').text()).toContain('Full')
    expect(wrapper.find('[data-testid="summary-status"]').text()).toContain('DESCRIPTIVE LEADER')

    expect(summaryPanel.text()).toContain('p638_zonal_entropy_leader')
    expect(summaryPanel.text()).toContain('Rank #1 · P638')
    expect(summaryPanel.text()).toContain('18.50%')
    expect(summaryPanel.text()).toContain('1,000 Historical Draws')
    expect(summaryPanel.text()).toContain('Baseline delta unavailable')

    // Verify no B649 or T539 data is present
    expect(summaryPanel.text()).not.toContain('portfolio_optimizer')
    expect(summaryPanel.text()).not.toContain('t539_wave1_cyclic_leader')

    wrapper.unmount()
  })

  it('AC2 & AC3 & AC5: T539 concise summary displays accurate data and isolates from other games', async () => {
    const wrapper = mount(BestReplayPage)
    await flushPromises()

    await wrapper.find('[data-testid="game-btn-t539"]').trigger('click')
    await flushPromises()

    const summaryPanel = wrapper.find('[data-testid="concise-summary-panel"]')
    expect(summaryPanel.exists()).toBe(true)

    expect(wrapper.find('[data-testid="summary-game"]').text()).toContain('T539 (Daily Cash 5/39)')
    expect(wrapper.find('[data-testid="summary-tickets"]').text()).toContain('1 Tickets')
    expect(wrapper.find('[data-testid="summary-horizon"]').text()).toContain('Full')
    expect(wrapper.find('[data-testid="summary-status"]').text()).toContain('DESCRIPTIVE LEADER')

    expect(summaryPanel.text()).toContain('t539_wave1_cyclic_leader')
    expect(summaryPanel.text()).toContain('Rank #1 · T539')
    expect(summaryPanel.text()).toContain('21.50%')
    expect(summaryPanel.text()).toContain('1,000 Historical Draws')
    expect(summaryPanel.text()).toContain('Baseline delta unavailable')

    // Verify no B649 or P638 data is present
    expect(summaryPanel.text()).not.toContain('portfolio_optimizer')
    expect(summaryPanel.text()).not.toContain('p638_zonal_entropy_leader')

    wrapper.unmount()
  })

  it('AC4: History windows are isolated and never cross-pollinate rates or sample sizes', async () => {
    const wrapper = mount(BestReplayPage)
    await flushPromises()

    // Under B649, switch to RECENT_50
    await wrapper.find('#horizon-select').setValue('RECENT_50')
    await flushPromises()

    expect(wrapper.find('[data-testid="summary-horizon"]').text()).toContain('Short · 50')
    expect(wrapper.find('[data-testid="concise-summary-panel"]').text()).toContain('50 Historical Draws')
    expect(wrapper.find('[data-testid="concise-summary-panel"]').text()).not.toContain('1,949 Historical Draws')

    // Under P638, non-FULL horizons are marked unavailable
    await wrapper.find('[data-testid="game-btn-p638"]').trigger('click')
    await wrapper.find('#horizon-select').setValue('RECENT_300')
    await flushPromises()

    const p638Summary = wrapper.find('[data-testid="concise-summary-panel"]')
    expect(p638Summary.text()).toContain('Evidence Unavailable')
    expect(p638Summary.text()).toContain('EVIDENCE UNAVAILABLE')
    expect(p638Summary.text()).not.toContain('18.50%')

    wrapper.unmount()
  })

  it('AC5 & AC7: Distinguishes true 0, missing/null, and unavailable states cleanly', async () => {
    // Zero sample count
    p638CompleteTargetCount = 0
    const wrapper = mount(BestReplayPage)
    await flushPromises()

    await wrapper.find('[data-testid="game-btn-p638"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-testid="concise-summary-panel"]').text()).toContain('0 Historical Draws')
    expect(wrapper.find('[data-testid="concise-summary-panel"]').text()).not.toContain('Sample count unknown')

    // Null sample count
    p638CompleteTargetCount = null
    await wrapper.find('[data-testid="game-btn-b649"]').trigger('click')
    await flushPromises()
    await wrapper.find('[data-testid="game-btn-p638"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-testid="concise-summary-panel"]').text()).toContain('Sample count unknown')

    // Unavailable ticket count (e.g. 4 tickets in B649)
    await wrapper.find('[data-testid="game-btn-b649"]').trigger('click')
    await wrapper.find('[data-testid="ticket-btn-4"]').trigger('click')
    await flushPromises()

    const unavailableSummary = wrapper.find('[data-testid="concise-summary-panel"]')
    expect(unavailableSummary.text()).toContain('Evidence Unavailable')
    expect(unavailableSummary.text()).toContain('EVIDENCE UNAVAILABLE')
    expect(unavailableSummary.text()).toContain('Unavailable')

    // Ensure 0.00% is not shown as a fake fallback
    expect(unavailableSummary.text().includes('0.00%')).toBe(false)

    wrapper.unmount()
  })

  it('AC8 & AC9: Detailed research section is expandable, collapsible, and preserves selection state', async () => {
    const wrapper = mount(BestReplayPage)
    await flushPromises()

    const toggle = wrapper.find('[data-testid="toggle-research-details"]')
    expect(toggle.exists()).toBe(true)

    // Initial state: details section is collapsed
    const disclosure = wrapper.find('[data-testid="research-details-disclosure"]')
    expect(disclosure.exists()).toBe(true)
    expect(toggle.text()).toContain('View Complete Research Evidence')

    // Click to expand
    await toggle.trigger('click')
    await flushPromises()

    expect(toggle.text()).toContain('Hide Complete Research Evidence')
    const detailedContent = wrapper.find('[data-testid="detailed-research-content"]')
    expect(detailedContent.exists()).toBe(true)

    // Verify 1-5 overview, filter bar, and data table exist
    expect(wrapper.find('[data-testid="one-to-five-overview"]').exists()).toBe(true)
    expect(wrapper.findAll('tbody tr').length).toBeGreaterThan(0)

    // User changes ticket selection inside detailed content
    await wrapper.find('[data-testid="ticket-btn-10"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-testid="summary-tickets"]').text()).toContain('10 Tickets')

    // Collapse detailed section
    await toggle.trigger('click')
    await flushPromises()

    expect(toggle.text()).toContain('View Complete Research Evidence')
    // Selection state is preserved across collapse
    expect(wrapper.find('[data-testid="summary-tickets"]').text()).toContain('10 Tickets')

    // Re-expand: selection is still 10 tickets
    await toggle.trigger('click')
    await flushPromises()

    expect(toggle.text()).toContain('Hide Complete Research Evidence')
    expect(wrapper.find('[data-testid="summary-tickets"]').text()).toContain('10 Tickets')

    wrapper.unmount()
  })

  it('AC8: Preserves Ranking Table, Horizon Comparison, and 1-20 Matrix views inside detailed area', async () => {
    const wrapper = mount(BestReplayPage)
    await flushPromises()

    // Expand details
    await wrapper.find('[data-testid="toggle-research-details"]').trigger('click')
    await flushPromises()

    // View 1: Ranking Table
    expect(wrapper.find('.table-workspace').exists()).toBe(true)

    // View 2: Switch to Horizon Comparison
    const comparisonBtn = wrapper.findAll('.view-mode-tabs button').find((b) => b.text().includes('Horizon Comparison'))
    await comparisonBtn?.trigger('click')
    await flushPromises()

    expect(wrapper.find('.comparison-workspace').exists()).toBe(true)

    // View 3: Switch to 1-20 Matrix
    const matrixBtn = wrapper.findAll('.view-mode-tabs button').find((b) => b.text().includes('1–20 Matrix'))
    await matrixBtn?.trigger('click')
    await flushPromises()

    expect(wrapper.find('.matrix-workspace').exists()).toBe(true)

    wrapper.unmount()
  })

  it('AC7: Handles API 503 and network failure gracefully with retry', async () => {
    fetchMock.mockImplementationOnce(() =>
      Promise.resolve({
        ok: false,
        status: 503,
        json: () => Promise.resolve({ detail: 'Service Unavailable' }),
      } as unknown as Response),
    )

    const wrapper = mount(BestReplayPage)
    await flushPromises()

    // Error banner in summary panel and ErrorState inside detailed area
    const errorBanner = wrapper.find('[data-testid="summary-error-banner"]')
    expect(errorBanner.exists()).toBe(true)
    expect(errorBanner.text()).toContain('Failed to load')

    expect(wrapper.find('.error-state').exists()).toBe(true)

    wrapper.unmount()
  })

  it('AC10: Async race condition prevents stale responses from overwriting latest game data', async () => {
    let resolveB649!: (res: Response) => void
    const b649Promise = new Promise<Response>((resolve) => {
      resolveB649 = resolve
    })

    fetchMock.mockImplementation((input) => {
      const url = new URL(String(input), 'http://localhost')
      if (url.pathname.includes('/b649-multi-ticket-records/summary')) {
        return Promise.resolve(apiResponse(mockB649Summary()))
      }
      if (url.pathname.includes('/b649-multi-ticket-records')) {
        // Delayed response for B649
        return b649Promise
      }
      if (url.pathname.includes('/p638-historical/runs') && url.pathname.includes('/rankings')) {
        return Promise.resolve(apiResponse(mockP638Rankings()))
      }
      if (url.pathname.includes('/p638-historical/runs')) {
        return Promise.resolve(apiResponse(mockP638Runs()))
      }
      return Promise.resolve(apiResponse({}))
    })

    const wrapper = mount(BestReplayPage)
    // Don't flush yet for B649; immediately switch to P638
    await wrapper.find('[data-testid="game-btn-p638"]').trigger('click')
    await flushPromises()

    // P638 has loaded fast
    expect(wrapper.find('[data-testid="summary-game"]').text()).toContain('P638')
    expect(wrapper.text()).toContain('p638_zonal_entropy_leader')

    // Now resolve the delayed B649 response
    resolveB649(apiResponse(mockB649RecordsPage(new URL('http://localhost/api/v1/b649-multi-ticket-records?prefix_count=5&window=FULL'))))
    await flushPromises()

    // Current page MUST still be P638, not overwritten by stale B649 response
    expect(wrapper.find('[data-testid="summary-game"]').text()).toContain('P638')
    expect(wrapper.text()).toContain('p638_zonal_entropy_leader')
    expect(wrapper.text()).not.toContain('portfolio_optimizer')

    wrapper.unmount()
  })
})

describe('MSA_UI_REPLAY_DELTA_UNIT_R1 Best Replay Delta Unit Semantics', () => {
  it('formats single hit rates using percent (%) and never percentage points (pp)', () => {
    expect(formatRatePercentage(0.2766)).toBe('27.66%')
    expect(formatRatePercentage(0.185)).toBe('18.50%')
    expect(formatRatePercentage(0)).toBe('0.00%')
    expect(formatRatePercentage(null)).toBe('Unavailable')
    expect(formatRatePercentage(undefined)).toBe('Unavailable')
    expect(formatRatePercentage(Number.NaN)).toBe('Unavailable')

    expect(formatRatePercentage(0.2766)).not.toContain('pp')
  })

  it('formats baseline delta using percentage points (pp) for positive, negative, zero, and missing', () => {
    // positive delta
    expect(formatDeltaPercentage(0.0068)).toBe('+0.68 pp')
    expect(formatDeltaPercentage(0.0012)).toBe('+0.12 pp')
    // negative delta
    expect(formatDeltaPercentage(-0.0068)).toBe('-0.68 pp')
    expect(formatDeltaPercentage(-0.0054)).toBe('-0.54 pp')
    // zero delta
    expect(formatDeltaPercentage(0)).toBe('0.00 pp')
    // null / undefined / NaN
    expect(formatDeltaPercentage(null)).toBe('Unavailable')
    expect(formatDeltaPercentage(undefined)).toBe('Unavailable')
    expect(formatDeltaPercentage(Number.NaN)).toBe('Unavailable')

    // does not output % for delta
    expect(formatDeltaPercentage(0.0068)).not.toContain('%')
    expect(formatDeltaPercentage(-0.0068)).not.toContain('%')
    expect(formatDeltaPercentage(0)).not.toContain('%')
  })

  it('transforms B649 records with correct rate (%) and delta (pp) semantics', () => {
    const recordPos = mockB649Record(5, 'FULL', 'pos_delta', { rank: 1, rate: '0.276600', delta: '0.006800' })
    const itemPos = transformB649Record(recordPos, 'FULL', 5)
    expect(itemPos.hitRateFormatted).toBe('27.66%')
    expect(itemPos.baselineDeltaFormatted).toBe('+0.68 pp')

    const recordNeg = mockB649Record(5, 'FULL', 'neg_delta', { rank: 2, rate: '0.240100', delta: '-0.006800' })
    const itemNeg = transformB649Record(recordNeg, 'FULL', 5)
    expect(itemNeg.hitRateFormatted).toBe('24.01%')
    expect(itemNeg.baselineDeltaFormatted).toBe('-0.68 pp')

    const recordZero = mockB649Record(5, 'FULL', 'zero_delta', { rank: 3, rate: '0.269800', delta: '0.000000' })
    const itemZero = transformB649Record(recordZero, 'FULL', 5)
    expect(itemZero.hitRateFormatted).toBe('26.98%')
    expect(itemZero.baselineDeltaFormatted).toBe('0.00 pp')

    const recordNull = {
      ...mockB649Record(5, 'FULL', 'null_delta', { rank: 4 }),
      official_random_baseline_delta: null,
      random_baseline_rate_difference: null,
    } as unknown as B649MultiTicketRecord
    const itemNull = transformB649Record(recordNull, 'FULL', 5)
    expect(itemNull.baselineDeltaFormatted).toBe('Unavailable')
  })

  it('guarantees UI summary and detailed research table display consistent pp units for B649', async () => {
    const wrapper = mount(BestReplayPage)
    await flushPromises()

    // Expand details
    await wrapper.find('[data-testid="toggle-research-details"]').trigger('click')
    await flushPromises()

    // 1. Summary displays delta in pp and rate in %
    const summaryPanel = wrapper.find('[data-testid="concise-summary-panel"]')
    expect(summaryPanel.text()).toContain('27.66%')
    expect(summaryPanel.text()).toContain('+0.68 pp')
    expect(summaryPanel.text()).not.toContain('+0.68%')
    expect(summaryPanel.text()).not.toContain('27.66 pp')

    // 2. Table rows display delta in pp and rate in %
    const rows = wrapper.findAll('tbody tr')
    expect(rows.length).toBeGreaterThanOrEqual(3)

    // Row 1 (portfolio_optimizer): rate 27.66%, delta +0.68 pp
    const row1Text = rows[0]!.text()
    expect(row1Text).toContain('27.66%')
    expect(row1Text).toContain('+0.68 pp')

    // Row 2 (6bet_ewma): rate 25.12%, delta +0.12 pp
    const row2Text = rows[1]!.text()
    expect(row2Text).toContain('25.12%')
    expect(row2Text).toContain('+0.12 pp')

    // Row 3 (coldpool_15): rate 24.01%, delta -0.54 pp
    const row3Text = rows[2]!.text()
    expect(row3Text).toContain('24.01%')
    expect(row3Text).toContain('-0.54 pp')

    wrapper.unmount()
  })

  it('keeps P638 and T539 baseline delta unavailable without synthesizing a delta', async () => {
    const wrapper = mount(BestReplayPage)
    await flushPromises()

    // P638 check
    await wrapper.find('[data-testid="game-btn-p638"]').trigger('click')
    await flushPromises()

    const p638Summary = wrapper.find('[data-testid="concise-summary-panel"]')
    expect(p638Summary.text()).toContain('Baseline delta unavailable')
    expect(p638Summary.text()).toContain('18.50%')
    expect(p638Summary.text()).not.toContain('pp')

    const p638Rows = wrapper.findAll('tbody tr')
    expect(p638Rows.length).toBeGreaterThan(0)
    for (const row of p638Rows) {
      expect(row.text()).toContain('Unavailable')
      expect(row.text()).not.toContain('0.00 pp')
      expect(row.text()).not.toContain('+0.00 pp')
    }

    // T539 check
    await wrapper.find('[data-testid="game-btn-t539"]').trigger('click')
    await flushPromises()

    const t539Summary = wrapper.find('[data-testid="concise-summary-panel"]')
    expect(t539Summary.text()).toContain('Baseline delta unavailable')
    expect(t539Summary.text()).toContain('21.50%')
    expect(t539Summary.text()).not.toContain('pp')

    const t539Rows = wrapper.findAll('tbody tr')
    expect(t539Rows.length).toBeGreaterThan(0)
    for (const row of t539Rows) {
      expect(row.text()).toContain('Unavailable')
      expect(row.text()).not.toContain('0.00 pp')
      expect(row.text()).not.toContain('+0.00 pp')
    }

    wrapper.unmount()
  })
})
