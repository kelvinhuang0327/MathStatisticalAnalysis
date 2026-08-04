<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'

import {
  commitHistoricalDrawImport,
  fileToBase64,
  previewHistoricalDrawImport,
  type HistoricalDrawImportFilter,
  type HistoricalDrawImportRequest,
  type HistoricalDrawImportResponse,
} from '../../api/historicalDrawImports'

type FileState = 'READING' | 'READY' | 'ERROR'

interface SelectedFile {
  id: number
  file: File
  encoded: string | null
  state: FileState
  error: string
}

const input = ref<HTMLInputElement>()
const files = ref<SelectedFile[]>([])
const lotteryFilter = ref<HistoricalDrawImportFilter>('ALL')
const preview = ref<HistoricalDrawImportResponse | null>(null)
const result = ref<HistoricalDrawImportResponse | null>(null)
const busy = ref<'PREVIEWING' | 'IMPORTING' | null>(null)
const confirmed = ref(false)
const message = ref('')
const generation = ref(0)
let nextId = 1
let controller: AbortController | undefined

const ready = computed(() => files.value.length > 0 && files.value.every((item) => item.state === 'READY'))
const activeResponse = computed(() => result.value ?? preview.value)

function selectFiles(event: Event): void {
  cancel(false)
  const selection = Array.from((event.currentTarget as HTMLInputElement).files ?? [])
  if (!selection.length) return
  const currentGeneration = generation.value
  files.value = selection.map((file) => ({
    id: nextId++,
    file,
    encoded: null,
    state: 'READING',
    error: '',
  }))
  void Promise.all(files.value.map((entry) => readFile(entry, currentGeneration)))
}

async function readFile(entry: SelectedFile, currentGeneration: number): Promise<void> {
  try {
    const encoded = await fileToBase64(entry.file)
    if (currentGeneration !== generation.value || !files.value.includes(entry)) return
    entry.encoded = encoded
    entry.state = 'READY'
  } catch {
    if (currentGeneration !== generation.value || !files.value.includes(entry)) return
    entry.state = 'ERROR'
    entry.error = 'The file could not be read.'
  }
}

async function previewImport(): Promise<void> {
  if (!ready.value || busy.value) return
  preview.value = null
  result.value = null
  message.value = ''
  confirmed.value = false
  busy.value = 'PREVIEWING'
  const currentGeneration = generation.value
  controller?.abort()
  controller = new AbortController()
  try {
    const response = await previewHistoricalDrawImport(buildRequest(), controller.signal)
    if (currentGeneration !== generation.value) return
    preview.value = response
  } catch (error: unknown) {
    if (currentGeneration !== generation.value || isAbort(error)) return
    message.value = error instanceof Error ? error.message : 'Historical draw preview failed.'
  } finally {
    if (currentGeneration === generation.value) busy.value = null
  }
}

async function commitImport(): Promise<void> {
  if (!ready.value || !preview.value || !confirmed.value || busy.value) return
  busy.value = 'IMPORTING'
  message.value = ''
  const currentGeneration = generation.value
  controller?.abort()
  controller = new AbortController()
  try {
    const response = await commitHistoricalDrawImport(buildRequest(), controller.signal)
    if (currentGeneration !== generation.value) return
    result.value = response
    confirmed.value = false
  } catch (error: unknown) {
    if (currentGeneration !== generation.value || isAbort(error)) return
    message.value = error instanceof Error ? error.message : 'Historical draw import failed.'
  } finally {
    if (currentGeneration === generation.value) busy.value = null
  }
}

function buildRequest(): HistoricalDrawImportRequest {
  return {
    files: files.value.map((entry) => ({
      filename: entry.file.name,
      content_base64: entry.encoded ?? '',
    })),
    lottery_filter: lotteryFilter.value,
  }
}

function invalidatePreview(): void {
  preview.value = null
  result.value = null
  confirmed.value = false
}

function cancel(clearInput = true): void {
  generation.value += 1
  controller?.abort()
  controller = undefined
  busy.value = null
  preview.value = null
  result.value = null
  confirmed.value = false
  message.value = ''
  files.value = []
  if (clearInput && input.value) input.value.value = ''
}

function reasonLabel(value: string | null): string {
  return value ?? '—'
}

function isAbort(error: unknown): boolean {
  return (error instanceof DOMException || error instanceof Error) && error.name === 'AbortError'
}

onBeforeUnmount(() => cancel())
</script>

