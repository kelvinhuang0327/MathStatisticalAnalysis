<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import {
  getT539Coverage,
  getT539Metrics,
  getT539Rankings,
  listT539Runs,
  listT539Strategies,
  T539HistoricalRequestError,
  type T539CoverageLedger,
  type T539Metrics,
  type T539RankingPage,
  type T539Run,
  type T539RunPage,
  type T539Strategy,
  type T539StrategyPage,
} from '../../api/t539Historical'
import type { LotteryType } from '../../api/strategies'
import { lotteryTypeDisplayLabel } from '../../utils/lotteryDisplayLabel'

type State = 'loading' | 'ready' | 'empty' | 'not-configured' | 'unavailable' | 'malformed' | 'error'
type SelectedMetricsState = State | 'idle'

const RUN_PAGE_SIZE = 25
const STRATEGY_PAGE_SIZE = 100

const runsState = ref<State>('loading')
const runsPage = ref<T539RunPage | null>(null)
const runsMessage = ref('')
const selectedRunId = ref('')

const coverageState = ref<State>('loading')
const coverageLedger = ref<T539CoverageLedger | null>(null)
const coverageMessage = ref('')

const strategiesState = ref<State>('loading')
const strategiesPage = ref<T539StrategyPage | null>(null)
const strategiesMessage = ref('')

const rankingsState = ref<State>('loading')
const rankingsPage = ref<T539RankingPage | null>(null)
const rankingsMessage = ref('')

const metricsState = ref<State>('loading')
const metrics = ref<T539Metrics | null>(null)
const metricsMessage = ref('')

const selectedStrategyId = ref('')
const selectedMetricsState = ref<SelectedMetricsState>('idle')
const selectedMetrics = ref<T539Metrics | null>(null)
const selectedMetricsMessage = ref('')

let mounted = false
let runsController: AbortController | undefined
let coverageController: AbortController | undefined
let strategiesController: AbortController | undefined
let rankingsController: AbortController | undefined
let metricsController: AbortController | undefined
let selectedMetricsController: AbortController | undefined
let runsGeneration = 0
let coverageGeneration = 0
let strategiesGeneration = 0
let rankingsGeneration = 0
let metricsGeneration = 0
let selectedMetricsGeneration = 0

const selectedRun = computed<T539Run | null>(
  () => runsPage.value?.items.find((run) => run.run_id === selectedRunId.value) ?? null,
)
const selectedStrategy = computed<T539Strategy | null>(
  () =>
    strategiesPage.value?.items.find((strategy) => strategy.strategy_id === selectedStrategyId.value) ??
    null,
)
const executedCount = computed<number | null>(() => coverageLedger.value?.executed.length ?? null)
const blockedCount = computed<number | null>(() => coverageLedger.value?.blocked.length ?? null)
const coverageComplete = computed<boolean | null>(() => coverageLedger.value?.coverage_complete ?? null)

async function loadRuns(): Promise<void> {
  runsController?.abort()
  const controller = new AbortController()
  runsController = controller
  const generation = ++runsGeneration
  runsState.value = 'loading'
  runsMessage.value = ''
  try {
    const page = await listT539Runs({ limit: RUN_PAGE_SIZE, offset: 0 }, controller.signal)
    if (!mounted || generation !== runsGeneration) return
    runsPage.value = page
    runsState.value = page.items.length ? 'ready' : 'empty'
    const runId = page.items.some((run) => run.run_id === selectedRunId.value)
      ? selectedRunId.value
      : (page.items[0]?.run_id ?? '')
    if (runId) await selectRun(runId)
  } catch (error: unknown) {
    if (!mounted || generation !== runsGeneration || isAbort(error)) return
    runsPage.value = null
    runsState.value = mapState(error)
    runsMessage.value = errorMessage(error)
  }
}

async function selectRun(runId: string): Promise<void> {
  if (!runId) return
  selectedRunId.value = runId
  selectedStrategyId.value = ''
  selectedMetrics.value = null
  selectedMetricsState.value = 'idle'
  selectedMetricsMessage.value = ''
  await Promise.all([
    loadCoverage(runId),
    loadStrategies(runId),
    loadRankings(runId),
    loadMetrics(runId),
  ])
}

