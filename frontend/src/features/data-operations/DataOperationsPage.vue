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
  type IngestionRunLotteryType,
  type IngestionRunQuery,
} from '../../api/drawData'
import { lotteryTypeDisplayLabel } from '../../utils/lotteryDisplayLabel'
import MetricCard from '../../components/MetricCard.vue'
import StatusBadge from '../../components/StatusBadge.vue'
import SectionHeader from '../../components/SectionHeader.vue'

type FileStatus =
  | 'READING'
  | 'NOT_PREVIEWED'
  | 'PREVIEWING'
  | 'VALID'
  | 'PARTIAL'
  | 'DUPLICATE'
  | 'CONFLICTED'
  | 'EXCLUDED'
  | 'INVALID'
  | 'ERROR'
type CommitStatus =
  | 'NOT_COMMITTED'
  | 'COMMITTING'
  | 'SUCCESS'
  | 'PARTIAL_SUCCESS'
  | 'DUPLICATE'
  | 'CONFLICTED'
  | 'FAILED'
type LoadState = 'loading' | 'ready' | 'empty' | 'error'
type IngestionRunFilter = 'ALL' | IngestionRunLotteryType

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
const isDragging = ref(false)
const batchConfirmed = ref(false)
const previewBusy = ref(false)
const commitBusy = ref(false)
const lastBatchStatus = ref<BatchImportCommit['status'] | null>(null)
const lastBatchResult = ref<BatchImportCommit | null>(null)
const ingestionRuns = ref<IngestionRun[]>([])
const ingestionRunFilter = ref<IngestionRunFilter>('ALL')
const ingestionSearchQuery = ref('')
const runsState = ref<LoadState>('loading')
const runsMessage = ref('')
const syncLotteryType = ref<IngestionRunLotteryType>('BIG_LOTTO')
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
      ['VALID', 'PARTIAL', 'DUPLICATE', 'CONFLICTED'].includes(entry.previewStatus) &&
      entry.contentBase64,
  ),
)
const selectedValidFiles = computed(() => validFiles.value.filter((entry) => entry.selected))
const batchStatus = computed(() => {
  if (lastBatchStatus.value) {
    const excludedFailure = files.value.some(
      (entry) =>
        ['INVALID', 'ERROR'].includes(entry.previewStatus) &&
        entry.commitStatus === 'NOT_COMMITTED',
    )
    return lastBatchStatus.value === 'SUCCESS' && excludedFailure
      ? 'PARTIAL_SUCCESS'
      : lastBatchStatus.value
  }
  const successCount = files.value.filter((entry) =>
    ['SUCCESS', 'DUPLICATE'].includes(entry.commitStatus),
  ).length
  const failedCount = files.value.filter((entry) => entry.commitStatus === 'FAILED').length
  if (successCount === 0 && failedCount === 0) return 'NOT_COMMITTED'
  if (successCount === validFiles.value.length && validFiles.value.length > 0) return 'SUCCESS'
  if (successCount === 0) return 'FAILED'
  return 'PARTIAL_SUCCESS'
})

const totalDiscoveredRows = computed(() =>
  files.value.reduce((acc, f) => acc + f.fileResults.reduce((sum, r) => sum + r.discovered_rows, 0), 0),
)
const totalAcceptedRows = computed(() =>
  files.value.reduce((acc, f) => acc + entryAcceptedRows(f), 0),
)
const totalDuplicateRows = computed(() =>
  files.value.reduce((acc, f) => acc + entryDuplicateRows(f), 0),
)
const totalFailedRows = computed(() =>
  files.value.reduce((acc, f) => acc + entryFailedRows(f), 0),
)

const filteredIngestionRuns = computed(() => {
  let list = ingestionRuns.value
  if (ingestionSearchQuery.value.trim()) {
    const q = ingestionSearchQuery.value.trim().toLowerCase()
    list = list.filter((r) =>
      r.run_id.toLowerCase().includes(q) ||
      (r.source_filename && r.source_filename.toLowerCase().includes(q)) ||
      (r.provider && r.provider.toLowerCase().includes(q)) ||
      r.trigger.toLowerCase().includes(q),
    )
  }
  return list
})

