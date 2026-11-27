import { afterEach, describe, expect, it, vi } from 'vitest'
import { scanReplayCoverage } from '../src/api/replayBackfill'
const strategies = Array.from({ length: 5 }, (_, i) => ({ id: `s${i}`, version: 'v1' }))
const query = { lotteryType: 'BIG_LOTTO' as const, startDate: '2020-01-01', endDate: '2020-01-02', strategies, limit: 20, offset: 0 }
const fixture = () => ({ lottery_type: 'BIG_LOTTO', window_start_date: '2020-01-01', window_end_date: '2020-01-02', source_target_count: 1, expected_cell_count: 5, complete_cell_count: 4, incomplete_cell_count: 1, complete_coverage_percent: 80, status_counts: { COMPLETE: 4, MISSING: 1 }, strategy_counts: Object.fromEntries(strategies.map((s, i) => [`${s.id}@${s.version}`, { complete: i ? 1 : 0, incomplete: i ? 0 : 1, execution_versions: [], dataset_identities: [] }])), orphan_replay_row_count: 2, items: [{ target_draw_id: '1', target_draw_date: '2020-01-01', strategy_id: 's0', strategy_version: 'v1', status: 'MISSING', reason: 'NO_SAVED_CELL', existing_records: [] }], total_count: 1, limit: 20, offset: 0, next_offset: null })
afterEach(() => vi.unstubAllGlobals())
describe('coverage scan', () => {
  it('maps query and preserves counts', async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify(fixture())))
    vi.stubGlobal('fetch', fetcher)
    expect(await scanReplayCoverage(query)).toMatchObject({ source_target_count: 1, incomplete_cell_count: 1, orphan_replay_row_count: 2 })
    const params = new URL(fetcher.mock.calls[0][0], 'http://localhost').searchParams
    expect(params.getAll('strategy_id')).toEqual(strategies.map(s => s.id))
    expect(params.getAll('strategy_version')).toEqual(strategies.map(s => s.version))
    expect(params.get('offset')).toBe('0')
  })
  it('rejects invalid query, malformed and HTTP errors', async () => {
    await expect(scanReplayCoverage({ ...query, startDate: '2020-02-30' })).rejects.toThrow()
    await expect(scanReplayCoverage({ ...query, strategies: Array(5).fill(strategies[0]) })).rejects.toThrow()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(new Response('{}')).mockResolvedValueOnce(new Response('{}', { status: 422 })).mockResolvedValueOnce(new Response('{}', { status: 503 })))
    await expect(scanReplayCoverage(query)).rejects.toMatchObject({ status: 502 })
    await expect(scanReplayCoverage(query)).rejects.toMatchObject({ status: 422 })
    await expect(scanReplayCoverage(query)).rejects.toMatchObject({ status: 503 })
  })
})
it('accepts an empty page while retaining global totals and zero-source response', async () => {
  const emptyPage = { ...fixture(), items: [], offset: 20, next_offset: null }
  const zero = { ...fixture(), source_target_count: 0, expected_cell_count: 0, complete_cell_count: 0, incomplete_cell_count: 0, complete_coverage_percent: 0, status_counts: {}, strategy_counts: Object.fromEntries(strategies.map(s => [`${s.id}@${s.version}`, { complete: 0, incomplete: 0, execution_versions: [], dataset_identities: [] }])), items: [], total_count: 0, orphan_replay_row_count: 0 }
  vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(new Response(JSON.stringify(emptyPage))).mockResolvedValueOnce(new Response(JSON.stringify(zero))))
  expect(await scanReplayCoverage({ ...query, offset: 20 })).toMatchObject({ source_target_count: 1, incomplete_cell_count: 1, items: [] })
  expect(await scanReplayCoverage(query)).toMatchObject({ source_target_count: 0, expected_cell_count: 0, items: [] })
})
