<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'

import {
  listDraws,
  type DrawHistoryQuery,
  type DrawHistoryResponse,
} from '../../api/drawData'
import { lotteryTypeDisplayLabel } from '../../utils/lotteryDisplayLabel'
import LotteryNumberBall from '../../components/LotteryNumberBall.vue'
import { isOptionalIsoCalendarDate } from '../../utils/isoDate'

type LoadState = 'loading' | 'ready' | 'empty' | 'error'
type DrawRecord = DrawHistoryResponse['records'][number]

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
const dateFiltersValid = computed(
  () =>
    isOptionalIsoCalendarDate(query.dateFrom) &&
    isOptionalIsoCalendarDate(query.dateTo),
)
const dateFromError = computed(() =>
  query.dateFrom && !isOptionalIsoCalendarDate(query.dateFrom)
    ? 'Enter a valid Gregorian date in YYYY-MM-DD format.'
    : '',
)
const dateToError = computed(() =>
  query.dateTo && !isOptionalIsoCalendarDate(query.dateTo)
    ? 'Enter a valid Gregorian date in YYYY-MM-DD format.'
    : '',
)
const mainNumberColumnLabel = computed(() =>
  query.lotteryType === 'POWER_LOTTO' ? 'First zone' : 'Main numbers',
)
const secondaryNumberColumnLabel = computed(() => {
  if (query.lotteryType === 'POWER_LOTTO') return 'Second zone'
  if (query.lotteryType === 'DAILY_539') return 'No secondary number'
  return 'Special number'
})
let requestController: AbortController | undefined
let requestVersion = 0

async function loadHistory(): Promise<void> {
  if (!dateFiltersValid.value) return
  requestController?.abort()
  const controller = new AbortController()
  requestController = controller
  const version = ++requestVersion
  const requestedQuery = { ...query }
  loadState.value = 'loading'
  result.value = null
  errorMessage.value = ''
  try {
    const page = await listDraws(requestedQuery, controller.signal)
    if (version !== requestVersion) return
    if (page.records.some((record) => record.lottery_type !== requestedQuery.lotteryType)) {
      throw new Error('Draw History returned records for a different lottery type.')
    }
    result.value = page
    loadState.value = page.records.length === 0 ? 'empty' : 'ready'
  } catch (error: unknown) {
    if (version !== requestVersion || isAbort(error)) return
    result.value = null
    loadState.value = 'error'
    errorMessage.value = error instanceof Error ? error.message : 'Draw History could not load.'
  }
}

async function applyFilters(): Promise<void> {
  if (!dateFiltersValid.value) return
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

async function changeLotteryType(event: Event): Promise<void> {
  const selectedType = (event.target as HTMLSelectElement).value
  if (!isLotteryType(selectedType) || selectedType === query.lotteryType) return
  query.lotteryType = selectedType
  query.page = 1
  query.drawNumber = ''
  await loadHistory()
}

function isLotteryType(value: string): value is DrawHistoryQuery['lotteryType'] {
  return value === 'BIG_LOTTO' || value === 'POWER_LOTTO' || value === 'DAILY_539'
}

function mainNumberAriaLabel(value: number): string {
  return query.lotteryType === 'POWER_LOTTO'
    ? `First zone number ${value}`
    : `Main number ${value}`
}

function secondaryNumberAriaLabel(value: number): string {
  return query.lotteryType === 'POWER_LOTTO'
    ? `Second zone number ${value}`
    : `Special number ${value}`
}

function secondaryNumbers(record: DrawRecord): number[] {
  return query.lotteryType === 'DAILY_539' ? [] : record.special_numbers
}

function displayText(value: unknown): string {
  return typeof value === 'string' && value ? value : '—'
}

function formatTimestamp(value: string): string {
  const parsed = new Date(value)
  return Number.isNaN(parsed.valueOf()) ? value : parsed.toLocaleString('en-US')
}

function isAbort(error: unknown): boolean {
  return error instanceof DOMException && error.name === 'AbortError'
}

onMounted(loadHistory)
onBeforeUnmount(() => {
  requestVersion += 1
  requestController?.abort()
})
</script>

<template>
  <section class="workspace-page" aria-labelledby="draw-history-title">
    <header class="page-heading">
      <div>
        <p class="eyebrow">P600D · immutable records</p>
        <h1 id="draw-history-title">Draw History</h1>
        <p class="page-intro">
          Search locally imported {{ lotteryTypeDisplayLabel(query.lotteryType) }} draws. Results use deterministic date and string-identity ordering.
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
          <select :value="query.lotteryType" name="lottery-type" @change="changeLotteryType">
            <option value="BIG_LOTTO">{{ lotteryTypeDisplayLabel('BIG_LOTTO') }}</option>
            <option value="POWER_LOTTO">{{ lotteryTypeDisplayLabel('POWER_LOTTO') }}</option>
            <option value="DAILY_539">{{ lotteryTypeDisplayLabel('DAILY_539') }}</option>
          </select>
        </label>
        <label>
          <span>Draw number contains</span>
          <input v-model.trim="query.drawNumber" name="draw-number" inputmode="numeric" pattern="[0-9]*" placeholder="e.g. 0001" />
        </label>
        <label>
          <span>Date from</span>
          <input v-model="query.dateFrom" name="date-from" type="text" inputmode="numeric" pattern="[0-9]{4}-[0-9]{2}-[0-9]{2}" maxlength="10" placeholder="YYYY-MM-DD" autocomplete="off" :aria-invalid="dateFromError ? 'true' : undefined" :aria-describedby="dateFromError ? 'draw-date-from-error' : undefined" />
          <small v-if="dateFromError" id="draw-date-from-error" class="date-validation-error" role="alert">{{ dateFromError }}</small>
        </label>
        <label>
          <span>Date to</span>
          <input v-model="query.dateTo" name="date-to" type="text" inputmode="numeric" pattern="[0-9]{4}-[0-9]{2}-[0-9]{2}" maxlength="10" placeholder="YYYY-MM-DD" autocomplete="off" :aria-invalid="dateToError ? 'true' : undefined" :aria-describedby="dateToError ? 'draw-date-to-error' : undefined" />
          <small v-if="dateToError" id="draw-date-to-error" class="date-validation-error" role="alert">{{ dateToError }}</small>
        </label>
      </div>
      <div class="filter-actions">
        <button class="button button--primary" type="submit" :disabled="!dateFiltersValid">Apply filters</button>
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
            <th>Draw</th><th>Date</th><th>{{ mainNumberColumnLabel }}</th><th>{{ secondaryNumberColumnLabel }}</th><th>Source</th><th>Ingestion</th><th>Timestamps</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="record in result.records" :key="`${record.lottery_type}-${record.draw_number}`">
            <td>
              <small>{{ lotteryTypeDisplayLabel(record.lottery_type) }}</small>
              <code class="draw-identity">{{ record.draw_number }}</code>
            </td>
            <td>{{ record.draw_date }}</td>
            <td>
              <span class="number-chips">
                <LotteryNumberBall
                  v-for="number in record.main_numbers"
                  :key="number"
                  :value="number"
                  variant="main"
                  size="sm"
                  :aria-label="mainNumberAriaLabel(number)"
                />
              </span>
            </td>
            <td>
              <span class="number-chips">
                <LotteryNumberBall
                  v-for="sp in secondaryNumbers(record)"
                  :key="sp"
                  :value="sp"
                  variant="special"
                  size="sm"
                  :aria-label="secondaryNumberAriaLabel(sp)"
                />
                <span v-if="query.lotteryType === 'DAILY_539'">—</span>
              </span>
            </td>
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
