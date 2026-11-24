/** Compare two explicit Replay runs on the same targets and causal histories. */
export interface ReplaySelection {
  runId: string
  strategyId: string
  strategyVersion: string
}

type JsonRecord = Record<string, unknown>
type Fetcher = (input: string, init?: RequestInit) => Promise<Response>

export interface ComparisonRow {
  strategyId: string
  strategyVersion: string
  successes: number
  evaluated: number
  rate: number
  rank: number
}

export interface PairComparison {
  rows: ComparisonRow[]
  firstDate: string
  lastDate: string
  sharedTargets: number
  evaluated: number
  excluded: number
  leftOnlyTargets: number
  rightOnlyTargets: number
  reasons: Record<string, number>
  differencePercentagePoints: number
}

function object(value: unknown): JsonRecord {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('回測資料格式無效。')
  return value as JsonRecord
}

function isIsoDate(value: unknown): value is string {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false
  const parsed = new Date(`${value}T00:00:00Z`)
  return Number.isFinite(parsed.getTime()) && parsed.toISOString().slice(0, 10) === value
}

async function getJson(url: string, fetcher: Fetcher, signal?: AbortSignal): Promise<JsonRecord> {
  const response = await fetcher(url, { signal })
  if (!response.ok) throw new Error(`回測資料讀取失敗（HTTP ${response.status}）。`)
  return object(await response.json())
}

async function loadSelection(selection: ReplaySelection, fetcher: Fetcher, signal?: AbortSignal) {
  if (!selection.runId.trim() || !selection.strategyId.trim() || !selection.strategyVersion.trim()) {
    throw new Error('請填寫兩個策略的 Run、策略 ID 與版本。')
  }
  const progress = await getJson(`/api/v1/replay-backfill/runs/${encodeURIComponent(selection.runId)}`, fetcher, signal)
  const manifest = object(progress.manifest)
  if (progress.run_id !== selection.runId || manifest.run_id !== selection.runId ||
      manifest.lottery_type !== 'BIG_LOTTO' || !Array.isArray(manifest.targets) || !Array.isArray(manifest.strategies)) {
    throw new Error('Run 缺少大樂透目標期清單。')
  }
  const strategies = manifest.strategies.map(object).filter((s) =>
    s.strategy_id === selection.strategyId && s.strategy_version === selection.strategyVersion,
  )
  if (strategies.length !== 1 || strategies[0]?.native_ticket_count !== 2) {
    throw new Error('指定 Run 中找不到唯一的兩注策略版本。')
  }
  const targets = new Map<string, string>()
  const winningDraws = new Map<string, JsonRecord>()
  for (const raw of manifest.targets) {
    const t = object(raw)
    if (typeof t.draw_number !== 'string' || !/^\d{1,15}$/.test(t.draw_number) || !isIsoDate(t.draw_date) || targets.has(t.draw_number)) {
      throw new Error('Run 目標期清單無效或重複。')
    }
    const special = t.special_numbers
    if (!Array.isArray(special) || special.length !== 1) throw new Error('Run 目標期缺少開獎資料。')
    const draw = { main_numbers: t.main_numbers, special_number: special[0] }
    if (!sameWinningDraw(draw, draw)) throw new Error('Run 目標期開獎資料無效。')
    targets.set(t.draw_number, t.draw_date)
    winningDraws.set(t.draw_number, draw)
  }
  if (!targets.size) throw new Error('Run 沒有目標期。')
  const cells = new Map<string, JsonRecord>()
  const limit = 200
  let expected: number | undefined
  for (let offset = 0; expected === undefined || offset < expected; offset += limit) {
    const params = new URLSearchParams({
      lottery_type: 'BIG_LOTTO', strategy_id: selection.strategyId,
      run_id: selection.runId, limit: String(limit), offset: String(offset),
    })
    const page = await getJson(`/api/v1/replay-backfill/results?${params}`, fetcher, signal)
    if (!Array.isArray(page.items) || !Number.isSafeInteger(page.total_count) ||
        typeof page.total_count !== 'number' || page.total_count < 0 || page.offset !== offset || page.limit !== limit) {
      throw new Error('回測分頁格式無效。')
    }
    expected ??= page.total_count
    if (page.total_count !== expected || page.items.length !== Math.min(limit, expected - offset)) {
      throw new Error('回測分頁不完整或查詢期間資料變動。')
    }
    for (const raw of page.items) {
      const row = object(raw)
      if (row.strategy_id !== selection.strategyId || row.strategy_version !== selection.strategyVersion ||
          typeof row.target_draw_id !== 'string' || cells.has(row.target_draw_id) || !targets.has(row.target_draw_id) ||
          row.execution_version !== manifest.execution_version || row.dataset_identity !== manifest.dataset_identity) {
        throw new Error('Run 包含不同版本、重複或無法確認身份的回測結果。')
      }
      cells.set(row.target_draw_id, row)
    }
  }
  return { targets, cells, winningDraws }
}

