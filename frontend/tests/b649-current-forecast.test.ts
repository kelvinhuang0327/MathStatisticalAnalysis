// @vitest-environment jsdom

import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import App from '../src/App.vue'
import B649CurrentForecastPage from '../src/features/b649-current-forecast/B649CurrentForecastPage.vue'

function apiResponse(payload: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: vi.fn().mockResolvedValue(payload),
  } as unknown as Response
}

function ticket(ticket_position: number, predicted_numbers: number[]) {
  return { ticket_position, predicted_numbers }
}

function ticketsInApiOrder(positions: number[]) {
  return positions.map((position, index) =>
    ticket(position, [index + 1, index + 2, index + 3, index + 4, index + 5, index + 6]),
  )
}

function currentForecast() {
  return {
    status: 'AVAILABLE',
    authority: 'SCHEDULER_ARTIFACT',
    current_target: {
      draw_number: '115000099',
      draw_date: '2099-10-03',
      scheduled_at: '2099-10-03T20:30:00+08:00',
    },
    consensus_numbers: [4, 12, 23, 26, 29],
    source_stream_count: 11,
    k5_tickets: ticketsInApiOrder([9, 2, 5, 1, 4]),
    k10_tickets: ticketsInApiOrder([7, 3, 10, 1, 6, 9, 4, 2, 8, 5]),
    k20_tickets: ticketsInApiOrder([
      6, 1, 19, 2, 18, 3, 17, 4, 16, 5, 15, 7, 14, 8, 13, 9, 12, 10, 11, 20,
    ]),
    forecast_actual_sha256: 'a'.repeat(64),
    forecast_method_id: 'B649_11_STREAM_EQUAL_WEIGHT_NUMBER_CONSENSUS',
    forecast_method_version: '1.0.0',
    portfolio_actual_sha256: 'b'.repeat(64),
    portfolio_method_id: 'B649_SEALED_GEOMETRY_PORTFOLIO',
    portfolio_method_version: '1.0.0',
  }
}

function ticketRows(wrapper: ReturnType<typeof mount>) {
  return wrapper.findAll('[data-testid="b649-ticket-row"]').map((row) => {
    const tableNumbers = row.find('[data-testid="b649-ticket-numbers"]')
    const ballNumbers = row.findAll('.ball__value').map((ball) => ball.text())
    return {
      position: row.get('[data-testid="b649-ticket-position"]').text(),
      numbers: tableNumbers.exists() ? tableNumbers.text() : ballNumbers.join(' · '),
    }
  })
}

function expectedRows(tickets: ReturnType<typeof ticketsInApiOrder>) {
  return tickets.map((item) => ({
    position: '票券 ' + item.ticket_position,
    numbers: item.predicted_numbers.join(' · '),
  }))
}

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((resolvePromise) => {
    resolve = resolvePromise
  })
  return { promise, resolve }
}

let fetchMock: ReturnType<typeof vi.fn<typeof fetch>>
let restoreClipboard: (() => void) | null = null

function stubClipboard(implementation?: (text: string) => Promise<void>) {
  const original = Object.getOwnPropertyDescriptor(navigator, 'clipboard')
  const writeText = vi.fn<(text: string) => Promise<void>>()
  if (implementation) writeText.mockImplementation(implementation)
  else writeText.mockResolvedValue(undefined)

  Object.defineProperty(navigator, 'clipboard', {
    configurable: true,
    value: { writeText },
  })
  restoreClipboard = () => {
    if (original) Object.defineProperty(navigator, 'clipboard', original)
    else Reflect.deleteProperty(navigator, 'clipboard')
    restoreClipboard = null
  }

  return writeText
}

