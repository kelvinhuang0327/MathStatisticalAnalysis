// @vitest-environment jsdom

import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import App from '../src/App.vue'

describe('Analysis Workspace production route', () => {
  let fetchMock: ReturnType<typeof vi.fn<typeof fetch>>

  beforeEach(() => {
    window.location.hash = '#/analysis-workspace'
    fetchMock = vi.fn<typeof fetch>()
    vi.stubGlobal('fetch', fetchMock)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    window.location.hash = ''
    document.body.replaceChildren()
  })

  it('renders a real navigation hub for the existing primary sections', async () => {
    const wrapper = mount(App, { attachTo: document.body })
    await flushPromises()

    expect(wrapper.find('#analysis-workspace-title').exists()).toBe(true)
    expect(wrapper.find('nav[aria-label="Primary navigation"] a[aria-current="page"]').text()).toBe(
      'Analysis Workspace',
    )

    const primaryNavigationHrefs = new Set(
      wrapper
        .find('nav[aria-label="Primary navigation"]')
        .findAll('a')
        .map((link) => link.attributes('href')),
    )
    const destinationLinks = wrapper.findAll('a[data-testid="workspace-destination"]')

    expect(destinationLinks).toHaveLength(9)
    expect(destinationLinks.every((link) => link.element.tagName === 'A')).toBe(true)
    expect(destinationLinks.every((link) => primaryNavigationHrefs.has(link.attributes('href')))).toBe(true)
    expect(destinationLinks.every((link) => (link.element as HTMLAnchorElement).tabIndex >= 0)).toBe(true)
    expect(wrapper.find('.pilot-demo-switcher').exists()).toBe(false)
    expect(wrapper.find('[data-testid="pilot-metrics"]').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('示範資料')
    expect(fetchMock).not.toHaveBeenCalled()

    wrapper.unmount()
  })

  it('keeps the default route available after entering the workspace', async () => {
    const wrapper = mount(App)
    await flushPromises()

    window.location.hash = '#/data-operations'
    window.dispatchEvent(new HashChangeEvent('hashchange'))
    await flushPromises()

    expect(wrapper.find('#data-center-title').exists()).toBe(true)
    expect(wrapper.find('nav[aria-label="Primary navigation"] a[aria-current="page"]').text()).toBe(
      'Data Operations',
    )

    wrapper.unmount()
  })
})
