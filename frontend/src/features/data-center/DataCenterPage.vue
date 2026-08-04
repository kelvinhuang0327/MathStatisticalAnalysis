<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'

import {
  commitBatchDrawImport,
  listIngestionRuns,
  previewBatchDrawImport,
  runDrawSync,
  type BatchImportCommit,
  type BatchImportPreview,
  type DrawSyncOperation,
  type DrawSyncResponse,
  type IngestionRun,
} from '../../api/drawData'

type FileStatus =
  | 'READING'
  | 'NOT_PREVIEWED'
  | 'PREVIEWING'
  | 'VALID'
  | 'PARTIAL'
  | 'EXCLUDED'
  | 'INVALID'
  | 'ERROR'
type CommitStatus = 'NOT_COMMITTED' | 'COMMITTING' | 'SUCCESS' | 'FAILED'
type LoadState = 'loading' | 'ready' | 'empty' | 'error'

interface BatchFile {
  id: number
  file: File
  filename: string
  size: number
  contentBase64: string
  selected: boolean
  previewStatus: FileStatus
  commitStatus: CommitStatus
  preview: BatchImportPreview | null
  fileResults: BatchImportPreview['files']
  result: BatchImportCommit | null
  error: string
}

const fileInput = ref<HTMLInputElement>()
const files = ref<BatchFile[]>([])
const batchConfirmed = ref(false)
const previewBusy = ref(false)
const commitBusy = ref(false)
const ingestionRuns = ref<IngestionRun[]>([])
const runsState = ref<LoadState>('loading')
const runsMessage = ref('')
const syncForm = reactive({ dateFrom: '', dateTo: '' })
const syncPending = ref<DrawSyncOperation | null>(null)
const syncResult = ref<DrawSyncResponse | null>(null)
const syncMessage = ref('')
let nextFileId = 1
let selectionGeneration = 0
let runsGeneration = 0
let syncGeneration = 0
let unmounted = false
let runsController: AbortController | undefined
let syncController: AbortController | undefined
const previewControllers = new Map<number, AbortController>()
const commitControllers = new Map<number, AbortController>()

const validFiles = computed(() =>
  files.value.filter(
    (entry) =>
      (entry.previewStatus === 'VALID' || entry.previewStatus === 'PARTIAL') &&
      entry.contentBase64,
  ),
)
const selectedValidFiles = computed(() => validFiles.value.filter((entry) => entry.selected))
const batchStatus = computed(() => {
  const successCount = files.value.filter((entry) => entry.commitStatus === 'SUCCESS').length
  const failedCount = files.value.filter((entry) => entry.commitStatus === 'FAILED').length
  if (successCount === 0 && failedCount === 0) return 'NOT_COMMITTED'
  if (successCount === validFiles.value.length && validFiles.value.length > 0) return 'SUCCESS'
  if (successCount === 0) return 'FAILED'
  return 'PARTIAL_SUCCESS'
})

async function selectFiles(event: Event): Promise<void> {
  cancelBatch(false)
  const input = event.currentTarget as HTMLInputElement
  const selected = Array.from(input.files ?? [])
  if (!selected.length) return
  const generation = selectionGeneration
  const entries = selected.map((file) =>
    reactive<BatchFile>({
      id: nextFileId++,
      file,
      filename: file.name,
      size: file.size,
      contentBase64: '',
      selected: true,
      previewStatus: 'READING',
      commitStatus: 'NOT_COMMITTED',
      preview: null,
      fileResults: [],
      result: null,
      error: '',
    }),
  )
  files.value = entries
  await Promise.all(
    entries.map(async (entry) => {
      try {
        const content = await readFileAsBase64(entry.file)
        if (!isCurrentEntry(generation, entry)) return
        entry.contentBase64 = content
        entry.previewStatus = 'NOT_PREVIEWED'
      } catch {
        if (!isCurrentEntry(generation, entry)) return
        entry.previewStatus = 'ERROR'
        entry.error = 'The file could not be read as UTF-8 text.'
      }
    }),
  )
}

