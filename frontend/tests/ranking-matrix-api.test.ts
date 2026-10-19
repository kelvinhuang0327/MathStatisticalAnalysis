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
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'

import {
  CANONICAL_TICKET_COUNTS,
  CANONICAL_WINDOWS,
  deriveComparabilityStatus,
  deriveWarningCodes,
  extractBestPrizeFromCounts,
  fetchCrossWindowData,
  fetchMultiTicketMatrix,
  fetchRankingData,
  formatCoveragePercentage,
  formatDeltaPercentage,
  formatRatePercentage,
  getWarningMeta,
  parseNumberString,
  transformB649K5ToRankingRow,
  transformB649K10ToRankingRow,
} from '../src/api/rankingMatrix'

describe('rankingMatrix API and utilities', () => {
  describe('formatting utilities', () => {
    it('formats rate percentages accurately and returns Unavailable for null/NaN', () => {
      expect(formatRatePercentage(0.245)).toBe('24.50%')
      expect(formatRatePercentage(0)).toBe('0.00%')
      expect(formatRatePercentage(1)).toBe('100.00%')
      expect(formatRatePercentage(null)).toBe('Unavailable')
      expect(formatRatePercentage(undefined)).toBe('Unavailable')
      expect(formatRatePercentage(Number.NaN)).toBe('Unavailable')
    })

    it('formats baseline delta percentages with sign prefixes', () => {
      expect(formatDeltaPercentage(0.023)).toBe('+2.30%')
      expect(formatDeltaPercentage(-0.015)).toBe('-1.50%')
      expect(formatDeltaPercentage(0)).toBe('0.00%')
      expect(formatDeltaPercentage(null)).toBe('Unavailable')
    })

    it('formats coverage percentages accurately', () => {
      expect(formatCoveragePercentage(0.9069)).toBe('90.69%')
      expect(formatCoveragePercentage(1.0)).toBe('100.00%')
      expect(formatCoveragePercentage(0.0019)).toBe('0.19%')
      expect(formatCoveragePercentage(null)).toBe('Unavailable')
    })

    it('parses numeric string safely', () => {
      expect(parseNumberString('0.245000')).toBe(0.245)
      expect(parseNumberString('-0.012000')).toBe(-0.012)
      expect(parseNumberString(null)).toBeNull()
      expect(parseNumberString('invalid')).toBeNull()
    })

    it('extracts best prize from prize counts', () => {
      expect(extractBestPrizeFromCounts({ first: 1, second: 0, third: 0, fourth: 0, fifth: 0, sixth: 0, seventh: 0, general: 0 })).toBe('頭獎 (1)')
      expect(extractBestPrizeFromCounts({ first: 0, second: 2, third: 0, fourth: 0, fifth: 0, sixth: 0, seventh: 0, general: 0 })).toBe('貳獎 (2)')
      expect(extractBestPrizeFromCounts({ first: 0, second: 0, third: 0, fourth: 0, fifth: 0, sixth: 0, seventh: 0, general: 5 })).toBe('普獎 (5)')
      expect(extractBestPrizeFromCounts({ first: 0, second: 0, third: 0, fourth: 0, fifth: 0, sixth: 0, seventh: 0, general: 0 })).toBe('無中獎')
      expect(extractBestPrizeFromCounts(null)).toBe('Unavailable')
    })
  })

  describe('comparability and warning derivations', () => {
    it('derives comparability status correctly', () => {
      expect(deriveComparabilityStatus(false, 'BACKTESTED', null, 300, 'RECENT_300').status).toBe('UNAVAILABLE')
      expect(deriveComparabilityStatus(true, 'CLOSED_UNEXECUTABLE', null, 300, 'RECENT_300').status).toBe('NOT_HISTORICALLY_COMPARABLE')
      expect(deriveComparabilityStatus(true, 'DUPLICATE_ALIAS', null, 300, 'RECENT_300').status).toBe('NOT_HISTORICALLY_COMPARABLE')
      expect(deriveComparabilityStatus(true, 'BACKTESTED', 'Unranked reason', 300, 'RECENT_300').status).toBe('NOT_HISTORICALLY_COMPARABLE')
      expect(deriveComparabilityStatus(true, 'BACKTESTED', 'RANKED_BACKTEST_EVIDENCE_AVAILABLE', 300, 'RECENT_300').status).toBe('COMPARABLE')
      expect(deriveComparabilityStatus(true, 'BACKTESTED', null, 25, 'RECENT_300').status).toBe('LOW_SAMPLE_SIZE')
      expect(deriveComparabilityStatus(true, 'BACKTESTED', null, 300, 'RECENT_300').status).toBe('COMPARABLE')
    })

    it('derives warning codes correctly for high rank low coverage and missing recent observations', () => {
      const warnings1 = deriveWarningCodes(1, 0.05, 300, 10, 'FULL', 'BACKTESTED', null, null)
      expect(warnings1).toContain('HIGH_RANK_LOW_COVERAGE')

      const warnings2 = deriveWarningCodes(5, 1.0, 50, 0, 'RECENT_50', 'BACKTESTED', null, null)
      expect(warnings2).toContain('NO_RECENT_OBSERVATIONS')

      const warnings3 = deriveWarningCodes(null, null, null, null, 'FULL', 'CLOSED_UNEXECUTABLE', null, 'FROZEN_PREDICTION_OUTPUT_AND_PRODUCER_UNAVAILABLE')
      expect(warnings3).toContain('CLOSED_UNEXECUTABLE')
      expect(warnings3).toContain('FROZEN_PREDICTION_OUTPUT_AND_PRODUCER_UNAVAILABLE')
    })

    it('returns metadata for known and unknown warning codes without dropping unknown ones', () => {
      expect(getWarningMeta('HIGH_RANK_LOW_COVERAGE').label).toBe('高排名低覆蓋率')
      const unknown = getWarningMeta('CUSTOM_FUTURE_WARNING')
      expect(unknown.label).toBe('CUSTOM_FUTURE_WARNING')
      expect(unknown.severity).toBe('warning')
    })
  })

  describe('canonical options and arrays', () => {
    it('exposes canonical 2, 3, 5, 10, 20 ticket counts and FULL, 750, 300, 50 windows', () => {
      expect(CANONICAL_TICKET_COUNTS).toEqual([2, 3, 5, 10, 20])
      expect(CANONICAL_WINDOWS).toEqual(['FULL', 'RECENT_750', 'RECENT_300', 'RECENT_50'])
    })
  })

  describe('fetchRankingData and matrix building', () => {
    let fetchMock: ReturnType<typeof vi.fn<typeof fetch>>

    beforeEach(() => {
      fetchMock = vi.fn<typeof fetch>().mockImplementation((input) => {
        const url = String(input)
        if (url.includes('/api/v1/b649-multi-ticket-records/summary')) {
          return Promise.resolve({
            ok: true,
            status: 200,
            json: () => Promise.resolve({
              progress: {
                total_strategy_count: 10,
                reproduced_count: 5,
                backtested_count: 5,
                closed_count: 0,
                duplicate_alias_count: 0,
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
              method_families: ['coldpool'],
              reproduction_statuses: ['BACKTESTED', 'CLOSED_UNEXECUTABLE', 'DUPLICATE_ALIAS'],
              catalog_sha256: 'a'.repeat(64),
              records_available: true,
              projection_sha256: 'b'.repeat(64),
              source_report_count: 10,
              metrics_available_strategy_count: 5,
              metrics_unavailable_strategy_count: 5,
              primary_ranking_criterion: 'OFFICIAL_ANY_PRIZE',
              research_disclaimer: '歷史成功率、排名與隨機基準差異僅供描述性研究，不構成未來預測、推薦、上線決策或中獎保證。',
            }),
          } as Response)
        }
        if (url.includes('/api/v1/strategies')) {
          return Promise.resolve({
            ok: true,
            status: 200,
            json: () => Promise.resolve([
              {
                strategy_id: 'strat_1',
                display_name: 'Strategy One',
                version: 'v1.0',
                supported_lottery_types: ['BIG_LOTTO'],
                minimum_history: 10,
                lifecycle_status: 'ONLINE',
                executable: true,
                provenance: ['catalog'],
              },
            ]),
          } as Response)
        }
        if (url.includes('/api/v1/b649-multi-ticket-records')) {
          return Promise.resolve({
            ok: true,
            status: 200,
            json: () => Promise.resolve({
              total: 1,
              limit: 100,
              offset: 0,
              prefix_count: 5,
              window: 'RECENT_300',
              criterion: 'M3_PLUS',
              research_disclaimer: '歷史成功率、排名與隨機基準差異僅供描述性研究，不構成未來預測、推薦、上線決策或中獎保證。',
              items: [
                {
                  strategy_id: 'strat_1',
                  strategy_version: 'v1.0',
                  legacy_method_id: 'strat_1',
                  source_path: 'strategies/strat_1.py',
                  method_family: 'coldpool',
                  reproduction_status: 'BACKTESTED',
                  duplicate_alias_target: null,
                  prefix_count: 5,
                  window: 'RECENT_300',
                  criterion: 'M3_PLUS',
                  rank: 1,
                  official_rank: 1,
                  official_any_prize_count: 30,
                  official_any_prize_rate: '0.300000000000000000',
                  official_random_baseline_probability: '0.220000000000000000',
                  official_random_baseline_delta: '0.080000000000000000',
                  unranked_reason: null,
                  success_count: 30,
                  effective_backtest_draw_count: 100,
                  successful_execution_count: 100,
                  historical_success_rate: '0.300000000000000000',
                  random_baseline_success_rate: '0.220000000000000000',
                  random_baseline_rate_difference: '0.080000000000000000',
                  coverage: '1.000000000000000000',
                  window_available_draws: 100,
                  window_requested_draws: 100,
                  window_complete: true,
                  official_prize_counts: { first: 1, second: 0, third: 0, fourth: 0, fifth: 0, sixth: 0, seventh: 0, general: 0 },
                  no_prize_count: 70,
                  report_sha256: 'c'.repeat(64),
                  report_file_sha256: 'd'.repeat(64),
                  catalog_sha256: 'a'.repeat(64),
                  authority_mode: 'HISTORICAL_SEALED_EVIDENCE_V1',
                  metrics_unavailable_reason: null,
                },
              ],
            }),
          } as Response)
        }
        if (url.includes('/api/v1/b649-exact-native-records')) {
          const urlObj = new URL(url, 'http://localhost')
          const tc = Number(urlObj.searchParams.get('ticket_count') || 2)
          const win = urlObj.searchParams.get('window') || 'RECENT_300'
          if (tc === 5) return Promise.resolve(new Response(JSON.stringify(k5Page(win))))
          if (tc === 10) return Promise.resolve(new Response(JSON.stringify(k10Page(win))))
          return Promise.resolve({
            ok: true,
            status: 200,
            json: () => Promise.resolve({
              total: 2,
              limit: 100,
              offset: 0,
              ticket_count: tc,
              window: win,
              criterion: 'OFFICIAL_ANY_PRIZE',
              research_disclaimer: '歷史成功率、排名與隨機基準差異僅供描述性研究，不構成未來預測、推薦、上線決策或中獎保證。',
              items: [
                {
                  strategy_id: 'strat_1',
                  strategy_version: 'v1.0',
                  legacy_method_id: 'strat_1',
                  source_path: 'strategies/strat_1.py',
                  method_family: 'coldpool',
                  reproduction_status: 'BACKTESTED',
                  duplicate_alias_target: null,
                  ticket_count: tc,
                  window: win,
                  criterion: 'OFFICIAL_ANY_PRIZE',
                  metric_status: 'AVAILABLE',
                  rankable: true,
                  unavailable_reason: null,
                  metrics_unavailable_reason: null,
                  unranked_reason: 'RANKED_BACKTEST_EVIDENCE_AVAILABLE',
                  official_any_prize_count: 18,
                  official_any_prize_rate: '0.060000000000000000',
                  official_random_baseline_probability: '0.060000000000000000',
                  official_random_baseline_delta: '0.000000000000000000',
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
                  strategy_id: 'strat_unavail',
                  strategy_version: 'v1.0',
                  legacy_method_id: 'strat_unavail',
                  source_path: 'strategies/strat_unavail.py',
                  method_family: 'statistical',
                  reproduction_status: 'BACKTESTED',
                  duplicate_alias_target: null,
                  ticket_count: tc,
                  window: win,
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
            }),
          } as Response)
        }
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve({ items: [], total: 0 }),
        } as Response)
      })
      vi.stubGlobal('fetch', fetchMock)
    })

    afterEach(() => {
      vi.unstubAllGlobals()
    })

    it('loads all five published K5 strategies including the uncatalogued composite', async () => {
      const rows = await fetchRankingData('BIG_LOTTO', 5, 'RECENT_300')
      const published = k5Packaged.filter((r) => r.window === 'RECENT_300')
      expect(rows.map((r) => r.k5Record)).toEqual(published)
      expect(rows).toHaveLength(5)
      expect(rows.find((r) => r.strategyId.startsWith('legacy_composite__'))?.isAvailable).toBe(true)
      expect(rows[0]?.officialAnyPrizeRateFormatted).toBe('15.67%')
      expect(fetchMock.mock.calls.every(([url]) => String(url).includes('b649-exact-native-records'))).toBe(true)
    })

    it('loads B649 ranking rows for 2 and 3 exact-native tickets with formal rank remaining null', async () => {
      const rows2 = await fetchRankingData('BIG_LOTTO', 2, 'RECENT_300')
      expect(rows2.length).toBe(2)

      // Available strategy
      const availRow = rows2.find((r) => r.strategyId === 'strat_1')
      expect(availRow).toBeDefined()
      expect(availRow?.officialRank).toBeNull()
      expect(availRow?.isAvailable).toBe(true)
      expect(availRow?.officialAnyPrizeRateFormatted).toBe('6.00%')
      expect(availRow?.baselineDeltaFormatted).toBe('0.00%')
      expect(availRow?.comparabilityStatus).toBe('COMPARABLE')

      // Unavailable strategy
      const unavailRow = rows2.find((r) => r.strategyId === 'strat_unavail')
      expect(unavailRow).toBeDefined()
      expect(unavailRow?.officialRank).toBeNull()
      expect(unavailRow?.isAvailable).toBe(false)
      expect(unavailRow?.comparabilityStatus).toBe('UNAVAILABLE')

      // Check K3 loads identically
      const rows3 = await fetchRankingData('BIG_LOTTO', 3, 'RECENT_300')
      expect(rows3.length).toBe(2)
      expect(rows3[0]?.officialRank).toBeNull()
    })

    it('builds multi-ticket matrix with 2, 3, 5, 10, 20 cells', async () => {
      const matrix = await fetchMultiTicketMatrix('BIG_LOTTO', 'RECENT_300')
      expect(matrix.length).toBe(9)
      const row = matrix.find((r) => r.strategyId === 'strat_1')!
      expect(row.cells[2].isAvailable).toBe(true)
      expect(row.cells[2].officialRank).toBeNull()
      expect(row.cells[2].officialAnyPrizeRateFormatted).toBe('6.00%')
      expect(row.cells[3].isAvailable).toBe(true)
      expect(row.cells[3].officialRank).toBeNull()
      expect(row.cells[5].isAvailable).toBe(false)
      expect(row.cells[5].officialRank).toBeNull()
      for (const record of k5Packaged.filter((r) => r.window === 'RECENT_300')) {
        expect(matrix.find((r) => r.strategyId === record.strategy_id)!.cells[5].k5Record).toEqual(record)
      }
      for (const record of k10Packaged.filter((r) => r.window === 'RECENT_300')) {
        const cell = matrix.find((r) => r.strategyId === record.strategy_id)!.cells[10]
        const mapped = transformB649K10ToRankingRow(record)
        expect(cell.officialRank).toBe(mapped.officialRank)
        expect(cell.officialAnyPrizeRate).toBe(mapped.officialAnyPrizeRate)
        expect(cell.baselineDelta).toBe(mapped.baselineDelta)
      }
    })

    it('fetches cross-window points across FULL, 750, 300, 50', async () => {
      const crossData = await fetchCrossWindowData('BIG_LOTTO', 5, 'strat_1', 'Strategy One')
      expect(crossData.points.length).toBe(4)
      expect(crossData.points.map((p) => p.window)).toEqual(['FULL', 'RECENT_750', 'RECENT_300', 'RECENT_50'])
    })
  })
})


describe('sealed K10 authority', () => {
  afterEach(() => vi.unstubAllGlobals())
  it.each(CANONICAL_WINDOWS)('loads %s directly despite legacy summary failure', async (window) => {
    const calls: string[] = []
    vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockImplementation(async (input) => {
      const url = String(input); calls.push(url)
      if (url.includes('b649-exact-native-records') && url.includes('ticket_count=10')) return new Response(JSON.stringify(k10Page(window)))
      return new Response('{}', { status: 503 })
    }))
    const rows = await fetchRankingData('BIG_LOTTO', 10, window)
    const expected = k10Packaged.filter((r) => r.window === window)
    expect(rows).toHaveLength(2)
    expect(rows.map((r) => r.strategyId)).toEqual(expected.map((r) => r.strategy_id))
    expect(rows.map((r) => r.officialRank)).toEqual([1, 2])
    expect(rows.map((r) => r.sourceOrder)).toEqual([1, 2])
    expect(rows.every((r) => r.strategyVersion === 'v0.1' && r.isAvailable)).toBe(true)
    expect(rows.map((r) => r.observations)).toEqual(expected.map((r) => r.evaluated_draws))
    expect(rows.map((r) => r.requestedDraws)).toEqual(expected.map((r) => r.requested_draws))
    expect(calls.every((url) => url.includes('b649-exact-native-records'))).toBe(true)
  })
  it('keeps null rank, unavailable metrics and authoritative zero', () => {
    const source = k10Packaged[0]!
    const zero = transformB649K10ToRankingRow({ ...source, rank: null, official_rank: null, unranked_reason: 'PRODUCER_UNRANKED', official_any_prize_rate: '0.000000000000000000', official_any_prize_numerator: 0 })
    expect(zero.officialRank).toBeNull()
    expect(zero.sourceOrder).toBe(1)
    expect(zero.officialAnyPrizeRateFormatted).toBe('0.00%')
    expect(zero.successes).toBe(0)
    expect(zero.unrankedReason).toBe('PRODUCER_UNRANKED')
    const unavailable = transformB649K10ToRankingRow({ ...source, rank: null, official_rank: null, metric_status: 'UNAVAILABLE', unavailable_reason: 'PRODUCER_FAILURE', official_any_prize_rate: null, baseline_delta: null, official_random_baseline: null, coverage: null, best_prize_counts: null })
    expect(unavailable.isAvailable).toBe(false)
    expect(unavailable.officialAnyPrizeRate).toBeNull()
    expect(unavailable.baselineDelta).toBeNull()
    expect(unavailable.bestOfficialPrize).toBe('Unavailable')
    expect(unavailable.unrankedReason).toBe('PRODUCER_FAILURE')
  })
  it('does not fall back to prefix data when exact K10 fails', async () => {
    const mock = vi.fn<typeof fetch>().mockResolvedValue(new Response('{}', { status: 503 }))
    vi.stubGlobal('fetch', mock)
    await expect(fetchRankingData('BIG_LOTTO', 10, 'FULL')).rejects.toThrow()
    expect(mock).toHaveBeenCalledTimes(1)
    expect(String(mock.mock.calls[0]?.[0])).toContain('ticket_count=10')
  })
})


