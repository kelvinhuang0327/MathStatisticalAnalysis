import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  listReplayBackfillPredictions,
  ReplayBackfillRequestError,
} from '../src/api/replayBackfill'

function prediction(overrides: Record<string, unknown> = {}) {
  return {
    lottery_type: 'BIG_LOTTO',
    strategy_id: 'strategy-1',
    strategy_version: 'v1',
    target_draw_number: '101',
    target_draw_date: '2026-11-01',
    prediction_status: 'COMPLETE',
    source_history_provenance_status: 'VERIFIED',
    predicted_tickets: [],
    actual_main_numbers: [1, 2, 3, 4, 5, 6],
    actual_special_numbers: [7],
    source_kind: 'TEST_FIXTURE',
    data_status: 'HAS_HISTORY',
    training: {
      training_status: 'NOT_TRAINABLE',
      model_version: null,
      training_cutoff: null,
      training_artifact_id: null,
    },
    portfolio_any_prize: null,
    best_main_hits: null,
    execution_version: 'EV1',
    dataset_identity: 'DS1',
    ...overrides,
  }
}

function predictionPage(items: unknown[], overrides: Record<string, unknown> = {}) {
  return {
    run_id: 'R1',
    total_count: items.length,
    items,
    next_cursor: null,
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

function requestUrl(fetchMock: ReturnType<typeof installResponse>, index = 0): URL {
  return new URL(String(fetchMock.mock.calls[index]?.[0]), 'http://localhost')
}

afterEach(() => vi.unstubAllGlobals())

describe('Replay Backfill prediction strategy-version identity', () => {
  it('sends a trimmed exact version with the run and strategy identity', async () => {
    const fetchMock = installResponse(predictionPage([prediction()]))
    const result = await listReplayBackfillPredictions({
      lotteryType: 'BIG_LOTTO',
      runId: ' R1 ',
      strategyId: ' strategy-1 ',
      strategyVersion: ' v1 ',
      period: 'ALL',
    })

    expect(Object.fromEntries(requestUrl(fetchMock).searchParams)).toMatchObject({
      lottery_type: 'BIG_LOTTO',
      run_id: 'R1',
      strategy_id: 'strategy-1',
      strategy_version: 'v1',
      period: 'ALL',
    })
    expect(result.items.map((item) => item.strategy_version)).toEqual(['v1'])
  })

  it('preserves all-version behavior when no version is selected', async () => {
    const fetchMock = installResponse(predictionPage([
      prediction({ strategy_version: 'v1' }),
      prediction({ strategy_version: 'v2', target_draw_number: '102' }),
    ]))
    const result = await listReplayBackfillPredictions({
      lotteryType: 'BIG_LOTTO',
      runId: 'R1',
      strategyId: 'strategy-1',
      period: 'ALL',
    })

    expect(requestUrl(fetchMock).searchParams.get('strategy_id')).toBe('strategy-1')
    expect(requestUrl(fetchMock).searchParams.has('strategy_version')).toBe(false)
    expect(result.items.map((item) => item.strategy_version)).toEqual(['v1', 'v2'])
  })

  it('rejects version without a strategy ID before fetching', async () => {
    const fetchMock = installResponse(predictionPage([]))
    await expect(listReplayBackfillPredictions({
      lotteryType: 'BIG_LOTTO',
      strategyVersion: 'v1',
      period: 'ALL',
    })).rejects.toThrow('A strategy version requires a complete strategy ID')
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it.each([
    ['wrong strategy', prediction({ strategy_id: 'strategy-2' })],
    ['wrong version', prediction({ strategy_version: 'v2' })],
  ])('rejects the whole HTTP 200 page when an item has %s identity', async (_label, item) => {
    installResponse(predictionPage([prediction(), item]))
    await expect(listReplayBackfillPredictions({
      lotteryType: 'BIG_LOTTO',
      runId: 'R1',
      strategyId: 'strategy-1',
      strategyVersion: 'v1',
      period: 'ALL',
    })).rejects.toMatchObject({
      name: 'ReplayBackfillRequestError',
      status: 502,
      message: 'Replay backfill returned an invalid response.',
    })
  })

  it.each([
    ['missing strategy version', (() => {
      const item = prediction()
      delete (item as Record<string, unknown>).strategy_version
      return item
    })()],
    ['malformed execution identity', prediction({ execution_version: 7 })],
  ])('rejects malformed HTTP 200 items: %s', async (_label, item) => {
    installResponse(predictionPage([item]))
    await expect(listReplayBackfillPredictions({
      lotteryType: 'BIG_LOTTO',
      strategyId: 'strategy-1',
      strategyVersion: 'v1',
      period: 'ALL',
    })).rejects.toBeInstanceOf(ReplayBackfillRequestError)
  })

  it('keeps the version and cursor together on the next-page request', async () => {
    const fetchMock = installResponse(predictionPage([], {
      total_count: 1,
      next_cursor: null,
    }))
    await listReplayBackfillPredictions({
      lotteryType: 'BIG_LOTTO',
      runId: 'R1',
      strategyId: 'strategy-1',
      strategyVersion: 'v1',
      period: 'ALL',
      cursor: 'cursor-v1',
    })

    expect(Object.fromEntries(requestUrl(fetchMock).searchParams)).toMatchObject({
      run_id: 'R1',
      strategy_id: 'strategy-1',
      strategy_version: 'v1',
      cursor: 'cursor-v1',
    })
  })

  it.each([422, 503])('keeps HTTP %i as an error instead of an empty result', async (status) => {
    installResponse({ message: `HTTP ${status} failed` }, status)
    await expect(listReplayBackfillPredictions({
      lotteryType: 'BIG_LOTTO',
      strategyId: 'strategy-1',
      strategyVersion: 'v1',
      period: 'ALL',
    })).rejects.toMatchObject({
      status,
      message: `HTTP ${status} failed`,
    })
  })
})
