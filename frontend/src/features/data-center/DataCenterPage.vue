<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'

import {
  commitDrawImport,
  listIngestionRuns,
  previewDrawImport,
  type DrawImportPreview,
  type ImportCommitResult,
  type IngestionRun,
} from '../../api/drawData'

type PreviewState = 'idle' | 'reading' | 'ready' | 'invalid' | 'error'
type LoadState = 'loading' | 'ready' | 'empty' | 'error'

const fileInput = ref<HTMLInputElement>()
const filename = ref('')
const fileSize = ref(0)
const csvText = ref('')
const preview = ref<DrawImportPreview | null>(null)
const previewState = ref<PreviewState>('idle')
const previewMessage = ref('')
const previewPending = ref(false)
const commitConfirmed = ref(false)
const commitPending = ref(false)
const commitResult = ref<ImportCommitResult | null>(null)
const commitMessage = ref('')
const commitKind = ref<'success' | 'conflict' | 'error' | ''>('')
const ingestionRuns = ref<IngestionRun[]>([])
const runsState = ref<LoadState>('loading')
const runsMessage = ref('')
let previewController: AbortController | undefined
let commitController: AbortController | undefined
let runsController: AbortController | undefined
let selectedFile: File | null = null
let selectionGeneration = 0
let previewGeneration = 0
let commitGeneration = 0
let runsGeneration = 0
let unmounted = false

async function selectFile(event: Event): Promise<void> {
  const input = event.currentTarget as HTMLInputElement
  const file = input.files?.[0]
  invalidateImportWork()
  clearSelectedCsv(false)
  clearCommitOutcome()
  if (!file) {
    return
  }

  const generation = selectionGeneration
  selectedFile = file
  filename.value = file.name
  fileSize.value = file.size
  previewState.value = 'reading'
  try {
    const content = await file.text()
    if (!isCurrentSelection(generation, file)) return
    csvText.value = content
    previewState.value = 'idle'
  } catch {
    if (!isCurrentSelection(generation, file)) return
    previewState.value = 'error'
    previewMessage.value = 'The selected file could not be read as UTF-8 text.'
  }
}

async function requestPreview(): Promise<void> {
  const file = selectedFile
  if (!file || !filename.value || !csvText.value) return
  const selection = selectionGeneration
  const selectedFilename = filename.value
  const selectedCsvText = csvText.value
  previewController?.abort()
  const generation = ++previewGeneration
  const controller = new AbortController()
  previewController = controller
  invalidateCommitWork()
  previewPending.value = true
  previewMessage.value = ''
  preview.value = null
  commitConfirmed.value = false
  commitResult.value = null
  commitKind.value = ''
  commitMessage.value = ''
  try {
    const outcome = await previewDrawImport(
      { filename: selectedFilename, csv_text: selectedCsvText },
      controller.signal,
    )
    if (
      !isCurrentPreview(
        generation,
        selection,
        file,
        selectedFilename,
        selectedCsvText,
      )
    ) {
      return
    }
    preview.value = outcome.preview
    if (outcome.ok) {
      previewState.value = 'ready'
    } else {
      previewState.value = 'invalid'
      previewMessage.value = outcome.message ?? 'CSV validation failed.'
    }
  } catch (error: unknown) {
    if (
      !isCurrentPreview(
        generation,
        selection,
        file,
        selectedFilename,
        selectedCsvText,
      )
    ) {
      return
    }
    if (isAbort(error)) return
    previewState.value = 'error'
    previewMessage.value = error instanceof Error ? error.message : 'CSV preview failed.'
  } finally {
    if (!unmounted && previewGeneration === generation) {
      previewPending.value = false
      if (previewController === controller) previewController = undefined
    }
  }
}

