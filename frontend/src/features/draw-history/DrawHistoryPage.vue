<script setup lang="ts">
import { onBeforeUnmount, onMounted, reactive, ref } from 'vue'

import {
  listDraws,
  type DrawHistoryQuery,
  type DrawHistoryResponse,
} from '../../api/drawData'

type LoadState = 'loading' | 'ready' | 'empty' | 'error'

const query = reactive<DrawHistoryQuery>({
  lotteryType: 'BIG_LOTTO',
  drawNumber: '',
  dateFrom: '',
  dateTo: '',
  page: 1,
  pageSize: 25,
})
const result = ref<DrawHistoryResponse | null>(null)
const loadState = ref<LoadState>('loading')
const errorMessage = ref('')
let requestController: AbortController | undefined

async function loadHistory(): Promise<void> {
  requestController?.abort()
  requestController = new AbortController()
  loadState.value = 'loading'
  errorMessage.value = ''
  try {
    const page = await listDraws({ ...query }, requestController.signal)
    result.value = page
    loadState.value = page.records.length === 0 ? 'empty' : 'ready'
  } catch (error: unknown) {
    if (isAbort(error)) return
    result.value = null
    loadState.value = 'error'
    errorMessage.value = error instanceof Error ? error.message : 'Draw History could not load.'
  }
}

async function applyFilters(): Promise<void> {
  query.page = 1
  await loadHistory()
}

async function resetQuery(): Promise<void> {
  query.drawNumber = ''
  query.dateFrom = ''
  query.dateTo = ''
  query.page = 1
  query.pageSize = 25
  await loadHistory()
}

async function changePage(direction: -1 | 1): Promise<void> {
  const target = query.page + direction
  const totalPages = result.value?.total_pages ?? 0
  if (target < 1 || (totalPages > 0 && target > totalPages)) return
  query.page = target
  await loadHistory()
}

async function changePageSize(): Promise<void> {
  query.page = 1
  await loadHistory()
}

function displayText(value: unknown): string {
  return typeof value === 'string' && value ? value : '—'
}

function formatTimestamp(value: string): string {
  const parsed = new Date(value)
  return Number.isNaN(parsed.valueOf()) ? value : parsed.toLocaleString()
}

function isAbort(error: unknown): boolean {
  return error instanceof DOMException && error.name === 'AbortError'
}

onMounted(loadHistory)
onBeforeUnmount(() => requestController?.abort())
</script>

<template>
  <section class="workspace-page" aria-labelledby="draw-history-title">
    <header class="page-heading">
      <div>
        <p class="eyebrow">P600D · immutable records</p>
        <h1 id="draw-history-title">Draw History</h1>
        <p class="page-intro">
          Search locally imported BIG_LOTTO draws. Results use deterministic date and string-identity ordering.
        </p>
      </div>
      <div class="scope-card" aria-label="History result count">
        <span>Matching draws</span>
        <strong>{{ loadState === 'loading' || loadState === 'error' ? '—' : (result?.total_count ?? 0) }}</strong>
        <small>read-only</small>
      </div>
    </header>

    <form class="panel filter-panel" @submit.prevent="applyFilters">
      <div class="filter-grid">
        <label>
          <span>Lottery type</span>
          <select :value="query.lotteryType" disabled>
            <option value="BIG_LOTTO">BIG_LOTTO</option>
          </select>
        </label>
        <label>
          <span>Draw number contains</span>
          <input v-model.trim="query.drawNumber" name="draw-number" inputmode="numeric" pattern="[0-9]*" placeholder="e.g. 0001" />
        </label>
        <label>
          <span>Date from</span>
          <input v-model="query.dateFrom" name="date-from" type="date" />
        </label>
        <label>
          <span>Date to</span>
          <input v-model="query.dateTo" name="date-to" type="date" />
        </label>
      </div>
      <div class="filter-actions">
        <button class="button button--primary" type="submit">Apply filters</button>
        <button class="button button--quiet" type="button" @click="resetQuery">Reset query</button>
      </div>
    </form>

    <div class="history-toolbar">
      <p v-if="result" class="sort-copy">Sort: {{ result.sort.join(' · ') }}</p>
      <label class="page-size-control">
        <span>Rows per page</span>
        <select v-model.number="query.pageSize" name="page-size" @change="changePageSize">
          <option :value="10">10</option>
          <option :value="25">25</option>
          <option :value="50">50</option>
          <option :value="100">100</option>
        </select>
      </label>
    </div>

    <div class="history-state" aria-live="polite">
      <p v-if="loadState === 'loading'" class="state-panel">Loading draw history…</p>
      <div v-else-if="loadState === 'error'" class="state-panel state-panel--error">
        <p>{{ errorMessage }}</p>
        <button class="button button--quiet" type="button" @click="loadHistory">Retry</button>
      </div>
      <p v-else-if="loadState === 'empty'" class="state-panel">
        No draws match this query. Import a canonical CSV in Data Center or reset the filters.
      </p>
    </div>

    <div v-if="loadState === 'ready' && result" class="table-wrap history-table">
      <table>
        <caption>Draw history — no edit or delete operations</caption>
        <thead>
          <tr>
            <th>Draw</th><th>Date</th><th>Main numbers</th><th>Special</th><th>Source</th><th>Ingestion</th><th>Timestamps</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="record in result.records" :key="`${record.lottery_type}-${record.draw_number}`">
            <td>
              <small>{{ record.lottery_type }}</small>
              <code class="draw-identity">{{ record.draw_number }}</code>
            </td>
            <td>{{ record.draw_date }}</td>
            <td>
              <span class="number-chips">
                <span v-for="number in record.main_numbers" :key="number">{{ number }}</span>
              </span>
            </td>
            <td><span class="number-chip number-chip--special">{{ record.special_numbers.join(' · ') }}</span></td>
            <td>
              <strong>{{ displayText(record.source_name) }}</strong>
              <small>{{ displayText(record.source_reference) }}</small>
            </td>
            <td><code>{{ record.ingestion_run_id }}</code></td>
            <td>
              <small>Created {{ formatTimestamp(record.created_at) }}</small>
              <small>Updated {{ formatTimestamp(record.updated_at) }}</small>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <nav v-if="result" class="pagination" aria-label="Draw history pages">
      <button class="button button--quiet" type="button" :disabled="query.page <= 1 || loadState === 'loading'" @click="changePage(-1)">
        Previous
      </button>
      <span>Page {{ result.page }} of {{ result.total_pages || 1 }}</span>
      <button
        class="button button--quiet"
        type="button"
        :disabled="result.total_pages === 0 || query.page >= result.total_pages || loadState === 'loading'"
        @click="changePage(1)"
      >
        Next
      </button>
    </nav>
  </section>
</template>