async function loadCoverage(runId: string): Promise<void> {
  coverageController?.abort()
  const controller = new AbortController()
  coverageController = controller
  const generation = ++coverageGeneration
  coverageState.value = 'loading'
  coverageMessage.value = ''
  try {
    const ledger = await getT539Coverage(runId, controller.signal)
    if (!mounted || generation !== coverageGeneration) return
    coverageLedger.value = ledger
    coverageState.value = ledger.executed.length || ledger.blocked.length ? 'ready' : 'empty'
  } catch (error: unknown) {
    if (!mounted || generation !== coverageGeneration || isAbort(error)) return
    coverageLedger.value = null
    coverageState.value = mapState(error)
    coverageMessage.value = errorMessage(error)
  }
}

async function loadStrategies(runId: string): Promise<void> {
  strategiesController?.abort()
  const controller = new AbortController()
  strategiesController = controller
  const generation = ++strategiesGeneration
  strategiesState.value = 'loading'
  strategiesMessage.value = ''
  try {
    const page = await listT539Strategies(
      runId,
      { limit: STRATEGY_PAGE_SIZE, offset: 0 },
      controller.signal,
    )
    if (!mounted || generation !== strategiesGeneration) return
    strategiesPage.value = page
    strategiesState.value = page.items.length ? 'ready' : 'empty'
  } catch (error: unknown) {
    if (!mounted || generation !== strategiesGeneration || isAbort(error)) return
    strategiesPage.value = null
    strategiesState.value = mapState(error)
    strategiesMessage.value = errorMessage(error)
  }
}

async function loadRankings(runId: string): Promise<void> {
  rankingsController?.abort()
  const controller = new AbortController()
  rankingsController = controller
  const generation = ++rankingsGeneration
  rankingsState.value = 'loading'
  rankingsMessage.value = ''
  try {
    const page = await getT539Rankings(runId, controller.signal)
    if (!mounted || generation !== rankingsGeneration) return
    rankingsPage.value = page
    rankingsState.value = page.items.length ? 'ready' : 'empty'
  } catch (error: unknown) {
    if (!mounted || generation !== rankingsGeneration || isAbort(error)) return
    rankingsPage.value = null
    rankingsState.value = mapState(error)
    rankingsMessage.value = errorMessage(error)
  }
}

async function loadMetrics(runId: string): Promise<void> {
  metricsController?.abort()
  const controller = new AbortController()
  metricsController = controller
  const generation = ++metricsGeneration
  metricsState.value = 'loading'
  metricsMessage.value = ''
  try {
    const result = await getT539Metrics(runId, undefined, controller.signal)
    if (!mounted || generation !== metricsGeneration) return
    metrics.value = result
    metricsState.value = 'ready'
  } catch (error: unknown) {
    if (!mounted || generation !== metricsGeneration || isAbort(error)) return
    metrics.value = null
    metricsState.value = mapState(error)
    metricsMessage.value = errorMessage(error)
  }
}

async function selectStrategy(strategyId: string): Promise<void> {
  selectedStrategyId.value = strategyId
  selectedMetrics.value = null
  selectedMetricsController?.abort()
  const controller = new AbortController()
  selectedMetricsController = controller
  const generation = ++selectedMetricsGeneration
  selectedMetricsState.value = 'loading'
  selectedMetricsMessage.value = ''
  const runId = selectedRunId.value
  if (!runId) return
  try {
    const result = await getT539Metrics(runId, strategyId, controller.signal)
    if (!mounted || generation !== selectedMetricsGeneration || selectedStrategyId.value !== strategyId) {
      return
    }
    selectedMetrics.value = result
    selectedMetricsState.value = 'ready'
  } catch (error: unknown) {
    if (
      !mounted ||
      generation !== selectedMetricsGeneration ||
      isAbort(error) ||
      selectedStrategyId.value !== strategyId
    ) {
      return
    }
    selectedMetrics.value = null
    selectedMetricsState.value = mapState(error)
    selectedMetricsMessage.value = errorMessage(error)
  }
}

function retrySelectedMetrics(): void {
  if (selectedStrategyId.value) void selectStrategy(selectedStrategyId.value)
}

function displayLotteryType(value: string): string {
  return lotteryTypeDisplayLabel(value as LotteryType)
}

