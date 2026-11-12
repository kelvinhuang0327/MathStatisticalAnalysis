// @vitest-environment jsdom

import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { B649MultiTicketRecord } from '../src/api/b649MultiTicketRecords'
import type { B649CanonicalForecast } from '../src/api/b649CanonicalForecast'
import type { RankingRow } from '../src/api/rankingMatrix'
import App from '../src/App.vue'
import B649CurrentForecastPage from '../src/features/b649-current-forecast/B649CurrentForecastPage.vue'
import StrategyForecastResearchPage from '../src/features/strategy-forecast-research/StrategyForecastResearchPage.vue'
import {
  fetchStrategyResearchRows,
  formatActualRateForDisplay,
  hasValidBaselineComparison,
  isAboveRandomBaseline,
  toStrategyResearchRows,
  type StrategyResearchRow,
} from '../src/features/strategy-forecast-research/model'

const api = vi.hoisted(() => ({
  fetchRankingData: vi.fn(),
  fetchB649MultiTicketRecords: vi.fn(),
  fetchB649CanonicalForecast: vi.fn(),
}))

vi.mock('../src/api/rankingMatrix', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../src/api/rankingMatrix')>()
  return { ...actual, fetchRankingData: api.fetchRankingData }
})

vi.mock('../src/api/b649MultiTicketRecords', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../src/api/b649MultiTicketRecords')>()
  return { ...actual, fetchB649MultiTicketRecords: api.fetchB649MultiTicketRecords }
})

vi.mock('../src/api/b649CanonicalForecast', () => ({
  fetchB649CanonicalForecast: api.fetchB649CanonicalForecast,
}))

function rankingRow(overrides: Partial<RankingRow> = {}): RankingRow {
  return {
    lotteryType: 'BIG_LOTTO',
    ticketCount: 5,
    window: 'FULL',
    officialRank: 7,
    strategyId: 'strat_alpha',
    displayName: 'Alpha Strategy',
    strategyVersion: 'v1.2.0',
    methodFamily: 'statistical',
    lifecycleStatus: 'BACKTESTED',
    successes: 12,
    observations: 100,
    officialAnyPrizeRate: 0.12,
    officialAnyPrizeRateFormatted: '12.00%',
    coverage: 0.92,
    coverageFormatted: '92.00%',
    baselineRate: 0.1,
    baselineRateFormatted: '10.00%',
    baselineDelta: 0.02,
    baselineDeltaFormatted: '+2.00%',
    bestOfficialPrize: '無中獎',
    comparabilityStatus: 'COMPARABLE',
    comparabilityLabel: '可正常比較',
    warningCodes: [],
    isAvailable: true,
    unrankedReason: null,
    ...overrides,
  } as RankingRow
}

function multiRecord(overrides: Partial<B649MultiTicketRecord> = {}): B649MultiTicketRecord {
  return {
    strategy_id: 'strat_m3',
    strategy_version: 'm3-v1',
    legacy_method_id: 'Legacy M3 method',
    source_path: 'legacy/m3.py',
    method_family: 'statistical',
    reproduction_status: 'BACKTESTED',
    duplicate_alias_target: null,
    prefix_count: 15,
    window: 'FULL',
    criterion: 'M3_PLUS',
    rank: 4,
    official_rank: 4,
    official_any_prize_count: 99,
    official_any_prize_rate: '0.900000000000000000',
    official_random_baseline_probability: '0.800000000000000000',
    official_random_baseline_delta: '0.100000000000000000',
    unranked_reason: null,
    success_count: 3,
    effective_backtest_draw_count: 12,
    successful_execution_count: 12,
    historical_success_rate: '0.250000000000000000',
    random_baseline_success_rate: '0.200000000000000000',
    random_baseline_rate_difference: '0.050000000000000000',
    coverage: '0.750000000000000000',
    window_available_draws: 12,
    window_requested_draws: 12,
    window_complete: true,
    official_prize_counts: null,
    no_prize_count: null,
    report_sha256: null,
    report_file_sha256: null,
    catalog_sha256: 'c'.repeat(64),
    authority_mode: null,
    metrics_unavailable_reason: null,
    ...overrides,
  } as B649MultiTicketRecord
}

