// @vitest-environment jsdom
import { mount } from '@vue/test-utils'
import { afterEach, expect, it, vi } from 'vitest'
import ReplayPairComparison from '../src/features/replay-history/ReplayPairComparison.vue'

vi.mock('../src/features/replay-history/replayPairComparison', () => ({
  compareReplayRuns: vi.fn(async () => ({
    firstDate: '2007-01-05', lastDate: '2026-11-17', sharedTargets: 2187,
    evaluated: 2186, excluded: 1, leftOnlyTargets: 1, rightOnlyTargets: 1,
    reasons: { '執行未完成': 1 }, differencePercentagePoints: 100 / 2186,
    rows: [
      { strategyId: 'candidate', strategyVersion: 'v1', successes: 138, evaluated: 2186, rate: 138 / 2186, rank: 1 },
      { strategyId: 'baseline', strategyVersion: 'v1', successes: 137, evaluated: 2186, rate: 137 / 2186, rank: 2 },
    ],
  })),
}))

afterEach(() => vi.clearAllMocks())

it('shows the compared denominator, failure, ranks and a stable baseline difference', async () => {
  const wrapper = mount(ReplayPairComparison)
  await wrapper.get('form').trigger('submit')
  await vi.waitFor(() => expect(wrapper.find('[data-testid="replay-pair-results"]').exists()).toBe(true))
  expect(wrapper.text()).toContain('可評估 2186 期')
  expect(wrapper.text()).toContain('執行未完成 1 期')
  expect(wrapper.text()).toContain('138 / 2186')
  expect(wrapper.text()).toContain('137 / 2186')
  expect(wrapper.text()).toContain('0.046 個百分點')
  await wrapper.findAll('input')[0]!.setValue('edited-after-comparison')
  expect(wrapper.text()).toContain('0.046 個百分點')
})