async function previewAll(): Promise<void> {
  if (previewBusy.value) return
  previewBusy.value = true
  const entries = files.value.filter(
    (entry) => entry.contentBase64 && entry.commitStatus !== 'SUCCESS',
  )
  const controller = new AbortController()
  previewControllers.set(0, controller)
  const selection = selectionGeneration
  for (const entry of entries) {
    entry.previewStatus = 'PREVIEWING'
    entry.preview = null
    entry.fileResults = []
    entry.result = null
    entry.commitStatus = 'NOT_COMMITTED'
    entry.error = ''
  }
  try {
    const outcome = await previewBatchDrawImport(
      {
        files: entries.map((entry) => ({
          filename: entry.filename,
          content_base64: entry.contentBase64,
        })),
      },
      controller.signal,
    )
    if (!isCurrentSelection(selection)) return
    applyBatchPreview(entries, outcome.preview, outcome.message)
  } catch (error: unknown) {
    if (!isCurrentSelection(selection) || isAbort(error)) return
    for (const entry of entries) {
      entry.previewStatus = 'ERROR'
      entry.error = error instanceof Error ? error.message : 'Batch preview failed.'
    }
  } finally {
    if (previewControllers.get(0) === controller) previewControllers.delete(0)
    previewBusy.value = false
    batchConfirmed.value = false
  }
}

async function commitFiles(entries: BatchFile[]): Promise<void> {
  if (!batchConfirmed.value || commitBusy.value || entries.length === 0) return
  commitBusy.value = true
  const controller = new AbortController()
  commitControllers.set(0, controller)
  const selection = selectionGeneration
  const payloads = entries.map((entry) => ({
    filename: entry.filename,
    content_base64: entry.contentBase64,
  }))
  for (const entry of entries) {
    entry.commitStatus = 'COMMITTING'
    entry.error = ''
  }
  try {
    const previewOutcome = await previewBatchDrawImport({ files: payloads }, controller.signal)
    if (!isCurrentSelection(selection)) return
    if (!previewOutcome.ok || !previewOutcome.preview?.is_valid) {
      applyBatchPreview(entries, previewOutcome.preview, previewOutcome.message)
      for (const entry of entries) {
        entry.commitStatus = 'FAILED'
      }
      return
    }
    applyBatchPreview(entries, previewOutcome.preview, '')
    const outcome = await commitBatchDrawImport(
      {
        files: payloads,
        expected_manifest_sha256: previewOutcome.preview.manifest_sha256,
        parser_version: previewOutcome.preview.parser_version,
      },
      controller.signal,
    )
    if (!isCurrentSelection(selection)) return
    for (const entry of entries) {
      entry.result = outcome.result
      const committed = outcome.ok && outcome.result?.status === 'SUCCESS'
      entry.commitStatus = committed ? 'SUCCESS' : 'FAILED'
      entry.error = committed
        ? ''
        : (outcome.message ?? outcome.result?.error_summary ?? 'Batch import was not committed.')
      if (committed) entry.contentBase64 = ''
    }
  } catch (error: unknown) {
    if (!isCurrentSelection(selection) || isAbort(error)) return
    for (const entry of entries) {
      entry.commitStatus = 'FAILED'
      entry.error = error instanceof Error ? error.message : 'Batch commit failed.'
    }
  } finally {
    if (commitControllers.get(0) === controller) commitControllers.delete(0)
    commitBusy.value = false
    batchConfirmed.value = false
    await loadIngestionRuns()
  }
}

function cancelBatch(clearInput = true): void {
  selectionGeneration += 1
  for (const controller of previewControllers.values()) controller.abort()
  for (const controller of commitControllers.values()) controller.abort()
  previewControllers.clear()
  commitControllers.clear()
  previewBusy.value = false
  commitBusy.value = false
  batchConfirmed.value = false
  for (const entry of files.value) entry.contentBase64 = ''
  files.value = []
  if (clearInput && fileInput.value) fileInput.value.value = ''
}

