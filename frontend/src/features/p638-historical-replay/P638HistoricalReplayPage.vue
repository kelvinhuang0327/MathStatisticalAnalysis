<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'

import {
  getP638Target,
  listP638Replay,
  listP638Runs,
  listP638Strategies,
  P638HistoricalRequestError,
  type P638Replay,
  type P638ReplayPage,
  type P638Run,
  type P638RunPage,
  type P638Status,
  type P638StrategyPage,
} from '../../api/p638Historical'

type State = 'loading' | 'ready' | 'empty' | 'not-configured' | 'unavailable' | 'error'
type StatusFilter = '' | P638Status

const PAGE_SIZE = 25
const runsState = ref<State>('loading')
const runsPage = ref<P638RunPage | null>(null)
const runsMessage = ref('')
const selectedRunId = ref('')
const strategiesPage = ref<P638StrategyPage | null>(null)
const replayPage = ref<P638ReplayPage | null>(null)
const dataState = ref<State>('loading')
const dataMessage = ref('')
const detailState = ref<'closed' | 'loading' | 'ready' | 'error'>('closed')
const detail = ref<P638Replay | null>(null)
const detailMessage = ref('')
const replayOffset = ref(0)
const filters = reactive<{
  strategyId: string
  dateFrom: string
  dateTo: string
  status: StatusFilter
}>({ strategyId: '', dateFrom: '', dateTo: '', status: '' })

let mounted = false
let runsController: AbortController | undefined
let dataController: AbortController | undefined
let detailController: AbortController | undefined
let runsGeneration = 0
let dataGeneration = 0
let detailGeneration = 0

const selectedRun = computed<P638Run | null>(
  () => runsPage.value?.items.find((run) => run.run_id === selectedRunId.value) ?? null,
)
const replayPageNumber = computed(() => Math.floor(replayOffset.value / PAGE_SIZE) + 1)
const replayPageCount = computed(() =>
  replayPage.value ? Math.max(1, Math.ceil(replayPage.value.total_count / PAGE_SIZE)) : 1,
)

async function loadRuns(): Promise<void> {
  runsController?.abort()
  const controller = new AbortController()
  runsController = controller
  const generation = ++runsGeneration
  runsState.value = 'loading'
  runsMessage.value = ''
  try {
    const page = await listP638Runs({ limit: 25, offset: 0 }, controller.signal)
    if (!mounted || generation !== runsGeneration) return
    runsPage.value = page
    runsState.value = page.items.length ? 'ready' : 'empty'
    const nextRunId = page.items.some((run) => run.run_id === selectedRunId.value)
      ? selectedRunId.value
      : page.items[0]?.run_id ?? ''
    selectedRunId.value = nextRunId
    if (nextRunId) await loadSelectedRun(nextRunId)
  } catch (error: unknown) {
    if (!mounted || generation !== runsGeneration || isAbort(error)) return
    runsPage.value = null
    runsState.value = mapState(error)
    runsMessage.value = errorMessage(error)
  }
}

async function loadSelectedRun(runId: string): Promise<void> {
  if (!runId) return
  selectedRunId.value = runId
  replayOffset.value = 0
  // A detail response is scoped to the selected run. Invalidate it before
  // starting the new run's requests so an older response cannot render under
  // the new run after a run switch.
  closeDetail()
  dataController?.abort()
  const controller = new AbortController()
  dataController = controller
  const generation = ++dataGeneration
  dataState.value = 'loading'
  dataMessage.value = ''
  try {
    const [strategyPage, replay] = await Promise.all([
      listP638Strategies(runId, { limit: 200, offset: 0 }, controller.signal),
      listP638Replay(
        runId,
        {
          limit: PAGE_SIZE,
          offset: 0,
          strategyId: filters.strategyId || undefined,
          dateFrom: filters.dateFrom || undefined,
          dateTo: filters.dateTo || undefined,
          status: filters.status || undefined,
        },
        controller.signal,
      ),
    ])
    if (!mounted || generation !== dataGeneration) return
    strategiesPage.value = strategyPage
    replayPage.value = replay
    dataState.value = replay.items.length ? 'ready' : 'empty'
  } catch (error: unknown) {
    if (!mounted || generation !== dataGeneration || isAbort(error)) return
    strategiesPage.value = null
    replayPage.value = null
    dataState.value = mapState(error)
    dataMessage.value = errorMessage(error)
  }
}