async function commitPreview(): Promise<void> {
  if (commitPending.value) return
  const approvedPreview = preview.value
  const file = selectedFile
  if (
    !file ||
    !approvedPreview?.is_valid ||
    !commitConfirmed.value ||
    !filename.value ||
    !csvText.value
  ) {
    return
  }
  const selection = selectionGeneration
  const selectedFilename = filename.value
  const selectedCsvText = csvText.value
  const previewDigest = approvedPreview.content_sha256
  const parserVersion = approvedPreview.parser_version
  commitController?.abort()
  const generation = ++commitGeneration
  const controller = new AbortController()
  commitController = controller
  commitPending.value = true
  commitKind.value = ''
  commitMessage.value = ''
  try {
    const outcome = await commitDrawImport(
      {
        filename: selectedFilename,
        csv_text: selectedCsvText,
        expected_sha256: previewDigest,
        parser_version: parserVersion,
        conflict_policy: 'REJECT',
      },
      controller.signal,
    )
    if (
      !isCurrentCommit(
        generation,
        selection,
        file,
        selectedFilename,
        selectedCsvText,
        previewDigest,
        parserVersion,
      )
    ) {
      return
    }
    commitResult.value = outcome.result
    if (outcome.ok) {
      commitKind.value = 'success'
      commitMessage.value = 'Import committed atomically.'
      selectedFile = null
      clearSelectedCsv()
      await loadIngestionRuns()
    } else {
      commitKind.value = outcome.status === 409 ? 'conflict' : 'error'
      commitMessage.value = outcome.message ?? 'Import was not committed.'
      if (outcome.preview) preview.value = outcome.preview
    }
  } catch (error: unknown) {
    if (
      !isCurrentCommit(
        generation,
        selection,
        file,
        selectedFilename,
        selectedCsvText,
        previewDigest,
        parserVersion,
      )
    ) {
      return
    }
    if (isAbort(error)) return
    commitKind.value = 'error'
    commitMessage.value = error instanceof Error ? error.message : 'Import commit failed.'
  } finally {
    if (!unmounted && commitGeneration === generation) {
      commitPending.value = false
      if (commitController === controller) commitController = undefined
    }
  }
}

async function loadIngestionRuns(): Promise<void> {
  runsController?.abort()
  const generation = ++runsGeneration
  const controller = new AbortController()
  runsController = controller
  runsState.value = 'loading'
  runsMessage.value = ''
  try {
    const page = await listIngestionRuns(controller.signal)
    if (unmounted || runsGeneration !== generation) return
    ingestionRuns.value = page.records
    runsState.value = page.records.length === 0 ? 'empty' : 'ready'
  } catch (error: unknown) {
    if (unmounted || runsGeneration !== generation) return
    if (isAbort(error)) return
    runsState.value = 'error'
    runsMessage.value = error instanceof Error ? error.message : 'Ingestion runs could not load.'
  } finally {
    if (!unmounted && runsGeneration === generation && runsController === controller) {
      runsController = undefined
    }
  }
}

function resetImport(): void {
  invalidateImportWork()
  clearSelectedCsv()
  clearCommitOutcome()
}

function invalidateImportWork(): void {
  selectionGeneration += 1
  selectedFile = null
  invalidatePreviewWork()
  invalidateCommitWork()
}

function invalidatePreviewWork(): void {
  previewGeneration += 1
  previewController?.abort()
  previewController = undefined
  previewPending.value = false
}

function invalidateCommitWork(): void {
  commitGeneration += 1
  commitController?.abort()
  commitController = undefined
  commitPending.value = false
}

function clearSelectedCsv(clearInput = true): void {
  filename.value = ''
  fileSize.value = 0
  csvText.value = ''
  preview.value = null
  previewState.value = 'idle'
  previewMessage.value = ''
  commitConfirmed.value = false
  if (clearInput && fileInput.value) fileInput.value.value = ''
}

function clearCommitOutcome(): void {
  commitResult.value = null
  commitKind.value = ''
  commitMessage.value = ''
}

function isCurrentSelection(generation: number, file: File): boolean {
  return !unmounted && selectionGeneration === generation && selectedFile === file
}

function isCurrentPreview(
  generation: number,
  selection: number,
  file: File,
  selectedFilename: string,
  selectedCsvText: string,
): boolean {
  return (
    previewGeneration === generation &&
    isCurrentSelection(selection, file) &&
    filename.value === selectedFilename &&
    csvText.value === selectedCsvText
  )
}

