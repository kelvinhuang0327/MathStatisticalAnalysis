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
    ticket(position, [index + 1, index + 11, index + 21]),
  )
}

function currentForecast() {
  return {
    status: 'AVAILABLE',
    authority: 'SCHEDULER_ARTIFACT',
    current_target: {
      draw_number: '115000099',
      draw_date: '2026-10-03',
      scheduled_at: '2026-10-03T20:30:00+08:00',
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

let fetchMock: ReturnType<typeof vi.fn<typeof fetch>>

beforeEach(() => {
  fetchMock = vi.fn<typeof fetch>().mockResolvedValue(apiResponse(currentForecast()))
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('B649 current forecast', () => {
  it('renders the exact current target, authority methods, and ticket order from the API', async () => {
    const payload = currentForecast()
    fetchMock.mockResolvedValueOnce(apiResponse(payload))
    const wrapper = mount(B649CurrentForecastPage)
    await flushPromises()

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/b649/canonical-forecast/current',
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    )
    expect(wrapper.text()).toContain('115000099')
    expect(wrapper.text()).toContain('2026-10-03')
    expect(wrapper.get('time').attributes('datetime')).toBe('2026-10-03T20:30:00+08:00')
    expect(wrapper.text()).toContain('資料生成時間未提供')

    expect(
      wrapper.findAll('.b649-current-forecast__tickets h2').map((heading) => heading.text()),
    ).toEqual(['K5', 'K10', 'K20'])
    expect(payload.status).toBe('AVAILABLE')
    expect(payload.k5_tickets).toHaveLength(5)
    expect(payload.k10_tickets).toHaveLength(10)
    expect(payload.k20_tickets).toHaveLength(20)
    for (const [key, testId] of [
      ['k5_tickets', 'b649-ticket-k5'],
      ['k10_tickets', 'b649-ticket-k10'],
      ['k20_tickets', 'b649-ticket-k20'],
    ] as const) {
      expect(
        wrapper
          .findAll(`[data-testid="${testId}"]`)
          .map((row) => [row.find('span').text(), row.find('strong').text()]),
      ).toEqual(
        payload[key].map((item) => [
          `票券 ${item.ticket_position}`,
          item.predicted_numbers.join(' · '),
        ]),
      )
    }

    expect(wrapper.text()).toContain('B649_11_STREAM_EQUAL_WEIGHT_NUMBER_CONSENSUS')
    expect(wrapper.text()).toContain('B649_SEALED_GEOMETRY_PORTFOLIO')
    expect(wrapper.text()).toContain('版本 1.0.0')
    expect(wrapper.text()).toContain('這些票券組合來自目前排程器權威')
    expect(wrapper.text()).toContain('已驗證的預測樣本外（OOS）提升')
    expect(wrapper.text()).not.toMatch(/較會中|最佳|高信心/)
    expect(wrapper.text()).not.toMatch(/\bK[23]\b/)
  })

  it('clears the previous tickets when the canonical endpoint returns 503', async () => {
    fetchMock
      .mockResolvedValueOnce(apiResponse(currentForecast()))
      .mockResolvedValueOnce(apiResponse({ error_code: 'AUTHORITY_UNAVAILABLE' }, 503))
    const wrapper = mount(B649CurrentForecastPage)
    await flushPromises()
    expect(wrapper.findAll('[data-testid="b649-ticket-k5"]')).toHaveLength(5)

    await wrapper.get('button').trigger('click')
    await flushPromises()

    expect(wrapper.get('[role="alert"]').text()).toContain('目前預測暫不可用')
    expect(wrapper.get('[role="alert"]').text()).toContain('不會顯示舊票券')
    expect(wrapper.find('[data-testid="b649-ticket-k5"]').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('115000099')
  })

  it('clears the previous tickets after a network failure', async () => {
    fetchMock
      .mockResolvedValueOnce(apiResponse(currentForecast()))
      .mockRejectedValueOnce(new TypeError('offline'))
    const wrapper = mount(B649CurrentForecastPage)
    await flushPromises()
    expect(wrapper.findAll('[data-testid="b649-ticket-k10"]')).toHaveLength(10)

    await wrapper.get('button').trigger('click')
    await flushPromises()

    expect(wrapper.get('[role="alert"]').text()).toContain('目前預測暫不可用')
    expect(wrapper.find('[data-testid="b649-ticket-k5"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="b649-ticket-k10"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="b649-ticket-k20"]').exists()).toBe(false)
  })

  it('treats ticket arrays with the wrong K counts as unavailable', async () => {
    const invalidForecast = currentForecast()
    invalidForecast.k10_tickets.pop()
    fetchMock.mockResolvedValueOnce(apiResponse(invalidForecast))
    const wrapper = mount(B649CurrentForecastPage)
    await flushPromises()

    expect(wrapper.get('[role="alert"]').text()).toContain('目前預測暫不可用')
    expect(wrapper.find('[data-testid="b649-ticket-k5"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="b649-ticket-k10"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="b649-ticket-k20"]').exists()).toBe(false)
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
