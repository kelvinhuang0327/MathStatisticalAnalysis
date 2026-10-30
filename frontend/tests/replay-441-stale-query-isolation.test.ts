// @vitest-environment jsdom

import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'

import ReplayHistoryPage from '../src/features/replay-history/ReplayHistoryPage.vue'

interface CapturedResponse {
  name?: string
  method?: string
  path?: string
  query?: Record<string, string>
  request?: {
    method: string
    path: string
    query: Record<string, string>
    url: string
  }
  status_code: number
  headers?: Record<string, string>
  raw_body: string
  body?: Record<string, unknown>
}

interface CompleteCatalogCapture {
  responses: Record<string, CapturedResponse>
}

interface PeriodCapture {
  responses: CapturedResponse[]
}

interface ObservedRequest {
  method: string
  path: string
  query: Record<string, string>
  signal: AbortSignal | null
}

type PredictionHandler = (
  url: URL,
  signal: AbortSignal | null,
) => Response | Promise<Response>

const completeCapture = JSON.parse(
  readFileSync(resolve(process.cwd(), 'tests/fixtures/replay-441-complete-catalog-http.json'), 'utf8'),
) as CompleteCatalogCapture
const periodCapture = JSON.parse(
  readFileSync(resolve(process.cwd(), 'tests/fixtures/replay-441-period-date-http.json'), 'utf8'),
) as PeriodCapture

function capturedCatalogResponse(name: string): CapturedResponse {
  const response = completeCapture.responses[name]
  if (!response) throw new Error(`Missing captured HTTP response ${name}`)
  return response
}

function capturedPeriodResponse(name: string): CapturedResponse {
  const response = periodCapture.responses.find((candidate) => candidate.name === name)
  if (!response) throw new Error(`Missing captured HTTP response ${name}`)
  return response
}

function responseFromCapture(record: CapturedResponse): Response {
  const payload = JSON.parse(record.raw_body) as unknown
  if (record.body) expect(payload).toEqual(record.body)
  return {
    ok: record.status_code >= 200 && record.status_code < 400,
    status: record.status_code,
    headers: new Headers(record.headers ?? {}),
    json: vi.fn().mockResolvedValue(payload),
  } as unknown as Response
}

function installRecordedFetch(predictionHandler: PredictionHandler) {
  const requests: ObservedRequest[] = []
  const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    const url = new URL(String(input), 'http://testserver')
    const method = init?.method ?? 'GET'
    const query = Object.fromEntries(url.searchParams.entries())
    const signal = init?.signal instanceof AbortSignal ? init.signal : null
    requests.push({ method, path: url.pathname, query, signal })

    if (url.pathname === '/api/v1/historical-results/runs') {
      return Promise.resolve({
        ok: true,
        status: 200,
        json: async () => ({ items: [], total_count: 0, limit: 50, offset: 0 }),
      } as Response)
    }

    if (url.pathname === '/api/v1/replay-backfill/predictions') {
      return Promise.resolve(predictionHandler(url, signal))
    }

    let recordName: string | undefined
    if (url.pathname === '/api/v1/replay-backfill/strategies') {
      recordName = query.lottery_type === 'DAILY_539'
        ? 'strategies_DAILY_539_page1'
        : 'strategies_BIG_LOTTO_page1'
    } else if (url.pathname === '/api/v1/replay-strategy-inventory') {
      recordName = `inventory_${query.lottery_type}`
    } else if (url.pathname === '/api/v1/replay-backfill/coverage') {
      recordName = `coverage_${query.lottery_type}`
    }

    if (!recordName) throw new Error(`Unexpected request ${method} ${url.pathname}${url.search}`)
    return Promise.resolve(responseFromCapture(capturedCatalogResponse(recordName)))
  })

  vi.stubGlobal('fetch', fetchMock)
  return { fetchMock, requests }
}

function deferred<T>() {
  let resolvePromise!: (value: T) => void
  let rejectPromise!: (reason: unknown) => void
  const promise = new Promise<T>((resolveValue, rejectValue) => {
    resolvePromise = resolveValue
    rejectPromise = rejectValue
  })
  return { promise, resolve: resolvePromise, reject: rejectPromise }
}

async function activateBackfill(wrapper: VueWrapper): Promise<void> {
  const tabs = wrapper.findAll('nav[aria-label="Replay history sections"] button')
  expect(tabs.length).toBeGreaterThan(2)
  await tabs[2]!.trigger('click')
  await flushPromises()
}

function backfillRoot(wrapper: VueWrapper) {
  return wrapper.get('[data-testid="strategy-backfill"]')
}

