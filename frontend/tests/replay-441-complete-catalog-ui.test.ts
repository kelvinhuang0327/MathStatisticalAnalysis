// @vitest-environment jsdom

import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { ReplayBackfillLotteryType } from '../src/api/replayBackfill'
import ReplayHistoryPage from '../src/features/replay-history/ReplayHistoryPage.vue'

interface CapturedRequest {
  method: string
  path: string
  query: Record<string, string>
  url: string
}

interface CapturedResponse {
  request: CapturedRequest
  status_code: number
  headers: Record<string, string>
  raw_body: string
  body: Record<string, any>
}

interface CompleteCatalogCapture {
  provenance: {
    fixture: {
      run_id: string
      target_count: number
      sqlite_sha256_before_http: string
      sqlite_sha256_after_http: string
      sqlite_changed_during_http: boolean
    }
    strategy_pagination: Record<
      ReplayBackfillLotteryType,
      { pages: number; item_counts: number[]; unique_count: number }
    >
    selected_strategy_id_for_query_semantics: string
  }
  responses: Record<string, CapturedResponse>
}

interface InventoryIdentity {
  lottery_type: ReplayBackfillLotteryType
  strategy_id: string
  strategy_version: string | null
  display_name: string
  lifecycle_status: string
  replay_data_status: string
  execution_capability: string
  wrapper_callable: boolean | null
  backfill_native_binding: boolean | null
  backfill_runnable: boolean
}

const capture = JSON.parse(
  readFileSync(resolve(process.cwd(), 'tests/fixtures/replay-441-complete-catalog-http.json'), 'utf8'),
) as CompleteCatalogCapture

const lotteryTypes: ReplayBackfillLotteryType[] = ['BIG_LOTTO', 'DAILY_539', 'POWER_LOTTO']
const lotteryLabels: Record<ReplayBackfillLotteryType, string> = {
  BIG_LOTTO: 'B649',
  DAILY_539: 'T539',
  POWER_LOTTO: 'P638',
}
const dataStatusLabels: Record<string, string> = {
  HAS_HISTORY: '有歷史資料',
  REBUILDABLE: '可重建',
  NO_HISTORY: '無歷史資料',
  ARTIFACT_ONLY: '僅有研究產物',
  CODE_ONLY: '僅有程式',
  REJECTED: '已拒絕',
}

function jsonRoundTrip(value: unknown): unknown {
  return JSON.parse(JSON.stringify(value)) as unknown
}

function canonicalQuery(query: Record<string, string>): string {
  const sorted = Object.fromEntries(
    Object.entries(query).sort(([left], [right]) => left.localeCompare(right)),
  )
  return JSON.stringify(jsonRoundTrip(sorted))
}

function capturedRecord(name: string): CapturedResponse {
  const record = capture.responses[name]
  if (!record) throw new Error(`Missing recorded TestClient response ${name}`)
  return record
}

function responseFromCapture(record: CapturedResponse): Response {
  const parsedRawBody = JSON.parse(record.raw_body) as unknown
  expect(jsonRoundTrip(parsedRawBody)).toEqual(jsonRoundTrip(record.body))
  return {
    ok: record.status_code >= 200 && record.status_code < 400,
    status: record.status_code,
    headers: new Headers(record.headers),
    json: vi.fn().mockResolvedValue(parsedRawBody),
  } as unknown as Response
}

function assertRequestMatchesCapture(url: URL, method: string, record: CapturedResponse): void {
  expect(method).toBe(record.request.method)
  expect(url.pathname).toBe(record.request.path)
  const actualQuery = Object.fromEntries(url.searchParams.entries())
  expect(jsonRoundTrip(actualQuery)).toEqual(jsonRoundTrip(record.request.query))
}

function selectCapturedResponse(url: URL, failNextStrategyPage: boolean): CapturedResponse {
  const actualQuery = Object.fromEntries(url.searchParams.entries())
  if (
    failNextStrategyPage &&
    url.pathname === '/api/v1/replay-backfill/strategies' &&
    actualQuery.lottery_type === 'BIG_LOTTO' &&
    actualQuery.cursor === capture.responses.strategies_BIG_LOTTO_page1.body.next_cursor
  ) {
    return capturedRecord('strategies_BIG_LOTTO_page2_503')
  }

  const matching = Object.values(capture.responses).filter((record) => {
    if (record.request.path !== url.pathname) return false
    return canonicalQuery(record.request.query) === canonicalQuery(actualQuery)
  })
  const success = matching.find((record) => record.status_code === 200)
  if (success) return success
  throw new Error(`No recorded TestClient response for ${url.pathname}${url.search}`)
}

