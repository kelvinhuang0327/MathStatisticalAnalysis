<script setup lang="ts">
import { onBeforeUnmount, onMounted, reactive, ref } from 'vue'

import {
  getIngestionRun,
  listIngestionRuns,
  type IngestionRun,
  type IngestionRunDetail,
} from '../../api/drawData'
import {
  HistoricalImportsRequestError,
  listHistoricalImportRuns,
  type HistoricalImportRunPage,
} from '../../api/historicalImports'
import DrawHistoryPage from '../draw-history/DrawHistoryPage.vue'

type Tab = 'draws' | 'ingestion' | 'imports'
type State = 'loading' | 'ready' | 'empty' | 'error' | 'not-configured'

const activeTab = ref<Tab>('draws')
const runs = ref<IngestionRun[]>([])
const runDetail = ref<IngestionRunDetail | null>(null)
const ingestionState = ref<State>('loading')
const ingestionMessage = ref('')
const imports = ref<HistoricalImportRunPage | null>(null)
const importsState = ref<State>('loading')
const importsMessage = ref('')
const runFilters = reactive({
  status: '',
  operationType: '',
  source: '',
  dateFrom: '',
  dateTo: '',
})
let ingestionController: AbortController | undefined
let detailController: AbortController | undefined
let importsController: AbortController | undefined
let ingestionGeneration = 0
let detailGeneration = 0
let importsGeneration = 0
let unmounted = false

async function loadIngestionRuns(): Promise<void> {
  ingestionController?.abort()
  invalidateRunDetail()
  const controller = new AbortController()
  ingestionController = controller
  const generation = ++ingestionGeneration
  ingestionState.value = 'loading'
  ingestionMessage.value = ''
  runDetail.value = null
  try {
    const page = await listIngestionRuns(
      {
        status:
          runFilters.status === 'RUNNING' ||
          runFilters.status === 'SUCCESS' ||
          runFilters.status === 'FAILED'
            ? runFilters.status
            : undefined,
        operationType:
          runFilters.operationType === 'DRAW_CSV_IMPORT' ||
          runFilters.operationType === 'MANUAL_SYNC' ||
          runFilters.operationType === 'MISSING_DRAW_SCAN' ||
          runFilters.operationType === 'BOUNDED_BACKFILL' ||
          runFilters.operationType === 'SCHEDULED_SYNC'
            ? runFilters.operationType
            : undefined,
        source: runFilters.source.trim() || undefined,
        dateFrom: runFilters.dateFrom || undefined,
        dateTo: runFilters.dateTo || undefined,
      },
      controller.signal,
    )
    if (unmounted || generation !== ingestionGeneration) return
    runs.value = page.records
    ingestionState.value = page.records.length ? 'ready' : 'empty'
  } catch (error: unknown) {
    if (unmounted || generation !== ingestionGeneration || isAbort(error)) return
    ingestionState.value = 'error'
    ingestionMessage.value =
      error instanceof Error ? error.message : 'Ingestion history could not load.'
  }
}

function invalidateRunDetail(): void {
  detailController?.abort()
  detailController = undefined
  detailGeneration += 1
  runDetail.value = null
}

async function showRunDetail(runId: string): Promise<void> {
  detailController?.abort()
  const controller = new AbortController()
  detailController = controller
  const generation = ++detailGeneration
  runDetail.value = null
  try {
    const detail = await getIngestionRun(runId, controller.signal)
    if (unmounted || generation !== detailGeneration) return
    runDetail.value = detail
  } catch (error: unknown) {
    if (unmounted || generation !== detailGeneration || isAbort(error)) return
    ingestionMessage.value =
      error instanceof Error ? error.message : 'Ingestion run detail could not load.'
  }
}

