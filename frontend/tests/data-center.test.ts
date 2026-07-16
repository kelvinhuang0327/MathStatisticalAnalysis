// @vitest-environment jsdom

import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type {
  DrawImportPreview,
  ImportCommitResult,
  IngestionRunPage,
} from '../src/api/drawData'
import DataCenterPage from '../src/features/data-center/DataCenterPage.vue'

const content =
  'lottery_type,draw_number,draw_date,main_numbers,special_numbers\n' +
  'BIG_LOTTO,0001,2026-07-16,1|3|9|17|24|49,7\n'

const validPreview = {
  filename: 'draws.csv',
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
  ignored_columns: ['note'],
  normalized_preview: [
    {
      source_row_number: 2,
      lottery_type: 'BIG_LOTTO',
      draw_number: '0001',
      draw_date: '2026-07-16',
      main_numbers: [1, 3, 9, 17, 24, 49],
      special_numbers: [7],
      source_reference: '<img src=x onerror=alert(1)>',
      normalized_record_hash: 'b'.repeat(64),
    },
  ],
  validation_errors: [],
  preview_truncated: false,
  errors_truncated: false,
} satisfies DrawImportPreview

const commitResult = {
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
  records: [
    {
      run_id: commitResult.run_id,
      operation_type: 'DRAW_CSV_IMPORT',
      status: 'SUCCESS',
      lottery_type: 'BIG_LOTTO',
      source_filename: 'draws.csv',
      source_sha256: validPreview.content_sha256,
      parser_version: validPreview.parser_version,
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
    },
  ],
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

async function chooseCsv(wrapper: VueWrapper): Promise<void> {
  const input = wrapper.get('[data-testid="csv-file"]')
  const file = {
    name: 'draws.csv',
    size: new TextEncoder().encode(content).length,
    text: vi.fn().mockResolvedValue(content),
  } as unknown as File
  Object.defineProperty(input.element, 'files', { configurable: true, value: [file] })
  await input.trigger('change')
  await flushPromises()
}

beforeEach(() => {
  fetchMock = vi.fn<typeof fetch>()
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('DataCenterPage', () => {
  it('renders the explicit empty state without unsupported automation controls', async () => {
    fetchMock.mockResolvedValue(apiResponse(emptyRuns))
    const wrapper = mount(DataCenterPage)
    await flushPromises()

    expect(wrapper.text()).toContain('No CSV selected')
    expect(wrapper.text()).toContain('No ingestion runs have been recorded')
    expect(wrapper.get('[data-testid="preview-action"]').attributes('disabled')).toBeDefined()
    const buttonLabels = wrapper.findAll('button').map((button) => button.text())
    expect(buttonLabels).not.toContain('Fetch latest')
    expect(buttonLabels).not.toContain('Missing scan')
    expect(buttonLabels).not.toContain('Backfill')
    wrapper.unmount()
  })

  it('renders a valid preview as text and requires confirmation before commit', async () => {
    fetchMock
      .mockResolvedValueOnce(apiResponse(emptyRuns))
      .mockResolvedValueOnce(apiResponse(validPreview))
      .mockResolvedValueOnce(apiResponse(commitResult))
      .mockResolvedValueOnce(apiResponse(populatedRuns))
    const wrapper = mount(DataCenterPage)
    await flushPromises()
    await chooseCsv(wrapper)

    expect(wrapper.text()).toContain('draws.csv')
    expect(wrapper.text()).toContain(`${content.length} B`)
    await wrapper.get('[data-testid="preview-action"]').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain(validPreview.content_sha256)
    expect(wrapper.text()).toContain('1 · 3 · 9 · 17 · 24 · 49')
    expect(wrapper.text()).toContain('<img src=x onerror=alert(1)>')
    expect(wrapper.find('img').exists()).toBe(false)
    expect(wrapper.text()).toContain('Ignored columns')
    expect(wrapper.get('[data-testid="commit-action"]').attributes('disabled')).toBeDefined()

    await wrapper.get('[data-testid="commit-confirmation"]').setValue(true)
    expect(wrapper.get('[data-testid="commit-action"]').attributes('disabled')).toBeUndefined()
    await wrapper.get('[data-testid="commit-action"]').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('Commit complete')
    expect(wrapper.text()).toContain(commitResult.run_id)
    expect(wrapper.text()).toContain('draws.csv')
    expect(wrapper.find('.file-facts').exists()).toBe(false)
    expect(wrapper.get('[data-testid="preview-action"]').attributes('disabled')).toBeDefined()

    const previewCall = fetchMock.mock.calls[1]
    const previewInit = previewCall?.[1] as RequestInit
    expect(JSON.parse(String(previewInit.body))).toEqual({
      filename: 'draws.csv',
      csv_text: content,
    })
    const commitCall = fetchMock.mock.calls[2]
    const commitInit = commitCall?.[1] as RequestInit
    expect(JSON.parse(String(commitInit.body))).toMatchObject({
      expected_sha256: validPreview.content_sha256,
      parser_version: validPreview.parser_version,
      conflict_policy: 'REJECT',
    })
    wrapper.unmount()
  })

  it('renders structured validation errors and never offers commit', async () => {
    const invalidPreview = {
      ...validPreview,
      is_valid: false,
      valid_rows: 0,
      validation_error_count: 1,
      normalized_preview: [],
      validation_errors: [
        {
          code: 'INVALID_DRAW_DATE',
          message: 'draw_date is not a valid calendar date.',
          row_number: 2,
          field: 'draw_date',
        },
      ],
    } satisfies DrawImportPreview
    fetchMock
      .mockResolvedValueOnce(apiResponse(emptyRuns))
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
    const wrapper = mount(DataCenterPage)
    await flushPromises()
    await chooseCsv(wrapper)
    await wrapper.get('[data-testid="preview-action"]').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('Validation requires attention')
    expect(wrapper.text()).toContain('INVALID_DRAW_DATE')
    expect(wrapper.text()).toContain('draw_date is not a valid calendar date.')
    expect(wrapper.find('[data-testid="commit-action"]').exists()).toBe(false)
    wrapper.unmount()
  })

  it('shows a conflict result without clearing the selected CSV', async () => {
    const failed = {
      ...commitResult,
      status: 'FAILED',
      inserted_count: 0,
      conflict_count: 1,
    } satisfies ImportCommitResult
    fetchMock
      .mockResolvedValueOnce(apiResponse(populatedRuns))
      .mockResolvedValueOnce(apiResponse(validPreview))
      .mockResolvedValueOnce(
        apiResponse(
          {
            error_code: 'EXISTING_DRAW_CONFLICT',
            message: 'Existing draw data conflicts; the batch inserted no draws.',
            result: failed,
          },
          409,
        ),
      )
    const wrapper = mount(DataCenterPage)
    await flushPromises()
    await chooseCsv(wrapper)
    await wrapper.get('[data-testid="preview-action"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="commit-confirmation"]').setValue(true)
    await wrapper.get('[data-testid="commit-action"]').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('Conflict rejected')
    expect(wrapper.text()).toContain('the batch inserted no draws')
    expect(wrapper.find('.file-facts').exists()).toBe(true)
    expect(fetchMock).toHaveBeenCalledTimes(3)
    wrapper.unmount()
  })
})