async function processSelectedFileList(selected: File[]): Promise<void> {
  cancelBatch(false)
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

async function selectFiles(event: Event): Promise<void> {
  const input = event.currentTarget as HTMLInputElement
  const selected = Array.from(input.files ?? [])
  await processSelectedFileList(selected)
}

function onDragOver(e: DragEvent): void {
  e.preventDefault()
  isDragging.value = true
}

function onDragLeave(e: DragEvent): void {
  e.preventDefault()
  isDragging.value = false
}

async function onDrop(e: DragEvent): Promise<void> {
  e.preventDefault()
  isDragging.value = false
  const dropped = Array.from(e.dataTransfer?.files ?? [])
  if (dropped.length) {
    await processSelectedFileList(dropped)
  }
}

async function previewAll(): Promise<void> {
  if (previewBusy.value) return
  previewBusy.value = true
  lastBatchStatus.value = null
  lastBatchResult.value = null
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
  lastBatchStatus.value = null
  lastBatchResult.value = null
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
      lastBatchStatus.value = 'FAILED'
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
    lastBatchResult.value = outcome.result
    lastBatchStatus.value = outcome.result?.status ?? 'FAILED'
    for (const entry of entries) {
      entry.result = outcome.result
      entry.fileResults = outcome.result ? resultsForEntry(outcome.result, entry) : []
      entry.commitStatus = commitStatusForEntry(entry, outcome.result)
      const completed = ['SUCCESS', 'DUPLICATE'].includes(entry.commitStatus)
      entry.error = completed
        ? ''
        : (outcome.message ?? outcome.result?.error_summary ?? 'Batch import was not completed.')
      if (completed) entry.contentBase64 = ''
    }
  } catch (error: unknown) {
    if (!isCurrentSelection(selection) || isAbort(error)) return
    for (const entry of entries) {
      entry.commitStatus = 'FAILED'
      entry.error = error instanceof Error ? error.message : 'Batch commit failed.'
    }
    lastBatchStatus.value = 'FAILED'
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
  lastBatchStatus.value = null
  lastBatchResult.value = null
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
        lottery_type: syncLotteryType.value,
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
    const page = await listIngestionRuns(buildIngestionRunQuery(), controller.signal)
    if (unmounted || generation !== runsGeneration) return
    ingestionRuns.value = page.records
    runsState.value = page.records.length ? 'ready' : 'empty'
  } catch (error: unknown) {
    if (unmounted || generation !== runsGeneration || isAbort(error)) return
    runsState.value = 'error'
    runsMessage.value = error instanceof Error ? error.message : 'Ingestion runs could not load.'
  }
}

function buildIngestionRunQuery(): IngestionRunQuery {
  return ingestionRunFilter.value === 'ALL'
    ? {}
    : { lotteryType: ingestionRunFilter.value }
}

function reloadIngestionRuns(): void {
  void loadIngestionRuns()
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
    const hasConflict = entry.fileResults.some((file) => file.status === 'CONFLICTED')
    const hasDuplicate =
      entry.fileResults.length > 0 &&
      entry.fileResults.every((file) => ['DUPLICATE', 'EXCLUDED'].includes(file.status))
    const hasInvalid = entry.fileResults.some((file) => file.status === 'INVALID')
    const hasExcluded =
      entry.fileResults.length > 0 &&
      entry.fileResults.every((file) => file.status === 'EXCLUDED')
    if (hasFailure) entry.previewStatus = 'ERROR'
    else if (accepted > 0 && (hasPartial || hasConflict)) entry.previewStatus = 'PARTIAL'
    else if (accepted > 0 && !hasInvalid) entry.previewStatus = 'VALID'
    else if (hasConflict) entry.previewStatus = 'CONFLICTED'
    else if (hasDuplicate) entry.previewStatus = 'DUPLICATE'
    else if (hasExcluded) entry.previewStatus = 'EXCLUDED'
    else if (hasInvalid) entry.previewStatus = 'INVALID'
    else entry.previewStatus = 'ERROR'
    entry.error = firstIssueSummary(entry) || fallbackMessage || ''
  }
}

function firstIssueSummary(entry: BatchFile): string {
  const firstIssue = entry.fileResults.flatMap((file) => file.issues)[0]
  return firstIssue ? `${firstIssue.code}: ${firstIssue.message}` : ''
}

function entryIssueCount(entry: BatchFile): number {
  return entry.fileResults.reduce((total, file) => total + file.issues.length, 0)
}

function resultsForEntry(
  result: { files: BatchImportPreview['files'] },
  entry: BatchFile,
): BatchImportPreview['files'] {
  return result.files.filter(
    (file) =>
      file.source_filename === entry.filename ||
      file.source_locator.startsWith(`${entry.filename}!`),
  )
}

