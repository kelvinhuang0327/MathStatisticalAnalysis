// @vitest-environment jsdom

import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { DrawHistoryResponse } from '../src/api/drawData'
import DrawPeriodOverview from '../src/features/data-operations/DrawPeriodOverview.vue'
import DataOperationsPage from '../src/features/data-operations/DataOperationsPage.vue'

let fetchMock: ReturnType<typeof vi.fn<typeof fetch>>

function deferred<T>() {
  let resolve!: (value: T | PromiseLike<T>) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

function apiResponse(payload: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: vi.fn().mockResolvedValue(payload),
  } as unknown as Response
}

function makeDrawRecord(
  lotteryType: 'BIG_LOTTO' | 'POWER_LOTTO' | 'DAILY_539',
  drawNumber: string,
  drawDate: string,
) {
  return {
    lottery_type: lotteryType,
    draw_number: drawNumber,
    draw_date: drawDate,
    main_numbers: [1, 2, 3, 4, 5, 6],
    special_numbers: [7],
    source_name: 'test.csv',
    source_reference: null,
    ingestion_run_id: 'test-run-id',
    created_at: '2026-07-16T00:00:00Z',
    updated_at: '2026-07-16T00:00:00Z',
  }
}

function makeDrawPage(
  lotteryType: 'BIG_LOTTO' | 'POWER_LOTTO' | 'DAILY_539',
  totalCount: number,
  drawNumber = '0001',
  drawDate = '2026-07-16',
): DrawHistoryResponse {
  return {
    records: totalCount > 0 ? [makeDrawRecord(lotteryType, drawNumber, drawDate)] : [],
    page: 1,
    page_size: 1,
    total_count: totalCount,
    total_pages: totalCount > 0 ? totalCount : 0,
    sort: ['draw_date:desc', 'draw_number:string_desc', 'id:desc'],
  }
}

const mockB649 = makeDrawPage('BIG_LOTTO', 1542, '0002', '2026-07-16')
const mockP638 = makeDrawPage('POWER_LOTTO', 890, '0042', '2026-08-01')
const mockT539 = makeDrawPage('DAILY_539', 3200, '0105', '2026-09-10')

function routeMockByUrl(urlStr: string): Response {
  const url = new URL(urlStr, 'http://localhost')
  if (url.pathname === '/api/v1/draws') {
    const lottery = url.searchParams.get('lottery_type')
    if (lottery === 'BIG_LOTTO') return apiResponse(mockB649)
    if (lottery === 'POWER_LOTTO') return apiResponse(mockP638)
    if (lottery === 'DAILY_539') return apiResponse(mockT539)
  }
  if (url.pathname === '/api/v1/ingestion-runs') {
    return apiResponse({
      records: [],
      page: 1,
      page_size: 25,
      total_count: 0,
      total_pages: 0,
      sort: ['started_at:desc', 'id:desc'],
    })
  }
  return apiResponse({}, 404)
}

