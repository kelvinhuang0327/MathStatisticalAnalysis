// @vitest-environment jsdom
import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import K3ComparisonPanel from '../src/features/replay-history/K3ComparisonPanel.vue'
import { getK3Comparison } from '../src/api/replayBackfill'

vi.mock('../src/api/replayBackfill', () => ({ getK3Comparison: vi.fn() }))

function comparison(strategy: 'optimizer' | 'ecp', unmatched = false) {
  return {
    run_id: 'saved-run', strategy, target_count: 51, paired_count: unmatched ? 50 : 51,
    unmatched_count: unmatched ? 1 : 0, old_wins: 2, new_wins: 3,
    old_only: 1, new_only: 2, fair_delta: 0.25, observed_minus_fair: 0.75,
    rows: Array.from({ length: 51 }, (_, i) => ({
      target_draw_number: String(100 + i), target_draw_date: '2026-11-13',
      match_status: unmatched && i === 0 ? 'MISSING_OR_AMBIGUOUS' : 'ORIGINAL_CELL',
      source_segment: 'RECOVERY', original_source_run_id: null, old_cell_identity: 'cell',
      old: unmatched && i === 0 ? null : { portfolio_any_prize: false, predicted_tickets: [{ ticket_position: 1, main_numbers: [1, 2, 3, 4, 5, 6] }] },
      new: { portfolio_any_prize: true, actual_main_numbers: [1, 2, 3, 4, 5, 6], actual_special_numbers: [7], predicted_tickets: [{ ticket_position: 1, main_numbers: [7, 8, 9, 10, 11, 12] }] },
    })),
  }
}

describe('K3 comparison panel', () => {
  afterEach(() => vi.resetAllMocks())

  it('shows paired summary and side-by-side tickets, and pages without double counting', async () => {
    vi.mocked(getK3Comparison).mockResolvedValue(comparison('optimizer') as never)
    const wrapper = mount(K3ComparisonPanel)
    await flushPromises()
    expect(wrapper.text()).toContain('成功配對 51 期')
    expect(wrapper.text()).toContain('+0.75 期')
    const rows = wrapper.findAll('tbody tr')
    expect(rows).toHaveLength(50)
    expect(rows[0]!.text()).toContain('1、2、3、4、5、6')
    expect(rows[0]!.text()).toContain('7、8、9、10、11、12')
    await wrapper.get('nav[aria-label="比較結果分頁"] button:nth-of-type(3)').trigger('click')
    expect(wrapper.findAll('tbody tr')).toHaveLength(1)
    expect(wrapper.text()).toContain('第 2 / 2 頁')
    wrapper.unmount()
  })

  it('switches strategies and marks unmatched periods rather than counting them', async () => {
    vi.mocked(getK3Comparison).mockImplementation(async (strategy) => comparison(strategy, strategy === 'ecp') as never)
    const wrapper = mount(K3ComparisonPanel)
    await flushPromises()
    await wrapper.get('select').setValue('ecp')
    await flushPromises()
    expect(getK3Comparison).toHaveBeenLastCalledWith('ecp', expect.any(AbortSignal))
    expect(wrapper.text()).toContain('1 期無法可靠配對，不計入中獎率')
    expect(wrapper.find('tbody tr').text()).toContain('未配對')
    wrapper.unmount()
  })
})
