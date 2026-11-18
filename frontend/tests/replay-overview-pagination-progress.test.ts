// @vitest-environment jsdom

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { B649RecordsRequestError } from '../src/api/b649MultiTicketRecords'
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

function makeMockSummary(recordsAvailable = true, totalCount = 12) {
  return {
    progress: {
      total_strategy_count: totalCount,
      reproduced_count: totalCount,
      backtested_count: totalCount,
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
    method_families: ['statistical', 'ml'],
    reproduction_statuses: ['BACKTESTED', 'CLOSED_UNEXECUTABLE', 'DUPLICATE_ALIAS'],
    catalog_sha256: SHA256_FIXTURE,
    records_available: recordsAvailable,
    projection_sha256: SHA256_FIXTURE,
    source_report_count: 100,
    primary_ranking_criterion: 'OFFICIAL_ANY_PRIZE',
    research_disclaimer: RESEARCH_DISCLAIMER,
  }
}

function makeMockRecord(i: number, prefixCount = 10, window = 'FULL') {
  return {
    strategy_id: `strategy_${i}`,
    strategy_version: 'v1.0',
    legacy_method_id: `tools/legacy_method_${i}.py`,
    source_path: `src/strategies/strategy_${i}.py`,
    method_family: 'statistical',
    reproduction_status: 'BACKTESTED',
    duplicate_alias_target: null,
    prefix_count: prefixCount,
    window,
    criterion: 'M3_PLUS',
    rank: i,
    official_rank: i,
    official_any_prize_count: 500 + i,
    official_any_prize_rate: '0.1000',
    official_random_baseline_probability: '0.0780',
    official_random_baseline_delta: '0.0220',
    unranked_reason: null,
    success_count: 500 + i,
    effective_backtest_draw_count: 1949,
    successful_execution_count: 1949,
    historical_success_rate: '0.1000',
    random_baseline_success_rate: '0.0780',
    random_baseline_rate_difference: '0.0220',
    coverage: '0.980',
    window_available_draws: 1949,
    window_requested_draws: 1949,
    window_complete: true,
    official_prize_counts: {
      first: 0,
      second: 0,
      third: 1,
      fourth: 2,
      fifth: 4,
      sixth: 8,
      seventh: 10,
      general: 15,
    },
    no_prize_count: 1449 - i,
    report_sha256: SHA256_FIXTURE,
    report_file_sha256: SHA256_FIXTURE,
    catalog_sha256: SHA256_FIXTURE,
  }
}

describe('Replay Overview pagination progress & integrity (AC02-AC07)', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('AC02: dense multi-page progression advances offset cleanly across pages without skipping or duplicating items', async () => {
    const totalRecords = 102
    const allRecords = Array.from({ length: totalRecords }, (_, idx) => makeMockRecord(idx + 1))
    const requestedOffsets: number[] = []
    const requestedLimits: number[] = []

    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
      const url = String(input)
      if (url.includes('/summary')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve(makeMockSummary(true, totalRecords)),
        } as Response)
      }

      const urlObj = new URL(url, 'http://localhost')
      const offset = Number(urlObj.searchParams.get('offset') ?? 0)
      const limit = Number(urlObj.searchParams.get('limit') ?? 100)
      requestedOffsets.push(offset)
      requestedLimits.push(limit)

      // Dense contract: Page 1 (offset=0, limit=100) returns 100 items; Page 2 (offset=100) returns remaining 2 items
      const slice = allRecords.slice(offset, offset + limit)

      return Promise.resolve({
        ok: true,
        status: 200,
        json: () =>
          Promise.resolve({
            items: slice,
            total: totalRecords,
            limit,
            offset,
            prefix_count: 10,
            window: 'FULL',
            criterion: 'M3_PLUS',
            research_disclaimer: RESEARCH_DISCLAIMER,
          }),
      } as Response)
    }))

    const result = await fetchReplayOverviewData('B649', 10, 'FULL')

    expect(requestedOffsets).toEqual([0, 100])
    expect(requestedLimits).toEqual([100, 100])
    expect(result.items).toHaveLength(102)
    const receivedIds = result.items.map((it) => it.strategyId)
    expect(new Set(receivedIds).size).toBe(102)
    expect(receivedIds).toEqual(allRecords.map((r) => r.strategy_id))
    expect(result.summary.totalStrategies).toBe(102)
    expect(result.summary.fullUniverseStatus).toBe('COMPLETE')
  })

  it('AC02 fail-closed: non-final short page is rejected immediately as MALFORMED_RESPONSE', async () => {
    const totalRecords = 12
    const allRecords = Array.from({ length: totalRecords }, (_, idx) => makeMockRecord(idx + 1))
    let fetchCalls = 0
    const requestedOffsets: number[] = []

    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
      const url = String(input)
      if (url.includes('/summary')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve(makeMockSummary(true, totalRecords)),
        } as Response)
      }

      fetchCalls++
      const urlObj = new URL(url, 'http://localhost')
      const offset = Number(urlObj.searchParams.get('offset') ?? 0)
      requestedOffsets.push(offset)

      return Promise.resolve({
        ok: true,
        status: 200,
        json: () =>
          Promise.resolve({
            items: allRecords.slice(0, 5),
            total: totalRecords,
            limit: 100,
            offset,
            prefix_count: 10,
            window: 'FULL',
            criterion: 'M3_PLUS',
            research_disclaimer: RESEARCH_DISCLAIMER,
          }),
      } as Response)
    }))

    let resolvedResult: unknown = null
    let caughtError: unknown = null
    try {
      resolvedResult = await fetchReplayOverviewData('B649', 10, 'FULL')
    } catch (error) {
      caughtError = error
    }

    expect(resolvedResult).toBeNull()
    expect(caughtError).toBeInstanceOf(B649RecordsRequestError)
    expect(caughtError).toMatchObject({
      kind: 'MALFORMED_RESPONSE',
      status: 200,
      message: 'The server response did not match the pinned B649 contract.',
    })
    expect(fetchCalls).toBe(1)
    expect(requestedOffsets).toEqual([0])
  })

  it('AC03: empty page with unsatisfied total fails explicitly as MALFORMED_RESPONSE on first records request (initial empty page)', async () => {
    let fetchCalls = 0
    const requestedOffsets: number[] = []

    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
      const url = String(input)
      if (url.includes('/summary')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve(makeMockSummary(true, 10)),
        } as Response)
      }

      fetchCalls++
      const urlObj = new URL(url, 'http://localhost')
      requestedOffsets.push(Number(urlObj.searchParams.get('offset') ?? 0))

      return Promise.resolve({
        ok: true,
        status: 200,
        json: () =>
          Promise.resolve({
            items: [],
            total: 10, // total is 10, but server returned 0 items
            limit: 100,
            offset: 0,
            prefix_count: 10,
            window: 'FULL',
            criterion: 'M3_PLUS',
            research_disclaimer: RESEARCH_DISCLAIMER,
          }),
      } as Response)
    }))

    let resolvedResult: unknown = null
    let caughtError: unknown = null
    try {
      resolvedResult = await fetchReplayOverviewData('B649', 10, 'FULL')
    } catch (error) {
      caughtError = error
    }

    expect(resolvedResult).toBeNull()
    expect(caughtError).toBeInstanceOf(B649RecordsRequestError)
    expect(caughtError).toMatchObject({
      kind: 'MALFORMED_RESPONSE',
      status: 200,
      message: 'The server response did not match the pinned B649 contract.',
    })

    // Terminated immediately on the 1st records page request without looping or treating missing data as valid empty
    expect(fetchCalls).toBe(1)
    expect(requestedOffsets).toEqual([0])
  })

  it('AC03 & AC05: empty page with unsatisfied total fails mid-stream as MALFORMED_RESPONSE and does not claim COMPLETE or fabricate data', async () => {
    const totalRecords = 103
    const firstPageItems = Array.from({ length: 100 }, (_, idx) => makeMockRecord(idx + 1))
    let fetchCalls = 0
    const requestedOffsets: number[] = []

    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
      const url = String(input)
      if (url.includes('/summary')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve(makeMockSummary(true, totalRecords)),
        } as Response)
      }

      fetchCalls++
      const urlObj = new URL(url, 'http://localhost')
      const offset = Number(urlObj.searchParams.get('offset') ?? 0)
      requestedOffsets.push(offset)

      if (offset === 0) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () =>
            Promise.resolve({
              items: firstPageItems,
              total: totalRecords,
              limit: 100,
              offset: 0,
              prefix_count: 10,
              window: 'FULL',
              criterion: 'M3_PLUS',
              research_disclaimer: RESEARCH_DISCLAIMER,
            }),
        } as Response)
      }

      // Next request at offset 100 returns empty items even though 3 records remain
      return Promise.resolve({
        ok: true,
        status: 200,
        json: () =>
          Promise.resolve({
            items: [],
            total: totalRecords,
            limit: 100,
            offset: 100,
            prefix_count: 10,
            window: 'FULL',
            criterion: 'M3_PLUS',
            research_disclaimer: RESEARCH_DISCLAIMER,
          }),
      } as Response)
    }))

    let resolvedResult: unknown = null
    let caughtError: unknown = null
    try {
      resolvedResult = await fetchReplayOverviewData('B649', 10, 'FULL')
    } catch (error) {
      caughtError = error
    }

    expect(resolvedResult).toBeNull()
    expect(caughtError).toBeInstanceOf(B649RecordsRequestError)
    expect(caughtError).toMatchObject({
      kind: 'MALFORMED_RESPONSE',
      status: 200,
      message: 'The server response did not match the pinned B649 contract.',
    })

    // Bounded: terminated cleanly on the 2nd records request with no 3rd request
    expect(fetchCalls).toBe(2)
    expect(requestedOffsets).toEqual([0, 100])
  })

  it('AC04: legal empty catalog preserves valid empty results with fullUniverseStatus COMPLETE', async () => {
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
      const url = String(input)
      if (url.includes('/summary')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve(makeMockSummary(true, 0)),
        } as Response)
      }

      return Promise.resolve({
        ok: true,
        status: 200,
        json: () =>
          Promise.resolve({
            items: [],
            total: 0,
            limit: 100,
            offset: 0,
            prefix_count: 10,
            window: 'FULL',
            criterion: 'M3_PLUS',
            research_disclaimer: RESEARCH_DISCLAIMER,
          }),
      } as Response)
    }))

    const result = await fetchReplayOverviewData('B649', 10, 'FULL')
    expect(result.items).toEqual([])
    expect(result.summary.totalStrategies).toBe(0)
    expect(result.summary.rankedStrategies).toBe(0)
    expect(result.summary.topStrategy).toBeNull()
    expect(result.summary.isDimensionAvailable).toBe(true)
    expect(result.summary.fullUniverseStatus).toBe('COMPLETE')
  })

  it('AC04: multi-page catalog full progression preserves valid results', async () => {
    const totalRecords = 120
    const allRecords = Array.from({ length: totalRecords }, (_, idx) => makeMockRecord(idx + 1))
    const requestedOffsets: number[] = []

    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
      const url = String(input)
      if (url.includes('/summary')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve(makeMockSummary(true, totalRecords)),
        } as Response)
      }

      const urlObj = new URL(url, 'http://localhost')
      const offset = Number(urlObj.searchParams.get('offset') ?? 0)
      const limit = Number(urlObj.searchParams.get('limit') ?? 100)
      requestedOffsets.push(offset)

      const slice = allRecords.slice(offset, offset + limit)
      return Promise.resolve({
        ok: true,
        status: 200,
        json: () =>
          Promise.resolve({
            items: slice,
            total: totalRecords,
            limit,
            offset,
            prefix_count: 10,
            window: 'FULL',
            criterion: 'M3_PLUS',
            research_disclaimer: RESEARCH_DISCLAIMER,
          }),
      } as Response)
    }))

    const result = await fetchReplayOverviewData('B649', 10, 'FULL')
    expect(requestedOffsets).toEqual([0, 100])
    expect(result.items.length).toBe(120)
    expect(result.summary.totalStrategies).toBe(120)
    expect(result.summary.fullUniverseStatus).toBe('COMPLETE')
    expect(result.summary.topStrategy?.strategyId).toBe('strategy_1')
  })

  it('AC06: official missing metrics remain Unavailable and valid zero remains 0', async () => {
    const recordMissing = {
      ...makeMockRecord(1),
      official_any_prize_count: null,
      official_any_prize_rate: null,
      official_random_baseline_probability: null,
      official_random_baseline_delta: null,
      coverage: null,
      success_count: 50,
      historical_success_rate: '0.2500',
      random_baseline_success_rate: '0.1000',
      random_baseline_rate_difference: '0.1500',
    }

    const recordZero = {
      ...makeMockRecord(2),
      official_any_prize_count: 0,
      official_any_prize_rate: '0.0000',
      official_random_baseline_probability: '0.0780',
      official_random_baseline_delta: '-0.0780',
      coverage: '0.000',
    }

    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
      const url = String(input)
      if (url.includes('/summary')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve(makeMockSummary(true, 2)),
        } as Response)
      }

      return Promise.resolve({
        ok: true,
        status: 200,
        json: () =>
          Promise.resolve({
            items: [recordMissing, recordZero],
            total: 2,
            limit: 100,
            offset: 0,
            prefix_count: 10,
            window: 'FULL',
            criterion: 'M3_PLUS',
            research_disclaimer: RESEARCH_DISCLAIMER,
          }),
      } as Response)
    }))

    const result = await fetchReplayOverviewData('B649', 10, 'FULL')
    const itemMissing = result.items[0]
    const itemZero = result.items[1]

    // Missing values stay Unavailable, never fallback to M3_PLUS
    expect(itemMissing.officialAnyPrizeCount).toBeNull()
    expect(itemMissing.officialAnyPrizeRate).toBeNull()
    expect(itemMissing.officialAnyPrizeRateFormatted).toBe('Unavailable')
    expect(itemMissing.officialRandomBaselineProbabilityFormatted).toBe('Unavailable')
    expect(itemMissing.officialRandomBaselineDeltaFormatted).toBe('Unavailable')
    expect(itemMissing.coverageFormatted).toBe('Unavailable')
    expect(itemMissing.isAvailable).toBe(false)

    // Valid zero values stay 0.00% / 0%
    expect(itemZero.officialAnyPrizeCount).toBe(0)
    expect(itemZero.officialAnyPrizeRate).toBe(0)
    expect(itemZero.officialAnyPrizeRateFormatted).toBe('0.00%')
    expect(itemZero.coverage).toBe(0)
    expect(itemZero.coverageFormatted).toBe('0.0%')
    expect(itemZero.isAvailable).toBe(true)
  })

  it('AC07: B649 K10/K15/K20 dimension availability and P638/T539 unavailability semantics', () => {
    expect(isDimensionAvailable('B649', 10)).toBe(true)
    expect(isDimensionAvailable('B649', 15)).toBe(true)
    expect(isDimensionAvailable('B649', 20)).toBe(true)
    expect(isDimensionAvailable('B649', 5 as any)).toBe(false)

    expect(isDimensionAvailable('P638', 10)).toBe(false)
    expect(isDimensionAvailable('P638', 15)).toBe(false)
    expect(isDimensionAvailable('P638', 20)).toBe(false)

    expect(isDimensionAvailable('T539', 10)).toBe(false)
    expect(isDimensionAvailable('T539', 15)).toBe(false)
    expect(isDimensionAvailable('T539', 20)).toBe(false)
  })
})
