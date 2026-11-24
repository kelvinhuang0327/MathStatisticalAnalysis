import { describe, expect, it } from 'vitest'
import { compareLoaded, compareReplayRuns, type ReplaySelection } from '../src/features/replay-history/replayPairComparison'

const left: ReplaySelection = { runId: 'left-run', strategyId: 'left', strategyVersion: 'v1' }
const right: ReplaySelection = { runId: 'right-run', strategyId: 'right', strategyVersion: 'v2' }
const winning = { main_numbers: [1, 2, 3, 4, 5, 6], special_number: 7 }
const winner = [{ main_numbers: [1, 2, 3, 20, 21, 22] }, { main_numbers: [30, 31, 32, 33, 34, 35] }]
const loser = [{ main_numbers: [10, 11, 12, 13, 14, 15] }, { main_numbers: [30, 31, 32, 33, 34, 35] }]
function cell(id: string, wins: boolean) {
  return { target_draw_id: id, target_draw_date: `2020-01-0${id}`, execution_status: 'COMPLETE',
    source_history_provenance_status: 'VERIFIED', winning_numbers: winning, history_fingerprint: `history-${id}`,
    history_count: Number(id), cutoff_draw_id: `previous-${id}`, cutoff_draw_date: '2019-12-31',
    predicted_tickets: wins ? winner : loser, combination_success: wins }
}
function data() {
  const targets = new Map([['1', '2020-01-01'], ['2', '2020-01-02'], ['3', '2020-01-03'], ['4', '2020-01-04']])
  const a = new Map([['1', cell('1', true)], ['2', cell('2', false)], ['3', cell('3', true)], ['4', cell('4', false)]])
  const b = new Map([['1', cell('1', false)], ['2', cell('2', false)], ['3', cell('3', true)], ['4', cell('4', true)]])
  return { targets, a, b, winningDraws: new Map([...targets.keys()].map(id => [id, winning])) }
}

describe('Replay two-strategy comparison', () => {
  it('ranks only shared valid periods and reports failed or mismatched records', () => {
    const { targets, a, b, winningDraws } = data()
    b.get('2')!.execution_status = 'FAILED'
    b.get('3')!.history_fingerprint = 'different'
    const result = compareLoaded({ targets, cells: a, winningDraws }, { targets, cells: b, winningDraws }, [left, right], 'ALL')
    expect(result.sharedTargets).toBe(4)
    expect(result.evaluated).toBe(2)
    expect(result.excluded).toBe(2)
    expect(result.reasons).toEqual({ '執行未完成': 1, '歷史或截止期不一致': 1 })
    expect(result.rows.map((row) => [row.strategyId, row.successes, row.rank])).toEqual([['left', 1, 1], ['right', 1, 1]])
  })

  it('excludes inconsistent stored success and history that reaches the target', () => {
    const { targets, a, b, winningDraws } = data()
    a.get('1')!.combination_success = false
    a.get('2')!.cutoff_draw_date = '2020-01-02'
    const result = compareLoaded({ targets, cells: a, winningDraws }, { targets, cells: b, winningDraws }, [left, right], 'ALL')
    expect(result.reasons).toEqual({ '票面或中獎結果不一致': 1, '歷史或截止期不一致': 1 })
    expect(result.evaluated).toBe(2)
  })

  it('counts two main hits plus the special number as a prize', () => {
    const targets = new Map([['1', '2020-01-01']])
    const winningDraws = new Map([['1', winning]])
    const a = cell('1', true)
    a.predicted_tickets = [{ main_numbers: [1, 2, 7, 20, 21, 22] }, ...loser.slice(1)]
    const result = compareLoaded({ targets, cells: new Map([['1', a]]), winningDraws },
      { targets, cells: new Map([['1', cell('1', false)]]), winningDraws }, [left, right], 'ALL')
    expect(result.rows.map(row => [row.successes, row.rank])).toEqual([[1, 1], [0, 2]])
  })

  it('reads exact run identities and rejects a changing or incomplete page', async () => {
    const { targets, a, b, winningDraws } = data()
    const fetcher = async (input: string) => {
      const url = new URL(input, 'http://test')
      const isLeft = url.pathname.endsWith('left-run') || url.searchParams.get('run_id') === 'left-run'
      const selection = isLeft ? left : right
      if (url.pathname.includes('/runs/')) return new Response(JSON.stringify({ run_id: selection.runId, manifest: {
        run_id: selection.runId, lottery_type: 'BIG_LOTTO', execution_version: 'exec', dataset_identity: 'data',
        targets: [...targets].map(([draw_number, draw_date]) => ({ draw_number, draw_date, main_numbers: winning.main_numbers, special_numbers: [winning.special_number] })),
        strategies: [{ strategy_id: selection.strategyId, strategy_version: selection.strategyVersion, native_ticket_count: 2 }],
      }}))
      const cells = [...(isLeft ? a : b).values()].map((row) => ({ ...row, strategy_id: selection.strategyId, strategy_version: selection.strategyVersion, execution_version: 'exec', dataset_identity: 'data' }))
      return new Response(JSON.stringify({ items: cells.slice(0, 3), total_count: 4, limit: 200, offset: 0 }))
    }
    await expect(compareReplayRuns(left, right, 'ALL', undefined, fetcher)).rejects.toThrow('分頁不完整')
  })
})
