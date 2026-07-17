// @vitest-environment jsdom

import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type {
  StrategyOverviewItem,
  StrategyOverviewResponse,
} from '../src/api/strategies'
import StrategyCatalogPage from '../src/features/strategy-catalog/StrategyCatalogPage.vue'

const observationStrategy = {
  strategy_id: 'biglotto_social_wisdom_anti_popularity',
  display_name: '大樂透 Social Wisdom Anti-Popularity',
  version: 'v0.1',
  supported_lottery_types: ['BIG_LOTTO'],
  minimum_history: 1,
  lifecycle_status: 'OBSERVATION',
  executable: false,
  provenance: [
    'legacy_commit:520c3922a7c8f47e5b6196fb4b0d54716fa5fd9f',
    'migration_task:P600B_R2',
  ],
} satisfies StrategyOverviewItem

const lifecycleStatuses = ['IDEA', 'OBSERVATION', 'ONLINE', 'REJECTED', 'RETIRED'] as const
const lotteryTypes = ['DAILY_539', 'BIG_LOTTO', 'POWER_LOTTO'] as const

let fetchMock: ReturnType<typeof vi.fn<typeof fetch>>

function makeOverview(
  items: StrategyOverviewItem[] = [observationStrategy],
): StrategyOverviewResponse {
  const lifecycleCounts: Record<string, number> = Object.fromEntries(
    lifecycleStatuses.map((status) => [status, 0]),
  )
  const lotteryTypeCounts: Record<string, number> = Object.fromEntries(
    lotteryTypes.map((lotteryType) => [lotteryType, 0]),
  )
  for (const item of items) {
    lifecycleCounts[item.lifecycle_status] += 1
    for (const lotteryType of item.supported_lottery_types) lotteryTypeCounts[lotteryType] += 1
  }
  const executableCount = items.filter((item) => item.executable).length
  return {
    items,
    summary: {
      total: items.length,
      executable_count: executableCount,
      metadata_only_count: items.length - executableCount,
      lifecycle_counts: lifecycleCounts,
      lottery_type_counts: lotteryTypeCounts,
    },
    capabilities: {
      evaluation_metrics_available: false,
      d3_status_available: false,
      best_strategy_ranking_available: false,
      unavailable_reason_codes: ['NO_CANONICAL_STRATEGY_EVALUATION_EVIDENCE'],
    },
  }
}

function apiResponse(payload: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: vi.fn().mockResolvedValue(payload),
  } as unknown as Response
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

