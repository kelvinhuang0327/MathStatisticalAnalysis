// @vitest-environment jsdom

import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import HistoricalSuccessWindowsPage from '../src/features/historical-success-windows/HistoricalSuccessWindowsPage.vue'
import {
  apiResponse,
  deferred,
  IMPORT_SHA,
  RIGHT_IMPORT_SHA,
  makeAllRelationsMatrix,
  makeFeatureCohortDiagnostics,
  makeFeatureCohortDiagnosticsForResult,
  makeFeatureCohorts,
  makeFeatureCohortsForResult,
  makeCrossImportConcordance,
  makeMultiImportConcordanceCensus,
  makeMatrix,
  makeResult,
  makeRun,
  makeRunPage,
  makeNotReadyTemporalHoldout,
  makeNotReadyRecent50StabilityAudit,
  makeNotReadyRandomBaseline,
  makeNotReadyCrossImportConcordance,
  makeTemporalHoldout,
  makeRecent50StabilityAudit,
  makeRandomBaseline,
  makeQualificationRandomBaselineEvidence,
  makeResearchQualification,
  makeWindowPage,
  makeZeroObservationFeatureCohortDiagnostics,
  makeZeroObservationFeatureCohorts,
  makeZeroObservationMatrix,
  makeZeroObservationResult,
  THIRD_IMPORT_SHA,
} from './historical-success-windows-fixtures'

let fetchMock: ReturnType<typeof vi.fn<typeof fetch>>

function successfulFetch(input: RequestInfo | URL): Promise<Response> {
  const url = String(input)
  if (url.includes('/random-null-baseline')) {
    return Promise.resolve(apiResponse(makeRandomBaseline()))
  }
  if (url.includes('/research-qualification/random-baseline-evidence')) {
    return Promise.resolve(
      apiResponse(makeQualificationRandomBaselineEvidence()),
    )
  }
  if (url.includes('/research-qualification')) {
    return Promise.resolve(apiResponse(makeResearchQualification()))
  }
  if (url.includes('/feature-cohorts/multi-import-concordance-census')) {
    return Promise.resolve(apiResponse(makeMultiImportConcordanceCensus()))
  }
  if (url.includes('/feature-cohorts/cross-import-concordance')) {
    return Promise.resolve(apiResponse(makeCrossImportConcordance()))
  }
  if (url.includes('/feature-cohorts/temporal-holdout')) {
    return Promise.resolve(apiResponse(makeTemporalHoldout()))
  }
  if (url.includes('/feature-cohorts/recent-50-stability-audit')) {
    return Promise.resolve(apiResponse(makeRecent50StabilityAudit()))
  }
  if (url.includes('/feature-cohorts/diagnostics')) {
    return Promise.resolve(apiResponse(makeFeatureCohortDiagnostics()))
  }
  if (url.includes('/feature-cohorts')) {
    return Promise.resolve(apiResponse(makeFeatureCohorts()))
  }
  if (url.includes('/matrix')) return Promise.resolve(apiResponse(makeMatrix()))
  if (url.includes('/strategies/')) return Promise.resolve(apiResponse(makeResult()))
  if (url.includes('/historical-prefix-success-windows')) {
    return Promise.resolve(apiResponse(makeWindowPage()))
  }
  return Promise.resolve(apiResponse(makeRunPage()))
}

async function mountWithRuns(): Promise<VueWrapper> {
  fetchMock.mockImplementation(successfulFetch)
  const wrapper = mount(HistoricalSuccessWindowsPage)
  await flushPromises()
  return wrapper
}

async function selectRun(wrapper: VueWrapper): Promise<void> {
  await wrapper.get('select[name="historical-run"]').setValue(IMPORT_SHA)
}

async function analyze(wrapper: VueWrapper): Promise<void> {
  await wrapper.get('form.analysis-controls').trigger('submit')
  await flushPromises()
}

async function selectMatrix(wrapper: VueWrapper, index = 0): Promise<void> {
  await wrapper.findAll('input.matrix-select')[index]!.setValue(true)
}

async function compareMatrices(wrapper: VueWrapper): Promise<void> {
  await wrapper.get('button.matrix-compare').trigger('click')
  await flushPromises()
}

async function loadRandomBaselines(wrapper: VueWrapper): Promise<void> {
  await wrapper.get('button.random-baseline-load').trigger('click')
  await flushPromises()
}

async function evaluateFeatureCohorts(wrapper: VueWrapper): Promise<void> {
  await wrapper.get('button.feature-cohort-evaluate').trigger('click')
  await flushPromises()
}

async function evaluateFeatureCohortDiagnostics(
  wrapper: VueWrapper,
): Promise<void> {
  await wrapper.get('button.feature-cohort-diagnostics-evaluate').trigger('click')
  await flushPromises()
}

async function evaluateTemporalHoldout(wrapper: VueWrapper): Promise<void> {
  await wrapper.get('button.temporal-holdout-action').trigger('click')
  await flushPromises()
}

async function evaluateRecent50StabilityAudit(wrapper: VueWrapper): Promise<void> {
  await wrapper.get('button.recent-50-stability-audit-action').trigger('click')
  await flushPromises()
}

async function evaluateCrossImportConcordance(wrapper: VueWrapper): Promise<void> {
  await wrapper.get('button.cross-import-concordance-action').trigger('click')
  await flushPromises()
}

async function evaluateMultiImportCensus(wrapper: VueWrapper): Promise<void> {
  await wrapper.get('button.multi-import-census-action').trigger('click')
  await flushPromises()
}

async function evaluateResearchQualification(
  wrapper: VueWrapper,
): Promise<void> {
  await wrapper.get('button.research-qualification-action').trigger('click')
  await flushPromises()
}

beforeEach(() => {
  fetchMock = vi.fn<typeof fetch>()
  vi.stubGlobal('fetch', fetchMock)
  Object.defineProperty(navigator, 'clipboard', {
    configurable: true,
    value: { writeText: vi.fn().mockResolvedValue(undefined) },
  })
})

afterEach(() => vi.unstubAllGlobals())

