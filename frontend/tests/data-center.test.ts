// @vitest-environment jsdom

import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type {
  DrawImportPreview,
  DrawSyncResponse,
  ImportCommitResult,
  IngestionRun,
  IngestionRunPage,
} from '../src/api/drawData'
import DataCenterPage from '../src/features/data-center/DataCenterPage.vue'

const csvText =
  'lottery_type,draw_number,draw_date,main_numbers,special_numbers\n' +
  'BIG_LOTTO,0001,2026-07-16,1|3|9|17|24|49,7\n'

const validPreview = {
  filename: 'valid.csv',
  is_valid: true,
  content_sha256: 'a'.repeat(64),
  parser_version: 'lottolab-draw-csv-v2',
  supported_lottery_types: ['BIG_LOTTO'],
  total_rows: 1,
  valid_rows: 1,
  blank_rows: 0,
  duplicate_rows: 0,
  conflict_rows_inside_input: 0,
  validation_error_count: 0,
  ignored_columns: [],
  normalized_preview: [],
  validation_errors: [],
  preview_truncated: false,
  errors_truncated: false,
} satisfies DrawImportPreview

const invalidPreview = {
  ...validPreview,
  filename: 'invalid.csv',
  is_valid: false,
  valid_rows: 0,
  validation_error_count: 1,
  validation_errors: [
    {
      code: 'INVALID_DRAW_DATE',
      message: 'draw_date is not a valid calendar date.',
      row_number: 2,
      field: 'draw_date',
    },
  ],
} satisfies DrawImportPreview

const commitSuccess = {
  run_id: '7de87eeb-ecc7-4c03-830a-c0fdb71254e8',
  status: 'SUCCESS',
  lottery_type: 'BIG_LOTTO',
  total_count: 1,
  inserted_count: 1,
  skipped_count: 0,
  conflict_count: 0,
  failed_count: 0,
  first_draw_number: '0001',
  last_draw_number: '0001',
  completed_at: '2026-07-16T07:00:00Z',
} satisfies ImportCommitResult

const commitFailure = {
  ...commitSuccess,
  run_id: 'f2b2ac5a-8ccf-48c4-9dfa-69787065b348',
  status: 'FAILED',
  inserted_count: 0,
  conflict_count: 1,
} satisfies ImportCommitResult

const runRecord = {
  run_id: commitSuccess.run_id,
  operation_type: 'DRAW_CSV_IMPORT',
  status: 'SUCCESS',
  lottery_type: 'BIG_LOTTO',
  source_filename: 'valid.csv',
  source_sha256: validPreview.content_sha256,
  parser_version: validPreview.parser_version,
  trigger: 'DRAW_CSV_IMPORT',
  provider: null,
  provider_version: null,
  requested_start: null,
  requested_end: null,
  resolved_start: '0001',
  resolved_end: '0001',
  fetched_count: 1,
  total_count: 1,
  inserted_count: 1,
  skipped_count: 0,
  conflict_count: 0,
  failed_count: 0,
  first_draw_number: '0001',
  last_draw_number: '0001',
  started_at: '2026-07-16T07:00:00Z',
  completed_at: '2026-07-16T07:00:00Z',
  error_summary: null,
} satisfies IngestionRun

const emptyRuns = {
  records: [],
  page: 1,
  page_size: 25,
  total_count: 0,
  total_pages: 0,
  sort: ['started_at:desc', 'id:desc'],
} satisfies IngestionRunPage

const populatedRuns = {
  ...emptyRuns,
  records: [runRecord],
  total_count: 1,
  total_pages: 1,
} satisfies IngestionRunPage

let fetchMock: ReturnType<typeof vi.fn<typeof fetch>>

function apiResponse(payload: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: vi.fn().mockResolvedValue(payload),
  } as unknown as Response
}

function file(name: string, text: Promise<string> = Promise.resolve(csvText)): File {
  return {
    name,
    size: csvText.length,
    text: vi.fn().mockReturnValue(text),
  } as unknown as File
}

