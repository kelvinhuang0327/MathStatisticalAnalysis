// @vitest-environment jsdom

import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import BestReplayHorizonComparison from '../src/features/best-replay/BestReplayHorizonComparison.vue'
import BestReplayMatrix from '../src/features/best-replay/BestReplayMatrix.vue'
import BestReplayPage from '../src/features/best-replay/BestReplayPage.vue'
import {
  ALL_TICKET_COUNTS,
  B649_AVAILABLE_TICKET_COUNTS,
  CANONICAL_HORIZONS,
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
      draws: window === 'RECENT_50' ? 50 : 1949,
      hits: window === 'RECENT_50' ? 14 : 539,
    }),
    mockB649Record(prefixCount, window, '6bet_ewma', {
      rank: 2,
      rate: '0.251200',
      delta: '0.001200',
      draws: window === 'RECENT_50' ? 50 : 1949,
      hits: window === 'RECENT_50' ? 12 : 489,
    }),
    mockB649Record(prefixCount, window, 'coldpool_15', {
      rank: 3,
      rate: '0.240100',
      delta: '-0.005400',
      draws: window === 'RECENT_50' ? 50 : 1949,
      hits: window === 'RECENT_50' ? 11 : 467,
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

beforeEach(() => {
  fetchMock = vi.fn<typeof fetch>().mockImplementation((input) => {
    const url = new URL(String(input), 'http://localhost')
    if (url.pathname.includes('/b649-multi-ticket-records/summary')) {
      return Promise.resolve(apiResponse(mockB649Summary()))
    }
    if (url.pathname.includes('/b649-multi-ticket-records')) {
      return Promise.resolve(apiResponse(mockB649RecordsPage(url)))
    }
    if (url.pathname.includes('/p638-historical/runs')) {
      return Promise.resolve(apiResponse({ error_code: 'P638_HISTORICAL_NOT_CONFIGURED', message: 'Not configured' }, 503))
    }
    if (url.pathname.includes('/t539-historical/runs')) {
      return Promise.resolve(apiResponse({ error_code: 'T539_HISTORICAL_NOT_CONFIGURED', message: 'Not configured' }, 503))
    }
    return Promise.resolve(apiResponse({}))
  })
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => vi.unstubAllGlobals())

describe('BestReplayPage Workspace', () => {
  it('mounts cleanly with SectionHeader, Summary Metrics Cards, and English-only copy', async () => {
    const wrapper = mount(BestReplayPage)
    await flushPromises()

    expect(wrapper.find('#best-replay-title h2').text()).toBe('Best Replay')
    expect(wrapper.text()).toContain('Multi-ticket horizon ranking')
    expect(wrapper.text()).toContain('Best Strategy')
    expect(wrapper.text()).toContain('Ticket Count')
    expect(wrapper.text()).toContain('Horizon')
    expect(wrapper.text()).toContain('Historical Hit Rate')
    expect(wrapper.text()).toContain('Evidence Guard')

    // CJK Audit: verify 0 CJK characters in visible text
    const visibleText = wrapper.text()
    const cjkMatches = visibleText.match(/[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]/g)
    expect(cjkMatches).toBeNull()

    wrapper.unmount()
  })

  it('renders ticket count controls 1..20 with quick presets', async () => {
    const wrapper = mount(BestReplayPage)
    await flushPromises()

    const chips = wrapper.findAll('.ticket-chip')
    expect(chips.length).toBe(20)

    // B649 available counts: 5, 10, 15, 20
    const availableChips = wrapper.findAll('.ticket-chip--available')
    expect(availableChips.length).toBe(B649_AVAILABLE_TICKET_COUNTS.length)

    const unavailableChips = wrapper.findAll('.ticket-chip--unavailable')
    expect(unavailableChips.length).toBe(ALL_TICKET_COUNTS.length - B649_AVAILABLE_TICKET_COUNTS.length)

    // Test quick presets
    const presetButtons = wrapper.findAll('.preset-buttons button')
    expect(presetButtons.length).toBe(7) // 1, 2, 3, 5, 10, 20, All Available

    // Click 10T preset
    await presetButtons.find((btn) => btn.text() === '10T')?.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('10 Tickets')

    wrapper.unmount()
  })

  it('distinguishes unavailable ticket counts explicitly without converting to zero', async () => {
    const wrapper = mount(BestReplayPage)
    await flushPromises()

    // Select ticket count 3 (unavailable in B649 canonical data)
    const chip3 = wrapper.findAll('.ticket-chip').find((c) => c.text().includes('3'))
    await chip3?.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('EVIDENCE UNAVAILABLE')
    expect(wrapper.text()).toContain('No canonical multi-ticket backtest evidence is recorded for ticket count 3')
    expect(wrapper.text()).toContain('Unavailable')

    // Confirm it does NOT show 0.00% hit rate
    const hitRateCells = wrapper.findAll('.font-mono')
    const hitRates = hitRateCells.map((c) => c.text())
    expect(hitRates.some((t) => t === '0.00%')).toBe(false)

    wrapper.unmount()
  })

  it('switches evaluation horizons between Short, Medium, Long, and Full', async () => {
    const wrapper = mount(BestReplayPage)
    await flushPromises()

    const horizonSelect = wrapper.find('#horizon-select')
    expect(horizonSelect.exists()).toBe(true)

    // Switch to Short · 50
    await horizonSelect.setValue('RECENT_50')
    await flushPromises()

    expect(wrapper.text()).toContain('Short · 50')
    expect(wrapper.text()).toContain('LOW POWER')

    wrapper.unmount()
  })

  it('switches view mode between Ranking Table, Horizon Comparison, and 1-20 Matrix', async () => {
    const wrapper = mount(BestReplayPage)
    await flushPromises()

    const tabs = wrapper.findAll('.view-mode-tabs button')
    expect(tabs.length).toBe(3)

    // Switch to Horizon Comparison
    await tabs[1]?.trigger('click')
    await flushPromises()
    expect(wrapper.find('[data-testid="horizon-comparison"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('All Candidate Strategies')

    // Switch to 1-20 Matrix
    await tabs[2]?.trigger('click')
    await flushPromises()
    expect(wrapper.find('[data-testid="best-replay-matrix"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Heatmap Intensity')

    wrapper.unmount()
  })

  it('contains zero forbidden predictive words', async () => {
    const wrapper = mount(BestReplayPage)
    await flushPromises()

    const text = wrapper.text().toLowerCase()
    expect(text.includes('recommended winning strategy')).toBe(false)
    expect(text.includes('best future bet')).toBe(false)
    expect(text.includes('guaranteed')).toBe(false)
    expect(text.includes('high chance to win')).toBe(false)

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
