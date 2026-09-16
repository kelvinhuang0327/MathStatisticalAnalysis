// @vitest-environment jsdom

import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { listIngestionRuns } from '../src/api/drawData'
import type {
  BatchImportCommit,
  BatchImportPreview,
  DrawSyncResponse,
  ImportCommitResult,
  IngestionRun,
  IngestionRunPage,
} from '../src/api/drawData'
import DataCenterPage from '../src/features/data-center/DataCenterPage.vue'
import MetricCard from '../src/components/MetricCard.vue'

const csvText =
  'lottery_type,draw_number,draw_date,main_numbers,special_numbers\n' +
  'BIG_LOTTO,0001,2026-07-16,1|3|9|17|24|49,7\n'

const validFile = {
  source_filename: 'valid.csv',
  source_locator: 'valid.csv',
  source_sha256: 'a'.repeat(64),
  status: 'ACCEPTED',
  lottery_type: 'BIG_LOTTO',
  discovered_rows: 1,
  accepted_rows: 1,
  excluded_rows: 0,
  duplicate_rows: 0,
  conflict_rows: 0,
  failed_rows: 0,
  imported_rows: 0,
  issues: [],
} satisfies BatchImportPreview['files'][number]

const invalidFile = {
  source_filename: 'invalid.csv',
  source_locator: 'invalid.csv',
  source_sha256: 'b'.repeat(64),
  status: 'INVALID',
  lottery_type: null,
  discovered_rows: 1,
  accepted_rows: 0,
  excluded_rows: 0,
  duplicate_rows: 0,
  conflict_rows: 0,
  failed_rows: 1,
  imported_rows: 0,
  issues: [
    {
      code: 'INVALID_DRAW_DATE',
      message: 'draw_date is not a valid calendar date.',
      row_number: 2,
      member_name: null,
    },
  ],
} satisfies BatchImportPreview['files'][number]

const partialFile = {
  ...validFile,
  source_filename: 'partial.csv',
  source_locator: 'partial.csv',
  status: 'PARTIAL',
  failed_rows: 1,
  issues: [
    {
      code: 'MISSING_REQUIRED_VALUE',
      message: 'Required value is blank.',
      row_number: 3,
      member_name: null,
    },
  ],
} satisfies BatchImportPreview['files'][number]

const validPreview = {
  source_filename: 'batch-import',
  is_valid: true,
  manifest_sha256: 'a'.repeat(64),
  parser_version: 'lottolab-legacy-draw-batch-v1',
  files: [validFile],
  summary: {
    discovered_files: 1,
    accepted_files: 1,
    excluded_files: 0,
    parsed_rows: 1,
    accepted_rows: 1,
    excluded_rows: 0,
    duplicate_rows: 0,
    conflict_rows: 0,
    imported_rows: 0,
    failed_rows: 0,
  },
  normalized_preview: [],
  preview_truncated: false,
} satisfies BatchImportPreview

const issueRichFile = {
  ...invalidFile,
  source_filename: 'issues.zip',
  source_locator: 'issues.zip!member.csv',
  discovered_rows: 2,
  failed_rows: 2,
  issues: [
    {
      code: 'INVALID_DRAW_DATE',
      message: 'draw_date contains <img src=x onerror=alert(1)>.',
      row_number: 2,
      member_name: 'member.csv',
    },
    {
      code: 'MISSING_REQUIRED_VALUE',
      message: 'Missing <tag> value.',
      row_number: null,
      member_name: null,
    },
  ],
} satisfies BatchImportPreview['files'][number]

const issueRichPreview = {
  ...validPreview,
  is_valid: false,
  files: [issueRichFile],
  summary: {
    ...validPreview.summary,
    accepted_files: 0,
    parsed_rows: 2,
    accepted_rows: 0,
    failed_rows: 2,
  },
} satisfies BatchImportPreview

const invalidPreview = {
  ...validPreview,
  files: [validFile, invalidFile],
  summary: {
    ...validPreview.summary,
    discovered_files: 2,
    parsed_rows: 2,
    failed_rows: 1,
  },
} satisfies BatchImportPreview

const partialPreview = {
  ...validPreview,
  files: [partialFile],
  summary: {
    ...validPreview.summary,
    failed_rows: 1,
  },
} satisfies BatchImportPreview

