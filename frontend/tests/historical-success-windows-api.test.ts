import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  getHistoricalSuccessStabilityMatrix,
  getHistoricalSuccessWindows,
  HistoricalSuccessWindowsRequestError,
  listHistoricalRuns,
  listHistoricalSuccessWindows,
} from '../src/api/historicalSuccessWindows'
import {
  apiResponse,
  IMPORT_SHA,
  makeAllRelationsMatrix,
  makeMatrix,
  makeResult,
  makeRunPage,
  makeWindowPage,
} from './historical-success-windows-fixtures'

let fetchMock: ReturnType<typeof vi.fn<typeof fetch>>

beforeEach(() => {
  fetchMock = vi.fn<typeof fetch>()
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => vi.unstubAllGlobals())

describe('Historical Success Windows API client', () => {
  it('lists runs with bounded pagination and preserves exact import identities', async () => {
    fetchMock.mockResolvedValue(apiResponse(makeRunPage()))

    const page = await listHistoricalRuns({ limit: 10, offset: 0 })

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/historical-results/runs?limit=10&offset=0',
      expect.objectContaining({ method: 'GET' }),
    )
    expect(page.items[0]?.import_identity_sha256).toBe(IMPORT_SHA)
  })

  it('forwards the exact SHA, prefix, criterion, limit, and offset without normalization', async () => {
    fetchMock.mockResolvedValue(apiResponse(makeWindowPage()))

    await listHistoricalSuccessWindows({
      import_identity_sha256: IMPORT_SHA,
      prefix_count: 1,
      criterion: 'M3_PLUS',
      limit: 20,
      offset: 0,
    })

    const url = new URL(String(fetchMock.mock.calls[0]?.[0]), 'http://localhost')
    expect(url.pathname).toBe('/api/v1/historical-prefix-success-windows')
    expect(Object.fromEntries(url.searchParams)).toEqual({
      import_identity_sha256: IMPORT_SHA,
      prefix_count: '1',
      criterion: 'M3_PLUS',
      limit: '20',
      offset: '0',
    })
  })

  it('does not trim or lowercase the caller-supplied source selector', async () => {
    const exactSelector = ` A${'B'.repeat(62)} `
    fetchMock.mockResolvedValue(
      apiResponse({ error_code: 'REQUEST_VALIDATION_FAILED', message: 'sanitized' }, 422),
    )

    await expect(
      listHistoricalSuccessWindows({
        import_identity_sha256: exactSelector,
        prefix_count: 1,
        criterion: 'M3_PLUS',
        limit: 20,
        offset: 0,
      }),
    ).rejects.toMatchObject({ kind: 'INVALID_REQUEST' })

    const url = new URL(String(fetchMock.mock.calls[0]?.[0]), 'http://localhost')
    expect(url.searchParams.get('import_identity_sha256')).toBe(exactSelector)
  })

  it('safely encodes every exact strategy path axis and validates returned identity', async () => {
    fetchMock.mockResolvedValue(apiResponse(makeResult()))

    await getHistoricalSuccessWindows({
      import_identity_sha256: IMPORT_SHA,
      strategy_id: 'alias strategy/one',
      strategy_version: 'v1 beta',
      replicate: 1,
      prefix_count: 1,
      criterion: 'M3_PLUS',
    })

    expect(String(fetchMock.mock.calls[0]?.[0])).toContain(
      '/strategies/alias%20strategy%2Fone/v1%20beta/1?',
    )
  })

  it('fetches one complete matrix with encoded identity, exact SHA, GET, and AbortSignal', async () => {
    const controller = new AbortController()
    fetchMock.mockResolvedValue(apiResponse(makeMatrix()))

    const matrix = await getHistoricalSuccessStabilityMatrix(
      {
        import_identity_sha256: IMPORT_SHA,
        strategy_id: 'alias strategy/one',
        strategy_version: 'v1 beta',
        replicate: 1,
      },
      controller.signal,
    )

    const [input, init] = fetchMock.mock.calls[0]!
    const url = new URL(String(input), 'http://localhost')
    expect(url.pathname).toBe(
      '/api/v1/historical-prefix-success-windows/strategies/alias%20strategy%2Fone/v1%20beta/1/matrix',
    )
    expect(Object.fromEntries(url.searchParams)).toEqual({
      import_identity_sha256: IMPORT_SHA,
    })
    expect(init).toMatchObject({ method: 'GET', signal: controller.signal })
    expect(matrix.cell_count).toBe(64)
    expect(matrix.cells).toHaveLength(64)
  })

  it('accepts canonical HIGHER, EQUAL, LOWER, and UNAVAILABLE arithmetic relations', async () => {
    fetchMock.mockResolvedValue(apiResponse(makeAllRelationsMatrix()))

    const matrix = await getHistoricalSuccessStabilityMatrix({
      import_identity_sha256: IMPORT_SHA,
      strategy_id: 'alias strategy/one',
      strategy_version: 'v1 beta',
      replicate: 1,
    })

    const relations = new Set(
      matrix.cells.flatMap((cell) => cell.comparisons.map((item) => item.relation)),
    )
    expect(relations).toEqual(new Set(['HIGHER', 'EQUAL', 'LOWER', 'UNAVAILABLE']))
  })

  it.each([
    [
      'missing cell',
      (matrix: ReturnType<typeof makeMatrix>) => {
        matrix.cells.pop()
      },
    ],
    [
      'duplicate cell',
      (matrix: ReturnType<typeof makeMatrix>) => {
        matrix.cells[1] = matrix.cells[0]!
      },
    ],
    [
      'incorrect order',
      (matrix: ReturnType<typeof makeMatrix>) => {
        ;[matrix.cells[0], matrix.cells[1]] = [matrix.cells[1]!, matrix.cells[0]!]
      },
    ],
    [
      'identity mismatch',
      (matrix: ReturnType<typeof makeMatrix>) => {
        matrix.strategy = { ...matrix.strategy, strategy_id: 'different' }
      },
    ],
    [
      'malformed signed delta',
      (matrix: ReturnType<typeof makeMatrix>) => {
        matrix.cells[0]!.comparisons[0]!.delta.numerator = -1
      },
    ],
    [
      'float rate',
      (matrix: ReturnType<typeof makeMatrix>) => {
        matrix.cells[0]!.windows[0]!.success_rate.numerator = 0.5
      },
    ],
  ])('rejects a matrix with %s', async (_label, mutate) => {
    const matrix = makeMatrix()
    mutate(matrix)
    fetchMock.mockResolvedValue(apiResponse(matrix))

    await expect(
      getHistoricalSuccessStabilityMatrix({
        import_identity_sha256: IMPORT_SHA,
        strategy_id: 'alias strategy/one',
        strategy_version: 'v1 beta',
        replicate: 1,
      }),
    ).rejects.toMatchObject({ kind: 'MALFORMED_RESPONSE', status: 502 })
  })

  it('fails closed when exact detail returns a different identity', async () => {
    const mismatched = makeResult({
      strategy: { ...makeResult().strategy, strategy_id: 'different' },
      selection: { ...makeResult().selection, strategy_id: 'different' },
    })
    fetchMock.mockResolvedValue(apiResponse(mismatched))

    await expect(
      getHistoricalSuccessWindows({
        import_identity_sha256: IMPORT_SHA,
        strategy_id: 'alias strategy/one',
        strategy_version: 'v1 beta',
        replicate: 1,
        prefix_count: 1,
        criterion: 'M3_PLUS',
      }),
    ).rejects.toMatchObject({ kind: 'MALFORMED_RESPONSE', status: 502 })
  })

  it('rejects malformed pages and non-canonical window order', async () => {
    const malformed = makeWindowPage()
    malformed.items[0]!.windows.reverse()
    fetchMock.mockResolvedValue(apiResponse(malformed))

    await expect(
      listHistoricalSuccessWindows({
        import_identity_sha256: IMPORT_SHA,
        prefix_count: 1,
        criterion: 'M3_PLUS',
        limit: 20,
        offset: 0,
      }),
    ).rejects.toMatchObject({ kind: 'MALFORMED_RESPONSE' })
  })

  it.each([
    [503, 'HISTORICAL_RESULTS_NOT_CONFIGURED', 'NOT_CONFIGURED'],
    [503, 'HISTORICAL_RESULTS_UNAVAILABLE', 'UNAVAILABLE'],
    [404, 'HISTORICAL_PREFIX_SUCCESS_IMPORT_NOT_FOUND', 'NOT_FOUND'],
    [422, 'REQUEST_VALIDATION_FAILED', 'INVALID_REQUEST'],
  ] as const)('classifies sanitized HTTP %s errors', async (status, errorCode, kind) => {
    fetchMock.mockResolvedValue(
      apiResponse({ error_code: errorCode, message: '/secret/database/path' }, status),
    )

    const error = await listHistoricalRuns({ limit: 10, offset: 0 }).catch(
      (caught: unknown) => caught,
    )

    expect(error).toBeInstanceOf(HistoricalSuccessWindowsRequestError)
    expect(error).toMatchObject({ status, errorCode, kind })
    expect(String((error as Error).message)).not.toContain('/secret/database/path')
  })

  it('classifies invalid JSON and network failures without exposing raw errors', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: vi.fn().mockRejectedValue(new SyntaxError('raw response body')),
    } as unknown as Response)

    await expect(listHistoricalRuns({ limit: 10, offset: 0 })).rejects.toMatchObject({
      kind: 'MALFORMED_RESPONSE',
    })

    fetchMock.mockRejectedValueOnce(new TypeError('/secret network detail'))
    const error = await listHistoricalRuns({ limit: 10, offset: 0 }).catch(
      (caught: unknown) => caught,
    )
    expect(error).toMatchObject({ kind: 'NETWORK', status: 0 })
    expect(String((error as Error).message)).not.toContain('/secret network detail')
  })
})
