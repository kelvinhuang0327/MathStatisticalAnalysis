// @vitest-environment jsdom

import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import DataTable from '../src/components/DataTable.vue'
import EmptyState from '../src/components/EmptyState.vue'
import ErrorState from '../src/components/ErrorState.vue'
import FilterBar from '../src/components/FilterBar.vue'
import LotteryNumberBall from '../src/components/LotteryNumberBall.vue'
import MetricCard from '../src/components/MetricCard.vue'
import SectionHeader from '../src/components/SectionHeader.vue'
import SkeletonLoader from '../src/components/SkeletonLoader.vue'
import StatusBadge from '../src/components/StatusBadge.vue'

describe('Reusable UI Components', () => {
  it.each(['MAIN', 'SPECIAL', 'HIT', 'MISS', 'SELECTED', 'DISABLED'] as const)(
    'renders the %s LotteryNumberBall state with stable semantics',
    (variant) => {
      const wrapper = mount(LotteryNumberBall, {
        props: { value: 7, variant },
      })

      expect(wrapper.classes()).toContain(`ball--${variant.toLowerCase()}`)
      expect(wrapper.attributes('data-state')).toBe(variant.toLowerCase())
      expect(wrapper.attributes('role')).toBe('img')
      expect(wrapper.find('.ball__value').text()).toBe('7')
    },
  )

  it('identifies special numbers explicitly and exposes an accessible name', () => {
    const wrapper = mount(LotteryNumberBall, {
      props: { value: 8, variant: 'SPECIAL' },
    })

    expect(wrapper.classes()).toContain('ball--special')
    expect(wrapper.classes()).toContain('ball--special-base')
    expect(wrapper.attributes('aria-label')).toBe('Special Number 8')
    expect(wrapper.find('.ball__special-badge').text()).toBe('S')
    expect(wrapper.find('.ball__special-badge').attributes('aria-hidden')).toBe('true')
  })

  it('keeps HIT and MISS states distinguishable without color alone', () => {
    const hit = mount(LotteryNumberBall, { props: { value: 9, variant: 'HIT' } })
    const miss = mount(LotteryNumberBall, { props: { value: 10, variant: 'MISS' } })

    expect(hit.find('.ball__hit-badge').text()).toBe('★')
    expect(hit.find('.ball__hit-badge').attributes('aria-hidden')).toBe('true')
    expect(hit.attributes('aria-label')).toBe('Number 9 (Hit)')
    expect(miss.find('.ball__miss-badge').text()).toBe('×')
    expect(miss.find('.ball__miss-badge').attributes('aria-hidden')).toBe('true')
    expect(miss.attributes('aria-label')).toBe('Number 10 (Miss)')
  })

  it('exposes selected and disabled semantics and preserves reduced-motion-compatible markup', () => {
    const selected = mount(LotteryNumberBall, {
      props: { value: 11, variant: 'SELECTED' },
    })
    const disabled = mount(LotteryNumberBall, {
      props: { value: 12, variant: 'DISABLED' },
    })

    expect(selected.attributes('aria-label')).toBe('Number 11 (Selected)')
    expect(selected.attributes('data-state')).toBe('selected')
    expect(selected.find('.ball__selected-badge').text()).toBe('✓')
    expect(selected.find('.ball__selected-badge').attributes('aria-hidden')).toBe('true')
    expect(disabled.attributes('aria-disabled')).toBe('true')
    expect(disabled.attributes('aria-label')).toBe('Number 12 (Unavailable)')
    expect(disabled.classes()).toContain('ball--disabled')
    expect(disabled.find('.ball__value').text()).toBe('12')
  })

  it('renders MetricCard with labels, value, subvalue, and badge', () => {
    const wrapper = mount(MetricCard, {
      props: {
        label: 'Accepted Rows',
        value: 1250,
        subvalue: 'Batch upload count',
        badge: 'NEW',
        variant: 'accent',
      },
    })
    expect(wrapper.text()).toContain('Accepted Rows')
    expect(wrapper.text()).toContain('1250')
    expect(wrapper.text()).toContain('Batch upload count')
    expect(wrapper.text()).toContain('NEW')
    expect(wrapper.classes()).toContain('metric-card--accent')
  })

  it('renders StatusBadge with inferred variants for success, warning, danger, and info', () => {
    const successBadge = mount(StatusBadge, { props: { status: 'SUCCESS' } })
    expect(successBadge.classes()).toContain('status-badge--success')
    expect(successBadge.text()).toBe('SUCCESS')

    const dangerBadge = mount(StatusBadge, { props: { status: 'FAILED' } })
    expect(dangerBadge.classes()).toContain('status-badge--danger')

    const warningBadge = mount(StatusBadge, { props: { status: 'PARTIAL_SUCCESS' } })
    expect(warningBadge.classes()).toContain('status-badge--warning')

    const infoBadge = mount(StatusBadge, { props: { status: 'RUNNING' } })
    expect(infoBadge.classes()).toContain('status-badge--info')
  })

  it('renders FilterBar with header counts and actions slot', () => {
    const wrapper = mount(FilterBar, {
      props: { title: 'Filter Options', count: 12, countLabel: 'runs' },
      slots: {
        default: '<input type="text" placeholder="Search..." />',
        actions: '<button type="button">Reset</button>',
      },
    })
    expect(wrapper.text()).toContain('Filter Options')
    expect(wrapper.text()).toContain('12 runs')
    expect(wrapper.find('input').exists()).toBe(true)
    expect(wrapper.find('button').text()).toBe('Reset')
  })

  it('renders DataTable with caption, slots, loading, and empty states', () => {
    const emptyWrapper = mount(DataTable, {
      props: { empty: true, emptyMessage: 'Custom empty message' },
    })
    expect(emptyWrapper.text()).toContain('Custom empty message')

    const loadingWrapper = mount(DataTable, {
      props: { loading: true },
    })
    expect(loadingWrapper.text()).toContain('Loading data…')

    const contentWrapper = mount(DataTable, {
      props: { caption: 'Test Table' },
      slots: {
        head: '<tr><th>Header</th></tr>',
        default: '<tr><td>Row Content</td></tr>',
      },
    })
    expect(contentWrapper.text()).toContain('Test Table')
    expect(contentWrapper.text()).toContain('Header')
    expect(contentWrapper.text()).toContain('Row Content')
  })

  it('renders SectionHeader with title, eyebrow, and step label', () => {
    const wrapper = mount(SectionHeader, {
      props: {
        title: 'Data Operations',
        stepLabel: '01 · File Selection',
        description: 'Manage imports and automation',
      },
    })
    expect(wrapper.text()).toContain('Data Operations')
    expect(wrapper.text()).toContain('01 · File Selection')
    expect(wrapper.text()).toContain('Manage imports and automation')
  })

  it('renders EmptyState and ErrorState with emit retry events', async () => {
    const emptyWrapper = mount(EmptyState, {
      props: { title: 'No runs found', description: 'Try adjusting filters' },
    })
    expect(emptyWrapper.text()).toContain('No runs found')
    expect(emptyWrapper.text()).toContain('Try adjusting filters')

    const errorWrapper = mount(ErrorState, {
      props: { message: 'Network connection failed', retryable: true },
    })
    expect(errorWrapper.text()).toContain('Network connection failed')
    const retryBtn = errorWrapper.get('button')
    await retryBtn.trigger('click')
    expect(errorWrapper.emitted('retry')).toHaveLength(1)
  })

  it('renders SkeletonLoader for card, table, and text types', () => {
    const cardLoader = mount(SkeletonLoader, { props: { type: 'card', rows: 4 } })
    expect(cardLoader.findAll('.skeleton-card')).toHaveLength(4)

    const tableLoader = mount(SkeletonLoader, { props: { type: 'table', rows: 5 } })
    expect(tableLoader.findAll('.skeleton-row')).toHaveLength(5)
  })
})
