// @vitest-environment jsdom

import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import App from '../src/App.vue'
import { makeRunPage } from './historical-success-windows-fixtures'

let fetchMock: ReturnType<typeof vi.fn<typeof fetch>>

function apiResponse(payload: unknown): Response {
  return {
    ok: true,
    status: 200,
    json: vi.fn().mockResolvedValue(payload),
  } as unknown as Response
}

beforeEach(() => {
  window.location.hash = '#/strategies'
  fetchMock = vi.fn<typeof fetch>().mockImplementation((input) => {
    const url = String(input)
    if (url.includes('/api/v1/strategy-overview')) {
      return Promise.resolve(
        apiResponse({
          items: [
            {
              strategy_id: 'biglotto_social_wisdom_anti_popularity',
              display_name: 'Strategy fixture',
              version: 'v0.1',
              supported_lottery_types: ['BIG_LOTTO'],
              minimum_history: 1,
              lifecycle_status: 'OBSERVATION',
              executable: false,
              provenance: ['fixture:navigation'],
            },
          ],
          summary: {
            total: 1,
            executable_count: 0,
            metadata_only_count: 1,
            lifecycle_counts: {
              IDEA: 0,
              OBSERVATION: 1,
              ONLINE: 0,
              REJECTED: 0,
              RETIRED: 0,
            },
            lottery_type_counts: {
              DAILY_539: 0,
              BIG_LOTTO: 1,
              POWER_LOTTO: 0,
            },
          },
          capabilities: {
            evaluation_metrics_available: false,
            d3_status_available: false,
            best_strategy_ranking_available: false,
            unavailable_reason_codes: ['NO_CANONICAL_STRATEGY_EVALUATION_EVIDENCE'],
          },
        }),
      )
    }
    if (url.includes('/api/v1/historical-results/runs')) {
      return Promise.resolve(apiResponse(makeRunPage()))
    }
    if (url.includes('/api/v1/ingestion-runs')) {
      return Promise.resolve(
        apiResponse({
          records: [],
          page: 1,
          page_size: 25,
          total_count: 0,
          total_pages: 0,
          sort: ['started_at:desc', 'id:desc'],
        }),
      )
    }
    return Promise.resolve(
      apiResponse({
        records: [],
        page: 1,
        page_size: 25,
        total_count: 0,
        total_pages: 0,
        sort: ['draw_date:desc', 'draw_number:string_desc', 'id:desc'],
      }),
    )
  })
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  vi.unstubAllGlobals()
  window.location.hash = ''
})

describe('App navigation', () => {
  it('navigates among every local workspace without a router', async () => {
    const wrapper = mount(App)
    await flushPromises()

    const navigation = wrapper.get('nav[aria-label="Primary navigation"]')
    expect(navigation.findAll('a').map((link) => link.text())).toEqual([
      'Strategy Overview',
      'Success Windows',
      'Data Center',
      'Draw History',
      'Live Zone Split Bets',
    ])
    expect(wrapper.find('#strategy-catalog-title').exists()).toBe(true)

    window.location.hash = '#/historical-success-windows'
    window.dispatchEvent(new HashChangeEvent('hashchange'))
    await flushPromises()
    expect(wrapper.find('#historical-success-title').exists()).toBe(true)
    expect(
      navigation
        .find('a[href="#/historical-success-windows"]')
        .attributes('aria-current'),
    ).toBe('page')

    window.location.hash = '#/data-center'
    window.dispatchEvent(new HashChangeEvent('hashchange'))
    await flushPromises()
    expect(wrapper.find('#data-center-title').exists()).toBe(true)
    expect(navigation.find('a[href="#/data-center"]').attributes('aria-current')).toBe('page')

    window.location.hash = '#/draw-history'
    window.dispatchEvent(new HashChangeEvent('hashchange'))
    await flushPromises()
    expect(wrapper.find('#draw-history-title').exists()).toBe(true)
    expect(navigation.find('a[href="#/draw-history"]').attributes('aria-current')).toBe('page')

    window.location.hash = '#/strategies'
    window.dispatchEvent(new HashChangeEvent('hashchange'))
    await flushPromises()
    expect(wrapper.find('#strategy-catalog-title').exists()).toBe(true)
    wrapper.unmount()
  })
})
