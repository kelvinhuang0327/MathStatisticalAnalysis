import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  getHistoricalSuccessFeatureCohortDiagnostics,
  getHistoricalSuccessFeatureCohorts,
  getHistoricalSuccessStabilityMatrix,
  getHistoricalSuccessTemporalHoldout,
  getHistoricalSuccessWindows,
  HistoricalSuccessWindowsRequestError,
  listHistoricalRuns,
  listHistoricalSuccessWindows,
} from '../src/api/historicalSuccessWindows'
import {
  apiResponse,
  IMPORT_SHA,
  makeFeatureCohortDiagnostics,
  makeFeatureCohorts,
  makeAllRelationsMatrix,
  makeMatrix,
  makeResult,
  makeRunPage,
  makeNotReadyTemporalHoldout,
  makeTemporalHoldout,
  makeWindowPage,
  makeZeroObservationFeatureCohorts,
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

  it('fetches exact walk-forward cohorts with encoded identity, selectors, GET, and AbortSignal', async () => {
    const controller = new AbortController()
    fetchMock.mockResolvedValue(apiResponse(makeFeatureCohorts()))

    const result = await getHistoricalSuccessFeatureCohorts(
      {
        import_identity_sha256: IMPORT_SHA,
        strategy_id: 'alias strategy/one',
        strategy_version: 'v1 beta',
        replicate: 1,
        prefix_count: 1,
        criterion: 'M3_PLUS',
      },
      controller.signal,
    )

    const [input, init] = fetchMock.mock.calls[0]!
    const url = new URL(String(input), 'http://localhost')
    expect(url.pathname).toBe(
      '/api/v1/historical-prefix-success-windows/strategies/alias%20strategy%2Fone/v1%20beta/1/feature-cohorts',
    )
    expect(Object.fromEntries(url.searchParams)).toEqual({
      import_identity_sha256: IMPORT_SHA,
      prefix_count: '1',
      criterion: 'M3_PLUS',
    })
    expect(init).toMatchObject({ method: 'GET', signal: controller.signal })
    expect(result.cohort_count).toBe(64)
    expect(result.cohorts).toHaveLength(64)
    expect(result.baseline.success_rate).toEqual({
      numerator: 2,
      denominator: 5,
      available: true,
    })
  })

  it('accepts the canonical zero-observation feature cohort grid', async () => {
    fetchMock.mockResolvedValue(apiResponse(makeZeroObservationFeatureCohorts()))

    const result = await getHistoricalSuccessFeatureCohorts({
      import_identity_sha256: IMPORT_SHA,
      strategy_id: 'zero-observation',
      strategy_version: 'v2',
      replicate: 2,
      prefix_count: 1,
      criterion: 'M3_PLUS',
    })

    expect(result.baseline.observation_count).toBe(0)
    expect(result.cohorts).toHaveLength(64)
    expect(result.cohorts.every((cohort) => cohort.first_target === null)).toBe(true)
  })

  it('fetches exact cohort diagnostics and preserves integers above 2^53 with BigInt', async () => {
    const controller = new AbortController()
    const diagnostics = makeFeatureCohortDiagnostics()
    diagnostics.diagnostics[0]!.raw_p_value = {
      numerator: '9007199254740993',
      denominator: '90071992547409931',
    }
    diagnostics.diagnostics[0]!.adjusted_p_value = {
      ...diagnostics.diagnostics[0]!.raw_p_value,
    }
    fetchMock.mockResolvedValue(apiResponse(diagnostics))

    const result = await getHistoricalSuccessFeatureCohortDiagnostics(
      {
        import_identity_sha256: IMPORT_SHA,
        strategy_id: 'alias strategy/one',
        strategy_version: 'v1 beta',
        replicate: 1,
        prefix_count: 1,
        criterion: 'M3_PLUS',
      },
      controller.signal,
    )

    const [input, init] = fetchMock.mock.calls[0]!
    const url = new URL(String(input), 'http://localhost')
    expect(url.pathname).toBe(
      '/api/v1/historical-prefix-success-windows/strategies/alias%20strategy%2Fone/v1%20beta/1/feature-cohorts/diagnostics',
    )
    expect(Object.fromEntries(url.searchParams)).toEqual({
      import_identity_sha256: IMPORT_SHA,
      prefix_count: '1',
      criterion: 'M3_PLUS',
    })
    expect(init).toMatchObject({ method: 'GET', signal: controller.signal })
    expect(result.family_size).toBe(64)
    expect(result.diagnostics).toHaveLength(64)
    expect(result.diagnostics[0]!.raw_p_value.numerator).toBe(
      '9007199254740993',
    )
    expect(BigInt(result.diagnostics[0]!.raw_p_value.numerator)).toBeGreaterThan(
      BigInt(Number.MAX_SAFE_INTEGER),
    )
  })

  it('fetches the fixed temporal holdout with exact forwarding, GET, and AbortSignal', async () => {
    const controller = new AbortController()
    const holdout = makeTemporalHoldout()
    holdout.discovery!.diagnostics[0]!.raw_p_value = {
      numerator: '9007199254740993',
      denominator: '90071992547409931',
    }
    holdout.discovery!.diagnostics[0]!.adjusted_p_value = {
      ...holdout.discovery!.diagnostics[0]!.raw_p_value,
    }
    fetchMock.mockResolvedValue(apiResponse(holdout))

    const result = await getHistoricalSuccessTemporalHoldout(
      {
        import_identity_sha256: IMPORT_SHA,
        strategy_id: 'alias strategy/one',
        strategy_version: 'v1 beta',
        replicate: 1,
        prefix_count: 1,
        criterion: 'M3_PLUS',
      },
      controller.signal,
    )

    const [input, init] = fetchMock.mock.calls[0]!
    const url = new URL(String(input), 'http://localhost')
    expect(url.pathname).toBe(
      '/api/v1/historical-prefix-success-windows/strategies/alias%20strategy%2Fone/v1%20beta/1/feature-cohorts/temporal-holdout',
    )
    expect(Object.fromEntries(url.searchParams)).toEqual({
      import_identity_sha256: IMPORT_SHA,
      prefix_count: '1',
      criterion: 'M3_PLUS',
    })
    expect(init).toMatchObject({ method: 'GET', signal: controller.signal })
    expect(result.evaluation_status).toBe('COMPLETE')
    expect(result.comparisons).toHaveLength(64)
    expect(
      BigInt(result.discovery!.diagnostics[0]!.raw_p_value.numerator),
    ).toBeGreaterThan(BigInt(Number.MAX_SAFE_INTEGER))
  })

  it('accepts the exact not-ready temporal holdout without partial diagnostics', async () => {
    fetchMock.mockResolvedValue(apiResponse(makeNotReadyTemporalHoldout()))

    const result = await getHistoricalSuccessTemporalHoldout({
      import_identity_sha256: IMPORT_SHA,
      strategy_id: 'alias strategy/one',
      strategy_version: 'v1 beta',
      replicate: 1,
      prefix_count: 1,
      criterion: 'M3_PLUS',
    })

    expect(result.evaluation_status).toBe('NOT_READY_INSUFFICIENT_HISTORY')
    expect(result.discovery).toBeNull()
    expect(result.confirmation).toBeNull()
    expect(result.comparisons).toEqual([])
  })

  it.each([
    [
      'wrong split method',
      (result: ReturnType<typeof makeTemporalHoldout>) => {
        result.split.split_method =
          'PERCENTAGE' as 'FIXED_LAST_750_DISCOVERY_LAST_300_CONFIRMATION'
      },
    ],
    [
      'wrong discovery count',
      (result: ReturnType<typeof makeTemporalHoldout>) => {
        result.split.discovery_count = 749
      },
    ],
    [
      'missing cohort comparison',
      (result: ReturnType<typeof makeTemporalHoldout>) => {
        result.comparisons.pop()
      },
    ],
    [
      'duplicate cohort comparison',
      (result: ReturnType<typeof makeTemporalHoldout>) => {
        result.comparisons[1] = result.comparisons[0]!
      },
    ],
    [
      'wrong comparison order',
      (result: ReturnType<typeof makeTemporalHoldout>) => {
        ;[result.comparisons[0], result.comparisons[1]] = [
          result.comparisons[1]!,
          result.comparisons[0]!,
        ]
      },
    ],
    [
      'identity mismatch',
      (result: ReturnType<typeof makeTemporalHoldout>) => {
        result.confirmation!.strategy = {
          ...result.confirmation!.strategy,
          strategy_id: 'different',
        }
      },
    ],
    [
      'malformed exact probability',
      (result: ReturnType<typeof makeTemporalHoldout>) => {
        result.confirmation!.diagnostics[0]!.raw_p_value.numerator = '01'
      },
    ],
    [
      'malformed effect change',
      (result: ReturnType<typeof makeTemporalHoldout>) => {
        result.comparisons[0]!.effect_change.numerator += 1
      },
    ],
  ])('rejects temporal holdout with %s', async (_label, mutate) => {
    const holdout = makeTemporalHoldout()
    mutate(holdout)
    fetchMock.mockResolvedValue(apiResponse(holdout))

    await expect(
      getHistoricalSuccessTemporalHoldout({
        import_identity_sha256: IMPORT_SHA,
        strategy_id: 'alias strategy/one',
        strategy_version: 'v1 beta',
        replicate: 1,
        prefix_count: 1,
        criterion: 'M3_PLUS',
      }),
    ).rejects.toMatchObject({ kind: 'MALFORMED_RESPONSE', status: 502 })
  })

  it.each([
    [
      'missing diagnostic',
      (result: ReturnType<typeof makeFeatureCohortDiagnostics>) => {
        result.diagnostics.pop()
      },
    ],
    [
      'duplicate diagnostic',
      (result: ReturnType<typeof makeFeatureCohortDiagnostics>) => {
        result.diagnostics[1] = result.diagnostics[0]!
      },
    ],
    [
      'wrong order',
      (result: ReturnType<typeof makeFeatureCohortDiagnostics>) => {
        ;[result.diagnostics[0], result.diagnostics[1]] = [
          result.diagnostics[1]!,
          result.diagnostics[0]!,
        ]
      },
    ],
    [
      'identity mismatch',
      (result: ReturnType<typeof makeFeatureCohortDiagnostics>) => {
        result.strategy = { ...result.strategy, strategy_id: 'different' }
      },
    ],
    [
      'malformed complement counts',
      (result: ReturnType<typeof makeFeatureCohortDiagnostics>) => {
        result.diagnostics[0]!.outside_counts.failure_count += 1
      },
    ],
    [
      'malformed baseline rate',
      (result: ReturnType<typeof makeFeatureCohortDiagnostics>) => {
        result.baseline.success_rate.numerator += 1
      },
    ],
    [
      'numeric p-value integer',
      (result: ReturnType<typeof makeFeatureCohortDiagnostics>) => {
        result.diagnostics[0]!.raw_p_value.numerator = 1 as unknown as string
      },
    ],
    [
      'leading-zero p-value integer',
      (result: ReturnType<typeof makeFeatureCohortDiagnostics>) => {
        result.diagnostics[0]!.raw_p_value.numerator = '01'
      },
    ],
    [
      'zero denominator',
      (result: ReturnType<typeof makeFeatureCohortDiagnostics>) => {
        result.diagnostics[0]!.raw_p_value.denominator = '0'
      },
    ],
    [
      'numerator above denominator',
      (result: ReturnType<typeof makeFeatureCohortDiagnostics>) => {
        result.diagnostics[0]!.raw_p_value = {
          numerator: '2',
          denominator: '1',
        }
      },
    ],
    [
      'wrong method identifier',
      (result: ReturnType<typeof makeFeatureCohortDiagnostics>) => {
        result.adjustment_method = 'BENJAMINI_HOCHBERG' as 'BENJAMINI_YEKUTIELI'
      },
    ],
  ])('rejects cohort diagnostics with %s', async (_label, mutate) => {
    const diagnostics = makeFeatureCohortDiagnostics()
    mutate(diagnostics)
    fetchMock.mockResolvedValue(apiResponse(diagnostics))

    await expect(
      getHistoricalSuccessFeatureCohortDiagnostics({
        import_identity_sha256: IMPORT_SHA,
        strategy_id: 'alias strategy/one',
        strategy_version: 'v1 beta',
        replicate: 1,
        prefix_count: 1,
        criterion: 'M3_PLUS',
      }),
    ).rejects.toMatchObject({ kind: 'MALFORMED_RESPONSE', status: 502 })
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

  it.each([
    [
      'missing cohort',
      (result: ReturnType<typeof makeFeatureCohorts>) => {
        result.cohorts.pop()
      },
    ],
    [
      'duplicate cohort',
      (result: ReturnType<typeof makeFeatureCohorts>) => {
        result.cohorts[1] = result.cohorts[0]!
      },
    ],
    [
      'wrong cohort order',
      (result: ReturnType<typeof makeFeatureCohorts>) => {
        ;[result.cohorts[0], result.cohorts[1]] = [
          result.cohorts[1]!,
          result.cohorts[0]!,
        ]
      },
    ],
    [
      'identity mismatch',
      (result: ReturnType<typeof makeFeatureCohorts>) => {
        result.strategy = { ...result.strategy, strategy_id: 'different' }
      },
    ],
    [
      'malformed counts',
      (result: ReturnType<typeof makeFeatureCohorts>) => {
        result.cohorts[0]!.failure_count += 1
      },
    ],
    [
      'malformed delta',
      (result: ReturnType<typeof makeFeatureCohorts>) => {
        result.cohorts[0]!.delta_vs_baseline.numerator *= -1
      },
    ],
    [
      'unavailable treated as zero',
      (result: ReturnType<typeof makeFeatureCohorts>) => {
        result.cohorts[2]!.success_rate = {
          numerator: 0,
          denominator: 1,
          available: true,
        }
      },
    ],
  ])('rejects feature cohorts with %s', async (_label, mutate) => {
    const result = makeFeatureCohorts()
    mutate(result)
    fetchMock.mockResolvedValue(apiResponse(result))

    await expect(
      getHistoricalSuccessFeatureCohorts({
        import_identity_sha256: IMPORT_SHA,
        strategy_id: 'alias strategy/one',
        strategy_version: 'v1 beta',
        replicate: 1,
        prefix_count: 1,
        criterion: 'M3_PLUS',
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
