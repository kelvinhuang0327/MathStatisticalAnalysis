// @vitest-environment jsdom

import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'

import ReplayOverviewPage from '../src/features/replay-overview/ReplayOverviewPage.vue'
import { transformB649Record } from '../src/api/replayOverview'

const researchDisclaimer =
  '歷史成功率、排名與隨機基準差異僅供描述性研究，不構成未來預測、推薦、上線決策或中獎保證。'

function makeRecord(overrides: Record<string, unknown> = {}) {
  return {
    strategy_id: 'fixture-a',
    strategy_version: 'v1',
    legacy_method_id: 'fixture',
    source_path: 'fixture',
    method_family: 'test',
    reproduction_status: 'BACKTESTED',
    duplicate_alias_target: null,
    prefix_count: 10,
    window: 'FULL',
    criterion: 'M3_PLUS',
    rank: 2,
    official_rank: 1,
    official_any_prize_count: 2,
    official_any_prize_rate: '0.200000000000000000',
    official_random_baseline_probability: '0.100000000000000000',
    official_random_baseline_delta: '0.100000000000000000',
    unranked_reason: null,
    success_count: 2,
    effective_backtest_draw_count: 1,
    successful_execution_count: 10,
    historical_success_rate: '0.200000000000000000',
    random_baseline_success_rate: '0.100000000000000000',
    random_baseline_rate_difference: '0.100000000000000000',
    coverage: '1.000',
    window_available_draws: 1,
    window_requested_draws: 10,
    window_complete: true,
    official_prize_counts: {
      first: 0,
      second: 0,
      third: 0,
      fourth: 0,
      fifth: 0,
      sixth: 0,
      seventh: 0,
      general: 0,
    },
    no_prize_count: 8,
    report_sha256: 'a'.repeat(64),
    report_file_sha256: 'a'.repeat(64),
    catalog_sha256: 'a'.repeat(64),
    ...overrides,
  }
}

function makeSummary() {
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
    method_families: ['test'],
    reproduction_statuses: ['BACKTESTED', 'CLOSED_UNEXECUTABLE', 'DUPLICATE_ALIAS'],
    catalog_sha256: 'a'.repeat(64),
    records_available: true,
    projection_sha256: 'a'.repeat(64),
    source_report_count: 1,
    primary_ranking_criterion: 'OFFICIAL_ANY_PRIZE',
    research_disclaimer: researchDisclaimer,
  }
}

function response(payload: unknown) {
  return {
    ok: true,
    status: 200,
    json: () => Promise.resolve(payload),
  } as Response
}

function stubOverviewFetch(records: ReturnType<typeof makeRecord>[]) {
  vi.stubGlobal(
    'fetch',
    vi.fn((input: RequestInfo | URL) => {
      const url = String(input)
      if (url.includes('/api/v1/b649-multi-ticket-records/summary')) {
        return Promise.resolve(response(makeSummary()))
      }

      if (url.includes('/api/v1/b649-multi-ticket-records')) {
        const urlObject = new URL(url, 'http://localhost')
        const prefixCount = Number(urlObject.searchParams.get('prefix_count') ?? 10)
        const window = urlObject.searchParams.get('window') ?? 'FULL'
        return Promise.resolve(
          response({
            items: records.map((record) => ({ ...record, prefix_count: prefixCount, window })),
            total: records.length,
            limit: 50,
            offset: 0,
            prefix_count: prefixCount,
            window,
            criterion: 'M3_PLUS',
            research_disclaimer: researchDisclaimer,
          }),
        )
      }

      return Promise.resolve(response({ items: [], total: 0 }))
    }),
  )
}

