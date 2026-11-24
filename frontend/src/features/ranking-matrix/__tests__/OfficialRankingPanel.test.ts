// @vitest-environment jsdom
import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, expect, it, vi } from 'vitest'
import OfficialRankingPanel from '../OfficialRankingPanel.vue'

afterEach(() => vi.unstubAllGlobals())

it('switches lottery and window and displays unknown results without a rank', async () => {
  const fetchMock = vi.fn(async (url: string) => {
    const power = url.includes('POWER_LOTTO')
    return { ok: true, json: async () => ({ items: [{ strategy_id: 's', strategy_name: 's', registered: false, strategy_version: 'v', execution_version: 'e', dataset_identity: 'd', run_id: 'r', ticket_count: 2, target_ids: ['1'], start_date: '2026-01-01', end_date: '2026-01-01', successes: power ? 0 : 1, evaluated: power ? 0 : 1, missing: 0, unknown: power ? 1 : 0, rate: power ? null : 1, baseline: power ? null : .1, delta: power ? null : .9, rank: power ? null : 1, unknown_reason: power ? '來源未核實' : null }] }) } as Response
  })
  vi.stubGlobal('fetch', fetchMock)
  const wrapper = mount(OfficialRankingPanel)
  await flushPromises()
  expect(wrapper.text()).toContain('依現行獎規計算')
  expect(wrapper.text()).toContain('成功從柒獎起（至少中 2 個主號及特別號）')
  expect(wrapper.text()).toContain('不含普獎（中 3 個主號但未中特別號）')
  expect(wrapper.text()).toContain('歷史獎規變更未追溯')
  expect(wrapper.text()).toContain('未登記')
  expect(wrapper.text()).toContain('100.00%')
  await wrapper.get('[data-testid="official-lottery"]').setValue('POWER_LOTTO')
  await wrapper.get('[data-testid="official-window"]').setValue('RECENT_50')
  await flushPromises()
  expect(fetchMock.mock.calls.at(-1)?.[0]).toContain('lottery_type=POWER_LOTTO&window=RECENT_50')
  expect(wrapper.text()).toContain('UNKNOWN')
  expect(wrapper.text()).toContain('來源未核實')
  expect(wrapper.get('tbody tr').text()).toContain('—')
  expect(wrapper.get('tbody tr').text()).toContain('UNKNOWN')
})

it('does not display zero successes when a cohort has no evaluated periods', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => ({
    ok: true,
    json: async () => ({ items: [{ strategy_id: 's', strategy_name: 's', registered: false, strategy_version: 'v', execution_version: 'e', dataset_identity: 'd', run_id: 'r', ticket_count: 2, target_ids: ['1'], start_date: '2026-01-01', end_date: '2026-01-01', successes: 0, evaluated: 0, missing: 1, unknown: 0, rate: null, baseline: null, delta: null, rank: null, unknown_reason: null }] }),
  })))
  const wrapper = mount(OfficialRankingPanel)
  await flushPromises()
  expect(wrapper.get('tbody tr').text()).toContain('UNKNOWN')
  expect(wrapper.get('tbody tr').text()).not.toMatch(/\s0\s/)
})

it('shows an undetermined window without a rate or rank', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => ({
    ok: true,
    json: async () => ({ items: [{ strategy_id: 's', strategy_name: 's', registered: false,
      strategy_version: 'v', execution_version: 'e', dataset_identity: 'd', run_id: 'r',
      scope_status: 'WINDOW_UNDETERMINED', missing_target_evidence: 1, conflicting_target_evidence: 0,
      ticket_count: 1, target_ids: ['1', '2'], start_date: '', end_date: '2026-01-01',
      successes: 0, evaluated: 0, missing: 0, unknown: 2, rate: null, baseline: null,
      delta: null, rank: null, unknown_reason: '目標日期不足, 窗口無法判定' }] }),
  })))
  const wrapper = mount(OfficialRankingPanel)
  await flushPromises()
  const row = wrapper.get('tbody tr').text()
  expect(row).toContain('WINDOW_UNDETERMINED')
  expect(row).toContain('窗口無法判定')
  expect(row).toContain('UNKNOWN')
})
