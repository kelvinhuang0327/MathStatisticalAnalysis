import { mount, flushPromises } from '@vue/test-utils'
import { afterEach, expect, it, vi } from 'vitest'
import ReplayCoverageScan from '../src/features/replay-history/ReplayCoverageScan.vue'
import { scanReplayCoverage } from '../src/api/replayBackfill'
vi.mock('../src/api/replayBackfill', () => ({ scanReplayCoverage: vi.fn() }))
const scan = vi.mocked(scanReplayCoverage)
const result = (offset = 0, incomplete = 0) => ({ lottery_type: 'BIG_LOTTO' as const, window_start_date: '2020-01-01', window_end_date: '2020-01-02', source_target_count: incomplete ? 5 : 0, expected_cell_count: incomplete ? 25 : 0, complete_cell_count: incomplete ? 0 : 0, incomplete_cell_count: incomplete, complete_coverage_percent: 0, status_counts: {}, strategy_counts: Object.fromEntries(Array.from({length:5},(_,i)=>[`s${i}@v1`, { complete:0, incomplete:incomplete ? 5 : 0, execution_versions:[], dataset_identities:[] }])), orphan_replay_row_count: 3, items: offset ? [] : Array.from({length: Math.min(20,incomplete)},(_,i)=>({ target_draw_id:`${i}`,target_draw_date:'2020-01-01',strategy_id:'s0',strategy_version:'v1',status:'MISSING',reason:'NO_SAVED_CELL',existing_records:[] })), total_count:incomplete, limit:20, offset, next_offset: incomplete > offset+20 ? offset+20 : null })
async function fill(wrapper: ReturnType<typeof mount>) {
  await wrapper.get('[aria-label="掃描開始日期"]').setValue('2020-01-01')
  await wrapper.get('[aria-label="掃描結束日期"]').setValue('2020-01-02')
  for (let i=0;i<5;i++) { await wrapper.get(`[aria-label="策略 ${i+1} ID"]`).setValue(`s${i}`); await wrapper.get(`[aria-label="策略 ${i+1} 版本"]`).setValue('v1') }
}
afterEach(() => vi.resetAllMocks())
it('shows zero expected and recovers from an error', async () => {
  scan.mockRejectedValueOnce(new Error('HTTP 503')).mockResolvedValueOnce(result())
  const w=mount(ReplayCoverageScan,{props:{lotteryType:'BIG_LOTTO'}}); await fill(w)
  await w.get('form').trigger('submit'); await flushPromises(); expect(w.get('[role="alert"]').text()).toContain('503')
  await w.get('form').trigger('submit'); await flushPromises(); expect(w.text()).toContain('來源期數 0'); expect(w.text()).toContain('完成 0／0'); expect(w.text()).toContain('此頁沒有缺口')
})
it('preserves global totals on an empty page and resets query to first page', async () => {
  scan.mockResolvedValueOnce(result(0,25)).mockResolvedValueOnce(result(20,20)).mockResolvedValueOnce(result())
  const w=mount(ReplayCoverageScan,{props:{lotteryType:'BIG_LOTTO'}}); await fill(w)
  await w.get('form').trigger('submit'); await flushPromises(); await w.findAll('button').find(b => b.text() === '下一頁')!.trigger('click'); await flushPromises()
  expect(w.text()).toContain('來源期數 5'); expect(w.text()).toContain('缺口 20 筆'); expect(w.text()).toContain('此頁沒有缺口')
  await w.get('[aria-label="策略 1 ID"]').setValue('new'); await w.get('form').trigger('submit'); await flushPromises()
  expect(scan.mock.calls[2]?.[0].offset).toBe(0)
})
it('ignores an older response even when the request ignores abort', async () => {
  let resolveOld!: (v: ReturnType<typeof result>) => void
  scan.mockImplementationOnce(() => new Promise(resolve => { resolveOld=resolve })).mockResolvedValueOnce(result())
  const w=mount(ReplayCoverageScan,{props:{lotteryType:'BIG_LOTTO'}}); await fill(w)
  await w.get('form').trigger('submit'); await w.get('[aria-label="策略 1 ID"]').setValue('new'); await w.get('form').trigger('submit'); await flushPromises()
  resolveOld(result(0,25)); await flushPromises(); expect(w.text()).toContain('來源期數 0'); expect(w.text()).not.toContain('來源期數 5')
})