async function selectFiles(wrapper: VueWrapper, selected: File[]): Promise<void> {
  const input = wrapper.get('[data-testid="csv-file"]')
  Object.defineProperty(input.element, 'files', {
    configurable: true,
    value: selected,
  })
  await input.trigger('change')
  await flushPromises()
}

interface Deferred<T> {
  promise: Promise<T>
  resolve: (value: T | PromiseLike<T>) => void
}

function deferred<T>(): Deferred<T> {
  let resolve!: Deferred<T>['resolve']
  const promise = new Promise<T>((promiseResolve) => {
    resolve = promiseResolve
  })
  return { promise, resolve }
}

async function previewOne(wrapper: VueWrapper): Promise<void> {
  await selectFiles(wrapper, [file('valid.csv')])
  await wrapper.get('[data-testid="preview-all"]').trigger('click')
  await flushPromises()
}

beforeEach(() => {
  fetchMock = vi.fn<typeof fetch>()
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('DataCenterPage batch ingestion', () => {
  it('renders explicit empty, audit, and disabled automation states', async () => {
    fetchMock.mockResolvedValue(apiResponse(emptyRuns))
    const wrapper = mount(DataCenterPage)
    await flushPromises()

    expect(wrapper.text()).toContain('No CSV selected')
    expect(wrapper.text()).toContain('No ingestion runs have been recorded')
    expect(wrapper.get('[data-testid="batch-status"]').text()).toBe('NOT_COMMITTED')
    expect(wrapper.get('[data-testid="manual-sync"]').attributes('disabled')).toBeDefined()
    expect(wrapper.get('[data-testid="csv-file"]').attributes('multiple')).toBeDefined()
    wrapper.unmount()
  })

  it('previews every file, exposes per-file validation, and commits only valid files', async () => {
    fetchMock
      .mockResolvedValueOnce(apiResponse(emptyRuns))
      .mockResolvedValueOnce(apiResponse(validPreview))
      .mockResolvedValueOnce(
        apiResponse(
          {
            error_code: 'CSV_VALIDATION_FAILED',
            message: 'CSV validation failed; no data was persisted.',
            preview: invalidPreview,
          },
          422,
        ),
      )
      .mockResolvedValueOnce(apiResponse(commitSuccess))
      .mockResolvedValueOnce(apiResponse(populatedRuns))
    const wrapper = mount(DataCenterPage)
    await flushPromises()

    await selectFiles(wrapper, [file('valid.csv'), file('invalid.csv')])
    await wrapper.get('[data-testid="preview-all"]').trigger('click')
    await flushPromises()

    expect(wrapper.findAll('tbody tr')).toHaveLength(2)
    expect(wrapper.text()).toContain(validPreview.content_sha256)
    expect(wrapper.text()).toContain('INVALID_DRAW_DATE')
    expect(wrapper.text()).toContain('1 valid · 0 invalid')
    expect(wrapper.text()).toContain('0 valid · 1 invalid')
    expect(wrapper.get('[data-testid="commit-selected-valid"]').attributes('disabled')).toBeDefined()

    await wrapper.get('[data-testid="batch-confirmation"]').setValue(true)
    await wrapper.get('[data-testid="commit-selected-valid"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-testid="batch-status"]').text()).toBe('PARTIAL_SUCCESS')
    expect(wrapper.text()).toContain(commitSuccess.run_id)
    const previewBodies = fetchMock.mock.calls.slice(1, 3).map((call) => {
      const init = call[1] as RequestInit
      return JSON.parse(String(init.body)) as Record<string, unknown>
    })
    expect(previewBodies.map((body) => body.filename)).toEqual(['valid.csv', 'invalid.csv'])
    const commitInit = fetchMock.mock.calls[3]?.[1] as RequestInit
    expect(JSON.parse(String(commitInit.body))).toMatchObject({
      filename: 'valid.csv',
      expected_sha256: validPreview.content_sha256,
      conflict_policy: 'REJECT',
    })
    wrapper.unmount()
  })

  it('reports partial success when independent file transactions diverge', async () => {
    fetchMock
      .mockResolvedValueOnce(apiResponse(emptyRuns))
      .mockResolvedValueOnce(apiResponse(validPreview))
      .mockResolvedValueOnce(apiResponse({ ...validPreview, filename: 'second.csv' }))
      .mockResolvedValueOnce(apiResponse(commitSuccess))
      .mockResolvedValueOnce(
        apiResponse(
          {
            error_code: 'EXISTING_DRAW_CONFLICT',
            message: 'Existing draw data conflicts; the batch inserted no draws.',
            result: commitFailure,
          },
          409,
        ),
      )
      .mockResolvedValueOnce(apiResponse(populatedRuns))
    const wrapper = mount(DataCenterPage)
    await flushPromises()

    await selectFiles(wrapper, [file('valid.csv'), file('second.csv')])
    await wrapper.get('[data-testid="preview-all"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="batch-confirmation"]').setValue(true)
    await wrapper.get('[data-testid="commit-all-valid"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-testid="batch-status"]').text()).toBe('PARTIAL_SUCCESS')
    expect(wrapper.text()).toContain('Existing draw data conflicts')
    expect(wrapper.text()).toContain(commitSuccess.run_id)
    expect(wrapper.text()).toContain(commitFailure.run_id)
    wrapper.unmount()
  })

  it('a newer selection invalidates late file reads', async () => {
    const oldRead = deferred<string>()
    fetchMock.mockResolvedValue(apiResponse(emptyRuns))
    const wrapper = mount(DataCenterPage)
    await flushPromises()

    await selectFiles(wrapper, [file('old.csv', oldRead.promise)])
    await selectFiles(wrapper, [file('new.csv')])
    oldRead.resolve(csvText.replace('0001', '9999'))
    await flushPromises()

    expect(wrapper.text()).toContain('new.csv')
    expect(wrapper.text()).not.toContain('old.csv')
    wrapper.unmount()
  })

  it('cancel aborts an in-flight preview and prevents stale repopulation', async () => {
    const pending = deferred<Response>()
    fetchMock
      .mockResolvedValueOnce(apiResponse(emptyRuns))
      .mockImplementationOnce(() => pending.promise)
    const wrapper = mount(DataCenterPage)
    await flushPromises()

    await selectFiles(wrapper, [file('valid.csv')])
    await wrapper.get('[data-testid="preview-all"]').trigger('click')
    await flushPromises()
    const previewInit = fetchMock.mock.calls[1]?.[1] as RequestInit
    await wrapper.get('[data-testid="cancel-batch"]').trigger('click')
    pending.resolve(apiResponse(validPreview))
    await flushPromises()

    expect(previewInit.signal?.aborted).toBe(true)
    expect(wrapper.text()).toContain('No CSV selected')
    expect(wrapper.text()).not.toContain(validPreview.content_sha256)
    wrapper.unmount()
  })

  it('unmount aborts an in-flight per-file commit', async () => {
    const pending = deferred<Response>()
    fetchMock
      .mockResolvedValueOnce(apiResponse(emptyRuns))
      .mockResolvedValueOnce(apiResponse(validPreview))
      .mockImplementationOnce(() => pending.promise)
    const wrapper = mount(DataCenterPage)
    await flushPromises()
    await previewOne(wrapper)
    await wrapper.get('[data-testid="batch-confirmation"]').setValue(true)
    await wrapper.get('[data-testid="commit-selected-valid"]').trigger('click')
    await flushPromises()
    const commitInit = fetchMock.mock.calls[2]?.[1] as RequestInit

    wrapper.unmount()
    pending.resolve(apiResponse(commitSuccess))
    await flushPromises()

    expect(commitInit.signal?.aborted).toBe(true)
  })

  it('a newer selection invalidates late commit success', async () => {
    const pending = deferred<Response>()
    fetchMock
      .mockResolvedValueOnce(apiResponse(emptyRuns))
      .mockResolvedValueOnce(apiResponse(validPreview))
      .mockImplementationOnce(() => pending.promise)
      .mockResolvedValueOnce(apiResponse(emptyRuns))
    const wrapper = mount(DataCenterPage)
    await flushPromises()
    await previewOne(wrapper)
    await wrapper.get('[data-testid="batch-confirmation"]').setValue(true)
    await wrapper.get('[data-testid="commit-selected-valid"]').trigger('click')
    await flushPromises()
    const commitInit = fetchMock.mock.calls[2]?.[1] as RequestInit

    await selectFiles(wrapper, [file('new.csv')])
    pending.resolve(apiResponse(commitSuccess))
    await flushPromises()

    expect(commitInit.signal?.aborted).toBe(true)
    expect(wrapper.text()).toContain('new.csv')
    expect(wrapper.text()).not.toContain(commitSuccess.run_id)
    wrapper.unmount()
  })

  it('a newer selection invalidates late commit errors', async () => {
    const pending = deferred<Response>()
    fetchMock
      .mockResolvedValueOnce(apiResponse(emptyRuns))
      .mockResolvedValueOnce(apiResponse(validPreview))
      .mockImplementationOnce(() => pending.promise)
      .mockResolvedValueOnce(apiResponse(emptyRuns))
    const wrapper = mount(DataCenterPage)
    await flushPromises()
    await previewOne(wrapper)
    await wrapper.get('[data-testid="batch-confirmation"]').setValue(true)
    await wrapper.get('[data-testid="commit-selected-valid"]').trigger('click')
    await flushPromises()

    await selectFiles(wrapper, [file('new.csv')])
    pending.resolve(
      apiResponse({ error_code: 'REPOSITORY_BUSY', message: 'Temporarily busy.' }, 503),
    )
    await flushPromises()

    expect(wrapper.text()).toContain('new.csv')
    expect(wrapper.text()).not.toContain('Temporarily busy.')
    wrapper.unmount()
  })

  it('two rapid batch commits issue one per-file request', async () => {
    const pending = deferred<Response>()
    fetchMock
      .mockResolvedValueOnce(apiResponse(emptyRuns))
      .mockResolvedValueOnce(apiResponse(validPreview))
      .mockImplementationOnce(() => pending.promise)
    const wrapper = mount(DataCenterPage)
    await flushPromises()
    await previewOne(wrapper)
    await wrapper.get('[data-testid="batch-confirmation"]').setValue(true)

    const button = wrapper.get('[data-testid="commit-selected-valid"]')
    await Promise.all([button.trigger('click'), button.trigger('click')])
    await flushPromises()

    expect(fetchMock).toHaveBeenCalledTimes(3)
    pending.resolve(apiResponse(commitSuccess))
    await flushPromises()
    wrapper.unmount()
  })

  it('runs a bounded sync and reloads the audit log', async () => {
    const syncResult = {
      operation_type: 'MANUAL_SYNC',
      provider: 'fixture-provider',
      requested_start: '2026-07-29',
      requested_end: '2026-07-29',
      resolved_start: '2026-07-29',
      resolved_end: '2026-07-29',
      fetched_count: 1,
      result: commitSuccess,
    } satisfies DrawSyncResponse
    fetchMock
      .mockResolvedValueOnce(apiResponse(emptyRuns))
      .mockResolvedValueOnce(apiResponse(syncResult))
      .mockResolvedValueOnce(apiResponse(populatedRuns))
    const wrapper = mount(DataCenterPage)
    await flushPromises()

    await wrapper.get('[data-testid="sync-date-from"]').setValue('2026-07-29')
    await wrapper.get('[data-testid="sync-date-to"]').setValue('2026-07-29')
    await wrapper.get('[data-testid="manual-sync"]').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('MANUAL_SYNC completed with 1 inserted')
    const request = fetchMock.mock.calls[1]
    expect(request?.[0]).toBe('/api/v1/draw-sync/manual')
    expect(JSON.parse(String((request?.[1] as RequestInit).body))).toEqual({
      lottery_type: 'BIG_LOTTO',
      date_from: '2026-07-29',
      date_to: '2026-07-29',
    })
    wrapper.unmount()
  })
})
