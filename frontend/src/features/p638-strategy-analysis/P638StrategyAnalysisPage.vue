<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import {
  getP638Metrics,
  listP638Runs,
  listP638Strategies,
  P638HistoricalRequestError,
  type P638Metrics,
  type P638Run,
  type P638RunPage,
  type P638Strategy,
  type P638StrategyPage,
} from '../../api/p638Historical'

type State = 'loading' | 'ready' | 'empty' | 'not-configured' | 'unavailable' | 'error'
const PAGE_SIZE = 10

const runsState = ref<State>('loading')
const runsPage = ref<P638RunPage | null>(null)
const runsMessage = ref('')
const selectedRunId = ref('')
const strategiesPage = ref<P638StrategyPage | null>(null)
const strategiesState = ref<State>('loading')
const strategiesMessage = ref('')
const metrics = ref<P638Metrics | null>(null)
const selectedMetrics = ref<P638Metrics | null>(null)
const metricsState = ref<State>('loading')
const metricsMessage = ref('')
const strategyOffset = ref(0)
const selectedStrategyId = ref('')

let mounted = false
let runsController: AbortController | undefined
let strategyController: AbortController | undefined
let metricsController: AbortController | undefined
let runsGeneration = 0
let strategyGeneration = 0
let metricsGeneration = 0

const selectedRun = computed<P638Run | null>(
  () => runsPage.value?.items.find((run) => run.run_id === selectedRunId.value) ?? null,
)
const selectedStrategy = computed<P638Strategy | null>(
  () => strategiesPage.value?.items.find((strategy) => strategy.strategy_id === selectedStrategyId.value) ?? null,
)
const strategyPageNumber = computed(() => Math.floor(strategyOffset.value / PAGE_SIZE) + 1)
const strategyPageCount = computed(() =>
  strategiesPage.value ? Math.max(1, Math.ceil(strategiesPage.value.total_count / PAGE_SIZE)) : 1,
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
    const runId = page.items.some((run) => run.run_id === selectedRunId.value)
      ? selectedRunId.value
      : page.items[0]?.run_id ?? ''
    selectedRunId.value = runId
    if (runId) await loadSelectedRun(runId)
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
  strategyOffset.value = 0
  selectedStrategyId.value = ''
  metrics.value = null
  selectedMetrics.value = null
  await Promise.all([loadStrategies(runId, 0), loadMetrics(runId, undefined)])
}

async function loadStrategies(runId: string, offset: number): Promise<void> {
  strategyController?.abort()
  const controller = new AbortController()
  strategyController = controller
  const generation = ++strategyGeneration
  strategiesState.value = 'loading'
  strategiesMessage.value = ''
  try {
    const page = await listP638Strategies(runId, { limit: PAGE_SIZE, offset }, controller.signal)
    if (!mounted || generation !== strategyGeneration) return
    strategiesPage.value = page
    strategyOffset.value = offset
    strategiesState.value = page.items.length ? 'ready' : 'empty'
  } catch (error: unknown) {
    if (!mounted || generation !== strategyGeneration || isAbort(error)) return
    strategiesPage.value = null
    strategiesState.value = mapState(error)
    strategiesMessage.value = errorMessage(error)
  }
}

async function loadMetrics(runId: string, strategyId: string | undefined): Promise<void> {
  metricsController?.abort()
  const controller = new AbortController()
  metricsController = controller
  const generation = ++metricsGeneration
  metricsState.value = 'loading'
  metricsMessage.value = ''
  try {
    const result = await getP638Metrics(runId, strategyId, controller.signal)
    if (!mounted || generation !== metricsGeneration) return
    if (strategyId) selectedMetrics.value = result
    else metrics.value = result
    metricsState.value = 'ready'
  } catch (error: unknown) {
    if (!mounted || generation !== metricsGeneration || isAbort(error)) return
    metricsState.value = mapState(error)
    metricsMessage.value = errorMessage(error)
  }
}

function selectStrategy(strategyId: string): void {
  selectedStrategyId.value = strategyId
  selectedMetrics.value = null
  if (selectedRunId.value && strategyId) void loadMetrics(selectedRunId.value, strategyId)
}

function changeStrategyPage(delta: number): void {
  if (!strategiesPage.value) return
  const nextOffset = strategyOffset.value + delta * PAGE_SIZE
  if (nextOffset < 0 || nextOffset >= strategiesPage.value.total_count) return
  if (selectedRunId.value) void loadStrategies(selectedRunId.value, nextOffset)
}

