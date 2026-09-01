// @vitest-environment jsdom

import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import BestReplayHorizonComparison from '../src/features/best-replay/BestReplayHorizonComparison.vue'
import BestReplayMatrix from '../src/features/best-replay/BestReplayMatrix.vue'
import BestReplayOneToFiveOverview from '../src/features/best-replay/BestReplayOneToFiveOverview.vue'
import BestReplayPage from '../src/features/best-replay/BestReplayPage.vue'
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
        complete_target_count: 1000,
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
        rank: 1,
        winning_target_rate: 0.185,
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
        rank: 2,
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
        rank: 1,
        winning_target_rate: 0.215,
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
        rank: 2,
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
    expect(wrapper.text()).toContain('+0.68%')

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
      baselineDeltaFormatted: '+0.67%',
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
    expect(wrapper.find('[data-testid="overview-card-5"]').text()).toContain('+0.67%')
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
      baselineDeltaFormatted: '+0.67%',
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
    expect(availableCell.text()).toContain('+0.67%')

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
      baselineDeltaFormatted: '+0.67%',
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
    expect(fullCard.text()).toContain('+0.67%')
    expect(fullCard.text()).toContain('DESCRIPTIVE LEADER')

    const shortCard = wrapper.find('[data-testid="horizon-card-recent-50"]')
    expect(shortCard.text()).toContain('Evidence Unavailable')

    wrapper.unmount()
  })
})