beforeEach(() => {
  fetchMock = vi.fn<typeof fetch>()
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('DrawPeriodOverview', () => {
  it('AC2: makes three distinct queries with exact enum lottery_type and page=1&page_size=1', async () => {
    fetchMock.mockImplementation((input) => Promise.resolve(routeMockByUrl(String(input))))
    const wrapper = mount(DrawPeriodOverview)
    await flushPromises()

    const drawCalls = fetchMock.mock.calls
      .map((call) => new URL(String(call[0]), 'http://localhost'))
      .filter((url) => url.pathname === '/api/v1/draws')

    expect(drawCalls).toHaveLength(3)

    const lotteryTypes = drawCalls.map((url) => url.searchParams.get('lottery_type'))
    expect(lotteryTypes).toContain('BIG_LOTTO')
    expect(lotteryTypes).toContain('POWER_LOTTO')
    expect(lotteryTypes).toContain('DAILY_539')

    for (const url of drawCalls) {
      expect(url.searchParams.get('page')).toBe('1')
      expect(url.searchParams.get('page_size')).toBe('1')
      expect(url.searchParams.has('draw_number')).toBe(false)
      expect(url.searchParams.has('date_from')).toBe(false)
      expect(url.searchParams.has('date_to')).toBe(false)
    }
    wrapper.unmount()
  })

  it('AC3: renders authoritative total_count from each game response', async () => {
    fetchMock.mockImplementation((input) => Promise.resolve(routeMockByUrl(String(input))))
    const wrapper = mount(DrawPeriodOverview)
    await flushPromises()

    expect(wrapper.get('[data-testid="total-count-B649"]').text()).toBe('1542')
    expect(wrapper.get('[data-testid="total-count-P638"]').text()).toBe('890')
    expect(wrapper.get('[data-testid="total-count-T539"]').text()).toBe('3200')
    wrapper.unmount()
  })

  it('AC4: renders latest draw number with leading zeros and draw date', async () => {
    fetchMock.mockImplementation((input) => Promise.resolve(routeMockByUrl(String(input))))
    const wrapper = mount(DrawPeriodOverview)
    await flushPromises()

    expect(wrapper.get('[data-testid="latest-draw-B649"]').text()).toBe('0002')
    expect(wrapper.get('[data-testid="latest-date-B649"]').text()).toBe('2026-07-16')

    expect(wrapper.get('[data-testid="latest-draw-P638"]').text()).toBe('0042')
    expect(wrapper.get('[data-testid="latest-date-P638"]').text()).toBe('2026-08-01')

    expect(wrapper.get('[data-testid="latest-draw-T539"]').text()).toBe('0105')
    expect(wrapper.get('[data-testid="latest-date-T539"]').text()).toBe('2026-09-10')
    wrapper.unmount()
  })

  it('AC5: enforces strict game isolation without cross-contamination', async () => {
    fetchMock.mockImplementation((input) => Promise.resolve(routeMockByUrl(String(input))))
    const wrapper = mount(DrawPeriodOverview)
    await flushPromises()

    const b649Card = wrapper.get('[data-testid="period-card-B649"]').text()
    expect(b649Card).toContain('1542')
    expect(b649Card).toContain('0002')
    expect(b649Card).not.toContain('890')
    expect(b649Card).not.toContain('0042')
    expect(b649Card).not.toContain('3200')

    const p638Card = wrapper.get('[data-testid="period-card-P638"]').text()
    expect(p638Card).toContain('890')
    expect(p638Card).toContain('0042')
    expect(p638Card).not.toContain('1542')
    expect(p638Card).not.toContain('0002')

    const t539Card = wrapper.get('[data-testid="period-card-T539"]').text()
    expect(t539Card).toContain('3200')
    expect(t539Card).toContain('0105')
    expect(t539Card).not.toContain('1542')
    expect(t539Card).not.toContain('890')
    wrapper.unmount()
  })

  it('AC6: empty state displays 0 total draws and dash for latest draw without fabricated values', async () => {
    fetchMock.mockImplementation((input) => {
      const url = new URL(String(input), 'http://localhost')
      const lottery = url.searchParams.get('lottery_type')
      if (lottery === 'BIG_LOTTO') {
        return Promise.resolve(apiResponse(makeDrawPage('BIG_LOTTO', 0)))
      }
      return Promise.resolve(routeMockByUrl(String(input)))
    })

    const wrapper = mount(DrawPeriodOverview)
    await flushPromises()

    expect(wrapper.get('[data-testid="total-count-B649"]').text()).toBe('0')
    expect(wrapper.get('[data-testid="latest-draw-B649"]').text()).toBe('—')
    expect(wrapper.get('[data-testid="latest-date-B649"]').text()).toBe('—')
    expect(wrapper.get('[data-testid="status-B649"]').text()).toBe('EMPTY')
    wrapper.unmount()
  })

  it('AC7: error or 503 displays unavailable and never shows fake 0', async () => {
    fetchMock.mockImplementation((input) => {
      const url = new URL(String(input), 'http://localhost')
      const lottery = url.searchParams.get('lottery_type')
      if (lottery === 'POWER_LOTTO') {
        return Promise.resolve(
          apiResponse(
            { error_code: 'REPOSITORY_UNAVAILABLE', message: 'Local draw data is unavailable.' },
            503,
          ),
        )
      }
      if (lottery === 'DAILY_539') {
        return Promise.reject(new TypeError('Failed to fetch'))
      }
      return Promise.resolve(routeMockByUrl(String(input)))
    })

    const wrapper = mount(DrawPeriodOverview)
    await flushPromises()

    // B649 succeeds normally
    expect(wrapper.get('[data-testid="total-count-B649"]').text()).toBe('1542')
    expect(wrapper.get('[data-testid="status-B649"]').text()).toBe('READY')

    // P638 HTTP 503
    expect(wrapper.get('[data-testid="total-count-P638"]').text()).toBe('Unavailable')
    expect(wrapper.get('[data-testid="total-count-P638"]').text()).not.toBe('0')
    expect(wrapper.get('[data-testid="latest-draw-P638"]').text()).toBe('—')
    expect(wrapper.get('[data-testid="status-P638"]').text()).toBe('UNAVAILABLE')
    expect(wrapper.get('[data-testid="error-P638"]').text()).toContain('Local draw data is unavailable.')
    expect(wrapper.find('[data-testid="retry-P638"]').exists()).toBe(true)

    // T539 Network error
    expect(wrapper.get('[data-testid="total-count-T539"]').text()).toBe('Unavailable')
    expect(wrapper.get('[data-testid="total-count-T539"]').text()).not.toBe('0')
    expect(wrapper.get('[data-testid="latest-draw-T539"]').text()).toBe('—')
    expect(wrapper.get('[data-testid="status-T539"]').text()).toBe('UNAVAILABLE')
    expect(wrapper.find('[data-testid="retry-T539"]').exists()).toBe(true)

    wrapper.unmount()
  })

  it('AC8: stale out-of-order response does not overwrite newer state', async () => {
    const slowResponse = deferred<Response>()
    let callCount = 0

    fetchMock.mockImplementation((input) => {
      const url = new URL(String(input), 'http://localhost')
      const lottery = url.searchParams.get('lottery_type')
      if (lottery === 'BIG_LOTTO') {
        callCount++
        if (callCount === 1) {
          // Slow initial call
          return slowResponse.promise
        }
        // Newer refresh call: completes fast with new data
        return Promise.resolve(
          apiResponse(makeDrawPage('BIG_LOTTO', 9999, '9999', '2026-12-31')),
        )
      }
      return Promise.resolve(routeMockByUrl(String(input)))
    })

    const wrapper = mount(DrawPeriodOverview)
    // First request is in flight for B649
    expect(wrapper.get('[data-testid="total-count-B649"]').text()).toBe('—')

    // Trigger a refresh (second request)
    await wrapper.get('[data-testid="refresh-overview"]').trigger('click')
    await flushPromises()

    // Second request resolved
    expect(wrapper.get('[data-testid="total-count-B649"]').text()).toBe('9999')
    expect(wrapper.get('[data-testid="latest-draw-B649"]').text()).toBe('9999')

    // Now resolve the older, slow response with stale data (1542, 0002)
    slowResponse.resolve(apiResponse(makeDrawPage('BIG_LOTTO', 1542, '0002', '2026-07-16')))
    await flushPromises()

    // B649 must still have 9999, not overwritten by 1542
    expect(wrapper.get('[data-testid="total-count-B649"]').text()).toBe('9999')
    expect(wrapper.get('[data-testid="latest-draw-B649"]').text()).toBe('9999')

    wrapper.unmount()
  })

  it('aborts pending fetch requests when component unmounts', async () => {
    const pending = deferred<Response>()
    fetchMock.mockImplementation(() => pending.promise)

    const wrapper = mount(DrawPeriodOverview)
    expect(fetchMock).toHaveBeenCalledTimes(3)

    const signal0 = (fetchMock.mock.calls[0]?.[1] as RequestInit).signal
    const signal1 = (fetchMock.mock.calls[1]?.[1] as RequestInit).signal
    const signal2 = (fetchMock.mock.calls[2]?.[1] as RequestInit).signal

    expect(signal0?.aborted).toBe(false)
    expect(signal1?.aborted).toBe(false)
    expect(signal2?.aborted).toBe(false)

    wrapper.unmount()

    expect(signal0?.aborted).toBe(true)
    expect(signal1?.aborted).toBe(true)
    expect(signal2?.aborted).toBe(true)
  })

  it('refresh button dispatches new requests for all three lotteries', async () => {
    fetchMock.mockImplementation((input) => Promise.resolve(routeMockByUrl(String(input))))
    const wrapper = mount(DrawPeriodOverview)
    await flushPromises()

    expect(fetchMock).toHaveBeenCalledTimes(3)

    fetchMock.mockClear()
    await wrapper.get('[data-testid="refresh-overview"]').trigger('click')
    await flushPromises()

    expect(fetchMock).toHaveBeenCalledTimes(3)
    const drawCalls = fetchMock.mock.calls
      .map((call) => new URL(String(call[0]), 'http://localhost'))
      .filter((url) => url.pathname === '/api/v1/draws')
    expect(drawCalls).toHaveLength(3)

    wrapper.unmount()
  })

  it('AC9: DataOperationsPage renders DrawPeriodOverview alongside legacy batch upload & sync controls', async () => {
    fetchMock.mockImplementation((input) => Promise.resolve(routeMockByUrl(String(input))))
    const wrapper = mount(DataOperationsPage)
    await flushPromises()

    // Draw Period Overview is present with 3 cards
    expect(wrapper.find('[data-testid="draw-period-overview"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="period-card-B649"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="period-card-P638"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="period-card-T539"]').exists()).toBe(true)

    // Original file upload & batch preview controls remain
    expect(wrapper.find('[data-testid="csv-file"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="cancel-batch"]').exists()).toBe(true)

    // Original metrics remain
    expect(wrapper.text()).toContain('Files Selected')
    expect(wrapper.text()).toContain('Discovered Rows')
    expect(wrapper.find('[data-testid="metric-duplicates-conflicts"]').exists()).toBe(true)

    // Automation draw sync controls remain
    expect(wrapper.find('[data-testid="manual-sync"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="scheduled-sync"]').exists()).toBe(true)

    // Recent ingestion runs audit table remain
    expect(wrapper.find('[data-testid="ingestion-run-filter"]').exists()).toBe(true)

    wrapper.unmount()
  })
})