async function runSync(operation: DrawSyncOperation): Promise<void> {
  if (!syncForm.dateFrom || !syncForm.dateTo || syncPending.value) return
  syncController?.abort()
  const controller = new AbortController()
  syncController = controller
  const generation = ++syncGeneration
  syncPending.value = operation
  syncMessage.value = ''
  syncResult.value = null
  try {
    const result = await runDrawSync(
      operation,
      {
        lottery_type: 'BIG_LOTTO',
        date_from: syncForm.dateFrom,
        date_to: syncForm.dateTo,
      },
      controller.signal,
    )
    if (unmounted || generation !== syncGeneration) return
    syncResult.value = result
    syncMessage.value = `${result.operation_type} completed with ${result.result.inserted_count} inserted and ${result.result.skipped_count} duplicates.`
    await loadIngestionRuns()
  } catch (error: unknown) {
    if (unmounted || generation !== syncGeneration || isAbort(error)) return
    syncMessage.value = error instanceof Error ? error.message : 'Draw automation failed.'
  } finally {
    if (!unmounted && generation === syncGeneration) {
      syncPending.value = null
      if (syncController === controller) syncController = undefined
    }
  }
}

async function loadIngestionRuns(): Promise<void> {
  runsController?.abort()
  const controller = new AbortController()
  runsController = controller
  const generation = ++runsGeneration
  runsState.value = 'loading'
  runsMessage.value = ''
  try {
    const page = await listIngestionRuns({}, controller.signal)
    if (unmounted || generation !== runsGeneration) return
    ingestionRuns.value = page.records
    runsState.value = page.records.length ? 'ready' : 'empty'
  } catch (error: unknown) {
    if (unmounted || generation !== runsGeneration || isAbort(error)) return
    runsState.value = 'error'
    runsMessage.value = error instanceof Error ? error.message : 'Ingestion runs could not load.'
  }
}

function isCurrentEntry(generation: number, entry: BatchFile): boolean {
  return (
    !unmounted &&
    generation === selectionGeneration &&
    files.value.some((candidate) => candidate.id === entry.id)
  )
}

function isCurrentSelection(generation: number): boolean {
  return !unmounted && generation === selectionGeneration
}

function applyBatchPreview(
  entries: BatchFile[],
  preview: BatchImportPreview | null,
  fallbackMessage?: string,
): void {
  for (const entry of entries) {
    entry.preview = preview
    entry.fileResults = preview ? resultsForEntry(preview, entry) : []
    const accepted = entryAcceptedRows(entry)
    const hasFailure = entry.fileResults.some((file) => file.status === 'FAILED')
    const hasPartial = entry.fileResults.some((file) => file.status === 'PARTIAL')
    const hasInvalid = entry.fileResults.some((file) => file.status === 'INVALID')
    const hasExcluded = entry.fileResults.length > 0 && entry.fileResults.every((file) => file.status === 'EXCLUDED')
    entry.previewStatus = hasFailure
      ? 'ERROR'
      : accepted > 0 && hasPartial
        ? 'PARTIAL'
        : accepted > 0 && !hasInvalid
        ? 'VALID'
        : hasExcluded
          ? 'EXCLUDED'
          : hasInvalid
            ? 'INVALID'
            : 'ERROR'
    const firstIssue = entry.fileResults.flatMap((file) => file.issues)[0]
    entry.error = firstIssue
      ? `${firstIssue.code}: ${firstIssue.message}`
      : fallbackMessage ?? ''
  }
}

function resultsForEntry(
  preview: BatchImportPreview,
  entry: BatchFile,
): BatchImportPreview['files'] {
  return preview.files.filter(
    (file) =>
      file.source_filename === entry.filename ||
      file.source_locator.startsWith(`${entry.filename}!`),
  )
}

function entryAcceptedRows(entry: BatchFile): number {
  return entry.fileResults.reduce((total, file) => total + file.accepted_rows, 0)
}

function entryFailedRows(entry: BatchFile): number {
  return entry.fileResults.reduce((total, file) => total + file.failed_rows, 0)
}

function entryExcludedRows(entry: BatchFile): number {
  return entry.fileResults.reduce((total, file) => total + file.excluded_rows, 0)
}

async function readFileAsBase64(file: File): Promise<string> {
  const buffer =
    typeof file.arrayBuffer === 'function'
      ? await file.arrayBuffer()
      : new TextEncoder().encode(await file.text()).buffer
  return arrayBufferToBase64(buffer)
}