async function loadHistoricalImports(): Promise<void> {
  importsController?.abort()
  const controller = new AbortController()
  importsController = controller
  const generation = ++importsGeneration
  importsState.value = 'loading'
  importsMessage.value = ''
  try {
    const page = await listHistoricalImportRuns(controller.signal)
    if (unmounted || generation !== importsGeneration) return
    imports.value = page
    importsState.value = page.items.length ? 'ready' : 'empty'
  } catch (error: unknown) {
    if (unmounted || generation !== importsGeneration || isAbort(error)) return
    imports.value = null
    importsState.value =
      error instanceof HistoricalImportsRequestError && error.errorCode === 'NOT_CONFIGURED'
        ? 'not-configured'
        : 'error'
    importsMessage.value =
      error instanceof Error ? error.message : 'Historical imports could not load.'
  }
}

function resetRunFilters(): void {
  runFilters.status = ''
  runFilters.operationType = ''
  runFilters.source = ''
  runFilters.dateFrom = ''
  runFilters.dateTo = ''
  void loadIngestionRuns()
}

function formatTimestamp(value: string | null): string {
  if (!value) return '—'
  const parsed = new Date(value)
  return Number.isNaN(parsed.valueOf()) ? value : parsed.toLocaleString()
}

function isAbort(error: unknown): boolean {
  return (error instanceof DOMException || error instanceof Error) && error.name === 'AbortError'
}

onMounted(() => {
  void loadIngestionRuns()
  void loadHistoricalImports()
})
onBeforeUnmount(() => {
  unmounted = true
  ingestionController?.abort()
  detailController?.abort()
  importsController?.abort()
})
</script>

