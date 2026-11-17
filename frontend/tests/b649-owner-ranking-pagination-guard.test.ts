import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import * as recordsApi from '../src/api/b649MultiTicketRecords'
import {
  B649_HISTORY_WINDOWS,
  B649_PREFIX_COUNTS,
  B649RecordsRequestError,
  type B649MultiTicketRecord,
  type B649MultiTicketRecordPage,
  type B649MultiTicketRecordQuery,
} from '../src/api/b649MultiTicketRecords'
import { fetchB649OwnerRankingData } from '../src/api/b649OwnerRanking'

const PAGE_SIZE = 100
const TARGET = { prefixCount: 5, window: 'FULL' as const }

function record(query: B649MultiTicketRecordQuery, offset: number, index: number) {
  return {
    strategy_id: `${query.prefixCount}:${query.window}:${offset + index}`,
    strategy_version: `fixture-${query.prefixCount}-${query.window}`,
    legacy_method_id: `method-${query.prefixCount}-${query.window}`,
    source_path: `fixture/${query.prefixCount}-${query.window}.json`,
    method_family: 'statistical',
    reproduction_status: 'BACKTESTED',
    duplicate_alias_target: null,
    prefix_count: query.prefixCount,
    window: query.window,
    criterion: query.criterion,
    rank: offset + index + 1,
    official_rank: offset + index + 1,
    official_any_prize_count: offset + index,
    official_any_prize_rate: `rate-${offset + index}`,
    official_random_baseline_probability: 'baseline-unchanged',
    official_random_baseline_delta: 'delta-unchanged',
    unranked_reason: null,
    success_count: offset + index,
    effective_backtest_draw_count: offset + index,
    successful_execution_count: offset + index,
    historical_success_rate: 'history-unchanged',
    random_baseline_success_rate: 'random-unchanged',
    random_baseline_rate_difference: 'difference-unchanged',
    coverage: 'coverage-unchanged',
    window_available_draws: 2149,
    window_requested_draws: 2149,
    window_complete: true,
    official_prize_counts: null,
    no_prize_count: 0,
    report_sha256: 'a'.repeat(64),
    report_file_sha256: 'b'.repeat(64),
    catalog_sha256: 'c'.repeat(64),
  } as unknown as B649MultiTicketRecord
}

function page(
  query: B649MultiTicketRecordQuery,
  total: number,
  offset: number,
  overrides: Partial<B649MultiTicketRecordPage> = {},
): B649MultiTicketRecordPage {
  const count = Math.max(0, Math.min(PAGE_SIZE, total - offset))
  return {
    items: Array.from({ length: count }, (_, index) => record(query, offset, index)),
    total,
    limit: PAGE_SIZE,
    offset,
    prefix_count: query.prefixCount,
    window: query.window,
    criterion: query.criterion,
    research_disclaimer: recordsApi.B649_RESEARCH_DISCLAIMER,
    ...overrides,
  } as B649MultiTicketRecordPage
}

function isTarget(query: B649MultiTicketRecordQuery): boolean {
  return query.prefixCount === TARGET.prefixCount && query.window === TARGET.window
}

function emptyPage(query: B649MultiTicketRecordQuery) {
  return page(query, 0, 0)
}

beforeEach(() => {
  vi.spyOn(recordsApi, 'fetchB649MultiTicketSummary').mockResolvedValue({
    records_available: true,
  } as recordsApi.B649MultiTicketSummary)
  vi.spyOn(recordsApi, 'fetchB649MultiTicketRecords').mockImplementation(async (query) =>
    emptyPage(query),
  )
})

afterEach(() => vi.restoreAllMocks())

