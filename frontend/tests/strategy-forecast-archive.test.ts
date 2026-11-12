// @vitest-environment jsdom

import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('../src/api/b649MultiTicketRecords', () => ({
  fetchB649MultiTicketRecords: vi.fn(),
  fetchB649MultiTicketSummary: vi.fn(),
}))

import {
  fetchB649MultiTicketRecords,
  fetchB649MultiTicketSummary,
  type B649MultiTicketRecord,
  type B649MultiTicketRecordPage,
  type B649MultiTicketSummary,
} from '../src/api/b649MultiTicketRecords'
import FullStrategyBacktestArchive from '../src/features/strategy-forecast-research/FullStrategyBacktestArchive.vue'
import {
  classifyFullStrategyArchivePerformance,
  fetchFullStrategyBacktestArchive,
  filterFullStrategyArchiveRecords,
  getFullStrategyArchiveMetrics,
  isFullStrategyArchiveLowCoverage,
  isFullStrategyArchiveLowSample,
} from '../src/features/strategy-forecast-research/fullStrategyArchive'

const HASH_A = 'a'.repeat(64)
const HASH_B = 'b'.repeat(64)
const HASH_C = 'c'.repeat(64)
const DISCLAIMER = '歷史成功率、排名與隨機基準差異僅供描述性研究，不構成未來預測、推薦、上線決策或中獎保證。'

function record(overrides: Partial<B649MultiTicketRecord> = {}): B649MultiTicketRecord {
  return {
    strategy_id: 'strategy-positive',
    strategy_version: 'v1',
    legacy_method_id: 'legacy-positive',
    source_path: 'legacy/strategy.py',
    method_family: 'fixture-family',
    reproduction_status: 'BACKTESTED',
    duplicate_alias_target: null,
    prefix_count: 15,
    window: 'FULL',
    criterion: 'M3_PLUS',
    rank: 1,
    official_rank: null,
    official_any_prize_count: 9,
    official_any_prize_rate: '0.90',
    official_random_baseline_probability: '0.10',
    official_random_baseline_delta: '0.80',
    unranked_reason: null,
    success_count: 2,
    effective_backtest_draw_count: 1,
    successful_execution_count: 10,
    historical_success_rate: '0.20',
    random_baseline_success_rate: '0.15',
    random_baseline_rate_difference: '0.05',
    coverage: '0.50',
    window_available_draws: 20,
    window_requested_draws: 20,
    window_complete: true,
    official_prize_counts: null,
    no_prize_count: null,
    report_sha256: HASH_A,
    report_file_sha256: HASH_B,
    catalog_sha256: HASH_C,
    authority_mode: 'FIXTURE_SOURCE',
    metrics_unavailable_reason: null,
    ...overrides,
  }
}

