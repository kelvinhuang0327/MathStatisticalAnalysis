import { afterEach, describe, expect, it, vi } from 'vitest'

import { fetchRankingData, type RankingRow } from '../src/api/rankingMatrix'

const DISCLAIMER = '歷史成功率、排名與隨機基準差異僅供描述性研究，不構成未來預測、推薦、上線決策或中獎保證。'
const HASH = 'a'.repeat(64)

interface PageSlice {
  items: Record<string, unknown>[]
  total: number
}

type PageResponder = (offset: number, requestCount: number) => PageSlice
type PaginatedTicketCount = 2 | 3 | 20

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), { status, headers: { 'Content-Type': 'application/json' } })
}

function summary() {
  return {
    progress: {
      total_strategy_count: 3,
      reproduced_count: 3,
      backtested_count: 3,
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
    catalog_sha256: HASH,
    records_available: true,
    projection_sha256: HASH,
    source_report_count: 3,
    metrics_available_strategy_count: 3,
    metrics_unavailable_strategy_count: 0,
    primary_ranking_criterion: 'OFFICIAL_ANY_PRIZE',
    research_disclaimer: DISCLAIMER,
  }
}

function exactNativeRecord(ticketCount: 2 | 3, index: number): Record<string, unknown> {
  return {
    strategy_id: `exact-${index}`,
    strategy_version: 'v1',
    legacy_method_id: `exact-${index}`,
    source_path: `strategies/exact-${index}.py`,
    method_family: 'coldpool',
    reproduction_status: 'BACKTESTED',
    duplicate_alias_target: null,
    ticket_count: ticketCount,
    window: 'RECENT_300',
    criterion: 'OFFICIAL_ANY_PRIZE',
    metric_status: 'AVAILABLE',
    rankable: true,
    unavailable_reason: null,
    metrics_unavailable_reason: null,
    unranked_reason: 'RANKED_BACKTEST_EVIDENCE_AVAILABLE',
    official_any_prize_count: index,
    official_any_prize_rate: '0.100000000000000000',
    official_random_baseline_probability: '0.060000000000000000',
    official_random_baseline_delta: '0.040000000000000000',
    coverage: '1.000000000000000000',
    official_prize_counts: { first: 0, second: 0, third: 0, fourth: 0, fifth: 0, sixth: 0, seventh: 0, general: 0 },
    no_prize_count: 100 - index,
    available_observation_count: 100,
    effective_backtest_draw_count: 100,
    successful_observation_count: index,
    window_available_draws: 300,
    window_requested_draws: 300,
    window_complete: true,
    native_ticket_count_classification: 'FIXED_EXACT_NATIVE_TICKET_COUNT',
    authority_mode: 'FRESH_CURRENT_CATALOG_REPRODUCTION_V1',
    catalog_sha256: HASH,
    official_rank: null,
  }
}

function prefixRecord(index: number): Record<string, unknown> {
  return {
    strategy_id: `prefix-${index}`,
    strategy_version: 'v1',
    legacy_method_id: `prefix-${index}`,
    source_path: `strategies/prefix-${index}.py`,
    method_family: 'coldpool',
    reproduction_status: 'BACKTESTED',
    duplicate_alias_target: null,
    prefix_count: 20,
    window: 'RECENT_300',
    criterion: 'M3_PLUS',
    rank: index,
    official_rank: index,
    official_any_prize_count: index,
    official_any_prize_rate: '0.100000000000000000',
    official_random_baseline_probability: '0.060000000000000000',
    official_random_baseline_delta: '0.040000000000000000',
    unranked_reason: null,
    success_count: index,
    effective_backtest_draw_count: 100,
    successful_execution_count: 100,
    historical_success_rate: '0.100000000000000000',
    random_baseline_success_rate: '0.060000000000000000',
    random_baseline_rate_difference: '0.040000000000000000',
    coverage: '1.000000000000000000',
    window_available_draws: 300,
    window_requested_draws: 300,
    window_complete: true,
    official_prize_counts: { first: 0, second: 0, third: 0, fourth: 0, fifth: 0, sixth: 0, seventh: 0, general: 0 },
    no_prize_count: 100 - index,
    report_sha256: 'b'.repeat(64),
    report_file_sha256: 'c'.repeat(64),
    catalog_sha256: HASH,
  }
}

function recordsFor(ticketCount: PaginatedTicketCount): Record<string, unknown>[] {
  return ticketCount === 20
    ? [prefixRecord(1), prefixRecord(2), prefixRecord(3)]
    : [exactNativeRecord(ticketCount, 1), exactNativeRecord(ticketCount, 2), exactNativeRecord(ticketCount, 3)]
}

function installPageMock(ticketCount: PaginatedTicketCount, respond: PageResponder): number[] {
  const offsets: number[] = []
  let requestCount = 0

  vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockImplementation(async (input) => {
    const url = new URL(String(input), 'http://localhost')
    if (url.pathname === '/api/v1/b649-multi-ticket-records/summary') return jsonResponse(summary())
    if (url.pathname === '/api/v1/strategies') return jsonResponse([])

    const isExactNative = url.pathname === '/api/v1/b649-exact-native-records'
    const isPrefix = url.pathname === '/api/v1/b649-multi-ticket-records'
    if (
      (isExactNative && Number(url.searchParams.get('ticket_count')) === ticketCount) ||
      (isPrefix && Number(url.searchParams.get('prefix_count')) === ticketCount)
    ) {
      requestCount += 1
      if (requestCount > 3) throw new Error('Bounded pagination mock exceeded 3 record requests.')
      const offset = Number(url.searchParams.get('offset'))
      offsets.push(offset)
      const page = respond(offset, requestCount)
      const envelope = ticketCount === 20
        ? {
            total: page.total,
            limit: 100,
            offset,
            prefix_count: 20,
            window: 'RECENT_300',
            criterion: 'M3_PLUS',
            research_disclaimer: DISCLAIMER,
            items: page.items,
          }
        : {
            total: page.total,
            limit: 100,
            offset,
            ticket_count: ticketCount,
            window: 'RECENT_300',
            criterion: 'OFFICIAL_ANY_PRIZE',
            research_disclaimer: DISCLAIMER,
            items: page.items,
          }
      return jsonResponse(envelope)
    }

    throw new Error(`Unexpected Ranking Matrix request: ${url.pathname}`)
  }))

  return offsets
}