<template>
  <section class="workspace-page history-workspace" aria-labelledby="history-title">
    <header class="page-heading">
      <div>
        <p class="eyebrow">Unified immutable records</p>
        <h1 id="history-title">History</h1>
        <p class="page-intro">
          Query draw records, ingestion audits, and historical-import metadata. This workspace
          provides no edit, delete, replay, prediction, ranking, or strategy execution action.
        </p>
      </div>
      <div class="scope-card"><span>Access</span><strong>READ ONLY</strong><small>deterministic queries</small></div>
    </header>

    <nav class="tab-list" aria-label="History sections">
      <button class="button" type="button" :aria-pressed="activeTab === 'draws'" @click="activeTab = 'draws'">Draw History</button>
      <button class="button" type="button" :aria-pressed="activeTab === 'ingestion'" @click="activeTab = 'ingestion'">Ingestion History</button>
      <button class="button" type="button" :aria-pressed="activeTab === 'imports'" @click="activeTab = 'imports'">Historical Import Runs</button>
    </nav>

    <DrawHistoryPage v-if="activeTab === 'draws'" />

    <section v-else-if="activeTab === 'ingestion'" aria-labelledby="ingestion-history-title">
      <h2 id="ingestion-history-title">Ingestion History</h2>
      <form class="panel filter-panel" @submit.prevent="loadIngestionRuns">
        <div class="filter-grid">
          <label><span>Status</span><select v-model="runFilters.status"><option value="">All</option><option>RUNNING</option><option>SUCCESS</option><option>FAILED</option></select></label>
          <label><span>Trigger</span><select v-model="runFilters.operationType"><option value="">All</option><option>DRAW_CSV_IMPORT</option><option>MANUAL_SYNC</option><option>MISSING_DRAW_SCAN</option><option>BOUNDED_BACKFILL</option><option>SCHEDULED_SYNC</option></select></label>
          <label><span>Provider or filename</span><input v-model="runFilters.source" maxlength="255" /></label>
          <label><span>Date from</span><input v-model="runFilters.dateFrom" type="date" /></label>
          <label><span>Date to</span><input v-model="runFilters.dateTo" type="date" /></label>
        </div>
        <div class="filter-actions">
          <button class="button button--primary" type="submit">Apply filters</button>
          <button class="button button--quiet" type="button" @click="resetRunFilters">Reset</button>
        </div>
      </form>

      <p v-if="ingestionState === 'loading'" class="state-panel">Loading ingestion history…</p>
      <div v-else-if="ingestionState === 'error'" class="state-panel state-panel--error"><p>{{ ingestionMessage }}</p><button class="button button--quiet" type="button" @click="loadIngestionRuns">Retry</button></div>
      <p v-else-if="ingestionState === 'empty'" class="state-panel">No ingestion runs match this query.</p>
      <div v-else class="table-wrap">
        <table>
          <caption>Ingestion runs — newest first</caption>
          <thead><tr><th>Status</th><th>Trigger</th><th>Provider / file</th><th>Requested / resolved</th><th>Counts</th><th>Time</th><th>Detail</th></tr></thead>
          <tbody>
            <tr v-for="run in runs" :key="run.run_id">
              <td>{{ run.status }}</td><td>{{ run.trigger }}</td>
              <td>{{ run.provider ?? run.source_filename }}</td>
              <td>{{ run.requested_start ?? '—' }} → {{ run.requested_end ?? '—' }}<small>{{ run.resolved_start ?? '—' }} → {{ run.resolved_end ?? '—' }}</small></td>
              <td>{{ run.fetched_count }} fetched · {{ run.inserted_count }} inserted · {{ run.skipped_count }} duplicate · {{ run.conflict_count }} conflict · {{ run.failed_count }} failed</td>
              <td>{{ formatTimestamp(run.started_at) }}<small>{{ formatTimestamp(run.completed_at) }}</small></td>
              <td><button class="button button--quiet" type="button" @click="showRunDetail(run.run_id)">Open</button></td>
            </tr>
          </tbody>
        </table>
      </div>

      <article v-if="runDetail" class="panel" aria-labelledby="run-detail-title">
        <h3 id="run-detail-title">Run Detail <code>{{ runDetail.run.run_id }}</code></h3>
        <p v-if="runDetail.items_truncated" class="state-panel state-panel--warning">Partial result: showing a bounded item set of {{ runDetail.item_count }} total items.</p>
        <div class="table-wrap">
          <table>
            <caption>Items, conflicts, and failures</caption>
            <thead><tr><th>Draw identity</th><th>Source</th><th>Result</th><th>Duplicate / conflict identity</th><th>Sanitized message</th></tr></thead>
            <tbody>
              <tr v-for="item in runDetail.items" :key="`${item.source_row_number}-${item.draw_number}`">
                <td>{{ item.lottery_type ?? '—' }} / {{ item.draw_number ?? '—' }}</td>
                <td>{{ item.source ?? '—' }}</td><td>{{ item.disposition }}</td>
                <td><code>{{ item.normalized_record_hash ?? '—' }}</code></td><td>{{ item.message ?? '—' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </article>
    </section>

    <section v-else aria-labelledby="historical-imports-title">
      <h2 id="historical-imports-title">Historical Import Runs</h2>
      <p class="page-intro">Metadata only. “Idempotent replay” means repeated import identity handling—not lottery replay.</p>
      <p v-if="importsState === 'loading'" class="state-panel">Loading historical imports…</p>
      <div v-else-if="importsState === 'not-configured'" class="state-panel state-panel--warning"><p>Historical Results storage is not configured.</p><button class="button button--quiet" type="button" @click="loadHistoricalImports">Retry</button></div>
      <div v-else-if="importsState === 'error'" class="state-panel state-panel--error"><p>{{ importsMessage }}</p><button class="button button--quiet" type="button" @click="loadHistoricalImports">Retry</button></div>
      <p v-else-if="importsState === 'empty'" class="state-panel">No completed historical import runs are available.</p>
      <div v-else-if="imports" class="table-wrap">
        <table>
          <caption>Completed historical-import metadata</caption>
          <thead><tr><th>Run</th><th>Import identity</th><th>Source</th><th>Status</th><th>Counts</th><th>Time</th><th>Idempotent replay</th></tr></thead>
          <tbody>
            <tr v-for="run in imports.items" :key="run.run_id">
              <td><code>{{ run.run_id }}</code></td><td><code>{{ run.import_identity_sha256 }}</code></td>
              <td>{{ run.source_kind }}</td><td>{{ run.status }}</td>
              <td>{{ run.strategy_count }} strategies · {{ run.draw_count }} draws · {{ run.portfolio_count }} portfolios</td>
              <td>{{ formatTimestamp(run.started_at) }}<small>{{ formatTimestamp(run.completed_at) }}</small></td>
              <td>{{ run.is_idempotent_replay ? 'YES' : 'NO' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </section>
</template>
