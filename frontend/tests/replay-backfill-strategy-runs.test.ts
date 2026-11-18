import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  listReplayStrategyRuns,
  ReplayBackfillRequestError,
} from '../src/api/replayBackfill'

const MAX_SAFE_INTEGER = Number.MAX_SAFE_INTEGER

function runItem(overrides: Record<string, unknown> = {}) {
  return {
    run_id: 'RUN-1',
    lottery_type: 'BIG_LOTTO',
    strategy_id: 'strategy-1',
    strategy_version: 'v1',
    run_created_at: '2026-11-16T08:00:00Z',
    inventory_present: true,
    associated_cell_count: 3,
    unique_target_draw_count: 2,
    execution_identity_count: 1,
    execution_status_counts: { COMPLETED: 1 },
    earliest_target_draw_date: '2026-11-01',
    latest_target_draw_date: '2026-11-15',
    ...overrides,
  }
}

function runsPage(
  items: unknown[] = [runItem()],
  overrides: Record<string, unknown> = {},
) {
  return {
    total_run_version_matches: items.length,
    items,
    has_more: false,
    limit: 50,
    offset: 0,
    ...overrides,
  }
}

function apiResponse(payload: unknown, status = 200): Response {
  return {
    ok: status < 400,
    status,
    json: vi.fn().mockResolvedValue(payload),
  } as unknown as Response
}

function installResponse(payload: unknown, status = 200) {
  const fetchMock = vi.fn().mockResolvedValue(apiResponse(payload, status))
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function requestUrl(fetchMock: ReturnType<typeof installResponse>): URL {
  return new URL(String(fetchMock.mock.calls[0]?.[0]), 'http://localhost')
}

afterEach(() => vi.unstubAllGlobals())

describe('Replay Backfill strategy-run discovery client', () => {
  it('sends the complete strategy identity and validates the requested page', async () => {
    const fetchMock = installResponse(runsPage())
    const result = await listReplayStrategyRuns({
      lotteryType: 'BIG_LOTTO',
      strategyId: ' strategy-1 ',
      strategyVersion: ' v1 ',
    })

    const url = requestUrl(fetchMock)
    expect(url.pathname).toBe('/api/v1/replay-backfill/strategy-runs')
    expect(Object.fromEntries(url.searchParams)).toEqual({
      lottery_type: 'BIG_LOTTO',
      strategy_id: 'strategy-1',
      strategy_version: 'v1',
      limit: '50',
      offset: '0',
    })
    expect(result.items[0]?.strategy_version).toBe('v1')
  })

  it('keeps unfiltered Run×version identities as separate rows', async () => {
    const fetchMock = installResponse(runsPage([
      runItem({ run_id: 'RUN-1', strategy_version: 'v1' }),
      runItem({ run_id: 'RUN-2', strategy_version: 'v2' }),
      runItem({ run_id: 'RUN-3', strategy_version: 'v1' }),
      runItem({ run_id: 'RUN-3', strategy_version: 'v2' }),
    ]))
    const result = await listReplayStrategyRuns({
      lotteryType: 'BIG_LOTTO',
      strategyId: 'strategy-1',
    })

    expect(requestUrl(fetchMock).searchParams.has('strategy_version')).toBe(false)
    expect(result.items.map(({ run_id, strategy_version }) => [run_id, strategy_version])).toEqual([
      ['RUN-1', 'v1'],
      ['RUN-2', 'v2'],
      ['RUN-3', 'v1'],
      ['RUN-3', 'v2'],
    ])
  })

  it('accepts an inventory-only row with zero cell counts and missing date bounds', async () => {
    const inventoryOnly = runItem({
      inventory_present: true,
      associated_cell_count: 0,
      unique_target_draw_count: 0,
      execution_identity_count: 0,
      execution_status_counts: {},
      earliest_target_draw_date: null,
      latest_target_draw_date: null,
    })
    installResponse(runsPage([inventoryOnly]))
    const result = await listReplayStrategyRuns({
      lotteryType: 'BIG_LOTTO',
      strategyId: 'strategy-1',
    })

    expect(result.items[0]).toMatchObject(inventoryOnly)
  })

  it('does not request discovery without a complete strategy ID', async () => {
    const fetchMock = installResponse(runsPage())
    await expect(listReplayStrategyRuns({
      lotteryType: 'BIG_LOTTO',
      strategyId: '   ',
    })).rejects.toThrow('A complete strategy ID is required')
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it.each([
    ['negative total count', runsPage([], { total_run_version_matches: -1 })],
    ['unsafe cell count', runsPage([runItem({ associated_cell_count: MAX_SAFE_INTEGER + 1 })])],
    ['negative execution status count', runsPage([runItem({ execution_status_counts: { FAILED: -1 } })])],
    ['wrong has_more type', runsPage([runItem()], { has_more: 'false' })],
    ['missing run identity', runsPage([runItem({ run_id: undefined })])],
    ['wrong item structure', runsPage([null])],
    ['unexpected response field', runsPage([runItem()], { success_count: 1 })],
    ['response page size mismatch', runsPage([runItem()], { limit: 25 })],
    ['unsafe response offset', runsPage([], { offset: MAX_SAFE_INTEGER + 1 })],
    ['version outside requested identity', runsPage([runItem({ strategy_version: 'v2' })])],
    ['more page without remaining matches', runsPage([runItem()], { has_more: true })],
  ])('rejects malformed HTTP 200 responses: %s', async (_label, payload) => {
    installResponse(payload)
    await expect(listReplayStrategyRuns({
      lotteryType: 'BIG_LOTTO',
      strategyId: 'strategy-1',
      strategyVersion: 'v1',
    })).rejects.toMatchObject({
      name: 'ReplayBackfillRequestError',
      status: 502,
      message: 'Replay backfill returned an invalid response.',
    })
  })

  it.each([422, 503])('keeps HTTP %i as an error instead of an empty page', async (status) => {
    installResponse({ message: 'request failed' }, status)
    const error = await listReplayStrategyRuns({
      lotteryType: 'BIG_LOTTO',
      strategyId: 'strategy-1',
    }).then(() => null, (reason: unknown) => reason)
    expect(error).toBeInstanceOf(ReplayBackfillRequestError)
    expect(error).toMatchObject({ status, message: 'request failed' })
  })

  it('validates safe request pagination and sends the same identity on later pages', async () => {
    const fetchMock = installResponse(runsPage([], { total_run_version_matches: 60, has_more: true, offset: 50 }))
    await expect(listReplayStrategyRuns({
      lotteryType: 'BIG_LOTTO',
      strategyId: 'strategy-1',
      limit: 251,
    })).rejects.toThrow('limit must be an integer')
    expect(fetchMock).not.toHaveBeenCalled()

    const offsetFetch = installResponse(runsPage([runItem({ run_id: 'RUN-2', lottery_type: 'DAILY_539' })], {
      total_run_version_matches: 2,
      limit: 1,
      offset: 1,
    }))
    const laterPage = await listReplayStrategyRuns({
      lotteryType: 'DAILY_539',
      strategyId: 'strategy-1',
      strategyVersion: 'v1',
      limit: 1,
      offset: 1,
    })
    expect(laterPage.items[0]?.run_id).toBe('RUN-2')
    expect(Object.fromEntries(requestUrl(offsetFetch).searchParams)).toEqual({
      lottery_type: 'DAILY_539',
      strategy_id: 'strategy-1',
      strategy_version: 'v1',
      limit: '1',
      offset: '1',
    })
  })
})