function commitStatusForEntry(
  entry: BatchFile,
  result: BatchImportCommit | null,
): CommitStatus {
  if (!result || entry.fileResults.length === 0) return 'FAILED'
  const statuses = entry.fileResults.map((file) => file.status)
  const imported = statuses.some((status) => status === 'IMPORTED')
  const partial = statuses.some((status) => status === 'PARTIAL_SUCCESS')
  const failed = statuses.some((status) => status === 'FAILED')
  const conflicted = statuses.some((status) => status === 'CONFLICTED')
  if (partial || (imported && (failed || conflicted))) return 'PARTIAL_SUCCESS'
  if (failed) return 'FAILED'
  if (conflicted) return 'CONFLICTED'
  if (statuses.every((status) => status === 'DUPLICATE')) return 'DUPLICATE'
  if (imported) return 'SUCCESS'
  return result.status === 'FAILED' ? 'FAILED' : 'SUCCESS'
}

function entryAcceptedRows(entry: BatchFile): number {
  return entry.fileResults.reduce((total, file) => total + file.accepted_rows, 0)
}

function entryFailedRows(entry: BatchFile): number {
  return entry.fileResults.reduce((total, file) => total + file.failed_rows, 0)
}

function entryImportedRows(entry: BatchFile): number {
  return entry.fileResults.reduce((total, file) => total + file.imported_rows, 0)
}

function entryDuplicateRows(entry: BatchFile): number {
  return entry.fileResults.reduce((total, file) => total + file.duplicate_rows, 0)
}

function entryConflictRows(entry: BatchFile): number {
  return entry.fileResults.reduce((total, file) => total + file.conflict_rows, 0)
}

