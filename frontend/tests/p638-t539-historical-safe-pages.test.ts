import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  listP638Draws,
  listP638Replay,
  listP638Runs,
  listP638Strategies,
  P638HistoricalRequestError,
} from '../src/api/p638Historical'
import {
  listT539Draws,
  listT539Runs,
  listT539Strategies,
} from '../src/api/t539Historical'

type PageQuery = { limit: number; offset: number }
type PageField = 'total_count' | 'limit' | 'offset'
type PagePayload = Record<string, unknown> & {
  items: unknown[]
  total_count: number
  limit: number
  offset: number
}
type PageCall = {
  label: string
  errorName: string
  url: string
  invoke: (query: PageQuery) => Promise<unknown>
  payload: () => PagePayload
}

const SAFE_MAX = 9007199254740991
const UNSAFE = 9007199254740992

let fetchMock: ReturnType<typeof vi.fn<typeof fetch>>

function apiResponse(payload: unknown, status = 200): Response {
  return {
    ok: status < 400,
    status,
    json: vi.fn().mockResolvedValue(payload),
  } as unknown as Response
}

function pagePayload(
  item: Record<string, unknown>,
  runId?: string,
  overrides: Partial<Record<PageField, unknown>> = {},
): PagePayload {
  return {
    ...(runId ? { run_id: runId } : {}),
    items: [item],
    total_count: 1,
    limit: 25,
    offset: 0,
    ...overrides,
  } as PagePayload
}

const PAGE_CALLS: PageCall[] = [
  {
    label: 'P638 runs',
    errorName: 'P638HistoricalRequestError',
    url: '/api/v1/p638-historical/runs?limit=25&offset=0',
    invoke: (query) => listP638Runs(query),
    payload: () => pagePayload({ run_id: 'run-p638-1', status: 'COMPLETE' }),
  },
  {
    label: 'P638 strategies',
    errorName: 'P638HistoricalRequestError',
    url: '/api/v1/p638-historical/runs/run-p638-1/strategies?limit=25&offset=0',
    invoke: (query) => listP638Strategies('run-p638-1', query),
    payload: () =>
      pagePayload({ strategy_id: 'p638-strategy-1', replay_status: 'COMPLETE' }, 'run-p638-1'),
  },
  {
    label: 'P638 draws',
    errorName: 'P638HistoricalRequestError',
    url: '/api/v1/p638-historical/runs/run-p638-1/draws?limit=25&offset=0',
    invoke: (query) => listP638Draws('run-p638-1', query),
    payload: () =>
      pagePayload(
        {
          draw_number: '1',
          draw_date: '2026-01-01',
          winning_zone1_numbers: [1, 2, 3, 4, 5, 6],
          winning_zone2_number: 1,
        },
        'run-p638-1',
      ),
  },
  {
    label: 'P638 replay',
    errorName: 'P638HistoricalRequestError',
    url: '/api/v1/p638-historical/runs/run-p638-1/replay?limit=25&offset=0',
    invoke: (query) => listP638Replay('run-p638-1', query),
    payload: () =>
      pagePayload({ target_id: 'draw-1', strategy_id: 'p638-strategy-1', tickets: [] }, 'run-p638-1'),
  },
  {
    label: 'T539 runs',
    errorName: 'T539HistoricalRequestError',
    url: '/api/v1/t539-historical/runs?limit=25&offset=0',
    invoke: (query) => listT539Runs(query),
    payload: () =>
      pagePayload({ run_id: 'run-t539-1', status: 'COMPLETE', lottery_type: 'DAILY_539' }),
  },
  {
    label: 'T539 strategies',
    errorName: 'T539HistoricalRequestError',
    url: '/api/v1/t539-historical/runs/run-t539-1/strategies?limit=25&offset=0',
    invoke: (query) => listT539Strategies('run-t539-1', query),
    payload: () =>
      pagePayload(
        { strategy_id: 't539-strategy-1', status: 'SUCCESS', hit_distribution: [] },
        'run-t539-1',
      ),
  },
  {
    label: 'T539 draws',
    errorName: 'T539HistoricalRequestError',
    url: '/api/v1/t539-historical/runs/run-t539-1/draws?limit=25&offset=0',
    invoke: (query) => listT539Draws('run-t539-1', query),
    payload: () =>
      pagePayload(
        { draw_id: 'draw-1', draw_date: '2026-01-01', winning_numbers: [1, 2, 3, 4, 5] },
        'run-t539-1',
      ),
  },
]

