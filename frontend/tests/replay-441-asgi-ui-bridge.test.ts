// @vitest-environment jsdom

import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  getReplayBackfillCoverage,
  listReplayBackfillPredictions,
  listReplayBackfillStrategies,
  listReplayStrategyInventory,
} from '../src/api/replayBackfill'
import App from '../src/App.vue'

interface CapturedRequest {
  method: string
  path: string
  query: Record<string, string | number>
  url: string
}

interface CapturedResponse {
  request: CapturedRequest
  status_code: number
  headers: Record<string, string>
  raw_body: string
  body: unknown
}

interface ReplayCapture {
  provenance: {
    fixture: {
      run_id: string
      sqlite_sha256_matches_original_b_sample: boolean
    }
  }
  responses: Record<string, CapturedResponse>
}

const capture = JSON.parse(
  readFileSync(resolve(process.cwd(), 'tests/fixtures/replay-441-asgi-http.json'), 'utf8'),
) as ReplayCapture

function jsonRoundTrip(value: unknown): unknown {
  return JSON.parse(JSON.stringify(value)) as unknown
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

function capturedRecord(name: string): CapturedResponse {
  const record = capture.responses[name]
  if (!record) throw new Error(`Missing recorded response ${name}`)
  return record
}

function assertRequestMatchesCapture(url: URL, method: string, record: CapturedResponse): void {
  expect(method).toBe(record.request.method)
  expect(url.pathname).toBe(record.request.path)
  const actualQuery = Object.fromEntries(url.searchParams.entries())
  const expectedQuery = Object.fromEntries(
    Object.entries(record.request.query).map(([key, value]) => [key, String(value)]),
  )
  expect(jsonRoundTrip(actualQuery)).toEqual(jsonRoundTrip(expectedQuery))
}

function selectRecordedResponse(url: URL): CapturedResponse {
  const lotteryType = url.searchParams.get('lottery_type')
  switch (url.pathname) {
    case '/api/v1/replay-strategy-inventory':
      if (lotteryType === 'BIG_LOTTO') return capturedRecord('inventory_big_lotto')
      if (lotteryType === 'POWER_LOTTO') return capturedRecord('inventory_power_lotto')
      break
    case '/api/v1/replay-backfill/strategies':
      if (url.searchParams.get('limit') === '64') {
        return capturedRecord('backfill_strategies_b_test_page64')
      }
      if (lotteryType === 'BIG_LOTTO') {
        return capturedRecord('backfill_strategies_ui_big_lotto_page100')
      }
      if (lotteryType === 'POWER_LOTTO') {
        return capturedRecord('backfill_strategies_ui_power_lotto_page100')
      }
      break
    case '/api/v1/replay-backfill/predictions':
      if (url.searchParams.get('limit') === '50') {
        return capturedRecord('predictions_ui_limit50')
      }
      break
    case '/api/v1/replay-backfill/coverage':
      if (lotteryType === 'BIG_LOTTO') return capturedRecord('coverage_ui_big_lotto')
      if (lotteryType === 'POWER_LOTTO') return capturedRecord('coverage_ui_power_lotto')
      break
  }
  throw new Error(`No captured ASGI response for ${url.pathname}${url.search}`)
}

function installRecordedFetch() {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input), 'http://testserver')
    if (url.pathname === '/api/v1/historical-results/runs') {
      return {
        ok: true,
        status: 200,
        json: async () => ({ items: [], total_count: 0, limit: 50, offset: 0 }),
      } as Response
    }
    const record = selectRecordedResponse(url)
    assertRequestMatchesCapture(url, init?.method ?? 'GET', record)
    return responseFromCapture(record)
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

