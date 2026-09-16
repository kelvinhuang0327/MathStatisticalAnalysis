// @vitest-environment jsdom

import { mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import GradientPillButton from '../src/features/ui-page-pilot/GradientPillButton.vue'
import ThreeUiPagePilot from '../src/features/ui-page-pilot/ThreeUiPagePilot.vue'
import { shouldActivateThreeUiPilot } from '../src/main'

describe('GradientPillButton', () => {
  it('emits click on a normal interaction', async () => {
    const wrapper = mount(GradientPillButton, { props: { label: '送出' } })
    await wrapper.get('button').trigger('click')
    expect(wrapper.emitted('click')).toHaveLength(1)
  })

  it('does not emit click when disabled', async () => {
    const wrapper = mount(GradientPillButton, { props: { label: '送出', disabled: true } })
    const button = wrapper.get('button')
    expect(button.attributes('disabled')).toBeDefined()
    await button.trigger('click')
    expect(wrapper.emitted('click')).toBeUndefined()
  })

  it('does not emit a duplicate click while loading', async () => {
    const wrapper = mount(GradientPillButton, { props: { label: '送出', loading: true } })
    const button = wrapper.get('button')
    expect(button.attributes('disabled')).toBeDefined()
    expect(button.attributes('aria-busy')).toBe('true')
    await button.trigger('click')
    await button.trigger('click')
    expect(wrapper.emitted('click')).toBeUndefined()
  })
})

describe('ThreeUiPagePilot', () => {
  let fetchSpy: ReturnType<typeof vi.fn>
  let originalFetch: typeof globalThis.fetch

  beforeEach(() => {
    originalFetch = globalThis.fetch
    fetchSpy = vi.fn()
    globalThis.fetch = fetchSpy as unknown as typeof fetch
  })

  afterEach(() => {
    globalThis.fetch = originalFetch
    vi.useRealTimers()
  })

  it('renders the READY state with clearly-labeled demo metrics by default', () => {
    const wrapper = mount(ThreeUiPagePilot)
    expect(wrapper.text()).toContain('分析工作區導覽')
    expect(wrapper.find('[data-testid="pilot-metrics"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('示範資料，非真實結果')
  })

  it('switches to LOADING, EMPTY, and ERROR via the demo switcher', async () => {
    const wrapper = mount(ThreeUiPagePilot)

    await wrapper.get('[data-testid="pilot-switch-loading"]').trigger('click')
    expect(wrapper.find('[data-testid="pilot-metrics"]').exists()).toBe(false)
    expect(wrapper.find('.skeleton-loader').exists()).toBe(true)

    await wrapper.get('[data-testid="pilot-switch-empty"]').trigger('click')
    expect(wrapper.text()).toContain('尚無示範資料')

    await wrapper.get('[data-testid="pilot-switch-error"]').trigger('click')
    expect(wrapper.text()).toContain('示範資料錯誤')
    expect(wrapper.get('button.button--danger').text()).toBe('重試')
  })

  it('restores an interactive READY state on error retry', async () => {
    const wrapper = mount(ThreeUiPagePilot)
    await wrapper.get('[data-testid="pilot-switch-error"]').trigger('click')

    await wrapper.get('button.button--danger').trigger('click')

    expect(wrapper.find('[data-testid="pilot-metrics"]').exists()).toBe(true)
    const regenerateButton = wrapper.findComponent(GradientPillButton)
    expect(regenerateButton.props('loading')).toBe(false)
    expect(regenerateButton.get('button').attributes('disabled')).toBeUndefined()
  })

  it('guards the regenerate action against duplicate clicks while its own loading state is active', async () => {
    vi.useFakeTimers()
    const wrapper = mount(ThreeUiPagePilot)

    await wrapper.findComponent(GradientPillButton).get('button').trigger('click')
    expect(wrapper.findComponent(GradientPillButton).props('loading')).toBe(true)

    await wrapper.findComponent(GradientPillButton).get('button').trigger('click')
    expect(wrapper.findComponent(GradientPillButton).emitted('click')).toHaveLength(1)

    vi.advanceTimersByTime(500)
    await wrapper.vm.$nextTick()
    expect(wrapper.findComponent(GradientPillButton).props('loading')).toBe(false)
  })

  it('never calls fetch across a full interaction cycle', async () => {
    vi.useFakeTimers()
    const wrapper = mount(ThreeUiPagePilot)

    await wrapper.get('[data-testid="pilot-switch-empty"]').trigger('click')
    await wrapper.findComponent(GradientPillButton).get('button').trigger('click')
    await wrapper.get('[data-testid="pilot-switch-error"]').trigger('click')
    await wrapper.get('button.button--danger').trigger('click')
    await wrapper.findComponent(GradientPillButton).get('button').trigger('click')
    vi.advanceTimersByTime(500)

    expect(fetchSpy).not.toHaveBeenCalled()
  })
})

describe('threeui pilot dev-only activation gate', () => {
  it('activates only in dev mode with the exact uiPilot=threeui query', () => {
    expect(shouldActivateThreeUiPilot(true, '?uiPilot=threeui')).toBe(true)
    expect(shouldActivateThreeUiPilot(false, '?uiPilot=threeui')).toBe(false)
    expect(shouldActivateThreeUiPilot(true, '?uiPilot=other')).toBe(false)
    expect(shouldActivateThreeUiPilot(true, '')).toBe(false)
  })
})
