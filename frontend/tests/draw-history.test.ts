// @vitest-environment jsdom

import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { DrawHistoryResponse } from '../src/api/drawData'
import DrawHistoryPage from '../src/features/draw-history/DrawHistoryPage.vue'

const draw = {
  lottery_type: 'BIG_LOTTO',
  draw_number: '0002',
  draw_date: '2026-07-16',
  main_numbers: [1, 3, 9, 17, 24, 49],
  special_numbers: [7],
  source_name: 'draws.csv',
  source_reference: 'synthetic-reference',
  ingestion_run_id: '7de87eeb-ecc7-4c03-830a-c0fdb71254e8',
  created_at: '2026-07-16T07:00:00Z',
  updated_at: '2026-07-16T07:00:00Z',
} satisfies DrawHistoryResponse['records'][number]

const emptyPage = {
  records: [],
  page: 1,
  page_size: 25,
  total_count: 0,
  total_pages: 0,
  sort: ['draw_date:desc', 'draw_number:string_desc', 'id:desc'],
} satisfies DrawHistoryResponse

const populatedPage = {
  ...emptyPage,
  records: [draw],
  total_count: 2,
  total_pages: 2,
} satisfies DrawHistoryResponse

function pageFor(
  drawNumber: string,
  totalCount: number,
  page: number,
  totalPages: number,
): DrawHistoryResponse {
  return {
    ...populatedPage,
    records: [{ ...draw, draw_number: drawNumber }],
    page,
    total_count: totalCount,
    total_pages: totalPages,
  }
}

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise
    reject = rejectPromise
  })
  return { promise, resolve, reject }
}

let fetchMock: ReturnType<typeof vi.fn<typeof fetch>>

function apiResponse(payload: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: vi.fn().mockResolvedValue(payload),
  } as unknown as Response
}