function arrayBufferToBase64(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer)
  let binary = ''
  const chunkSize = 0x8000
  for (let offset = 0; offset < bytes.length; offset += chunkSize) {
    binary += String.fromCharCode(...bytes.subarray(offset, offset + chunkSize))
  }
  return btoa(binary)
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  return `${(bytes / 1024).toFixed(1)} KiB`
}

function displayText(value: unknown): string {
  return typeof value === 'string' && value ? value : '—'
}

function formatTimestamp(value: unknown): string {
  if (typeof value !== 'string' || !value) return '—'
  const parsed = new Date(value)
  return Number.isNaN(parsed.valueOf()) ? value : parsed.toLocaleString()
}

function isAbort(error: unknown): boolean {
  return (error instanceof DOMException || error instanceof Error) && error.name === 'AbortError'
}

onMounted(loadIngestionRuns)
onBeforeUnmount(() => {
  unmounted = true
  cancelBatch()
  runsController?.abort()
  syncController?.abort()
})
</script>

<template>
  <section class="workspace-page" aria-labelledby="data-center-title">
    <header class="page-heading">
      <div>
        <p class="eyebrow">Non-multiticket migration · audited local data</p>
        <h1 id="data-center-title">Data Center</h1>
        <p class="page-intro">
          Preview one or many legacy CSV, TXT, or ZIP files, commit only explicit selections, or
          run a bounded provider synchronization. The selected batch uses one atomic audit run.
        </p>
      </div>
      <div class="scope-card" aria-label="Batch status">
        <span>Batch status</span>
        <strong data-testid="batch-status">{{ batchStatus }}</strong>
        <small>L649 · T539 · P638 · atomic REJECT conflicts</small>
      </div>
    </header>

    <article class="panel upload-panel">
      <div class="panel__heading">
        <div>
          <p class="step-label">01 · Select</p>
          <h2>Choose legacy CSV, TXT, or ZIP files</h2>
        </div>
        <button class="button button--quiet" data-testid="cancel-batch" type="button" @click="cancelBatch()">
          Cancel batch
        </button>
      </div>
      <label class="file-picker">
        <span>Select one or more import files</span>
        <input
          ref="fileInput"
          data-testid="csv-file"
          type="file"
          accept=".csv,.txt,.zip,text/csv,text/plain,application/zip"
          multiple
          @change="selectFiles"
        />
      </label>
      <p v-if="files.length === 0" class="empty-copy">
        No import file selected. Raw content remains only in this page session and is discarded after a
        successful commit or cancellation.
      </p>
      <div v-else class="filter-actions">
        <button
          class="button button--primary"
          data-testid="preview-all"
          type="button"
          :disabled="previewBusy || commitBusy"
          @click="previewAll"
        >
          {{ previewBusy ? 'Previewing…' : 'Preview all files' }}
        </button>
      </div>
    </article>

    <div v-if="files.length" class="table-wrap">
      <table>
        <caption>Per-file preview and commit status</caption>
        <thead>
          <tr>
            <th>Select</th><th>File</th><th>Digest / parser</th><th>Validation</th>
            <th>Counts</th><th>Commit</th><th>Run / error</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="entry in files" :key="entry.id" :data-testid="`batch-file-${entry.id}`">
            <td>
              <input
                v-model="entry.selected"
                type="checkbox"
                :aria-label="`Select ${entry.filename} for commit`"
                :disabled="!['VALID', 'PARTIAL'].includes(entry.previewStatus) || entry.commitStatus === 'SUCCESS'"
              />
            </td>
            <td><strong>{{ entry.filename }}</strong><small>{{ formatBytes(entry.size) }}</small></td>
            <td>
              <code>{{ entry.preview?.manifest_sha256 ?? '—' }}</code>
              <small>{{ entry.preview?.parser_version ?? '—' }}</small>
            </td>
            <td><span class="status-badge">{{ entry.previewStatus }}</span></td>
            <td>
              {{ entryAcceptedRows(entry) }} valid ·
              {{ entryFailedRows(entry) }} invalid ·
              {{ entryExcludedRows(entry) }} excluded
            </td>
            <td><span class="status-badge">{{ entry.commitStatus }}</span></td>
            <td>
              <code>{{ displayText(entry.result?.run_id) }}</code>
              <small v-if="entry.error" class="error-copy">{{ entry.error }}</small>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <article v-if="validFiles.length" class="panel commit-box">
      <p class="step-label">02 · Confirm</p>
      <label class="confirmation">
        <input v-model="batchConfirmed" data-testid="batch-confirmation" type="checkbox" />
        <span>
          I confirm the selected valid files should be committed as one atomic batch with conflict
          policy REJECT. A conflict rolls back every draw in this batch.
        </span>
      </label>
      <div class="filter-actions">
        <button
          class="button button--primary"
          data-testid="commit-all-valid"
          type="button"
          :disabled="!batchConfirmed || commitBusy"
          @click="commitFiles(validFiles)"
        >
          Commit all valid files
        </button>
        <button
          class="button button--quiet"
          data-testid="commit-selected-valid"
          type="button"
          :disabled="!batchConfirmed || commitBusy || selectedValidFiles.length === 0"
          @click="commitFiles(selectedValidFiles)"
        >
          Commit selected valid files
        </button>
      </div>
    </article>

    <article class="panel automation-panel" aria-labelledby="automation-title">
      <div class="panel__heading">
        <div>
          <p class="step-label">03 · Automated source boundary</p>
          <h2 id="automation-title">Bounded draw synchronization</h2>
        </div>
        <span class="status-badge">{{ syncPending ? 'RUNNING' : 'READY' }}</span>
      </div>
      <div class="filter-grid">
        <label><span>Date from</span><input v-model="syncForm.dateFrom" data-testid="sync-date-from" type="date" /></label>
        <label><span>Date to</span><input v-model="syncForm.dateTo" data-testid="sync-date-to" type="date" /></label>
      </div>
      <div class="filter-actions" aria-label="Draw synchronization actions">
        <button class="button button--primary" data-testid="manual-sync" type="button" :disabled="!!syncPending || !syncForm.dateFrom || !syncForm.dateTo" @click="runSync('manual')">Manual sync</button>
        <button class="button button--quiet" type="button" :disabled="!!syncPending || !syncForm.dateFrom || !syncForm.dateTo" @click="runSync('missing-scan')">Scan missing draws</button>
        <button class="button button--quiet" type="button" :disabled="!!syncPending || !syncForm.dateFrom || !syncForm.dateTo" @click="runSync('backfill')">Bounded backfill</button>
        <button class="button button--quiet" data-testid="scheduled-sync" type="button" :disabled="!!syncPending || !syncForm.dateFrom || !syncForm.dateTo" @click="runSync('scheduled')">Run scheduled trigger</button>
      </div>
      <p v-if="syncMessage" class="state-panel" :class="{ 'state-panel--error': !syncResult }" aria-live="polite">
        {{ syncMessage }}
      </p>
    </article>

    <section class="log-section" aria-labelledby="ingestion-log-title">
      <div class="section-heading">
        <div><p class="eyebrow">Append-only audit</p><h2 id="ingestion-log-title">Recent ingestion runs</h2></div>
        <a class="button button--quiet" href="#/history">Open full history</a>
      </div>
      <p v-if="runsState === 'loading'" class="state-panel">Loading ingestion runs…</p>
      <div v-else-if="runsState === 'error'" class="state-panel state-panel--error">
        <p>{{ runsMessage }}</p>
        <button class="button button--quiet" type="button" @click="loadIngestionRuns">Retry</button>
      </div>
      <p v-else-if="runsState === 'empty'" class="state-panel">No ingestion runs have been recorded.</p>
      <div v-else class="table-wrap">
        <table>
          <caption>Newest runs first</caption>
          <thead><tr><th>Status</th><th>Trigger</th><th>Source</th><th>Counts</th><th>Range</th><th>Started</th></tr></thead>
          <tbody>
            <tr v-for="run in ingestionRuns" :key="run.run_id">
              <td><span class="status-badge">{{ run.status }}</span></td>
              <td>{{ run.trigger }}</td>
              <td>{{ run.provider ?? run.source_filename }}</td>
              <td>{{ run.fetched_count }} fetched · {{ run.inserted_count }} inserted · {{ run.skipped_count }} duplicate</td>
              <td>{{ displayText(run.requested_start) }} → {{ displayText(run.requested_end) }}</td>
              <td>{{ formatTimestamp(run.started_at) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </section>
</template>
