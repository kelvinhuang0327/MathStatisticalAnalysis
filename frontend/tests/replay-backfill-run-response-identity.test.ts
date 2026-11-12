import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  getReplayBackfillCoverage,
  listReplayBackfillPredictions,
  ReplayBackfillRequestError,
} from '../src/api/replayBackfill'

const predictionPage = (runId: string | null) => ({
  run_id: runId,
  total_count: 0,
  items: [],
  next_cursor: null,
})

const coverage = (runId: string | null) => ({
  expected_strategy_count: 0,
  expected_target_count: 0,
  expected_cell_count: 0,
  completed_cell_count: 0,
  failed_cell_count: 0,
  closed_cell_count: 0,
  complete_coverage_percent: 0,
  missing_strategy_ids: [],
  run_id: runId,
})

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

async function expectRunIdMismatch(promise: Promise<unknown>) {
  const error = await promise.then(() => null, (reason: unknown) => reason)
  expect(error).toBeInstanceOf(ReplayBackfillRequestError)
  expect(error).toMatchObject({
    errorCode: 'REPLAY_RUN_ID_MISMATCH',
    message: expect.stringContaining('run ID'),
    status: 200,
  })
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('Replay Backfill response run identity', () => {
  it('rejects a valid different-run empty predictions page on the first page', async () => {
    const fetchMock = installResponse(predictionPage('R2'))
    await expectRunIdMismatch(listReplayBackfillPredictions({
      lotteryType: 'BIG_LOTTO',
      runId: 'R1',
      period: 'ALL',
    }))
    expect(requestUrl(fetchMock).searchParams.get('run_id')).toBe('R1')
  })

  it('rejects a valid different-run empty predictions page after a cursor', async () => {
    const fetchMock = installResponse(predictionPage('R2'))
    await expectRunIdMismatch(listReplayBackfillPredictions({
      lotteryType: 'BIG_LOTTO',
      runId: 'R1',
      period: 'ALL',
      cursor: 'cursor-page-2',
    }))
    const request = requestUrl(fetchMock)
    expect(request.searchParams.get('run_id')).toBe('R1')
    expect(request.searchParams.get('cursor')).toBe('cursor-page-2')
  })

  it('rejects coverage from a different explicit run with the same error code', async () => {
    installResponse(coverage('R2'))
    await expectRunIdMismatch(getReplayBackfillCoverage('BIG_LOTTO', undefined, 'R1'))
  })

  it('accepts a matching trimmed coverage run ID', async () => {
    const fetchMock = installResponse(coverage('R1'))
    const result = await getReplayBackfillCoverage('BIG_LOTTO', undefined, ' R1 ')
    expect(result.run_id).toBe('R1')
    expect(requestUrl(fetchMock).searchParams.get('run_id')).toBe('R1')
  })

  it.each([
    ['omitted', undefined],
    ['empty', ''],
    ['whitespace', '   '],
  ] as const)('keeps latest-run coverage when run ID is %s', async (_label, runId) => {
    const fetchMock = installResponse(coverage('R2'))
    const result = await getReplayBackfillCoverage('BIG_LOTTO', undefined, runId)
    expect(result.run_id).toBe('R2')
    expect(requestUrl(fetchMock).searchParams.has('run_id')).toBe(false)
  })

  it('preserves a null coverage run ID without filling it from the request', async () => {
    installResponse(coverage(null))
    const result = await getReplayBackfillCoverage('BIG_LOTTO', undefined, 'R1')
    expect(result.run_id).toBeNull()
  })

  it.each(['R1', ' R1 '])('accepts a matching explicit run request %j', async (runId) => {
    const fetchMock = installResponse(predictionPage('R1'))
    const result = await listReplayBackfillPredictions({ lotteryType: 'BIG_LOTTO', runId, period: 'ALL' })
    expect(result.run_id).toBe('R1')
    expect(requestUrl(fetchMock).searchParams.get('run_id')).toBe('R1')
  })

  it.each([
    ['omitted', undefined],
    ['empty', ''],
    ['whitespace', '   '],
  ] as const)('keeps latest-run behavior when run ID is %s', async (_label, runId) => {
    const fetchMock = installResponse(predictionPage('R2'))
    const result = await listReplayBackfillPredictions({ lotteryType: 'BIG_LOTTO', runId, period: 'ALL' })
    expect(result.run_id).toBe('R2')
    expect(requestUrl(fetchMock).searchParams.has('run_id')).toBe(false)
  })

  it('preserves a null response run ID without filling it from the request', async () => {
    installResponse(predictionPage(null))
    const result = await listReplayBackfillPredictions({
      lotteryType: 'BIG_LOTTO',
      runId: 'R1',
      period: 'ALL',
    })
    expect(result.run_id).toBeNull()
  })

  it('treats opaque run IDs as case-sensitive', async () => {
    installResponse(predictionPage('r1'))
    await expectRunIdMismatch(listReplayBackfillPredictions({
      lotteryType: 'BIG_LOTTO',
      runId: 'R1',
      period: 'ALL',
    }))
  })

  it('keeps malformed JSON as the existing invalid-response error', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: vi.fn().mockRejectedValue(new SyntaxError('invalid JSON')),
    }))
    await expect(listReplayBackfillPredictions({ lotteryType: 'BIG_LOTTO', runId: 'R1', period: 'ALL' }))
      .rejects.toMatchObject({ name: 'ReplayBackfillRequestError', status: 200, errorCode: undefined })
  })

  it('keeps schema validation ahead of run identity checks', async () => {
    installResponse({ ...predictionPage('R2'), total_count: -1 })
    await expect(listReplayBackfillPredictions({ lotteryType: 'BIG_LOTTO', runId: 'R1', period: 'ALL' }))
      .rejects.toMatchObject({
        name: 'ReplayBackfillRequestError',
        message: 'Replay backfill returned an invalid response.',
        errorCode: undefined,
      })
  })

  it('preserves non-success HTTP errors', async () => {
    installResponse({ message: 'service unavailable', error_code: 'TEST_HTTP_ERROR' }, 503)
    await expect(listReplayBackfillPredictions({ lotteryType: 'BIG_LOTTO', runId: 'R1', period: 'ALL' }))
      .rejects.toMatchObject({
        name: 'ReplayBackfillRequestError',
        status: 503,
        message: 'service unavailable',
        errorCode: 'TEST_HTTP_ERROR',
      })
  })

  it('preserves AbortSignal rejection', async () => {
    const abortError = new DOMException('The operation was aborted.', 'AbortError')
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(abortError))
    const controller = new AbortController()
    controller.abort()
    await expect(listReplayBackfillPredictions(
      { lotteryType: 'BIG_LOTTO', runId: 'R1', period: 'ALL' },
      controller.signal,
    )).rejects.toBe(abortError)
  })
})
