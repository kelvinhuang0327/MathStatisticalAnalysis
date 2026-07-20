// @vitest-environment jsdom

import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { LiveZoneSplitBetsResponse } from '../src/api/liveZoneSplitBets'
import App from '../src/App.vue'
import LiveZoneSplitBetsPage from '../src/features/live-zone-split-bets/LiveZoneSplitBetsPage.vue'

let fetchMock: ReturnType<typeof vi.fn<typeof fetch>>

function apiResponse(payload: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: vi.fn().mockResolvedValue(payload),
  } as unknown as Response
}

function okResponse(
  overrides: Partial<LiveZoneSplitBetsResponse> = {},
): LiveZoneSplitBetsResponse {
  return {
    status: 'OK',
    bets: [
      [1, 2, 3, 4, 5, 6],
      [7, 8, 9, 10, 11, 12],
    ],
    coverage_rate: 0.42,
    total_unique_numbers: 20,
    method: 'zone_split',
    philosophy: 'diversify across zones',
    reason_code: null,
    ...overrides,
  }
}

function deferred<T>(): {
  promise: Promise<T>
  resolve: (value: T | PromiseLike<T>) => void
} {
  let resolve!: (value: T | PromiseLike<T>) => void
  const promise = new Promise<T>((resolver) => {
    resolve = resolver
  })
  return { promise, resolve }
}

beforeEach(() => {
  fetchMock = vi.fn<typeof fetch>()
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  vi.unstubAllGlobals()
  window.location.hash = ''
})