function displayRunIds(result: BatchImportCommit | null): string {
  if (!result) return '—'
  return result.run_ids.length ? result.run_ids.join(', ') : displayText(result.run_id)
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
    <SectionHeader
      id="data-center-title"
      title="Data Operations"
      eyebrow="Data Center · Audited Ingestion & Automation"
      description="Preview single or multiple legacy CSV, TXT, or ZIP files, commit explicit selections into chunked audit logs, or trigger provider synchronization for B649, P638, and T539."
    >
      <template #actions>
        <div class="scope-card" aria-label="Batch status">
          <span>Batch status</span>
          <strong data-testid="batch-status">{{ batchStatus }}</strong>
          <small>B649 · T539 · P638 · ≤500-row chunks · reject conflicts</small>
        </div>
      </template>
    </SectionHeader>

    <!-- Metrics overview bar -->
    <div class="metrics-grid">
      <MetricCard
        label="Files Selected"
        :value="files.length"
        :subvalue="files.length ? `${selectedValidFiles.length} valid selected` : 'None'"
        :variant="files.length ? 'accent' : 'default'"
      />
      <MetricCard
        label="Discovered Rows"
        :value="totalDiscoveredRows"
        :subvalue="`${totalAcceptedRows} accepted`"
      />
      <MetricCard
        label="Duplicates / Conflicts"
        :value="totalDuplicateRows"
        :subvalue="`${totalDuplicateRows} duplicate · 0 conflict`"
        :variant="totalDuplicateRows > 0 ? 'warning' : 'default'"
      />
      <MetricCard
        label="Failed / Invalid"
        :value="totalFailedRows"
        :subvalue="totalFailedRows ? 'Review issue details below' : 'None'"
        :variant="totalFailedRows > 0 ? 'danger' : 'success'"
      />
    </div>

    <!-- Section 1: File Upload & Batch Preview -->
    <article class="panel upload-panel" style="margin-top: 24px">
      <div class="panel__heading">
        <div>
          <p class="step-label">01 · File Selection & Validation</p>
          <h2>Upload Legacy Draw Files (CSV, TXT, ZIP)</h2>
        </div>
        <button
          class="button button--quiet"
          data-testid="cancel-batch"
          type="button"
          @click="cancelBatch()"
        >
          Cancel batch
        </button>
      </div>

      <!-- Drag & Drop Zone -->
      <div
        class="file-dropzone"
        :class="{ 'file-dropzone--active': isDragging }"
        @dragover="onDragOver"
        @dragleave="onDragLeave"
        @drop="onDrop"
      >
        <div class="file-dropzone__icon">📁</div>
        <div class="file-dropzone__content">
          <label class="file-picker">
            <span>Select or drag & drop one or more import files</span>
            <input
              ref="fileInput"
              data-testid="csv-file"
              type="file"
              accept=".csv,.txt,.zip,text/csv,text/plain,application/zip"
              multiple
              @change="selectFiles"
            />
          </label>
          <p class="file-dropzone__hint">
            Accepted formats: <code>.csv</code>, <code>.txt</code>, <code>.zip</code> · Automatic header & date validation
          </p>
        </div>
      </div>

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

    <!-- Per-file Status Table -->
    <div v-if="files.length" class="table-wrap">
      <table>
        <caption>Per-file preview and commit status</caption>
        <thead>
          <tr>
            <th>Select</th>
            <th>File</th>
            <th>Digest / parser</th>
            <th>Validation</th>
            <th>Counts</th>
            <th>Commit</th>
            <th>Run / error</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="entry in files" :key="entry.id" :data-testid="`batch-file-${entry.id}`">
            <td>
              <input
                v-model="entry.selected"
                type="checkbox"
                :aria-label="`Select ${entry.filename} for commit`"
                :disabled="!['VALID', 'PARTIAL', 'DUPLICATE', 'CONFLICTED'].includes(entry.previewStatus) || ['SUCCESS', 'DUPLICATE'].includes(entry.commitStatus)"
              />
            </td>
            <td>
              <strong>{{ entry.filename }}</strong>
              <small>{{ formatBytes(entry.size) }}</small>
            </td>
            <td>
              <code>{{ entry.preview?.manifest_sha256 ?? '—' }}</code>
              <small>{{ entry.preview?.parser_version ?? '—' }}</small>
            </td>
            <td>
              <StatusBadge :status="entry.previewStatus" />
            </td>
            <td>
              {{ entryAcceptedRows(entry) }} accepted ·
              {{ entryImportedRows(entry) }} imported ·
              {{ entryDuplicateRows(entry) }} duplicate ·
              {{ entryConflictRows(entry) }} conflict ·
              {{ entryFailedRows(entry) }} failed ·
              {{ entryExcludedRows(entry) }} excluded
            </td>
            <td>
              <StatusBadge :status="entry.commitStatus" />
            </td>
            <td>
              <code>{{ displayRunIds(entry.result) }}</code>
              <small
                v-if="entry.error"
                :data-testid="`batch-first-issue-${entry.id}`"
                class="error-copy"
              >
                {{ entry.error }}
              </small>
              <small
                v-if="firstIssueSummary(entry) && firstIssueSummary(entry) !== entry.error"
                :data-testid="`batch-first-issue-after-result-${entry.id}`"
                class="error-copy"
              >
                {{ firstIssueSummary(entry) }}
              </small>
              <details
                v-if="entryIssueCount(entry) > 0"
                :data-testid="`batch-issues-${entry.id}`"
                class="issue-details"
              >
                <summary>View {{ entryIssueCount(entry) }} issue{{ entryIssueCount(entry) === 1 ? '' : 's' }}</summary>
                <template v-for="(fileResult, fileResultIndex) in entry.fileResults" :key="fileResult.source_locator">
                  <div v-if="fileResult.issues.length" class="issue-group">
                    <strong>{{ fileResult.source_locator }}</strong>
                    <ul class="reason-list">
                      <li
                        v-for="(issue, issueIndex) in fileResult.issues"
                        :key="`${fileResult.source_locator}-${issue.code}-${issue.row_number ?? 'file'}-${issueIndex}`"
                        :data-testid="`batch-issue-${entry.id}-${fileResultIndex}-${issueIndex}`"
                      >
                        <span>{{ issue.code }}: {{ issue.message }}</span>
                        <small v-if="issue.member_name !== null">Member: {{ issue.member_name }}</small>
                        <small v-if="issue.row_number !== null">Row {{ issue.row_number }}</small>
                      </li>
                    </ul>
                  </div>
                </template>
              </details>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Step 2: Explicit Confirmation Boundary -->
    <article v-if="validFiles.length" class="panel commit-box">
      <p class="step-label">02 · Confirm & Commit</p>
      <label class="confirmation">
        <input v-model="batchConfirmed" data-testid="batch-confirmation" type="checkbox" />
        <span>
          I confirm the selected files should be classified together, with conflicts rejected and
          accepted rows committed in independent chunks of at most 500. Earlier successful chunks
          remain durable if a later chunk fails.
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
          {{ commitBusy ? 'Committing…' : 'Commit all valid files' }}
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

    <div v-if="lastBatchResult" class="state-panel" data-testid="batch-identity-summary">
      <strong>Batch commit identity</strong>
      <span>Run IDs: <code>{{ displayRunIds(lastBatchResult) }}</code></span>
      <span>{{ lastBatchResult.committed_chunks }} committed chunks</span>
      <span>{{ lastBatchResult.failed_chunks }} failed chunks</span>
    </div>

    <!-- Section 2: Automated Draw Sync -->
    <article class="panel automation-panel" aria-labelledby="automation-title">
      <div class="panel__heading">
        <div>
          <p class="step-label">03 · Automated Draw Sync</p>
          <h2 id="automation-title">Bounded Provider Synchronization</h2>
        </div>
        <StatusBadge :status="syncPending ? 'RUNNING' : 'READY'" />
      </div>

      <div class="sync-games-bar">
        <span class="sync-games-label">Canonical Games:</span>
        <button
          type="button"
          class="button"
          :class="{ 'button--primary': syncLotteryType === 'BIG_LOTTO', 'button--quiet': syncLotteryType !== 'BIG_LOTTO' }"
          @click="syncLotteryType = 'BIG_LOTTO'"
        >
          B649
        </button>
        <button
          type="button"
          class="button"
          :class="{ 'button--primary': syncLotteryType === 'POWER_LOTTO', 'button--quiet': syncLotteryType !== 'POWER_LOTTO' }"
          @click="syncLotteryType = 'POWER_LOTTO'"
        >
          P638
        </button>
        <button
          type="button"
          class="button"
          :class="{ 'button--primary': syncLotteryType === 'DAILY_539', 'button--quiet': syncLotteryType !== 'DAILY_539' }"
          @click="syncLotteryType = 'DAILY_539'"
        >
          T539
        </button>
      </div>

      <div class="filter-grid" style="margin-top: 14px">
        <label>
          <span>Date from</span>
          <input v-model="syncForm.dateFrom" data-testid="sync-date-from" type="date" />
        </label>
        <label>
          <span>Date to</span>
          <input v-model="syncForm.dateTo" data-testid="sync-date-to" type="date" />
        </label>
      </div>

      <div class="filter-actions" aria-label="Draw synchronization actions">
        <button
          class="button button--primary"
          data-testid="manual-sync"
          type="button"
          :disabled="!!syncPending || !syncForm.dateFrom || !syncForm.dateTo"
          @click="runSync('manual')"
        >
          Manual sync
        </button>
        <button
          class="button button--quiet"
          type="button"
          :disabled="!!syncPending || !syncForm.dateFrom || !syncForm.dateTo"
          @click="runSync('missing-scan')"
        >
          Scan missing draws
        </button>
        <button
          class="button button--quiet"
          type="button"
          :disabled="!!syncPending || !syncForm.dateFrom || !syncForm.dateTo"
          @click="runSync('backfill')"
        >
          Bounded backfill
        </button>
        <button
          class="button button--quiet"
          data-testid="scheduled-sync"
          type="button"
          :disabled="!!syncPending || !syncForm.dateFrom || !syncForm.dateTo"
          @click="runSync('scheduled')"
        >
          Run scheduled trigger
        </button>
      </div>

      <p v-if="syncMessage" class="state-panel" :class="{ 'state-panel--error': !syncResult }" aria-live="polite">
        {{ syncMessage }}
      </p>
    </article>

    <!-- Section 3: Import Operations (Audit log) -->
    <section class="log-section" aria-labelledby="ingestion-log-title">
      <div class="section-heading">
        <div>
          <p class="eyebrow">Append-only audit</p>
          <h2 id="ingestion-log-title">Recent Ingestion Runs</h2>
        </div>
        <div class="filter-actions">
          <label class="filter-item">
            <span>Lottery history</span>
            <select
              v-model="ingestionRunFilter"
              data-testid="ingestion-run-filter"
              @change="reloadIngestionRuns"
            >
              <option value="ALL">ALL</option>
              <option value="DAILY_539">T539</option>
              <option value="BIG_LOTTO">B649</option>
              <option value="POWER_LOTTO">P638</option>
            </select>
          </label>
          <label class="filter-item">
            <span>Search runs</span>
            <input
              v-model="ingestionSearchQuery"
              type="search"
              placeholder="Filter by run ID, trigger, or file"
            />
          </label>
          <a class="button button--quiet" href="#/history">Open full history</a>
        </div>
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
          <thead>
            <tr>
              <th>Status</th>
              <th>Lottery</th>
              <th>Trigger</th>
              <th>Source</th>
              <th>Counts</th>
              <th>Range</th>
              <th>Started</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="run in filteredIngestionRuns" :key="run.run_id">
              <td>
                <StatusBadge :status="run.status" />
              </td>
              <td>
                <strong>{{ run.lottery_type ? lotteryTypeDisplayLabel(run.lottery_type) : '—' }}</strong>
              </td>
              <td>{{ run.trigger }}</td>
              <td>{{ run.provider ?? run.source_filename }}</td>
              <td>
                {{ run.fetched_count }} fetched · {{ run.inserted_count }} inserted · {{ run.skipped_count }} duplicate
              </td>
              <td>{{ displayText(run.requested_start) }} → {{ displayText(run.requested_end) }}</td>
              <td>{{ formatTimestamp(run.started_at) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </section>
</template>
