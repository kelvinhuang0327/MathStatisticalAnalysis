import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  getHistoricalSuccessFeatureCohortDiagnostics,
  getHistoricalSuccessFeatureCohorts,
  getHistoricalSuccessCrossImportConcordance,
  getHistoricalSuccessMultiImportConcordanceCensus,
  getHistoricalSuccessQualificationRandomBaselineEvidence,
  getHistoricalSuccessRecent50StabilityAudit,
  getHistoricalSuccessRandomBaseline,
  getHistoricalSuccessResearchQualification,
  getHistoricalSuccessStabilityMatrix,
  getHistoricalSuccessTemporalHoldout,
  getHistoricalSuccessWindows,
  HistoricalSuccessWindowsRequestError,
  listHistoricalRuns,
  listHistoricalSuccessWindows,
  type HistoricalSuccessQualificationRandomBaselineEvidence,
} from '../src/api/historicalSuccessWindows'
import {
  apiResponse,
  IMPORT_SHA,
  makeFeatureCohortDiagnostics,
  makeFeatureCohorts,
  makeCrossImportConcordance,
  makeMultiImportConcordanceCensus,
  makeAllRelationsMatrix,
  makeMatrix,
  makeResult,
  makeRunPage,
  makeNotReadyTemporalHoldout,
  makeNotReadyRecent50StabilityAudit,
  makeNotReadyRandomBaseline,
  makeNotReadyCrossImportConcordance,
  RIGHT_IMPORT_SHA,
  THIRD_IMPORT_SHA,
  makeTemporalHoldout,
  makeRecent50StabilityAudit,
  makeRandomBaseline,
  makeQualificationRandomBaselineEvidence,
  makeResearchQualification,
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

  it('fetches all four exact random-baseline windows with encoded identity, query axes, GET, and AbortSignal', async () => {
    const controller = new AbortController()
    const windowKinds = [
      'FULL_HISTORY',
      'LONG',
      'MEDIUM',
      'SHORT',
    ] as const
    for (const windowKind of windowKinds) {
      fetchMock.mockResolvedValueOnce(
        apiResponse(
          makeRandomBaseline({
            cell: {
              ...makeRandomBaseline().cell,
              window_kind: windowKind,
            },
          }),
        ),
      )
      const result = await getHistoricalSuccessRandomBaseline(
        {
          import_identity_sha256: IMPORT_SHA,
          strategy_id: 'alias strategy/one',
          strategy_version: 'v1 beta',
          replicate: 1,
          prefix_count: 1,
          criterion: 'M3_PLUS',
          window_kind: windowKind,
        },
        controller.signal,
      )
      expect(result.cell.window_kind).toBe(windowKind)
    }

    for (const [index, [input, init]] of fetchMock.mock.calls.entries()) {
      const url = new URL(String(input), 'http://localhost')
      expect(url.pathname).toBe(
        '/api/v1/historical-prefix-success-windows/strategies/alias%20strategy%2Fone/v1%20beta/1/random-null-baseline',
      )
      expect(Object.fromEntries(url.searchParams)).toEqual({
        import_identity_sha256: IMPORT_SHA,
        prefix_count: '1',
        criterion: 'M3_PLUS',
        window_kind: windowKinds[index],
      })
      expect(init).toMatchObject({ method: 'GET', signal: controller.signal })
    }
  })

  it('accepts a closed NOT_READY baseline and rejects extra, contradictory, or inexact payloads', async () => {
    fetchMock.mockResolvedValueOnce(apiResponse(makeNotReadyRandomBaseline()))
    const query = {
      import_identity_sha256: IMPORT_SHA,
      strategy_id: 'alias strategy/one',
      strategy_version: 'v1 beta',
      replicate: 1,
      prefix_count: 1 as const,
      criterion: 'M3_PLUS' as const,
      window_kind: 'LONG' as const,
    }

    await expect(getHistoricalSuccessRandomBaseline(query)).resolves.toMatchObject({
      readiness: 'NOT_READY',
      reason_codes: ['WINDOW_INCOMPLETE'],
      observed_success_count: null,
    })

    fetchMock.mockResolvedValueOnce(
      apiResponse(
        makeRandomBaseline({
          observed_success_count: 2,
          upper_tail_probability: {
            numerator: '21659716',
            denominator: '62355583521',
            decimal_18: '0.000347358083702408',
          },
        }),
      ),
    )
    await expect(getHistoricalSuccessRandomBaseline(query)).resolves.toMatchObject({
      readiness: 'READY',
      observed_success_count: 2,
    })

    const malformed = [
      { ...makeRandomBaseline(), unexpected: true },
      {
        ...makeRandomBaseline(),
        cell: {
          ...makeRandomBaseline().cell,
          import_identity_sha256: RIGHT_IMPORT_SHA,
        },
      },
      {
        ...makeRandomBaseline(),
        portfolio_success_probability: {
          ...makeRandomBaseline().portfolio_success_probability,
          decimal_18: '0.018637545002022339',
        },
      },
      {
        ...makeRandomBaseline(),
        readiness: 'READY' as const,
        reason_codes: ['NO_OBSERVATIONS'] as const,
      },
      {
        ...makeRandomBaseline(),
        success_ticket_count: '260625',
      },
      {
        ...makeRandomBaseline(),
        upper_tail_probability: {
          numerator: '1',
          denominator: '1',
          decimal_18: '1.000000000000000000',
        },
      },
    ]
    for (const payload of malformed) {
      fetchMock.mockResolvedValueOnce(apiResponse(payload))
      await expect(getHistoricalSuccessRandomBaseline(query)).rejects.toMatchObject({
        kind: 'MALFORMED_RESPONSE',
      })
    }
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

  it('fetches the recent-50 stability audit with lossless probabilities and exact forwarding', async () => {
    const controller = new AbortController()
    const audit = makeRecent50StabilityAudit()
    audit.recent!.diagnostics[0]!.raw_p_value = {
      numerator: '9007199254740993',
      denominator: '90071992547409931',
    }
    audit.recent!.diagnostics[0]!.adjusted_p_value = {
      ...audit.recent!.diagnostics[0]!.raw_p_value,
    }
    fetchMock.mockResolvedValue(apiResponse(audit))

    const result = await getHistoricalSuccessRecent50StabilityAudit(
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
      '/api/v1/historical-prefix-success-windows/strategies/alias%20strategy%2Fone/v1%20beta/1/feature-cohorts/recent-50-stability-audit',
    )
    expect(Object.fromEntries(url.searchParams)).toEqual({
      import_identity_sha256: IMPORT_SHA,
      prefix_count: '1',
      criterion: 'M3_PLUS',
    })
    expect(init).toMatchObject({ method: 'GET', signal: controller.signal })
    expect(result.audit_status).toBe('COMPLETE')
    expect(result.reference!.diagnostics).toHaveLength(64)
    expect(result.recent!.diagnostics).toHaveLength(64)
    expect(result.comparisons).toHaveLength(64)
    expect(
      BigInt(result.recent!.diagnostics[0]!.raw_p_value.numerator),
    ).toBeGreaterThan(BigInt(Number.MAX_SAFE_INTEGER))
  })

  it('accepts not-ready recent-50 audit without partial families', async () => {
    fetchMock.mockResolvedValue(apiResponse(makeNotReadyRecent50StabilityAudit()))

    const result = await getHistoricalSuccessRecent50StabilityAudit({
      import_identity_sha256: IMPORT_SHA,
      strategy_id: 'alias strategy/one',
      strategy_version: 'v1 beta',
      replicate: 1,
      prefix_count: 1,
      criterion: 'M3_PLUS',
    })

    expect(result.audit_status).toBe('NOT_READY_INSUFFICIENT_HISTORY')
    expect(result.reference).toBeNull()
    expect(result.recent).toBeNull()
    expect(result.comparisons).toEqual([])
  })

  it('fetches ordered cross-import concordance and preserves BigInt probabilities', async () => {
    const controller = new AbortController()
    const concordance = makeCrossImportConcordance()
    concordance.comparisons[0]!.left_confirmation_diagnostic.raw_p_value = {
      numerator: '9007199254740993',
      denominator: '90071992547409931',
    }
    concordance.comparisons[0]!.left_confirmation_diagnostic.adjusted_p_value = {
      ...concordance.comparisons[0]!.left_confirmation_diagnostic.raw_p_value,
    }
    fetchMock.mockResolvedValue(apiResponse(concordance))

    const result = await getHistoricalSuccessCrossImportConcordance(
      {
        left_import_identity_sha256: IMPORT_SHA,
        right_import_identity_sha256: RIGHT_IMPORT_SHA,
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
      '/api/v1/historical-prefix-success-windows/strategies/alias%20strategy%2Fone/v1%20beta/1/feature-cohorts/cross-import-concordance',
    )
    expect(Object.fromEntries(url.searchParams)).toEqual({
      left_import_identity_sha256: IMPORT_SHA,
      right_import_identity_sha256: RIGHT_IMPORT_SHA,
      prefix_count: '1',
      criterion: 'M3_PLUS',
    })
    expect(init).toMatchObject({ method: 'GET', signal: controller.signal })
    expect(result.metadata.left.import_identity_sha256).toBe(IMPORT_SHA)
    expect(result.metadata.right.import_identity_sha256).toBe(RIGHT_IMPORT_SHA)
    expect(result.comparisons).toHaveLength(64)
    expect(
      BigInt(
        result.comparisons[0]!.left_confirmation_diagnostic.raw_p_value.numerator,
      ),
    ).toBeGreaterThan(BigInt(Number.MAX_SAFE_INTEGER))
  })

  it('rejects identical cross-import selectors without issuing a request', async () => {
    await expect(
      getHistoricalSuccessCrossImportConcordance({
        left_import_identity_sha256: IMPORT_SHA,
        right_import_identity_sha256: IMPORT_SHA,
        strategy_id: 'alias strategy/one',
        strategy_version: 'v1 beta',
        replicate: 1,
        prefix_count: 1,
        criterion: 'M3_PLUS',
      }),
    ).rejects.toMatchObject({ kind: 'INVALID_REQUEST', status: 422 })
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('fetches an ordered repeated-query multi-import census and preserves BigInt probabilities', async () => {
    const controller = new AbortController()
    const census = makeMultiImportConcordanceCensus()
    census.cohort_census[0]!.confirmation_diagnostics[0]!.diagnostic.raw_p_value = {
      numerator: '9007199254740993',
      denominator: '90071992547409931',
    }
    census.cohort_census[0]!.confirmation_diagnostics[0]!.diagnostic.adjusted_p_value = {
      ...census.cohort_census[0]!.confirmation_diagnostics[0]!.diagnostic
        .raw_p_value,
    }
    fetchMock.mockResolvedValue(apiResponse(census))

    const result = await getHistoricalSuccessMultiImportConcordanceCensus(
      {
        import_identity_sha256: [
          IMPORT_SHA,
          RIGHT_IMPORT_SHA,
          THIRD_IMPORT_SHA,
        ],
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
      '/api/v1/historical-prefix-success-windows/strategies/alias%20strategy%2Fone/v1%20beta/1/feature-cohorts/multi-import-concordance-census',
    )
    expect(url.searchParams.getAll('import_identity_sha256')).toEqual([
      IMPORT_SHA,
      RIGHT_IMPORT_SHA,
      THIRD_IMPORT_SHA,
    ])
    expect(init).toMatchObject({ method: 'GET', signal: controller.signal })
    expect(result.pair_count).toBe(3)
    expect(result.cohort_census).toHaveLength(64)
    expect(
      BigInt(
        result.cohort_census[0]!.confirmation_diagnostics[0]!.diagnostic
          .raw_p_value.numerator,
      ),
    ).toBeGreaterThan(BigInt(Number.MAX_SAFE_INTEGER))
  })

  it.each([
    [[IMPORT_SHA]],
    [[IMPORT_SHA, IMPORT_SHA]],
    [[IMPORT_SHA, RIGHT_IMPORT_SHA, THIRD_IMPORT_SHA, 'd'.repeat(64), 'e'.repeat(64)]],
    [[IMPORT_SHA, 'BAD']],
  ])('rejects invalid multi-import selectors before fetch', async (identities) => {
    await expect(
      getHistoricalSuccessMultiImportConcordanceCensus({
        import_identity_sha256: identities,
        strategy_id: 'alias strategy/one',
        strategy_version: 'v1 beta',
        replicate: 1,
        prefix_count: 1,
        criterion: 'M3_PLUS',
      }),
    ).rejects.toMatchObject({ kind: 'INVALID_REQUEST', status: 422 })
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('accepts partial readiness only without census rows', async () => {
    const census = makeMultiImportConcordanceCensus()
    census.imports[0]!.holdout_status = 'NOT_READY_INSUFFICIENT_HISTORY'
    census.census_status = 'PARTIAL_NOT_READY'
    census.cohort_census_count = 0
    census.cohort_census = []
    for (const pair of census.pairs) {
      if (pair.left_import_index === 0) {
        pair.left_holdout_status = 'NOT_READY_INSUFFICIENT_HISTORY'
        pair.pair_status = 'LEFT_NOT_READY'
        pair.confirmation_target_overlap = null
      }
    }
    fetchMock.mockResolvedValue(apiResponse(census))

    const result = await getHistoricalSuccessMultiImportConcordanceCensus({
      import_identity_sha256: [IMPORT_SHA, RIGHT_IMPORT_SHA, THIRD_IMPORT_SHA],
      strategy_id: 'alias strategy/one',
      strategy_version: 'v1 beta',
      replicate: 1,
      prefix_count: 1,
      criterion: 'M3_PLUS',
    })

    expect(result.census_status).toBe('PARTIAL_NOT_READY')
    expect(result.cohort_census).toEqual([])
  })

  it.each([
    [
      'pair order',
      (result: ReturnType<typeof makeMultiImportConcordanceCensus>) => {
        ;[result.pairs[0], result.pairs[1]] = [
          result.pairs[1]!,
          result.pairs[0]!,
        ]
      },
    ],
    [
      'direction count',
      (result: ReturnType<typeof makeMultiImportConcordanceCensus>) => {
        result.cohort_census[0]!.higher_count += 1
      },
    ],
    [
      'summary',
      (result: ReturnType<typeof makeMultiImportConcordanceCensus>) => {
        result.cohort_census[0]!.summary = 'MIXED_AVAILABLE'
      },
    ],
    [
      'diagnostic import order',
      (result: ReturnType<typeof makeMultiImportConcordanceCensus>) => {
        result.cohort_census[0]!.confirmation_diagnostics[0]!.import_index = 1
      },
    ],
    [
      'numeric probability',
      (result: ReturnType<typeof makeMultiImportConcordanceCensus>) => {
        result.cohort_census[0]!.confirmation_diagnostics[0]!.diagnostic.raw_p_value.numerator =
          1 as unknown as string
      },
    ],
  ])('rejects malformed multi-import census %s', async (_label, mutate) => {
    const census = makeMultiImportConcordanceCensus()
    mutate(census)
    fetchMock.mockResolvedValue(apiResponse(census))

    await expect(
      getHistoricalSuccessMultiImportConcordanceCensus({
        import_identity_sha256: [IMPORT_SHA, RIGHT_IMPORT_SHA, THIRD_IMPORT_SHA],
        strategy_id: 'alias strategy/one',
        strategy_version: 'v1 beta',
        replicate: 1,
        prefix_count: 1,
        criterion: 'M3_PLUS',
      }),
    ).rejects.toMatchObject({ kind: 'MALFORMED_RESPONSE', status: 502 })
  })

  it('fetches research qualification with exact import order, selectors, and AbortSignal', async () => {
    const controller = new AbortController()
    fetchMock.mockResolvedValue(apiResponse(makeResearchQualification()))

    const result = await getHistoricalSuccessResearchQualification(
      {
        import_identity_sha256: [IMPORT_SHA, RIGHT_IMPORT_SHA],
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
      '/api/v1/historical-prefix-success-windows/strategies/alias%20strategy%2Fone/v1%20beta/1/research-qualification',
    )
    expect(url.searchParams.getAll('import_identity_sha256')).toEqual([
      IMPORT_SHA,
      RIGHT_IMPORT_SHA,
    ])
    expect(Object.fromEntries(url.searchParams)).toMatchObject({
      prefix_count: '1',
      criterion: 'M3_PLUS',
    })
    expect(init).toMatchObject({ method: 'GET', signal: controller.signal })
    expect(result.primary_status).toBe('RESEARCH_CANDIDATE')
    expect(result.informational_flags).toEqual([
      'HISTORICAL_CONCORDANCE_OBSERVED',
    ])
    expect(result.ordered_import_evidence.map(
      (item) => item.import_identity_sha256,
    )).toEqual([IMPORT_SHA, RIGHT_IMPORT_SHA])
  })

  it.each([
    [[IMPORT_SHA]],
    [[IMPORT_SHA, IMPORT_SHA]],
    [[IMPORT_SHA, RIGHT_IMPORT_SHA, THIRD_IMPORT_SHA, 'd'.repeat(64), 'e'.repeat(64)]],
    [[IMPORT_SHA, 'BAD']],
  ])('rejects invalid qualification selectors before fetch', async (identities) => {
    await expect(
      getHistoricalSuccessResearchQualification({
        import_identity_sha256: identities,
        strategy_id: 'alias strategy/one',
        strategy_version: 'v1 beta',
        replicate: 1,
        prefix_count: 1,
        criterion: 'M3_PLUS',
      }),
    ).rejects.toMatchObject({ kind: 'INVALID_REQUEST', status: 422 })
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it.each([
    [
      'flag order',
      (result: ReturnType<typeof makeResearchQualification>) => {
        result.ordered_import_evidence[0]!.recent_relationship_difference_count = 1
        result.informational_flags = [
          'RECENT_RELATIONSHIP_DIFFERENCE',
          'HISTORICAL_CONCORDANCE_OBSERVED',
        ]
      },
    ],
    [
      'contradictory flags',
      (result: ReturnType<typeof makeResearchQualification>) => {
        result.informational_flags = [
          'CROSS_IMPORT_UNRESOLVED',
          'HISTORICAL_CONCORDANCE_OBSERVED',
        ]
      },
    ],
    [
      'candidate caveat',
      (result: ReturnType<typeof makeResearchQualification>) => {
        result.random_baseline_caveat = null
      },
    ],
    [
      'non-candidate caveat',
      (result: ReturnType<typeof makeResearchQualification>) => {
        result.primary_status = 'EVIDENCE_INCOMPLETE'
        result.informational_flags = ['CROSS_IMPORT_UNRESOLVED']
      },
    ],
    [
      'import order',
      (result: ReturnType<typeof makeResearchQualification>) => {
        result.ordered_import_evidence[0]!.import_index = 1
      },
    ],
    [
      'pair comparability',
      (result: ReturnType<typeof makeResearchQualification>) => {
        result.pair_evidence[0]!.r1_comparable = false
      },
    ],
    [
      'pair count',
      (result: ReturnType<typeof makeResearchQualification>) => {
        result.actual_pair_count = 0
      },
    ],
    [
      'recent flag omission',
      (result: ReturnType<typeof makeResearchQualification>) => {
        result.ordered_import_evidence[0]!.recent_relationship_difference_count = 1
      },
    ],
  ])('rejects malformed research qualification %s', async (_label, mutate) => {
    const qualification = makeResearchQualification()
    mutate(qualification)
    fetchMock.mockResolvedValue(apiResponse(qualification))

    await expect(
      getHistoricalSuccessResearchQualification({
        import_identity_sha256: [IMPORT_SHA, RIGHT_IMPORT_SHA],
        strategy_id: 'alias strategy/one',
        strategy_version: 'v1 beta',
        replicate: 1,
        prefix_count: 1,
        criterion: 'M3_PLUS',
      }),
    ).rejects.toMatchObject({ kind: 'MALFORMED_RESPONSE', status: 502 })
  })

  it('fetches qualification random evidence with ordered repeated imports and AbortSignal', async () => {
    const controller = new AbortController()
    fetchMock.mockResolvedValue(
      apiResponse(makeQualificationRandomBaselineEvidence()),
    )

    const result =
      await getHistoricalSuccessQualificationRandomBaselineEvidence(
        {
          import_identity_sha256: [IMPORT_SHA, RIGHT_IMPORT_SHA],
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
      '/api/v1/historical-prefix-success-windows/strategies/alias%20strategy%2Fone/v1%20beta/1/research-qualification/random-baseline-evidence',
    )
    expect(url.searchParams.getAll('import_identity_sha256')).toEqual([
      IMPORT_SHA,
      RIGHT_IMPORT_SHA,
    ])
    expect(init).toMatchObject({ method: 'GET', signal: controller.signal })
    expect(result.availability_summary).toMatchObject({
      availability_status: 'COMPLETE',
      evaluated_cell_count: 8,
      ready_cell_count: 8,
      raw_upper_tail_probability_count: 8,
    })
    expect(
      result.ordered_cells.map((cell) => [
        cell.import_index,
        cell.window_index,
        cell.qualification_random_role,
        cell.baseline.cell.window_kind,
      ]),
    ).toEqual([
      [0, 0, 'REFERENCE_ONLY', 'FULL_HISTORY'],
      [0, 1, 'PRIMARY_DESCRIPTIVE_COMPARISON', 'LONG'],
      [0, 2, 'CONFIRMATION_DESCRIPTIVE_COMPARISON', 'MEDIUM'],
      [0, 3, 'AUDIT_ONLY_NON_BLOCKING', 'SHORT'],
      [1, 0, 'REFERENCE_ONLY', 'FULL_HISTORY'],
      [1, 1, 'PRIMARY_DESCRIPTIVE_COMPARISON', 'LONG'],
      [1, 2, 'CONFIRMATION_DESCRIPTIVE_COMPARISON', 'MEDIUM'],
      [1, 3, 'AUDIT_ONLY_NON_BLOCKING', 'SHORT'],
    ])
  })

  it.each([
    [[IMPORT_SHA]],
    [[IMPORT_SHA, IMPORT_SHA]],
    [
      [
        IMPORT_SHA,
        RIGHT_IMPORT_SHA,
        THIRD_IMPORT_SHA,
        'd'.repeat(64),
        'e'.repeat(64),
      ],
    ],
    [[IMPORT_SHA, 'BAD']],
  ])(
    'rejects invalid qualification random-evidence selectors before fetch',
    async (identities) => {
      await expect(
        getHistoricalSuccessQualificationRandomBaselineEvidence({
          import_identity_sha256: identities,
          strategy_id: 'alias strategy/one',
          strategy_version: 'v1 beta',
          replicate: 1,
          prefix_count: 1,
          criterion: 'M3_PLUS',
        }),
      ).rejects.toMatchObject({ kind: 'INVALID_REQUEST', status: 422 })
      expect(fetchMock).not.toHaveBeenCalled()
    },
  )

  it('accepts a closed PARTIAL aggregate without fabricating not-ready values', async () => {
    const aggregate = makeQualificationRandomBaselineEvidence()
    const notReady = makeNotReadyRandomBaseline()
    aggregate.ordered_cells[0]!.baseline = {
      ...notReady,
      cell: { ...aggregate.ordered_cells[0]!.baseline.cell },
    }
    aggregate.availability_summary.availability_status = 'PARTIAL'
    aggregate.availability_summary.ready_cell_count = 7
    aggregate.availability_summary.raw_upper_tail_probability_count = 7
    fetchMock.mockResolvedValue(apiResponse(aggregate))

    const result =
      await getHistoricalSuccessQualificationRandomBaselineEvidence({
        import_identity_sha256: [IMPORT_SHA, RIGHT_IMPORT_SHA],
        strategy_id: 'alias strategy/one',
        strategy_version: 'v1 beta',
        replicate: 1,
        prefix_count: 1,
        criterion: 'M3_PLUS',
      })

    expect(result.availability_summary.availability_status).toBe('PARTIAL')
    expect(result.ordered_cells[0]!.baseline).toMatchObject({
      readiness: 'NOT_READY',
      observed_success_count: null,
      expected_successes: null,
      upper_tail_probability: null,
    })
  })

  it.each([
    [
      'cell order',
      (result: ReturnType<typeof makeQualificationRandomBaselineEvidence>) => {
        ;[result.ordered_cells[0], result.ordered_cells[1]] = [
          result.ordered_cells[1]!,
          result.ordered_cells[0]!,
        ]
      },
    ],
    [
      'role mismatch',
      (result: ReturnType<typeof makeQualificationRandomBaselineEvidence>) => {
        result.ordered_cells[0]!.qualification_random_role =
          'AUDIT_ONLY_NON_BLOCKING'
      },
    ],
    [
      'import identity mismatch',
      (result: ReturnType<typeof makeQualificationRandomBaselineEvidence>) => {
        result.ordered_cells[0]!.baseline.cell.import_identity_sha256 =
          THIRD_IMPORT_SHA
      },
    ],
    [
      'source hash drift',
      (result: ReturnType<typeof makeQualificationRandomBaselineEvidence>) => {
        result.ordered_cells[1]!.baseline.cell.dataset_sha256 = '9'.repeat(64)
      },
    ],
    [
      'availability count',
      (result: ReturnType<typeof makeQualificationRandomBaselineEvidence>) => {
        result.availability_summary.ready_cell_count = 7
      },
    ],
    [
      'warning',
      (result: ReturnType<typeof makeQualificationRandomBaselineEvidence>) => {
        result.availability_summary.multiple_testing_warning =
          'No warning available.'
      },
    ],
    [
      'numeric rational',
      (result: ReturnType<typeof makeQualificationRandomBaselineEvidence>) => {
        result.ordered_cells[0]!.baseline.upper_tail_probability!.numerator =
          1 as unknown as string
      },
    ],
    [
      'extra field',
      (result: ReturnType<typeof makeQualificationRandomBaselineEvidence>) => {
        ;(
          result as HistoricalSuccessQualificationRandomBaselineEvidence & {
            adjusted_probability?: string
          }
        ).adjusted_probability = '0.5'
      },
    ],
  ])(
    'rejects malformed qualification random evidence %s',
    async (_label, mutate) => {
      const aggregate = makeQualificationRandomBaselineEvidence()
      mutate(aggregate)
      fetchMock.mockResolvedValue(apiResponse(aggregate))

      await expect(
        getHistoricalSuccessQualificationRandomBaselineEvidence({
          import_identity_sha256: [IMPORT_SHA, RIGHT_IMPORT_SHA],
          strategy_id: 'alias strategy/one',
          strategy_version: 'v1 beta',
          replicate: 1,
          prefix_count: 1,
          criterion: 'M3_PLUS',
        }),
      ).rejects.toMatchObject({ kind: 'MALFORMED_RESPONSE', status: 502 })
    },
  )

  it('accepts every not-ready cross-import pair status only without a family', async () => {
    for (const [pair_status, left_holdout_status, right_holdout_status] of [
      ['LEFT_NOT_READY', 'NOT_READY_INSUFFICIENT_HISTORY', 'COMPLETE'],
      ['RIGHT_NOT_READY', 'COMPLETE', 'NOT_READY_INSUFFICIENT_HISTORY'],
      [
        'BOTH_NOT_READY',
        'NOT_READY_INSUFFICIENT_HISTORY',
        'NOT_READY_INSUFFICIENT_HISTORY',
      ],
    ] as const) {
      fetchMock.mockResolvedValueOnce(
        apiResponse(
          makeNotReadyCrossImportConcordance({
            pair_status,
            left_holdout_status,
            right_holdout_status,
          }),
        ),
      )
      const result = await getHistoricalSuccessCrossImportConcordance({
        left_import_identity_sha256: IMPORT_SHA,
        right_import_identity_sha256: RIGHT_IMPORT_SHA,
        strategy_id: 'alias strategy/one',
        strategy_version: 'v1 beta',
        replicate: 1,
        prefix_count: 1,
        criterion: 'M3_PLUS',
      })
      expect(result.pair_status).toBe(pair_status)
      expect(result.confirmation_target_overlap).toBeNull()
      expect(result.comparisons).toEqual([])
    }
  })

  it.each([
    [
      'malformed overlap arithmetic',
      (result: ReturnType<typeof makeCrossImportConcordance>) => {
        result.confirmation_target_overlap!.overlap_count = 299
      },
    ],
    [
      'missing comparison',
      (result: ReturnType<typeof makeCrossImportConcordance>) => {
        result.comparisons.pop()
      },
    ],
    [
      'duplicate comparison',
      (result: ReturnType<typeof makeCrossImportConcordance>) => {
        result.comparisons[1] = result.comparisons[0]!
      },
    ],
    [
      'wrong order',
      (result: ReturnType<typeof makeCrossImportConcordance>) => {
        ;[result.comparisons[0], result.comparisons[1]] = [
          result.comparisons[1]!,
          result.comparisons[0]!,
        ]
      },
    ],
    [
      'identity mismatch',
      (result: ReturnType<typeof makeCrossImportConcordance>) => {
        result.metadata.right.import_identity_sha256 = 'c'.repeat(64)
      },
    ],
    [
      'numeric probability',
      (result: ReturnType<typeof makeCrossImportConcordance>) => {
        result.comparisons[0]!.right_confirmation_diagnostic.raw_p_value.numerator =
          1 as unknown as string
      },
    ],
  ])('rejects cross-import concordance with %s', async (_label, mutate) => {
    const concordance = makeCrossImportConcordance()
    mutate(concordance)
    fetchMock.mockResolvedValue(apiResponse(concordance))

    await expect(
      getHistoricalSuccessCrossImportConcordance({
        left_import_identity_sha256: IMPORT_SHA,
        right_import_identity_sha256: RIGHT_IMPORT_SHA,
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
      'wrong reference count',
      (result: ReturnType<typeof makeRecent50StabilityAudit>) => {
        result.split.reference_count = 249 as 250
      },
    ],
    [
      'overlapping boundary',
      (result: ReturnType<typeof makeRecent50StabilityAudit>) => {
        result.split.recent_first_target = result.split.reference_last_target
      },
    ],
    [
      'missing reference diagnostic',
      (result: ReturnType<typeof makeRecent50StabilityAudit>) => {
        result.reference!.diagnostics.pop()
      },
    ],
    [
      'missing recent diagnostic',
      (result: ReturnType<typeof makeRecent50StabilityAudit>) => {
        result.recent!.diagnostics.pop()
      },
    ],
    [
      'missing comparison',
      (result: ReturnType<typeof makeRecent50StabilityAudit>) => {
        result.comparisons.pop()
      },
    ],
    [
      'duplicate comparison',
      (result: ReturnType<typeof makeRecent50StabilityAudit>) => {
        result.comparisons[1] = result.comparisons[0]!
      },
    ],
    [
      'numeric probability',
      (result: ReturnType<typeof makeRecent50StabilityAudit>) => {
        result.recent!.diagnostics[0]!.raw_p_value.numerator =
          1 as unknown as string
      },
    ],
    [
      'reversed effect subtraction',
      (result: ReturnType<typeof makeRecent50StabilityAudit>) => {
        result.comparisons[0]!.effect_change.numerator += 1
      },
    ],
  ])('rejects recent-50 stability audit with %s', async (_label, mutate) => {
    const audit = makeRecent50StabilityAudit()
    mutate(audit)
    fetchMock.mockResolvedValue(apiResponse(audit))

    await expect(
      getHistoricalSuccessRecent50StabilityAudit({
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