describe('LiveZoneSplitBetsPage', () => {
  it('makes no request on mount', () => {
    const wrapper = mount(LiveZoneSplitBetsPage)
    expect(fetchMock).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('sends exactly num_bets on a valid submission', async () => {
    fetchMock.mockResolvedValue(apiResponse(okResponse()))
    const wrapper = mount(LiveZoneSplitBetsPage)

    await wrapper.get('input[name="num_bets"]').setValue(5)
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [url, init] = fetchMock.mock.calls[0]!
    expect(url).toBe('/api/v1/live-zone-split-bets')
    expect(init?.method).toBe('POST')
    expect(init?.headers).toMatchObject({ 'Content-Type': 'application/json' })
    expect(JSON.parse(String(init?.body))).toEqual({ num_bets: 5 })
    wrapper.unmount()
  })

  it('renders bets[0] as the primary bet on success', async () => {
    fetchMock.mockResolvedValue(apiResponse(okResponse()))
    const wrapper = mount(LiveZoneSplitBetsPage)
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    const primary = wrapper.get('.primary-bet')
    expect(primary.findAll('.number-chip').map((chip) => chip.text())).toEqual([
      '1',
      '2',
      '3',
      '4',
      '5',
      '6',
    ])
    wrapper.unmount()
  })

  it('renders every bet and all metadata on success', async () => {
    const payload = okResponse()
    fetchMock.mockResolvedValue(apiResponse(payload))
    const wrapper = mount(LiveZoneSplitBetsPage)
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.findAll('.all-bets li')).toHaveLength(payload.bets!.length)
    expect(wrapper.text()).toContain('42.0%')
    expect(wrapper.text()).toContain('20')
    expect(wrapper.text()).toContain('zone_split')
    expect(wrapper.text()).toContain('diversify across zones')
    wrapper.unmount()
  })

  it('treats INVALID_REQUEST as an HTTP-200 application failure, not a transport exception', async () => {
    fetchMock.mockResolvedValue(
      apiResponse({
        status: 'INVALID_REQUEST',
        bets: null,
        coverage_rate: null,
        total_unique_numbers: null,
        method: null,
        philosophy: null,
        reason_code: 'INVALID_NUM_BETS',
      }),
    )
    const wrapper = mount(LiveZoneSplitBetsPage)
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.find('.state-panel--error').exists()).toBe(false)
    expect(wrapper.get('.state-panel--warning').text()).toContain('Request rejected')
    expect(wrapper.text()).toContain('INVALID_NUM_BETS')
    wrapper.unmount()
  })

  it('handles INVALID_OUTPUT deterministically', async () => {
    fetchMock.mockResolvedValue(
      apiResponse({
        status: 'INVALID_OUTPUT',
        bets: null,
        coverage_rate: null,
        total_unique_numbers: null,
        method: null,
        philosophy: null,
        reason_code: 'MALFORMED_OUTPUT',
      }),
    )
    const wrapper = mount(LiveZoneSplitBetsPage)
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.find('.state-panel--error').exists()).toBe(false)
    expect(wrapper.get('.state-panel--warning').text()).toContain('Invalid result')
    wrapper.unmount()
  })

  it('handles EXECUTION_ERROR deterministically', async () => {
    fetchMock.mockResolvedValue(
      apiResponse({
        status: 'EXECUTION_ERROR',
        bets: null,
        coverage_rate: null,
        total_unique_numbers: null,
        method: null,
        philosophy: null,
        reason_code: 'EXECUTION_ERROR',
      }),
    )
    const wrapper = mount(LiveZoneSplitBetsPage)
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.find('.state-panel--error').exists()).toBe(false)
    expect(wrapper.get('.state-panel--warning').text()).toContain('Execution failed')
    wrapper.unmount()
  })

  it('handles a sanitized HTTP 422 separately from application statuses', async () => {
    fetchMock.mockResolvedValue(
      apiResponse(
        { error_code: 'VALIDATION_ERROR', message: 'num_bets must be an integer from server' },
        422,
      ),
    )
    const wrapper = mount(LiveZoneSplitBetsPage)
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    const errorText = wrapper.get('.state-panel--error').text()
    expect(errorText).not.toContain('num_bets must be an integer from server')
    expect(errorText).toContain('rejected the request as invalid')
    wrapper.unmount()
  })

  it('handles a network failure separately, without leaking raw exception text', async () => {
    fetchMock.mockRejectedValue(new TypeError('Failed to fetch'))
    const wrapper = mount(LiveZoneSplitBetsPage)
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    const errorText = wrapper.get('.state-panel--error').text()
    expect(errorText).not.toContain('Failed to fetch')
    expect(errorText).toContain('failed before a response was received')
    wrapper.unmount()
  })

  it('aborts a stale in-flight request when a new submission starts', async () => {
    const first = deferred<Response>()
    const second = deferred<Response>()
    fetchMock.mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise)
    const wrapper = mount(LiveZoneSplitBetsPage)

    await wrapper.get('form').trigger('submit')
    const firstSignal = fetchMock.mock.calls[0]?.[1]?.signal as AbortSignal
    expect(firstSignal.aborted).toBe(false)

    await wrapper.get('input[name="num_bets"]').setValue(7)
    await wrapper.get('form').trigger('submit')
    expect(firstSignal.aborted).toBe(true)

    second.resolve(apiResponse(okResponse({ method: 'second' })))
    await flushPromises()
    expect(wrapper.text()).toContain('second')

    first.resolve(apiResponse(okResponse({ method: 'stale' })))
    await flushPromises()
    expect(wrapper.text()).not.toContain('stale')
    wrapper.unmount()
  })

  it('aborts the active request when the component unmounts', async () => {
    fetchMock.mockReturnValue(new Promise<Response>(() => undefined))
    const wrapper = mount(LiveZoneSplitBetsPage)
    await wrapper.get('form').trigger('submit')

    const signal = fetchMock.mock.calls[0]?.[1]?.signal as AbortSignal
    expect(signal.aborted).toBe(false)
    wrapper.unmount()
    expect(signal.aborted).toBe(true)
  })

  it('does not call fetch for an invalid local num_bets value', async () => {
    const wrapper = mount(LiveZoneSplitBetsPage)

    await wrapper.get('input[name="num_bets"]').setValue(0)
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(fetchMock).not.toHaveBeenCalled()

    await wrapper.get('input[name="num_bets"]').setValue(11)
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(fetchMock).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('renders the page at the App hash route', async () => {
    window.location.hash = '#/live-zone-split-bets'
    fetchMock.mockResolvedValue(apiResponse(okResponse()))
    const wrapper = mount(App)
    await flushPromises()

    expect(wrapper.find('#live-zone-split-bets-title').exists()).toBe(true)
    wrapper.unmount()
  })

  it('never sends lottery_type, history, seed, strategy_id, or sampler', async () => {
    fetchMock.mockResolvedValue(apiResponse(okResponse()))
    const wrapper = mount(LiveZoneSplitBetsPage)
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    const body = JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body))
    expect(Object.keys(body)).toEqual(['num_bets'])
    expect(body).not.toHaveProperty('lottery_type')
    expect(body).not.toHaveProperty('history')
    expect(body).not.toHaveProperty('seed')
    expect(body).not.toHaveProperty('strategy_id')
    expect(body).not.toHaveProperty('sampler')
    wrapper.unmount()
  })
})