function recordPage(
  items: B649MultiTicketRecord[],
  window = 'FULL',
  total = items.length,
  offset = 0,
) {
  return {
    items,
    total,
    limit: 100,
    offset,
    prefix_count: 15,
    window,
    criterion: 'M3_PLUS',
    research_disclaimer: 'descriptive',
  }
}

function strategyResearchRow(overrides: Partial<StrategyResearchRow> = {}): StrategyResearchRow {
  return {
    ...toStrategyResearchRows([rankingRow()], 5, 'FULL')[0],
    ...overrides,
  }
}

function tickets(count: number) {
  return Array.from({ length: count }, (_, index) => ({
    ticket_position: index + 1,
    predicted_numbers: [index + 1, index + 11, index + 21],
  }))
}

function forecast(): B649CanonicalForecast {
  return {
    status: 'AVAILABLE',
    authority: 'SCHEDULER_ARTIFACT',
    current_target: {
      draw_number: '115000099',
      draw_date: '2026-10-03',
      scheduled_at: '2026-10-03T20:30:00+08:00',
    },
    consensus_numbers: [4, 12, 23, 26, 29],
    source_stream_count: 11,
    k5_tickets: tickets(5),
    k10_tickets: tickets(10),
    k20_tickets: tickets(20),
    forecast_actual_sha256: 'a'.repeat(64),
    forecast_method_id: 'B649_TEST_CONSENSUS',
    forecast_method_version: '1.0.0',
    portfolio_actual_sha256: 'b'.repeat(64),
    portfolio_method_id: 'B649_TEST_PORTFOLIO',
    portfolio_method_version: '2.0.0',
  }
}