describe('HistoricalSuccessWindowsPage', () => {
  it('loads run metadata without selecting a run or requesting analysis', async () => {
    const wrapper = await mountWithRuns()

    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(String(fetchMock.mock.calls[0]?.[0])).toContain('/historical-results/runs')
    expect((wrapper.get('select[name="historical-run"]').element as HTMLSelectElement).value).toBe('')
    expect((wrapper.get('select[name="comparison-run"]').element as HTMLSelectElement).value).toBe('')
    expect(wrapper.get('button[type="submit"]').attributes('disabled')).toBeDefined()
    expect(wrapper.text()).toContain('Results remain empty until Analyze is activated.')
    wrapper.unmount()
  })

  it('offers all closed prefix and criterion sets and requires explicit Analyze', async () => {
    const wrapper = await mountWithRuns()

    expect(
      wrapper.get('select[name="prefix-count"]').findAll('option').map((option) => option.text()),
    ).toEqual(['1', '2', '3', '4', '5', '10', '15', '20'])
    expect(
      wrapper.get('select[name="criterion"]').findAll('option').map((option) => option.text()),
    ).toEqual([
      'M3_PLUS',
      'M4_PLUS',
      'M5_PLUS',
      'M6',
      'M2_PLUS_SPECIAL',
      'M3_PLUS_SPECIAL',
      'M4_PLUS_SPECIAL',
      'M5_PLUS_SPECIAL',
    ])

    await selectRun(wrapper)
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('Run selected. No analysis request has been made yet.')

    await analyze(wrapper)
    expect(fetchMock).toHaveBeenCalledTimes(2)
    const url = new URL(String(fetchMock.mock.calls[1]?.[0]), 'http://localhost')
    expect(Object.fromEntries(url.searchParams)).toMatchObject({
      import_identity_sha256: IMPORT_SHA,
      prefix_count: '1',
      criterion: 'M3_PLUS',
    })
    wrapper.unmount()
  })

  it('renders aliases, replicates, zero observations, canonical windows, and exact fractions in server order', async () => {
    const wrapper = await mountWithRuns()
    await selectRun(wrapper)
    await analyze(wrapper)

    const cards = wrapper.findAll('.strategy-window-card')
    expect(cards).toHaveLength(2)
    expect(cards[0]!.text()).toContain('alias strategy/one')
    expect(cards[0]!.text()).toContain('Alias targeteffective-strategy')
    expect(cards[1]!.text()).toContain('replicate 2')
    expect(cards[1]!.text()).toContain('ZERO OBSERVATIONS')
    expect(cards[0]!.findAll('.window-card').map((window) => window.text())).toEqual([
      expect.stringContaining('FULL_HISTORYREFERENCE_ONLY'),
      expect.stringContaining('LONGPRIMARY_EVIDENCE'),
      expect.stringContaining('MEDIUMSTABILITY_CONFIRMATION'),
      expect.stringContaining('SHORTDEGRADATION_VETO'),
    ])
    expect(cards[0]!.text()).toContain('1 / 4')
    expect(wrapper.text()).not.toMatch(/\d+(?:\.\d+)?%/)
    expect(wrapper.text()).not.toContain('PROMOTION_FILTER')
    expect(wrapper.text()).not.toMatch(/winner|best strategy/i)
    wrapper.unmount()
  })

  it('never requests a matrix until the explicit compare action', async () => {
    const wrapper = await mountWithRuns()
    await selectRun(wrapper)
    await wrapper.get('select[name="prefix-count"]').setValue('2')
    await wrapper.get('select[name="criterion"]').setValue('M4_PLUS')
    expect(fetchMock).toHaveBeenCalledTimes(1)
    await wrapper.get('select[name="prefix-count"]').setValue('1')
    await wrapper.get('select[name="criterion"]').setValue('M3_PLUS')

    await analyze(wrapper)
    expect(fetchMock).toHaveBeenCalledTimes(2)
    await selectMatrix(wrapper)
    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('1 exact identity selected in manual order.')

    await compareMatrices(wrapper)
    expect(fetchMock).toHaveBeenCalledTimes(3)
    expect(String(fetchMock.mock.calls[2]?.[0])).toContain('/matrix?')
    wrapper.unmount()
  })

  it('preserves ordered selections across pagination and control changes and rejects a fifth identity', async () => {
    const items = Array.from({ length: 5 }, (_, index) => {
      const base = makeResult()
      const strategyId = index === 0 ? 'alias strategy/one' : `strategy-${index + 1}`
      return makeResult({
        strategy: {
          ...base.strategy,
          strategy_id: strategyId,
          effective_strategy_id: index === 0 ? 'effective-strategy' : strategyId,
          replicate: index === 4 ? 2 : 1,
          descriptor_sha256: String(index + 1).repeat(64),
        },
        selection: {
          ...base.selection,
          strategy_id: strategyId,
          replicate: index === 4 ? 2 : 1,
        },
      })
    })
    const firstPage = makeWindowPage({ items, total_count: 25 })
    const secondPage = makeWindowPage({ items: [items[4]!], total_count: 25, offset: 20 })
    fetchMock.mockImplementation((input) => {
      const url = String(input)
      if (url.includes('/historical-results/runs')) return Promise.resolve(apiResponse(makeRunPage()))
      return Promise.resolve(apiResponse(url.includes('offset=20') ? secondPage : firstPage))
    })
    const wrapper = mount(HistoricalSuccessWindowsPage)
    await flushPromises()
    await selectRun(wrapper)
    await analyze(wrapper)
    for (const checkbox of wrapper.findAll('input.matrix-select').slice(0, 4)) {
      await checkbox.setValue(true)
    }

    expect(wrapper.findAll('input.matrix-select')[4]!.attributes('disabled')).toBeDefined()
    expect(wrapper.text()).toContain('Selection limit reached: four exact identities.')
    await wrapper.get('nav[aria-label="Historical Success Window pages"] button:last-child').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('4 exact identities selected in manual order.')
    expect(wrapper.findAll('input.matrix-select')[0]!.attributes('disabled')).toBeDefined()

    await wrapper.get('select[name="prefix-count"]').setValue('5')
    await wrapper.get('select[name="criterion"]').setValue('M5_PLUS_SPECIAL')
    expect(wrapper.text()).toContain('4 exact identities selected in manual order.')
    wrapper.unmount()
  })

  it('issues exactly N matrix requests in selection order and renders exact neutral values', async () => {
    const first = makeResult()
    const second = makeZeroObservationResult()
    fetchMock.mockImplementation((input) => {
      const url = String(input)
      if (url.includes('/historical-results/runs')) return Promise.resolve(apiResponse(makeRunPage()))
      if (url.includes('/matrix')) {
        return Promise.resolve(
          apiResponse(
            url.includes('zero-observation')
              ? makeZeroObservationMatrix()
              : {
                  ...makeAllRelationsMatrix(),
                  strategy: first.strategy,
                },
          ),
        )
      }
      return Promise.resolve(apiResponse(makeWindowPage({ items: [first, second] })))
    })
    const wrapper = mount(HistoricalSuccessWindowsPage)
    await flushPromises()
    await selectRun(wrapper)
    await analyze(wrapper)
    await selectMatrix(wrapper, 1)
    await selectMatrix(wrapper, 0)
    fetchMock.mockClear()

    await compareMatrices(wrapper)

    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(String(fetchMock.mock.calls[0]?.[0])).toContain('/zero-observation/v2/2/matrix?')
    expect(String(fetchMock.mock.calls[1]?.[0])).toContain(
      '/alias%20strategy%2Fone/v1%20beta/1/matrix?',
    )
    const cards = wrapper.findAll('.matrix-result-card')
    expect(cards).toHaveLength(2)
    expect(cards[0]!.text()).toContain('zero-observation')
    expect(cards[0]!.text()).toContain('Zero-observation matrix')
    expect(cards[1]!.text()).toContain('1 / 4')
    expect(cards[1]!.text()).toContain('HIGHER')
    expect(cards[1]!.text()).toContain('EQUAL')
    expect(cards[1]!.text()).toContain('LOWER')
    expect(cards[1]!.text()).toContain('UNAVAILABLE')
    expect(cards[1]!.text()).not.toMatch(/winner|ranking|promotion|rejection|prediction/i)
    wrapper.unmount()
  })

  it('copies and forwards the exact run SHA unchanged', async () => {
    const wrapper = await mountWithRuns()
    await selectRun(wrapper)

    await wrapper.get('.copy-button').trigger('click')
    await flushPromises()

    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(IMPORT_SHA)
    expect(wrapper.text()).toContain('Copied')
    wrapper.unmount()
  })

  it('paginates server results without changing the selected controls or client-sorting', async () => {
    const first = makeWindowPage({ total_count: 22 })
    const second = makeWindowPage({ total_count: 22, offset: 20 })
    fetchMock.mockImplementation((input) => {
      const url = String(input)
      if (url.includes('/historical-results/runs')) return Promise.resolve(apiResponse(makeRunPage()))
      return Promise.resolve(apiResponse(url.includes('offset=20') ? second : first))
    })
    const wrapper = mount(HistoricalSuccessWindowsPage)
    await flushPromises()
    await selectRun(wrapper)
    await analyze(wrapper)

    await wrapper.get('nav[aria-label="Historical Success Window pages"] button:last-child').trigger('click')
    await flushPromises()

    const url = new URL(String(fetchMock.mock.calls.at(-1)?.[0]), 'http://localhost')
    expect(url.searchParams.get('offset')).toBe('20')
    expect(url.searchParams.get('import_identity_sha256')).toBe(IMPORT_SHA)
    expect((wrapper.get('select[name="historical-run"]').element as HTMLSelectElement).value).toBe(IMPORT_SHA)
    expect((wrapper.get('select[name="prefix-count"]').element as HTMLSelectElement).value).toBe('1')
    expect((wrapper.get('select[name="criterion"]').element as HTMLSelectElement).value).toBe('M3_PLUS')
    wrapper.unmount()
  })

  it('uses the exact strategy endpoint instead of deriving detail from the list', async () => {
    const wrapper = await mountWithRuns()
    await selectRun(wrapper)
    await analyze(wrapper)
    fetchMock.mockClear()
    fetchMock.mockResolvedValue(apiResponse(makeResult()))

    await wrapper.findAll('.inspect-button')[0]!.trigger('click')
    await flushPromises()

    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(String(fetchMock.mock.calls[0]?.[0])).toContain(
      '/strategies/alias%20strategy%2Fone/v1%20beta/1?',
    )
    expect(wrapper.get('.detail-panel').text()).toContain('alias strategy/one')
    wrapper.unmount()
  })

  it.each([
    [404, 'HISTORICAL_PREFIX_SUCCESS_IMPORT_NOT_FOUND', 'no longer exists'],
    [422, 'REQUEST_VALIDATION_FAILED', 'rejected the exact historical selection'],
    [503, 'HISTORICAL_PREFIX_SUCCESS_WINDOWS_UNAVAILABLE', 'database is unavailable'],
  ] as const)('renders recoverable sanitized analysis state for HTTP %s', async (status, code, text) => {
    fetchMock
      .mockResolvedValueOnce(apiResponse(makeRunPage()))
      .mockResolvedValueOnce(apiResponse({ error_code: code, message: '/secret/path' }, status))
      .mockResolvedValueOnce(apiResponse(makeWindowPage()))
    const wrapper = mount(HistoricalSuccessWindowsPage)
    await flushPromises()
    await selectRun(wrapper)
    await analyze(wrapper)

    expect(wrapper.text()).toContain(text)
    expect(wrapper.text()).not.toContain('/secret/path')
    await wrapper.get('.research-state--error .button').trigger('click')
    await flushPromises()
    expect(wrapper.findAll('.strategy-window-card')).toHaveLength(2)
    wrapper.unmount()
  })

  it('renders configuration-required, no-runs, and malformed-response states', async () => {
    fetchMock.mockResolvedValueOnce(
      apiResponse({ error_code: 'HISTORICAL_RESULTS_NOT_CONFIGURED', message: '/secret' }, 503),
    )
    const unconfigured = mount(HistoricalSuccessWindowsPage)
    await flushPromises()
    expect(unconfigured.text()).toContain('Historical database configuration required.')
    expect(unconfigured.text()).not.toContain('/secret')
    unconfigured.unmount()

    fetchMock.mockResolvedValueOnce(apiResponse(makeRunPage({ items: [], total_count: 0 })))
    const empty = mount(HistoricalSuccessWindowsPage)
    await flushPromises()
    expect(empty.text()).toContain('No completed Historical Results runs are available.')
    empty.unmount()

    fetchMock
      .mockResolvedValueOnce(apiResponse(makeRunPage()))
      .mockResolvedValueOnce(apiResponse({ malformed: true }))
    const malformed = mount(HistoricalSuccessWindowsPage)
    await flushPromises()
    await selectRun(malformed)
    await analyze(malformed)
    expect(malformed.text()).toContain('invalid historical response')
    malformed.unmount()
  })

  it('keeps successful matrices on partial failure and retries with sanitized errors', async () => {
    const wrapper = await mountWithRuns()
    await selectRun(wrapper)
    await analyze(wrapper)
    await selectMatrix(wrapper, 0)
    await selectMatrix(wrapper, 1)
    fetchMock.mockReset()
    fetchMock.mockImplementation((input) =>
      String(input).includes('zero-observation')
        ? Promise.resolve(
            apiResponse(
              {
                error_code: 'HISTORICAL_PREFIX_SUCCESS_STRATEGY_NOT_FOUND',
                message: '/secret/path',
              },
              404,
            ),
          )
        : Promise.resolve(apiResponse(makeMatrix())),
    )

    await compareMatrices(wrapper)

    expect(wrapper.text()).toContain('Some exact matrices are unavailable')
    expect(wrapper.findAll('.matrix-result-card')).toHaveLength(2)
    expect(wrapper.text()).toContain('no longer exists')
    expect(wrapper.text()).not.toContain('/secret/path')

    fetchMock.mockReset()
    fetchMock.mockImplementation((input) =>
      Promise.resolve(
        apiResponse(
          String(input).includes('zero-observation')
            ? makeZeroObservationMatrix()
            : makeMatrix(),
        ),
      ),
    )
    await wrapper.get('button.matrix-retry').trigger('click')
    await flushPromises()
    expect(wrapper.findAll('.matrix-result-card')).toHaveLength(2)
    expect(wrapper.text()).not.toContain('Some exact matrices are unavailable')
    wrapper.unmount()
  })

  it('aborts prior matrix comparisons, ignores stale responses, and clears on run change', async () => {
    const wrapper = await mountWithRuns()
    await selectRun(wrapper)
    await analyze(wrapper)
    await selectMatrix(wrapper)
    const older = deferred<Response>()
    const newer = deferred<Response>()
    fetchMock.mockReset()
    fetchMock.mockReturnValueOnce(older.promise).mockReturnValueOnce(newer.promise)

    await wrapper.get('button.matrix-compare').trigger('click')
    const oldSignal = fetchMock.mock.calls[0]?.[1]?.signal as AbortSignal
    await wrapper.get('button.matrix-compare').trigger('click')
    expect(oldSignal.aborted).toBe(true)
    newer.resolve(apiResponse(makeMatrix()))
    await flushPromises()
    older.resolve(apiResponse(makeMatrix({ strategy: { ...makeMatrix().strategy, strategy_id: 'stale' } })))
    await flushPromises()
    expect(wrapper.findAll('.matrix-result-card')).toHaveLength(1)
    expect(wrapper.text()).not.toContain('stale')

    const pending = deferred<Response>()
    fetchMock.mockReset()
    fetchMock.mockReturnValueOnce(pending.promise)
    await wrapper.get('button.matrix-compare').trigger('click')
    const runChangeSignal = fetchMock.mock.calls[0]?.[1]?.signal as AbortSignal
    await wrapper.get('select[name="historical-run"]').setValue('')
    expect(runChangeSignal.aborted).toBe(true)
    expect(wrapper.findAll('.matrix-result-card')).toHaveLength(0)
    expect(wrapper.text()).toContain('Select a run before choosing stability matrices.')
    pending.resolve(apiResponse(makeMatrix()))
    await flushPromises()
    expect(wrapper.findAll('.matrix-result-card')).toHaveLength(0)
    wrapper.unmount()
  })

  it('aborts every in-flight matrix request on unmount', async () => {
    const wrapper = await mountWithRuns()
    await selectRun(wrapper)
    await analyze(wrapper)
    await selectMatrix(wrapper, 0)
    await selectMatrix(wrapper, 1)
    fetchMock.mockReset()
    fetchMock.mockImplementation(() => new Promise<Response>(() => undefined))

    await wrapper.get('button.matrix-compare').trigger('click')
    const signals = fetchMock.mock.calls.map((call) => call[1]?.signal as AbortSignal)
    expect(signals).toHaveLength(2)
    expect(signals.every((signal) => !signal.aborted)).toBe(true)
    wrapper.unmount()
    expect(signals.every((signal) => signal.aborted)).toBe(true)
  })

  it('aborts and ignores stale run-list and analysis responses', async () => {
    const wrapper = await mountWithRuns()
    const olderRuns = deferred<Response>()
    const newerRuns = deferred<Response>()
    fetchMock.mockReset()
    fetchMock.mockReturnValueOnce(olderRuns.promise).mockReturnValueOnce(newerRuns.promise)

    await wrapper.get('.refresh-runs').trigger('click')
    const oldRunSignal = fetchMock.mock.calls[0]?.[1]?.signal as AbortSignal
    await wrapper.get('.refresh-runs').trigger('click')
    expect(oldRunSignal.aborted).toBe(true)
    newerRuns.resolve(apiResponse(makeRunPage({ items: [makeRun({ dataset_identity: 'newer-runs' })] })))
    await flushPromises()
    olderRuns.resolve(apiResponse(makeRunPage({ items: [makeRun({ dataset_identity: 'stale-runs' })] })))
    await flushPromises()
    expect(wrapper.text()).toContain('newer-runs')
    expect(wrapper.text()).not.toContain('stale-runs')

    await selectRun(wrapper)
    const olderAnalysis = deferred<Response>()
    const newerAnalysis = deferred<Response>()
    fetchMock.mockReset()
    fetchMock.mockReturnValueOnce(olderAnalysis.promise).mockReturnValueOnce(newerAnalysis.promise)
    await wrapper.get('form.analysis-controls').trigger('submit')
    const oldAnalysisSignal = fetchMock.mock.calls[0]?.[1]?.signal as AbortSignal
    await wrapper.get('select[name="historical-run"]').setValue('')
    expect(oldAnalysisSignal.aborted).toBe(true)
    await wrapper.get('select[name="historical-run"]').setValue(IMPORT_SHA)
    await wrapper.get('form.analysis-controls').trigger('submit')
    newerAnalysis.resolve(apiResponse(makeWindowPage()))
    await flushPromises()
    olderAnalysis.resolve(apiResponse(makeWindowPage({ items: [makeZeroObservationResult()] })))
    await flushPromises()
    expect(wrapper.findAll('.strategy-window-card')).toHaveLength(2)
    wrapper.unmount()
  })

  it('aborts stale exact-detail responses and all pending work on unmount', async () => {
    const wrapper = await mountWithRuns()
    await selectRun(wrapper)
    await analyze(wrapper)
    const older = deferred<Response>()
    const newer = deferred<Response>()
    fetchMock.mockReset()
    fetchMock.mockReturnValueOnce(older.promise).mockReturnValueOnce(newer.promise)

    await wrapper.findAll('.inspect-button')[0]!.trigger('click')
    const firstSignal = fetchMock.mock.calls[0]?.[1]?.signal as AbortSignal
    await wrapper.findAll('.inspect-button')[1]!.trigger('click')
    expect(firstSignal.aborted).toBe(true)
    const secondSignal = fetchMock.mock.calls[1]?.[1]?.signal as AbortSignal
    newer.resolve(apiResponse(makeZeroObservationResult()))
    await flushPromises()
    older.resolve(apiResponse(makeResult()))
    await flushPromises()
    expect(wrapper.get('.detail-panel').text()).toContain('zero-observation')
    expect(wrapper.get('.detail-panel').text()).not.toContain('alias strategy/one')

    fetchMock.mockReturnValueOnce(new Promise<Response>(() => undefined))
    await wrapper.findAll('.inspect-button')[0]!.trigger('click')
    const unmountSignal = fetchMock.mock.calls[2]?.[1]?.signal as AbortSignal
    expect(unmountSignal.aborted).toBe(false)
    wrapper.unmount()
    expect(unmountSignal.aborted).toBe(true)
    expect(secondSignal.aborted).toBe(true)
  })

  it('keeps the random baseline explicit, defaults to LONG, and loads one to four strategies in selection order', async () => {
    const strategies = Array.from({ length: 4 }, (_, index) => {
      const base = makeResult()
      const strategyId = `strategy-${index + 1}`
      return makeResult({
        strategy: {
          ...base.strategy,
          strategy_id: strategyId,
          effective_strategy_id: strategyId,
          alias_of_strategy_id: null,
          descriptor_sha256: String(index + 1).repeat(64),
        },
        selection: {
          ...base.selection,
          strategy_id: strategyId,
        },
      })
    })
    const page = makeWindowPage({
      items: strategies,
      total_count: strategies.length,
    })
    fetchMock.mockImplementation((input) => {
      const url = new URL(String(input), 'http://localhost')
      if (url.pathname.includes('/random-null-baseline')) {
        const match = url.pathname.match(
          /\/strategies\/([^/]+)\/([^/]+)\/([0-9]+)\/random-null-baseline$/,
        )!
        const fixture = makeRandomBaseline()
        return Promise.resolve(
          apiResponse(
            makeRandomBaseline({
              cell: {
                ...fixture.cell,
                strategy_id: decodeURIComponent(match[1]!),
                strategy_version: decodeURIComponent(match[2]!),
                replicate: Number(match[3]),
              },
            }),
          ),
        )
      }
      if (url.pathname === '/api/v1/historical-prefix-success-windows') {
        return Promise.resolve(apiResponse(page))
      }
      return Promise.resolve(apiResponse(makeRunPage()))
    })
    const wrapper = mount(HistoricalSuccessWindowsPage)
    await flushPromises()

    expect(
      (
        wrapper.get(
          'select[name="random-baseline-window"]',
        ).element as HTMLSelectElement
      ).value,
    ).toBe('LONG')
    expect(
      wrapper
        .get('select[name="random-baseline-window"]')
        .findAll('option')
        .map((option) => option.text()),
    ).toEqual(['FULL_HISTORY', 'LONG', 'MEDIUM', 'SHORT'])

    await selectRun(wrapper)
    await analyze(wrapper)
    expect(wrapper.text()).toContain(
      'Selection and window changes never load a baseline automatically.',
    )
    for (const checkbox of wrapper.findAll('input.matrix-select')) {
      await checkbox.setValue(true)
    }
    expect(fetchMock).toHaveBeenCalledTimes(2)

    await loadRandomBaselines(wrapper)
    const baselineCalls = fetchMock.mock.calls.slice(2)
    expect(baselineCalls).toHaveLength(4)
    expect(
      baselineCalls.map((call) => {
        const url = new URL(String(call[0]), 'http://localhost')
        return {
          strategy: decodeURIComponent(
            url.pathname.match(/\/strategies\/([^/]+)\//)![1]!,
          ),
          query: Object.fromEntries(url.searchParams),
        }
      }),
    ).toEqual(
      strategies.map((strategy) => ({
        strategy: strategy.strategy.strategy_id,
        query: {
          import_identity_sha256: IMPORT_SHA,
          prefix_count: '1',
          criterion: 'M3_PLUS',
          window_kind: 'LONG',
        },
      })),
    )
    expect(wrapper.findAll('.random-baseline-result-card')).toHaveLength(4)
    expect(wrapper.text()).toContain('0.018637545002022338')
    expect(wrapper.text()).toContain(
      'This result does not establish statistical significance, ranking, promotion, rejection, prediction quality, production eligibility, or monetary cost equivalence.',
    )
    wrapper.unmount()
  })

  it('renders closed NOT_READY and partial random-baseline outcomes without fabricating result fields', async () => {
    const wrapper = await mountWithRuns()
    await selectRun(wrapper)
    await analyze(wrapper)
    await selectMatrix(wrapper, 0)
    fetchMock.mockImplementation((input) => {
      const url = String(input)
      if (url.includes('/random-null-baseline')) {
        return Promise.resolve(apiResponse(makeNotReadyRandomBaseline()))
      }
      return successfulFetch(input)
    })

    await loadRandomBaselines(wrapper)
    expect(wrapper.get('.random-baseline-not-ready').text()).toContain(
      'WINDOW_INCOMPLETE',
    )
    expect(wrapper.get('.random-baseline-not-ready').text()).toContain(
      'No observed, expected, or upper-tail result is exposed.',
    )
    expect(wrapper.find('.random-baseline-exact-grid').exists()).toBe(false)

    await selectMatrix(wrapper, 1)
    fetchMock.mockImplementation((input) => {
      const url = String(input)
      if (url.includes('/zero-observation/')) {
        return Promise.resolve(
          apiResponse(
            { error_code: 'HISTORICAL_PREFIX_SUCCESS_WINDOWS_UNAVAILABLE' },
            503,
          ),
        )
      }
      if (url.includes('/random-null-baseline')) {
        return Promise.resolve(apiResponse(makeRandomBaseline()))
      }
      return successfulFetch(input)
    })
    await loadRandomBaselines(wrapper)
    expect(wrapper.text()).toContain(
      'Some random-baseline requests are unavailable; successful results remain visible.',
    )
    expect(wrapper.findAll('.random-baseline-result-card')).toHaveLength(2)
    expect(wrapper.text()).toContain('0.018637545002022338')
    expect(wrapper.find('.random-baseline-item-error').exists()).toBe(true)
    wrapper.unmount()
  })

  it('aborts and ignores stale random baselines on window changes and unmount', async () => {
    const wrapper = await mountWithRuns()
    await selectRun(wrapper)
    await analyze(wrapper)
    await selectMatrix(wrapper)
    const older = deferred<Response>()
    const newer = deferred<Response>()
    fetchMock.mockReset()
    fetchMock
      .mockReturnValueOnce(older.promise)
      .mockReturnValueOnce(newer.promise)

    await wrapper.get('button.random-baseline-load').trigger('click')
    const olderSignal = fetchMock.mock.calls[0]?.[1]?.signal as AbortSignal
    await wrapper
      .get('select[name="random-baseline-window"]')
      .setValue('MEDIUM')
    expect(olderSignal.aborted).toBe(true)
    expect(fetchMock).toHaveBeenCalledTimes(1)

    await wrapper.get('button.random-baseline-load').trigger('click')
    const newerSignal = fetchMock.mock.calls[1]?.[1]?.signal as AbortSignal
    const medium = makeRandomBaseline()
    newer.resolve(
      apiResponse(
        makeRandomBaseline({
          cell: { ...medium.cell, window_kind: 'MEDIUM' },
        }),
      ),
    )
    await flushPromises()
    older.resolve(apiResponse(makeRandomBaseline()))
    await flushPromises()
    expect(wrapper.get('.random-baseline-result-card').text()).toContain(
      'MEDIUM',
    )
    expect(wrapper.get('.random-baseline-result-card').text()).not.toContain(
      'LONG',
    )

    fetchMock.mockReturnValueOnce(new Promise<Response>(() => undefined))
    await wrapper.get('button.random-baseline-load').trigger('click')
    const unmountSignal = fetchMock.mock.calls[2]?.[1]?.signal as AbortSignal
    wrapper.unmount()
    expect(newerSignal.aborted).toBe(true)
    expect(unmountSignal.aborted).toBe(true)
  })

  it('never requests feature cohorts until the separate explicit action', async () => {
    const wrapper = await mountWithRuns()
    expect(fetchMock).toHaveBeenCalledTimes(1)
    await selectRun(wrapper)
    expect(fetchMock).toHaveBeenCalledTimes(1)
    await wrapper.get('select[name="prefix-count"]').setValue('2')
    await wrapper.get('select[name="criterion"]').setValue('M4_PLUS')
    expect(fetchMock).toHaveBeenCalledTimes(1)
    await wrapper.get('select[name="prefix-count"]').setValue('1')
    await wrapper.get('select[name="criterion"]').setValue('M3_PLUS')
    await analyze(wrapper)
    expect(fetchMock).toHaveBeenCalledTimes(2)
    await selectMatrix(wrapper)
    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('1 exact identity selected in manual order.')

    await evaluateFeatureCohorts(wrapper)

    expect(fetchMock).toHaveBeenCalledTimes(3)
    const url = new URL(String(fetchMock.mock.calls[2]?.[0]), 'http://localhost')
    expect(url.pathname).toContain('/feature-cohorts')
    expect(Object.fromEntries(url.searchParams)).toEqual({
      import_identity_sha256: IMPORT_SHA,
      prefix_count: '1',
      criterion: 'M3_PLUS',
    })
    wrapper.unmount()
  })

  it('issues exactly N feature-cohort requests in selection order and renders all canonical rows', async () => {
    const first = makeResult()
    const second = makeZeroObservationResult()
    fetchMock.mockImplementation((input) => {
      const url = String(input)
      if (url.includes('/historical-results/runs')) {
        return Promise.resolve(apiResponse(makeRunPage()))
      }
      if (url.includes('/feature-cohorts')) {
        return Promise.resolve(
          apiResponse(
            url.includes('zero-observation')
              ? makeZeroObservationFeatureCohorts()
              : makeFeatureCohortsForResult(first),
          ),
        )
      }
      return Promise.resolve(
        apiResponse(makeWindowPage({ items: [first, second] })),
      )
    })
    const wrapper = mount(HistoricalSuccessWindowsPage)
    await flushPromises()
    await selectRun(wrapper)
    await analyze(wrapper)
    await selectMatrix(wrapper, 1)
    await selectMatrix(wrapper, 0)
    fetchMock.mockClear()

    await evaluateFeatureCohorts(wrapper)

    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(String(fetchMock.mock.calls[0]?.[0])).toContain(
      '/zero-observation/v2/2/feature-cohorts?',
    )
    expect(String(fetchMock.mock.calls[1]?.[0])).toContain(
      '/alias%20strategy%2Fone/v1%20beta/1/feature-cohorts?',
    )
    const cards = wrapper.findAll('.feature-cohort-result-card')
    expect(cards).toHaveLength(2)
    expect(cards[0]!.findAll('tbody tr')).toHaveLength(64)
    expect(cards[1]!.findAll('tbody tr')).toHaveLength(64)
    expect(cards[0]!.text()).toContain('Unavailable (0 / 0)')
    expect(cards[1]!.text()).toContain('Baseline exact rate2 / 5')
    expect(cards[1]!.text()).toContain('3 / 5')
    expect(cards[1]!.text()).toContain('-2 / 5')
    expect(cards[1]!.text()).toContain('-1 / 15')
    expect(cards[1]!.text()).toContain('HIGHER')
    expect(cards[1]!.text()).toContain('LOWER')
    expect(cards[1]!.text()).not.toMatch(
      /best feature|winning pattern|recommendation|promotion|rejection/i,
    )
    wrapper.unmount()
  })

  it('keeps successful feature cohorts on partial failure and retries all selections', async () => {
    const wrapper = await mountWithRuns()
    await selectRun(wrapper)
    await analyze(wrapper)
    await selectMatrix(wrapper, 0)
    await selectMatrix(wrapper, 1)
    fetchMock.mockReset()
    fetchMock.mockImplementation((input) =>
      String(input).includes('zero-observation')
        ? Promise.resolve(
            apiResponse(
              {
                error_code: 'HISTORICAL_PREFIX_SUCCESS_STRATEGY_NOT_FOUND',
                message: '/secret/path',
              },
              404,
            ),
          )
        : Promise.resolve(apiResponse(makeFeatureCohorts())),
    )

    await evaluateFeatureCohorts(wrapper)

    expect(wrapper.text()).toContain('Some exact feature-cohort requests are unavailable')
    expect(wrapper.findAll('.feature-cohort-result-card')).toHaveLength(2)
    expect(wrapper.text()).toContain('no longer exists')
    expect(wrapper.text()).not.toContain('/secret/path')

    fetchMock.mockReset()
    fetchMock.mockImplementation((input) =>
      Promise.resolve(
        apiResponse(
          String(input).includes('zero-observation')
            ? makeZeroObservationFeatureCohorts()
            : makeFeatureCohorts(),
        ),
      ),
    )
    await wrapper.get('button.feature-cohort-retry').trigger('click')
    await flushPromises()
    expect(wrapper.findAll('.feature-cohort-result-card')).toHaveLength(2)
    expect(wrapper.text()).not.toContain('Some exact feature-cohort requests are unavailable')
    wrapper.unmount()
  })

  it('aborts stale feature cohorts on reevaluation, control/run change, and unmount', async () => {
    const wrapper = await mountWithRuns()
    await selectRun(wrapper)
    await analyze(wrapper)
    await selectMatrix(wrapper)
    const older = deferred<Response>()
    const newer = deferred<Response>()
    fetchMock.mockReset()
    fetchMock.mockReturnValueOnce(older.promise).mockReturnValueOnce(newer.promise)

    await wrapper.get('button.feature-cohort-evaluate').trigger('click')
    const oldSignal = fetchMock.mock.calls[0]?.[1]?.signal as AbortSignal
    await wrapper.get('button.feature-cohort-evaluate').trigger('click')
    expect(oldSignal.aborted).toBe(true)
    newer.resolve(apiResponse(makeFeatureCohorts()))
    await flushPromises()
    older.resolve(apiResponse(makeFeatureCohorts({
      strategy: { ...makeFeatureCohorts().strategy, strategy_id: 'stale' },
    })))
    await flushPromises()
    expect(wrapper.findAll('.feature-cohort-result-card')).toHaveLength(1)
    expect(wrapper.text()).not.toContain('stale')

    const controlPending = deferred<Response>()
    fetchMock.mockReset()
    fetchMock.mockReturnValueOnce(controlPending.promise)
    await wrapper.get('button.feature-cohort-evaluate').trigger('click')
    const controlSignal = fetchMock.mock.calls[0]?.[1]?.signal as AbortSignal
    await wrapper.get('select[name="prefix-count"]').setValue('2')
    expect(controlSignal.aborted).toBe(true)
    expect(wrapper.findAll('.feature-cohort-result-card')).toHaveLength(0)
    controlPending.resolve(apiResponse(makeFeatureCohorts()))
    await flushPromises()
    expect(wrapper.findAll('.feature-cohort-result-card')).toHaveLength(0)

    await wrapper.get('select[name="prefix-count"]').setValue('1')
    const runPending = deferred<Response>()
    fetchMock.mockReset()
    fetchMock.mockReturnValueOnce(runPending.promise)
    await wrapper.get('button.feature-cohort-evaluate').trigger('click')
    const runSignal = fetchMock.mock.calls[0]?.[1]?.signal as AbortSignal
    await wrapper.get('select[name="historical-run"]').setValue('')
    expect(runSignal.aborted).toBe(true)
    runPending.resolve(apiResponse(makeFeatureCohorts()))
    await flushPromises()
    expect(wrapper.findAll('.feature-cohort-result-card')).toHaveLength(0)

    fetchMock.mockImplementation(successfulFetch)
    await wrapper.get('select[name="historical-run"]').setValue(IMPORT_SHA)
    await analyze(wrapper)
    await selectMatrix(wrapper, 0)
    await selectMatrix(wrapper, 1)
    fetchMock.mockReset()
    fetchMock.mockImplementation(() => new Promise<Response>(() => undefined))
    await wrapper.get('button.feature-cohort-evaluate').trigger('click')
    const unmountSignals = fetchMock.mock.calls.map(
      (call) => call[1]?.signal as AbortSignal,
    )
    expect(unmountSignals).toHaveLength(2)
    wrapper.unmount()
    expect(unmountSignals.every((signal) => signal.aborted)).toBe(true)
  })

  it('never requests inferential diagnostics until its separate explicit action', async () => {
    const wrapper = await mountWithRuns()
    await selectRun(wrapper)
    await analyze(wrapper)
    await selectMatrix(wrapper)
    await evaluateFeatureCohorts(wrapper)
    expect(
      fetchMock.mock.calls.some((call) =>
        String(call[0]).includes('/feature-cohorts/diagnostics'),
      ),
    ).toBe(false)

    await evaluateFeatureCohortDiagnostics(wrapper)

    const diagnosticsCalls = fetchMock.mock.calls.filter((call) =>
      String(call[0]).includes('/feature-cohorts/diagnostics'),
    )
    expect(diagnosticsCalls).toHaveLength(1)
    const url = new URL(String(diagnosticsCalls[0]![0]), 'http://localhost')
    expect(Object.fromEntries(url.searchParams)).toEqual({
      import_identity_sha256: IMPORT_SHA,
      prefix_count: '1',
      criterion: 'M3_PLUS',
    })
    wrapper.unmount()
  })

  it('issues exactly N diagnostics requests in selection order and renders all canonical rows', async () => {
    const first = makeResult()
    const second = makeZeroObservationResult()
    fetchMock.mockImplementation((input) => {
      const url = String(input)
      if (url.includes('/historical-results/runs')) {
        return Promise.resolve(apiResponse(makeRunPage()))
      }
      if (url.includes('/feature-cohorts/diagnostics')) {
        return Promise.resolve(
          apiResponse(
            url.includes('zero-observation')
              ? makeZeroObservationFeatureCohortDiagnostics()
              : makeFeatureCohortDiagnosticsForResult(first),
          ),
        )
      }
      return Promise.resolve(
        apiResponse(makeWindowPage({ items: [first, second] })),
      )
    })
    const wrapper = mount(HistoricalSuccessWindowsPage)
    await flushPromises()
    await selectRun(wrapper)
    await analyze(wrapper)
    await selectMatrix(wrapper, 1)
    await selectMatrix(wrapper, 0)
    fetchMock.mockClear()

    await evaluateFeatureCohortDiagnostics(wrapper)

    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(String(fetchMock.mock.calls[0]?.[0])).toContain(
      '/zero-observation/v2/2/feature-cohorts/diagnostics?',
    )
    expect(String(fetchMock.mock.calls[1]?.[0])).toContain(
      '/alias%20strategy%2Fone/v1%20beta/1/feature-cohorts/diagnostics?',
    )
    const cards = wrapper.findAll('.feature-cohort-diagnostics-result-card')
    expect(cards).toHaveLength(2)
    expect(cards[0]!.findAll('tbody tr')).toHaveLength(64)
    expect(cards[1]!.findAll('tbody tr')).toHaveLength(64)
    expect(cards[1]!.text()).toContain(
      'FISHER_EXACT_TWO_SIDED_PROBABILITY_ORDERING',
    )
    expect(cards[1]!.text()).toContain('BENJAMINI_YEKUTIELI')
    expect(cards[1]!.text()).toContain('TESTED')
    expect(cards[1]!.text()).toContain('1 / 1')
    expect(cards[1]!.text()).not.toMatch(
      /significant|winner|best pattern|promotion|prediction/i,
    )
    wrapper.unmount()
  })

  it('aborts stale diagnostics on reevaluation, control/run change, and unmount', async () => {
    const wrapper = await mountWithRuns()
    await selectRun(wrapper)
    await analyze(wrapper)
    await selectMatrix(wrapper)
    const older = deferred<Response>()
    const newer = deferred<Response>()
    fetchMock.mockReset()
    fetchMock.mockReturnValueOnce(older.promise).mockReturnValueOnce(newer.promise)

    await wrapper.get('button.feature-cohort-diagnostics-evaluate').trigger('click')
    const oldSignal = fetchMock.mock.calls[0]?.[1]?.signal as AbortSignal
    await wrapper.get('button.feature-cohort-diagnostics-evaluate').trigger('click')
    expect(oldSignal.aborted).toBe(true)
    newer.resolve(apiResponse(makeFeatureCohortDiagnostics()))
    await flushPromises()
    older.resolve(
      apiResponse(
        makeFeatureCohortDiagnostics({
          strategy: {
            ...makeFeatureCohortDiagnostics().strategy,
            strategy_id: 'stale',
          },
        }),
      ),
    )
    await flushPromises()
    expect(wrapper.findAll('.feature-cohort-diagnostics-result-card')).toHaveLength(1)
    expect(wrapper.text()).not.toContain('stale')

    const controlPending = deferred<Response>()
    fetchMock.mockReset()
    fetchMock.mockReturnValueOnce(controlPending.promise)
    await wrapper.get('button.feature-cohort-diagnostics-evaluate').trigger('click')
    const controlSignal = fetchMock.mock.calls[0]?.[1]?.signal as AbortSignal
    await wrapper.get('select[name="criterion"]').setValue('M4_PLUS')
    expect(controlSignal.aborted).toBe(true)
    expect(wrapper.findAll('.feature-cohort-diagnostics-result-card')).toHaveLength(0)

    await wrapper.get('select[name="criterion"]').setValue('M3_PLUS')
    const runPending = deferred<Response>()
    fetchMock.mockReset()
    fetchMock.mockReturnValueOnce(runPending.promise)
    await wrapper.get('button.feature-cohort-diagnostics-evaluate').trigger('click')
    const runSignal = fetchMock.mock.calls[0]?.[1]?.signal as AbortSignal
    await wrapper.get('select[name="historical-run"]').setValue('')
    expect(runSignal.aborted).toBe(true)

    fetchMock.mockImplementation(successfulFetch)
    await wrapper.get('select[name="historical-run"]').setValue(IMPORT_SHA)
    await analyze(wrapper)
    await selectMatrix(wrapper)
    fetchMock.mockReset()
    fetchMock.mockImplementation(() => new Promise<Response>(() => undefined))
    await wrapper.get('button.feature-cohort-diagnostics-evaluate').trigger('click')
    const unmountSignal = fetchMock.mock.calls[0]?.[1]?.signal as AbortSignal
    wrapper.unmount()
    expect(unmountSignal.aborted).toBe(true)
  })

  it('never requests the temporal holdout before its separate explicit action', async () => {
    const wrapper = await mountWithRuns()
    await selectRun(wrapper)
    await analyze(wrapper)
    await selectMatrix(wrapper)
    await wrapper.get('select[name="prefix-count"]').setValue('2')
    await wrapper.get('select[name="criterion"]').setValue('M4_PLUS')
    await wrapper.get('select[name="prefix-count"]').setValue('1')
    await wrapper.get('select[name="criterion"]').setValue('M3_PLUS')
    await compareMatrices(wrapper)
    await evaluateFeatureCohorts(wrapper)
    await evaluateFeatureCohortDiagnostics(wrapper)

    expect(
      fetchMock.mock.calls.some((call) =>
        String(call[0]).includes('/feature-cohorts/temporal-holdout'),
      ),
    ).toBe(false)

    await evaluateTemporalHoldout(wrapper)

    const calls = fetchMock.mock.calls.filter((call) =>
      String(call[0]).includes('/feature-cohorts/temporal-holdout'),
    )
    expect(calls).toHaveLength(1)
    const url = new URL(String(calls[0]![0]), 'http://localhost')
    expect(Object.fromEntries(url.searchParams)).toEqual({
      import_identity_sha256: IMPORT_SHA,
      prefix_count: '1',
      criterion: 'M3_PLUS',
    })
    wrapper.unmount()
  })

  it('issues exactly N temporal holdout requests in selection order and renders all 64 neutral rows', async () => {
    const first = makeResult()
    const second = makeZeroObservationResult()
    const forResult = (result: ReturnType<typeof makeResult>) => {
      const holdout = makeTemporalHoldout()
      holdout.strategy = result.strategy
      holdout.discovery!.strategy = result.strategy
      holdout.confirmation!.strategy = result.strategy
      return holdout
    }
    fetchMock.mockImplementation((input) => {
      const url = String(input)
      if (url.includes('/historical-results/runs')) {
        return Promise.resolve(apiResponse(makeRunPage()))
      }
      if (url.includes('/feature-cohorts/temporal-holdout')) {
        return Promise.resolve(
          apiResponse(url.includes('zero-observation') ? forResult(second) : forResult(first)),
        )
      }
      return Promise.resolve(apiResponse(makeWindowPage({ items: [first, second] })))
    })
    const wrapper = mount(HistoricalSuccessWindowsPage)
    await flushPromises()
    await selectRun(wrapper)
    await analyze(wrapper)
    await selectMatrix(wrapper, 1)
    await selectMatrix(wrapper, 0)
    fetchMock.mockClear()

    await evaluateTemporalHoldout(wrapper)

    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(String(fetchMock.mock.calls[0]?.[0])).toContain(
      '/zero-observation/v2/2/feature-cohorts/temporal-holdout?',
    )
    expect(String(fetchMock.mock.calls[1]?.[0])).toContain(
      '/alias%20strategy%2Fone/v1%20beta/1/feature-cohorts/temporal-holdout?',
    )
    const cards = wrapper.findAll('.temporal-holdout-result-card')
    expect(cards).toHaveLength(2)
    expect(cards[0]!.findAll('tbody tr')).toHaveLength(64)
    expect(cards[1]!.findAll('tbody tr')).toHaveLength(64)
    expect(cards[1]!.text()).toContain('FIXED_LAST_750_DISCOVERY_LAST_300_CONFIRMATION')
    expect(cards[1]!.text()).toContain('SAME_HIGHER')
    expect(cards[1]!.text()).toContain('SAME_LOWER')
    expect(cards[1]!.text()).toContain('UNAVAILABLE')
    expect(cards[1]!.text()).not.toMatch(
      /replicated|confirmed|failed replication|significant|winner|promotion|rejection|prediction/i,
    )
    wrapper.unmount()
  })

  it('renders not-ready temporal holdout without fabricated phase rows', async () => {
    const wrapper = await mountWithRuns()
    await selectRun(wrapper)
    await analyze(wrapper)
    await selectMatrix(wrapper)
    fetchMock.mockReset()
    fetchMock.mockResolvedValue(apiResponse(makeNotReadyTemporalHoldout()))

    await evaluateTemporalHoldout(wrapper)

    expect(wrapper.text()).toContain('NOT_READY_INSUFFICIENT_HISTORY')
    expect(wrapper.text()).toContain('Neither phase was shortened')
    expect(wrapper.findAll('.temporal-holdout-comparison')).toHaveLength(0)
    wrapper.unmount()
  })

  it('keeps successful temporal holdouts on partial failure and retries all selections', async () => {
    const wrapper = await mountWithRuns()
    await selectRun(wrapper)
    await analyze(wrapper)
    await selectMatrix(wrapper, 0)
    await selectMatrix(wrapper, 1)
    fetchMock.mockReset()
    fetchMock.mockImplementation((input) =>
      String(input).includes('zero-observation')
        ? Promise.resolve(
            apiResponse(
              {
                error_code: 'HISTORICAL_PREFIX_SUCCESS_STRATEGY_NOT_FOUND',
                message: '/secret/path',
              },
              404,
            ),
          )
        : Promise.resolve(apiResponse(makeTemporalHoldout())),
    )

    await evaluateTemporalHoldout(wrapper)

    expect(wrapper.text()).toContain('Some temporal holdout requests are unavailable')
    expect(wrapper.findAll('.temporal-holdout-result-card')).toHaveLength(2)
    expect(wrapper.text()).not.toContain('/secret/path')

    fetchMock.mockReset()
    fetchMock.mockResolvedValue(apiResponse(makeTemporalHoldout()))
    await wrapper.get('button.temporal-holdout-retry').trigger('click')
    await flushPromises()
    expect(fetchMock).toHaveBeenCalledTimes(2)
    wrapper.unmount()
  })

  it('aborts stale temporal holdouts on reevaluation, control/run change, and unmount', async () => {
    const wrapper = await mountWithRuns()
    await selectRun(wrapper)
    await analyze(wrapper)
    await selectMatrix(wrapper)
    const older = deferred<Response>()
    const newer = deferred<Response>()
    fetchMock.mockReset()
    fetchMock.mockReturnValueOnce(older.promise).mockReturnValueOnce(newer.promise)

    await wrapper.get('button.temporal-holdout-action').trigger('click')
    const oldSignal = fetchMock.mock.calls[0]?.[1]?.signal as AbortSignal
    await wrapper.get('button.temporal-holdout-action').trigger('click')
    expect(oldSignal.aborted).toBe(true)
    newer.resolve(apiResponse(makeTemporalHoldout()))
    await flushPromises()
    older.resolve(
      apiResponse(
        makeTemporalHoldout({
          strategy: { ...makeTemporalHoldout().strategy, strategy_id: 'stale' },
        }),
      ),
    )
    await flushPromises()
    expect(wrapper.findAll('.temporal-holdout-result-card')).toHaveLength(1)
    expect(wrapper.text()).not.toContain('stale')

    const controlPending = deferred<Response>()
    fetchMock.mockReset()
    fetchMock.mockReturnValueOnce(controlPending.promise)
    await wrapper.get('button.temporal-holdout-action').trigger('click')
    const controlSignal = fetchMock.mock.calls[0]?.[1]?.signal as AbortSignal
    await wrapper.get('select[name="criterion"]').setValue('M4_PLUS')
    expect(controlSignal.aborted).toBe(true)
    expect(wrapper.findAll('.temporal-holdout-result-card')).toHaveLength(0)

    await wrapper.get('select[name="criterion"]').setValue('M3_PLUS')
    const runPending = deferred<Response>()
    fetchMock.mockReset()
    fetchMock.mockReturnValueOnce(runPending.promise)
    await wrapper.get('button.temporal-holdout-action').trigger('click')
    const runSignal = fetchMock.mock.calls[0]?.[1]?.signal as AbortSignal
    await wrapper.get('select[name="historical-run"]').setValue('')
    expect(runSignal.aborted).toBe(true)

    fetchMock.mockImplementation(successfulFetch)
    await wrapper.get('select[name="historical-run"]').setValue(IMPORT_SHA)
    await analyze(wrapper)
    await selectMatrix(wrapper)
    fetchMock.mockReset()
    fetchMock.mockImplementation(() => new Promise<Response>(() => undefined))
    await wrapper.get('button.temporal-holdout-action').trigger('click')
    const unmountSignal = fetchMock.mock.calls[0]?.[1]?.signal as AbortSignal
    wrapper.unmount()
    expect(unmountSignal.aborted).toBe(true)
  })

  it('never requests the recent-50 audit before its separate explicit action', async () => {
    const wrapper = await mountWithRuns()
    await selectRun(wrapper)
    await analyze(wrapper)
    await selectMatrix(wrapper)
    await compareMatrices(wrapper)
    await evaluateFeatureCohorts(wrapper)
    await evaluateFeatureCohortDiagnostics(wrapper)
    await evaluateTemporalHoldout(wrapper)

    expect(
      fetchMock.mock.calls.some((call) =>
        String(call[0]).includes('/feature-cohorts/recent-50-stability-audit'),
      ),
    ).toBe(false)

    await evaluateRecent50StabilityAudit(wrapper)

    const calls = fetchMock.mock.calls.filter((call) =>
      String(call[0]).includes('/feature-cohorts/recent-50-stability-audit'),
    )
    expect(calls).toHaveLength(1)
    const url = new URL(String(calls[0]![0]), 'http://localhost')
    expect(Object.fromEntries(url.searchParams)).toEqual({
      import_identity_sha256: IMPORT_SHA,
      prefix_count: '1',
      criterion: 'M3_PLUS',
    })
    wrapper.unmount()
  })

  it('issues exactly N recent-50 requests in selection order and renders 64 canonical rows', async () => {
    const first = makeResult()
    const second = makeZeroObservationResult()
    const forResult = (result: ReturnType<typeof makeResult>) => {
      const audit = makeRecent50StabilityAudit()
      audit.strategy = result.strategy
      audit.reference!.strategy = result.strategy
      audit.recent!.strategy = result.strategy
      return audit
    }
    fetchMock.mockImplementation((input) => {
      const url = String(input)
      if (url.includes('/historical-results/runs')) {
        return Promise.resolve(apiResponse(makeRunPage()))
      }
      if (url.includes('/feature-cohorts/recent-50-stability-audit')) {
        return Promise.resolve(
          apiResponse(url.includes('zero-observation') ? forResult(second) : forResult(first)),
        )
      }
      return Promise.resolve(apiResponse(makeWindowPage({ items: [first, second] })))
    })
    const wrapper = mount(HistoricalSuccessWindowsPage)
    await flushPromises()
    await selectRun(wrapper)
    await analyze(wrapper)
    await selectMatrix(wrapper, 1)
    await selectMatrix(wrapper, 0)
    fetchMock.mockClear()

    await evaluateRecent50StabilityAudit(wrapper)

    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(String(fetchMock.mock.calls[0]?.[0])).toContain(
      '/zero-observation/v2/2/feature-cohorts/recent-50-stability-audit?',
    )
    expect(String(fetchMock.mock.calls[1]?.[0])).toContain(
      '/alias%20strategy%2Fone/v1%20beta/1/feature-cohorts/recent-50-stability-audit?',
    )
    const cards = wrapper.findAll('.recent-50-stability-audit-result-card')
    expect(cards).toHaveLength(2)
    expect(cards[0]!.findAll('.recent-50-stability-audit-comparison')).toHaveLength(64)
    expect(cards[1]!.findAll('.recent-50-stability-audit-comparison')).toHaveLength(64)
    expect(cards[1]!.text()).toContain(
      'FIXED_CONFIRMATION_FIRST_250_REFERENCE_LAST_50_RECENT',
    )
    expect(cards[1]!.text()).toContain('Reference')
    expect(cards[1]!.text()).toContain('Recent')
    expect(cards[1]!.text()).toContain('250')
    expect(cards[1]!.text()).toContain('50')
    expect(wrapper.get('.recent-50-descriptive-notice').text()).toContain(
      'Descriptive only',
    )
    expect(
      wrapper.get('.recent-50-stability-audit-panel').text(),
    ).not.toMatch(
      /\bveto\b|\bpass\b|\bfail\b|degraded|promoted|rejected|significant|winner|score|rank|prediction/i,
    )
    wrapper.unmount()
  })

  it('renders not-ready and partial recent-50 outcomes without fabricating rows', async () => {
    const wrapper = await mountWithRuns()
    await selectRun(wrapper)
    await analyze(wrapper)
    await selectMatrix(wrapper, 0)
    await selectMatrix(wrapper, 1)
    fetchMock.mockReset()
    fetchMock.mockImplementation((input) =>
      String(input).includes('zero-observation')
        ? Promise.resolve(
            apiResponse(
              {
                error_code: 'HISTORICAL_PREFIX_SUCCESS_STRATEGY_NOT_FOUND',
                message: '/secret/path',
              },
              404,
            ),
          )
        : Promise.resolve(apiResponse(makeNotReadyRecent50StabilityAudit())),
    )

    await evaluateRecent50StabilityAudit(wrapper)

    expect(wrapper.text()).toContain('Some recent-50 audit requests are unavailable')
    expect(wrapper.text()).toContain('NOT_READY_INSUFFICIENT_HISTORY')
    expect(wrapper.findAll('.recent-50-stability-audit-comparison')).toHaveLength(0)
    expect(wrapper.text()).not.toContain('/secret/path')

    fetchMock.mockReset()
    fetchMock.mockResolvedValue(apiResponse(makeRecent50StabilityAudit()))
    await wrapper.get('button.recent-50-stability-audit-retry').trigger('click')
    await flushPromises()
    expect(fetchMock).toHaveBeenCalledTimes(2)
    wrapper.unmount()
  })

  it('aborts stale recent-50 requests on reevaluation, other research, controls, run change, and unmount', async () => {
    const wrapper = await mountWithRuns()
    await selectRun(wrapper)
    await analyze(wrapper)
    await selectMatrix(wrapper)
    const older = deferred<Response>()
    const newer = deferred<Response>()
    fetchMock.mockReset()
    fetchMock.mockReturnValueOnce(older.promise).mockReturnValueOnce(newer.promise)

    await wrapper.get('button.recent-50-stability-audit-action').trigger('click')
    const oldSignal = fetchMock.mock.calls[0]?.[1]?.signal as AbortSignal
    await wrapper.get('button.recent-50-stability-audit-action').trigger('click')
    expect(oldSignal.aborted).toBe(true)
    newer.resolve(apiResponse(makeRecent50StabilityAudit()))
    await flushPromises()
    older.resolve(
      apiResponse(
        makeRecent50StabilityAudit({
          strategy: {
            ...makeRecent50StabilityAudit().strategy,
            strategy_id: 'stale',
          },
        }),
      ),
    )
    await flushPromises()
    expect(wrapper.findAll('.recent-50-stability-audit-result-card')).toHaveLength(1)
    expect(wrapper.text()).not.toContain('stale')

    const otherResearchPending = deferred<Response>()
    fetchMock.mockReset()
    fetchMock.mockReturnValueOnce(otherResearchPending.promise)
    await wrapper.get('button.recent-50-stability-audit-action').trigger('click')
    const otherResearchSignal = fetchMock.mock.calls[0]?.[1]?.signal as AbortSignal
    fetchMock.mockImplementation(successfulFetch)
    await wrapper.get('button.temporal-holdout-action').trigger('click')
    expect(otherResearchSignal.aborted).toBe(true)

    const controlPending = deferred<Response>()
    fetchMock.mockReset()
    fetchMock.mockReturnValueOnce(controlPending.promise)
    await wrapper.get('button.recent-50-stability-audit-action').trigger('click')
    const controlSignal = fetchMock.mock.calls[0]?.[1]?.signal as AbortSignal
    await wrapper.get('select[name="prefix-count"]').setValue('2')
    expect(controlSignal.aborted).toBe(true)

    await wrapper.get('select[name="prefix-count"]').setValue('1')
    const runPending = deferred<Response>()
    fetchMock.mockReset()
    fetchMock.mockReturnValueOnce(runPending.promise)
    await wrapper.get('button.recent-50-stability-audit-action').trigger('click')
    const runSignal = fetchMock.mock.calls[0]?.[1]?.signal as AbortSignal
    await wrapper.get('select[name="historical-run"]').setValue('')
    expect(runSignal.aborted).toBe(true)

    fetchMock.mockImplementation(successfulFetch)
    await wrapper.get('select[name="historical-run"]').setValue(IMPORT_SHA)
    await analyze(wrapper)
    await selectMatrix(wrapper)
    fetchMock.mockReset()
    fetchMock.mockImplementation(() => new Promise<Response>(() => undefined))
    await wrapper.get('button.recent-50-stability-audit-action').trigger('click')
    const unmountSignal = fetchMock.mock.calls[0]?.[1]?.signal as AbortSignal
    wrapper.unmount()
    expect(unmountSignal.aborted).toBe(true)
  })

  it('keeps both run selections explicit and preserves them across run pagination', async () => {
    const primary = makeRun()
    const comparison = makeRun({
      run_id: 'run-explicit-2',
      import_identity_sha256: RIGHT_IMPORT_SHA,
    })
    const other = makeRun({
      run_id: 'run-explicit-3',
      import_identity_sha256: 'c'.repeat(64),
    })
    fetchMock.mockImplementation((input) => {
      const url = new URL(String(input), 'http://localhost')
      if (url.pathname === '/api/v1/historical-results/runs') {
        return Promise.resolve(
          apiResponse(
            url.searchParams.get('offset') === '10'
              ? makeRunPage({ items: [other], total_count: 11, offset: 10 })
              : makeRunPage({
                  items: [primary, comparison],
                  total_count: 11,
                  limit: 10,
                }),
          ),
        )
      }
      return Promise.resolve(apiResponse(makeWindowPage()))
    })
    const wrapper = mount(HistoricalSuccessWindowsPage)
    await flushPromises()

    expect((wrapper.get('select[name="comparison-run"]').element as HTMLSelectElement).value).toBe('')
    await wrapper.get('select[name="historical-run"]').setValue(IMPORT_SHA)
    await wrapper.get('select[name="comparison-run"]').setValue(RIGHT_IMPORT_SHA)
    expect(fetchMock).toHaveBeenCalledTimes(1)

    await wrapper
      .get('nav[aria-label="Historical run pages"] button:last-child')
      .trigger('click')
    await flushPromises()

    expect((wrapper.get('select[name="historical-run"]').element as HTMLSelectElement).value).toBe(
      IMPORT_SHA,
    )
    expect((wrapper.get('select[name="comparison-run"]').element as HTMLSelectElement).value).toBe(
      RIGHT_IMPORT_SHA,
    )
    expect(wrapper.get('select[name="historical-run"]').findAll('option')).toHaveLength(3)
    expect(wrapper.get('select[name="comparison-run"]').findAll('option')).toHaveLength(3)
    expect(
      fetchMock.mock.calls.some((call) =>
        String(call[0]).includes('/cross-import-concordance'),
      ),
    ).toBe(false)
    wrapper.unmount()
  })

  it('rejects identical runs and requires the separate concordance action', async () => {
    const comparison = makeRun({
      run_id: 'run-explicit-2',
      import_identity_sha256: RIGHT_IMPORT_SHA,
    })
    fetchMock.mockImplementation((input) => {
      const url = String(input)
      if (url.includes('/historical-results/runs')) {
        return Promise.resolve(
          apiResponse(makeRunPage({ items: [makeRun(), comparison], total_count: 2 })),
        )
      }
      if (url.includes('/feature-cohorts/cross-import-concordance')) {
        return Promise.resolve(apiResponse(makeCrossImportConcordance()))
      }
      return Promise.resolve(apiResponse(makeWindowPage()))
    })
    const wrapper = mount(HistoricalSuccessWindowsPage)
    await flushPromises()
    await selectRun(wrapper)
    await wrapper.get('select[name="comparison-run"]').setValue(IMPORT_SHA)

    expect(wrapper.text()).toContain('Choose two distinct imports')
    expect(
      wrapper.get('button.cross-import-concordance-action').attributes('disabled'),
    ).toBeDefined()

    await wrapper.get('select[name="comparison-run"]').setValue(RIGHT_IMPORT_SHA)
    await analyze(wrapper)
    await selectMatrix(wrapper)
    await wrapper.get('select[name="prefix-count"]').setValue('2')
    await wrapper.get('select[name="criterion"]').setValue('M4_PLUS')
    expect(
      fetchMock.mock.calls.some((call) =>
        String(call[0]).includes('/cross-import-concordance'),
      ),
    ).toBe(false)
    await wrapper.get('select[name="prefix-count"]').setValue('1')
    await wrapper.get('select[name="criterion"]').setValue('M3_PLUS')

    await evaluateCrossImportConcordance(wrapper)

    const calls = fetchMock.mock.calls.filter((call) =>
      String(call[0]).includes('/cross-import-concordance'),
    )
    expect(calls).toHaveLength(1)
    const url = new URL(String(calls[0]![0]), 'http://localhost')
    expect(Object.fromEntries(url.searchParams)).toEqual({
      left_import_identity_sha256: IMPORT_SHA,
      right_import_identity_sha256: RIGHT_IMPORT_SHA,
      prefix_count: '1',
      criterion: 'M3_PLUS',
    })
    wrapper.unmount()
  })

  it('issues exactly N ordered concordance requests and renders neutral confirmation rows', async () => {
    const primary = makeRun()
    const comparisonRun = makeRun({
      run_id: 'run-explicit-2',
      import_identity_sha256: RIGHT_IMPORT_SHA,
    })
    const first = makeResult()
    const second = makeZeroObservationResult()
    const forResult = (result: ReturnType<typeof makeResult>) =>
      makeCrossImportConcordance({ strategy: result.strategy })
    fetchMock.mockImplementation((input) => {
      const url = String(input)
      if (url.includes('/historical-results/runs')) {
        return Promise.resolve(
          apiResponse(
            makeRunPage({ items: [primary, comparisonRun], total_count: 2 }),
          ),
        )
      }
      if (url.includes('/feature-cohorts/cross-import-concordance')) {
        return Promise.resolve(
          apiResponse(url.includes('zero-observation') ? forResult(second) : forResult(first)),
        )
      }
      return Promise.resolve(apiResponse(makeWindowPage({ items: [first, second] })))
    })
    const wrapper = mount(HistoricalSuccessWindowsPage)
    await flushPromises()
    await selectRun(wrapper)
    await wrapper.get('select[name="comparison-run"]').setValue(RIGHT_IMPORT_SHA)
    await analyze(wrapper)
    await selectMatrix(wrapper, 1)
    await selectMatrix(wrapper, 0)
    fetchMock.mockClear()

    await evaluateCrossImportConcordance(wrapper)

    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(String(fetchMock.mock.calls[0]?.[0])).toContain(
      '/zero-observation/v2/2/feature-cohorts/cross-import-concordance?',
    )
    expect(String(fetchMock.mock.calls[1]?.[0])).toContain(
      '/alias%20strategy%2Fone/v1%20beta/1/feature-cohorts/cross-import-concordance?',
    )
    const cards = wrapper.findAll('.cross-import-concordance-result-card')
    expect(cards).toHaveLength(2)
    expect(cards[0]!.findAll('tbody tr')).toHaveLength(64)
    expect(cards[1]!.findAll('tbody tr')).toHaveLength(64)
    expect(cards[1]!.text()).toContain('Same dataset SHAYES')
    expect(cards[1]!.text()).toContain('Target overlap300')
    expect(cards[1]!.text()).toContain('SAME_HIGHER')
    expect(cards[1]!.text()).not.toMatch(
      /independent|replicated|confirmed|significant|rank|winner|promotion|rejection|prediction/i,
    )
    wrapper.unmount()
  })

  it('handles partial concordance failure, retries, and renders not-ready without rows', async () => {
    const comparisonRun = makeRun({
      run_id: 'run-explicit-2',
      import_identity_sha256: RIGHT_IMPORT_SHA,
    })
    fetchMock.mockImplementation((input) => {
      const url = String(input)
      if (url.includes('/historical-results/runs')) {
        return Promise.resolve(
          apiResponse(
            makeRunPage({ items: [makeRun(), comparisonRun], total_count: 2 }),
          ),
        )
      }
      return Promise.resolve(apiResponse(makeWindowPage()))
    })
    const active = mount(HistoricalSuccessWindowsPage)
    await flushPromises()
    await selectRun(active)
    await active.get('select[name="comparison-run"]').setValue(RIGHT_IMPORT_SHA)
    await analyze(active)
    await selectMatrix(active, 0)
    await selectMatrix(active, 1)
    fetchMock.mockReset()
    fetchMock
      .mockResolvedValueOnce(apiResponse(makeCrossImportConcordance()))
      .mockResolvedValueOnce(
        apiResponse(
          {
            error_code: 'HISTORICAL_PREFIX_SUCCESS_STRATEGY_NOT_FOUND',
            message: '/secret/path',
          },
          404,
        ),
      )

    await evaluateCrossImportConcordance(active)

    expect(active.text()).toContain('Some concordance requests are unavailable')
    expect(active.findAll('.cross-import-concordance-result-card')).toHaveLength(2)
    expect(active.text()).not.toContain('/secret/path')

    fetchMock.mockReset()
    fetchMock.mockImplementation((input) =>
      Promise.resolve(
        apiResponse(
          makeNotReadyCrossImportConcordance({
            strategy: String(input).includes('zero-observation')
              ? makeZeroObservationResult().strategy
              : makeResult().strategy,
          }),
        ),
      ),
    )
    await active.get('button.cross-import-concordance-retry').trigger('click')
    await flushPromises()
    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(active.text()).toContain('LEFT_NOT_READY')
    expect(active.findAll('.cross-import-concordance-comparison')).toHaveLength(0)
    active.unmount()
  })

  it('preserves explicit ordered census import selections across pagination without requesting', async () => {
    const first = makeRun()
    const second = makeRun({
      run_id: 'run-explicit-2',
      import_identity_sha256: RIGHT_IMPORT_SHA,
    })
    const third = makeRun({
      run_id: 'run-explicit-3',
      import_identity_sha256: THIRD_IMPORT_SHA,
    })
    fetchMock.mockImplementation((input) => {
      const url = new URL(String(input), 'http://localhost')
      if (url.pathname.includes('/historical-results/runs')) {
        return Promise.resolve(
          apiResponse(
            url.searchParams.get('offset') === '10'
              ? makeRunPage({ items: [third], total_count: 11, offset: 10 })
              : makeRunPage({ items: [first, second], total_count: 11 }),
          ),
        )
      }
      return Promise.resolve(apiResponse(makeWindowPage()))
    })
    const wrapper = mount(HistoricalSuccessWindowsPage)
    await flushPromises()

    const firstPageOptions = wrapper.findAll('.census-import-option input')
    await firstPageOptions[1]!.setValue(true)
    await firstPageOptions[0]!.setValue(true)
    expect(
      wrapper
        .findAll('.census-import-selection-order li code')
        .map((item) => item.text()),
    ).toEqual([RIGHT_IMPORT_SHA, IMPORT_SHA])
    expect(
      fetchMock.mock.calls.some((call) =>
        String(call[0]).includes('/multi-import-concordance-census'),
      ),
    ).toBe(false)

    await wrapper
      .get('nav[aria-label="Historical run pages"] button:last-child')
      .trigger('click')
    await flushPromises()

    expect(wrapper.findAll('.census-import-selection-order li')).toHaveLength(2)
    await wrapper.get('.census-import-option input').setValue(true)
    expect(
      wrapper
        .findAll('.census-import-selection-order li code')
        .map((item) => item.text()),
    ).toEqual([RIGHT_IMPORT_SHA, IMPORT_SHA, THIRD_IMPORT_SHA])
    expect(fetchMock).toHaveBeenCalledTimes(2)
    wrapper.unmount()
  })

  it('issues exactly M census requests with the same ordered imports and renders canonical pairs and 64 rows', async () => {
    const runs = [
      makeRun(),
      makeRun({
        run_id: 'run-explicit-2',
        import_identity_sha256: RIGHT_IMPORT_SHA,
      }),
      makeRun({
        run_id: 'run-explicit-3',
        import_identity_sha256: THIRD_IMPORT_SHA,
      }),
    ]
    const first = makeResult()
    const second = makeZeroObservationResult()
    fetchMock.mockImplementation((input) => {
      const url = new URL(String(input), 'http://localhost')
      if (url.pathname.includes('/historical-results/runs')) {
        return Promise.resolve(
          apiResponse(makeRunPage({ items: runs, total_count: 3 })),
        )
      }
      if (url.pathname.includes('/multi-import-concordance-census')) {
        const identities = url.searchParams.getAll(
          'import_identity_sha256',
        )
        const strategy = url.pathname.includes('zero-observation')
          ? second.strategy
          : first.strategy
        return Promise.resolve(
          apiResponse(
            makeMultiImportConcordanceCensus(
              identities.length,
              { strategy },
              identities,
            ),
          ),
        )
      }
      return Promise.resolve(
        apiResponse(makeWindowPage({ items: [first, second] })),
      )
    })
    const wrapper = mount(HistoricalSuccessWindowsPage)
    await flushPromises()
    await selectRun(wrapper)
    await analyze(wrapper)
    const importOptions = wrapper.findAll('.census-import-option input')
    await importOptions[2]!.setValue(true)
    await importOptions[0]!.setValue(true)
    await importOptions[1]!.setValue(true)
    await selectMatrix(wrapper, 1)
    await selectMatrix(wrapper, 0)
    fetchMock.mockClear()

    await evaluateMultiImportCensus(wrapper)

    expect(fetchMock).toHaveBeenCalledTimes(2)
    for (const call of fetchMock.mock.calls) {
      const url = new URL(String(call[0]), 'http://localhost')
      expect(url.searchParams.getAll('import_identity_sha256')).toEqual([
        THIRD_IMPORT_SHA,
        IMPORT_SHA,
        RIGHT_IMPORT_SHA,
      ])
    }
    expect(String(fetchMock.mock.calls[0]?.[0])).toContain(
      '/zero-observation/v2/2/feature-cohorts/multi-import-concordance-census?',
    )
    expect(String(fetchMock.mock.calls[1]?.[0])).toContain(
      '/alias%20strategy%2Fone/v1%20beta/1/feature-cohorts/multi-import-concordance-census?',
    )
    const cards = wrapper.findAll('.multi-import-census-result-card')
    expect(cards).toHaveLength(2)
    expect(cards[0]!.findAll('.multi-import-pair-row')).toHaveLength(3)
    expect(cards[0]!.findAll('.multi-import-census-row')).toHaveLength(64)
    expect(cards[1]!.findAll('.multi-import-census-row')).toHaveLength(64)
    expect(cards[0]!.text()).toContain('NO_AVAILABLE_EFFECT')
    expect(cards[0]!.text()).not.toMatch(
      /rank|winner|promotion|rejection|prediction|combined/i,
    )
    wrapper.unmount()
  })

  it('handles partial census failure and retries in strategy order', async () => {
    const runs = [
      makeRun(),
      makeRun({
        run_id: 'run-explicit-2',
        import_identity_sha256: RIGHT_IMPORT_SHA,
      }),
    ]
    fetchMock.mockImplementation((input) => {
      const url = String(input)
      if (url.includes('/historical-results/runs')) {
        return Promise.resolve(
          apiResponse(makeRunPage({ items: runs, total_count: 2 })),
        )
      }
      return Promise.resolve(
        apiResponse(
          makeWindowPage({
            items: [makeResult(), makeZeroObservationResult()],
          }),
        ),
      )
    })
    const wrapper = mount(HistoricalSuccessWindowsPage)
    await flushPromises()
    await selectRun(wrapper)
    await analyze(wrapper)
    for (const option of wrapper.findAll('.census-import-option input')) {
      await option.setValue(true)
    }
    await selectMatrix(wrapper, 0)
    await selectMatrix(wrapper, 1)
    fetchMock.mockReset()
    fetchMock
      .mockResolvedValueOnce(
        apiResponse(makeMultiImportConcordanceCensus(2)),
      )
      .mockResolvedValueOnce(
        apiResponse(
          {
            error_code: 'HISTORICAL_PREFIX_SUCCESS_STRATEGY_NOT_FOUND',
            message: '/secret/path',
          },
          404,
        ),
      )

    await evaluateMultiImportCensus(wrapper)

    expect(wrapper.text()).toContain('Some census requests are unavailable')
    expect(wrapper.findAll('.multi-import-census-result-card')).toHaveLength(2)
    expect(wrapper.text()).not.toContain('/secret/path')

    fetchMock.mockReset()
    fetchMock.mockImplementation((input) => {
      const strategy = String(input).includes('zero-observation')
        ? makeZeroObservationResult().strategy
        : makeResult().strategy
      return Promise.resolve(
        apiResponse(makeMultiImportConcordanceCensus(2, { strategy })),
      )
    })
    await wrapper.get('button.multi-import-census-retry').trigger('click')
    await flushPromises()
    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(wrapper.findAll('.multi-import-census-row')).toHaveLength(128)
    wrapper.unmount()
  })

  it('aborts stale census requests on reevaluation, import change, controls, and unmount', async () => {
    const runs = [
      makeRun(),
      makeRun({
        run_id: 'run-explicit-2',
        import_identity_sha256: RIGHT_IMPORT_SHA,
      }),
    ]
    fetchMock.mockImplementation((input) => {
      const url = String(input)
      if (url.includes('/historical-results/runs')) {
        return Promise.resolve(
          apiResponse(makeRunPage({ items: runs, total_count: 2 })),
        )
      }
      return Promise.resolve(apiResponse(makeWindowPage()))
    })
    const wrapper = mount(HistoricalSuccessWindowsPage)
    await flushPromises()
    await selectRun(wrapper)
    await analyze(wrapper)
    for (const option of wrapper.findAll('.census-import-option input')) {
      await option.setValue(true)
    }
    await selectMatrix(wrapper)
    const older = deferred<Response>()
    const newer = deferred<Response>()
    fetchMock.mockReset()
    fetchMock.mockReturnValueOnce(older.promise).mockReturnValueOnce(newer.promise)

    await wrapper.get('button.multi-import-census-action').trigger('click')
    const oldSignal = fetchMock.mock.calls[0]?.[1]?.signal as AbortSignal
    await wrapper.get('button.multi-import-census-action').trigger('click')
    expect(oldSignal.aborted).toBe(true)
    newer.resolve(apiResponse(makeMultiImportConcordanceCensus(2)))
    await flushPromises()
    older.resolve(
      apiResponse(
        makeMultiImportConcordanceCensus(2, {
          strategy: {
            ...makeMultiImportConcordanceCensus(2).strategy,
            strategy_id: 'stale',
          },
        }),
      ),
    )
    await flushPromises()
    expect(wrapper.findAll('.multi-import-census-result-card')).toHaveLength(1)
    expect(wrapper.text()).not.toContain('stale')

    const importPending = deferred<Response>()
    fetchMock.mockReset()
    fetchMock.mockReturnValueOnce(importPending.promise)
    await wrapper.get('button.multi-import-census-action').trigger('click')
    const importSignal = fetchMock.mock.calls[0]?.[1]?.signal as AbortSignal
    await wrapper.get('button.census-import-remove').trigger('click')
    expect(importSignal.aborted).toBe(true)

    await wrapper.get('.census-import-option input').setValue(true)
    const controlPending = deferred<Response>()
    fetchMock.mockReset()
    fetchMock.mockReturnValueOnce(controlPending.promise)
    await wrapper.get('button.multi-import-census-action').trigger('click')
    const controlSignal = fetchMock.mock.calls[0]?.[1]?.signal as AbortSignal
    await wrapper.get('select[name="criterion"]').setValue('M4_PLUS')
    expect(controlSignal.aborted).toBe(true)

    await wrapper.get('select[name="criterion"]').setValue('M3_PLUS')
    fetchMock.mockReset()
    fetchMock.mockImplementation(() => new Promise<Response>(() => undefined))
    await wrapper.get('button.multi-import-census-action').trigger('click')
    const unmountSignal = fetchMock.mock.calls[0]?.[1]?.signal as AbortSignal
    wrapper.unmount()
    expect(unmountSignal.aborted).toBe(true)
  })

  it('requires the explicit qualification action and issues independent ordered projection and random-evidence requests', async () => {
    const runs = [
      makeRun(),
      makeRun({
        run_id: 'run-explicit-2',
        import_identity_sha256: RIGHT_IMPORT_SHA,
      }),
    ]
    const first = makeResult()
    const second = makeZeroObservationResult()
    fetchMock.mockImplementation((input) => {
      const url = new URL(String(input), 'http://localhost')
      if (url.pathname.includes('/historical-results/runs')) {
        return Promise.resolve(
          apiResponse(makeRunPage({ items: runs, total_count: 2 })),
        )
      }
      if (url.pathname.includes('/research-qualification')) {
        const strategy = url.pathname.includes('zero-observation')
          ? second.strategy
          : first.strategy
        if (url.pathname.includes('/random-baseline-evidence')) {
          return Promise.resolve(
            apiResponse(
              makeQualificationRandomBaselineEvidence({
                qualification_identity: {
                  strategy_id: strategy.strategy_id,
                  strategy_version: strategy.strategy_version,
                  replicate: strategy.replicate,
                  prefix_count: 1,
                  criterion: 'M3_PLUS',
                },
              }),
            ),
          )
        }
        return Promise.resolve(
          apiResponse(
            makeResearchQualification({
              identity: {
                strategy_id: strategy.strategy_id,
                strategy_version: strategy.strategy_version,
                replicate: strategy.replicate,
                prefix_count: 1,
                criterion: 'M3_PLUS',
              },
            }),
          ),
        )
      }
      if (url.pathname.includes('/multi-import-concordance-census')) {
        return Promise.resolve(apiResponse(makeMultiImportConcordanceCensus(2)))
      }
      return Promise.resolve(
        apiResponse(makeWindowPage({ items: [first, second] })),
      )
    })
    const wrapper = mount(HistoricalSuccessWindowsPage)
    await flushPromises()
    await selectRun(wrapper)
    await analyze(wrapper)
    const importOptions = wrapper.findAll('.census-import-option input')
    await importOptions[0]!.setValue(true)
    await importOptions[1]!.setValue(true)
    await selectMatrix(wrapper, 1)
    await selectMatrix(wrapper, 0)

    expect(
      fetchMock.mock.calls.some((call) =>
        String(call[0]).includes('/research-qualification'),
      ),
    ).toBe(false)
    await evaluateMultiImportCensus(wrapper)
    expect(
      fetchMock.mock.calls.some((call) =>
        String(call[0]).includes('/research-qualification'),
      ),
    ).toBe(false)
    fetchMock.mockClear()

    await evaluateResearchQualification(wrapper)

    expect(fetchMock).toHaveBeenCalledTimes(4)
    for (const call of fetchMock.mock.calls) {
      const url = new URL(String(call[0]), 'http://localhost')
      expect(url.searchParams.getAll('import_identity_sha256')).toEqual([
        IMPORT_SHA,
        RIGHT_IMPORT_SHA,
      ])
      expect(Object.fromEntries(url.searchParams)).toMatchObject({
        prefix_count: '1',
        criterion: 'M3_PLUS',
      })
    }
    const aggregateCalls = fetchMock.mock.calls.filter((call) =>
      String(call[0]).includes('/random-baseline-evidence'),
    )
    const qualificationCalls = fetchMock.mock.calls.filter(
      (call) =>
        String(call[0]).includes('/research-qualification') &&
        !String(call[0]).includes('/random-baseline-evidence'),
    )
    expect(aggregateCalls).toHaveLength(2)
    expect(qualificationCalls).toHaveLength(2)
    expect(String(qualificationCalls[0]?.[0])).toContain(
      '/zero-observation/v2/2/research-qualification?',
    )
    expect(String(qualificationCalls[1]?.[0])).toContain(
      '/alias%20strategy%2Fone/v1%20beta/1/research-qualification?',
    )
    const cards = wrapper.findAll('.research-qualification-result-card')
    expect(cards).toHaveLength(2)
    expect(cards[0]!.findAll('.research-qualification-import-row')).toHaveLength(2)
    expect(cards[0]!.findAll('.research-qualification-pair-row')).toHaveLength(1)
    expect(wrapper.text()).toContain(
      'Research qualification only. This result does not rank, promote, reject, predict, or establish production eligibility.',
    )
    expect(cards[0]!.text()).toContain(
      'Exact official-six-number IID random-benchmark cells are available as descriptive evidence when READY',
    )
    expect(cards.map((card) => card.find('h3').text())).toEqual([
      'zero-observation',
      'alias strategy/one',
    ])
    const randomCards = wrapper.findAll(
      '.qualification-random-baseline-result-card',
    )
    expect(randomCards).toHaveLength(2)
    expect(
      randomCards.map((card) =>
        card.findAll('.qualification-random-baseline-cell').length,
      ),
    ).toEqual([8, 8])
    expect(wrapper.text()).toContain(
      'Each READY upper_tail_probability is a raw, unadjusted exact descriptive value.',
    )
    expect(randomCards[0]!.text()).toContain('REFERENCE_ONLY')
    expect(randomCards[0]!.text()).toContain(
      'AUDIT_ONLY_NON_BLOCKING',
    )
    expect(randomCards[0]!.text()).toContain(
      'Descriptive official-six-number IID random benchmark only.',
    )
    wrapper.unmount()
  })

  it('keeps partial qualification results visible and retries in strategy order', async () => {
    const runs = [
      makeRun(),
      makeRun({
        run_id: 'run-explicit-2',
        import_identity_sha256: RIGHT_IMPORT_SHA,
      }),
    ]
    const first = makeResult()
    const second = makeZeroObservationResult()
    fetchMock.mockImplementation((input) => {
      const url = String(input)
      if (url.includes('/historical-results/runs')) {
        return Promise.resolve(
          apiResponse(makeRunPage({ items: runs, total_count: 2 })),
        )
      }
      return Promise.resolve(
        apiResponse(makeWindowPage({ items: [first, second] })),
      )
    })
    const wrapper = mount(HistoricalSuccessWindowsPage)
    await flushPromises()
    await selectRun(wrapper)
    await analyze(wrapper)
    for (const option of wrapper.findAll('.census-import-option input')) {
      await option.setValue(true)
    }
    await selectMatrix(wrapper, 0)
    await selectMatrix(wrapper, 1)
    fetchMock.mockReset()
    let qualificationCalls = 0
    fetchMock.mockImplementation((input) => {
      const url = String(input)
      const strategy = url.includes('zero-observation')
        ? second.strategy
        : first.strategy
      if (url.includes('/random-baseline-evidence')) {
        return Promise.resolve(
          apiResponse(
            makeQualificationRandomBaselineEvidence({
              qualification_identity: {
                strategy_id: strategy.strategy_id,
                strategy_version: strategy.strategy_version,
                replicate: strategy.replicate,
                prefix_count: 1,
                criterion: 'M3_PLUS',
              },
            }),
          ),
        )
      }
      qualificationCalls += 1
      return Promise.resolve(
        qualificationCalls === 1
          ? apiResponse(makeResearchQualification())
          : apiResponse(
              {
                error_code: 'HISTORICAL_PREFIX_SUCCESS_STRATEGY_NOT_FOUND',
                message: '/secret/path',
              },
              404,
            ),
      )
    })

    await evaluateResearchQualification(wrapper)

    expect(wrapper.text()).toContain(
      'Some qualification requests are unavailable',
    )
    expect(wrapper.findAll('.research-qualification-result-card')).toHaveLength(2)
    expect(
      wrapper.findAll('.qualification-random-baseline-result-card'),
    ).toHaveLength(2)
    expect(wrapper.text()).not.toContain('/secret/path')

    fetchMock.mockReset()
    fetchMock.mockImplementation((input) => {
      const strategy = String(input).includes('zero-observation')
        ? second.strategy
        : first.strategy
      if (String(input).includes('/random-baseline-evidence')) {
        return Promise.resolve(
          apiResponse(
            makeQualificationRandomBaselineEvidence({
              qualification_identity: {
                strategy_id: strategy.strategy_id,
                strategy_version: strategy.strategy_version,
                replicate: strategy.replicate,
                prefix_count: 1,
                criterion: 'M3_PLUS',
              },
            }),
          ),
        )
      }
      return Promise.resolve(
        apiResponse(
          makeResearchQualification({
            identity: {
              strategy_id: strategy.strategy_id,
              strategy_version: strategy.strategy_version,
              replicate: strategy.replicate,
              prefix_count: 1,
              criterion: 'M3_PLUS',
            },
          }),
        ),
      )
    })
    await wrapper.get('button.research-qualification-retry').trigger('click')
    await flushPromises()
    expect(fetchMock).toHaveBeenCalledTimes(4)
    expect(wrapper.findAll('.research-qualification-pair-row')).toHaveLength(2)
    expect(
      wrapper
        .findAll('.research-qualification-result-card')
        .map((card) => card.find('h3').text()),
    ).toEqual(['alias strategy/one', 'zero-observation'])
    wrapper.unmount()
  })

  it('isolates aggregate failures and renders closed NOT_READY cells on aggregate-only retry', async () => {
    const runs = [
      makeRun(),
      makeRun({
        run_id: 'run-explicit-2',
        import_identity_sha256: RIGHT_IMPORT_SHA,
      }),
    ]
    fetchMock.mockImplementation((input) => {
      const url = String(input)
      if (url.includes('/historical-results/runs')) {
        return Promise.resolve(
          apiResponse(makeRunPage({ items: runs, total_count: 2 })),
        )
      }
      return Promise.resolve(apiResponse(makeWindowPage()))
    })
    const wrapper = mount(HistoricalSuccessWindowsPage)
    await flushPromises()
    await selectRun(wrapper)
    await analyze(wrapper)
    for (const option of wrapper.findAll('.census-import-option input')) {
      await option.setValue(true)
    }
    await selectMatrix(wrapper)
    fetchMock.mockReset()
    fetchMock.mockImplementation((input) =>
      String(input).includes('/random-baseline-evidence')
        ? Promise.resolve(
            apiResponse(
              {
                error_code: 'HISTORICAL_PREFIX_SUCCESS_WINDOWS_UNAVAILABLE',
                message: '/private/detail',
              },
              503,
            ),
          )
        : Promise.resolve(apiResponse(makeResearchQualification())),
    )

    await evaluateResearchQualification(wrapper)

    expect(wrapper.findAll('.research-qualification-result-card')).toHaveLength(1)
    expect(wrapper.get('.qualification-random-baseline-error').text()).toContain(
      'Qualification projections above remain independent.',
    )
    expect(wrapper.text()).not.toContain('/private/detail')

    const partial = makeQualificationRandomBaselineEvidence()
    const notReady = makeNotReadyRandomBaseline()
    partial.ordered_cells[0]!.baseline = {
      ...notReady,
      cell: { ...partial.ordered_cells[0]!.baseline.cell },
    }
    partial.availability_summary.availability_status = 'PARTIAL'
    partial.availability_summary.ready_cell_count = 7
    partial.availability_summary.raw_upper_tail_probability_count = 7
    fetchMock.mockReset()
    fetchMock.mockResolvedValue(apiResponse(partial))

    await wrapper
      .get('button.qualification-random-baseline-retry')
      .trigger('click')
    await flushPromises()

    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(String(fetchMock.mock.calls[0]?.[0])).toContain(
      '/random-baseline-evidence',
    )
    const cells = wrapper.findAll('.qualification-random-baseline-cell')
    expect(cells).toHaveLength(8)
    expect(cells[0]!.text()).toContain('NOT_READY')
    expect(cells[0]!.text()).toContain('WINDOW_INCOMPLETE')
    expect(cells[0]!.text()).toContain('Not available')
    expect(wrapper.findAll('.research-qualification-result-card')).toHaveLength(1)
    wrapper.unmount()
  })

  it('aborts and ignores stale projection and random-evidence responses on selection changes and unmount', async () => {
    const runs = [
      makeRun(),
      makeRun({
        run_id: 'run-explicit-2',
        import_identity_sha256: RIGHT_IMPORT_SHA,
      }),
    ]
    fetchMock.mockImplementation((input) => {
      const url = String(input)
      if (url.includes('/historical-results/runs')) {
        return Promise.resolve(
          apiResponse(makeRunPage({ items: runs, total_count: 2 })),
        )
      }
      return Promise.resolve(apiResponse(makeWindowPage()))
    })
    const wrapper = mount(HistoricalSuccessWindowsPage)
    await flushPromises()
    await selectRun(wrapper)
    await analyze(wrapper)
    for (const option of wrapper.findAll('.census-import-option input')) {
      await option.setValue(true)
    }
    await selectMatrix(wrapper)
    const olderAggregate = deferred<Response>()
    const olderQualification = deferred<Response>()
    const newerAggregate = deferred<Response>()
    const newerQualification = deferred<Response>()
    fetchMock.mockReset()
    fetchMock
      .mockReturnValueOnce(olderAggregate.promise)
      .mockReturnValueOnce(olderQualification.promise)
      .mockReturnValueOnce(newerAggregate.promise)
      .mockReturnValueOnce(newerQualification.promise)

    await wrapper.get('button.research-qualification-action').trigger('click')
    const oldSignals = fetchMock.mock.calls
      .slice(0, 2)
      .map((call) => call[1]?.signal as AbortSignal)
    await wrapper.get('button.research-qualification-action').trigger('click')
    expect(oldSignals.every((signal) => signal.aborted)).toBe(true)
    newerAggregate.resolve(
      apiResponse(makeQualificationRandomBaselineEvidence()),
    )
    newerQualification.resolve(apiResponse(makeResearchQualification()))
    await flushPromises()
    const staleQualification = makeResearchQualification()
    staleQualification.identity.strategy_id = 'stale'
    const staleAggregate = makeQualificationRandomBaselineEvidence()
    staleAggregate.qualification_identity.strategy_id = 'stale'
    olderAggregate.resolve(apiResponse(staleAggregate))
    olderQualification.resolve(apiResponse(staleQualification))
    await flushPromises()
    expect(wrapper.findAll('.research-qualification-result-card')).toHaveLength(1)
    expect(
      wrapper.findAll('.qualification-random-baseline-result-card'),
    ).toHaveLength(1)
    expect(wrapper.text()).not.toContain('stale')

    const startPendingPair = async (): Promise<AbortSignal[]> => {
      const aggregatePending = deferred<Response>()
      const qualificationPending = deferred<Response>()
      fetchMock.mockReset()
      fetchMock
        .mockReturnValueOnce(aggregatePending.promise)
        .mockReturnValueOnce(qualificationPending.promise)
      await wrapper.get('button.research-qualification-action').trigger('click')
      return fetchMock.mock.calls.map(
        (call) => call[1]?.signal as AbortSignal,
      )
    }

    let signals = await startPendingPair()
    await wrapper.get('button.census-import-remove').trigger('click')
    expect(signals.every((signal) => signal.aborted)).toBe(true)
    await wrapper.get('.census-import-option input').setValue(true)

    signals = await startPendingPair()
    await wrapper.get('input.matrix-select').setValue(false)
    expect(signals.every((signal) => signal.aborted)).toBe(true)
    await wrapper.get('input.matrix-select').setValue(true)

    for (const [selector, value, reset] of [
      ['select[name="prefix-count"]', '2', '1'],
      ['select[name="criterion"]', 'M4_PLUS', 'M3_PLUS'],
    ] as const) {
      signals = await startPendingPair()
      await wrapper.get(selector).setValue(value)
      expect(signals.every((signal) => signal.aborted)).toBe(true)
      await wrapper.get(selector).setValue(reset)
    }

    signals = await startPendingPair()
    await wrapper.get('select[name="historical-run"]').setValue('')
    expect(signals.every((signal) => signal.aborted)).toBe(true)

    fetchMock.mockImplementation(successfulFetch)
    await wrapper.get('select[name="historical-run"]').setValue(IMPORT_SHA)
    await analyze(wrapper)
    for (const option of wrapper.findAll('.census-import-option input')) {
      await option.setValue(true)
    }
    await selectMatrix(wrapper)
    signals = await startPendingPair()
    wrapper.unmount()
    expect(signals.every((signal) => signal.aborted)).toBe(true)
  })

  it('aborts stale concordance on reevaluation, either run change, controls, and unmount', async () => {
    const comparison = makeRun({
      run_id: 'run-explicit-2',
      import_identity_sha256: RIGHT_IMPORT_SHA,
    })
    fetchMock.mockImplementation((input) => {
      const url = String(input)
      if (url.includes('/historical-results/runs')) {
        return Promise.resolve(
          apiResponse(makeRunPage({ items: [makeRun(), comparison], total_count: 2 })),
        )
      }
      return Promise.resolve(apiResponse(makeWindowPage()))
    })
    const wrapper = mount(HistoricalSuccessWindowsPage)
    await flushPromises()
    await selectRun(wrapper)
    await wrapper.get('select[name="comparison-run"]').setValue(RIGHT_IMPORT_SHA)
    await analyze(wrapper)
    await selectMatrix(wrapper)
    const older = deferred<Response>()
    const newer = deferred<Response>()
    fetchMock.mockReset()
    fetchMock.mockReturnValueOnce(older.promise).mockReturnValueOnce(newer.promise)

    await wrapper.get('button.cross-import-concordance-action').trigger('click')
    const oldSignal = fetchMock.mock.calls[0]?.[1]?.signal as AbortSignal
    await wrapper.get('button.cross-import-concordance-action').trigger('click')
    expect(oldSignal.aborted).toBe(true)
    newer.resolve(apiResponse(makeCrossImportConcordance()))
    await flushPromises()
    older.resolve(
      apiResponse(
        makeCrossImportConcordance({
          strategy: { ...makeCrossImportConcordance().strategy, strategy_id: 'stale' },
        }),
      ),
    )
    await flushPromises()
    expect(wrapper.findAll('.cross-import-concordance-result-card')).toHaveLength(1)
    expect(wrapper.text()).not.toContain('stale')

    const rightPending = deferred<Response>()
    fetchMock.mockReset()
    fetchMock.mockReturnValueOnce(rightPending.promise)
    await wrapper.get('button.cross-import-concordance-action').trigger('click')
    const rightSignal = fetchMock.mock.calls[0]?.[1]?.signal as AbortSignal
    await wrapper.get('select[name="comparison-run"]').setValue('')
    expect(rightSignal.aborted).toBe(true)

    await wrapper.get('select[name="comparison-run"]').setValue(RIGHT_IMPORT_SHA)
    const controlPending = deferred<Response>()
    fetchMock.mockReset()
    fetchMock.mockReturnValueOnce(controlPending.promise)
    await wrapper.get('button.cross-import-concordance-action').trigger('click')
    const controlSignal = fetchMock.mock.calls[0]?.[1]?.signal as AbortSignal
    await wrapper.get('select[name="criterion"]').setValue('M4_PLUS')
    expect(controlSignal.aborted).toBe(true)

    await wrapper.get('select[name="criterion"]').setValue('M3_PLUS')
    const leftPending = deferred<Response>()
    fetchMock.mockReset()
    fetchMock.mockReturnValueOnce(leftPending.promise)
    await wrapper.get('button.cross-import-concordance-action').trigger('click')
    const leftSignal = fetchMock.mock.calls[0]?.[1]?.signal as AbortSignal
    await wrapper.get('select[name="historical-run"]').setValue('')
    expect(leftSignal.aborted).toBe(true)

    fetchMock.mockImplementation(successfulFetch)
    await wrapper.get('select[name="historical-run"]').setValue(IMPORT_SHA)
    await analyze(wrapper)
    await selectMatrix(wrapper)
    fetchMock.mockReset()
    fetchMock.mockImplementation(() => new Promise<Response>(() => undefined))
    await wrapper.get('button.cross-import-concordance-action').trigger('click')
    const unmountSignal = fetchMock.mock.calls[0]?.[1]?.signal as AbortSignal
    wrapper.unmount()
    expect(unmountSignal.aborted).toBe(true)
  })
})
