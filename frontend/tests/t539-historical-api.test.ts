import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  getT539Coverage,
  getT539Metrics,
  getT539Rankings,
  listT539Runs,
  listT539Strategies,
  T539HistoricalRequestError,
} from '../src/api/t539Historical'

let fetchMock: ReturnType<typeof vi.fn<typeof fetch>>

function apiResponse(payload: unknown, status = 200): Response {
  return {
    ok: status < 400,
    status,
    json: vi.fn().mockResolvedValue(payload),
  } as unknown as Response
}

function makeRun(overrides: Partial<Record<string, unknown>> = {}): Record<string, unknown> {
  return {
    run_id: 'run-t539-1',
    schema_version: 'v1',
    lottery_type: 'DAILY_539',
    source_endpoint: 'https://example.invalid/t539',
    source_sha256: 'a'.repeat(64),
    as_of_date: '2026-08-01',
    adapter_source_commit: 'b'.repeat(40),
    status: 'COMPLETE',
    strategy_count: 8,
    draw_count: 100,
    eligible_target_count: 90,
    ticket_count: 900,
    failure_count: 0,
    first_draw_id: 'draw-1',
    first_draw_date: '2020-01-01',
    last_draw_id: 'draw-100',
    last_draw_date: '2026-07-30',
    ...overrides,
  }
}

function makeStrategy(overrides: Partial<Record<string, unknown>> = {}): Record<string, unknown> {
  return {
    run_id: 'run-t539-1',
    strategy_id: 't539_strategy_one',
    strategy_version: 'v1',
    native_ticket_count: 1,
    min_history: 30,
    first_eligible_target_draw_id: 'draw-31',
    expected_target_draw_count: 90,
    processed_target_draw_count: 90,
    successful_target_draw_count: 90,
    failed_target_draw_count: 0,
    status: 'SUCCESS',
    ticket_count: 90,
    winning_ticket_count: 9,
    hit_distribution: [{ value: 3, count: 9 }],
    first_target_draw_date: '2020-02-01',
    last_target_draw_date: '2026-07-30',
    ...overrides,
  }
}

function makeMetrics(overrides: Partial<Record<string, unknown>> = {}): Record<string, unknown> {
  return {
    run_id: 'run-t539-1',
    strategy_id: null,
    target_count: 90,
    ticket_count: 900,
    winning_ticket_count: 72,
    winning_target_count: 60,
    hit_distribution: [{ value: 3, count: 60 }],
    prize_tier_counts: [{ prize_tier: 'sixth', count: 60 }],
    first_target_draw_date: '2020-02-01',
    last_target_draw_date: '2026-07-30',
    ...overrides,
  }
}

function makeRanking(overrides: Partial<Record<string, unknown>> = {}): Record<string, unknown> {
  return {
    run_id: 'run-t539-1',
    rank: 1,
    strategy_id: 't539_strategy_one',
    strategy_version: 'v1',
    native_ticket_count: 1,
    eligible_target_count: 90,
    winning_target_count: 60,
    winning_target_rate: 0.6667,
    total_ticket_count: 90,
    winning_ticket_count: 72,
    ticket_winning_rate: 0.8,
    prize_tier_counts: [{ prize_tier: 'sixth', count: 60 }],
    highest_prize_tier_achieved: 'sixth',
    first_eligible_draw: 'draw-31',
    last_eligible_draw: 'draw-100',
    prize_rule_version: 'v1',
    prize_rule_provenance: 'fixture',
    ...overrides,
  }
}