function strategyIdentityTable(wrapper: VueWrapper) {
  const table = backfillRoot(wrapper)
    .findAll('table')
    .find((candidate) => candidate.find('caption').text().startsWith('Strategy identities'))
  if (!table) throw new Error('Strategy identity table was not rendered')
  return table
}

function predictionRows(wrapper: VueWrapper) {
  return backfillRoot(wrapper).findAll('[data-testid^="backfill-row-"]')
}

function renderedDrawNumbers(wrapper: VueWrapper): string[] {
  return predictionRows(wrapper).map((row) => row.findAll('td')[1]!.text())
}

function renderedPredictionIdentities(wrapper: VueWrapper): string[] {
  return predictionRows(wrapper).map((row) => {
    const cells = row.findAll('td')
    const strategyCell = cells[3]!
    return JSON.stringify([
      cells[0]!.text(),
      strategyCell.find('code').text(),
      strategyCell.find('span').text(),
      cells[1]!.text(),
    ])
  })
}

function responseItems(record: CapturedResponse): Array<Record<string, unknown>> {
  const payload = JSON.parse(record.raw_body) as { items: Array<Record<string, unknown>> }
  return payload.items
}

function capturedPredictionIdentities(record: CapturedResponse): string[] {
  return responseItems(record).map((item) => JSON.stringify([
    item.lottery_type === 'BIG_LOTTO' ? 'B649' : String(item.lottery_type),
    item.strategy_id,
    item.strategy_version,
    item.target_draw_number,
  ]))
}

afterEach(() => vi.unstubAllGlobals())