describe('fetchB649OwnerRankingData pagination guards', () => {
  it('collects all 16 dense M3_PLUS slices in request order despite out-of-order page completion', async () => {
    const totals = [230, 0, 1, 100, 135, 99, 101, 200, 2, 130, 100, 1, 0, 4, 101, 100]
    const expectedBySlice = new Map<string, Map<number, B649MultiTicketRecord[]>>()
    const completionOrder: string[] = []
    let firstPageCount = 0

    vi.mocked(recordsApi.fetchB649MultiTicketRecords).mockImplementation(async (query) => {
      const index = B649_PREFIX_COUNTS.indexOf(query.prefixCount) * B649_HISTORY_WINDOWS.length
        + B649_HISTORY_WINDOWS.indexOf(query.window)
      const total = totals[index]
      const response = page(query, total, query.offset)
      const key = `${query.prefixCount}:${query.window}`

      if (isTarget(query) && query.offset === 100) {
        await new Promise((resolve) => setTimeout(resolve, 25))
      }
      completionOrder.push(`${key}:${query.offset}`)
      const pages = expectedBySlice.get(key) ?? new Map<number, B649MultiTicketRecord[]>()
      pages.set(query.offset, response.items)
      expectedBySlice.set(key, pages)
      if (query.offset === 0) firstPageCount += 1
      return response
    })

    const result = await fetchB649OwnerRankingData()
    const expectedRows = B649_PREFIX_COUNTS.flatMap((prefixCount) =>
      B649_HISTORY_WINDOWS.flatMap((window) => {
        const pages = expectedBySlice.get(`${prefixCount}:${window}`) ?? new Map()
        return [...pages.entries()]
          .sort(([left], [right]) => left - right)
          .flatMap(([, rows]) => rows)
      }),
    )

    expect(firstPageCount).toBe(16)
    expect(result.records).toEqual(expectedRows)
    expect(result.records).toHaveLength(totals.reduce((sum, total) => sum + total, 0))
    expect(completionOrder.indexOf('5:FULL:200')).toBeLessThan(
      completionOrder.indexOf('5:FULL:100'),
    )

    const firstPageCalls = vi.mocked(recordsApi.fetchB649MultiTicketRecords).mock.calls
      .map(([query]) => query)
      .filter((query) => query.offset === 0)
    expect(firstPageCalls).toHaveLength(16)
    expect(new Set(firstPageCalls.map((query) => `${query.prefixCount}:${query.window}:${query.criterion}`)).size)
      .toBe(16)
    expect(firstPageCalls.every((query) => query.criterion === 'M3_PLUS' && query.limit === PAGE_SIZE))
      .toBe(true)

    for (let index = 0; index < 16; index += 1) {
      const prefixCount = B649_PREFIX_COUNTS[Math.floor(index / 4)]
      const window = B649_HISTORY_WINDOWS[index % 4]
      const expectedTotal = totals[index]
      const offsets = vi.mocked(recordsApi.fetchB649MultiTicketRecords).mock.calls
        .map(([query]) => query)
        .filter((query) => query.prefixCount === prefixCount && query.window === window)
        .map((query) => query.offset)
      expect(offsets).toEqual(
        Array.from(
          { length: Math.max(1, Math.ceil(expectedTotal / PAGE_SIZE)) },
          (_, pageIndex) => pageIndex * PAGE_SIZE,
        ),
      )
    }

    const boundaryPages = expectedBySlice.get('10:FULL') ?? new Map()
    expect(
      [...boundaryPages.entries()]
        .sort(([left], [right]) => left - right)
        .map(([offset, rows]) => [offset, rows.length]),
    ).toEqual([[0, 100], [100, 35]])
  })

  it('rejects a later page whose response offset differs from the requested offset', async () => {
    vi.mocked(recordsApi.fetchB649MultiTicketRecords).mockImplementation(async (query) => {
      const response = page(query, isTarget(query) ? 101 : 0, query.offset)
      return isTarget(query) && query.offset === 100
        ? { ...response, offset: 99 }
        : response
    })

    await expect(fetchB649OwnerRankingData()).rejects.toThrow(/offset/i)
  })

  it('rejects a page whose response limit differs from the requested limit', async () => {
    vi.mocked(recordsApi.fetchB649MultiTicketRecords).mockImplementation(async (query) => {
      const response = page(query, isTarget(query) ? 101 : 0, query.offset)
      return isTarget(query) && query.offset === 100
        ? { ...response, limit: 99 }
        : response
    })

    await expect(fetchB649OwnerRankingData()).rejects.toThrow(/limit/i)
  })

  it('rejects a later page whose total changes during the same slice', async () => {
    vi.mocked(recordsApi.fetchB649MultiTicketRecords).mockImplementation(async (query) => {
      const response = page(query, isTarget(query) ? 101 : 0, query.offset)
      return isTarget(query) && query.offset === 100
        ? { ...response, total: 102 }
        : response
    })

    await expect(fetchB649OwnerRankingData()).rejects.toThrow(/total/i)
  })

  it.each([
    ['prefix_count', { prefix_count: 10 }],
    ['window', { window: 'RECENT_50' }],
    ['criterion', { criterion: 'M4_PLUS' }],
  ] as const)('rejects a later page with a mismatched %s identity', async (_name, identity) => {
    vi.mocked(recordsApi.fetchB649MultiTicketRecords).mockImplementation(async (query) => {
      const response = page(query, isTarget(query) ? 101 : 0, query.offset)
      return isTarget(query) && query.offset === 100
        ? { ...response, ...identity }
        : response
    })

    await expect(fetchB649OwnerRankingData()).rejects.toThrow(/identity/i)
  })

  it('rejects a short first page instead of advancing from its returned item count', async () => {
    vi.mocked(recordsApi.fetchB649MultiTicketRecords).mockImplementation(async (query) => {
      if (isTarget(query) && query.offset === 0) {
        const response = page(query, 101, 0)
        return { ...response, items: response.items.slice(0, 99) }
      }
      return page(query, isTarget(query) ? 101 : 0, query.offset)
    })

    await expect(fetchB649OwnerRankingData()).rejects.toThrow(/item count/i)
  })

  it('rejects a short middle page', async () => {
    vi.mocked(recordsApi.fetchB649MultiTicketRecords).mockImplementation(async (query) => {
      const response = page(query, isTarget(query) ? 230 : 0, query.offset)
      return isTarget(query) && query.offset === 100
        ? { ...response, items: response.items.slice(0, 99) }
        : response
    })

    await expect(fetchB649OwnerRankingData()).rejects.toThrow(/item count/i)
  })

  it('rejects an empty page while the requested offset is still below total', async () => {
    vi.mocked(recordsApi.fetchB649MultiTicketRecords).mockImplementation(async (query) => {
      const response = page(query, isTarget(query) ? 230 : 0, query.offset)
      return isTarget(query) && query.offset === 100
        ? { ...response, items: [] }
        : response
    })

    await expect(fetchB649OwnerRankingData()).rejects.toThrow(/item count/i)
  })

  it.each([
    new B649RecordsRequestError('invalid request', 422, 'INVALID_REQUEST'),
    new B649RecordsRequestError('temporarily unavailable', 503, 'UNAVAILABLE'),
    new B649RecordsRequestError('network failure', 0, 'NETWORK'),
  ])('preserves API request errors unchanged', async (error) => {
    vi.mocked(recordsApi.fetchB649MultiTicketRecords).mockRejectedValue(error)

    await expect(fetchB649OwnerRankingData()).rejects.toBe(error)
  })

  it('preserves AbortSignal cancellation unchanged', async () => {
    const controller = new AbortController()
    const abortError = new DOMException('Aborted', 'AbortError')
    vi.mocked(recordsApi.fetchB649MultiTicketRecords).mockRejectedValue(abortError)

    await expect(fetchB649OwnerRankingData(controller.signal)).rejects.toBe(abortError)
    expect(recordsApi.fetchB649MultiTicketSummary).toHaveBeenCalledWith(controller.signal)
    expect(
      vi.mocked(recordsApi.fetchB649MultiTicketRecords).mock.calls.every(
        ([, signal]) => signal === controller.signal,
      ),
    ).toBe(true)
  })
})