it.each(['ID', '版本'])('rejects a missing strategy %s without sending an HTTP request', async (field) => {
  const actual = await vi.importActual<typeof import('../src/api/replayBackfill')>('../src/api/replayBackfill')
  scan.mockImplementation(actual.scanReplayCoverage)
  const fetcher = vi.fn()
  vi.stubGlobal('fetch', fetcher)
  const w = mount(ReplayCoverageScan, { props: { lotteryType: 'BIG_LOTTO' } }); await fill(w)
  await w.get(`[aria-label="策略 1 ${field}"]`).setValue('  ')
  await w.get('form').trigger('submit'); await flushPromises()
  expect(w.get('[role="alert"]').text()).toContain('五組不同策略 ID／版本')
  expect(fetcher).not.toHaveBeenCalled()
  vi.unstubAllGlobals()
})

it('shows full denominators and each strategy count when all cells are complete', async () => {
  const complete = { ...result(), source_target_count: 5, expected_cell_count: 25, complete_cell_count: 25, incomplete_cell_count: 0, complete_coverage_percent: 100, status_counts: { COMPLETE: 25 }, strategy_counts: Object.fromEntries(Array.from({length: 5}, (_, i) => [`s${i}@v1`, { complete: 5, incomplete: 0, execution_versions: [], dataset_identities: [] }])), total_count: 0, items: [] }
  scan.mockResolvedValueOnce(complete)
  const w = mount(ReplayCoverageScan, { props: { lotteryType: 'BIG_LOTTO' } }); await fill(w)
  await w.get('form').trigger('submit'); await flushPromises()
  expect(w.text()).toContain('來源期數 5；預期 cell 25；完成 25／25；未完成 0／25；覆蓋 100.0%')
  for (let i = 0; i < 5; i++) expect(w.text()).toContain(`s${i}@v1：完成 5／5，缺口 0／5`)
  expect(w.text()).toContain('此頁沒有缺口'); expect(w.text()).toContain('缺口 0 筆')
  expect(w.find('tbody').exists()).toBe(false)
})

it.each(['422', '503', 'malformed'])('clears the old result and recovers with unchanged query after %s', async (failure) => {
  const actual = await vi.importActual<typeof import('../src/api/replayBackfill')>('../src/api/replayBackfill')
  scan.mockImplementation(actual.scanReplayCoverage)
  const valid = { ...result(), source_target_count: 5, expected_cell_count: 25, complete_cell_count: 25, complete_coverage_percent: 100, status_counts: { COMPLETE: 25 }, strategy_counts: Object.fromEntries(Array.from({length: 5}, (_, i) => [`s${i}@v1`, { complete: 5, incomplete: 0, execution_versions: [], dataset_identities: [] }])) }
  const failedResponse = failure === 'malformed' ? new Response('{}') : new Response('{}', { status: Number(failure) })
  const fetcher = vi.fn().mockResolvedValueOnce(new Response(JSON.stringify(valid))).mockResolvedValueOnce(failedResponse).mockResolvedValueOnce(new Response(JSON.stringify(valid)))
  vi.stubGlobal('fetch', fetcher)
  const w = mount(ReplayCoverageScan, { props: { lotteryType: 'BIG_LOTTO' } }); await fill(w)
  await w.get('form').trigger('submit'); await flushPromises(); expect(w.text()).toContain('完成 25／25')
  await w.get('form').trigger('submit'); await flushPromises()
  expect(w.find('[role="alert"]').exists()).toBe(true); expect(w.text()).not.toContain('完成 25／25'); expect(w.text()).not.toContain('s0@v1：完成')
  await w.get('form').trigger('submit'); await flushPromises()
  expect(w.find('[role="alert"]').exists()).toBe(false); expect(w.text()).toContain('完成 25／25')
  expect(fetcher).toHaveBeenCalledTimes(3); expect(fetcher.mock.calls[0][0]).toBe(fetcher.mock.calls[1][0]); expect(fetcher.mock.calls[1][0]).toBe(fetcher.mock.calls[2][0])
  vi.unstubAllGlobals()
})
