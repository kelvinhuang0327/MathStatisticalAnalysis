// @vitest-environment jsdom
import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import ReplayHistoryPage from '../src/features/replay-history/ReplayHistoryPage.vue'

const id = 'research_biglotto__k9_optimal_coverage_candidate'
const inventory = {
  lottery_type: 'BIG_LOTTO', strategy_id: id, strategy_version: 'v0.1-research',
  display_name: 'K9', source_kind: 'STRATEGY_ADAPTER_CODE', source_locator: 'fixture',
  lifecycle_status: 'CODE_ONLY', replay_data_status: 'CODE_ONLY',
  execution_capability: 'UNAVAILABLE', reconstruction_reason: 'fixture',
  historical_data_count: 0, historical_execution_count: 0,
}
const replay = {
  lottery_type: 'BIG_LOTTO', strategy_id: id, strategy_version: 'v0.1-research',
  display_name: 'K9 replay', lifecycle_status: 'OFFLINE', data_status: 'CODE_ONLY',
  source_kind: 'NATIVE_REPLAY', executable: false, available_target_count: 2183,
  training_status: 'NOT_APPLICABLE_FIXED', history_status: 'HAS_HISTORY',
  history_run_id: 'run-1', history_counts: { saved_prediction_cell_count: 2183 },
}
const response = (payload: unknown, status = 200) => ({
  ok: status < 400, status, json: async () => payload,
}) as Response
const page = (items: unknown[], next_cursor: string | null = null, run = 'run-1') => ({
  items, total_count: items.length, next_cursor,
  history_scope: { runs: { BIG_LOTTO: { run_id: run } } },
})
const settleTimer = async () => {
  await new Promise((resolve) => setTimeout(resolve, 15))
  await flushPromises()
}

function setup(lookup: (url: URL) => Promise<Response>) {
  vi.stubGlobal('fetch', vi.fn((input) => {
    const url = new URL(String(input), 'http://localhost')
    if (url.pathname === '/api/v1/historical-results/runs') return Promise.resolve(response({ items: [], total_count: 0, limit: 50, offset: 0 }))
    if (url.pathname === '/api/v1/replay-strategy-inventory') return Promise.resolve(response({ strategy_count: 1, strategies: [inventory] }))
    if (url.pathname === '/api/v1/replay-backfill/strategies') return url.searchParams.has('q') ? lookup(url) : Promise.resolve(response(page([])))
    if (url.pathname === '/api/v1/replay-backfill/coverage') return Promise.resolve(response({ expected_strategy_count: 0, expected_target_count: 0, expected_cell_count: 0, completed_cell_count: 0, failed_cell_count: 0, closed_cell_count: 0, complete_coverage_percent: 0, missing_strategy_ids: [], run_id: 'run' }))
    throw new Error(`Unexpected URL: ${url}`)
  }))
}
async function open() {
  const wrapper = mount(ReplayHistoryPage)
  await flushPromises()
  await wrapper.findAll('nav[aria-label="Replay history sections"] button')[2]!.trigger('click')
  await flushPromises()
  return wrapper
}
function row(wrapper: ReturnType<typeof mount>) {
  return wrapper.findAll('tbody tr').find((item) => item.text().includes(id))!
}
afterEach(() => vi.unstubAllGlobals())