async function mountLoaded(
  payload: StrategyOverviewResponse = makeOverview(),
): Promise<VueWrapper> {
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
  it('loads the Strategy Overview endpoint and renders deterministic cards', async () => {
    const wrapper = await mountLoaded()

    expect(fetchMock).toHaveBeenCalledWith('/api/v1/strategy-overview', expect.any(Object))
    expect(wrapper.get('#strategy-catalog-title').text()).toBe('Strategy Overview')
    expect(wrapper.findAll('.strategy-card')).toHaveLength(1)
    expect(wrapper.text()).toContain(observationStrategy.display_name)
    expect(wrapper.text()).toContain(observationStrategy.strategy_id)
    wrapper.unmount()
  })

  it('renders a loading state while the initial request is pending', () => {
    fetchMock.mockReturnValue(new Promise<Response>(() => undefined))
    const wrapper = mount(StrategyCatalogPage)

    expect(wrapper.text()).toContain('Loading Strategy Overview…')
    expect(wrapper.get('.catalog__scope strong').text()).toBe('—')
    wrapper.unmount()
  })

  it('maps text and all filters to bounded query parameters', async () => {
    const wrapper = await mountLoaded()
    fetchMock.mockClear()
    fetchMock.mockResolvedValue(apiResponse(makeOverview()))

    await wrapper.get('input[name="q"]').setValue('  Social Wisdom  ')
    await wrapper.get('select[name="lottery_type"]').setValue('BIG_LOTTO')
    await wrapper.get('select[name="lifecycle_status"]').setValue('OBSERVATION')
    await wrapper.get('select[name="executable"]').setValue('false')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    const lastRequest = fetchMock.mock.calls.at(-1)?.[0]
    const url = new URL(String(lastRequest), 'http://localhost')
    expect(url.pathname).toBe('/api/v1/strategy-overview')
    expect(Object.fromEntries(url.searchParams)).toEqual({
      q: 'Social Wisdom',
      lottery_type: 'BIG_LOTTO',
      lifecycle_status: 'OBSERVATION',
      executable: 'false',
    })
    wrapper.unmount()
  })

  it('resets every filter and reloads the unfiltered endpoint', async () => {
    const wrapper = await mountLoaded()
    fetchMock.mockClear()
    fetchMock.mockResolvedValue(apiResponse(makeOverview()))

    await wrapper.get('input[name="q"]').setValue('social')
    await wrapper.get('select[name="lifecycle_status"]').setValue('OBSERVATION')
    await wrapper.get('.strategy-filter-reset').trigger('click')
    await flushPromises()

    expect((wrapper.get('input[name="q"]').element as HTMLInputElement).value).toBe('')
    expect(
      (wrapper.get('select[name="lifecycle_status"]').element as HTMLSelectElement).value,
    ).toBe('')
    expect(fetchMock.mock.calls.at(-1)?.[0]).toBe('/api/v1/strategy-overview')
    wrapper.unmount()
  })

  it('renders returned-result and lifecycle summaries', async () => {
    const wrapper = await mountLoaded()

    expect(wrapper.findAll('.strategy-summary__metrics dd').map((node) => node.text())).toEqual([
      '1',
      '0',
      '1',
    ])
    const lifecycleEntries = wrapper.findAll('.lifecycle-summary li').map((item) =>
      item
        .findAll('span, strong')
        .map((node) => node.text())
        .join(':'),
    )
    expect(lifecycleEntries).toContain('OBSERVATION:1')
    expect(lifecycleEntries).toContain('ONLINE:0')
    wrapper.unmount()
  })

  it('renders descriptor provenance through normal Vue interpolation', async () => {
    const wrapper = await mountLoaded()

    expect(wrapper.get('.strategy-card__provenance summary').text()).toBe('Provenance (2)')
    expect(wrapper.text()).toContain(observationStrategy.provenance[0])
    expect(wrapper.text()).toContain(observationStrategy.provenance[1])
    expect(wrapper.html()).not.toContain('v-html')
    wrapper.unmount()
  })

  it('states every unavailable evidence capability and its reason', async () => {
    const wrapper = await mountLoaded()
    const evidence = wrapper.get('.evidence-panel').text()

    expect(evidence).toContain('No canonical evaluation metrics are currently registered.')
    expect(evidence).toContain('D3 status is not yet available.')
    expect(evidence).toContain('Best-strategy ranking is not yet available.')
    expect(evidence).toContain('must not be interpreted as quality')
    expect(evidence).toContain('NO_CANONICAL_STRATEGY_EVALUATION_EVIDENCE')
    wrapper.unmount()
  })

  it('distinguishes a filtered-empty result from an empty catalog', async () => {
    fetchMock
      .mockResolvedValueOnce(apiResponse(makeOverview()))
      .mockResolvedValueOnce(apiResponse(makeOverview([])))
    const wrapper = mount(StrategyCatalogPage)
    await flushPromises()

    await wrapper.get('input[name="q"]').setValue('not-present')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.text()).toContain('No strategies match the current filters.')
    expect(wrapper.text()).not.toContain('No strategies are available in the canonical')
    expect(wrapper.findAll('.strategy-card')).toHaveLength(0)
    expect(wrapper.find('.evidence-panel').exists()).toBe(true)
    wrapper.unmount()
  })

  it('renders a catalog-empty state for an unfiltered empty response', async () => {
    const wrapper = await mountLoaded(makeOverview([]))

    expect(wrapper.text()).toContain('No strategies are available in the canonical Strategy Catalog.')
    expect(wrapper.get('.catalog__scope strong').text()).toBe('0')
    wrapper.unmount()
  })

  it('retries an HTTP failure and reaches the populated state', async () => {
    fetchMock
      .mockResolvedValueOnce(apiResponse({ detail: 'unavailable' }, 503))
      .mockResolvedValueOnce(apiResponse(makeOverview()))
    const wrapper = mount(StrategyCatalogPage)
    await flushPromises()

    expect(wrapper.text()).toContain('HTTP 503')
    await wrapper.get('.catalog__retry').trigger('click')
    await flushPromises()

    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(wrapper.findAll('.strategy-card')).toHaveLength(1)
    wrapper.unmount()
  })

  it('prevents an older response from overwriting newer filters', async () => {
    const older = deferred<Response>()
    const newer = deferred<Response>()
    const newerStrategy = {
      ...observationStrategy,
      strategy_id: 'newer_filtered_strategy',
      display_name: 'Newer Filtered Strategy',
    }
    fetchMock.mockReturnValueOnce(older.promise).mockReturnValueOnce(newer.promise)
    const wrapper = mount(StrategyCatalogPage)

    await wrapper.get('select[name="lottery_type"]').setValue('BIG_LOTTO')
    expect((fetchMock.mock.calls[0]?.[1]?.signal as AbortSignal).aborted).toBe(true)
    newer.resolve(apiResponse(makeOverview([newerStrategy])))
    await flushPromises()
    expect(wrapper.text()).toContain('Newer Filtered Strategy')

    older.resolve(apiResponse(makeOverview()))
    await flushPromises()
    expect(wrapper.text()).toContain('Newer Filtered Strategy')
    expect(wrapper.text()).not.toContain(observationStrategy.display_name)
    wrapper.unmount()
  })

  it('aborts the pending request when unmounted', () => {
    fetchMock.mockReturnValue(new Promise<Response>(() => undefined))
    const wrapper = mount(StrategyCatalogPage)
    const signal = fetchMock.mock.calls[0]?.[1]?.signal as AbortSignal

    expect(signal.aborted).toBe(false)
    wrapper.unmount()
    expect(signal.aborted).toBe(true)
  })

  it('renders no fabricated result or execution controls', async () => {
    const wrapper = await mountLoaded()
    const text = wrapper.text()
    const buttonLabels = wrapper.findAll('button').map((button) => button.text()).join(' ')

    expect(text).not.toContain('Best strategy')
    expect(text).not.toMatch(/\bD3\s*[:=]\s*\d/i)
    expect(text).not.toMatch(/\d+(?:\.\d+)?%/)
    expect(text).not.toContain('Hit rate')
    expect(buttonLabels).not.toMatch(/run|evaluate|predict|generate/i)
    expect(wrapper.findAll('canvas')).toHaveLength(0)
    expect(wrapper.findAll('svg')).toHaveLength(0)
    wrapper.unmount()
  })
})