function installRecordedFetch(options: { failNextStrategyPage?: boolean } = {}) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input), 'http://testserver')
    const method = init?.method ?? 'GET'
    if (url.pathname === '/api/v1/historical-results/runs') {
      return {
        ok: true,
        status: 200,
        json: async () => ({ items: [], total_count: 0, limit: 50, offset: 0 }),
      } as Response
    }
    const record = selectCapturedResponse(url, options.failNextStrategyPage ?? false)
    assertRequestMatchesCapture(url, method, record)
    return responseFromCapture(record)
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

async function activateBackfill(wrapper: VueWrapper): Promise<void> {
  const tabs = wrapper.findAll('nav[aria-label="Replay history sections"] button')
  expect(tabs.length).toBeGreaterThan(2)
  await tabs[2]!.trigger('click')
  await flushPromises()
}

function strategyIdentityTable(wrapper: VueWrapper) {
  const table = wrapper
    .get('[data-testid="strategy-backfill"]')
    .findAll('table')
    .find((candidate) => candidate.find('caption').exists() &&
      candidate.find('caption').text().startsWith('Strategy identities'))
  expect(table).toBeDefined()
  return table!
}

function predictionTable(wrapper: VueWrapper) {
  const table = wrapper
    .get('[data-testid="strategy-backfill"]')
    .findAll('table')
    .find((candidate) => candidate.find('caption').exists() &&
      candidate.find('caption').text().startsWith('Per-draw replay predictions'))
  expect(table).toBeDefined()
  return table!
}

function renderedIdentityRows(table: ReturnType<typeof strategyIdentityTable>, lotteryType: ReplayBackfillLotteryType) {
  return table.findAll('tbody tr').map((row) => {
    const cells = row.findAll('td')
    const strategyId = cells[0]!.find('code').text()
    const versionLabel = cells[0]!.find('span').text()
    const strategyVersion = versionLabel === '版本未提供' ? null : versionLabel
    expect(cells[1]!.text()).toBe(lotteryLabels[lotteryType])
    return {
      key: JSON.stringify(jsonRoundTrip([lotteryType, strategyId, strategyVersion])),
      strategyId,
      strategyVersion,
      text: row.text(),
    }
  })
}

function inventoryRows(): InventoryIdentity[] {
  return lotteryTypes.flatMap((lotteryType) =>
    capture.responses[`inventory_${lotteryType}`]!.body.strategies as InventoryIdentity[],
  )
}

function inventoryIdentityKey(item: InventoryIdentity): string {
  return JSON.stringify(jsonRoundTrip([item.lottery_type, item.strategy_id, item.strategy_version]))
}