const secondValidFile = {
  ...validFile,
  source_filename: 'second.csv',
  source_locator: 'second.csv',
  source_sha256: 'c'.repeat(64),
} satisfies BatchImportPreview['files'][number]

const twoFilePreview = {
  ...validPreview,
  files: [validFile, secondValidFile],
  summary: {
    ...validPreview.summary,
    discovered_files: 2,
    accepted_files: 2,
    parsed_rows: 2,
    accepted_rows: 2,
  },
} satisfies BatchImportPreview

const conflictOnlyFile = {
  ...validFile,
  source_filename: 'conflict.csv',
  source_locator: 'conflict.csv',
  status: 'CONFLICTED',
  discovered_rows: 3,
  accepted_rows: 0,
  excluded_rows: 0,
  duplicate_rows: 0,
  conflict_rows: 3,
  failed_rows: 0,
  imported_rows: 0,
  issues: [
    {
      code: 'DRAW_CONFLICT',
      message: 'Draw number 0001 already exists with conflicting winning numbers.',
      row_number: 2,
      member_name: null,
    },
  ],
} satisfies BatchImportPreview['files'][number]

const conflictOnlyPreview = {
  ...validPreview,
  files: [conflictOnlyFile],
  summary: {
    ...validPreview.summary,
    parsed_rows: 3,
    accepted_rows: 0,
    duplicate_rows: 0,
    conflict_rows: 3,
  },
} satisfies BatchImportPreview

const duplicateOnlyFile = {
  ...validFile,
  source_filename: 'duplicate.csv',
  source_locator: 'duplicate.csv',
  status: 'DUPLICATE',
  discovered_rows: 2,
  accepted_rows: 0,
  excluded_rows: 0,
  duplicate_rows: 2,
  conflict_rows: 0,
  failed_rows: 0,
  imported_rows: 0,
  issues: [],
} satisfies BatchImportPreview['files'][number]

const duplicateOnlyPreview = {
  ...validPreview,
  files: [duplicateOnlyFile],
  summary: {
    ...validPreview.summary,
    parsed_rows: 2,
    accepted_rows: 0,
    duplicate_rows: 2,
    conflict_rows: 0,
  },
} satisfies BatchImportPreview

const mixedConflictDuplicateFile = {
  ...validFile,
  source_filename: 'mixed.csv',
  source_locator: 'mixed.csv',
  status: 'CONFLICTED',
  discovered_rows: 7,
  accepted_rows: 0,
  excluded_rows: 0,
  duplicate_rows: 4,
  conflict_rows: 3,
  failed_rows: 0,
  imported_rows: 0,
  issues: [
    {
      code: 'DRAW_CONFLICT',
      message: 'Draw number 0002 has conflicting numbers.',
      row_number: 3,
      member_name: null,
    },
  ],
} satisfies BatchImportPreview['files'][number]

const mixedConflictDuplicatePreview = {
  ...validPreview,
  files: [mixedConflictDuplicateFile],
  summary: {
    ...validPreview.summary,
    parsed_rows: 7,
    accepted_rows: 0,
    duplicate_rows: 4,
    conflict_rows: 3,
  },
} satisfies BatchImportPreview

const batchCommitSuccess = {
  run_id: '7de87eeb-ecc7-4c03-830a-c0fdb71254e8',
  status: 'SUCCESS',
  manifest_sha256: validPreview.manifest_sha256,
  summary: { ...validPreview.summary, imported_rows: 1 },
  files: [{ ...validFile, status: 'IMPORTED', imported_rows: 1 }],
  completed_at: '2026-07-16T07:00:00Z',
  error_summary: null,
  run_ids: ['7de87eeb-ecc7-4c03-830a-c0fdb71254e8'],
  committed_chunks: 1,
  failed_chunks: 0,
} satisfies BatchImportCommit

const batchCommitFailure = {
  ...batchCommitSuccess,
  status: 'FAILED',
  summary: { ...validPreview.summary, failed_rows: 1 },
  files: [{ ...validFile, status: 'FAILED', accepted_rows: 1, failed_rows: 1 }],
  committed_chunks: 0,
  failed_chunks: 1,
  error_summary: 'Existing draw data conflicts; the batch inserted no draws.',
} satisfies BatchImportCommit