function sameWinningDraw(left: unknown, right: unknown): boolean {
  try {
    const a = object(left), b = object(right)
    if (!Array.isArray(a.main_numbers) || !Array.isArray(b.main_numbers)) return false
    const valid = (xs: unknown[]) => xs.length === 6 && xs.every((x) => typeof x === 'number' && Number.isInteger(x) && x >= 1 && x <= 49) && new Set(xs).size === 6
    if (!valid(a.main_numbers) || !valid(b.main_numbers)) return false
    const sorted = (xs: unknown[]) => [...xs].map(Number).sort((x, y) => x - y).join(',')
    return sorted(a.main_numbers) === sorted(b.main_numbers) && typeof a.special_number === 'number' && Number.isInteger(a.special_number) && a.special_number >= 1 && a.special_number <= 49 && !a.main_numbers.includes(a.special_number) && a.special_number === b.special_number
  } catch { return false }
}

function checkedSuccess(row: JsonRecord): boolean | null {
  try {
    const draw = object(row.winning_numbers)
    if (!Array.isArray(draw.main_numbers) || typeof draw.special_number !== 'number' ||
        !Array.isArray(row.predicted_tickets) || row.predicted_tickets.length !== 2 ||
        typeof row.combination_success !== 'boolean') return null
    const winning = new Set(draw.main_numbers)
    let storedRuleWins = false
    let historicalWins = false
    if (typeof row.target_draw_id !== 'string' || !/^\d{1,15}$/.test(row.target_draw_id)) return null
    const seventhPrizeExists = Number(row.target_draw_id) >= 103000081
    for (const raw of row.predicted_tickets) {
      const ticket = object(raw)
      if (!Array.isArray(ticket.main_numbers) || ticket.main_numbers.length !== 6 ||
          !ticket.main_numbers.every((x) => typeof x === 'number' && Number.isInteger(x) && x >= 1 && x <= 49) ||
          new Set(ticket.main_numbers).size !== 6) return null
      const hits = ticket.main_numbers.filter((x) => winning.has(x)).length
      const seventh = hits === 2 && ticket.main_numbers.includes(draw.special_number)
      storedRuleWins ||= hits >= 3 || seventh
      historicalWins ||= hits >= 3 || (seventh && seventhPrizeExists)
    }
    // Stored backfill cells use the current rule; the existing prediction API
    // projects the seventh prize only from draw 103000081 onward.
    return storedRuleWins === row.combination_success ? historicalWins : null
  } catch { return null }
}

