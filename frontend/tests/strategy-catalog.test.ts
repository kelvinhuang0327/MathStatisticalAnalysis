// @vitest-environment jsdom

import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { StrategyView } from '../src/api/strategies'
import StrategyCatalogPage from '../src/features/strategy-catalog/StrategyCatalogPage.vue'

const observationStrategy = {
  strategy_id: 'biglotto_social_wisdom_anti_popularity',
  display_name: '大樂透 Social Wisdom Anti-Popularity',
  version: 'v0.1',
  supported_lottery_types: ['BIG_LOTTO'],
  minimum_history: 1,
  lifecycle_status: 'OBSERVATION',
  executable: false,
} satisfies StrategyView

let fetchMock: ReturnType<typeof vi.fn<typeof fetch>>

function apiResponse(payload: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: vi.fn().mockResolvedValue(payload),
  } as unknown as Response
}

async function mountLoaded(payload: unknown): Promise<VueWrapper> {
  fetchMock.mockResolvedValue(apiResponse(payload))
  const wrapper = mount(StrategyCatalogPage)
  await flushPromises()
  return wrapper
}

beforeEach(() => {
  fetchMock = vi.fn<typeof fetch>()
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('StrategyCatalogPage', () => {
  it('renders a loading state while the request is pending', () => {
    fetchMock.mockReturnValue(new Promise<Response>(() => undefined))
    const wrapper = mount(StrategyCatalogPage)

    expect(wrapper.text()).toContain('Loading catalog metadata…')
    expect(wrapper.get('.catalog__scope strong').text()).toBe('—')
    wrapper.unmount()
  })

  it('renders metadata but no generation action for OBSERVATION payloads', async () => {
    const adversarial = { ...observationStrategy, executable: true } satisfies StrategyView
    const wrapper = await mountLoaded([adversarial])

    expect(fetchMock).toHaveBeenCalledWith('/api/v1/strategies', expect.any(Object))
    expect(wrapper.text()).toContain(adversarial.display_name)
    expect(wrapper.text()).toContain(adversarial.strategy_id)
    expect(wrapper.text()).toContain('Metadata only')
    expect(wrapper.text()).toContain('Unavailable')
    expect(wrapper.findAll('button')).toHaveLength(0)
    expect(wrapper.findAll('a')).toHaveLength(0)
    wrapper.unmount()
  })

  it('renders an explicit zero count for an empty catalog', async () => {
    const wrapper = await mountLoaded([])

    expect(wrapper.text()).toContain('No strategies are available')
    expect(wrapper.get('.catalog__scope strong').text()).toBe('0')
    wrapper.unmount()
  })

  it('rejects malformed successful records into the recoverable error state', async () => {
    const wrapper = await mountLoaded([{}])

    expect(wrapper.text()).toContain('invalid record at index 0')
    expect(wrapper.findAll('.strategy-card')).toHaveLength(0)
    expect(wrapper.get('button').text()).toBe('Retry')
    wrapper.unmount()
  })

  it('retries an HTTP failure and reaches the populated state', async () => {
    fetchMock
      .mockResolvedValueOnce(apiResponse({ detail: 'unavailable' }, 503))
      .mockResolvedValueOnce(apiResponse([observationStrategy]))
    const wrapper = mount(StrategyCatalogPage)
    await flushPromises()

    expect(wrapper.text()).toContain('HTTP 503')
    await wrapper.get('button').trigger('click')
    await flushPromises()

    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(wrapper.findAll('.strategy-card')).toHaveLength(1)
    expect(wrapper.findAll('button')).toHaveLength(0)
    wrapper.unmount()
  })
})