const batchCommitPartial = {
  ...batchCommitSuccess,
  status: 'PARTIAL_SUCCESS',
  summary: { ...twoFilePreview.summary, imported_rows: 1, failed_rows: 1 },
  files: [
    { ...validFile, status: 'IMPORTED', imported_rows: 1 },
    { ...secondValidFile, status: 'FAILED', failed_rows: 1 },
  ],
  error_summary: '1 persistence chunk(s) failed',
  run_ids: [batchCommitSuccess.run_id, '65919e1c-40a6-4587-8d4f-911f352064e4'],
  committed_chunks: 1,
  failed_chunks: 1,
} satisfies BatchImportCommit

const drawCommitSuccess = {
  run_id: batchCommitSuccess.run_id,
  status: 'SUCCESS',
  lottery_type: 'BIG_LOTTO',
  total_count: 1,
  inserted_count: 1,
  skipped_count: 0,
  conflict_count: 0,
  failed_count: 0,
  first_draw_number: '0001',
  last_draw_number: '0001',
  completed_at: batchCommitSuccess.completed_at,
} satisfies ImportCommitResult

const runRecord = {
  run_id: drawCommitSuccess.run_id,
  operation_type: 'DRAW_CSV_IMPORT',
  status: 'SUCCESS',
  lottery_type: 'BIG_LOTTO',
  source_filename: 'valid.csv',
  source_sha256: validPreview.manifest_sha256,
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

function requestUrl(callIndex: number): URL {
  return new URL(String(fetchMock.mock.calls[callIndex]?.[0]), 'http://localhost')
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

describe('ingestion run lottery query', () => {
  it('omits the lottery filter for ALL and sends each explicit internal enum', async () => {
    fetchMock.mockResolvedValue(apiResponse(emptyRuns))

    await listIngestionRuns()
    expect(requestUrl(0).searchParams.has('lottery_type')).toBe(false)

    for (const lotteryType of ['DAILY_539', 'BIG_LOTTO', 'POWER_LOTTO'] as const) {
      await listIngestionRuns({ lotteryType })
      expect(requestUrl(fetchMock.mock.calls.length - 1).searchParams.get('lottery_type')).toBe(
        lotteryType,
      )
    }
  })
})

describe('DataCenterPage batch ingestion', () => {
  it('renders explicit empty, audit, and disabled automation states', async () => {
    fetchMock.mockResolvedValue(apiResponse(emptyRuns))
    const wrapper = mount(DataCenterPage)
    await flushPromises()

    expect(wrapper.text()).toContain('No import file selected')
    expect(wrapper.text()).toContain('No ingestion runs have been recorded')
    expect(wrapper.get('[data-testid="batch-status"]').text()).toBe('NOT_COMMITTED')
    expect(wrapper.text()).toContain('B649')
    expect(wrapper.text()).not.toContain('BIG_LOTTO')
    expect(wrapper.get('[data-testid="manual-sync"]').attributes('disabled')).toBeDefined()
    expect(wrapper.get('[data-testid="csv-file"]').attributes('multiple')).toBeDefined()
    wrapper.unmount()
  })

  it('defaults history to ALL and prevents stale filtered runs from overwriting the latest selection', async () => {
    const staleRuns = deferred<Response>()
    const currentRuns = deferred<Response>()
    fetchMock
      .mockResolvedValueOnce(apiResponse(emptyRuns))
      .mockImplementationOnce(() => staleRuns.promise)
      .mockImplementationOnce(() => currentRuns.promise)
    const wrapper = mount(DataCenterPage)
    await flushPromises()

    expect(requestUrl(0).searchParams.has('lottery_type')).toBe(false)
    const filter = wrapper.get('[data-testid="ingestion-run-filter"]')
    await filter.setValue('BIG_LOTTO')
    await flushPromises()
    expect(requestUrl(1).searchParams.get('lottery_type')).toBe('BIG_LOTTO')

    await filter.setValue('DAILY_539')
    await flushPromises()
    expect((fetchMock.mock.calls[1]?.[1] as RequestInit).signal?.aborted).toBe(true)
    expect(requestUrl(2).searchParams.get('lottery_type')).toBe('DAILY_539')

    staleRuns.resolve(apiResponse(populatedRuns))
    await flushPromises()
    expect(wrapper.text()).not.toContain(runRecord.run_id)

    currentRuns.resolve(apiResponse(emptyRuns))
    await flushPromises()
    expect(wrapper.text()).toContain('No ingestion runs have been recorded')
    wrapper.unmount()
  })

  it('renders every issue with member and row context while escaping issue text', async () => {
    fetchMock
      .mockResolvedValueOnce(apiResponse(emptyRuns))
      .mockResolvedValueOnce(apiResponse(issueRichPreview))
    const wrapper = mount(DataCenterPage)
    await flushPromises()

    await selectFiles(wrapper, [file('issues.zip')])
    await wrapper.get('[data-testid="preview-all"]').trigger('click')
    await flushPromises()

    const details = wrapper.get('[data-testid="batch-issues-1"]')
    expect(details.element.tagName).toBe('DETAILS')
    expect(details.findAll('[data-testid^="batch-issue-1-"]')).toHaveLength(2)
    expect(details.text()).toContain('INVALID_DRAW_DATE')
    expect(details.text()).toContain('draw_date contains <img src=x onerror=alert(1)>.')
    expect(details.text()).toContain('Member: member.csv')
    expect(details.text()).toContain('Row 2')
    expect(details.text()).toContain('MISSING_REQUIRED_VALUE')
    expect(details.text()).toContain('Missing <tag> value.')
    expect(wrapper.get('[data-testid="batch-first-issue-1"]').text()).toContain('INVALID_DRAW_DATE')
    expect(wrapper.find('img').exists()).toBe(false)
    wrapper.unmount()
  })

  it('previews every file, exposes per-file validation, and commits selected files', async () => {
    fetchMock
      .mockResolvedValueOnce(apiResponse(emptyRuns))
      .mockResolvedValueOnce(apiResponse(invalidPreview))
      .mockResolvedValueOnce(apiResponse(validPreview))
      .mockResolvedValueOnce(apiResponse(batchCommitSuccess))
      .mockResolvedValueOnce(apiResponse(populatedRuns))
    const wrapper = mount(DataCenterPage)
    await flushPromises()

    await selectFiles(wrapper, [file('valid.csv'), file('invalid.csv')])
    await wrapper.get('[data-testid="preview-all"]').trigger('click')
    await flushPromises()

    expect(wrapper.findAll('tbody tr')).toHaveLength(2)
    expect(wrapper.text()).toContain(validPreview.manifest_sha256)
    expect(wrapper.text()).toContain('INVALID_DRAW_DATE')
    expect(wrapper.text()).toContain('1 accepted · 0 imported')
    expect(wrapper.text()).toContain('0 accepted · 0 imported')
    expect(wrapper.text()).toContain('1 failed')
    expect(wrapper.get('[data-testid="commit-selected-valid"]').attributes('disabled')).toBeDefined()

    await wrapper.get('[data-testid="batch-confirmation"]').setValue(true)
    await wrapper.get('[data-testid="commit-selected-valid"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-testid="batch-status"]').text()).toBe('PARTIAL_SUCCESS')
    expect(wrapper.text()).toContain(batchCommitSuccess.run_id)
    expect(wrapper.get('[data-testid="batch-identity-summary"]').text()).toContain(
      '1 committed chunks',
    )
    expect(wrapper.get('[data-testid="batch-identity-summary"]').text()).toContain(
      '0 failed chunks',
    )
    const previewBody = JSON.parse(
      String((fetchMock.mock.calls[1]?.[1] as RequestInit).body),
    ) as { files: Array<{ filename: string; content_base64: string }> }
    expect(previewBody.files.map((file) => file.filename)).toEqual(['valid.csv', 'invalid.csv'])
    const commitInit = fetchMock.mock.calls[3]?.[1] as RequestInit
    expect(JSON.parse(String(commitInit.body))).toMatchObject({
      files: [{ filename: 'valid.csv' }],
      expected_manifest_sha256: validPreview.manifest_sha256,
      parser_version: validPreview.parser_version,
    })
    wrapper.unmount()
  })

  it('preserves partial file status in the per-file preview', async () => {
    fetchMock
      .mockResolvedValueOnce(apiResponse(emptyRuns))
      .mockResolvedValueOnce(apiResponse(partialPreview))
    const wrapper = mount(DataCenterPage)
    await flushPromises()

    await selectFiles(wrapper, [file('partial.csv')])
    await wrapper.get('[data-testid="preview-all"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-testid="batch-file-1"]').text()).toContain('PARTIAL')
    wrapper.unmount()
  })

  it('fails closed when the committed batch does not match its preview', async () => {
    fetchMock
      .mockResolvedValueOnce(apiResponse(emptyRuns))
      .mockResolvedValueOnce(
        apiResponse({
          ...validPreview,
          files: [validFile, { ...validFile, source_filename: 'second.csv' }],
          summary: { ...validPreview.summary, discovered_files: 2, accepted_rows: 2 },
        }),
      )
      .mockResolvedValueOnce(
        apiResponse({
          ...validPreview,
          files: [validFile, { ...validFile, source_filename: 'second.csv' }],
          summary: { ...validPreview.summary, discovered_files: 2, accepted_rows: 2 },
        }),
      )
      .mockResolvedValueOnce(
        apiResponse(
          {
            error_code: 'BATCH_DIGEST_MISMATCH',
            message: 'Batch content does not match the preview manifest.',
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

    expect(wrapper.get('[data-testid="batch-status"]').text()).toBe('FAILED')
    expect(wrapper.text()).toContain('Batch content does not match')
    wrapper.unmount()
  })

  it('treats an HTTP-200 FAILED batch result as a failed commit', async () => {
    fetchMock
      .mockResolvedValueOnce(apiResponse(emptyRuns))
      .mockResolvedValueOnce(apiResponse(validPreview))
      .mockResolvedValueOnce(apiResponse(validPreview))
      .mockResolvedValueOnce(apiResponse(batchCommitFailure))
      .mockResolvedValueOnce(apiResponse(populatedRuns))
    const wrapper = mount(DataCenterPage)
    await flushPromises()

    await selectFiles(wrapper, [file('valid.csv')])
    await wrapper.get('[data-testid="preview-all"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="batch-confirmation"]').setValue(true)
    await wrapper.get('[data-testid="commit-selected-valid"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-testid="batch-status"]').text()).toBe('FAILED')
    expect(wrapper.text()).toContain('Existing draw data conflicts')
    wrapper.unmount()
  })

  it('renders successful and failed files distinctly for a partial batch', async () => {
    fetchMock
      .mockResolvedValueOnce(apiResponse(emptyRuns))
      .mockResolvedValueOnce(apiResponse(twoFilePreview))
      .mockResolvedValueOnce(apiResponse(twoFilePreview))
      .mockResolvedValueOnce(apiResponse(batchCommitPartial))
      .mockResolvedValueOnce(apiResponse(populatedRuns))
    const wrapper = mount(DataCenterPage)
    await flushPromises()

    await selectFiles(wrapper, [file('valid.csv'), file('second.csv')])
    await wrapper.get('[data-testid="preview-all"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="batch-confirmation"]').setValue(true)
    await wrapper.get('[data-testid="commit-all-valid"]').trigger('click')
    await flushPromises()

    const rows = wrapper.findAll('[data-testid^="batch-file-"]')
    expect(wrapper.get('[data-testid="batch-status"]').text()).toBe('PARTIAL_SUCCESS')
    expect(rows).toHaveLength(2)
    expect(rows[0]?.text()).toContain('SUCCESS')
    expect(rows[0]?.text()).not.toContain('FAILED')
    expect(rows[1]?.text()).toContain('FAILED')
    expect(rows[1]?.text()).not.toContain('SUCCESS')
    expect(wrapper.text()).toContain('1 imported')
    expect(wrapper.text()).toContain('1 failed')
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
    expect(wrapper.text()).toContain('No import file selected')
    expect(wrapper.text()).not.toContain(validPreview.manifest_sha256)
    wrapper.unmount()
  })

  it('unmount aborts an in-flight batch commit', async () => {
    const pending = deferred<Response>()
    fetchMock
      .mockResolvedValueOnce(apiResponse(emptyRuns))
      .mockResolvedValueOnce(apiResponse(validPreview))
      .mockResolvedValueOnce(apiResponse(validPreview))
      .mockImplementationOnce(() => pending.promise)
    const wrapper = mount(DataCenterPage)
    await flushPromises()
    await previewOne(wrapper)
    await wrapper.get('[data-testid="batch-confirmation"]').setValue(true)
    await wrapper.get('[data-testid="commit-selected-valid"]').trigger('click')
    await flushPromises()
    const commitInit = fetchMock.mock.calls[3]?.[1] as RequestInit

    wrapper.unmount()
    pending.resolve(apiResponse(batchCommitSuccess))
    await flushPromises()

    expect(commitInit.signal?.aborted).toBe(true)
  })

  it('a newer selection invalidates late commit success', async () => {
    const pending = deferred<Response>()
    fetchMock
      .mockResolvedValueOnce(apiResponse(emptyRuns))
      .mockResolvedValueOnce(apiResponse(validPreview))
      .mockResolvedValueOnce(apiResponse(validPreview))
      .mockImplementationOnce(() => pending.promise)
      .mockResolvedValueOnce(apiResponse(emptyRuns))
    const wrapper = mount(DataCenterPage)
    await flushPromises()
    await previewOne(wrapper)
    await wrapper.get('[data-testid="batch-confirmation"]').setValue(true)
    await wrapper.get('[data-testid="commit-selected-valid"]').trigger('click')
    await flushPromises()
    const commitInit = fetchMock.mock.calls[3]?.[1] as RequestInit

    await selectFiles(wrapper, [file('new.csv')])
    pending.resolve(apiResponse(batchCommitSuccess))
    await flushPromises()

    expect(commitInit.signal?.aborted).toBe(true)
    expect(wrapper.text()).toContain('new.csv')
    expect(wrapper.text()).not.toContain(batchCommitSuccess.run_id)
    wrapper.unmount()
  })

  it('a newer selection invalidates late commit errors', async () => {
    const pending = deferred<Response>()
    fetchMock
      .mockResolvedValueOnce(apiResponse(emptyRuns))
      .mockResolvedValueOnce(apiResponse(validPreview))
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
      .mockResolvedValueOnce(apiResponse(validPreview))
      .mockImplementationOnce(() => pending.promise)
    const wrapper = mount(DataCenterPage)
    await flushPromises()
    await previewOne(wrapper)
    await wrapper.get('[data-testid="batch-confirmation"]').setValue(true)

    const button = wrapper.get('[data-testid="commit-selected-valid"]')
    await Promise.all([button.trigger('click'), button.trigger('click')])
    await flushPromises()

    expect(fetchMock).toHaveBeenCalledTimes(4)
    pending.resolve(apiResponse(batchCommitSuccess))
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
      result: drawCommitSuccess,
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

describe('summary metric availability', () => {
  function rowMetrics(wrapper: VueWrapper) {
    return wrapper.findAllComponents(MetricCard).filter((card) => card.props('label') !== 'Files Selected')
  }

  function expectUnavailable(wrapper: VueWrapper, value: string, variant: string) {
    const cards = rowMetrics(wrapper)
    expect(cards).toHaveLength(3)
    for (const card of cards) {
      expect(card.props('value')).toBe(value)
      expect(card.get('.metric-card__value').text()).toBe(value)
      expect(card.get('.metric-card__subvalue').text()).not.toMatch(/\b0\b|^None$/)
      expect(card.classes()).toContain(`metric-card--${variant}`)
      expect(card.classes()).not.toContain('metric-card--success')
    }
  }

  it('distinguishes no selection, file reading, and not-previewed files from zero', async () => {
    const reading = deferred<string>()
    fetchMock.mockResolvedValueOnce(apiResponse(emptyRuns))
    const wrapper = mount(DataCenterPage)
    await flushPromises()

    expectUnavailable(wrapper, 'Not previewed', 'default')
    expect(wrapper.findComponent(MetricCard).props('value')).toBe(0)
    await selectFiles(wrapper, [file('valid.csv', reading.promise)])
    expectUnavailable(wrapper, 'Loading…', 'info')
    reading.resolve(csvText)
    await flushPromises()
    expectUnavailable(wrapper, 'Not previewed', 'default')
    wrapper.unmount()
  })

  it('does not replace prior counts with zero during re-preview or request failure', async () => {
    const pending = deferred<Response>()
    fetchMock
      .mockResolvedValueOnce(apiResponse(emptyRuns))
      .mockResolvedValueOnce(apiResponse(validPreview))
      .mockImplementationOnce(() => pending.promise)
    const wrapper = mount(DataCenterPage)
    await flushPromises()
    await previewOne(wrapper)
    expect(rowMetrics(wrapper).map((card) => card.props('value'))).toEqual([1, 0, 0])

    await wrapper.get('[data-testid="preview-all"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="batch-file-1"]').text()).toContain('PREVIEWING')
    expectUnavailable(wrapper, 'Loading…', 'info')
    pending.resolve(apiResponse({ message: 'Preview unavailable' }, 503))
    await flushPromises()
    expect(wrapper.get('[data-testid="batch-file-1"]').text()).toContain('ERROR')
    expectUnavailable(wrapper, 'Unavailable', 'danger')
    wrapper.unmount()
  })

  it('keeps network request failure unavailable', async () => {
    fetchMock
      .mockResolvedValueOnce(apiResponse(emptyRuns))
      .mockRejectedValueOnce(new TypeError('Failed to fetch'))
    const wrapper = mount(DataCenterPage)
    await flushPromises()
    await previewOne(wrapper)
    expectUnavailable(wrapper, 'Unavailable', 'danger')
    wrapper.unmount()
  })

  it.each([false, true])('does not confirm totals when a response omits file results (partial=%s)', async (partial) => {
    fetchMock
      .mockResolvedValueOnce(apiResponse(emptyRuns))
      .mockResolvedValueOnce(apiResponse({ ...validPreview, files: partial ? [validFile] : [] }))
    const wrapper = mount(DataCenterPage)
    await flushPromises()
    await selectFiles(wrapper, partial ? [file('valid.csv'), file('missing.csv')] : [file('valid.csv')])
    await wrapper.get('[data-testid="preview-all"]').trigger('click')
    await flushPromises()
    expectUnavailable(wrapper, 'Unavailable', 'danger')
    wrapper.unmount()
  })

  it('preserves numeric zero from authoritative empty-file results', async () => {
    const zeroPreview = {
      ...validPreview,
      files: [{ ...validFile, status: 'EXCLUDED', discovered_rows: 0, accepted_rows: 0 }],
      summary: { ...validPreview.summary, accepted_files: 0, excluded_files: 1, parsed_rows: 0, accepted_rows: 0 },
    } satisfies BatchImportPreview
    fetchMock
      .mockResolvedValueOnce(apiResponse(emptyRuns))
      .mockResolvedValueOnce(apiResponse(zeroPreview))
    const wrapper = mount(DataCenterPage)
    await flushPromises()
    await previewOne(wrapper)

    for (const card of rowMetrics(wrapper)) {
      expect(card.props('value')).toBe(0)
      expect(card.get('.metric-card__value').text()).toBe('0')
    }
    expect(rowMetrics(wrapper)[0]?.props('subvalue')).toBe('0 accepted')
    expect(rowMetrics(wrapper)[1]?.props('subvalue')).toBe('0 duplicate · 0 conflict')
    expect(rowMetrics(wrapper)[2]?.classes()).toContain('metric-card--success')
    await wrapper.get('[data-testid="cancel-batch"]').trigger('click')
    expectUnavailable(wrapper, 'Not previewed', 'default')
    wrapper.unmount()
  })
})

describe('Duplicates / Conflicts metric card truthfulness', () => {
  it('CASE 1: duplicates=0, conflicts>0 displays exact non-zero conflict count and non-default danger status without claiming 0 conflict', async () => {
    fetchMock
      .mockResolvedValueOnce(apiResponse(emptyRuns))
      .mockResolvedValueOnce(apiResponse(conflictOnlyPreview))
    const wrapper = mount(DataCenterPage)
    await flushPromises()

    await selectFiles(wrapper, [file('conflict.csv')])
    await wrapper.get('[data-testid="preview-all"]').trigger('click')
    await flushPromises()

    const card = wrapper.get('[data-testid="metric-duplicates-conflicts"]')
    expect(card.find('.metric-card__value').text()).toBe('3')
    expect(card.find('.metric-card__subvalue').text()).toBe('0 duplicate · 3 conflict')
    expect(card.text()).not.toContain('0 conflict')
    expect(card.classes()).toContain('metric-card--danger')
    expect(card.classes()).not.toContain('metric-card--default')
    wrapper.unmount()
  })

  it('CASE 2: duplicates>0, conflicts=0 preserves truthful duplicate count and warning status with 0 conflict', async () => {
    fetchMock
      .mockResolvedValueOnce(apiResponse(emptyRuns))
      .mockResolvedValueOnce(apiResponse(duplicateOnlyPreview))
    const wrapper = mount(DataCenterPage)
    await flushPromises()

    await selectFiles(wrapper, [file('duplicate.csv')])
    await wrapper.get('[data-testid="preview-all"]').trigger('click')
    await flushPromises()

    const card = wrapper.get('[data-testid="metric-duplicates-conflicts"]')
    expect(card.find('.metric-card__value').text()).toBe('2')
    expect(card.find('.metric-card__subvalue').text()).toBe('2 duplicate · 0 conflict')
    expect(card.classes()).toContain('metric-card--warning')
    expect(card.classes()).not.toContain('metric-card--default')
    expect(card.classes()).not.toContain('metric-card--danger')
    wrapper.unmount()
  })

  it('CASE 3: duplicates>0, conflicts>0 displays both counts correctly and sums them into the combined card value with danger status', async () => {
    fetchMock
      .mockResolvedValueOnce(apiResponse(emptyRuns))
      .mockResolvedValueOnce(apiResponse(mixedConflictDuplicatePreview))
    const wrapper = mount(DataCenterPage)
    await flushPromises()

    await selectFiles(wrapper, [file('mixed.csv')])
    await wrapper.get('[data-testid="preview-all"]').trigger('click')
    await flushPromises()

    const card = wrapper.get('[data-testid="metric-duplicates-conflicts"]')
    expect(card.find('.metric-card__value').text()).toBe('7')
    expect(card.find('.metric-card__subvalue').text()).toBe('4 duplicate · 3 conflict')
    expect(card.classes()).toContain('metric-card--danger')
    expect(card.classes()).not.toContain('metric-card--default')
    wrapper.unmount()
  })

  it('CASE 4: duplicates=0, conflicts=0 displays truthful zero state with default non-warning status', async () => {
    fetchMock
      .mockResolvedValueOnce(apiResponse(emptyRuns))
      .mockResolvedValueOnce(apiResponse(validPreview))
    const wrapper = mount(DataCenterPage)
    await flushPromises()

    const initialCard = wrapper.get('[data-testid="metric-duplicates-conflicts"]')
    expect(initialCard.find('.metric-card__value').text()).toBe('Not previewed')
    expect(initialCard.find('.metric-card__subvalue').text()).toBe('Preview results required')
    expect(initialCard.classes()).toContain('metric-card--default')
    expect(initialCard.classes()).not.toContain('metric-card--warning')
    expect(initialCard.classes()).not.toContain('metric-card--danger')

    await selectFiles(wrapper, [file('valid.csv')])
    await wrapper.get('[data-testid="preview-all"]').trigger('click')
    await flushPromises()

    const card = wrapper.get('[data-testid="metric-duplicates-conflicts"]')
    expect(card.find('.metric-card__value').text()).toBe('0')
    expect(card.find('.metric-card__subvalue').text()).toBe('0 duplicate · 0 conflict')
    expect(card.classes()).toContain('metric-card--default')
    expect(card.classes()).not.toContain('metric-card--warning')
    expect(card.classes()).not.toContain('metric-card--danger')
    wrapper.unmount()
  })

  it('aggregates duplicates and conflicts across multiple files', async () => {
    const multiFileConflictDuplicatePreview = {
      ...validPreview,
      files: [duplicateOnlyFile, conflictOnlyFile],
      summary: {
        ...validPreview.summary,
        discovered_files: 2,
        parsed_rows: 5,
        accepted_rows: 0,
        duplicate_rows: 2,
        conflict_rows: 3,
      },
    } satisfies BatchImportPreview

    fetchMock
      .mockResolvedValueOnce(apiResponse(emptyRuns))
      .mockResolvedValueOnce(apiResponse(multiFileConflictDuplicatePreview))
    const wrapper = mount(DataCenterPage)
    await flushPromises()

    await selectFiles(wrapper, [file('duplicate.csv'), file('conflict.csv')])
    await wrapper.get('[data-testid="preview-all"]').trigger('click')
    await flushPromises()

    const card = wrapper.get('[data-testid="metric-duplicates-conflicts"]')
    expect(card.find('.metric-card__value').text()).toBe('5')
    expect(card.find('.metric-card__subvalue').text()).toBe('2 duplicate · 3 conflict')
    expect(card.classes()).toContain('metric-card--danger')
    wrapper.unmount()
  })
})