function isCurrentCommit(
  generation: number,
  selection: number,
  file: File,
  selectedFilename: string,
  selectedCsvText: string,
  previewDigest: string,
  parserVersion: string,
): boolean {
  return (
    commitGeneration === generation &&
    isCurrentSelection(selection, file) &&
    filename.value === selectedFilename &&
    csvText.value === selectedCsvText &&
    preview.value?.content_sha256 === previewDigest &&
    preview.value.parser_version === parserVersion
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
  return (
    (error instanceof DOMException || error instanceof Error) && error.name === 'AbortError'
  )
}

onMounted(loadIngestionRuns)
onBeforeUnmount(() => {
  unmounted = true
  invalidateImportWork()
  runsGeneration += 1
  runsController?.abort()
  runsController = undefined
  csvText.value = ''
})
</script>

<template>
  <section class="workspace-page" aria-labelledby="data-center-title">
    <header class="page-heading">
      <div>
        <p class="eyebrow">P600D · local data foundation</p>
        <h1 id="data-center-title">Data Center</h1>
        <p class="page-intro">
          Preview LottoLab-owned CSV content before one explicit, transactional commit. Validation
          remains backend-authoritative.
        </p>
      </div>
      <div class="scope-card" aria-label="Supported import type">
        <span>Supported import</span>
        <strong>BIG_LOTTO</strong>
        <small>CSV · REJECT conflicts</small>
      </div>
    </header>

    <div class="workspace-grid workspace-grid--import">
      <article class="panel upload-panel">
        <div class="panel__heading">
          <div>
            <p class="step-label">01 · Select</p>
            <h2>Choose a canonical CSV</h2>
          </div>
          <button
            class="button button--quiet"
            data-testid="reset-import"
            type="button"
            @click="resetImport"
          >
            Reset
          </button>
        </div>

        <label class="file-picker">
          <span>Select CSV file</span>
          <input
            ref="fileInput"
            data-testid="csv-file"
            type="file"
            accept=".csv,text/csv"
            @change="selectFile"
          />
        </label>

        <dl v-if="filename" class="file-facts">
          <div>
            <dt>Filename</dt>
            <dd>{{ filename }}</dd>
          </div>
          <div>
            <dt>UTF-8 file size</dt>
            <dd>{{ formatBytes(fileSize) }}</dd>
          </div>
        </dl>
        <p v-else class="empty-copy">No CSV selected. File content stays only in this page session.</p>

        <button
          class="button button--primary"
          data-testid="preview-action"
          type="button"
          :disabled="!csvText || previewPending || commitPending || previewState === 'reading'"
          @click="requestPreview"
        >
          {{ previewPending ? 'Previewing…' : previewState === 'reading' ? 'Reading…' : 'Preview CSV' }}
        </button>
      </article>

      <article class="panel policy-panel">
        <p class="step-label">Import boundary</p>
        <h2>Local and deliberate</h2>
        <ul class="plain-list">
          <li>Filename is display metadata, never a filesystem path.</li>
          <li>Preview performs no database operation.</li>
          <li>Commit re-parses the exact content and rejects every conflict.</li>
          <li>Fetch-latest, missing scan, and backfill are outside this release.</li>
        </ul>
      </article>
    </div>

    <div class="status-region" aria-live="polite">
      <p v-if="previewState === 'error'" class="state-panel state-panel--error">
        {{ previewMessage }}
      </p>
      <p v-else-if="previewState === 'invalid'" class="state-panel state-panel--warning">
        {{ previewMessage }}
      </p>
    </div>

    <article v-if="preview" class="panel preview-panel">
      <div class="panel__heading">
        <div>
          <p class="step-label">02 · Preview</p>
          <h2>{{ preview.is_valid ? 'Ready for confirmation' : 'Validation requires attention' }}</h2>
        </div>
        <span class="status-badge" :class="preview.is_valid ? 'status-badge--success' : 'status-badge--failed'">
          {{ preview.is_valid ? 'VALID' : 'INVALID' }}
        </span>
      </div>

      <dl class="metric-grid">
        <div><dt>Total rows</dt><dd>{{ preview.total_rows }}</dd></div>
        <div><dt>Valid rows</dt><dd>{{ preview.valid_rows }}</dd></div>
        <div><dt>Blank</dt><dd>{{ preview.blank_rows }}</dd></div>
        <div><dt>Duplicates</dt><dd>{{ preview.duplicate_rows }}</dd></div>
        <div><dt>Input conflicts</dt><dd>{{ preview.conflict_rows_inside_input }}</dd></div>
        <div><dt>Errors</dt><dd>{{ preview.validation_error_count }}</dd></div>
      </dl>

      <div class="digest-block">
        <span>Content SHA-256</span>
        <code>{{ preview.content_sha256 }}</code>
        <small>{{ preview.parser_version }}</small>
      </div>

      <div v-if="preview.ignored_columns.length" class="notice-row">
        <strong>Ignored columns</strong>
        <span>{{ preview.ignored_columns.join(', ') }}</span>
      </div>

      <div v-if="preview.normalized_preview.length" class="table-wrap">
        <table>
          <caption>Bounded normalized-row preview</caption>
          <thead>
            <tr>
              <th>Row</th><th>Draw</th><th>Date</th><th>Main numbers</th><th>Special</th><th>Source</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="record in preview.normalized_preview" :key="`${record.source_row_number}-${record.draw_number}`">
              <td>{{ record.source_row_number }}</td>
              <td><code>{{ record.draw_number }}</code></td>
              <td>{{ record.draw_date }}</td>
              <td><span class="number-sequence">{{ record.main_numbers.join(' · ') }}</span></td>
              <td><span class="special-number">{{ record.special_numbers.join(' · ') }}</span></td>
              <td>{{ displayText(record.source_reference) }}</td>
            </tr>
          </tbody>
        </table>
        <p v-if="preview.preview_truncated" class="table-note">Additional normalized rows are not displayed.</p>
      </div>

      <div v-if="preview.validation_errors.length" class="table-wrap table-wrap--errors">
        <table>
          <caption>Structured validation errors</caption>
          <thead><tr><th>Row</th><th>Field</th><th>Code</th><th>Message</th></tr></thead>
          <tbody>
            <tr v-for="(error, index) in preview.validation_errors" :key="`${error.code}-${error.row_number}-${index}`">
              <td>{{ error.row_number ?? 'Document' }}</td>
              <td>{{ displayText(error.field) }}</td>
              <td><code>{{ error.code }}</code></td>
              <td>{{ error.message }}</td>
            </tr>
          </tbody>
        </table>
        <p v-if="preview.errors_truncated" class="table-note">Additional validation errors are not displayed.</p>
      </div>

      <div v-if="preview.is_valid" class="commit-box">
        <p class="step-label">03 · Confirm</p>
        <label class="confirmation">
          <input v-model="commitConfirmed" data-testid="commit-confirmation" type="checkbox" />
          <span>I confirm this exact digest should be committed with conflict policy REJECT.</span>
        </label>
        <button
          class="button button--primary"
          data-testid="commit-action"
          type="button"
          :disabled="!commitConfirmed || commitPending"
          @click="commitPreview"
        >
          {{ commitPending ? 'Committing…' : 'Commit import' }}
        </button>
      </div>
    </article>

    <div v-if="commitKind" class="status-region" aria-live="polite">
      <article class="state-panel" :class="`state-panel--${commitKind}`">
        <strong>{{ commitKind === 'success' ? 'Commit complete' : commitKind === 'conflict' ? 'Conflict rejected' : 'Commit failed' }}</strong>
        <p>{{ commitMessage }}</p>
        <dl v-if="commitResult" class="inline-counts">
          <div><dt>Run</dt><dd><code>{{ displayText(commitResult.run_id) }}</code></dd></div>
          <div><dt>Inserted</dt><dd>{{ commitResult.inserted_count }}</dd></div>
          <div><dt>Skipped</dt><dd>{{ commitResult.skipped_count }}</dd></div>
          <div><dt>Conflicts</dt><dd>{{ commitResult.conflict_count }}</dd></div>
          <div><dt>Failed</dt><dd>{{ commitResult.failed_count }}</dd></div>
        </dl>
      </article>
    </div>

    <section class="log-section" aria-labelledby="ingestion-log-title">
      <div class="section-heading">
        <div>
          <p class="eyebrow">Operation log</p>
          <h2 id="ingestion-log-title">Ingestion runs</h2>
        </div>
        <button class="button button--quiet" type="button" @click="loadIngestionRuns">Refresh</button>
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
            <tr><th>Status</th><th>File</th><th>Counts</th><th>Draw range</th><th>Started</th><th>Run ID</th></tr>
          </thead>
          <tbody>
            <tr v-for="run in ingestionRuns" :key="run.run_id">
              <td><span class="status-badge" :class="`status-badge--${run.status.toLowerCase()}`">{{ run.status }}</span></td>
              <td>{{ run.source_filename }}</td>
              <td>{{ run.inserted_count }} in · {{ run.skipped_count }} skip · {{ run.conflict_count }} conflict</td>
              <td>{{ displayText(run.first_draw_number) }} → {{ displayText(run.last_draw_number) }}</td>
              <td>{{ formatTimestamp(run.started_at) }}</td>
              <td><code>{{ run.run_id }}</code></td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </section>
</template>
