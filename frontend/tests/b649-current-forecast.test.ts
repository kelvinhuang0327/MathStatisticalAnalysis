// @vitest-environment jsdom

import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import App from '../src/App.vue'
import {
  B649CanonicalForecastRequestError,
  fetchB649CanonicalForecast,
} from '../src/api/b649CanonicalForecast'
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

function ticketNumbers(index: number) {
  if (index === 0) return [49, 1, 11, 21, 31, 41]
  if (index === 1) return [21, 2, 12, 22, 32, 42]
  return [20, 0, 40, 10, 30, 5].map((offset) => ((index + offset) % 49) + 1)
}

function ticketsInApiOrder(count: number) {
  return Array.from({ length: count }, (_, index) =>
    ticket(index + 1, ticketNumbers(index)),
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
    consensus_numbers: [49, 1, 11, 21, 31, 41],
    source_stream_count: 11,
    k5_tickets: ticketsInApiOrder(5),
    k10_tickets: ticketsInApiOrder(10),
    k20_tickets: ticketsInApiOrder(20),
    forecast_actual_sha256: 'a'.repeat(64),
    forecast_method_id: 'B649_11_STREAM_EQUAL_WEIGHT_NUMBER_CONSENSUS',
    forecast_method_version: '1.0.0',
    portfolio_actual_sha256: 'b'.repeat(64),
    portfolio_method_id: 'B649_SEALED_GEOMETRY_PORTFOLIO',
    portfolio_method_version: '8.0.0',
  }
}

type ForecastFixture = ReturnType<typeof currentForecast>
type ForecastMutation = (payload: ForecastFixture) => void

const malformedNumberCases = [
  ['zero', [0, 2, 3, 4, 5, 6]],
  ['above the official range', [50, 2, 3, 4, 5, 6]],
  ['negative', [-1, 2, 3, 4, 5, 6]],
  ['fractional', [1.5, 2, 3, 4, 5, 6]],
  ['unsafe integer', [Number.MAX_SAFE_INTEGER + 1, 2, 3, 4, 5, 6]],
  ['duplicate number', [1, 1, 3, 4, 5, 6]],
] as const

const numberTargets = [
  {
    name: 'ticket',
    set(payload: ForecastFixture, numbers: number[]) {
      payload.k5_tickets[0].predicted_numbers = numbers
    },
  },
  {
    name: 'consensus',
    set(payload: ForecastFixture, numbers: number[]) {
      payload.consensus_numbers = numbers
    },
  },
] as const

const invalidNumberMutations = numberTargets.flatMap((target) =>
  malformedNumberCases.map(([reason, numbers]) => ({
    name: `${target.name}: ${reason}`,
    mutate: (payload: ForecastFixture) => target.set(payload, [...numbers]),
  })),
)

const malformedContractMutations: Array<{ name: string; mutate: ForecastMutation }> = [
  ...[3, 5, 7].map((length) => ({
    name: `ticket with ${length} numbers`,
    mutate: (payload: ForecastFixture) => {
      payload.k5_tickets[0].predicted_numbers = Array.from(
        { length },
        (_, index) => index + 1,
      )
    },
  })),
  {
    name: 'duplicate ticket position',
    mutate: (payload) => {
      payload.k5_tickets[1].ticket_position = 1
    },
  },
  {
    name: 'skipped ticket position',
    mutate: (payload) => {
      payload.k5_tickets[1].ticket_position = 3
    },
  },
  {
    name: 'out-of-order ticket positions',
    mutate: (payload) => {
      payload.k5_tickets[0].ticket_position = 2
      payload.k5_tickets[1].ticket_position = 1
    },
  },
  ...[5, 7].map((length) => ({
    name: `consensus with ${length} numbers`,
    mutate: (payload: ForecastFixture) => {
      payload.consensus_numbers = Array.from({ length }, (_, index) => index + 1)
    },
  })),
  {
    name: 'wrong source stream count',
    mutate: (payload) => {
      payload.source_stream_count = 10
    },
  },
  {
    name: 'too many source streams',
    mutate: (payload) => {
      payload.source_stream_count = 12
    },
  },
  {
    name: 'wrong forecast method id',
    mutate: (payload) => {
      payload.forecast_method_id = 'OTHER_METHOD'
    },
  },
  {
    name: 'wrong forecast method version',
    mutate: (payload) => {
      payload.forecast_method_version = '2.0.0'
    },
  },
  {
    name: 'wrong portfolio method id',
    mutate: (payload) => {
      payload.portfolio_method_id = 'OTHER_PORTFOLIO'
    },
  },
  {
    name: 'wrong portfolio method version',
    mutate: (payload) => {
      payload.portfolio_method_version = '7.0.0'
    },
  },
]

