// @vitest-environment jsdom

import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type {
  DrawHistoryResponse,
  DrawSyncResponse,
  IngestionRunPage,
} from '../src/api/drawData'
import type { HistoricalImportRunPage } from '../src/api/historicalImports'
import type {
  P638Replay,
  P638ReplayPage,
  P638Run,
  P638RunPage,
  P638Strategy,
  P638StrategyPage,
} from '../src/api/p638Historical'
import DataOperationsPage from '../src/features/data-operations/DataOperationsPage.vue'
import DrawHistoryPage from '../src/features/draw-history/DrawHistoryPage.vue'
import HistoryPage from '../src/features/history/HistoryPage.vue'
import P638HistoricalReplayPage from '../src/features/p638-historical-replay/P638HistoricalReplayPage.vue'
import { isOptionalIsoCalendarDate, isValidIsoCalendarDate } from '../src/utils/isoDate'

let fetchMock: ReturnType<typeof vi.fn<typeof fetch>>

function apiResponse(payload: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: vi.fn().mockResolvedValue(payload),
  } as unknown as Response
}

const emptyRuns = {
  records: [],
  page: 1,
  page_size: 25,
  total_count: 0,
  total_pages: 0,
  sort: ['started_at:desc', 'id:desc'],
} satisfies IngestionRunPage

const emptyDraws = {
  records: [],
  page: 1,
  page_size: 25,
  total_count: 0,
  total_pages: 0,
  sort: ['draw_date:desc', 'draw_number:string_desc', 'id:desc'],
} satisfies DrawHistoryResponse

const emptyHistoricalImports = {
  items: [],
  total_count: 0,
  limit: 50,
  offset: 0,
} satisfies HistoricalImportRunPage

const syncResponse = {
  operation_type: 'MANUAL_SYNC',
  provider: 'fixture-provider',
  requested_start: '2026-08-25',
  requested_end: '2026-08-25',
  resolved_start: '2026-08-25',
  resolved_end: '2026-08-25',
  fetched_count: 0,
  result: {
    run_id: null,
    status: 'SUCCESS',
    lottery_type: 'BIG_LOTTO',
    total_count: 0,
    inserted_count: 0,
    skipped_count: 0,
    conflict_count: 0,
    failed_count: 0,
    first_draw_number: null,
    last_draw_number: null,
    completed_at: '2026-08-25T00:00:00Z',
  },
} satisfies DrawSyncResponse

const p638Run = {
  run_id: 'p638-run-1',
  import_identity_sha256: 'a'.repeat(64),
  manifest_sha256: 'b'.repeat(64),
  contract_version: 'fixture-v1',
  source_run_id: 'source-run-1',
  source_replay_sha256: 'c'.repeat(64),
  source_draw_db_sha256: 'd'.repeat(64),
  source_commit_oid: 'e'.repeat(40),
  source_content_sha256: 'f'.repeat(64),
  second_zone_ssot_version: 'fixture-zone-v1',
  status: 'COMPLETE',
  started_at: '2026-08-25T00:00:00Z',
  completed_at: '2026-08-25T00:00:00Z',
  strategy_count: 1,
  draw_count: 1,
  complete_target_count: 1,
  excluded_target_count: 0,
  failed_target_count: 0,
  ticket_count: 0,
  first_draw_number: '0001',
  first_draw_date: '2026-08-25',
  last_draw_number: '0001',
  last_draw_date: '2026-08-25',
  is_idempotent_replay: true,
} satisfies P638Run

const p638Runs = {
  items: [p638Run],
  total_count: 1,
  limit: 25,
  offset: 0,
} satisfies P638RunPage