<template>
  <article class="panel historical-import-panel" aria-labelledby="historical-import-title">
    <div class="panel__heading">
      <div>
        <p class="step-label">01B · Historical V2 archive import</p>
        <h2 id="historical-import-title">Import legacy CSV or ZIP draw history</h2>
      </div>
      <span class="status-badge">{{ busy ?? activeResponse?.status ?? 'READY' }}</span>
    </div>
    <p class="panel-copy">
      Upload one or many legacy files. Preview and commit use the same safe parser, preserve file/member/row provenance,
      skip identical draws, reject conflicts, and commit in chunks of at most 500 rows.
    </p>
    <div class="filter-grid">
      <label class="file-picker">
        <span>Select CSV or ZIP files</span>
        <input
          ref="input"
          data-testid="historical-draw-files"
          type="file"
          accept=".csv,.zip,text/csv,application/zip"
          multiple
          @change="selectFiles"
        />
      </label>
      <label>
        <span>Lottery filter</span>
        <select v-model="lotteryFilter" data-testid="historical-draw-filter" @change="invalidatePreview">
          <option value="ALL">All supported games</option>
          <option value="DAILY_539">今彩539</option>
          <option value="BIG_LOTTO">大樂透</option>
          <option value="POWER_LOTTO">威力彩</option>
        </select>
      </label>
    </div>
    <p v-if="files.length === 0" class="empty-copy">
      No historical archive selected. Uploaded bytes stay in this page session until preview, import, or cancellation.
    </p>
    <ul v-else class="file-list" aria-label="Selected historical files">
      <li v-for="entry in files" :key="entry.id">
        <strong>{{ entry.file.name }}</strong>
        <span>{{ entry.file.size }} bytes · {{ entry.state }}</span>
        <small v-if="entry.error" class="error-copy">{{ entry.error }}</small>
      </li>
    </ul>
    <div class="filter-actions">
      <button class="button button--primary" data-testid="historical-draw-preview" type="button" :disabled="!ready || !!busy" @click="previewImport">
        {{ busy === 'PREVIEWING' ? 'Previewing…' : 'Preview historical import' }}
      </button>
      <button class="button button--quiet" type="button" :disabled="!files.length || !!busy" @click="cancel()">
        Cancel
      </button>
    </div>
    <p v-if="message" class="state-panel state-panel--error" aria-live="polite">{{ message }}</p>
    <div v-if="activeResponse" class="historical-import-result" data-testid="historical-draw-result">
      <div class="result-summary">
        <strong>{{ activeResponse.status }}</strong>
        <span v-if="activeResponse.run_id">Run {{ activeResponse.run_id }}</span>
        <span>{{ activeResponse.summary.imported_rows }} imported</span>
        <span>{{ activeResponse.summary.duplicate_rows }} duplicate</span>
        <span>{{ activeResponse.summary.conflict_rows }} conflict</span>
        <span>{{ activeResponse.summary.failed_rows }} failed</span>
      </div>
      <label v-if="preview && !result" class="confirmation">
        <input v-model="confirmed" data-testid="historical-draw-confirmation" type="checkbox" />
        <span>I confirm this preview should be committed to the configured Historical V2 database.</span>
      </label>
      <button
        v-if="preview && !result"
        class="button button--primary"
        data-testid="historical-draw-commit"
        type="button"
        :disabled="!confirmed || !!busy"
        @click="commitImport"
      >
        {{ busy === 'IMPORTING' ? 'Importing…' : 'Commit historical import' }}
      </button>
      <div class="table-wrap">
        <table>
          <caption>Historical import file outcomes</caption>
          <thead><tr><th>File</th><th>Status</th><th>Rows</th><th>Reasons</th></tr></thead>
          <tbody>
            <tr v-for="file in activeResponse.files" :key="file.source_sha256">
              <td><strong>{{ file.filename }}</strong><small>{{ file.source_sha256 }}</small></td>
              <td><span class="status-badge">{{ file.status }}</span></td>
              <td>{{ file.imported_rows }} imported · {{ file.failed_rows }} failed · {{ file.duplicate_rows }} duplicate</td>
              <td>
                <ul class="reason-list">
                  <li v-for="row in file.rows.filter((item) => item.reason_code)" :key="`${row.member_path}-${row.source_row_number}-${row.reason_code}`">
                    {{ reasonLabel(row.reason_code) }}<small>{{ row.member_path }} · {{ row.message }}</small>
                  </li>
                  <li v-if="!file.rows.some((item) => item.reason_code)">No exclusions or errors</li>
                </ul>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </article>
</template>