function findRenderedIdentity(
  rows: ReturnType<typeof renderedIdentityRows>,
  identity: InventoryIdentity,
) {
  const key = inventoryIdentityKey(identity)
  const found = rows.find((row) => row.key === key)
  expect(found).toBeDefined()
  return found!
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('complete 441-strategy Replay History catalog', () => {
  it('walks actual TestClient cursor pages for each lottery and preserves canonical identities', async () => {
    const fetchMock = installRecordedFetch()
    const wrapper = mount(ReplayHistoryPage)
    await flushPromises()
    await activateBackfill(wrapper)

    const allInventoryRows = inventoryRows()
    expect(allInventoryRows).toHaveLength(441)
    expect(capture.provenance.strategy_pagination).toMatchObject({
      BIG_LOTTO: { pages: 4, item_counts: [100, 100, 100, 55], unique_count: 355 },
      DAILY_539: { pages: 1, item_counts: [62], unique_count: 62 },
      POWER_LOTTO: { pages: 1, item_counts: [24], unique_count: 24 },
    })

    for (const lotteryType of lotteryTypes) {
      const backfill = wrapper.get('[data-testid="strategy-backfill"]')
      await backfill.get('select[name="lottery_type"]').setValue(lotteryType)
      await flushPromises()

      for (let page = 0; page < 8; page += 1) {
        const loadMore = backfill.findAll('button').find((button) => button.text().trim() === 'Load more strategies')
        if (!loadMore) break
        await loadMore.trigger('click')
        await flushPromises()
      }

      const table = strategyIdentityTable(wrapper)
      const rendered = renderedIdentityRows(table, lotteryType)
      const expectedRows = capture.responses[`inventory_${lotteryType}`]!.body.strategies as InventoryIdentity[]
      const expected = expectedRows.map(inventoryIdentityKey).sort()
      const actual = rendered.map((row) => row.key).sort()
      expect(actual).toEqual(expected)
      expect(new Set(actual).size).toBe(expectedRows.length)

      const strategyRequests = fetchMock.mock.calls
        .map(([input]) => new URL(String(input), 'http://testserver'))
        .filter((url) => url.pathname === '/api/v1/replay-backfill/strategies')
        .filter((url) => url.searchParams.get('lottery_type') === lotteryType)
      expect(strategyRequests).toHaveLength(capture.provenance.strategy_pagination[lotteryType].pages)
      expect(table.find('caption').text()).toContain(`${expectedRows.length} shown / ${expectedRows.length} matching`)

      if (lotteryType === 'BIG_LOTTO') {
        const bigLottoRows = rendered
        for (const status of ['REJECTED', 'ARTIFACT_ONLY', 'CODE_ONLY', 'NO_HISTORY']) {
          const source = expectedRows.find((row) =>
            row.replay_data_status === status || (status === 'CODE_ONLY' && row.lifecycle_status === status),
          )
          expect(source).toBeDefined()
          const visible = findRenderedIdentity(bigLottoRows, source!)
          if (status === 'CODE_ONLY' && source!.replay_data_status !== status) {
            expect(visible.text).toContain(`生命週期：${status}`)
          } else {
            expect(visible.text).toContain(dataStatusLabels[status])
          }
          expect(visible.text).toContain(`生命週期：${source!.lifecycle_status}`)
        }

        const versionsById = new Map<string, InventoryIdentity[]>()
        for (const row of expectedRows) {
          const versions = versionsById.get(row.strategy_id) ?? []
          versions.push(row)
          versionsById.set(row.strategy_id, versions)
        }
        const sameIdDifferentVersions = [...versionsById.values()].find((versions) =>
          new Set(versions.map((row) => row.strategy_version)).size > 1,
        )
        expect(sameIdDifferentVersions).toBeDefined()
        for (const version of sameIdDifferentVersions!) {
          expect(findRenderedIdentity(bigLottoRows, version).strategyVersion).toBe(version.strategy_version)
        }

        const wrapperOnly = expectedRows.find((row) =>
          row.execution_capability === 'EXECUTABLE' &&
          row.wrapper_callable === true &&
          row.backfill_native_binding === false &&
          row.backfill_runnable === false,
        )
        expect(wrapperOnly).toBeDefined()
        const wrapperOnlyText = findRenderedIdentity(bigLottoRows, wrapperOnly!).text
        expect(wrapperOnlyText).toContain('具有 Replay 執行能力')
        expect(wrapperOnlyText).toContain('Wrapper 可呼叫')
        expect(wrapperOnlyText).toContain('沒有 Native binding')
        expect(wrapperOnlyText).not.toContain('Native Backfill 可執行')
      }
    }

    const executableCount = allInventoryRows.filter((row) => row.execution_capability === 'EXECUTABLE').length
    const nativeRunnableCount = allInventoryRows.filter((row) => row.backfill_runnable).length
    const wrapperOnlyCount = allInventoryRows.filter((row) =>
      row.execution_capability === 'EXECUTABLE' && row.wrapper_callable === true &&
      row.backfill_native_binding === false && row.backfill_runnable === false,
    ).length
    expect([executableCount, nativeRunnableCount, wrapperOnlyCount]).toEqual([211, 205, 6])
    wrapper.unmount()
  })

  it('preserves period/date/strategy query semantics and displays actual replay results faithfully', async () => {
    const fetchMock = installRecordedFetch()
    const wrapper = mount(ReplayHistoryPage)
    await flushPromises()
    await activateBackfill(wrapper)

    const backfill = wrapper.get('[data-testid="strategy-backfill"]')
    const form = backfill.get('form')
    await form.get('input[name="from_date"]').setValue('2026-01-01')
    await form.get('input[name="to_date"]').setValue('2026-02-22')
    await form.get('select[name="period"]').setValue('ALL')
    await form.trigger('submit')
    await flushPromises()

    const firstRow = backfill.get('[data-testid="backfill-row-202600001-fixture-biglotto-native"]')
    const ticketPositions = firstRow.findAll('td:nth-child(5) li').map((item) => item.text().match(/^#(\d+)/)?.[1])
    expect(ticketPositions).toEqual(['2', '3', '1'])
    expect(firstRow.find('td:nth-child(9)').text()).toBe('中獎')
    expect(firstRow.findAll('td:nth-child(8) table tbody tr td:nth-child(4)').map((cell) => cell.text())).toEqual(['6', '5', '0'])
    expect(firstRow.text()).toContain('生命週期：OFFLINE')
    expect(firstRow.text()).toContain('VERIFIED')
    expect(firstRow.text()).toContain('此策略不需要模型訓練。')
    expect(firstRow.text()).toContain('Training cutoff')
    expect(firstRow.text()).toContain('Prediction cutoff')
    expect(firstRow.text()).not.toContain('重訓成功')
    expect(firstRow.text()).not.toContain('0%')
    const cutoffFacts = firstRow.findAll('dl div').map((fact) => [
      fact.find('dt').text(),
      fact.find('dd').text(),
    ])
    expect(cutoffFacts.find(([label]) => label === 'Training cutoff')?.[1]).toBe('API未提供')
    expect(cutoffFacts.find(([label]) => label === 'Prediction cutoff')?.[1]).toBe('VERIFIED')

    const zeroRow = backfill.get('[data-testid="backfill-row-202600002-fixture-biglotto-native"]')
    expect(zeroRow.find('td:nth-child(9)').text()).toBe('評估狀態未確認')
    expect(zeroRow.find('td:nth-child(8)').text()).toContain('Best main hits: 資料核對不一致')
    expect(zeroRow.text()).toContain('UNTRUSTED · CUTOFF_NOT_BEFORE_TARGET')

    const nullRow = backfill.get('[data-testid="backfill-row-202600003-fixture-biglotto-native"]')
    expect(nullRow.find('td:nth-child(9)').text()).toBe('尚未計算')
    expect(nullRow.find('td:nth-child(8)').text()).toContain('Best main hits: 尚未計算')

    const unknownCutoffRow = backfill.get('[data-testid="backfill-row-202600004-fixture-biglotto-native"]')
    expect(unknownCutoffRow.text()).toContain('UNKNOWN · PREDICTION_INPUT_NOT_RECORDED')

    const loadMorePredictions = backfill.findAll('button').find((button) => button.text().trim() === 'Load more')
    expect(loadMorePredictions).toBeDefined()
    await loadMorePredictions!.trigger('click')
    await flushPromises()
    expect(predictionTable(wrapper).find('caption').text()).toContain('53 total')
    expect(backfill.text()).toContain('Showing 53 / 53')

    const selectedStrategy = capture.provenance.selected_strategy_id_for_query_semantics
    const strategySelect = backfill.get('select[name="strategy_id"]')
    await strategySelect.setValue(selectedStrategy)
    for (const period of ['50', '300', '750', 'ALL']) {
      await backfill.get('select[name="period"]').setValue(period)
      await form.trigger('submit')
      await flushPromises()
      expect(backfill.text()).toContain('No replay records match the selected filters.')
    }

    const periodQueries = fetchMock.mock.calls
      .map(([input]) => new URL(String(input), 'http://testserver'))
      .filter((url) => url.pathname === '/api/v1/replay-backfill/predictions')
      .map((url) => url.searchParams.get('period'))
    expect(periodQueries).toEqual(['ALL', 'ALL', '50', '300', '750', 'ALL'])
    for (const input of fetchMock.mock.calls.map(([request]) => String(request))) {
      if (!input.includes('/api/v1/replay-backfill/predictions')) continue
      const url = new URL(input, 'http://testserver')
      expect(url.searchParams.get('from_date')).toBe('2026-01-01')
      expect(url.searchParams.get('to_date')).toBe('2026-02-22')
    }
    wrapper.unmount()
  })

  it('retains loaded identities and reports a real 503 from the next cursor page', async () => {
    const fetchMock = installRecordedFetch({ failNextStrategyPage: true })
    const wrapper = mount(ReplayHistoryPage)
    await flushPromises()
    await activateBackfill(wrapper)

    const table = strategyIdentityTable(wrapper)
    const beforeFailure = renderedIdentityRows(table, 'BIG_LOTTO')
    expect(beforeFailure).toHaveLength(100)
    const loadMore = wrapper
      .get('[data-testid="strategy-backfill"]')
      .findAll('button')
      .find((button) => button.text().trim() === 'Load more strategies')
    expect(loadMore).toBeDefined()
    await loadMore!.trigger('click')
    await flushPromises()

    const afterFailure = renderedIdentityRows(strategyIdentityTable(wrapper), 'BIG_LOTTO')
    expect(afterFailure.length).toBeGreaterThanOrEqual(beforeFailure.length)
    const afterKeys = new Set(afterFailure.map((row) => row.key))
    expect(beforeFailure.every((row) => afterKeys.has(row.key))).toBe(true)
    const error = wrapper.get('[data-testid="backfill-strategies-pagination-error"]')
    expect(error.text()).toContain('HTTP 503')
    expect(error.text()).toContain('服務暫不可用')

    const failure = capturedRecord('strategies_BIG_LOTTO_page2_503')
    expect(failure.status_code).toBe(503)
    expect(failure.request.query.cursor).toBe(capture.responses.strategies_BIG_LOTTO_page1!.body.next_cursor)
    expect(fetchMock.mock.calls.some(([input]) => String(input).includes(failure.request.query.cursor))).toBe(true)
    wrapper.unmount()
  })
})