function formatRate(value: number): string {
  return `${(value * 100).toFixed(1)}%`
}

function formatCount(value: number): string {
  return value.toLocaleString()
}

function distributionText(items: Array<{ value: number; count: number }>): string {
  return items.map((item) => `${item.value}: ${item.count.toLocaleString()}`).join(' · ') || '—'
}

function tierCountsText(items: Array<{ prize_tier: string; count: number }>): string {
  const won = items.filter((item) => item.count > 0)
  return won.length
    ? won.map((item) => `${item.prize_tier}: ${item.count.toLocaleString()}`).join(' · ')
    : 'No wins'
}

function mapState(error: unknown): State {
  if (error instanceof T539HistoricalRequestError) {
    if (error.kind === 'NOT_CONFIGURED') return 'not-configured'
    if (error.kind === 'UNAVAILABLE') return 'unavailable'
    if (error.kind === 'MALFORMED_RESPONSE') return 'malformed'
  }
  return 'error'
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'T539 Strategy Analysis could not load.'
}

function isAbort(error: unknown): boolean {
  return (error instanceof DOMException || error instanceof Error) && error.name === 'AbortError'
}

onMounted(() => {
  mounted = true
  void loadRuns()
})

onBeforeUnmount(() => {
  mounted = false
  runsController?.abort()
  coverageController?.abort()
  strategiesController?.abort()
  rankingsController?.abort()
  metricsController?.abort()
  selectedMetricsController?.abort()
})
</script>

