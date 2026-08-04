// @vitest-environment jsdom

import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import HistoricalDrawImportPanel from '../src/features/data-center/HistoricalDrawImportPanel.vue'

const previewPayload = {
  run_id: null,
  status: 'PREVIEW',
  lottery_filter: 'POWER_LOTTO',
  files: [
    {
      filename: 'legacy.zip',
      source_sha256: 'a'.repeat(64),
      status: 'PARTIAL_SUCCESS',
      discovered_members: 2,
      accepted_files: 1,
      excluded_files: 1,
      parsed_rows: 1,
      valid_rows: 1,
      excluded_rows: 1,
      duplicate_rows: 0,
      conflict_rows: 0,
      imported_rows: 0,
      failed_rows: 0,
      rows: [
        {
          source_filename: 'legacy.zip',
          source_sha256: 'a'.repeat(64),
          member_path: '賓果.csv',
          member_sha256: null,
          source_row_number: null,
          lottery_type: null,
          draw_number: null,
          draw_date: null,
          main_numbers: [],
          special_numbers: [],
          disposition: 'EXCLUDED',
          reason_code: 'BINGO_EXCLUDED',
          normalized_record_hash: null,
          message: 'Bingo excluded',
          historical_run_id: null,
        },
      ],
    },
  ],
  chunks: [],
  summary: {
    discovered_files: 1,
    accepted_files: 1,
    excluded_files: 1,
    parsed_rows: 1,
    valid_rows: 1,
    excluded_rows: 1,
    duplicate_rows: 0,
    conflict_rows: 0,
    imported_rows: 0,
    failed_rows: 0,
    committed_chunks: 0,
    failed_chunks: 0,
  },
  row_results: [],
}

const committedPayload = {
  ...previewPayload,
  run_id: 'run-1',
  status: 'COMPLETED',
  files: previewPayload.files.map((file) => ({ ...file, status: 'ACCEPTED', imported_rows: 1 })),
  summary: { ...previewPayload.summary, imported_rows: 1, excluded_rows: 0 },
}

let fetchMock: ReturnType<typeof vi.fn<typeof fetch>>

function selectedFile(): File {
  return {
    name: 'legacy.zip',
    size: 8,
    arrayBuffer: vi.fn().mockResolvedValue(new Uint8Array([1, 2, 3]).buffer),
  } as unknown as File
}

beforeEach(() => {
  fetchMock = vi.fn<typeof fetch>()
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => vi.unstubAllGlobals())

describe('HistoricalDrawImportPanel', () => {
  it('previews CSV/ZIP selections, renders exclusions, and commits after confirmation', async () => {
    fetchMock
      .mockResolvedValueOnce(new Response(JSON.stringify(previewPayload), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(committedPayload), { status: 200 }))
    const wrapper = mount(HistoricalDrawImportPanel)
    const input = wrapper.get('[data-testid="historical-draw-files"]')
    Object.defineProperty(input.element, 'files', { configurable: true, value: [selectedFile()] })
    await input.trigger('change')
    await flushPromises()

    await wrapper.get('[data-testid="historical-draw-preview"]').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('BINGO_EXCLUDED')
    expect(wrapper.get('[data-testid="historical-draw-confirmation"]')).toBeTruthy()

    await wrapper.get('[data-testid="historical-draw-confirmation"]').setValue(true)
    await wrapper.get('[data-testid="historical-draw-commit"]').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('COMPLETED')
    expect(wrapper.text()).toContain('run-1')
    expect(fetchMock).toHaveBeenCalledTimes(2)
    wrapper.unmount()
  })
})