function applyFilters(): void {
  if (selectedRunId.value) void loadSelectedRun(selectedRunId.value)
}

function changeReplayPage(delta: number): void {
  if (!replayPage.value) return
  const nextOffset = replayOffset.value + delta * PAGE_SIZE
  if (nextOffset < 0 || nextOffset >= replayPage.value.total_count) return
  replayOffset.value = nextOffset
  void loadReplayPage()
}

async function loadReplayPage(): Promise<void> {
  if (!selectedRunId.value) return
  dataController?.abort()
  const controller = new AbortController()
  dataController = controller
  const generation = ++dataGeneration
  dataState.value = 'loading'
  dataMessage.value = ''
  try {
    const replay = await listP638Replay(
      selectedRunId.value,
      {
        limit: PAGE_SIZE,
        offset: replayOffset.value,
        strategyId: filters.strategyId || undefined,
        dateFrom: filters.dateFrom || undefined,
        dateTo: filters.dateTo || undefined,
        status: filters.status || undefined,
      },
      controller.signal,
    )
    if (!mounted || generation !== dataGeneration) return
    replayPage.value = replay
    dataState.value = replay.items.length ? 'ready' : 'empty'
  } catch (error: unknown) {
    if (!mounted || generation !== dataGeneration || isAbort(error)) return
    dataState.value = mapState(error)
    dataMessage.value = errorMessage(error)
  }
}

async function openTarget(targetId: string): Promise<void> {
  if (!selectedRunId.value) return
  detailController?.abort()
  const controller = new AbortController()
  detailController = controller
  const generation = ++detailGeneration
  detailState.value = 'loading'
  detail.value = null
  detailMessage.value = ''
  try {
    const result = await getP638Target(selectedRunId.value, targetId, controller.signal)
    if (!mounted || generation !== detailGeneration) return
    detail.value = result
    detailState.value = 'ready'
  } catch (error: unknown) {
    if (!mounted || generation !== detailGeneration || isAbort(error)) return
    detailState.value = 'error'
    detailMessage.value = errorMessage(error)
  }
}

function closeDetail(): void {
  detailController?.abort()
  detailGeneration += 1
  detail.value = null
  detailState.value = 'closed'
}

function mapState(error: unknown): State {
  if (error instanceof P638HistoricalRequestError) {
    if (error.kind === 'NOT_CONFIGURED') return 'not-configured'
    if (error.kind === 'UNAVAILABLE' || error.kind === 'MALFORMED_RESPONSE') return 'unavailable'
  }
  return 'error'
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'P638 Historical Results could not load.'
}

function isAbort(error: unknown): boolean {
  return (error instanceof DOMException || error instanceof Error) && error.name === 'AbortError'
}

function formatCount(value: number): string {
  return value.toLocaleString()
}

onMounted(() => {
  mounted = true
  void loadRuns()
})

onBeforeUnmount(() => {
  mounted = false
  runsController?.abort()
  dataController?.abort()
  detailController?.abort()
})
</script>