function mapState(error: unknown): State {
  if (error instanceof P638HistoricalRequestError) {
    if (error.kind === 'NOT_CONFIGURED') return 'not-configured'
    if (error.kind === 'UNAVAILABLE' || error.kind === 'MALFORMED_RESPONSE') return 'unavailable'
  }
  return 'error'
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'P638 Strategy Analysis could not load.'
}

function isAbort(error: unknown): boolean {
  return (error instanceof DOMException || error instanceof Error) && error.name === 'AbortError'
}

function formatCount(value: number): string {
  return value.toLocaleString()
}

function distributionText(items: Array<{ value: number; count: number }>): string {
  return items.map((item) => `${item.value}: ${item.count.toLocaleString()}`).join(' · ') || '—'
}

onMounted(() => {
  mounted = true
  void loadRuns()
})

onBeforeUnmount(() => {
  mounted = false
  runsController?.abort()
  strategyController?.abort()
  metricsController?.abort()
})
</script>

<template>
  <section class="workspace-page" aria-labelledby="p638-analysis-title">
    <header class="page-heading p638-page-heading">
      <div>
        <p class="eyebrow">Registry coverage · descriptive statistics</p>
        <h1 id="p638-analysis-title">P638 Strategy Analysis</h1>
        <p class="page-intro">
          Inspect the versioned P638 identity ledger, replay coverage, hit distributions, and
          provenance. Excluded identities remain visible with their exact exclusion reason. No
          historical statistic is presented as a forecast, rank, or recommendation.
        </p>
      </div>
      <div class="scope-card"><span>Analysis scope</span><strong>10 identities</strong><small>8 reusable · 2 excluded</small></div>
    </header>

    <p v-if="runsState === 'loading'" class="state-panel">Loading P638 analysis runs…</p>
    <div v-else-if="runsState === 'not-configured'" class="state-panel state-panel--warning"><p>Historical Results storage is not configured for this local runtime.</p></div>
    <div v-else-if="runsState === 'unavailable' || runsState === 'error'" class="state-panel state-panel--error"><p>{{ runsMessage }}</p><button class="button button--quiet" type="button" @click="loadRuns">Retry</button></div>
    <p v-else-if="runsState === 'empty'" class="state-panel">No completed P638 analysis run is available.</p>

    <template v-else-if="runsPage && runsPage.items.length">
      <article class="panel">
        <div class="panel__heading"><div><p class="step-label">Frozen source</p><h2>Analysis run</h2></div><button class="button button--quiet" type="button" @click="loadRuns">Refresh</button></div>
        <label class="filter-field"><span>Historical run</span><select v-model="selectedRunId" @change="loadSelectedRun(selectedRunId)"><option v-for="run in runsPage.items" :key="run.run_id" :value="run.run_id">{{ run.run_id }} · {{ run.source_run_id }}</option></select></label>
        <p v-if="selectedRun" class="panel__note">Source replay <code>{{ selectedRun.source_replay_sha256 }}</code> · draw authority <code>{{ selectedRun.source_draw_db_sha256 }}</code> · SSOT <code>{{ selectedRun.second_zone_ssot_version }}</code></p>
      </article>

      <div v-if="metricsState === 'loading'" class="state-panel">Loading aggregate P638 statistics…</div>
      <div v-else-if="metricsState === 'unavailable' || metricsState === 'error'" class="state-panel state-panel--error"><p>{{ metricsMessage }}</p><button class="button button--quiet" type="button" @click="loadSelectedRun(selectedRunId)">Retry</button></div>
      <template v-else-if="metrics">
        <div class="section-heading p638-section-heading"><div><p class="step-label">Run aggregate</p><h2>Descriptive coverage</h2></div><span class="table-note">P638 only · no predictive interpretation</span></div>
        <div class="metric-grid metric-grid--p638"><div><span>Targets</span><strong>{{ formatCount(metrics.target_count) }}</strong></div><div><span>Complete</span><strong>{{ formatCount(metrics.complete_target_count) }}</strong></div><div><span>Excluded</span><strong>{{ formatCount(metrics.excluded_target_count) }}</strong></div><div><span>Failed</span><strong>{{ formatCount(metrics.failed_target_count) }}</strong></div><div><span>Tickets</span><strong>{{ formatCount(metrics.ticket_count) }}</strong></div><div><span>4+ + zone 2</span><strong>{{ formatCount(metrics.combined_zone1_4plus_zone2_hit_count) }}</strong></div></div>
        <div class="workspace-grid workspace-grid--p638"><article class="panel"><p class="step-label">Zone 1 hit distribution</p><h2>Stored comparisons</h2><p class="distribution-line">{{ distributionText(metrics.zone1_hit_distribution) }}</p></article><article class="panel"><p class="step-label">Zone 2 distribution</p><h2>Stored comparisons</h2><p class="distribution-line">{{ distributionText(metrics.zone2_hit_distribution) }}</p></article></div>
      </template>

      <div class="section-heading p638-section-heading"><div><p class="step-label">Registry snapshot</p><h2>All identities and replay coverage</h2></div><span class="table-note">{{ strategiesPage?.total_count ?? 0 }} identities</span></div>
      <div v-if="strategiesState === 'loading'" class="state-panel">Loading the strategy ledger…</div>
      <div v-else-if="strategiesState === 'unavailable' || strategiesState === 'error'" class="state-panel state-panel--error"><p>{{ strategiesMessage }}</p><button class="button button--quiet" type="button" @click="loadStrategies(selectedRunId, strategyOffset)">Retry</button></div>
      <p v-else-if="strategiesState === 'empty'" class="state-panel">The P638 identity ledger is empty.</p>
      <template v-else-if="strategiesPage">
        <div class="table-wrap"><table><caption>Versioned P638 strategy identities</caption><thead><tr><th>Identity</th><th>Lifecycle / replay</th><th>Contracts</th><th>Coverage</th><th>Provenance / exclusion</th><th>Analysis</th></tr></thead><tbody>
          <tr v-for="strategy in strategiesPage.items" :key="strategy.strategy_snapshot_id"><td><strong>{{ strategy.strategy_id }}</strong><small>{{ strategy.display_label }}</small><small>{{ strategy.strategy_version }}</small></td><td>{{ strategy.lifecycle_status }}<small>{{ strategy.replay_status }}</small></td><td>{{ strategy.zone1_contract }}<small>{{ strategy.zone2_contract }}</small></td><td>{{ formatCount(strategy.complete_target_count) }} complete<small>{{ formatCount(strategy.excluded_target_count) }} excluded · {{ formatCount(strategy.ticket_count) }} tickets</small></td><td><code>{{ strategy.exclusion_reason ?? strategy.source_paths.join(' · ') }}</code><small>{{ strategy.provenance }}</small></td><td><button class="button button--quiet" type="button" :disabled="!strategy.executable" @click="selectStrategy(strategy.strategy_id)">{{ strategy.executable ? 'Analyse' : 'Excluded' }}</button></td></tr>
        </tbody></table></div>
        <div class="pagination p638-pagination"><button class="button button--quiet" type="button" :disabled="strategyOffset === 0" @click="changeStrategyPage(-1)">Previous</button><span>Page {{ strategyPageNumber }} / {{ strategyPageCount }}</span><button class="button button--quiet" type="button" :disabled="strategyOffset + PAGE_SIZE >= strategiesPage.total_count" @click="changeStrategyPage(1)">Next</button></div>
      </template>

      <div v-if="selectedStrategy" class="panel p638-detail-panel" aria-live="polite">
        <div class="panel__heading"><div><p class="step-label">Selected identity</p><h2>{{ selectedStrategy.strategy_id }}</h2></div><span class="status-pill status-pill--complete">{{ selectedStrategy.replay_status }}</span></div>
        <p class="panel__note">{{ selectedStrategy.display_label }} · {{ selectedStrategy.strategy_version }} · {{ selectedStrategy.zone1_contract }} + {{ selectedStrategy.zone2_contract }}. Metrics describe stored replay rows only.</p>
        <div v-if="selectedMetrics" class="metric-grid metric-grid--p638"><div><span>Targets</span><strong>{{ formatCount(selectedMetrics.target_count) }}</strong></div><div><span>Complete</span><strong>{{ formatCount(selectedMetrics.complete_target_count) }}</strong></div><div><span>Excluded</span><strong>{{ formatCount(selectedMetrics.excluded_target_count) }}</strong></div><div><span>Tickets</span><strong>{{ formatCount(selectedMetrics.ticket_count) }}</strong></div><div><span>4+ + zone 2</span><strong>{{ formatCount(selectedMetrics.combined_zone1_4plus_zone2_hit_count) }}</strong></div><div><span>Draw range</span><strong>{{ selectedMetrics.first_draw_number ?? '—' }} → {{ selectedMetrics.last_draw_number ?? '—' }}</strong></div></div>
        <p v-else-if="metricsState === 'loading'" class="state-panel">Loading identity metrics…</p><p v-else class="state-panel state-panel--error">{{ metricsMessage || 'Identity metrics are unavailable.' }}</p>
      </div>
    </template>
  </section>
</template>