export function compareLoaded(
  left: Awaited<ReturnType<typeof loadSelection>>,
  right: Awaited<ReturnType<typeof loadSelection>>,
  selections: [ReplaySelection, ReplaySelection],
  window: 50 | 300 | 750 | 'ALL',
): PairComparison {
  const ids = [...left.targets.keys()].filter((id) => right.targets.has(id))
  for (const id of ids) {
    if (left.targets.get(id) !== right.targets.get(id)) throw new Error('兩個 Run 的相同期號日期不一致。')
  }
  ids.sort((a, b) => (left.targets.get(a) ?? '').localeCompare(left.targets.get(b) ?? '') || Number(a) - Number(b))
  const scoped = window === 'ALL' ? ids : ids.slice(-window)
  if (!scoped.length) throw new Error('兩個 Run 沒有共同目標期。')
  const reasons: Record<string, number> = {}
  let leftWins = 0, rightWins = 0, evaluated = 0
  const reject = (reason: string) => { reasons[reason] = (reasons[reason] ?? 0) + 1 }
  for (const id of scoped) {
    const a = left.cells.get(id), b = right.cells.get(id)
    if (!a || !b) { reject('缺少紀錄'); continue }
    if (a.execution_status !== 'COMPLETE' || b.execution_status !== 'COMPLETE') { reject('執行未完成'); continue }
    if (a.source_history_provenance_status !== 'VERIFIED' || b.source_history_provenance_status !== 'VERIFIED') { reject('歷史來源未驗證'); continue }
    if (a.target_draw_date !== left.targets.get(id) || b.target_draw_date !== right.targets.get(id) || !sameWinningDraw(a.winning_numbers, b.winning_numbers) ||
        !sameWinningDraw(a.winning_numbers, left.winningDraws.get(id)) || !sameWinningDraw(b.winning_numbers, right.winningDraws.get(id))) { reject('開獎資料不一致'); continue }
    if (typeof a.history_fingerprint !== 'string' || !a.history_fingerprint || a.history_fingerprint !== b.history_fingerprint ||
        typeof a.history_count !== 'number' || !Number.isSafeInteger(a.history_count) || a.history_count < 1 || a.history_count !== b.history_count || a.cutoff_draw_id !== b.cutoff_draw_id || !isIsoDate(a.cutoff_draw_date) || a.cutoff_draw_date !== b.cutoff_draw_date || a.cutoff_draw_date >= String(a.target_draw_date)) { reject('歷史或截止期不一致'); continue }
    const aSuccess = checkedSuccess(a), bSuccess = checkedSuccess(b)
    if (aSuccess === null || bSuccess === null) { reject('票面或中獎結果不一致'); continue }
    evaluated++
    leftWins += Number(aSuccess)
    rightWins += Number(bSuccess)
  }
  if (!evaluated) throw new Error('共同期別沒有可比較的完整紀錄。')
  const results = [leftWins, rightWins].map((successes, index) => ({
    strategyId: selections[index]!.strategyId, strategyVersion: selections[index]!.strategyVersion,
    successes, evaluated, rate: successes / evaluated, rank: successes < Math.max(leftWins, rightWins) ? 2 : 1,
  })).sort((a, b) => a.rank - b.rank)
  return { rows: results, firstDate: left.targets.get(scoped[0]!)!, lastDate: left.targets.get(scoped[scoped.length - 1]!)!,
    sharedTargets: scoped.length, evaluated, excluded: scoped.length - evaluated,
    leftOnlyTargets: left.targets.size - ids.length, rightOnlyTargets: right.targets.size - ids.length, reasons,
    differencePercentagePoints: (leftWins - rightWins) * 100 / evaluated }
}

export async function compareReplayRuns(
  left: ReplaySelection, right: ReplaySelection, window: 50 | 300 | 750 | 'ALL',
  signal?: AbortSignal, fetcher: Fetcher = fetch,
): Promise<PairComparison> {
  if (left.strategyId === right.strategyId && left.strategyVersion === right.strategyVersion) {
    throw new Error('請選擇兩個不同的策略版本。')
  }
  const [a, b] = await Promise.all([loadSelection(left, fetcher, signal), loadSelection(right, fetcher, signal)])
  return compareLoaded(a, b, [left, right], window)
}