<template>
  <section class="workspace-page" aria-labelledby="p638-replay-title">
    <header class="page-heading p638-page-heading">
      <div>
        <p class="eyebrow">Historical Results V2 · read-only projection</p>
        <h1 id="p638-replay-title">P638 Historical Replay</h1>
        <p class="page-intro">
          Browse the complete Power Lotto P638 replay ledger, including every reusable result and
          every explicit exclusion. Results are descriptive historical evidence; this page makes
          no future prediction or betting recommendation.
        </p>
      </div>
      <div class="scope-card"><span>Lottery scope</span><strong>POWER_LOTTO</strong><small>P638 · server-side filters</small></div>
    </header>

    <p v-if="runsState === 'loading'" class="state-panel">Loading P638 run provenance…</p>
    <div v-else-if="runsState === 'not-configured'" class="state-panel state-panel--warning"><p>Historical Results storage is not configured for this local runtime.</p></div>
    <div v-else-if="runsState === 'unavailable' || runsState === 'error'" class="state-panel state-panel--error"><p>{{ runsMessage }}</p><button class="button button--quiet" type="button" @click="loadRuns">Retry</button></div>
    <p v-else-if="runsState === 'empty'" class="state-panel">No completed P638 Historical Results V2 run is available.</p>

    <template v-else-if="runsPage && runsPage.items.length">
      <div class="workspace-grid workspace-grid--p638">
        <article class="panel">
          <div class="panel__heading"><div><p class="step-label">Committed run</p><h2>Run provenance</h2></div><button class="button button--quiet" type="button" @click="loadRuns">Refresh</button></div>
          <label class="filter-field"><span>Historical run</span><select v-model="selectedRunId" @change="loadSelectedRun(selectedRunId)"><option v-for="run in runsPage.items" :key="run.run_id" :value="run.run_id">{{ run.run_id }} · {{ run.status }}</option></select></label>
          <template v-if="selectedRun">
            <div class="metric-grid metric-grid--p638">
              <div><span>Strategies</span><strong>{{ formatCount(selectedRun.strategy_count) }}</strong></div><div><span>Draws</span><strong>{{ formatCount(selectedRun.draw_count) }}</strong></div><div><span>Complete targets</span><strong>{{ formatCount(selectedRun.complete_target_count) }}</strong></div><div><span>Excluded targets</span><strong>{{ formatCount(selectedRun.excluded_target_count) }}</strong></div><div><span>Failed targets</span><strong>{{ formatCount(selectedRun.failed_target_count) }}</strong></div><div><span>Tickets</span><strong>{{ formatCount(selectedRun.ticket_count) }}</strong></div>
            </div>
            <dl class="provenance-list">
              <div><dt>Source replay run</dt><dd><code>{{ selectedRun.source_run_id }}</code></dd></div><div><dt>Replay SHA-256</dt><dd><code>{{ selectedRun.source_replay_sha256 }}</code></dd></div><div><dt>Draw DB SHA-256</dt><dd><code>{{ selectedRun.source_draw_db_sha256 }}</code></dd></div><div><dt>Second-zone SSOT</dt><dd><code>{{ selectedRun.second_zone_ssot_version }}</code></dd></div><div><dt>Draw range</dt><dd>{{ selectedRun.first_draw_number }} ({{ selectedRun.first_draw_date }}) → {{ selectedRun.last_draw_number }} ({{ selectedRun.last_draw_date }})</dd></div>
            </dl>
          </template>
        </article>

        <article class="panel">
          <p class="step-label">Query contract</p><h2>Replay filters</h2><p class="panel__note">Filters are applied by the API before pagination. The page never loads the full replay into the browser.</p>
          <div class="filter-grid filter-grid--p638">
            <label class="filter-field"><span>Strategy identity</span><select v-model="filters.strategyId"><option value="">All current identities</option><option v-for="strategy in strategiesPage?.items ?? []" :key="strategy.strategy_id" :value="strategy.strategy_id">{{ strategy.strategy_id }} · {{ strategy.replay_status }}</option></select></label>
            <label class="filter-field"><span>Status</span><select v-model="filters.status"><option value="">All statuses</option><option value="COMPLETE">COMPLETE</option><option value="EXCLUDED_INSUFFICIENT_HISTORY">EXCLUDED_INSUFFICIENT_HISTORY</option><option value="FAILED">FAILED</option></select></label>
            <label class="filter-field"><span>Draw date from</span><input v-model="filters.dateFrom" type="date" /></label><label class="filter-field"><span>Draw date to</span><input v-model="filters.dateTo" type="date" /></label>
          </div>
          <button class="button button--primary" type="button" @click="applyFilters">Apply server-side filters</button>
        </article>
      </div>

      <div v-if="dataState === 'loading'" class="state-panel">Loading the selected P638 replay page…</div>
      <div v-else-if="dataState === 'unavailable' || dataState === 'error'" class="state-panel state-panel--error"><p>{{ dataMessage }}</p><button class="button button--quiet" type="button" @click="loadSelectedRun(selectedRunId)">Retry</button></div>
      <p v-else-if="dataState === 'empty'" class="state-panel">No P638 targets match the selected server-side filters.</p>
      <template v-else-if="replayPage">
        <div class="section-heading p638-section-heading"><div><p class="step-label">Exact source rows</p><h2>Replay targets</h2></div><span class="table-note">{{ formatCount(replayPage.total_count) }} matching targets · page {{ replayPageNumber }} of {{ replayPageCount }}</span></div>
        <div class="table-wrap"><table><caption>P638 target replay and ticket evidence</caption><thead><tr><th>Target draw</th><th>Strategy</th><th>Status</th><th>History boundary</th><th>Tickets</th><th>Source</th><th>Detail</th></tr></thead><tbody>
          <tr v-for="item in replayPage.items" :key="item.target_id"><td><strong>{{ item.target_draw_number }}</strong><small>{{ item.target_draw_date }}</small></td><td><code>{{ item.strategy_id }}</code><small>{{ item.strategy_version }}</small></td><td><span :class="item.status === 'COMPLETE' ? 'status-pill status-pill--complete' : 'status-pill status-pill--excluded'">{{ item.status }}</span><small v-if="item.exclusion_reason">{{ item.exclusion_reason }}</small></td><td>{{ item.history_boundary_draw_number ?? '—' }}<small>{{ item.history_length }} draws · {{ item.history_boundary_date ?? '—' }}</small></td><td>{{ item.tickets.length }} / {{ item.expected_ticket_count }}</td><td><code>{{ item.source_target_locator ?? '—' }}</code></td><td><button class="button button--quiet" type="button" @click="openTarget(item.target_id)">Open</button></td></tr>
        </tbody></table></div>
        <div class="pagination p638-pagination"><button class="button button--quiet" type="button" :disabled="replayOffset === 0" @click="changeReplayPage(-1)">Previous</button><span>Page {{ replayPageNumber }} / {{ replayPageCount }}</span><button class="button button--quiet" type="button" :disabled="replayOffset + PAGE_SIZE >= replayPage.total_count" @click="changeReplayPage(1)">Next</button></div>
      </template>

      <div v-if="detailState === 'loading'" class="state-panel">Loading target detail…</div>
      <div v-else-if="detailState === 'error'" class="state-panel state-panel--error"><p>{{ detailMessage }}</p><button class="button button--quiet" type="button" @click="closeDetail">Close</button></div>
      <article v-else-if="detail" class="panel p638-detail-panel" aria-labelledby="p638-detail-title">
        <div class="panel__heading"><div><p class="step-label">Target detail</p><h2 id="p638-detail-title">{{ detail.target_id }}</h2></div><button class="button button--quiet" type="button" @click="closeDetail">Close</button></div>
        <p class="panel__note">Actual draw: {{ detail.actual_zone1_numbers.join(', ') }} + {{ detail.actual_zone2_number }}. This is a historical comparison record, not a generated bet.</p>
        <div v-if="detail.tickets.length" class="table-wrap"><table><caption>Stored ticket comparisons</caption><thead><tr><th>Position</th><th>Predicted zone 1</th><th>Predicted zone 2</th><th>Hits</th><th>Provenance</th></tr></thead><tbody><tr v-for="ticket in detail.tickets" :key="ticket.ticket_id"><td>{{ ticket.ticket_position }}</td><td>{{ ticket.predicted_zone1_numbers.join(', ') }}</td><td>{{ ticket.predicted_zone2_number }}</td><td>{{ ticket.zone1_hit_count }} + zone 2 {{ ticket.zone2_hit ? 'HIT' : 'MISS' }}</td><td><code>{{ ticket.source_record_locator ?? ticket.source_replay_sha256 }}</code></td></tr></tbody></table></div>
        <p v-else class="state-panel">This target has no stored tickets because it is explicitly excluded or failed.</p><p class="provenance-line">{{ detail.provenance }}</p>
      </article>
    </template>
  </section>
</template>