const p638Strategy = {
  strategy_snapshot_id: 'snapshot-1',
  run_id: p638Run.run_id,
  strategy_id: 'fixture-strategy',
  display_label: 'Fixture strategy',
  strategy_version: 'v1',
  executable: false,
  adapter_path: null,
  native_ticket_count: null,
  min_history: 0,
  zone1_contract: 'fixture-zone-1',
  zone2_contract: 'fixture-zone-2',
  lifecycle_status: 'OBSERVATION',
  replay_status: 'COMPLETE',
  source_run_id: 'source-run-1',
  source_replay_sha256: 'c'.repeat(64),
  source_paths: ['fixture'],
  provenance: 'fixture',
  exclusion_reason: null,
  complete_target_count: 1,
  excluded_target_count: 0,
  failed_target_count: 0,
  ticket_count: 0,
  zone1_hit_distribution: [],
  zone2_hit_distribution: [],
  first_draw_number: '0001',
  first_draw_date: '2026-08-25',
  last_draw_number: '0001',
  last_draw_date: '2026-08-25',
} satisfies P638Strategy

const p638Strategies = {
  run_id: p638Run.run_id,
  items: [p638Strategy],
  total_count: 1,
  limit: 200,
  offset: 0,
} satisfies P638StrategyPage

const p638Replay = {
  target_id: 'target-1',
  run_id: p638Run.run_id,
  strategy_snapshot_id: p638Strategy.strategy_snapshot_id,
  strategy_id: p638Strategy.strategy_id,
  strategy_version: p638Strategy.strategy_version,
  target_draw_number: '0001',
  target_draw_date: '2026-08-25',
  history_boundary_draw_number: null,
  history_boundary_date: null,
  history_length: 0,
  expected_ticket_count: 0,
  status: 'COMPLETE',
  exclusion_reason: null,
  failure_reason: null,
  actual_zone1_numbers: [1, 2, 3, 4, 5, 6],
  actual_zone2_number: 7,
  source_target_locator: 'fixture:target-1',
  source_run_id: 'source-run-1',
  source_replay_sha256: 'c'.repeat(64),
  provenance: 'fixture',
  reason_type: null,
  reason: null,
  target_success: true,
  tickets: [],
} satisfies P638Replay

const p638ReplayPage = {
  run_id: p638Run.run_id,
  items: [p638Replay],
  total_count: 1,
  limit: 25,
  offset: 0,
} satisfies P638ReplayPage