beforeEach(() => {
  fetchMock = vi.fn<typeof fetch>()
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => vi.unstubAllGlobals())

describe('P638 and T539 historical safe page integers', () => {
  describe('baseline regression: unsafe page fields must be malformed', () => {
    const baselineCases = PAGE_CALLS.filter((call) => call.label.endsWith('runs')).flatMap((call) =>
      (['total_count', 'limit', 'offset'] as const).map((field) => ({ call, field })),
    )

    it.each(baselineCases)('$call.label rejects unsafe $field', async ({ call, field }) => {
      const payload = call.payload()
      payload[field] = UNSAFE
      fetchMock.mockResolvedValue(apiResponse(payload))

      await expect(call.invoke({ limit: 25, offset: 0 })).rejects.toMatchObject({
        name: call.errorName,
        kind: 'MALFORMED_RESPONSE',
      })
    })
  })

  it.each(PAGE_CALLS)('$label rejects unsafe, negative, fractional, and non-finite page fields', async (call) => {
    const invalidNumbers = [UNSAFE, -1, 1.5, Number.NaN, Number.POSITIVE_INFINITY]

    for (const field of ['total_count', 'limit', 'offset'] as const) {
      for (const value of invalidNumbers) {
        const payload = call.payload()
        payload[field] = value
        fetchMock.mockResolvedValue(apiResponse(payload))

        await expect(call.invoke({ limit: 25, offset: 0 })).rejects.toMatchObject({
          name: call.errorName,
          kind: 'MALFORMED_RESPONSE',
        })
        fetchMock.mockClear()
      }
    }
  })

  it.each(PAGE_CALLS)('$label accepts the largest safe total_count exactly', async (call) => {
    const payload = call.payload()
    payload.total_count = SAFE_MAX
    fetchMock.mockResolvedValue(apiResponse(payload))

    await expect(call.invoke({ limit: 25, offset: 0 })).resolves.toMatchObject({
      total_count: SAFE_MAX,
    })
  })

  it.each(PAGE_CALLS)('$label preserves a valid empty page and its GET URL', async (call) => {
    const payload = { ...call.payload(), items: [], total_count: 0, limit: 25, offset: 0 }
    fetchMock.mockResolvedValue(apiResponse(payload))

    await expect(call.invoke({ limit: 25, offset: 0 })).resolves.toEqual(payload)
    expect(fetchMock).toHaveBeenCalledWith(call.url, { signal: undefined })
  })

  it.each(PAGE_CALLS.filter((call) => call.label.endsWith('runs')))(
    '$label keeps null distinct from an empty page',
    async (call) => {
      fetchMock.mockResolvedValue(apiResponse(null))
      await expect(call.invoke({ limit: 25, offset: 0 })).rejects.toMatchObject({
        name: call.errorName,
        kind: 'MALFORMED_RESPONSE',
      })

      const emptyPage = { items: [], total_count: 0, limit: 25, offset: 0 }
      fetchMock.mockResolvedValue(apiResponse(emptyPage))
      await expect(call.invoke({ limit: 25, offset: 0 })).resolves.toEqual(emptyPage)
    },
  )

  it.each(PAGE_CALLS)('$label rejects invalid query integers before fetch', async (call) => {
    const invalidQueries: PageQuery[] = [
      { limit: UNSAFE, offset: 0 },
      { limit: 1.5, offset: 0 },
      { limit: Number.NaN, offset: 0 },
      { limit: Number.POSITIVE_INFINITY, offset: 0 },
      { limit: 0, offset: 0 },
      { limit: -1, offset: 0 },
      { limit: 25, offset: UNSAFE },
      { limit: 25, offset: 1.5 },
      { limit: 25, offset: Number.NaN },
      { limit: 25, offset: Number.POSITIVE_INFINITY },
      { limit: 25, offset: -1 },
    ]

    for (const query of invalidQueries) {
      await expect(call.invoke(query)).rejects.toMatchObject({
        name: call.errorName,
        kind: 'INVALID_REQUEST',
      })
      expect(fetchMock).not.toHaveBeenCalled()
    }
  })

  it('retains P638 404, 422, 503, and AbortError behavior', async () => {
    fetchMock.mockResolvedValue(apiResponse({ message: 'missing' }, 404))
    await expect(listP638Runs({ limit: 25, offset: 0 })).rejects.toMatchObject({
      name: P638HistoricalRequestError.name,
      kind: 'NOT_FOUND',
      status: 404,
    })

    fetchMock.mockResolvedValue(apiResponse({ message: 'invalid' }, 422))
    await expect(listP638Runs({ limit: 25, offset: 0 })).rejects.toMatchObject({
      kind: 'INVALID_REQUEST',
      status: 422,
    })

    fetchMock.mockResolvedValue(apiResponse({ error_code: 'P638_HISTORICAL_NOT_CONFIGURED' }, 503))
    await expect(listP638Runs({ limit: 25, offset: 0 })).rejects.toMatchObject({
      kind: 'NOT_CONFIGURED',
      status: 503,
    })

    fetchMock.mockResolvedValue(apiResponse({ message: 'unavailable' }, 503))
    await expect(listP638Runs({ limit: 25, offset: 0 })).rejects.toMatchObject({
      kind: 'UNAVAILABLE',
      status: 503,
    })

    fetchMock.mockRejectedValue(new DOMException('aborted', 'AbortError'))
    await expect(listP638Runs({ limit: 25, offset: 0 })).rejects.toMatchObject({
      name: 'AbortError',
    })
  })
})
