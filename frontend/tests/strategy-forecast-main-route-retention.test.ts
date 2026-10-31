// @vitest-environment jsdom

import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('../src/features/strategy-forecast-research/StrategyForecastResearchPage.vue', () => ({
  default: {
    name: 'StrategyForecastResearchPage',
    template: '<div data-testid="strategy-forecast-research-page">Strategy Forecast Research test stub</div>',
  },
}))

vi.mock('../src/features/replay-history/ReplayHistoryPage.vue', () => ({
  default: {
    name: 'ReplayHistoryPage',
    template: '<div data-testid="replay-history-page">Replay History test stub</div>',
  },
}))

import App from '../src/App.vue'

let unmountApp: (() => void) | undefined

beforeEach(() => {
  window.history.replaceState(null, '', '#/strategy-forecast-research')
})

afterEach(() => {
  unmountApp?.()
  unmountApp = undefined
  window.history.replaceState(null, '', '/')
})

describe('Strategy Forecast Research route retention', () => {
  it('mounts the research page and keeps Replay History independently reachable', async () => {
    const wrapper = mount(App)
    unmountApp = () => wrapper.unmount()

    const navigation = wrapper.get('nav[aria-label="Primary navigation"]')
    const researchLink = navigation.get('a[href="#/strategy-forecast-research"]')
    const replayHistoryLink = navigation.get('a[href="#/replay-history"]')

    expect(wrapper.find('[data-testid="strategy-forecast-research-page"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="replay-history-page"]').exists()).toBe(false)
    expect(researchLink.attributes('aria-current')).toBe('page')
    expect(replayHistoryLink.attributes('aria-current')).toBeUndefined()
    expect(navigation.findAll('a[aria-current="page"]')).toHaveLength(1)

    for (const href of [
      '#/history',
      '#/replay-overview',
      '#/b649-replay',
      '#/p638-replay',
      '#/t539-replay',
    ]) {
      expect(navigation.find(`a[href="${href}"]`).exists()).toBe(true)
    }

    const routeChanged = new Promise<void>((resolve) => {
      window.addEventListener('hashchange', () => resolve(), { once: true })
    })
    await replayHistoryLink.trigger('click')
    await routeChanged
    await flushPromises()

    expect(window.location.hash).toBe('#/replay-history')
    expect(wrapper.find('[data-testid="strategy-forecast-research-page"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="replay-history-page"]').exists()).toBe(true)
    expect(researchLink.attributes('aria-current')).toBeUndefined()
    expect(replayHistoryLink.attributes('aria-current')).toBe('page')
    expect(navigation.findAll('a[aria-current="page"]')).toHaveLength(1)
  })

  it('mounts Replay History directly with only its own navigation entry active', () => {
    window.history.replaceState(null, '', '#/replay-history')
    const wrapper = mount(App)
    unmountApp = () => wrapper.unmount()

    const navigation = wrapper.get('nav[aria-label="Primary navigation"]')
    expect(wrapper.find('[data-testid="replay-history-page"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="strategy-forecast-research-page"]').exists()).toBe(false)
    expect(navigation.get('a[href="#/replay-history"]').attributes('aria-current')).toBe('page')
    expect(navigation.get('a[href="#/strategy-forecast-research"]').attributes('aria-current')).toBeUndefined()
    expect(navigation.findAll('a[aria-current="page"]')).toHaveLength(1)
  })
})