beforeEach(() => {
  fetchMock = vi.fn<typeof fetch>()
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

function dateFilterInputs(wrapper: ReturnType<typeof mount>) {
  return wrapper.findAll('input[placeholder="YYYY-MM-DD"]')
}

function buttonWithText(wrapper: ReturnType<typeof mount>, text: string) {
  return wrapper.findAll('button').find((button) => button.text() === text)
}

function ingestionRunResponse(input: RequestInfo | URL): Response {
  const url = String(input)
  if (url.includes('/api/v1/draws?')) return apiResponse(emptyDraws)
  if (url.includes('/api/v1/historical-results/runs?')) return apiResponse(emptyHistoricalImports)
  if (url.includes('/api/v1/ingestion-runs?')) return apiResponse(emptyRuns)
  return apiResponse({})
}

function p638Response(input: RequestInfo | URL): Response {
  const url = String(input)
  if (url.includes('/strategies?')) return apiResponse(p638Strategies)
  if (url.includes('/replay?')) return apiResponse(p638ReplayPage)
  if (url.includes('/api/v1/p638-historical/runs?')) return apiResponse(p638Runs)
  return apiResponse({})
}

describe('strict ISO calendar date validation', () => {
  it('accepts real ISO calendar dates and preserves optional empty semantics', () => {
    expect(isValidIsoCalendarDate('2026-08-25')).toBe(true)
    expect(isValidIsoCalendarDate('2024-02-29')).toBe(true)
    expect(isOptionalIsoCalendarDate('')).toBe(true)
  })

  it('rejects impossible dates and malformed values', () => {
    for (const value of [
      '2026-99-99',
      '2026-02-30',
      '2025-02-29',
      '0000-00-00',
      'not-a-date',
      '2026/08/25',
      '2026-8-25',
    ]) {
      expect(isValidIsoCalendarDate(value)).toBe(false)
      expect(isOptionalIsoCalendarDate(value)).toBe(false)
    }
  })
})

describe('Data Operations date-gated sync', () => {
  it('disables every sync action and dispatches nothing for invalid required dates', async () => {
    fetchMock.mockResolvedValue(apiResponse(emptyRuns))
    const wrapper = mount(DataOperationsPage)
    await flushPromises()

    const dateInputs = dateFilterInputs(wrapper)
    const manualSync = wrapper.get('[data-testid="manual-sync"]')
    const scheduledSync = wrapper.get('[data-testid="scheduled-sync"]')
    expect(manualSync.attributes('disabled')).toBeDefined()
    expect(scheduledSync.attributes('disabled')).toBeDefined()
    expect(fetchMock).toHaveBeenCalledTimes(1)

    await dateInputs[0]?.setValue('2026-08-25')
    for (const invalidDate of ['2026-99-99', '2026-02-30', 'not-a-date']) {
      await dateInputs[0]?.setValue(invalidDate)
      await dateInputs[1]?.setValue('2026-08-25')
      expect(manualSync.attributes('disabled')).toBeDefined()
      expect(scheduledSync.attributes('disabled')).toBeDefined()

      await manualSync.trigger('click')
      await scheduledSync.trigger('click')
      expect(fetchMock).toHaveBeenCalledTimes(1)
    }

    wrapper.unmount()
  })

  it('keeps a valid date range enabled and sends the existing sync request', async () => {
    fetchMock
      .mockResolvedValueOnce(apiResponse(emptyRuns))
      .mockResolvedValueOnce(apiResponse(syncResponse))
      .mockResolvedValueOnce(apiResponse(emptyRuns))
    const wrapper = mount(DataOperationsPage)
    await flushPromises()

    const dateInputs = dateFilterInputs(wrapper)
    await dateInputs[0]?.setValue('2024-02-29')
    await dateInputs[1]?.setValue('2026-08-25')
    const manualSync = wrapper.get('[data-testid="manual-sync"]')
    expect(manualSync.attributes('disabled')).toBeUndefined()
    await manualSync.trigger('click')
    await flushPromises()

    expect(fetchMock.mock.calls[1]?.[0]).toBe('/api/v1/draw-sync/manual')
    expect(JSON.parse(String((fetchMock.mock.calls[1]?.[1] as RequestInit).body))).toMatchObject({
      date_from: '2024-02-29',
      date_to: '2026-08-25',
    })
    wrapper.unmount()
  })
})

describe('P638 Historical Replay date-gated query', () => {
  it('keeps empty filters optional, rejects invalid dates, and only queries valid filters', async () => {
    fetchMock.mockImplementation((input) => Promise.resolve(p638Response(input)))
    const wrapper = mount(P638HistoricalReplayPage)
    await flushPromises()

    const dateInputs = dateFilterInputs(wrapper)
    const apply = buttonWithText(wrapper, 'Apply server-side filters')
    expect(apply).toBeDefined()
    expect(apply?.attributes('disabled')).toBeUndefined()
    const initialReplayUrl = String(
      fetchMock.mock.calls.find((call) => String(call[0]).includes('/replay?'))?.[0],
    )
    expect(initialReplayUrl).not.toContain('date_from')
    expect(initialReplayUrl).not.toContain('date_to')

    await dateInputs[0]?.setValue('2026-08-25')
    for (const [index, invalidDate] of [
      [0, '2026-99-99'],
      [1, '2026-02-30'],
      [0, 'not-a-date'],
    ] as const) {
      await dateInputs[index]?.setValue(invalidDate)
      await dateInputs[index === 0 ? 1 : 0]?.setValue('2026-08-25')
      expect(apply?.attributes('disabled')).toBeDefined()
      const requestCount = fetchMock.mock.calls.length
      await apply?.trigger('click')
      await flushPromises()
      expect(fetchMock).toHaveBeenCalledTimes(requestCount)
    }

    await dateInputs[0]?.setValue('2024-02-29')
    await dateInputs[1]?.setValue('2026-08-25')
    expect(apply?.attributes('disabled')).toBeUndefined()
    await apply?.trigger('click')
    await flushPromises()

    const validReplayUrl = String(
      fetchMock.mock.calls.filter((call) => String(call[0]).includes('/replay?')).at(-1)?.[0],
    )
    expect(validReplayUrl).toContain('date_from=2024-02-29')
    expect(validReplayUrl).toContain('date_to=2026-08-25')
    wrapper.unmount()
  })
})

describe('History date-gated ingestion query', () => {
  it('preserves optional empty filters, rejects invalid dates, and queries valid dates only', async () => {
    fetchMock.mockImplementation((input) => Promise.resolve(ingestionRunResponse(input)))
    const wrapper = mount(HistoryPage)
    await flushPromises()

    await wrapper
      .get('nav[aria-label="History sections"]')
      .findAll('button')[1]
      ?.trigger('click')
    const section = wrapper.get('section[aria-labelledby="ingestion-history-title"]')
    const dateInputs = dateFilterInputs(section)
    const apply = buttonWithText(section, 'Apply filters')
    const initialIngestionUrl = String(
      fetchMock.mock.calls.find((call) => String(call[0]).includes('/api/v1/ingestion-runs?'))?.[0],
    )
    expect(new URL(initialIngestionUrl, 'http://localhost').searchParams.has('date_from')).toBe(false)
    expect(apply?.attributes('disabled')).toBeUndefined()

    for (const [index, invalidDate] of [
      [0, '2026-99-99'],
      [1, '2026-02-30'],
      [0, 'not-a-date'],
    ] as const) {
      await dateInputs[index]?.setValue(invalidDate)
      await dateInputs[index === 0 ? 1 : 0]?.setValue('2026-08-25')
      expect(apply?.attributes('disabled')).toBeDefined()
      const requestCount = fetchMock.mock.calls.length
      await section.get('form').trigger('submit')
      await flushPromises()
      expect(fetchMock).toHaveBeenCalledTimes(requestCount)
    }

    await dateInputs[0]?.setValue('2024-02-29')
    await dateInputs[1]?.setValue('2026-08-25')
    expect(apply?.attributes('disabled')).toBeUndefined()
    await section.get('form').trigger('submit')
    await flushPromises()

    const validIngestionUrl = String(
      fetchMock.mock.calls.filter((call) => String(call[0]).includes('/api/v1/ingestion-runs?')).at(-1)?.[0],
    )
    expect(validIngestionUrl).toContain('date_from=2024-02-29')
    expect(validIngestionUrl).toContain('date_to=2026-08-25')
    wrapper.unmount()
  })
})

describe('Draw History date-gated query', () => {
  it('preserves empty filters, rejects invalid dates without dispatch, and accepts valid dates', async () => {
    fetchMock.mockResolvedValue(apiResponse(emptyDraws))
    const wrapper = mount(DrawHistoryPage)
    await flushPromises()

    const dateFrom = wrapper.get('input[name="date-from"]')
    const dateTo = wrapper.get('input[name="date-to"]')
    const apply = buttonWithText(wrapper, 'Apply filters')
    const initialUrl = String(fetchMock.mock.calls[0]?.[0])
    expect(new URL(initialUrl, 'http://localhost').searchParams.has('date_from')).toBe(false)
    expect(apply?.attributes('disabled')).toBeUndefined()

    await dateTo.setValue('2026-08-25')
    for (const invalidDate of ['2026-99-99', '2026-02-30', 'not-a-date']) {
      await dateFrom.setValue(invalidDate)
      expect(apply?.attributes('disabled')).toBeDefined()
      const requestCount = fetchMock.mock.calls.length
      await wrapper.get('form').trigger('submit')
      await flushPromises()
      expect(fetchMock).toHaveBeenCalledTimes(requestCount)
    }

    await dateFrom.setValue('2024-02-29')
    expect(apply?.attributes('disabled')).toBeUndefined()
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    const validUrl = String(fetchMock.mock.calls.at(-1)?.[0])
    expect(validUrl).toContain('date_from=2024-02-29')
    expect(validUrl).toContain('date_to=2026-08-25')
    wrapper.unmount()
  })
})