describe('fixture-run-53 recorded ASGI response bridge', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    window.location.hash = '#/'
  })

  it('validates the recorded B and UI request bodies through the current API adapter', async () => {
    expect(capture.provenance.fixture.run_id).toBe('fixture-run-53')
    expect(capture.provenance.fixture.sqlite_sha256_matches_original_b_sample).toBe(false)

    const fetchMock = installRecordedFetch()
    const inventoryBigRecord = capturedRecord('inventory_big_lotto')
    const inventoryPowerRecord = capturedRecord('inventory_power_lotto')
    const bStrategiesRecord = capturedRecord('backfill_strategies_b_test_page64')
    const uiStrategiesBigRecord = capturedRecord('backfill_strategies_ui_big_lotto_page100')
    const uiStrategiesPowerRecord = capturedRecord('backfill_strategies_ui_power_lotto_page100')
    const uiPredictionsRecord = capturedRecord('predictions_ui_limit50')
    const coverageBigRecord = capturedRecord('coverage_ui_big_lotto')
    const coveragePowerRecord = capturedRecord('coverage_ui_power_lotto')
    const bPredictionsRecord = capturedRecord('predictions_b_test_limit100')

    const inventoryBig = await listReplayStrategyInventory(
      inventoryBigRecord.request.query.lottery_type as 'BIG_LOTTO',
    )
    const inventoryPower = await listReplayStrategyInventory(
      inventoryPowerRecord.request.query.lottery_type as 'POWER_LOTTO',
    )
    const bStrategies = await listReplayBackfillStrategies({
      lotteryType: bStrategiesRecord.request.query.lottery_type as 'BIG_LOTTO',
      limit: bStrategiesRecord.request.query.limit as number,
    })
    const uiStrategiesBig = await listReplayBackfillStrategies({
      lotteryType: uiStrategiesBigRecord.request.query.lottery_type as 'BIG_LOTTO',
      limit: uiStrategiesBigRecord.request.query.limit as number,
    })
    const uiStrategiesPower = await listReplayBackfillStrategies({
      lotteryType: uiStrategiesPowerRecord.request.query.lottery_type as 'POWER_LOTTO',
      limit: uiStrategiesPowerRecord.request.query.limit as number,
    })
    const uiPredictions = await listReplayBackfillPredictions({
      lotteryType: uiPredictionsRecord.request.query.lottery_type as 'BIG_LOTTO',
      period: uiPredictionsRecord.request.query.period as 'ALL',
      limit: uiPredictionsRecord.request.query.limit as number,
      fromDate: uiPredictionsRecord.request.query.from_date as string,
      toDate: uiPredictionsRecord.request.query.to_date as string,
    })
    const coverageBig = await getReplayBackfillCoverage(
      coverageBigRecord.request.query.lottery_type as 'BIG_LOTTO',
    )
    const coveragePower = await getReplayBackfillCoverage(
      coveragePowerRecord.request.query.lottery_type as 'POWER_LOTTO',
    )

    expect(jsonRoundTrip(inventoryBig)).toEqual(jsonRoundTrip(inventoryBigRecord.body))
    expect(jsonRoundTrip(inventoryPower)).toEqual(jsonRoundTrip(inventoryPowerRecord.body))
    expect(jsonRoundTrip(bStrategies)).toEqual(jsonRoundTrip(bStrategiesRecord.body))
    expect(jsonRoundTrip(uiStrategiesBig)).toEqual(jsonRoundTrip(uiStrategiesBigRecord.body))
    expect(jsonRoundTrip(uiStrategiesPower)).toEqual(jsonRoundTrip(uiStrategiesPowerRecord.body))
    expect(jsonRoundTrip(uiPredictions)).toEqual(jsonRoundTrip(uiPredictionsRecord.body))
    expect(jsonRoundTrip(coverageBig)).toEqual(jsonRoundTrip(coverageBigRecord.body))
    expect(jsonRoundTrip(coveragePower)).toEqual(jsonRoundTrip(coveragePowerRecord.body))

    const bPredictionBody = bPredictionsRecord.body as {
      items: unknown[]
      next_cursor: string | null
      run_id: string
    }
    expect(bPredictionsRecord.request.query).toEqual({
      from_date: '2026-01-01',
      limit: 100,
      lottery_type: 'BIG_LOTTO',
      period: 'ALL',
      run_id: 'fixture-run-53',
      strategy_id: 'fixture-biglotto-native',
      to_date: '2026-02-22',
    })
    expect(bPredictionBody.run_id).toBe('fixture-run-53')
    expect(bPredictionBody.items).toHaveLength(53)
    expect(bPredictionBody.next_cursor).toBeNull()
    expect(uiPredictions.items).toHaveLength(50)
    expect(uiPredictions.next_cursor).toBe(uiPredictionsRecord.body &&
      (uiPredictionsRecord.body as { next_cursor: string }).next_cursor)
    expect(fetchMock).toHaveBeenCalledTimes(8)
  })

  it('mounts #/replay-history and renders captured identities, statuses, tickets, cutoffs, training, and coverage', async () => {
    installRecordedFetch()
    window.location.hash = '#/replay-history'
    const wrapper = mount(App)
    await flushPromises()

    expect(wrapper.get('#replay-history-title').text()).toBe('Replay History')
    const backfillTab = wrapper.findAll('nav[aria-label="Replay history sections"] button')[2]
    expect(backfillTab).toBeDefined()
    await backfillTab!.trigger('click')
    await flushPromises()

    const backfill = wrapper.get('[data-testid="strategy-backfill"]')
    const identityTable = backfill.findAll('table').find((table) =>
      table.find('caption').text().startsWith('Strategy identities'),
    )
    expect(identityTable).toBeDefined()

    const deviationRows = identityTable!.findAll('tbody tr').filter((row) =>
      row.find('code').text() === 'biglotto_deviation_2bet',
    )
    expect(deviationRows).toHaveLength(2)
    const unidentifiedDeviation = deviationRows.find((row) => row.text().includes('版本未提供'))
    const registeredDeviation = deviationRows.find((row) => row.text().includes('v0.1'))
    expect(unidentifiedDeviation?.text()).toContain('生命週期：UNREGISTERED_IDENTIFIED')
    expect(unidentifiedDeviation?.text()).toContain('無歷史資料')
    expect(unidentifiedDeviation?.text()).toContain('Wrapper 狀態未提供')
    expect(unidentifiedDeviation?.text()).toContain(
      '未證明可正式回填：Native binding 未知 (binding=null, runnable=false)',
    )
    expect(registeredDeviation?.text()).toContain('生命週期：ONLINE')
    expect(registeredDeviation?.text()).toContain('可重建')
    expect(registeredDeviation?.text()).toContain('具有 Replay 執行能力')
    expect(registeredDeviation?.text()).toContain('Wrapper 可呼叫')
    expect(registeredDeviation?.text()).toContain('Native Backfill 可執行 (binding=true, runnable=true)')
    expect(identityTable!.text()).toContain('bet2_fourier_expansion_biglotto')

    const queryForm = backfill.get('form')
    await queryForm.get('input[name="from_date"]').setValue('2026-01-01')
    await queryForm.get('input[name="to_date"]').setValue('2026-02-22')
    await queryForm.get('select[name="period"]').setValue('ALL')
    await queryForm.trigger('submit')
    await flushPromises()

    const firstRow = backfill.get('[data-testid="backfill-row-202600001-fixture-biglotto-native"]')
    const firstTicketPositions = firstRow.findAll('td:nth-child(5) li').map((item) =>
      item.text().match(/^#(\d+)/)?.[1],
    )
    expect(firstTicketPositions).toEqual(['2', '3', '1'])
    expect(firstRow.findAll('td:nth-child(8) table tbody tr td:nth-child(4)').map((cell) =>
      cell.text(),
    )).toEqual(['6', '5', '0'])
    expect(firstRow.findAll('td:nth-child(8) table tbody tr td:nth-child(5)').map((cell) =>
      cell.text(),
    )).toEqual([
      '未命中',
      '命中',
      '未命中',
    ])
    expect(firstRow.text()).toContain('VERIFIED')
    expect(firstRow.text()).toContain('此策略不需要模型訓練。')
    expect(firstRow.text()).toContain('Training cutoff')
    expect(firstRow.text()).toContain('Prediction cutoff')
    expect(firstRow.text()).not.toContain('重訓成功')

    const zeroRow = backfill.get('[data-testid="backfill-row-202600002-fixture-biglotto-native"]')
    expect(zeroRow.get('td:nth-child(9)').text()).toBe('評估狀態未確認')
    expect(zeroRow.get('td:nth-child(8)').text()).toContain('Best main hits: 資料核對不一致')
    expect(zeroRow.findAll('td:nth-child(8) table tbody tr td:nth-child(4)')[0].text()).toBe(
      '資料核對不一致（來源 0；集合交集 6）',
    )
    expect(zeroRow.text()).toContain('UNTRUSTED · CUTOFF_NOT_BEFORE_TARGET')

    const nullRow = backfill.get('[data-testid="backfill-row-202600003-fixture-biglotto-native"]')
    expect(nullRow.get('td:nth-child(9)').text()).toBe('尚未計算')
    expect(nullRow.get('td:nth-child(8)').text()).toContain('Best main hits: 尚未計算')
    expect(nullRow.findAll('td:nth-child(8) table tbody tr td:nth-child(4)').map((cell) =>
      cell.text(),
    )).toEqual(['尚未計算', '尚未計算', '尚未計算'])
    expect(nullRow.text()).toContain('UNTRUSTED · CUTOFF_INPUT_IDENTITY_CONFLICT')

    const unknownCutoffRow = backfill.get('[data-testid="backfill-row-202600004-fixture-biglotto-native"]')
    expect(unknownCutoffRow.text()).toContain('UNKNOWN · PREDICTION_INPUT_NOT_RECORDED')
    expect(unknownCutoffRow.get('td:nth-child(9)').text()).toBe('尚未計算')

    expect(backfill.text()).toContain('fixture-run-53')
    expect(backfill.text()).toContain('53 / 53')
    expect(backfill.text()).toContain('Showing 50 / 53')

    await backfill.get('select[name="lottery_type"]').setValue('POWER_LOTTO')
    await flushPromises()
    const powerIdentityTable = backfill.findAll('table').find((table) =>
      table.find('caption').text().startsWith('Strategy identities'),
    )
    expect(powerIdentityTable).toBeDefined()
    const wave2Row = powerIdentityTable!.findAll('tbody tr').find((row) =>
      row.text().includes('lag_reversion_2bet') && row.text().includes('v0.1-p638-wave2'),
    )
    expect(wave2Row?.text()).toContain('生命週期：UNREGISTERED_IDENTIFIED')
    expect(wave2Row?.text()).toContain('Wrapper 可呼叫')
    expect(wave2Row?.text()).toContain(
      '未證明可正式回填：沒有 Native binding (binding=false, runnable=false)',
    )
    expect(wave2Row?.text()).not.toContain('Native Backfill 可執行')
    wrapper.unmount()
  })
})