function strategyIds(rows: RankingRow[]): string[] {
  return rows.map((row) => row.strategyId)
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe.each([2, 3, 20] as const)('B649 K%s pagination guard', (ticketCount) => {
  it('advances by received items and preserves strategy order across partial pages', async () => {
    const records = recordsFor(ticketCount)
    const offsets = installPageMock(ticketCount, (offset) => {
      if (offset === 0) return { items: records.slice(0, 2), total: 3 }
      if (offset === 2) return { items: records.slice(2), total: 3 }
      return { items: [], total: 3 }
    })

    const rows = await fetchRankingData('BIG_LOTTO', ticketCount, 'RECENT_300').catch(() => null)

    expect(offsets).toEqual([0, 2])
    expect(rows).not.toBeNull()
    if (rows === null) return
    expect(rows).toHaveLength(3)
    expect(strategyIds(rows)).toEqual(records.map((record) => String(record.strategy_id)))
    expect(rows.map((row) => row.officialRank)).toEqual(ticketCount === 20 ? [1, 2, 3] : [null, null, null])
  })

  it('fails closed when a page is empty before total is complete', async () => {
    const records = recordsFor(ticketCount)
    const offsets = installPageMock(ticketCount, (offset) => (
      offset === 0 ? { items: records.slice(0, 1), total: 3 } : { items: [], total: 3 }
    ))

    const error = await fetchRankingData('BIG_LOTTO', ticketCount, 'RECENT_300').catch((value: unknown) => value)

    expect(offsets).toEqual([0, 1])
    expect(error).toBeInstanceOf(Error)
    expect((error as Error).message).toBe(ticketCount === 20 ? 'Incomplete K20 prefix page' : 'Incomplete K2/K3 exact-native page')
  })

  it('preserves one-page and genuinely empty results', async () => {
    const records = recordsFor(ticketCount)
    const singlePageOffsets = installPageMock(ticketCount, () => ({ items: records.slice(0, 2), total: 2 }))

    const singlePageRows = await fetchRankingData('BIG_LOTTO', ticketCount, 'RECENT_300')
    expect(singlePageOffsets).toEqual([0])
    expect(singlePageRows).toHaveLength(2)
    expect(strategyIds(singlePageRows)).toEqual(records.slice(0, 2).map((record) => String(record.strategy_id)))

    vi.unstubAllGlobals()
    const emptyPageOffsets = installPageMock(ticketCount, () => ({ items: [], total: 0 }))

    await expect(fetchRankingData('BIG_LOTTO', ticketCount, 'RECENT_300')).resolves.toEqual([])
    expect(emptyPageOffsets).toEqual([0])
  })
})