beforeEach(() => {
  api.fetchRankingData.mockReset().mockResolvedValue([rankingRow()])
  api.fetchB649MultiTicketRecords.mockReset().mockResolvedValue(recordPage([]))
  api.fetchB649CanonicalForecast.mockReset().mockResolvedValue(forecast())
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('StrategyForecastResearchPage', () => {
  it('offers all supported B649 K values and keeps the selected K group distinct', async () => {
    api.fetchRankingData.mockImplementation((_lottery, ticketCount, windowKey) =>
      Promise.resolve([rankingRow({ ticketCount, window: windowKey })]),
    )
    const wrapper = mount(StrategyForecastResearchPage)
    await flushPromises()
    expect(wrapper.get('select[aria-label="票券數 K"]').findAll('option').map((option) => option.text()))
      .toEqual(['K2', 'K3', 'K5', 'K10', 'K15', 'K20'])

    for (const k of [2, 3, 10, 20] as const) {
      await wrapper.get('select[aria-label="票券數 K"]').setValue(String(k))
      await flushPromises()
      expect(api.fetchRankingData).toHaveBeenLastCalledWith('BIG_LOTTO', k, 'FULL', expect.any(AbortSignal))
      expect(wrapper.get('table').attributes('data-k')).toBe(String(k))
    }
    wrapper.unmount()
  })

  it('uses the exact K15 M3_PLUS source and preserves its criterion-specific success and baseline values', async () => {
    api.fetchB649MultiTicketRecords.mockResolvedValue(recordPage([multiRecord()]))
    const wrapper = mount(StrategyForecastResearchPage)
    await flushPromises()
    await wrapper.get('select[aria-label="票券數 K"]').setValue('15')
    await flushPromises()

    expect(api.fetchB649MultiTicketRecords).toHaveBeenLastCalledWith(
      { prefixCount: 15, window: 'FULL', criterion: 'M3_PLUS', limit: 100, offset: 0 },
      expect.any(AbortSignal),
    )
    const row = wrapper.get('[data-testid="history-row-strat_m3"]')
    expect(row.text()).toContain('M3_PLUS')
    expect(row.text()).toContain('3 / 12')
    expect(row.text()).toContain('25.00%')
    expect(row.text()).toContain('20.00%')
    expect(row.text()).toContain('+5.00%')
    expect(row.text()).not.toContain('90.00%')
    expect(row.text()).not.toContain('+10.00%')
    wrapper.unmount()
  })

  it('uses successful execution count rather than the effective ratio denominator for K15 M3_PLUS', async () => {
    api.fetchB649MultiTicketRecords.mockResolvedValue(recordPage([
      multiRecord({
        success_count: 9,
        effective_backtest_draw_count: 16,
        successful_execution_count: 48,
        historical_success_rate: '0.187500000000000000',
        random_baseline_success_rate: '0.170000000000000000',
        random_baseline_rate_difference: '0.017500000000000000',
      }),
    ]))
    const wrapper = mount(StrategyForecastResearchPage)
    await flushPromises()
    await wrapper.get('select[aria-label="票券數 K"]').setValue('15')
    await flushPromises()

    const row = wrapper.get('[data-testid="history-row-strat_m3"]')
    expect(row.text()).toContain('9 / 48')
    expect(row.text()).not.toContain('9 / 16')
    expect(row.text()).toContain('18.75%')
    expect(row.text()).toContain('17.00%')
    expect(row.text()).toContain('+1.75%')
    wrapper.unmount()
  })

  it('rejects K15 source metrics explicitly marked unavailable', async () => {
    api.fetchB649MultiTicketRecords.mockResolvedValue(recordPage([
      multiRecord({ metrics_unavailable_reason: 'METRICS_UNAVAILABLE', random_baseline_rate_difference: '0.05' }),
    ]))
    const [row] = await fetchStrategyResearchRows(15, 'FULL')

    expect(row?.eventCriterion).toBe('M3_PLUS')
    expect(row?.warningCodes).toContain('METRICS_UNAVAILABLE')
    expect(row?.isAvailable).toBe(false)
    expect(isAboveRandomBaseline(row!)).toBe(false)
  })

  it('loads every K15 source page and retains every matching strategy', async () => {
    const first = multiRecord({ strategy_id: 'm3_first' })
    const second = multiRecord({ strategy_id: 'm3_second', official_rank: 9 })
    api.fetchB649MultiTicketRecords
      .mockResolvedValueOnce(recordPage([first], 'FULL', 2, 0))
      .mockResolvedValueOnce(recordPage([second], 'FULL', 2, 1))
    const wrapper = mount(StrategyForecastResearchPage)
    await flushPromises()
    await wrapper.get('select[aria-label="票券數 K"]').setValue('15')
    await flushPromises()

    expect(api.fetchB649MultiTicketRecords).toHaveBeenNthCalledWith(
      1,
      { prefixCount: 15, window: 'FULL', criterion: 'M3_PLUS', limit: 100, offset: 0 },
      expect.any(AbortSignal),
    )
    expect(api.fetchB649MultiTicketRecords).toHaveBeenNthCalledWith(
      2,
      { prefixCount: 15, window: 'FULL', criterion: 'M3_PLUS', limit: 100, offset: 1 },
      expect.any(AbortSignal),
    )
    expect(wrapper.findAll('tbody tr')).toHaveLength(2)
    expect(wrapper.find('[data-testid="history-row-m3_first"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="history-row-m3_second"]').exists()).toBe(true)
    wrapper.unmount()
  })

  it('keeps FULL, RECENT_750, RECENT_300, and RECENT_50 results separate and clears stale rows', async () => {
    let resolveRecent!: (rows: RankingRow[]) => void
    api.fetchRankingData.mockImplementation((_lottery, _k, window) => {
      if (window === 'FULL') return Promise.resolve([rankingRow({ strategyId: 'full_only' })])
      if (window === 'RECENT_750') return Promise.resolve([rankingRow({ window, strategyId: 'recent_750' })])
      if (window === 'RECENT_300') return new Promise((resolve) => { resolveRecent = resolve })
      return Promise.resolve([rankingRow({ window, strategyId: 'recent_50' })])
    })
    const wrapper = mount(StrategyForecastResearchPage)
    await flushPromises()
    expect(wrapper.text()).toContain('full_only')

    await wrapper.get('select[aria-label="歷史窗口"]').setValue('RECENT_750')
    await flushPromises()
    expect(wrapper.text()).toContain('recent_750')
    expect(wrapper.text()).not.toContain('full_only')

    await wrapper.get('select[aria-label="歷史窗口"]').setValue('RECENT_300')
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).not.toContain('recent_750')
    expect(wrapper.get('[role="status"]').text()).toContain('RECENT_300')
    resolveRecent([rankingRow({ window: 'RECENT_300', strategyId: 'recent_300' })])
    await flushPromises()
    expect(wrapper.text()).toContain('recent_300')
    expect(wrapper.get('table').attributes('data-window')).toBe('RECENT_300')

    await wrapper.get('select[aria-label="歷史窗口"]').setValue('RECENT_50')
    await flushPromises()
    expect(wrapper.text()).toContain('recent_50')
    expect(wrapper.text()).not.toContain('recent_300')
    wrapper.unmount()
  })

  it('finds every valid positive delta strategy without truncating the result list', async () => {
    const rows = Array.from({ length: 135 }, (_, index) => rankingRow({
      strategyId: `positive_${index}`,
      officialRank: 135 - index,
      baselineDelta: 0.001,
    }))
    rows.push(rankingRow({ strategyId: 'missing_baseline', baselineRate: null, baselineDelta: 0.5 }))
    rows.push(rankingRow({ strategyId: 'missing_actual', officialAnyPrizeRate: null, baselineDelta: 0.5 }))
    api.fetchRankingData.mockResolvedValue(rows)
    const wrapper = mount(StrategyForecastResearchPage)
    await flushPromises()
    await wrapper.get('input[type="checkbox"]').setValue(true)
    await flushPromises()

    expect(wrapper.findAll('tbody tr')).toHaveLength(135)
    expect(wrapper.get('[data-testid="history-row-positive_134"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="history-row-missing_baseline"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="history-row-missing_actual"]').exists()).toBe(false)
    wrapper.unmount()
  })

  it('does not count a positive delta as above baseline when either rate or baseline is missing', async () => {
    const rows = [
      rankingRow({ strategyId: 'valid', baselineDelta: 0.01 }),
      rankingRow({ strategyId: 'no_baseline', baselineRate: null, baselineDelta: 0.5 }),
      rankingRow({ strategyId: 'no_actual', officialAnyPrizeRate: null, baselineDelta: 0.5 }),
      rankingRow({ strategyId: 'no_delta', baselineDelta: null }),
    ]
    api.fetchRankingData.mockResolvedValue(rows)
    const wrapper = mount(StrategyForecastResearchPage)
    await flushPromises()
    await wrapper.get('input[type="checkbox"]').setValue(true)
    await flushPromises()

    expect(wrapper.findAll('tbody tr').map((row) => row.attributes('data-testid')))
      .toEqual(['history-row-valid'])
    wrapper.unmount()
  })

  it.each([
    ['a missing denominator', { denominator: null }],
    ['an undefined denominator', { denominator: undefined as unknown as null }],
    ['a zero denominator', { denominator: 0 }],
    ['a negative denominator', { denominator: -1 }],
    ['a fractional denominator', { denominator: 1.5 }],
    ['a NaN denominator', { denominator: Number.NaN }],
    ['an infinite denominator', { denominator: Number.POSITIVE_INFINITY }],
    ['a missing numerator', { numerator: null }],
    ['an undefined numerator', { numerator: undefined as unknown as null }],
    ['a negative numerator', { numerator: -1 }],
    ['a fractional numerator', { numerator: 1.5 }],
    ['a numerator above the denominator', { numerator: 101 }],
    ['an unavailable source', { isAvailable: false }],
    ['a non-comparable source', { comparabilityStatus: 'NOT_HISTORICALLY_COMPARABLE' }],
    ['an unavailable comparability status', { comparabilityStatus: 'UNAVAILABLE' }],
    ['an insufficient window', { comparabilityStatus: 'INSUFFICIENT_WINDOW' }],
    ['a missing actual rate', { actualRate: null }],
    ['a non-finite actual rate', { actualRate: Number.POSITIVE_INFINITY }],
    ['an out-of-range actual rate', { actualRate: 1.01 }],
    ['a missing baseline rate', { baselineRate: null }],
    ['a non-finite baseline rate', { baselineRate: Number.NaN }],
    ['an out-of-range baseline rate', { baselineRate: -0.01 }],
    ['a missing baseline delta', { baselineDelta: null }],
    ['a non-finite baseline delta', { baselineDelta: Number.POSITIVE_INFINITY }],
    ['a zero delta', { baselineDelta: 0 }],
    ['a negative delta', { baselineDelta: -0.01 }],
    ['a mismatched event identity', { eventCriterion: 'M3_PLUS' }],
  ])('does not include %s as a positive baseline comparison', (_case, overrides) => {
    expect(isAboveRandomBaseline(strategyResearchRow(overrides))).toBe(false)
  })

  it('accepts a complete positive delta while keeping K15 M3_PLUS event identity distinct', () => {
    const completePositiveDelta = strategyResearchRow({ baselineDelta: 0.01 })
    expect(hasValidBaselineComparison(completePositiveDelta)).toBe(true)
    expect(isAboveRandomBaseline(completePositiveDelta)).toBe(true)

    expect(isAboveRandomBaseline({
      ...completePositiveDelta,
      ticketCount: 15,
      eventCriterion: 'M3_PLUS',
    })).toBe(true)
    expect(isAboveRandomBaseline({
      ...completePositiveDelta,
      ticketCount: 15,
      eventCriterion: 'OFFICIAL_ANY_PRIZE',
    })).toBe(false)
    expect(isAboveRandomBaseline({
      ...completePositiveDelta,
      eventCriterion: 'M3_PLUS',
    })).toBe(false)
  })

  it('keeps a missing source numerator visible and excludes it from positive-delta results', async () => {
    api.fetchRankingData.mockResolvedValue([
      rankingRow({ strategyId: 'missing_numerator', successes: null, baselineDelta: 0.5 }),
    ])
    const wrapper = mount(StrategyForecastResearchPage)
    await flushPromises()
    const row = wrapper.get('[data-testid="history-row-missing_numerator"]')
    expect(row.text()).toContain('不可用 / 100')
    expect(row.text()).toContain('未構成有效基準比較')

    await wrapper.get('input[type="checkbox"]').setValue(true)
    await flushPromises()
    expect(wrapper.find('[data-testid="history-row-missing_numerator"]').exists()).toBe(false)
    wrapper.unmount()
  })

  it('shows a 0/0 rate as unavailable and does not treat it as above baseline', () => {
    const row = toStrategyResearchRows([
      rankingRow({ strategyId: 'zero-zero', successes: 0, observations: 0, officialAnyPrizeRate: 0.5, baselineDelta: 0.4 }),
    ], 5, 'FULL')[0]
    expect(formatActualRateForDisplay(row)).toBe('不可用（0 / 0）')
    expect(isAboveRandomBaseline(row)).toBe(false)
  })

  it('preserves a true 0 percent rate when the denominator is greater than zero', async () => {
    api.fetchRankingData.mockResolvedValue([
      rankingRow({ strategyId: 'zero-of-fifty', successes: 0, observations: 50, officialAnyPrizeRate: 0, baselineRate: 0.02, baselineDelta: -0.02 }),
    ])
    const wrapper = mount(StrategyForecastResearchPage)
    await flushPromises()
    const row = wrapper.get('[data-testid="history-row-zero-of-fifty"]')
    expect(row.text()).toContain('0.00%')
    expect(row.text()).toContain('0 / 50')
    wrapper.unmount()
  })

  it('keeps strategy IDs and versions bound as a single displayed identity', async () => {
    api.fetchRankingData.mockResolvedValue([
      rankingRow({ strategyId: 'same-strategy', strategyVersion: 'v1' }),
      rankingRow({ strategyId: 'same-strategy', strategyVersion: 'v2' }),
    ])
    const wrapper = mount(StrategyForecastResearchPage)
    await flushPromises()
    const rows = wrapper.findAll('[data-testid="history-row-same-strategy"]')
    expect(rows).toHaveLength(2)
    expect(rows[0]?.text()).toContain('same-strategy')
    expect(rows[0]?.text()).toContain('版本 v1')
    expect(rows[1]?.text()).toContain('版本 v2')
    await rows[1]?.get('button').trigger('click')
    expect(wrapper.get('.selected-identity').text()).toContain('版本 v2')
    wrapper.unmount()
  })

  it('preserves source rank values and source order without ranking rows again', () => {
    const rows = toStrategyResearchRows([
      rankingRow({ strategyId: 'source_first', officialRank: 9 }),
      rankingRow({ strategyId: 'source_second', officialRank: 2 }),
    ], 5, 'FULL')
    expect(rows.map((row) => [row.strategyId, row.officialRank])).toEqual([
      ['source_first', 9],
      ['source_second', 2],
    ])
  })

  it('shows low coverage and source warnings explicitly', async () => {
    api.fetchRankingData.mockResolvedValue([
      rankingRow({
        strategyId: 'low_coverage',
        coverage: 0.04,
        baselineDelta: 0.01,
        warningCodes: ['HIGH_RANK_LOW_COVERAGE'],
      }),
    ])
    const wrapper = mount(StrategyForecastResearchPage)
    await flushPromises()
    await wrapper.get('input[type="checkbox"]').setValue(true)
    await flushPromises()
    const row = wrapper.get('[data-testid="history-row-low_coverage"]')
    expect(row.text()).toContain('低覆蓋率')
    expect(row.text()).toContain('來源警示：高排名但覆蓋率低')
    wrapper.unmount()
  })

  it('retains the low-sample warning for a valid descriptive positive delta', async () => {
    api.fetchRankingData.mockResolvedValue([
      rankingRow({
        strategyId: 'low_sample_positive',
        observations: 10,
        successes: 2,
        comparabilityStatus: 'LOW_SAMPLE_SIZE',
        comparabilityLabel: '低樣本數',
        warningCodes: ['LOW_SAMPLE_SIZE'],
        baselineDelta: 0.01,
      }),
    ])
    const wrapper = mount(StrategyForecastResearchPage)
    await flushPromises()
    await wrapper.get('input[type="checkbox"]').setValue(true)
    await flushPromises()
    const row = wrapper.get('[data-testid="history-row-low_sample_positive"]')
    expect(row.text()).toContain('低樣本數')
    expect(row.text()).toContain('2 / 10')
    wrapper.unmount()
  })

  it('does not claim formal OOS evidence or predictive lift from the history endpoint', async () => {
    const wrapper = mount(StrategyForecastResearchPage)
    await flushPromises()
    expect(wrapper.get('[data-testid="history-row-strat_alpha"]').text())
      .toContain('此歷史來源未提供；不宣稱預測優勢')
    expect(wrapper.text()).toContain('不代表統計顯著、未來增益或策略適用性')
    wrapper.unmount()
  })

  it('clears old consensus tickets after a current forecast API error', async () => {
    api.fetchB649CanonicalForecast
      .mockResolvedValueOnce(forecast())
      .mockRejectedValueOnce(Object.assign(new Error('HTTP 503'), { status: 503 }))
    const wrapper = mount(StrategyForecastResearchPage)
    await flushPromises()
    expect(wrapper.text()).toContain('115000099')
    expect(wrapper.findAll('.ticket-group li')).toHaveLength(35)

    await wrapper.get('.consensus-panel .quiet-button').trigger('click')
    await flushPromises()
    expect(wrapper.get('.consensus-panel [role="alert"]').text()).toContain('目前預測不可用')
    expect(wrapper.get('.consensus-panel [role="alert"]').text()).toContain('不顯示任何舊票券')
    expect(wrapper.findAll('.ticket-group li')).toHaveLength(0)
    expect(wrapper.text()).not.toContain('115000099')
    wrapper.unmount()
  })

  it('keeps consensus tickets separate from a selected strategy forecast', async () => {
    const wrapper = mount(StrategyForecastResearchPage)
    await flushPromises()
    await wrapper.get('[data-testid="history-row-strat_alpha"] button').trigger('click')
    expect(wrapper.get('.strategy-linkage').text()).toContain('strat_alpha')
    expect(wrapper.get('.strategy-linkage').text()).toContain('PER_STRATEGY_FORECAST_NOT_AVAILABLE')
    expect(wrapper.get('.strategy-linkage').text()).not.toContain('票券 1')
    expect(wrapper.get('.consensus-panel').text()).toContain('CURRENT_CONSENSUS_FORECAST')
    expect(wrapper.get('.consensus-panel').text()).toContain('NOT_PER_STRATEGY_FORECAST')
    expect(wrapper.get('.consensus-panel').text()).toContain('B649_TEST_CONSENSUS')
    wrapper.unmount()
  })

  it('distinguishes a normal empty response from a history API error', async () => {
    api.fetchRankingData.mockResolvedValueOnce([]).mockRejectedValueOnce(new Error('offline'))
    const wrapper = mount(StrategyForecastResearchPage)
    await flushPromises()
    expect(wrapper.get('[role="status"]').text()).toContain('成功查詢後的空資料結果')
    expect(wrapper.find('[role="alert"]').exists()).toBe(false)

    await wrapper.get('.history-controls .quiet-button').trigger('click')
    await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toContain('歷史資料查詢失敗')
    expect(wrapper.find('[data-testid="history-row-strat_alpha"]').exists()).toBe(false)
    wrapper.unmount()
  })

  it('clears prior K and window data while the next query is pending', async () => {
    const pendingResolvers: Array<(rows: RankingRow[]) => void> = []
    api.fetchRankingData.mockImplementation((_lottery, ticketCount, window) => {
      if (ticketCount === 5 && window === 'FULL') {
        return Promise.resolve([rankingRow({ strategyId: 'old_group' })])
      }
      return new Promise((resolve) => { pendingResolvers.push(resolve) })
    })
    const wrapper = mount(StrategyForecastResearchPage)
    await flushPromises()
    expect(wrapper.text()).toContain('old_group')

    await wrapper.get('select[aria-label="票券數 K"]').setValue('10')
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).not.toContain('old_group')
    expect(wrapper.get('[role="status"]').text()).toContain('K10')
    await wrapper.get('select[aria-label="歷史窗口"]').setValue('RECENT_300')
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).not.toContain('old_group')
    pendingResolvers.at(-1)?.([rankingRow({ ticketCount: 10, window: 'RECENT_300', strategyId: 'new_group' })])
    await flushPromises()
    expect(wrapper.text()).toContain('new_group')
    expect(wrapper.get('table').attributes()).toMatchObject({ 'data-k': '10', 'data-window': 'RECENT_300' })
    wrapper.unmount()
  })

  it('leaves the existing B649 Current Forecast page behavior and route intact', async () => {
    window.location.hash = '#/b649-current-forecast'
    const wrapper = mount(App)
    await flushPromises()
    expect(wrapper.get('h1').text()).toBe('B649 目前預測')
    expect(wrapper.get('a[href="#/b649-current-forecast"]').attributes('aria-current')).toBe('page')
    wrapper.unmount()

    const existingPage = mount(B649CurrentForecastPage)
    await flushPromises()
    expect(existingPage.text()).toContain('B649 目前預測')
    expect(existingPage.text()).toContain('B649_TEST_CONSENSUS')
    expect(existingPage.findAll('[data-testid="b649-ticket-k5"]')).toHaveLength(5)
    existingPage.unmount()
  })

  it('opens from App navigation at the requested hash route', async () => {
    window.location.hash = '#/strategy-forecast-research'
    const wrapper = mount(App)
    await flushPromises()
    expect(wrapper.get('h1').text()).toBe('策略歷史表現與目前預測')
    expect(wrapper.get('a[href="#/strategy-forecast-research"]').attributes('aria-current')).toBe('page')
    expect(wrapper.get('a[href="#/b649-current-forecast"]').attributes('aria-current')).toBeUndefined()
    wrapper.unmount()
  })
})