describe('inventory and replay reconciliation', () => {
  it('resolves the selected identity past the first page, preserving inventory capabilities', async () => {
    setup(async (url) => response(url.searchParams.has('cursor') ? page([replay]) : page([], 'next')))
    const wrapper = await open()
    expect(row(wrapper).text()).toContain('歷史狀態待確認')
    await wrapper.get('select[name="strategy_id"]').setValue(id)
    await settleTimer()
    const text = row(wrapper).text()
    expect(text).toContain('有歷史資料')
    expect(text).toContain('2,183')
    expect(text).toContain('生命週期：CODE_ONLY')
    expect(text).toContain('目前沒有可用 Replay 執行器')
    expect(text).not.toContain('沒有可用歷史回放期數')
    expect(text).not.toContain('僅有程式')
    wrapper.unmount()
  })

  it('does not attach data from a different version or lottery', async () => {
    setup(async () => response(page([
      { ...replay, strategy_version: 'v2' },
      { ...replay, lottery_type: 'POWER_LOTTO' },
    ])))
    const wrapper = await open()
    await wrapper.get('select[name="strategy_id"]').setValue(id)
    await settleTimer()
    const original = wrapper.findAll('tbody tr').find((item) => item.text().includes('v0.1-research'))!
    expect(original.text()).toContain('歷史狀態待確認')
    expect(original.text()).not.toContain('2183')
    wrapper.unmount()
  })

  it('leaves history unconfirmed if lookup fails', async () => {
    setup(async () => response({}, 503))
    const wrapper = await open()
    await wrapper.get('select[name="strategy_id"]').setValue(id)
    await settleTimer()
    expect(row(wrapper).text()).toContain('歷史狀態待確認')
    expect(row(wrapper).text()).not.toContain('2183')
    wrapper.unmount()
  })

  it('discards an obsolete response after the selection changes', async () => {
    let finish!: (result: Response) => void
    setup(() => new Promise<Response>((resolve) => { finish = resolve }))
    const wrapper = await open()
    await wrapper.get('select[name="strategy_id"]').setValue(id)
    await settleTimer()
    await wrapper.get('select[name="strategy_id"]').setValue('')
    finish(response(page([replay])))
    await flushPromises()
    expect(row(wrapper).text()).toContain('歷史狀態待確認')
    expect(row(wrapper).text()).not.toContain('2183')
    wrapper.unmount()
  })
  it('automatically resolves a search without selecting an identity', async () => {
    setup(async () => response(page([replay])))
    const wrapper = await open()
    await wrapper.get('input[name="strategy_search"]').setValue('K9')
    await new Promise((resolve) => setTimeout(resolve, 300))
    await flushPromises()
    expect(row(wrapper).text()).toContain('有歷史資料')
    expect(row(wrapper).text()).toContain('2,183')
    wrapper.unmount()
  })

  it('does not mix runs if the latest run changes across lookup pages', async () => {
    setup(async (url) => response(url.searchParams.has('cursor') ? page([replay], null, 'run-2') : page([], 'next')))
    const wrapper = await open()
    await wrapper.get('select[name="strategy_id"]').setValue(id)
    await settleTimer()
    expect(row(wrapper).text()).toContain('歷史狀態待確認')
    expect(row(wrapper).text()).not.toContain('2,183')
    wrapper.unmount()
  })

  it('discards an obsolete lookup when a different run is selected', async () => {
    let finish!: (result: Response) => void
    setup((url) => url.searchParams.get('run_id') === 'run-2'
      ? Promise.resolve(response(page([], null, 'run-2')))
      : new Promise<Response>((resolve) => { finish = resolve }))
    const wrapper = await open()
    await wrapper.get('select[name="strategy_id"]').setValue(id)
    await settleTimer()
    await wrapper.get('input[name="replay_run_id"]').setValue('run-2')
    await settleTimer()
    finish(response(page([replay])))
    await flushPromises()
    expect(row(wrapper).text()).toContain('本 Run 的歷史狀態待確認')
    expect(row(wrapper).text()).not.toContain('2,183')
    wrapper.unmount()
  })

  it('does not combine a lookup from a different latest run with the catalog', async () => {
    setup(async () => response(page([{ ...replay, history_run_id: 'run-2' }], null, 'run-2')))
    const wrapper = await open()
    await wrapper.get('select[name="strategy_id"]').setValue(id)
    await settleTimer()
    expect(row(wrapper).text()).toContain('歷史狀態待確認')
    expect(row(wrapper).text()).not.toContain('2,183')
    wrapper.unmount()
  })

  it('reports available periods without inventing saved history for a legacy response', async () => {
    setup(async () => response({ items: [{ ...replay, history_status: undefined, history_run_id: undefined }], total_count: 1, next_cursor: null }))
    const wrapper = await open()
    await wrapper.get('select[name="strategy_id"]').setValue(id)
    await settleTimer()
    expect(row(wrapper).text()).toContain('已提供可用回放期數')
    expect(row(wrapper).text()).toContain('2183')
    expect(row(wrapper).text()).not.toContain('有歷史資料')
    wrapper.unmount()
  })

})