beforeEach(() => {
  fetchMock = vi.fn<typeof fetch>().mockResolvedValue(apiResponse(currentForecast()))
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  restoreClipboard?.()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('B649 current forecast', () => {
  it('shows exact API target and provenance and preserves K ticket order in both views', async () => {
    const payload = currentForecast()
    fetchMock.mockResolvedValueOnce(apiResponse(payload))
    const wrapper = mount(B649CurrentForecastPage)
    await flushPromises()

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/b649/canonical-forecast/current',
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    )
    expect(wrapper.text()).toContain('115000099')
    expect(wrapper.text()).toContain('2099-10-03')
    expect(wrapper.get('time').attributes('datetime')).toBe('2099-10-03T20:30:00+08:00')
    expect(wrapper.text()).toContain('資料生成時間未提供')
    expect(wrapper.get('[data-testid="b649-size-k5"]').attributes('aria-pressed')).toBe('true')
    expect(ticketRows(wrapper)).toEqual(expectedRows(payload.k5_tickets))

    for (const [size, key] of [
      [5, 'k5_tickets'],
      [10, 'k10_tickets'],
      [20, 'k20_tickets'],
    ] as const) {
      await wrapper.get('[data-testid="b649-size-k' + size + '"]').trigger('click')
      await flushPromises()
      expect(wrapper.get('[data-testid="b649-size-k' + size + '"]').attributes('aria-pressed')).toBe('true')
      expect(ticketRows(wrapper)).toEqual(expectedRows(payload[key]))
    }

    const ballRows = ticketRows(wrapper)
    await wrapper.get('[data-testid="b649-display-table"]').trigger('click')
    await flushPromises()
    expect(wrapper.find('table').exists()).toBe(true)
    expect(ticketRows(wrapper)).toEqual(ballRows)
    await wrapper.get('[data-testid="b649-display-balls"]').trigger('click')
    await flushPromises()
    expect(ticketRows(wrapper)).toEqual(ballRows)

    await wrapper.get('summary').trigger('click')
    expect(wrapper.text()).toContain('SCHEDULER_ARTIFACT')
    expect(wrapper.text()).toContain('B649_11_STREAM_EQUAL_WEIGHT_NUMBER_CONSENSUS')
    expect(wrapper.text()).toContain('B649_SEALED_GEOMETRY_PORTFOLIO')
    expect(wrapper.text()).toContain('版本 1.0.0')
    expect(wrapper.text()).toContain('a'.repeat(64))
    expect(wrapper.text()).toContain('b'.repeat(64))
    expect(wrapper.text()).toContain('這些票券組合來自目前排程器權威')
    expect(wrapper.text()).toContain('尚無可驗證的三策略單注選號資料')
    expect(wrapper.text()).toContain('不會以 K5 前三注代替')
    expect(wrapper.text()).not.toMatch(/較會中|高信心/)
    expect(wrapper.text()).not.toMatch(/\bK[23]\b/)
  })

  it('copies one API ticket and the selected K portfolio with target and position', async () => {
    const payload = currentForecast()
    const writeText = stubClipboard()
    fetchMock.mockResolvedValueOnce(apiResponse(payload))
    const wrapper = mount(B649CurrentForecastPage)
    await flushPromises()

    await wrapper.get('[data-testid="b649-copy-ticket-9"]').trigger('click')
    await flushPromises()
    expect(writeText).toHaveBeenCalledWith(
      'B649 第 115000099 期\n票券 9：1 2 3 4 5 6',
    )
    expect(wrapper.get('[role="status"]').text()).toContain('已複製票券 9')

    await wrapper.get('[data-testid="b649-size-k10"]').trigger('click')
    await wrapper.get('[data-testid="b649-copy-portfolio"]').trigger('click')
    await flushPromises()
    const expectedCopy = [
      'B649 第 115000099 期 K10 組合',
      ...payload.k10_tickets.map(
        (item) => '票券 ' + item.ticket_position + '：' + item.predicted_numbers.join(' '),
      ),
    ].join('\n')
    expect(writeText).toHaveBeenLastCalledWith(expectedCopy)
    expect(expectedCopy.split('\n')).toHaveLength(11)
    expect(wrapper.get('[role="status"]').text()).toContain('已複製K10 組合')
  })

  it('shows the actual clipboard error and never reports a failed copy as successful', async () => {
    stubClipboard(() => Promise.reject(new Error('NotAllowedError: permission denied')))
    const wrapper = mount(B649CurrentForecastPage)
    await flushPromises()

    await wrapper.get('[data-testid="b649-copy-portfolio"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('[role="alert"]').text()).toContain(
      '複製失敗：NotAllowedError: permission denied',
    )
    expect(wrapper.get('[role="alert"]').text()).not.toContain('已複製')
  })

  it('clears old tickets and shows the HTTP error when the canonical endpoint returns 503', async () => {
    fetchMock
      .mockResolvedValueOnce(apiResponse(currentForecast()))
      .mockResolvedValueOnce(apiResponse({ error_code: 'AUTHORITY_UNAVAILABLE' }, 503))
    const wrapper = mount(B649CurrentForecastPage)
    await flushPromises()
    expect(wrapper.findAll('[data-testid="b649-ticket-row"]')).toHaveLength(5)

    await wrapper.get('.b649-current-forecast__refresh').trigger('click')
    await flushPromises()

    expect(wrapper.get('[role="alert"]').text()).toContain('目前預測暫不可用')
    expect(wrapper.get('[role="alert"]').text()).toContain('HTTP 503')
    expect(wrapper.find('[data-testid="b649-ticket-row"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="b649-copy-portfolio"]').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('115000099')
  })

  it('clears old tickets after a network failure', async () => {
    fetchMock
      .mockResolvedValueOnce(apiResponse(currentForecast()))
      .mockRejectedValueOnce(new TypeError('offline'))
    const wrapper = mount(B649CurrentForecastPage)
    await flushPromises()
    expect(wrapper.findAll('[data-testid="b649-ticket-row"]')).toHaveLength(5)

    await wrapper.get('.b649-current-forecast__refresh').trigger('click')
    await flushPromises()

    expect(wrapper.get('[role="alert"]').text()).toContain('目前預測暫不可用')
    expect(wrapper.get('[role="alert"]').text()).toContain('NETWORK: Network request failed.')
    expect(wrapper.find('[data-testid="b649-ticket-row"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="b649-copy-portfolio"]').exists()).toBe(false)
  })

  it('treats wrong K counts and malformed six-number tickets as unavailable', async () => {
    const invalidCount = currentForecast()
    invalidCount.k10_tickets.pop()
    fetchMock.mockResolvedValueOnce(apiResponse(invalidCount))
    const countWrapper = mount(B649CurrentForecastPage)
    await flushPromises()

    expect(countWrapper.get('[role="alert"]').text()).toContain('目前預測暫不可用')
    expect(countWrapper.find('[data-testid="b649-ticket-row"]').exists()).toBe(false)
    expect(countWrapper.find('[data-testid="b649-copy-portfolio"]').exists()).toBe(false)
    countWrapper.unmount()

    const malformedNumbers = currentForecast()
    malformedNumbers.k5_tickets[0].predicted_numbers.pop()
    fetchMock.mockResolvedValueOnce(apiResponse(malformedNumbers))
    const formatWrapper = mount(B649CurrentForecastPage)
    await flushPromises()

    expect(formatWrapper.get('[role="alert"]').text()).toContain('六個互異的 1–49 號碼')
    expect(formatWrapper.find('[data-testid="b649-ticket-row"]').exists()).toBe(false)
    expect(formatWrapper.find('[data-testid="b649-copy-portfolio"]').exists()).toBe(false)
  })

  it('fails closed on a forecast whose scheduled target has expired', async () => {
    const expired = currentForecast()
    expired.current_target.draw_date = '2020-10-03'
    expired.current_target.scheduled_at = '2020-10-03T20:30:00+08:00'
    fetchMock.mockResolvedValueOnce(apiResponse(expired))
    const wrapper = mount(B649CurrentForecastPage)
    await flushPromises()

    expect(wrapper.get('[role="alert"]').text()).toContain('目標期別已過期')
    expect(wrapper.find('[data-testid="b649-ticket-row"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="b649-copy-portfolio"]').exists()).toBe(false)
  })

  it('does not let a cancelled response overwrite the latest reload', async () => {
    const first = deferred<Response>()
    const latest = currentForecast()
    latest.current_target.draw_number = '115000100'
    let firstSignal: AbortSignal | null = null
    fetchMock.mockImplementationOnce((_input, init) => {
      firstSignal = init?.signal as AbortSignal
      return first.promise
    })
    fetchMock.mockResolvedValueOnce(apiResponse(latest))

    const wrapper = mount(B649CurrentForecastPage)
    await flushPromises()
    await wrapper.get('.b649-current-forecast__refresh').trigger('click')
    await flushPromises()

    expect(firstSignal?.aborted).toBe(true)
    expect(wrapper.text()).toContain('115000100')
    first.resolve(apiResponse(currentForecast()))
    await flushPromises()

    expect(wrapper.text()).toContain('115000100')
    expect(wrapper.text()).not.toContain('115000099')
    expect(ticketRows(wrapper)).toEqual(expectedRows(latest.k5_tickets))
  })

  it('opens as a dedicated B649 current forecast page from navigation', async () => {
    window.location.hash = '#/b649-current-forecast'
    const wrapper = mount(App)
    await flushPromises()

    expect(wrapper.get('h1').text()).toBe('B649 目前預測')
    expect(
      wrapper.get('a[href="#/b649-current-forecast"]').attributes('aria-current'),
    ).toBe('page')
  })
})
