// @vitest-environment jsdom

import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { ReplayBackfillPredictionItem } from '../src/api/replayBackfill'
import ReplayHistoryPage from '../src/features/replay-history/ReplayHistoryPage.vue'
import {
  assessReplayScoreTrust,
  verifyMainHitCount,
} from '../src/features/replay-history/replayScoreTrust'

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
  body: {
    items?: Array<Record<string, any>>
    next_cursor?: string | null
    run_id?: string | null
    total_count?: number
    [key: string]: unknown
  }
}

interface CompleteCatalogCapture {
  responses: Record<string, CapturedResponse>
}

const capture = JSON.parse(
  readFileSync(resolve(process.cwd(), 'tests/fixtures/replay-441-complete-catalog-http.json'), 'utf8'),
) as CompleteCatalogCapture

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

function selectCapturedResponse(url: URL): CapturedResponse {
  const actualQuery = Object.fromEntries(url.searchParams.entries())
  const matching = Object.values(capture.responses).filter((record) => {
    return record.request.path === url.pathname &&
      canonicalQuery(record.request.query) === canonicalQuery(actualQuery)
  })
  const success = matching.find((record) => record.status_code === 200)
  if (success) return success
  throw new Error(`No recorded TestClient response for ${url.pathname}${url.search}`)
}

function installRecordedFetch() {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = new URL(String(input), 'http://testserver')
    if (url.pathname === '/api/v1/historical-results/runs') {
      return {
        ok: true,
        status: 200,
        json: async () => ({ items: [], total_count: 0, limit: 50, offset: 0 }),
      } as Response
    }
    const record = selectCapturedResponse(url)
    expect(record.request.method).toBe('GET')
    return responseFromCapture(record)
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function predictionItems(): ReplayBackfillPredictionItem[] {
  return [
    ...capturedRecord('predictions_BIG_LOTTO_all_page1').body.items!,
    ...capturedRecord('predictions_BIG_LOTTO_all_page2').body.items!,
  ] as unknown as ReplayBackfillPredictionItem[]
}

afterEach(() => vi.unstubAllGlobals())

describe('Replay score trust guard', () => {
  it('checks main-hit counts against unique number-set intersections', () => {
    const mismatchedZero = verifyMainHitCount([1, 2, 3, 4, 5, 6], [1, 2, 3, 4, 5, 7], 0)
    expect(mismatchedZero).toEqual({ status: 'INCONSISTENT', source_hits: 0, computed_hits: 5 })

    const validFive = verifyMainHitCount([1, 2, 3, 4, 5, 6], [1, 2, 3, 4, 5, 7], 5)
    expect(validFive).toEqual({ status: 'VERIFIED', source_hits: 5, computed_hits: 5 })

    const validZero = verifyMainHitCount([1, 2, 3, 4, 5, 6], [7, 8, 9, 10, 11, 12], 0)
    expect(validZero).toEqual({ status: 'VERIFIED', source_hits: 0, computed_hits: 0 })

    const duplicatesAreUnique = verifyMainHitCount([1, 1, 2, 3], [1, 2, 2, 8], 2)
    expect(duplicatesAreUnique).toEqual({ status: 'VERIFIED', source_hits: 2, computed_hits: 2 })
  })

  it('keeps null uncomputed and incomplete numbers unverifiable', () => {
    expect(verifyMainHitCount([1, 2], [1, 2], null)).toEqual({
      status: 'NOT_COMPUTED', source_hits: null, computed_hits: null,
    })
    expect(verifyMainHitCount([1, 2], [], 0)).toEqual({
      status: 'UNVERIFIABLE', source_hits: 0, computed_hits: null,
    })
  })

  it('counts every ticket across the full recorded 53-target cursor chain', () => {
    const items = predictionItems()
    expect(items).toHaveLength(53)

    let comparableTickets = 0
    let inconsistentTickets = 0
    let unverifiableTickets = 0
    let inconsistentAggregates = 0

    for (const item of items) {
      const assessment = assessReplayScoreTrust(item)
      for (const ticket of assessment.tickets) {
        if (ticket.status === 'VERIFIED' || ticket.status === 'INCONSISTENT') {
          comparableTickets += 1
        } else {
          unverifiableTickets += 1
        }
        if (ticket.status === 'INCONSISTENT') inconsistentTickets += 1
      }
      if (assessment.aggregate_status === 'INCONSISTENT') inconsistentAggregates += 1
    }

    expect({
      comparableTickets,
      inconsistentTickets,
      unverifiableTickets,
      inconsistentAggregates,
    }).toEqual({
      comparableTickets: 151,
      inconsistentTickets: 98,
      unverifiableTickets: 8,
      inconsistentAggregates: 49,
    })
  })

  it('marks inconsistent paginated UI rows without confirming their score or prize outcome', async () => {
    installRecordedFetch()
    const wrapper = mount(ReplayHistoryPage)
    await flushPromises()
    await wrapper.findAll('nav[aria-label="Replay history sections"] button')[2]?.trigger('click')
    await flushPromises()
    await wrapper.get('input[name="from_date"]').setValue('2026-01-01')
    await wrapper.get('input[name="to_date"]').setValue('2026-02-22')
    await wrapper.get('select[name="period"]').setValue('ALL')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.findAll('[data-testid^="backfill-row-"]')).toHaveLength(50)
    await wrapper.findAll('button').find((button) => button.text().trim() === 'Load more')?.trigger('click')
    await flushPromises()
    const rows = wrapper.findAll('[data-testid^="backfill-row-"]')
    expect(rows).toHaveLength(53)

    const firstMismatch = predictionItems().find((item) =>
      assessReplayScoreTrust(item).status === 'INCONSISTENT',
    )!
    const row = wrapper.get(
      `[data-testid="backfill-row-${firstMismatch.target_draw_number}-${firstMismatch.strategy_id}"]`,
    )
    expect(row.get(`[data-testid="score-trust-${firstMismatch.target_draw_number}-${firstMismatch.strategy_id}"]`).text())
      .toBe('資料核對不一致')
    expect(row.find('td:nth-child(5)').text()).toContain(firstMismatch.predicted_tickets[0]!.main_numbers.join('、'))
    expect(row.find('td:nth-child(6)').text()).toBe(firstMismatch.actual_main_numbers.join('、'))
    expect(row.find('td:nth-child(8)').text()).toContain('Best main hits: 資料核對不一致')
    expect(row.find('td:nth-child(8)').text()).toContain('集合交集')
    expect(row.find('td:nth-child(9)').text()).toBe('評估狀態未確認')
    expect(row.find('td:nth-child(9)').text()).not.toBe('未命中')
    expect(row.text()).not.toContain('中獎')
    expect(row.text()).not.toContain('未命中')

    const verifiedItem = predictionItems().find((item) => {
      const assessment = assessReplayScoreTrust(item)
      return assessment.status === 'VERIFIED' && item.target_draw_number === '202600001'
    })!
    const verifiedRow = wrapper.get(
      `[data-testid="backfill-row-${verifiedItem.target_draw_number}-${verifiedItem.strategy_id}"]`,
    )
    expect(verifiedRow.get(`[data-testid="score-trust-${verifiedItem.target_draw_number}-${verifiedItem.strategy_id}"]`).text())
      .toBe('已評估結果')
    expect(verifiedRow.find('td:nth-child(9)').text()).toBe('中獎')
    expect(verifiedRow.find('td:nth-child(8)').text()).toContain('Best main hits: 6')
    expect(verifiedRow.find('td:nth-child(8)').text()).toContain('未命中')
    wrapper.unmount()
  })
})
