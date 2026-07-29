<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'

import {
  commitDrawImport,
  listIngestionRuns,
  previewDrawImport,
  runDrawSync,
  type DrawImportPreview,
  type DrawSyncOperation,
  type DrawSyncResponse,
  type ImportCommitResult,
  type IngestionRun,
} from '../../api/drawData'

type FileStatus = 'READING' | 'NOT_PREVIEWED' | 'PREVIEWING' | 'VALID' | 'INVALID' | 'ERROR'
type CommitStatus = 'NOT_COMMITTED' | 'COMMITTING' | 'SUCCESS' | 'FAILED'
type LoadState = 'loading' | 'ready' | 'empty' | 'error'

interface BatchFile {
  id: number
  file: File
  filename: string
  size: number
  csvText: string
  selected: boolean
  previewStatus: FileStatus
  commitStatus: CommitStatus
  preview: DrawImportPreview | null
  result: ImportCommitResult | null
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
  files.value.filter((entry) => entry.previewStatus === 'VALID' && entry.csvText),
)
const selectedValidFiles = computed(() => validFiles.value.filter((entry) => entry.selected))
const batchStatus = computed(() => {
  const successCount = files.value.filter((entry) => entry.commitStatus === 'SUCCESS').length
  const failedCount = files.value.filter((entry) => entry.commitStatus === 'FAILED').length
  if (successCount === 0 && failedCount === 0) return 'NOT_COMMITTED'
  if (successCount === files.value.length) return 'SUCCESS'
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
      csvText: '',
      selected: true,
      previewStatus: 'READING',
      commitStatus: 'NOT_COMMITTED',
      preview: null,
      result: null,
      error: '',
    }),
  )
  files.value = entries
  await Promise.all(
    entries.map(async (entry) => {
      try {
        const content = await entry.file.text()
        if (!isCurrentEntry(generation, entry)) return
        entry.csvText = content
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
  await Promise.all(
    files.value
      .filter((entry) => entry.csvText && entry.commitStatus !== 'SUCCESS')
      .map(previewFile),
  )
  previewBusy.value = false
  batchConfirmed.value = false
}

async function previewFile(entry: BatchFile): Promise<void> {
  previewControllers.get(entry.id)?.abort()
  const controller = new AbortController()
  previewControllers.set(entry.id, controller)
  const selection = selectionGeneration
  const content = entry.csvText
  entry.previewStatus = 'PREVIEWING'
  entry.preview = null
  entry.result = null
  entry.commitStatus = 'NOT_COMMITTED'
  entry.error = ''
  try {
    const outcome = await previewDrawImport(
      { filename: entry.filename, csv_text: content },
      controller.signal,
    )
    if (!isCurrentEntry(selection, entry) || entry.csvText !== content) return
    entry.preview = outcome.preview
    entry.previewStatus = outcome.ok ? 'VALID' : 'INVALID'
    const firstError = outcome.preview?.validation_errors[0]
    entry.error = outcome.ok
      ? ''
      : [
          outcome.message ?? 'CSV validation failed.',
          firstError ? `${firstError.code}: ${firstError.message}` : '',
        ]
          .filter(Boolean)
          .join(' ')
  } catch (error: unknown) {
    if (!isCurrentEntry(selection, entry) || isAbort(error)) return
    entry.previewStatus = 'ERROR'
    entry.error = error instanceof Error ? error.message : 'CSV preview failed.'
  } finally {
    if (previewControllers.get(entry.id) === controller) previewControllers.delete(entry.id)
  }
}

async function commitFiles(entries: BatchFile[]): Promise<void> {
  if (!batchConfirmed.value || commitBusy.value || entries.length === 0) return
  commitBusy.value = true
  await Promise.all(entries.map(commitFile))
  commitBusy.value = false
  batchConfirmed.value = false
  await loadIngestionRuns()
}

async function commitFile(entry: BatchFile): Promise<void> {
  const approved = entry.preview
  if (!approved?.is_valid || !entry.csvText) return
  commitControllers.get(entry.id)?.abort()
  const controller = new AbortController()
  commitControllers.set(entry.id, controller)
  const selection = selectionGeneration
  const content = entry.csvText
  const digest = approved.content_sha256
  entry.commitStatus = 'COMMITTING'
  entry.error = ''
  try {
    const outcome = await commitDrawImport(
      {
        filename: entry.filename,
        csv_text: content,
        expected_sha256: digest,
        parser_version: approved.parser_version,
        conflict_policy: 'REJECT',
      },
      controller.signal,
    )
    if (
      !isCurrentEntry(selection, entry) ||
      entry.csvText !== content ||
      entry.preview?.content_sha256 !== digest
    ) {
      return
    }
    entry.result = outcome.result
    entry.commitStatus = outcome.ok ? 'SUCCESS' : 'FAILED'
    entry.error = outcome.ok ? '' : (outcome.message ?? 'Import was not committed.')
    if (outcome.ok) entry.csvText = ''
  } catch (error: unknown) {
    if (!isCurrentEntry(selection, entry) || isAbort(error)) return
    entry.commitStatus = 'FAILED'
    entry.error = error instanceof Error ? error.message : 'Import commit failed.'
  } finally {
    if (commitControllers.get(entry.id) === controller) commitControllers.delete(entry.id)
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
  for (const entry of files.value) entry.csvText = ''
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
          Preview one or many canonical CSV files, commit only explicit selections, or run a
          bounded provider synchronization. Every file uses its own transaction and audit run.
        </p>
      </div>
      <div class="scope-card" aria-label="Batch status">
        <span>Batch status</span>
        <strong data-testid="batch-status">{{ batchStatus }}</strong>
        <small>BIG_LOTTO · REJECT conflicts</small>
      </div>
    </header>

    <article class="panel upload-panel">
      <div class="panel__heading">
        <div>
          <p class="step-label">01 · Select</p>
          <h2>Choose canonical CSV files</h2>
        </div>
        <button class="button button--quiet" data-testid="cancel-batch" type="button" @click="cancelBatch()">
          Cancel batch
        </button>
      </div>
      <label class="file-picker">
        <span>Select one or more CSV files</span>
        <input
          ref="fileInput"
          data-testid="csv-file"
          type="file"
          accept=".csv,text/csv"
          multiple
          @change="selectFiles"
        />
      </label>
      <p v-if="files.length === 0" class="empty-copy">
        No CSV selected. Raw content remains only in this page session and is discarded after a
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
                :disabled="entry.previewStatus !== 'VALID' || entry.commitStatus === 'SUCCESS'"
              />
            </td>
            <td><strong>{{ entry.filename }}</strong><small>{{ formatBytes(entry.size) }}</small></td>
            <td>
              <code>{{ entry.preview?.content_sha256 ?? '—' }}</code>
              <small>{{ entry.preview?.parser_version ?? '—' }}</small>
            </td>
            <td><span class="status-badge">{{ entry.previewStatus }}</span></td>
            <td>
              {{ entry.preview?.valid_rows ?? 0 }} valid ·
              {{ entry.preview?.validation_error_count ?? 0 }} invalid ·
              {{ entry.preview?.duplicate_rows ?? 0 }} duplicate ·
              {{ entry.preview?.conflict_rows_inside_input ?? 0 }} conflict
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
          I confirm each selected valid file should be committed independently with conflict
          policy REJECT. This does not claim cross-file atomicity.
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