async function expectMalformedResponse(payload: unknown) {
  fetchMock.mockResolvedValueOnce(apiResponse(payload))
  await expect(fetchB649CanonicalForecast()).rejects.toMatchObject({
    name: 'B649CanonicalForecastRequestError',
    kind: 'MALFORMED_RESPONSE',
    status: 200,
  } satisfies Partial<B649CanonicalForecastRequestError>)
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
    expect(wrapper.text()).toContain('版本 8.0.0')
    expect(wrapper.text()).toContain('這些票券組合來自目前排程器權威')
    expect(wrapper.text()).toContain('已驗證的預測樣本外（OOS）提升')
    expect(wrapper.text()).not.toMatch(/較會中|最佳|高信心/)
    expect(wrapper.text()).not.toMatch(/\bK[23]\b/)
  })

  it.each(invalidNumberMutations)(
    'rejects invalid $name numbers in an HTTP 200 response',
    async ({ mutate }) => {
      const payload = currentForecast()
      mutate(payload)
      await expectMalformedResponse(payload)
    },
  )

  it.each(malformedContractMutations)(
    'rejects a response with $name',
    async ({ mutate }) => {
      const payload = currentForecast()
      mutate(payload)
      await expectMalformedResponse(payload)
    },
  )

  it('accepts an exact legal contract without changing number or ticket order', async () => {
    const payload = currentForecast()
    fetchMock.mockResolvedValueOnce(apiResponse(payload))

    await expect(fetchB649CanonicalForecast()).resolves.toBe(payload)
    expect(payload.k5_tickets.map((item) => item.ticket_position)).toEqual([1, 2, 3, 4, 5])
    expect(payload.k10_tickets.map((item) => item.ticket_position)).toEqual(
      Array.from({ length: 10 }, (_, index) => index + 1),
    )
    expect(payload.k20_tickets.map((item) => item.ticket_position)).toEqual(
      Array.from({ length: 20 }, (_, index) => index + 1),
    )
    expect(payload.k5_tickets[0].predicted_numbers).toEqual([49, 1, 11, 21, 31, 41])
    expect(payload.k5_tickets[1].predicted_numbers).toContain(21)
  })

  it('propagates AbortError without translating it to a network error', async () => {
    const abortError = new DOMException('Aborted', 'AbortError')
    fetchMock.mockRejectedValueOnce(abortError)

    await expect(fetchB649CanonicalForecast()).rejects.toBe(abortError)
  })

  it('propagates body-consumption AbortError without reclassifying it', async () => {
    const abortError = new DOMException('Aborted', 'AbortError')
    const response = apiResponse(currentForecast())
    response.json = vi.fn().mockRejectedValueOnce(abortError)
    fetchMock.mockResolvedValueOnce(response)

    await expect(fetchB649CanonicalForecast()).rejects.toBe(abortError)
  })

  it('classifies a JSON syntax error during body consumption as malformed response', async () => {
    const response = apiResponse(currentForecast())
    response.json = vi.fn().mockRejectedValueOnce(new SyntaxError('Invalid JSON'))
    fetchMock.mockResolvedValueOnce(response)

    await expect(fetchB649CanonicalForecast()).rejects.toMatchObject({
      name: 'B649CanonicalForecastRequestError',
      kind: 'MALFORMED_RESPONSE',
      status: 200,
    } satisfies Partial<B649CanonicalForecastRequestError>)
  })

  it('classifies a non-abort fetch rejection as a network error', async () => {
    fetchMock.mockRejectedValueOnce(new TypeError('offline'))

    await expect(fetchB649CanonicalForecast()).rejects.toMatchObject({
      name: 'B649CanonicalForecastRequestError',
      kind: 'NETWORK',
      status: 0,
    } satisfies Partial<B649CanonicalForecastRequestError>)
  })

  it('classifies a non-200 response as an HTTP error', async () => {
    fetchMock.mockResolvedValueOnce(apiResponse({ error_code: 'AUTHORITY_UNAVAILABLE' }, 503))

    await expect(fetchB649CanonicalForecast()).rejects.toMatchObject({
      name: 'B649CanonicalForecastRequestError',
      kind: 'HTTP',
      status: 503,
    } satisfies Partial<B649CanonicalForecastRequestError>)
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