describe('sealed K5 authority', () => {
  afterEach(() => vi.unstubAllGlobals())
  it.each(CANONICAL_WINDOWS)('loads %s before legacy admission paths and retains every producer value', async (window) => {
    const calls: string[] = []
    vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockImplementation(async (input) => {
      const url = String(input); calls.push(url)
      if (url.includes('b649-exact-native-records') && url.includes('ticket_count=5')) return new Response(JSON.stringify(k5Page(window)))
      return new Response('{}', { status: 503 })
    }))
    const rows = await fetchRankingData('BIG_LOTTO', 5, window)
    const expected = k5Packaged.filter((r) => r.window === window)
    expect(rows.map((r) => r.k5Record)).toEqual(expected)
    expect(rows.map((r) => r.officialRank)).toEqual(expected.map((r) => r.rank))
    expect(rows.map((r) => r.rawRank)).toEqual(expected.map((r) => r.rank))
    expect(rows.map((r) => r.position)).toEqual([1, 2, 3, 4, 5])
    expect(rows.map((r) => r.sourceOrder)).toEqual([1, 2, 3, 4, 5])
    expect(rows.every((r) => r.isAvailable)).toBe(true)
    expect(rows.every((r) => JSON.stringify(r.producerTies) === JSON.stringify(k5Projection.ties_by_window[window]))).toBe(true)
    expect(calls).toHaveLength(1)
    expect(calls[0]).toContain('ticket_count=5')
  })
  it('preserves published zero, unavailable reason and sparse prize counts', () => {
    const source = k5Packaged[0]!
    const zero = transformB649K5ToRankingRow({ ...source, official_any_prize_rate: '0.000000000000000000', official_any_prize_numerator: 0, best_prize_counts: { GENERAL: 0 } })
    expect(zero.officialAnyPrizeRateFormatted).toBe('0.00%')
    expect(zero.successes).toBe(0)
    expect(zero.k5Record?.best_prize_counts).toEqual({ GENERAL: 0 })
    expect(zero.k5Record?.typed_replay_failures_count).toBe(500)
    expect(zero.isAvailable).toBe(true)
    const unavailable = transformB649K5ToRankingRow({ ...source, metric_status: 'UNAVAILABLE', metric_unavailable_reason: 'EXECUTION_FAILURE', official_rank: null, rank: null, official_any_prize_rate: null, official_any_prize_numerator: null, official_any_prize_denominator: null, official_random_baseline: null, baseline_delta: null, coverage: null, best_prize_counts: null })
    expect(unavailable.officialAnyPrizeRateFormatted).toBe('Unavailable')
    expect(unavailable.successes).toBeNull()
    expect(unavailable.bestOfficialPrize).toBe('Unavailable')
    expect(unavailable.unrankedReason).toBe('EXECUTION_FAILURE')
  })
  it('uses K5 authority for cross-window points including the composite leader', async () => {
    vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockImplementation(async (input) => {
      const url = new URL(String(input), 'http://localhost')
      expect(url.pathname).toBe('/api/v1/b649-exact-native-records')
      expect(url.searchParams.get('ticket_count')).toBe('5')
      return new Response(JSON.stringify(k5Page(url.searchParams.get('window')!)))
    }))
    const sid = 'legacy_composite__quick_predict_5bet_ts3_markov_freqort'
    const result = await fetchCrossWindowData('BIG_LOTTO', 5, sid, 'Composite')
    expect(result.points.map((p) => p.k5Record)).toEqual(CANONICAL_WINDOWS.map((w) => k5Packaged.find((r) => r.window === w && r.strategy_id === sid)))
    expect(result.points[1]?.officialRank).toBe(1)
  })
  it.each([503, 422])('never falls back when K5 returns %s', async (status) => {
    const mock = vi.fn<typeof fetch>().mockResolvedValue(new Response('{}', { status }))
    vi.stubGlobal('fetch', mock)
    await expect(fetchRankingData('BIG_LOTTO', 5, 'FULL')).rejects.toThrow()
    expect(mock).toHaveBeenCalledTimes(1)
    expect(String(mock.mock.calls[0]?.[0])).toContain('ticket_count=5')
  })
  it('rejects a legacy or K10 envelope on the K5 route', async () => {
    vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockResolvedValue(new Response(JSON.stringify(k10Page('FULL')))))
    await expect(fetchRankingData('BIG_LOTTO', 5, 'FULL')).rejects.toThrow('Invalid K5 authority response')
  })
  it('paginates without renumbering ties or publication order', async () => {
    vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockImplementation(async (input) => {
      const url = new URL(String(input), 'http://localhost')
      const page = k5Page('RECENT_50')
      const offset = Number(url.searchParams.get('offset'))
      return new Response(JSON.stringify({ ...page, offset, limit: 2, items: page.items.slice(offset, offset + 2) }))
    }))
    const rows = await fetchRankingData('BIG_LOTTO', 5, 'RECENT_50')
    expect(rows.map((r) => r.officialRank)).toEqual([1, 2, 2, 2, 5])
    expect(rows.map((r) => r.sourceOrder)).toEqual([1, 2, 3, 4, 5])
    expect(rows[4]?.producerTies).toEqual(k5Projection.ties_by_window.RECENT_50)
  })
})