async function mountOverview(records: ReturnType<typeof makeRecord>[]) {
  stubOverviewFetch(records)
  const wrapper = mount(ReplayOverviewPage)
  await flushPromises()
  return wrapper
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('B649 replay overview official denominator contract', () => {
  it('shows successes over official N and sorts observations by official N', async () => {
    const fixtureA = makeRecord({
      strategy_id: 'fixture-a',
      effective_backtest_draw_count: 100,
      successful_execution_count: 10,
    })
    const fixtureB = makeRecord({
      strategy_id: 'fixture-b',
      rank: 5,
      official_rank: 2,
      official_any_prize_count: 4,
      official_any_prize_rate: '0.400000000000000000',
      effective_backtest_draw_count: 1,
      successful_execution_count: 20,
    })
    const wrapper = await mountOverview([fixtureA, fixtureB])

    const rowA = wrapper.find('[data-testid="table-row-fixture-a"]')
    expect(rowA.text()).toContain('#1')
    expect(rowA.find('[data-testid="row-hit-rate"]').text()).toBe('20.00%')
    expect(rowA.findAll('td')[3].text()).toBe('2 / 10')

    const observationsHeader = wrapper
      .findAll('th')
      .find((header) => header.text().includes('Official N'))
    await observationsHeader?.trigger('click')
    await flushPromises()

    const rows = wrapper.findAll('[data-testid^="table-row-fixture-"]')
    expect(rows[0].attributes('data-testid')).toBe('table-row-fixture-b')
    expect(rows[0].text()).toContain('4 / 20')
    expect(rows[1].attributes('data-testid')).toBe('table-row-fixture-a')
  })

  it.each(['RECENT_50', 'RECENT_300', 'RECENT_750', 'FULL'] as const)(
    'uses official N for the %s window',
    (window) => {
      const item = transformB649Record(makeRecord(), 10, window)
      expect(item.officialAnyPrizeRateFormatted).toBe('20.00%')
      expect(item.officialAnyPrizeCount).toBe(2)
      expect(item.successfulExecutionCount).toBe(10)
      expect(item.effectiveBacktestDrawCount).toBe(1)
    },
  )

  it('uses the verified K=10 FULL official denominator instead of the legacy count', async () => {
    const fixture = makeRecord({
      strategy_id: 'fixture-k10-full-official',
      prefix_count: 10,
      window: 'FULL',
      rank: 1,
      official_rank: 1,
      official_any_prize_count: 495,
      official_any_prize_rate: '0.230446927374301676',
      effective_backtest_draw_count: 716,
      successful_execution_count: 2148,
      window_available_draws: 716,
    })
    const item = transformB649Record(fixture, 10, 'FULL')
    expect(item.officialAnyPrizeCount).toBe(495)
    expect(item.successfulExecutionCount).toBe(2148)
    expect(item.effectiveBacktestDrawCount).toBe(716)
    expect(item.officialAnyPrizeRateFormatted).toBe('23.04%')

    const wrapper = await mountOverview([fixture])
    const row = wrapper.find('[data-testid="table-row-fixture-k10-full-official"]')
    expect(row.find('[data-testid="row-hit-rate"]').text()).toBe('23.04%')
    expect(row.findAll('td')[3].text()).toBe('495 / 2148')
    expect(row.findAll('td')[3].text()).not.toBe('495 / 716')
  })

  it('distinguishes no sample, missing official rate, and a valid zero hit rate', async () => {
    const fixtureB = makeRecord({
      strategy_id: 'fixture-b-zero-n',
      rank: null,
      official_rank: null,
      official_any_prize_count: 0,
      official_any_prize_rate: '0.000000000000000000',
      successful_execution_count: 0,
    })
    expect(transformB649Record(fixtureB, 10, 'FULL').officialRank).toBeNull()
    const fixtureC = makeRecord({
      strategy_id: 'fixture-c-null-n',
      rank: null,
      official_rank: null,
      official_any_prize_count: 2,
      official_any_prize_rate: '0.200000000000000000',
      historical_success_rate: '0.500000000000000000',
      effective_backtest_draw_count: 1,
      successful_execution_count: null,
      window_available_draws: 500,
    })
    const fixtureCNullRate = makeRecord({
      strategy_id: 'fixture-c-null-rate',
      official_any_prize_rate: null,
      historical_success_rate: '0.500000000000000000',
      successful_execution_count: 10,
    })
    const fixtureD = makeRecord({
      strategy_id: 'fixture-d-zero-hits',
      rank: 8,
      official_rank: 7,
      official_any_prize_count: 0,
      official_any_prize_rate: '0.000000000000000000',
      effective_backtest_draw_count: 1,
      successful_execution_count: 10,
    })

    const mappedB = transformB649Record(fixtureB, 10, 'FULL')
    const mappedC = transformB649Record(fixtureC, 10, 'FULL')
    const mappedCNullRate = transformB649Record(fixtureCNullRate, 10, 'FULL')
    const mappedD = transformB649Record(fixtureD, 10, 'FULL')

    expect(mappedB.isAvailable).toBe(false)
    expect(mappedB.officialAnyPrizeRateFormatted).toBe('Unavailable')
    expect(mappedC.successfulExecutionCount).toBeNull()
    expect(mappedC.officialAnyPrizeRateFormatted).toBe('Unavailable')
    expect(mappedCNullRate.isAvailable).toBe(false)
    expect(mappedCNullRate.officialAnyPrizeRateFormatted).toBe('Unavailable')
    expect(mappedD.isAvailable).toBe(true)
    expect(mappedD.officialAnyPrizeRateFormatted).toBe('0.00%')
    expect(mappedD.officialAnyPrizeCount).toBe(0)
    expect(mappedD.successfulExecutionCount).toBe(10)

    const wrapper = await mountOverview([fixtureB, fixtureC, fixtureCNullRate, fixtureD])
    const rowB = wrapper.find('[data-testid="table-row-fixture-b-zero-n"]')
    const rowC = wrapper.find('[data-testid="table-row-fixture-c-null-n"]')
    const rowD = wrapper.find('[data-testid="table-row-fixture-d-zero-hits"]')
    expect(rowB.findAll('td')[3].text()).toBe('-')
    expect(rowB.find('[data-testid="row-hit-rate"]').exists()).toBe(false)
    expect(rowC.findAll('td')[3].text()).toBe('-')
    expect(rowC.find('[data-testid="row-hit-rate"]').exists()).toBe(false)
    expect(rowD.find('[data-testid="row-hit-rate"]').text()).toBe('0.00%')
    expect(rowD.findAll('td')[3].text()).toBe('0 / 10')
  })

  it('labels M3_PLUS selection separately and preserves rank and official_rank', async () => {
    const fixtureE = makeRecord({
      strategy_id: 'fixture-e',
      rank: 2,
      official_rank: 9,
      official_any_prize_count: 3,
      official_any_prize_rate: '0.300000000000000000',
      successful_execution_count: 10,
    })
    const mappedE = transformB649Record(fixtureE, 10, 'FULL')
    expect(mappedE.rank).toBe(2)
    expect(mappedE.officialRank).toBe(9)

    const wrapper = await mountOverview([fixtureE])
    const basis = wrapper.find('[data-testid="ranking-basis-note"]')
    expect(basis.exists()).toBe(true)
    expect(basis.text()).toContain('M3_PLUS')
    expect(basis.text()).toContain('OFFICIAL_ANY_PRIZE')
    const rowE = wrapper.find('[data-testid="table-row-fixture-e"]')
    expect(rowE.text()).toContain('#9')
    expect(rowE.findAll('td')[3].text()).toBe('3 / 10')
  })
})