beforeEach(() => {
  fetchMock = vi.fn<typeof fetch>()
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('DrawHistoryPage', () => {
  it('renders loading then the explicit empty state', async () => {
    fetchMock.mockReturnValue(new Promise<Response>(() => undefined))
    const wrapper = mount(DrawHistoryPage)
    expect(wrapper.text()).toContain('Loading draw history…')
    wrapper.unmount()

    fetchMock.mockResolvedValue(apiResponse(emptyPage))
    const empty = mount(DrawHistoryPage)
    await flushPromises()
    expect(empty.text()).toContain('No draws match this query')
    expect(empty.text()).toContain('Matching draws0')
    empty.unmount()
  })

  it('renders deterministic draw, source, run, and timestamp metadata', async () => {
    fetchMock.mockResolvedValue(apiResponse(populatedPage))
    const wrapper = mount(DrawHistoryPage)
    await flushPromises()

    expect(wrapper.text()).toContain('0002')
    expect(wrapper.text()).toContain('1')
    expect(wrapper.text()).toContain('49')
    expect(wrapper.text()).toContain('draws.csv')
    expect(wrapper.text()).toContain('synthetic-reference')
    expect(wrapper.text()).toContain(draw.ingestion_run_id)
    expect(wrapper.text()).toContain('draw_date:desc · draw_number:string_desc · id:desc')
    expect(wrapper.text()).toContain('B649')
    expect(wrapper.text()).not.toContain('BIG_LOTTO')
    const buttonLabels = wrapper.findAll('button').map((button) => button.text())
    expect(buttonLabels).not.toContain('Edit')
    expect(buttonLabels).not.toContain('Delete')
    wrapper.unmount()
  })

  it('sends filters, bounded page size, pagination, and reset queries', async () => {
    fetchMock.mockResolvedValue(apiResponse(populatedPage))
    const wrapper = mount(DrawHistoryPage)
    await flushPromises()

    await wrapper.get('input[name="draw-number"]').setValue('000')
    await wrapper.get('input[name="date-from"]').setValue('2026-02-30')
    expect(wrapper.get('input[name="date-from"]').attributes('aria-invalid')).toBe('true')
    expect(wrapper.get('button[type="submit"]').attributes('disabled')).toBeDefined()
    await wrapper.get('input[name="date-from"]').setValue('2026-07-01')
    await wrapper.get('input[name="date-to"]').setValue('2026-07-16')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    const filterUrl = String(fetchMock.mock.calls[1]?.[0])
    expect(filterUrl).toContain('lottery_type=BIG_LOTTO')
    expect(filterUrl).toContain('draw_number=000')
    expect(filterUrl).toContain('date_from=2026-07-01')
    expect(filterUrl).toContain('date_to=2026-07-16')
    expect(filterUrl).toContain('page=1')

    const next = wrapper.findAll('button').find((button) => button.text() === 'Next')
    expect(next).toBeDefined()
    await next?.trigger('click')
    await flushPromises()
    expect(String(fetchMock.mock.calls[2]?.[0])).toContain('page=2')

    for (const [index, pageSize] of [10, 25, 50, 100].entries()) {
      await wrapper.get('select[name="page-size"]').setValue(String(pageSize))
      await flushPromises()
      const sizeUrl = String(fetchMock.mock.calls[index + 3]?.[0])
      expect(sizeUrl).toContain(`page_size=${pageSize}`)
      expect(sizeUrl).toContain('page=1')
    }

    const reset = wrapper.findAll('button').find((button) => button.text() === 'Reset query')
    await reset?.trigger('click')
    await flushPromises()
    const resetUrl = String(fetchMock.mock.calls[7]?.[0])
    expect(resetUrl).not.toContain('draw_number')
    expect(resetUrl).not.toContain('date_from')
    expect(resetUrl).toContain('page_size=25')
    wrapper.unmount()
  })

  it('renders a recoverable sanitized error state', async () => {
    fetchMock.mockResolvedValue(
      apiResponse(
        { error_code: 'REPOSITORY_UNAVAILABLE', message: 'Local draw data is unavailable.' },
        503,
      ),
    )
    const wrapper = mount(DrawHistoryPage)
    await flushPromises()

    expect(wrapper.text()).toContain('Local draw data is unavailable.')
    const retry = wrapper.findAll('button').find((button) => button.text() === 'Retry')
    expect(retry).toBeDefined()
    await retry?.trigger('click')
    await flushPromises()
    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('Local draw data is unavailable.')
    expect(wrapper.find('table').exists()).toBe(false)
    wrapper.unmount()
  })

  it('keeps the newest successful query when an aborted request resolves later', async () => {
    const earlier = deferred<Response>()
    const latest = deferred<Response>()
    fetchMock.mockReturnValueOnce(earlier.promise).mockReturnValueOnce(latest.promise)
    const wrapper = mount(DrawHistoryPage)

    expect(fetchMock).toHaveBeenCalledTimes(1)
    await wrapper.get('input[name="draw-number"]').setValue('0003')
    await wrapper.get('form').trigger('submit')
    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(fetchMock.mock.calls[0]?.[1]?.signal?.aborted).toBe(true)

    latest.resolve(apiResponse(pageFor('0003', 3, 1, 4)))
    await flushPromises()
    expect(wrapper.get('.scope-card strong').text()).toBe('3')
    expect(wrapper.get('code.draw-identity').text()).toBe('0003')
    expect(wrapper.get('.pagination').text()).toContain('Page 1 of 4')
    expect(wrapper.find('.state-panel').exists()).toBe(false)

    earlier.resolve(apiResponse(pageFor('0001', 99, 8, 9)))
    await flushPromises()
    expect(wrapper.get('.scope-card strong').text()).toBe('3')
    expect(wrapper.get('code.draw-identity').text()).toBe('0003')
    expect(wrapper.get('.pagination').text()).toContain('Page 1 of 4')
    expect(wrapper.find('.state-panel').exists()).toBe(false)
    wrapper.unmount()
  })

  it('ignores an earlier query failure after the latest query succeeds', async () => {
    const earlier = deferred<Response>()
    const latest = deferred<Response>()
    fetchMock.mockReturnValueOnce(earlier.promise).mockReturnValueOnce(latest.promise)
    const wrapper = mount(DrawHistoryPage)

    await wrapper.get('input[name="draw-number"]').setValue('0003')
    await wrapper.get('form').trigger('submit')
    latest.resolve(apiResponse(pageFor('0003', 3, 1, 4)))
    await flushPromises()
    earlier.reject(new Error('stale A failure'))
    await flushPromises()

    expect(wrapper.get('.scope-card strong').text()).toBe('3')
    expect(wrapper.get('code.draw-identity').text()).toBe('0003')
    expect(wrapper.get('.pagination').text()).toContain('Page 1 of 4')
    expect(wrapper.text()).not.toContain('stale A failure')
    expect(wrapper.find('.state-panel--error').exists()).toBe(false)
    wrapper.unmount()
  })

  it('shows the latest query error and retry action', async () => {
    const earlier = deferred<Response>()
    const latest = deferred<Response>()
    fetchMock.mockReturnValueOnce(earlier.promise).mockReturnValueOnce(latest.promise)
    const wrapper = mount(DrawHistoryPage)

    await wrapper.get('input[name="draw-number"]').setValue('0003')
    await wrapper.get('form').trigger('submit')
    latest.reject(new Error('latest query failed'))
    await flushPromises()
    expect(wrapper.find('.state-panel--error').text()).toContain('latest query failed')
    expect(wrapper.findAll('button').some((button) => button.text() === 'Retry')).toBe(true)

    earlier.resolve(apiResponse(pageFor('0001', 99, 8, 9)))
    await flushPromises()
    expect(wrapper.find('.state-panel--error').text()).toContain('latest query failed')
    expect(wrapper.get('.scope-card strong').text()).toBe('—')
    expect(wrapper.find('table').exists()).toBe(false)
    wrapper.unmount()
  })

  it('aborts the previous query and the current query on unmount', async () => {
    fetchMock.mockReturnValue(new Promise<Response>(() => undefined))
    const wrapper = mount(DrawHistoryPage)
    const earlierSignal = fetchMock.mock.calls[0]?.[1]?.signal

    await wrapper.get('input[name="draw-number"]').setValue('0003')
    await wrapper.get('form').trigger('submit')
    const latestSignal = fetchMock.mock.calls[1]?.[1]?.signal
    expect(earlierSignal?.aborted).toBe(true)
    expect(latestSignal?.aborted).toBe(false)

    wrapper.unmount()
    expect(latestSignal?.aborted).toBe(true)
  })
})
