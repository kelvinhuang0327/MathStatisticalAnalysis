// @vitest-environment jsdom

import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import HistoricalSuccessWindowsPage from '../src/features/historical-success-windows/HistoricalSuccessWindowsPage.vue'
import {
  apiResponse,
  deferred,
  IMPORT_SHA,
  makeAllRelationsMatrix,
  makeMatrix,
  makeResult,
  makeRun,
  makeRunPage,
  makeWindowPage,
  makeZeroObservationMatrix,
  makeZeroObservationResult,
} from './historical-success-windows-fixtures'

let fetchMock: ReturnType<typeof vi.fn<typeof fetch>>

function successfulFetch(input: RequestInfo | URL): Promise<Response> {
  const url = String(input)
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
})