function summaryFor(input: {
  total: number
  backtested: number
  closed: number
  aliases: number
}): B649MultiTicketSummary {
  return {
    progress: {
      total_strategy_count: input.total,
      reproduced_count: input.backtested,
      backtested_count: input.backtested,
      closed_count: input.closed,
      duplicate_alias_count: input.aliases,
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
    method_families: ['fixture-family'],
    reproduction_statuses: ['BACKTESTED', 'CLOSED_UNEXECUTABLE', 'DUPLICATE_ALIAS'],
    catalog_sha256: HASH_C,
    records_available: true,
    projection_sha256: HASH_B,
    source_report_count: input.backtested,
    metrics_available_strategy_count: input.backtested,
    metrics_unavailable_strategy_count: 0,
    primary_ranking_criterion: 'OFFICIAL_ANY_PRIZE',
    research_disclaimer: DISCLAIMER,
  }
}

function page(
  items: B649MultiTicketRecord[],
  total: number,
  offset: number,
): B649MultiTicketRecordPage {
  return {
    items,
    total,
    limit: 100,
    offset,
    prefix_count: 15,
    window: 'FULL',
    criterion: 'M3_PLUS',
    research_disclaimer: DISCLAIMER,
  }
}

function statusRecords() {
  return [
    record({ strategy_id: 'positive' }),
    record({
      strategy_id: 'zero',
      historical_success_rate: '0.15',
      random_baseline_rate_difference: '0',
      random_baseline_success_rate: '0.15',
    }),
    record({
      strategy_id: 'negative',
      historical_success_rate: '0.10',
      random_baseline_rate_difference: '-0.05',
      random_baseline_success_rate: '0.15',
      official_random_baseline_delta: '0.99',
    }),
    record({
      strategy_id: 'closed',
      reproduction_status: 'CLOSED_UNEXECUTABLE',
      success_count: null,
      successful_execution_count: null,
      historical_success_rate: null,
      random_baseline_success_rate: null,
      random_baseline_rate_difference: null,
      metrics_unavailable_reason: null,
      unranked_reason: 'CLOSED_UNEXECUTABLE:FIXTURE_REASON',
      report_sha256: null,
      report_file_sha256: null,
      authority_mode: null,
    }),
    record({
      strategy_id: 'alias',
      reproduction_status: 'DUPLICATE_ALIAS',
      duplicate_alias_target: 'strategy-positive@v1',
      success_count: null,
      successful_execution_count: null,
      historical_success_rate: null,
      random_baseline_success_rate: null,
      random_baseline_rate_difference: null,
      metrics_unavailable_reason: null,
      unranked_reason: 'DUPLICATE_ALIAS',
      report_sha256: null,
      report_file_sha256: null,
      authority_mode: null,
    }),
    record({
      strategy_id: 'unavailable',
      metrics_unavailable_reason: 'FROZEN_PREDICTION_OUTPUT_AND_PRODUCER_UNAVAILABLE',
      success_count: null,
      successful_execution_count: null,
      historical_success_rate: null,
      random_baseline_success_rate: null,
      random_baseline_rate_difference: null,
    }),
  ]
}

describe('FullStrategyBacktestArchive', () => {
  beforeEach(() => {
    vi.mocked(fetchB649MultiTicketRecords).mockReset()
    vi.mocked(fetchB649MultiTicketSummary).mockReset()
  })

  it('loads every page in the fixed B649 K15 FULL M3_PLUS source and preserves source order', async () => {
    const records = Array.from({ length: 101 }, (_, index) =>
      record({ strategy_id: `strategy-${String(index).padStart(3, '0')}` }),
    )
    vi.mocked(fetchB649MultiTicketSummary).mockResolvedValue(
      summaryFor({ total: 101, backtested: 101, closed: 0, aliases: 0 }),
    )
    vi.mocked(fetchB649MultiTicketRecords)
      .mockResolvedValueOnce(page(records.slice(0, 100), 101, 0))
      .mockResolvedValueOnce(page(records.slice(100), 101, 100))

    const snapshot = await fetchFullStrategyBacktestArchive()

    expect(snapshot.total).toBe(101)
    expect(snapshot.records).toHaveLength(101)
    expect(snapshot.records[0]?.strategy_id).toBe('strategy-000')
    expect(snapshot.records[100]?.strategy_id).toBe('strategy-100')
    expect(fetchB649MultiTicketRecords).toHaveBeenNthCalledWith(
      1,
      { prefixCount: 15, window: 'FULL', criterion: 'M3_PLUS', limit: 100, offset: 0 },
      undefined,
    )
    expect(fetchB649MultiTicketRecords).toHaveBeenNthCalledWith(
      2,
      { prefixCount: 15, window: 'FULL', criterion: 'M3_PLUS', limit: 100, offset: 100 },
      undefined,
    )
  })

  it('keeps every status by default and filters status separately from descriptive performance', () => {
    const rows = statusRecords()
    expect(filterFullStrategyArchiveRecords(rows, 'ALL', 'ALL')).toHaveLength(rows.length)
    expect(filterFullStrategyArchiveRecords(rows, 'ALL', 'ABOVE_RANDOM').map((row) => row.strategy_id))
      .toEqual(['positive'])
    expect(filterFullStrategyArchiveRecords(rows, 'ALL', 'AT_RANDOM').map((row) => row.strategy_id))
      .toEqual(['zero'])
    expect(filterFullStrategyArchiveRecords(rows, 'ALL', 'BELOW_RANDOM').map((row) => row.strategy_id))
      .toEqual(['negative'])
    expect(filterFullStrategyArchiveRecords(rows, 'ALL', 'METRIC_UNAVAILABLE').map((row) => row.strategy_id))
      .toEqual(['closed', 'alias', 'unavailable'])
    expect(filterFullStrategyArchiveRecords(rows, 'CLOSED_UNEXECUTABLE', 'ALL').map((row) => row.strategy_id))
      .toEqual(['closed'])
  })

  it('uses the M3_PLUS source rate and raw successful execution denominator, not official-prize metrics', () => {
    const row = record({
      success_count: 425,
      effective_backtest_draw_count: 97,
      successful_execution_count: 1649,
      historical_success_rate: '0.257731958762886598',
      random_baseline_success_rate: '0.245878052137833005',
      random_baseline_rate_difference: '0.011853906625053593',
      official_random_baseline_delta: '-0.90',
    })

    expect(getFullStrategyArchiveMetrics(row)).toMatchObject({
      numerator: 425,
      denominator: 1649,
      effectiveBacktestDrawCount: 97,
      actualRate: 0.257731958762886598,
      delta: 0.011853906625053593,
    })
    expect(classifyFullStrategyArchivePerformance(row)).toBe('ABOVE_RANDOM')
  })

  it('treats 0/N as a real zero rate and 0/0 as unavailable', () => {
    const zeroOfTwenty = record({
      success_count: 0,
      successful_execution_count: 20,
      historical_success_rate: '0.000000000000000000',
      random_baseline_success_rate: '0.1',
      random_baseline_rate_difference: '-0.1',
    })
    const zeroOfZero = record({
      success_count: 0,
      successful_execution_count: 0,
      historical_success_rate: '0.000000000000000000',
      random_baseline_success_rate: '0.1',
      random_baseline_rate_difference: '-0.1',
    })

    expect(getFullStrategyArchiveMetrics(zeroOfTwenty)).toMatchObject({
      numerator: 0,
      denominator: 20,
      actualRate: 0,
    })
    expect(classifyFullStrategyArchivePerformance(zeroOfZero)).toBe('METRIC_UNAVAILABLE')
    expect(getFullStrategyArchiveMetrics(zeroOfZero)).toBeNull()
  })

  it('surfaces low sample and low coverage from their separate source fields', () => {
    const lowSampleLowCoverage = record({ successful_execution_count: 49, coverage: '0.04' })
    expect(isFullStrategyArchiveLowSample(lowSampleLowCoverage)).toBe(true)
    expect(isFullStrategyArchiveLowCoverage(lowSampleLowCoverage)).toBe(true)
    expect(isFullStrategyArchiveLowSample(record({ successful_execution_count: 50 }))).toBe(false)
    expect(isFullStrategyArchiveLowSample(record({ successful_execution_count: 0 }))).toBe(true)
  })

  it('distinguishes a successful empty response from an API error and clears stale rows when filters change', async () => {
    vi.mocked(fetchB649MultiTicketSummary).mockResolvedValue(
      summaryFor({ total: 0, backtested: 0, closed: 0, aliases: 0 }),
    )
    vi.mocked(fetchB649MultiTicketRecords).mockResolvedValue(page([], 0, 0))
    const emptyWrapper = mount(FullStrategyBacktestArchive)
    await flushPromises()
    expect(emptyWrapper.get('[role="status"]').text()).toContain('查詢成功')
    emptyWrapper.unmount()

    const rows = statusRecords()
    vi.mocked(fetchB649MultiTicketSummary).mockResolvedValue(
      summaryFor({ total: 6, backtested: 4, closed: 1, aliases: 1 }),
    )
    vi.mocked(fetchB649MultiTicketRecords).mockResolvedValue(page(rows, 6, 0))
    const wrapper = mount(FullStrategyBacktestArchive)
    await flushPromises()
    expect(wrapper.findAll('tbody tr')).toHaveLength(rows.length)

    await wrapper.get('select[aria-label="全策略回測狀態篩選"]').setValue('DUPLICATE_ALIAS')
    expect(wrapper.findAll('tbody tr')).toHaveLength(1)
    expect(wrapper.find('[data-testid="archive-row-alias"]').exists()).toBe(true)

    await wrapper.get('select[aria-label="全策略描述性表現篩選"]').setValue('BELOW_RANDOM')
    expect(wrapper.findAll('tbody tr')).toHaveLength(0)
    expect(wrapper.get('.archive-summary').text()).toContain('顯示 0 / 6')
    wrapper.unmount()
  })

  it('renders a failed API request as an error instead of an empty result', async () => {
    vi.mocked(fetchB649MultiTicketSummary).mockRejectedValue(new Error('summary unavailable'))
    const wrapper = mount(FullStrategyBacktestArchive)
    await flushPromises()

    expect(wrapper.get('.archive-state--error').text()).toContain('summary unavailable')
    expect(wrapper.find('[role="status"]').exists()).toBe(false)
    expect(fetchB649MultiTicketRecords).not.toHaveBeenCalled()
    wrapper.unmount()
  })
})
