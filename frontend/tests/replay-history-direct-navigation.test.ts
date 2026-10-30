// @vitest-environment jsdom

import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('../src/features/future-modules/FutureModulesPage.vue', () => ({
  default: {
    name: 'FutureModulesPage',
    template: '<div data-testid="future-modules-page">Future Modules test stub</div>',
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
  window.history.replaceState(null, '', '#/future-modules')
})

afterEach(() => {
  unmountApp?.()
  unmountApp = undefined
  window.history.replaceState(null, '', '/')
})

describe('Replay History direct navigation', () => {
  it('opens the existing page from primary navigation and marks only it current', async () => {
    const wrapper = mount(App)
    unmountApp = () => wrapper.unmount()

    const navigation = wrapper.get('nav[aria-label="Primary navigation"]')
    const replayHistoryLink = navigation.get('a[href="#/replay-history"]')
    const futureModulesLink = navigation.get('a[href="#/future-modules"]')

    expect(replayHistoryLink.text()).toBe('Replay History')
    expect(replayHistoryLink.attributes('href')).toBe('#/replay-history')
    expect(futureModulesLink.attributes('aria-current')).toBe('page')

    expect(
      ['#/history', '#/replay-overview', '#/b649-replay', '#/p638-replay', '#/t539-replay'].every(
        (href) => navigation.find(`a[href="${href}"]`).exists(),
      ),
    ).toBe(true)

    const routeChanged = new Promise<void>((resolve) => {
      window.addEventListener('hashchange', () => resolve(), { once: true })
    })
    await replayHistoryLink.trigger('click')
    await routeChanged
    await flushPromises()

    expect(window.location.hash).toBe('#/replay-history')
    expect(wrapper.find('[data-testid="replay-history-page"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="future-modules-page"]').exists()).toBe(false)
    expect(replayHistoryLink.attributes('aria-current')).toBe('page')
    expect(futureModulesLink.attributes('aria-current')).toBeUndefined()
    expect(navigation.findAll('a[aria-current="page"]')).toHaveLength(1)
  })
})