describe('Replay History stale query isolation', () => {
  it('keeps DAILY_539 selected when a stale BIG_LOTTO success finishes after the current 503', async () => {
    const oldBigLottoResponse = deferred<Response>()
    const predictionSequence: string[] = []
    const harness = installRecordedFetch((url) => {
      const lotteryType = url.searchParams.get('lottery_type')
      predictionSequence.push(`REQUEST ${lotteryType}`)
      if (lotteryType === 'BIG_LOTTO') return oldBigLottoResponse.promise
      if (lotteryType === 'DAILY_539') {
        return responseFromCapture(capturedCatalogResponse('strategies_BIG_LOTTO_page2_503'))
      }
      throw new Error(`Unexpected prediction lottery ${lotteryType}`)
    })

    const wrapper = mount(ReplayHistoryPage)
    await flushPromises()
    await activateBackfill(wrapper)

    const backfill = backfillRoot(wrapper)
    const form = backfill.get('form')
    await form.get('input[name="from_date"]').setValue('2026-01-01')
    await form.get('input[name="to_date"]').setValue('2026-02-22')
    await form.get('select[name="period"]').setValue('ALL')
    await form.trigger('submit')
    await flushPromises()
    expect(predictionSequence).toEqual(['REQUEST BIG_LOTTO'])

    await backfill.get('select[name="lottery_type"]').setValue('DAILY_539')
    await flushPromises()
    expect(harness.requests.find((request) => request.path === '/api/v1/replay-backfill/predictions')?.signal?.aborted).toBe(true)

    const dailyIdentityRows = strategyIdentityTable(wrapper).findAll('tbody tr')
    expect(dailyIdentityRows.length).toBeGreaterThan(0)
    expect(dailyIdentityRows.every((row) => row.findAll('td')[1]!.text() === 'T539')).toBe(true)
    expect(strategyIdentityTable(wrapper).text()).toContain('539_3bet_orthogonal')

    await form.trigger('submit')
    await flushPromises()
    expect(predictionSequence).toEqual(['REQUEST BIG_LOTTO', 'REQUEST DAILY_539'])
    expect(backfill.get('[data-testid="backfill-predictions-error"]').text()).toContain('HTTP 503')
    expect(backfill.get('[data-testid="backfill-query-status"]').text()).toContain('error')
    expect(backfill.find('[data-testid="backfill-predictions-empty"]').exists()).toBe(false)

    const oldBigLottoCapture = capturedCatalogResponse('predictions_BIG_LOTTO_all_page1')
    expect(responseItems(oldBigLottoCapture).every((item) => item.lottery_type === 'BIG_LOTTO')).toBe(true)
    oldBigLottoResponse.resolve(responseFromCapture(oldBigLottoCapture))
    await flushPromises()

    expect((backfill.get('select[name="lottery_type"]').element as HTMLSelectElement).value).toBe('DAILY_539')
    expect(strategyIdentityTable(wrapper).findAll('tbody tr').every((row) => row.findAll('td')[1]!.text() === 'T539')).toBe(true)
    expect(predictionRows(wrapper)).toHaveLength(0)
    expect(backfill.get('[data-testid="backfill-predictions-error"]').text()).toContain('HTTP 503')
    expect(backfill.get('[data-testid="backfill-query-status"]').text()).toContain('error')
    wrapper.unmount()
  })

  it('keeps the ALL result when a slower 50-period response arrives last', async () => {
    const oldFiftyResponse = deferred<Response>()
    const completionOrder: string[] = []
    const harness = installRecordedFetch((url) => {
      const period = url.searchParams.get('period')
      if (period === '50') return oldFiftyResponse.promise
      if (period === 'ALL') {
        return Promise.resolve(responseFromCapture(capturedPeriodResponse('period_ALL')))
      }
      throw new Error(`Unexpected replay period ${period}`)
    })

    const wrapper = mount(ReplayHistoryPage)
    await flushPromises()
    await activateBackfill(wrapper)
    const backfill = backfillRoot(wrapper)
    const form = backfill.get('form')

    await backfill.get('select[name="period"]').setValue('50')
    await form.trigger('submit')
    await flushPromises()
    expect(harness.requests.filter((request) => request.path === '/api/v1/replay-backfill/predictions').map((request) => request.query.period)).toEqual(['50'])

    await backfill.get('select[name="period"]').setValue('ALL')
    await flushPromises()
    await form.trigger('submit')
    await flushPromises()
    completionOrder.push('ALL success')

    const allCapture = capturedPeriodResponse('period_ALL')
    const expectedAllDraws = responseItems(allCapture).map((item) => String(item.target_draw_number))
    expect((backfill.get('select[name="period"]').element as HTMLSelectElement).value).toBe('ALL')
    expect(renderedDrawNumbers(wrapper)).toEqual(expectedAllDraws)
    expect(renderedPredictionIdentities(wrapper)).toEqual(capturedPredictionIdentities(allCapture))
    expect(new Set(renderedPredictionIdentities(wrapper)).size).toBe(expectedAllDraws.length)
    expect(backfill.get('[data-testid="backfill-query-status"]').text()).toContain('ready')

    oldFiftyResponse.resolve(responseFromCapture(capturedPeriodResponse('period_50')))
    await flushPromises()
    completionOrder.push('50 success')

    expect(completionOrder).toEqual(['ALL success', '50 success'])
    expect(renderedDrawNumbers(wrapper)).toEqual(expectedAllDraws)
    expect(renderedDrawNumbers(wrapper)).toHaveLength(53)
    expect(backfill.find('[data-testid="backfill-predictions-error"]').exists()).toBe(false)
    wrapper.unmount()
  })

  it('ignores a stale 503 while preserving the newer successful query', async () => {
    const oldFiftyResponse = deferred<Response>()
    const harness = installRecordedFetch((url) => {
      const period = url.searchParams.get('period')
      if (period === '50') return oldFiftyResponse.promise
      if (period === 'ALL') {
        return Promise.resolve(responseFromCapture(capturedPeriodResponse('period_ALL')))
      }
      throw new Error(`Unexpected replay period ${period}`)
    })

    const wrapper = mount(ReplayHistoryPage)
    await flushPromises()
    await activateBackfill(wrapper)
    const backfill = backfillRoot(wrapper)
    const form = backfill.get('form')

    await backfill.get('select[name="period"]').setValue('50')
    await form.trigger('submit')
    await flushPromises()
    await backfill.get('select[name="period"]').setValue('ALL')
    await flushPromises()
    await form.trigger('submit')
    await flushPromises()

    const expectedAllDraws = responseItems(capturedPeriodResponse('period_ALL'))
      .map((item) => String(item.target_draw_number))
    expect(renderedDrawNumbers(wrapper)).toEqual(expectedAllDraws)
    expect(renderedPredictionIdentities(wrapper)).toEqual(
      capturedPredictionIdentities(capturedPeriodResponse('period_ALL')),
    )

    oldFiftyResponse.resolve(responseFromCapture(capturedCatalogResponse('strategies_BIG_LOTTO_page2_503')))
    await flushPromises()

    expect((backfill.get('select[name="period"]').element as HTMLSelectElement).value).toBe('ALL')
    expect(renderedDrawNumbers(wrapper)).toEqual(expectedAllDraws)
    expect(backfill.get('[data-testid="backfill-query-status"]').text()).toContain('ready')
    expect(backfill.find('[data-testid="backfill-predictions-error"]').exists()).toBe(false)
    expect(backfill.find('[data-testid="backfill-predictions-empty"]').exists()).toBe(false)
    expect(harness.requests.filter((request) => request.path === '/api/v1/replay-backfill/predictions').map((request) => request.query.period)).toEqual(['50', 'ALL'])
    wrapper.unmount()
  })
})