beforeEach(() => {
  fetchMock = vi.fn<typeof fetch>()
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => vi.unstubAllGlobals())

describe('T539 Historical API client', () => {
  it('lists runs with the exact limit and offset query parameters', async () => {
    fetchMock.mockResolvedValue(
      apiResponse({ items: [makeRun()], total_count: 1, limit: 25, offset: 0 }),
    )

    const page = await listT539Runs({ limit: 25, offset: 0 })

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/t539-historical/runs?limit=25&offset=0',
      expect.objectContaining({}),
    )
    expect(page.items[0]?.run_id).toBe('run-t539-1')
    expect(page.items[0]?.lottery_type).toBe('DAILY_539')
  })

  it('URL-encodes the run id when listing strategies', async () => {
    fetchMock.mockResolvedValue(
      apiResponse({ run_id: 'run a/b', items: [makeStrategy({ run_id: 'run a/b' })], total_count: 1, limit: 100, offset: 0 }),
    )

    const page = await listT539Strategies('run a/b', { limit: 100, offset: 0 })

    const url = String(fetchMock.mock.calls[0]?.[0])
    expect(url).toBe('/api/v1/t539-historical/runs/run%20a%2Fb/strategies?limit=100&offset=0')
    expect(page.items).toHaveLength(1)
  })

  it('omits the strategy_id query parameter for run-level metrics', async () => {
    fetchMock.mockResolvedValue(apiResponse(makeMetrics()))

    await getT539Metrics('run-t539-1', undefined)

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/t539-historical/runs/run-t539-1/metrics',
      expect.objectContaining({}),
    )
  })

  it('includes the strategy_id query parameter for strategy-scoped metrics', async () => {
    fetchMock.mockResolvedValue(apiResponse(makeMetrics({ strategy_id: 't539_strategy_one' })))

    const metrics = await getT539Metrics('run-t539-1', 't539_strategy_one')

    const url = new URL(String(fetchMock.mock.calls[0]?.[0]), 'http://localhost')
    expect(url.pathname).toBe('/api/v1/t539-historical/runs/run-t539-1/metrics')
    expect(url.searchParams.get('strategy_id')).toBe('t539_strategy_one')
    expect(metrics.strategy_id).toBe('t539_strategy_one')
  })

  it('renders the official-prize ranking in exact server response order without local re-sorting', async () => {
    const items = [makeRanking({ rank: 1, strategy_id: 'first' }), makeRanking({ rank: 2, strategy_id: 'second' })]
    fetchMock.mockResolvedValue(apiResponse({ run_id: 'run-t539-1', items, disclaimer: 'fixture disclaimer' }))

    const page = await getT539Rankings('run-t539-1')

    expect(page.items.map((item) => item.strategy_id)).toEqual(['first', 'second'])
    expect(page.disclaimer).toBe('fixture disclaimer')
  })

  it('returns the coverage ledger with executed, blocked, and coverage_complete intact', async () => {
    fetchMock.mockResolvedValue(
      apiResponse({
        run_id: 'run-t539-1',
        executed: [
          { strategy_id: 'a', strategy_version: 'v1', native_ticket_count: 1, min_history: 30, selection_reason: 'wave1' },
        ],
        blocked: [{ strategy_id: 'b', reason_code: 'INSUFFICIENT_HISTORY', reason: 'not enough draws' }],
        coverage_complete: false,
      }),
    )

    const ledger = await getT539Coverage('run-t539-1')

    expect(ledger.executed).toHaveLength(1)
    expect(ledger.blocked).toHaveLength(1)
    expect(ledger.coverage_complete).toBe(false)
  })

  it('maps a 503 T539_HISTORICAL_NOT_CONFIGURED response to the NOT_CONFIGURED error kind', async () => {
    fetchMock.mockResolvedValue(
      apiResponse({ error_code: 'T539_HISTORICAL_NOT_CONFIGURED', message: 'not configured' }, 503),
    )

    await expect(listT539Runs({ limit: 25, offset: 0 })).rejects.toMatchObject({
      kind: 'NOT_CONFIGURED',
    })
  })

  it('maps a generic 503 response to the UNAVAILABLE error kind', async () => {
    fetchMock.mockResolvedValue(
      apiResponse({ error_code: 'T539_HISTORICAL_UNAVAILABLE', message: 'unavailable' }, 503),
    )

    await expect(listT539Runs({ limit: 25, offset: 0 })).rejects.toMatchObject({
      kind: 'UNAVAILABLE',
    })
  })

  it('maps a 404 response to the NOT_FOUND error kind', async () => {
    fetchMock.mockResolvedValue(
      apiResponse({ error_code: 'T539_RUN_NOT_FOUND', message: 'missing' }, 404),
    )

    await expect(listT539Strategies('missing-run', { limit: 100, offset: 0 })).rejects.toMatchObject({
      kind: 'NOT_FOUND',
    })
  })

  it('maps a 422 response to the INVALID_REQUEST error kind', async () => {
    fetchMock.mockResolvedValue(
      apiResponse({ error_code: 'T539_HISTORICAL_INVALID_QUERY', message: 'invalid' }, 422),
    )

    await expect(listT539Runs({ limit: 25, offset: 0 })).rejects.toMatchObject({
      kind: 'INVALID_REQUEST',
    })
  })

  it('rejects a shape that does not satisfy the run page runtime guard with MALFORMED_RESPONSE', async () => {
    fetchMock.mockResolvedValue(apiResponse({ items: [{ run_id: 'incomplete' }], total_count: 1, limit: 25, offset: 0 }))

    await expect(listT539Runs({ limit: 25, offset: 0 })).rejects.toMatchObject({
      kind: 'MALFORMED_RESPONSE',
    })
  })

  it('rejects a coverage ledger missing coverage_complete with MALFORMED_RESPONSE', async () => {
    fetchMock.mockResolvedValue(apiResponse({ run_id: 'run-t539-1', executed: [], blocked: [] }))

    await expect(getT539Coverage('run-t539-1')).rejects.toBeInstanceOf(T539HistoricalRequestError)
    await expect(getT539Coverage('run-t539-1')).rejects.toMatchObject({ kind: 'MALFORMED_RESPONSE' })
  })

  it('propagates an AbortError without wrapping it in T539HistoricalRequestError', async () => {
    const controller = new AbortController()
    fetchMock.mockImplementation(() => {
      const error = new DOMException('aborted', 'AbortError')
      return Promise.reject(error)
    })
    controller.abort()

    await expect(listT539Runs({ limit: 25, offset: 0 }, controller.signal)).rejects.toMatchObject({
      name: 'AbortError',
    })
  })
})