<template>
  <section class="workspace-page t539-analysis-page" aria-labelledby="t539-analysis-title">
    <header class="page-heading">
      <div>
        <p class="eyebrow">Wave 1 replay coverage · descriptive statistics</p>
        <h1 id="t539-analysis-title">T539 Strategy Analysis</h1>
        <p class="page-intro">
          This page projects the merged, read-only T539 Historical API. Executed strategies are
          replayed and ranked from stored evidence only; blocked or deferred identities stay
          visible with their exact reason and are never hidden or relabeled.
        </p>
      </div>
      <div class="scope-card">
        <span>Analysis scope</span>
        <strong>{{ executedCount === null ? 'Loading…' : `${executedCount} executed` }}</strong>
        <small v-if="executedCount !== null">
          {{ blockedCount }} blocked/deferred · {{ coverageComplete ? 'coverage complete' : 'coverage incomplete' }}
        </small>
      </div>
    </header>

    <div v-if="coverageComplete === false" class="notice-row" data-testid="t539-coverage-incomplete-notice">
      Coverage is incomplete for this run: not every strategy identity has an executed replay yet.
      Blocked and deferred identities below are excluded from the ranking, not hidden.
    </div>

    <p v-if="runsState === 'loading'" class="state-panel">Loading T539 analysis runs…</p>
    <div v-else-if="runsState === 'not-configured'" class="state-panel state-panel--warning">
      <p>T539 Historical Results storage is not configured for this local runtime.</p>
    </div>
    <div
      v-else-if="runsState === 'unavailable' || runsState === 'malformed' || runsState === 'error'"
      class="state-panel state-panel--error"
    >
      <p>{{ runsMessage }}</p>
      <button class="button button--quiet" type="button" data-testid="t539-retry-runs" @click="loadRuns">
        Retry
      </button>
    </div>
    <p v-else-if="runsState === 'empty'" class="state-panel">No completed T539 analysis run is available.</p>

    <template v-else-if="runsPage && runsPage.items.length">
      <article class="panel">
        <div class="panel__heading">
          <div>
            <p class="step-label">Frozen source</p>
            <h2>Analysis run</h2>
          </div>
          <button class="button button--quiet" type="button" data-testid="t539-refresh-runs" @click="loadRuns">
            Refresh
          </button>
        </div>
        <label class="filter-field">
          <span>Historical run</span>
          <select
            v-model="selectedRunId"
            data-testid="t539-run-select"
            @change="selectRun(selectedRunId)"
          >
            <option v-for="run in runsPage.items" :key="run.run_id" :value="run.run_id">
              {{ run.run_id }} · {{ displayLotteryType(run.lottery_type) }} · {{ run.status }}
            </option>
          </select>
        </label>
        <p v-if="selectedRun" class="panel__note">
          Schema {{ selectedRun.schema_version }} · as of {{ selectedRun.as_of_date }} · source
          <code>{{ selectedRun.source_sha256 }}</code> · adapter
          <code>{{ selectedRun.adapter_source_commit }}</code>
        </p>
      </article>

      <section aria-labelledby="t539-ranking-title" class="panel">
        <div class="panel__heading">
          <div>
            <p class="step-label">Historical winning performance</p>
            <h2 id="t539-ranking-title">Official-prize ranking</h2>
          </div>
          <button
            class="button button--quiet"
            type="button"
            data-testid="t539-refresh-rankings"
            @click="selectedRunId && loadRankings(selectedRunId)"
          >
            Refresh
          </button>
        </div>
        <p class="panel__note">
          {{
            rankingsPage?.disclaimer ??
            'Historical winning rank describes past replay only and does not guarantee future winning.'
          }}
        </p>
        <p v-if="rankingsState === 'loading'" class="state-panel">Loading the official-prize ranking…</p>
        <div v-else-if="rankingsState === 'not-configured'" class="state-panel state-panel--warning">
          <p>The T539 ranking projection is not configured for this local runtime.</p>
        </div>
        <div
          v-else-if="rankingsState === 'unavailable' || rankingsState === 'malformed' || rankingsState === 'error'"
          class="state-panel state-panel--error"
        >
          <p>{{ rankingsMessage }}</p>
          <button
            class="button button--quiet"
            type="button"
            data-testid="t539-retry-rankings"
            @click="selectedRunId && loadRankings(selectedRunId)"
          >
            Retry
          </button>
        </div>
        <p v-else-if="rankingsState === 'empty'" class="state-panel">No ranked strategy is available for this run.</p>
        <div v-else-if="rankingsPage" class="table-wrap">
          <table>
            <caption>Executed strategies ranked in server response order</caption>
            <thead>
              <tr>
                <th>Rank</th>
                <th>Strategy</th>
                <th>Tickets</th>
                <th>Eligible targets</th>
                <th>Winning targets</th>
                <th>Winning-target rate</th>
                <th>Ticket win rate</th>
                <th>Highest tier</th>
                <th>Prize tier distribution</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in rankingsPage.items" :key="row.strategy_id">
                <td><strong>{{ row.rank }}</strong></td>
                <td><strong>{{ row.strategy_id }}</strong><small>{{ row.strategy_version }}</small></td>
                <td>{{ formatCount(row.native_ticket_count) }}</td>
                <td>{{ formatCount(row.eligible_target_count) }}</td>
                <td>{{ formatCount(row.winning_target_count) }}</td>
                <td>{{ formatRate(row.winning_target_rate) }}</td>
                <td>{{ formatRate(row.ticket_winning_rate) }}</td>
                <td>{{ row.highest_prize_tier_achieved ?? 'No wins' }}</td>
                <td><small>{{ tierCountsText(row.prize_tier_counts) }}</small></td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="panel" aria-labelledby="t539-run-metrics-title">
        <div class="panel__heading">
          <div>
            <p class="step-label">Run aggregate</p>
            <h2 id="t539-run-metrics-title">Descriptive coverage</h2>
          </div>
          <span class="table-note">All executed strategies combined · no predictive interpretation</span>
        </div>
        <p v-if="metricsState === 'loading'" class="state-panel">Loading aggregate T539 statistics…</p>
        <div v-else-if="metricsState === 'not-configured'" class="state-panel state-panel--warning">
          <p>T539 run metrics are not configured for this local runtime.</p>
        </div>
        <div
          v-else-if="metricsState === 'unavailable' || metricsState === 'malformed' || metricsState === 'error'"
          class="state-panel state-panel--error"
        >
          <p>{{ metricsMessage }}</p>
          <button
            class="button button--quiet"
            type="button"
            data-testid="t539-retry-metrics"
            @click="selectedRunId && loadMetrics(selectedRunId)"
          >
            Retry
          </button>
        </div>
        <p v-else-if="metricsState === 'empty'" class="state-panel">No run metrics are available yet.</p>
        <template v-else-if="metrics">
          <div class="metric-grid">
            <div><span>Targets</span><strong>{{ formatCount(metrics.target_count) }}</strong></div>
            <div><span>Tickets</span><strong>{{ formatCount(metrics.ticket_count) }}</strong></div>
            <div><span>Winning targets</span><strong>{{ formatCount(metrics.winning_target_count) }}</strong></div>
            <div><span>Winning tickets</span><strong>{{ formatCount(metrics.winning_ticket_count) }}</strong></div>
            <div><span>First target draw</span><strong>{{ metrics.first_target_draw_date ?? '—' }}</strong></div>
            <div><span>Last target draw</span><strong>{{ metrics.last_target_draw_date ?? '—' }}</strong></div>
          </div>
          <p class="distribution-line">Hit distribution: {{ distributionText(metrics.hit_distribution) }}</p>
          <p class="distribution-line">Prize tiers: {{ tierCountsText(metrics.prize_tier_counts) }}</p>
        </template>
      </section>

      <section class="section-heading">
        <div>
          <p class="step-label">Registry snapshot</p>
          <h2>Executed strategy replay coverage</h2>
        </div>
        <span class="table-note">{{ strategiesPage?.total_count ?? 0 }} executed identities</span>
      </section>
      <p v-if="strategiesState === 'loading'" class="state-panel">Loading the strategy coverage ledger…</p>
      <div v-else-if="strategiesState === 'not-configured'" class="state-panel state-panel--warning">
        <p>T539 strategy coverage is not configured for this local runtime.</p>
      </div>
      <div
        v-else-if="strategiesState === 'unavailable' || strategiesState === 'malformed' || strategiesState === 'error'"
        class="state-panel state-panel--error"
      >
        <p>{{ strategiesMessage }}</p>
        <button
          class="button button--quiet"
          type="button"
          data-testid="t539-retry-strategies"
          @click="selectedRunId && loadStrategies(selectedRunId)"
        >
          Retry
        </button>
      </div>
      <p v-else-if="strategiesState === 'empty'" class="state-panel">No executed T539 strategy is available yet.</p>
      <div v-else-if="strategiesPage" class="table-wrap">
        <table>
          <caption>Executed T539 strategy identities and their replay coverage</caption>
          <thead>
            <tr>
              <th>Identity</th>
              <th>Contracts</th>
              <th>Target draws</th>
              <th>Tickets</th>
              <th>Hit distribution</th>
              <th>Status</th>
              <th>Analysis</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="strategy in strategiesPage.items"
              :key="strategy.strategy_id"
              :data-testid="`t539-strategy-row-${strategy.strategy_id}`"
            >
              <td><strong>{{ strategy.strategy_id }}</strong><small>{{ strategy.strategy_version }}</small></td>
              <td>
                {{ formatCount(strategy.native_ticket_count) }} tickets
                <small>min history {{ formatCount(strategy.min_history) }}</small>
              </td>
              <td>
                {{ formatCount(strategy.expected_target_draw_count) }} expected
                <small>
                  {{ formatCount(strategy.processed_target_draw_count) }} processed ·
                  {{ formatCount(strategy.successful_target_draw_count) }} success ·
                  {{ formatCount(strategy.failed_target_draw_count) }} failed
                </small>
              </td>
              <td>
                {{ formatCount(strategy.ticket_count) }}
                <small>{{ formatCount(strategy.winning_ticket_count) }} winning</small>
              </td>
              <td><small>{{ distributionText(strategy.hit_distribution) }}</small></td>
              <td><span class="status-pill status-pill--complete">{{ strategy.status }}</span></td>
              <td>
                <button
                  class="button button--quiet"
                  type="button"
                  :data-testid="`t539-select-strategy-${strategy.strategy_id}`"
                  @click="selectStrategy(strategy.strategy_id)"
                >
                  Analyze
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-if="selectedStrategy" class="panel" aria-live="polite">
        <div class="panel__heading">
          <div>
            <p class="step-label">Selected identity</p>
            <h2>{{ selectedStrategy.strategy_id }}</h2>
          </div>
          <span class="status-pill status-pill--complete">{{ selectedStrategy.status }}</span>
        </div>
        <p class="panel__note">
          {{ selectedStrategy.strategy_version }} · min history {{ formatCount(selectedStrategy.min_history) }}.
          Metrics describe stored replay rows only.
        </p>
        <p v-if="selectedMetricsState === 'loading'" class="state-panel">Loading identity metrics…</p>
        <div
          v-else-if="
            selectedMetricsState === 'unavailable' ||
            selectedMetricsState === 'malformed' ||
            selectedMetricsState === 'error'
          "
          class="state-panel state-panel--error"
        >
          <p>{{ selectedMetricsMessage }}</p>
          <button
            class="button button--quiet"
            type="button"
            data-testid="t539-retry-selected-metrics"
            @click="retrySelectedMetrics"
          >
            Retry
          </button>
        </div>
        <div v-else-if="selectedMetricsState === 'not-configured'" class="state-panel state-panel--warning">
          <p>Identity metrics are not configured for this local runtime.</p>
        </div>
        <template v-else-if="selectedMetrics">
          <div class="metric-grid">
            <div><span>Targets</span><strong>{{ formatCount(selectedMetrics.target_count) }}</strong></div>
            <div><span>Tickets</span><strong>{{ formatCount(selectedMetrics.ticket_count) }}</strong></div>
            <div><span>Winning targets</span><strong>{{ formatCount(selectedMetrics.winning_target_count) }}</strong></div>
            <div><span>Winning tickets</span><strong>{{ formatCount(selectedMetrics.winning_ticket_count) }}</strong></div>
            <div><span>First target draw</span><strong>{{ selectedMetrics.first_target_draw_date ?? '—' }}</strong></div>
            <div><span>Last target draw</span><strong>{{ selectedMetrics.last_target_draw_date ?? '—' }}</strong></div>
          </div>
          <p class="distribution-line">Hit distribution: {{ distributionText(selectedMetrics.hit_distribution) }}</p>
          <p class="distribution-line">Prize tiers: {{ tierCountsText(selectedMetrics.prize_tier_counts) }}</p>
        </template>
      </div>

      <section class="section-heading">
        <div>
          <p class="step-label">Coverage ledger</p>
          <h2>Executed and blocked/deferred identities</h2>
        </div>
        <button
          class="button button--quiet"
          type="button"
          data-testid="t539-refresh-coverage"
          @click="selectedRunId && loadCoverage(selectedRunId)"
        >
          Refresh
        </button>
      </section>
      <p v-if="coverageState === 'loading'" class="state-panel">Loading the coverage ledger…</p>
      <div v-else-if="coverageState === 'not-configured'" class="state-panel state-panel--warning">
        <p>The T539 coverage ledger is not configured for this local runtime.</p>
      </div>
      <div
        v-else-if="coverageState === 'unavailable' || coverageState === 'malformed' || coverageState === 'error'"
        class="state-panel state-panel--error"
      >
        <p>{{ coverageMessage }}</p>
        <button
          class="button button--quiet"
          type="button"
          data-testid="t539-retry-coverage"
          @click="selectedRunId && loadCoverage(selectedRunId)"
        >
          Retry
        </button>
      </div>
      <p v-else-if="coverageState === 'empty'" class="state-panel">The coverage ledger has no entries yet.</p>
      <template v-else-if="coverageLedger">
        <div class="table-wrap">
          <table>
            <caption>Executed identities (ranked and included in the strategy coverage table above)</caption>
            <thead>
              <tr>
                <th>Strategy</th>
                <th>Contracts</th>
                <th>Selection reason</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="entry in coverageLedger.executed" :key="entry.strategy_id">
                <td><strong>{{ entry.strategy_id }}</strong><small>{{ entry.strategy_version }}</small></td>
                <td>
                  {{ formatCount(entry.native_ticket_count) }} tickets
                  <small>min history {{ formatCount(entry.min_history) }}</small>
                </td>
                <td>{{ entry.selection_reason }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="table-wrap">
          <table>
            <caption>Blocked / deferred identities (excluded from the ranking, never hidden)</caption>
            <thead>
              <tr>
                <th>Strategy</th>
                <th>Reason code</th>
                <th>Reason</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="entry in coverageLedger.blocked" :key="entry.strategy_id">
                <td><strong>{{ entry.strategy_id }}</strong></td>
                <td><code>{{ entry.reason_code }}</code></td>
                <td>{{ entry.reason }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </template>
    </template>
  </section>
</template>
