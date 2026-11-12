import { afterEach, describe, expect, it, vi } from 'vitest'
import recordedCapture from './fixtures/replay-441-period-date-http.json'
import { listReplayBackfillPredictions } from '../src/api/replayBackfill'

type RecordedResponse = {
  name: string
  method: string
  path: string
  query: Record<string, string>
  status_code: number
  raw_body: string
}

type RecordedCapture = {
  provenance: {
    fixture: {
      draw_order: Array<{
        target_draw_number: string
        target_draw_date: string
      }>
    }
  }
  responses: RecordedResponse[]
}

const capture = recordedCapture as RecordedCapture

function canonicalQuery(query: Record<string, string>): string {
  return JSON.stringify(Object.entries(query).sort(([left], [right]) => left.localeCompare(right)))
}

function installRecordedFetch() {
  const matchedResponses: string[] = []
  const requests: Array<{ method: string; path: string; query: Record<string, string> }> = []
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input), 'http://localhost')
    const method = init?.method ?? 'GET'
    const query = Object.fromEntries(url.searchParams.entries())
    const recorded = capture.responses.find(
      (response) =>
        response.method === method &&
        response.path === url.pathname &&
        canonicalQuery(response.query) === canonicalQuery(query),
    )

    if (!recorded) {
      throw new Error(`No recorded response for ${method} ${url.pathname}?${url.searchParams.toString()}`)
    }

    matchedResponses.push(recorded.name)
    requests.push({ method, path: url.pathname, query })
    return {
      ok: recorded.status_code >= 200 && recorded.status_code < 300,
      status: recorded.status_code,
      json: async () => JSON.parse(recorded.raw_body),
    } as unknown as Response
  })

  vi.stubGlobal('fetch', fetchMock)
  return { matchedResponses, requests }
}

const drawOrder = capture.provenance.fixture.draw_order
const drawNumbers = drawOrder.map((draw) => draw.target_draw_number)

describe('Replay Backfill period, date, and cursor contract', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('uses unique target draws for 50, 300, 750, and ALL', async () => {
    const { matchedResponses, requests } = installRecordedFetch()
    const expectedByPeriod = new Map([
      [50, drawNumbers.slice(-50)],
      [300, drawNumbers],
      [750, drawNumbers],
      ['ALL', drawNumbers],
    ])

    for (const [period, expectedTargets] of expectedByPeriod) {
      const page = await listReplayBackfillPredictions({
        lotteryType: 'BIG_LOTTO',
        strategyId: 'fixture-biglotto-native',
        period: period as 50 | 300 | 750 | 'ALL',
        limit: 100,
      })

      expect(page.total_count).toBe(expectedTargets.length)
      expect(page.items.map((item) => item.target_draw_number)).toEqual(expectedTargets)
      expect(new Set(page.items.map((item) => item.target_draw_number)).size).toBe(expectedTargets.length)
    }

    expect(matchedResponses).toEqual(['period_50', 'period_300', 'period_750', 'period_ALL'])
    expect(requests.map((request) => request.path)).toEqual(
      Array(4).fill('/api/v1/replay-backfill/predictions'),
    )
  })

  it('sends inclusive date bounds and excludes targets outside each range', async () => {
    const { matchedResponses, requests } = installRecordedFetch()
    const februaryTargets = drawOrder
      .filter((draw) => draw.target_draw_date >= '2026-02-01' && draw.target_draw_date <= '2026-02-22')
      .map((draw) => draw.target_draw_number)

    const february = await listReplayBackfillPredictions({
      lotteryType: 'BIG_LOTTO',
      strategyId: 'fixture-biglotto-native',
      period: 'ALL',
      limit: 100,
      fromDate: '2026-02-01',
      toDate: '2026-02-22',
    })
    const finalDay = await listReplayBackfillPredictions({
      lotteryType: 'BIG_LOTTO',
      strategyId: 'fixture-biglotto-native',
      period: 'ALL',
      limit: 100,
      fromDate: '2026-02-22',
      toDate: '2026-02-22',
    })

    expect(february.total_count).toBe(22)
    expect(february.items.map((item) => item.target_draw_number)).toEqual(februaryTargets)
    expect(february.items.every((item) => item.target_draw_date >= '2026-02-01' && item.target_draw_date <= '2026-02-22')).toBe(true)
    expect(finalDay.total_count).toBe(1)
    expect(finalDay.items.map((item) => item.target_draw_number)).toEqual(['202600053'])
    expect(matchedResponses).toEqual(['date_2026-02-01_to_2026-02-22', 'date_2026-02-22_only'])
    expect(requests.map((request) => request.query.from_date)).toEqual(['2026-02-01', '2026-02-22'])
    expect(requests.map((request) => request.query.to_date)).toEqual(['2026-02-22', '2026-02-22'])
  })

  it('follows the API next_cursor across all pages without repeats or omissions', async () => {
    const { matchedResponses, requests } = installRecordedFetch()
    const query = {
      lotteryType: 'BIG_LOTTO' as const,
      strategyId: 'fixture-biglotto-native',
      period: 'ALL' as const,
      limit: 20,
    }
    const first = await listReplayBackfillPredictions(query)
    if (typeof first.next_cursor !== 'string') throw new Error('Expected the API to return page two cursor')
    const second = await listReplayBackfillPredictions({ ...query, cursor: first.next_cursor })
    if (typeof second.next_cursor !== 'string') throw new Error('Expected the API to return page three cursor')
    const third = await listReplayBackfillPredictions({ ...query, cursor: second.next_cursor })

    const pages = [first, second, third]
    const pageTargets = pages.flatMap((page) => page.items.map((item) => item.target_draw_number))
    expect(pages.map((page) => page.items.length)).toEqual([20, 20, 13])
    expect(third.next_cursor).toBeNull()
    expect(pageTargets).toEqual(drawNumbers)
    expect(new Set(pageTargets).size).toBe(53)
    expect(matchedResponses).toEqual(['cursor_page_1', 'cursor_page_2', 'cursor_page_3'])
    expect(requests[1].query.cursor).toBe(first.next_cursor)
    expect(requests[2].query.cursor).toBe(second.next_cursor)
  })

  it('keeps target denominators and leaves empty or short windows without a hit rate', async () => {
    const { matchedResponses } = installRecordedFetch()
    const fifty = await listReplayBackfillPredictions({
      lotteryType: 'BIG_LOTTO',
      strategyId: 'fixture-biglotto-native',
      period: 50,
      limit: 100,
    })
    const short750 = await listReplayBackfillPredictions({
      lotteryType: 'BIG_LOTTO',
      strategyId: 'fixture-biglotto-native',
      period: 750,
      limit: 100,
    })
    const empty = await listReplayBackfillPredictions({
      lotteryType: 'BIG_LOTTO',
      strategyId: 'fixture-biglotto-native',
      period: 'ALL',
      limit: 100,
      fromDate: '2025-12-01',
      toDate: '2025-12-31',
    })

    const ticketCount = fifty.items.reduce((count, item) => count + item.predicted_tickets.length, 0)
    expect(fifty.total_count).toBe(50)
    expect(ticketCount).toBe(150)
    expect(short750.total_count).toBe(53)
    expect(short750.items).toHaveLength(53)
    expect(empty.total_count).toBe(0)
    expect(empty.items).toEqual([])
    for (const page of [fifty, short750, empty]) {
      expect(Object.prototype.hasOwnProperty.call(page, 'hit_rate')).toBe(false)
    }
    expect(matchedResponses).toEqual(['period_50', 'period_750', 'date_empty_before_fixture'])
  })
})
