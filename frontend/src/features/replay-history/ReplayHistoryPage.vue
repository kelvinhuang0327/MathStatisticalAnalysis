<script setup lang="ts">
import { onBeforeUnmount, ref } from 'vue'

import { listHistoricalImportRuns, type HistoricalImportRunPage } from '../../api/historicalImports'
import {
  listHistoricalRunStrategies,
  listHistoricalRunReplayPortfolios,
  HistoricalResultsRequestError,
  type HistoricalReplayPageResponse,
  type HistoricalStrategySummaryListResponse,
  type HistoricalStrategySummaryView,
  type TicketCountFilter,
} from '../../api/historicalResults'
import {
  getOptimalReplayPortfolioRankings,
  isValidScoringArtifactSha256,
  ReplayPortfolioRankingsRequestError,
  type ReplayPortfolioRankingResponse,
} from '../../api/replayPortfolioRankings'
import {
  getReplayScoringOverallAggregate,
  getReplayScoringRun,
  listReplayScoringPredictions,
  listReplayScoringStrategyAggregates,
  ReplayScoringProjectionsRequestError,
  type ReplayOverallAggregateResponse,
  type ReplayScoredPredictionView,
  type ReplayScoringPredictionsQuery,
  type ReplayStrategyAggregateView,
} from '../../api/replayScoringProjections'
import type { LotteryType } from '../../api/strategies'
import { lotteryTypeDisplayLabel } from '../../utils/lotteryDisplayLabel'
import LotteryNumberBall from '../../components/LotteryNumberBall.vue'

function lotteryLabel(value: string): string {
  return lotteryTypeDisplayLabel(value as LotteryType)
}

type Tab = 'overview' | 'optimal'
type LoadState = 'idle' | 'loading' | 'ready' | 'empty' | 'error'
const TICKET_COUNTS: readonly TicketCountFilter[] = [10, 15, 20]

const activeTab = ref<Tab>('overview')

// --- Overview replay (req #4): all strategies for one run + ticket count -----

const runsState = ref<LoadState>('loading')
const runsError = ref('')
const runs = ref<HistoricalImportRunPage['items']>([])
const selectedRunId = ref('')
const selectedTicketCount = ref<TicketCountFilter>(10)

const strategiesState = ref<LoadState>('idle')
const strategiesError = ref('')
const strategies = ref<HistoricalStrategySummaryView[]>([])
const selectedStrategyId = ref('')

const replayState = ref<LoadState>('idle')
const replayError = ref('')
const replayPage = ref<HistoricalReplayPageResponse | null>(null)
const m4plusOnly = ref(false)
const replayOffset = ref(0)
const REPLAY_PAGE_SIZE = 20

let runsController: AbortController | undefined
let strategiesController: AbortController | undefined
let replayController: AbortController | undefined

async function loadRuns(): Promise<void> {
  runsController?.abort()
  const controller = new AbortController()
  runsController = controller
  runsState.value = 'loading'
  runsError.value = ''
  try {
    const page = await listHistoricalImportRuns(controller.signal)
    if (controller.signal.aborted) return
    runs.value = page.items
    runsState.value = page.items.length ? 'ready' : 'empty'
  } catch (error) {
    if (controller.signal.aborted) return
    runsError.value = error instanceof Error ? error.message : 'Unable to load runs'
    runsState.value = 'error'
  }
}

function hitRate(summary: HistoricalStrategySummaryView): string {
  if (summary.evaluated_draws === 0) return '—'
  return `${((summary.m4plus_hit_count / summary.evaluated_draws) * 100).toFixed(1)}%`
}

async function loadStrategies(): Promise<void> {
  if (!selectedRunId.value) return
  strategiesController?.abort()
  const controller = new AbortController()
  strategiesController = controller
  strategiesState.value = 'loading'
  strategiesError.value = ''
  selectedStrategyId.value = ''
  replayPage.value = null
  replayState.value = 'idle'
  try {
    const response: HistoricalStrategySummaryListResponse = await listHistoricalRunStrategies(
      selectedRunId.value,
      selectedTicketCount.value,
      controller.signal,
    )
    if (controller.signal.aborted) return
    strategies.value = response.items
    strategiesState.value = response.items.length ? 'ready' : 'empty'
  } catch (error) {
    if (controller.signal.aborted) return
    strategiesError.value =
      error instanceof HistoricalResultsRequestError
        ? error.message
        : error instanceof Error
          ? error.message
          : 'Unable to load strategies'
    strategiesState.value = 'error'
  }
}

async function loadReplay(): Promise<void> {
  if (!selectedRunId.value || !selectedStrategyId.value) return
  replayController?.abort()
  const controller = new AbortController()
  replayController = controller
  replayState.value = 'loading'
  replayError.value = ''
  try {
    const page = await listHistoricalRunReplayPortfolios(
      selectedRunId.value,
      {
        strategyId: selectedStrategyId.value,
        ticketCount: selectedTicketCount.value,
        m4plusOnly: m4plusOnly.value,
        limit: REPLAY_PAGE_SIZE,
        offset: replayOffset.value,
      },
      controller.signal,
    )
    if (controller.signal.aborted) return
    replayPage.value = page
    replayState.value = page.items.length ? 'ready' : 'empty'
  } catch (error) {
    if (controller.signal.aborted) return
    replayError.value = error instanceof Error ? error.message : 'Unable to load replay portfolios'
    replayState.value = 'error'
  }
}

function chooseStrategy(strategyId: string): void {
  selectedStrategyId.value = strategyId
  replayOffset.value = 0
  void loadReplay()
}

function nextReplayPage(): void {
  if (!replayPage.value) return
  if (replayOffset.value + REPLAY_PAGE_SIZE >= replayPage.value.total_count) return
  replayOffset.value += REPLAY_PAGE_SIZE
  void loadReplay()
}

function previousReplayPage(): void {
  replayOffset.value = Math.max(0, replayOffset.value - REPLAY_PAGE_SIZE)
  void loadReplay()
}

void loadRuns()

// --- Optimal replay (req #3): rank-1 portfolios for one scoring artifact -----

const scoringArtifactSha256 = ref('')
const topK = ref(10)
const optimalState = ref<LoadState>('idle')
const optimalError = ref('')
const optimalResult = ref<ReplayPortfolioRankingResponse | null>(null)
let optimalController: AbortController | undefined

const shaInputInvalid = ref(false)
const scoringDetailVisible = ref(false)
const scoringDetailState = ref<LoadState>('idle')
const scoringDetailError = ref('')
const scoringDetailRun = ref<Awaited<ReturnType<typeof getReplayScoringRun>> | null>(null)
const scoringStrategyAggregates = ref<ReplayStrategyAggregateView[]>([])
const scoringOverallAggregate = ref<ReplayOverallAggregateResponse | null>(null)
const scoringPredictions = ref<ReplayScoredPredictionView[]>([])
const scoringPredictionsState = ref<LoadState>('idle')
const scoringPredictionsError = ref('')
const predictionFilters = ref({ targetDraw: '', strategyId: '', status: '', tier: '' })
let scoringDetailController: AbortController | undefined
let scoringPredictionsController: AbortController | undefined

const aggregateCountFields = [
  { key: 'source_snapshot_count', label: 'Source snapshots' },
  { key: 'scored_count', label: 'Scored' },
  { key: 'history_closed_count', label: 'History closed' },
  { key: 'prediction_closed_count', label: 'Prediction closed' },
  { key: 'target_outcome_not_found_count', label: 'Outcome not found' },
  { key: 'target_identity_mismatch_count', label: 'Identity mismatch' },
] as const

const prizeCountFields = [
  { key: 'first_prize_count', label: '1st prize' },
  { key: 'second_prize_count', label: '2nd prize' },
  { key: 'third_prize_count', label: '3rd prize' },
  { key: 'fourth_prize_count', label: '4th prize' },
  { key: 'fifth_prize_count', label: '5th prize' },
  { key: 'sixth_prize_count', label: '6th prize' },
  { key: 'seventh_prize_count', label: '7th prize' },
  { key: 'general_prize_count', label: 'General prize' },
  { key: 'no_prize_count', label: 'No prize' },
] as const

function clearScoringDetail(): void {
  scoringDetailController?.abort()
  scoringPredictionsController?.abort()
  scoringDetailVisible.value = false
  scoringDetailState.value = 'idle'
  scoringDetailError.value = ''
  scoringDetailRun.value = null
  scoringStrategyAggregates.value = []
  scoringOverallAggregate.value = null
  scoringPredictions.value = []
  scoringPredictionsState.value = 'idle'
  scoringPredictionsError.value = ''
}

function resetOptimalSelection(): void {
  optimalController?.abort()
  optimalResult.value = null
  optimalState.value = 'idle'
  optimalError.value = ''
  shaInputInvalid.value = false
  clearScoringDetail()
}

function scoringErrorMessage(error: unknown): string {
  if (error instanceof ReplayScoringProjectionsRequestError) {
    if (error.status === 0) return error.message
    const statusLabel =
      error.status === 404
        ? 'Scoring artifact not found (404)'
        : error.status === 422
          ? 'Scoring detail request was rejected (422)'
          : error.status === 503
            ? 'Scoring service unavailable (503)'
            : `Scoring detail request failed (${error.status})`
    return `${statusLabel}: ${error.message}`
  }
  return error instanceof Error ? error.message : 'Unable to load scoring artifact detail'
}

function selectedPredictionFilters(): ReplayScoringPredictionsQuery {
  const filters = predictionFilters.value
  return {
    ...(filters.targetDraw ? { target_draw: filters.targetDraw.trim() } : {}),
    ...(filters.strategyId ? { strategy_id: filters.strategyId.trim() } : {}),
    ...(filters.status ? { status: filters.status.trim() } : {}),
    ...(filters.tier ? { tier: filters.tier.trim() } : {}),
  }
}

function isCurrentScoringArtifact(hash: string, signal: AbortSignal): boolean {
  return (
    !signal.aborted &&
    optimalResult.value?.source_scoring_artifact_payload_sha256 === hash
  )
}

async function loadScoringArtifactDetail(): Promise<void> {
  const hash = optimalResult.value?.source_scoring_artifact_payload_sha256 ?? ''
  scoringDetailVisible.value = true
  if (!isValidScoringArtifactSha256(hash)) {
    scoringDetailState.value = 'error'
    scoringDetailError.value =
      'The ranking response does not contain a valid source scoring artifact SHA-256.'
    scoringDetailRun.value = null
    scoringStrategyAggregates.value = []
    scoringOverallAggregate.value = null
    scoringPredictions.value = []
    scoringPredictionsState.value = 'idle'
    return
  }

  scoringDetailController?.abort()
  scoringPredictionsController?.abort()
  const controller = new AbortController()
  scoringDetailController = controller
  scoringDetailState.value = 'loading'
  scoringDetailError.value = ''
  scoringPredictionsState.value = 'loading'
  scoringPredictionsError.value = ''
  scoringDetailRun.value = null
  scoringStrategyAggregates.value = []
  scoringOverallAggregate.value = null
  scoringPredictions.value = []
  try {
    const [run, predictions, strategyAggregates, overallAggregate] = await Promise.all([
      getReplayScoringRun(hash, controller.signal),
      listReplayScoringPredictions(hash, selectedPredictionFilters(), controller.signal),
      listReplayScoringStrategyAggregates(hash, controller.signal),
      getReplayScoringOverallAggregate(hash, controller.signal),
    ])
    if (!isCurrentScoringArtifact(hash, controller.signal)) return
    if (run.scoring_artifact_payload_sha256 !== hash) {
      throw new ReplayScoringProjectionsRequestError(
        'The returned scoring artifact identity did not match the ranking source.',
        502,
      )
    }
    scoringDetailRun.value = run
    scoringPredictions.value = predictions
    scoringStrategyAggregates.value = strategyAggregates
    scoringOverallAggregate.value = overallAggregate
    scoringDetailState.value = 'ready'
    scoringPredictionsState.value = predictions.length ? 'ready' : 'empty'
  } catch (error) {
    if (!isCurrentScoringArtifact(hash, controller.signal)) return
    scoringDetailError.value = scoringErrorMessage(error)
    scoringDetailState.value = 'error'
    scoringPredictionsState.value = 'error'
  }
}

async function loadFilteredScoringPredictions(): Promise<void> {
  const hash = optimalResult.value?.source_scoring_artifact_payload_sha256 ?? ''
  if (!isValidScoringArtifactSha256(hash)) {
    scoringPredictionsState.value = 'error'
    scoringPredictionsError.value =
      'The ranking response does not contain a valid source scoring artifact SHA-256.'
    return
  }
  scoringPredictionsController?.abort()
  const controller = new AbortController()
  scoringPredictionsController = controller
  scoringPredictionsState.value = 'loading'
  scoringPredictionsError.value = ''
  scoringPredictions.value = []
  try {
    const predictions = await listReplayScoringPredictions(
      hash,
      selectedPredictionFilters(),
      controller.signal,
    )
    if (!isCurrentScoringArtifact(hash, controller.signal)) return
    scoringPredictions.value = predictions
    scoringPredictionsState.value = predictions.length ? 'ready' : 'empty'
  } catch (error) {
    if (!isCurrentScoringArtifact(hash, controller.signal)) return
    scoringPredictionsError.value = scoringErrorMessage(error)
    scoringPredictionsState.value = 'error'
  }
}

async function loadOptimalRankings(): Promise<void> {
  if (!isValidScoringArtifactSha256(scoringArtifactSha256.value)) {
    shaInputInvalid.value = true
    return
  }
  clearScoringDetail()
  shaInputInvalid.value = false
  optimalController?.abort()
  const controller = new AbortController()
  optimalController = controller
  optimalState.value = 'loading'
  optimalError.value = ''
  try {
    const result = await getOptimalReplayPortfolioRankings(
      scoringArtifactSha256.value,
      topK.value,
      controller.signal,
    )
    if (controller.signal.aborted) return
    optimalResult.value = result
    optimalState.value = result.groups.some((group) => group.candidates.length) ? 'ready' : 'empty'
  } catch (error) {
    if (controller.signal.aborted) return
    optimalError.value =
      error instanceof ReplayPortfolioRankingsRequestError
        ? error.message
        : error instanceof Error
          ? error.message
          : 'Unable to load optimal replay rankings'
    optimalState.value = 'error'
  }
}

onBeforeUnmount(() => {
  runsController?.abort()
  strategiesController?.abort()
  replayController?.abort()
  optimalController?.abort()
  scoringDetailController?.abort()
  scoringPredictionsController?.abort()
})

function nullableText(value: string | null | undefined): string {
  return value ?? '—'
}

function predictedNumbers(value: number[] | null | undefined): string {
  return value?.join(', ') ?? '—'
}
</script>

<template>
  <section class="workspace-page" aria-labelledby="replay-history-title">
    <header class="page-heading">
      <div>
        <p class="eyebrow">Descriptive research only</p>
        <h1 id="replay-history-title">Replay History</h1>
        <p class="page-intro">
          Historical success rates, rankings, and random-baseline differences are descriptive
          research only — not a prediction, recommendation, go-live decision, or winning
          guarantee.
        </p>
      </div>
    </header>

    <nav class="tab-list" aria-label="Replay history sections">
      <button
        class="button"
        type="button"
        :aria-pressed="activeTab === 'overview'"
        @click="activeTab = 'overview'"
      >
        Overview Replay
      </button>
      <button
        class="button"
        type="button"
        :aria-pressed="activeTab === 'optimal'"
        @click="activeTab = 'optimal'"
      >
        Optimal Replay
      </button>
    </nav>

    <section v-if="activeTab === 'overview'" aria-labelledby="overview-replay-title">
      <h2 id="overview-replay-title">Overview replay</h2>

      <form class="panel filter-panel" @submit.prevent="loadStrategies">
        <div class="filter-grid">
          <label>
            <span>Run</span>
            <select v-model="selectedRunId" name="run_id" :disabled="runsState !== 'ready'">
              <option value="">Select a completed run</option>
              <option v-for="run in runs" :key="run.run_id" :value="run.run_id">
                {{ run.run_id }} · {{ lotteryLabel(run.lottery_type) }} · {{ run.completed_at }}
              </option>
            </select>
          </label>
          <label>
            <span>Ticket count</span>
            <select v-model.number="selectedTicketCount" name="ticket_count">
              <option v-for="count in TICKET_COUNTS" :key="count" :value="count">{{ count }}</option>
            </select>
          </label>
        </div>
        <div class="filter-actions">
          <button class="button button--primary" type="submit" :disabled="!selectedRunId">
            Load strategies
          </button>
        </div>
      </form>

      <p v-if="runsState === 'loading'" class="state-panel">Loading runs…</p>
      <p v-else-if="runsState === 'empty'" class="state-panel">No completed runs are available.</p>
      <p v-else-if="runsState === 'error'" class="state-panel state-panel--error">{{ runsError }}</p>

      <p v-if="strategiesState === 'loading'" class="state-panel">Loading strategies…</p>
      <p v-else-if="strategiesState === 'empty'" class="state-panel">
        No strategies match this run and ticket count.
      </p>
      <p v-else-if="strategiesState === 'error'" class="state-panel state-panel--error">
        {{ strategiesError }}
      </p>

      <div v-if="strategiesState === 'ready'" class="table-wrap">
        <table>
          <caption>All strategies for this run and ticket count</caption>
          <thead>
            <tr>
              <th scope="col">Strategy</th>
              <th scope="col">Governance</th>
              <th scope="col">Evaluated draws</th>
              <th scope="col">Complete portfolios</th>
              <th scope="col">M4+ hit rate</th>
              <th scope="col"></th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="summary in strategies"
              :key="summary.strategy_snapshot_id"
              :data-testid="`strategy-row-${summary.strategy_id}`"
              :aria-current="selectedStrategyId === summary.strategy_id ? 'true' : undefined"
            >
              <td>{{ summary.effective_strategy_id }}</td>
              <td>{{ summary.governance_status }}</td>
              <td>{{ summary.evaluated_draws }}</td>
              <td>{{ summary.complete_portfolios }}</td>
              <td>{{ hitRate(summary) }} ({{ summary.m4plus_hit_count }}/{{ summary.evaluated_draws }})</td>
              <td>
                <button
                  class="button button--quiet"
                  type="button"
                  @click="chooseStrategy(summary.strategy_id)"
                >
                  View replay
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <p v-if="replayState === 'loading'" class="state-panel">Loading replay portfolios…</p>
      <p v-else-if="replayState === 'empty'" class="state-panel">
        No replay portfolios match this selection.
      </p>
      <p v-else-if="replayState === 'error'" class="state-panel state-panel--error">
        {{ replayError }}
      </p>

      <section v-if="replayPage" aria-labelledby="replay-portfolios-title">
        <h3 id="replay-portfolios-title">Replay portfolios — {{ replayPage.strategy_id }}</h3>
        <label class="confirmation">
          <input v-model="m4plusOnly" type="checkbox" name="m4plus_only" @change="chooseStrategy(selectedStrategyId)" />
          <span>M4+ only</span>
        </label>
        <div class="table-wrap">
          <table>
            <caption>Per-draw replay portfolios (descriptive; no prediction or recommendation)</caption>
            <thead>
              <tr>
                <th scope="col">Target draw</th>
                <th scope="col">Cutoff draw</th>
                <th scope="col">M4+</th>
                <th scope="col">Tickets</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="portfolio in replayPage.items" :key="portfolio.portfolio_id">
                <td>{{ portfolio.target_draw.draw_number }} · {{ portfolio.target_draw.draw_date }}</td>
                <td>{{ portfolio.cutoff_draw.draw_number }} · {{ portfolio.cutoff_draw.draw_date }}</td>
                <td>{{ portfolio.m4plus ? 'YES' : 'NO' }}</td>
                <td>
                  <details>
                    <summary>{{ portfolio.tickets.length }} tickets</summary>
                    <ul class="ticket-list">
                      <li v-for="ticket in portfolio.tickets" :key="ticket.ticket_sha256">
                        <span class="number-chips">
                          <LotteryNumberBall
                            v-for="num in ticket.main_numbers"
                            :key="num"
                            :value="num"
                            variant="main"
                            size="sm"
                          />
                          <LotteryNumberBall
                            v-for="snum in ticket.special_numbers"
                            :key="snum"
                            :value="snum"
                            variant="special"
                            size="sm"
                          />
                        </span>
                        — {{ ticket.main_hit_count }} hit(s){{ ticket.special_hit ? ' + special' : '' }}
                      </li>
                    </ul>
                  </details>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="filter-actions">
          <button class="button" type="button" :disabled="replayOffset === 0" @click="previousReplayPage">
            Previous
          </button>
          <button
            class="button"
            type="button"
            :disabled="replayOffset + REPLAY_PAGE_SIZE >= replayPage.total_count"
            @click="nextReplayPage"
          >
            Next
          </button>
          <span>{{ replayPage.total_count }} total</span>
        </div>
      </section>
    </section>

    <section v-else aria-labelledby="optimal-replay-title">
      <h2 id="optimal-replay-title">Optimal replay</h2>
      <p class="page-intro">
        Ranks 1–5-strategy portfolios drawn from one already-validated Replay-scoring artifact.
        "Optimal" means rank 1 under a frozen descriptive policy only — this carries no payout,
        probability, EV, ROI, recommendation, or future-performance claim.
      </p>

      <form class="panel filter-panel" @submit.prevent="loadOptimalRankings">
        <div class="filter-grid">
          <label>
            <span>Scoring artifact SHA-256</span>
            <input
              v-model.trim="scoringArtifactSha256"
              name="scoring_artifact_sha256"
              placeholder="64 hex characters"
              autocomplete="off"
              @input="resetOptimalSelection"
            />
          </label>
          <label>
            <span>Top K</span>
            <input
              v-model.number="topK"
              type="number"
              name="top_k"
              min="1"
              max="50"
              @input="resetOptimalSelection"
            />
          </label>
        </div>
        <p v-if="shaInputInvalid" class="state-panel state-panel--error">
          Enter an exact lowercase 64-character SHA-256.
        </p>
        <div class="filter-actions">
          <button class="button button--primary" type="submit">Load rankings</button>
        </div>
      </form>

      <p v-if="optimalState === 'loading'" class="state-panel">Loading rankings…</p>
      <p v-else-if="optimalState === 'empty'" class="state-panel">No candidates were found.</p>
      <p v-else-if="optimalState === 'error'" class="state-panel state-panel--error">
        {{ optimalError }}
      </p>

      <template v-if="optimalResult && optimalState === 'ready'">
        <dl class="source-facts">
          <div>
            <dt>Source scoring artifact</dt>
            <dd><code>{{ optimalResult.source_scoring_artifact_payload_sha256 }}</code></dd>
          </div>
          <div><dt>Lottery</dt><dd>{{ lotteryLabel(optimalResult.lottery_type) }}</dd></div>
          <div><dt>Dataset</dt><dd>{{ optimalResult.dataset_id }} · {{ optimalResult.dataset_version }}</dd></div>
          <div><dt>Ranking policy</dt><dd>{{ optimalResult.ranking_policy_id }}</dd></div>
          <div><dt>Strategy count</dt><dd>{{ optimalResult.strategy_count }}</dd></div>
        </dl>
        <div class="filter-actions">
          <button class="button button--primary" type="button" @click="loadScoringArtifactDetail">
            Scoring Artifact Detail
          </button>
        </div>

        <section v-if="scoringDetailVisible" aria-labelledby="scoring-artifact-detail-title">
          <h3 id="scoring-artifact-detail-title">Scoring Artifact Detail</h3>
          <p v-if="scoringDetailState === 'loading'" class="state-panel">
            Loading scoring artifact, predictions, and aggregates…
          </p>
          <div v-else-if="scoringDetailState === 'error'" class="state-panel state-panel--error">
            <p>{{ scoringDetailError }}</p>
            <button class="button button--quiet" type="button" @click="loadScoringArtifactDetail">
              Retry scoring detail
            </button>
          </div>

          <template v-else-if="scoringDetailState === 'ready' && scoringDetailRun && scoringOverallAggregate">
            <dl class="source-facts">
              <div>
                <dt>Scoring artifact SHA-256</dt>
                <dd><code>{{ scoringDetailRun.scoring_artifact_payload_sha256 }}</code></dd>
              </div>
              <div>
                <dt>Dataset</dt>
                <dd>{{ scoringDetailRun.dataset_id }} · {{ scoringDetailRun.dataset_version }}</dd>
              </div>
              <div><dt>Lottery</dt><dd>{{ lotteryLabel(scoringDetailRun.lottery_type) }}</dd></div>
              <div><dt>Target count</dt><dd>{{ scoringDetailRun.target_count }}</dd></div>
              <div><dt>Strategy count</dt><dd>{{ scoringDetailRun.strategy_count }}</dd></div>
              <div><dt>Scored record count</dt><dd>{{ scoringDetailRun.scored_record_count }}</dd></div>
              <div>
                <dt>Source replay artifact</dt>
                <dd><code>{{ scoringDetailRun.source_replay_artifact_payload_sha256 }}</code></dd>
              </div>
            </dl>

            <section aria-labelledby="strategy-scoring-aggregates-title">
              <h4 id="strategy-scoring-aggregates-title">Strategy aggregates</h4>
              <div v-if="scoringStrategyAggregates.length" class="table-wrap">
                <table>
                  <caption>Raw per-strategy source, status, and prize counts</caption>
                  <thead>
                    <tr>
                      <th scope="col">Strategy</th>
                      <th scope="col">Version</th>
                      <th v-for="field in aggregateCountFields" :key="field.key" scope="col">
                        {{ field.label }}
                      </th>
                      <th v-for="field in prizeCountFields" :key="field.key" scope="col">
                        {{ field.label }}
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="aggregate in scoringStrategyAggregates" :key="aggregate.aggregate_sha256">
                      <th scope="row">{{ aggregate.strategy_id }}</th>
                      <td>{{ nullableText(aggregate.strategy_version) }}</td>
                      <td v-for="field in aggregateCountFields" :key="field.key">
                        {{ aggregate[field.key] }}
                      </td>
                      <td v-for="field in prizeCountFields" :key="field.key">
                        {{ aggregate[field.key] }}
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <p v-else class="state-panel">No strategy aggregate rows are available.</p>
            </section>

            <section aria-labelledby="overall-scoring-aggregate-title">
              <h4 id="overall-scoring-aggregate-title">Overall aggregate</h4>
              <dl class="source-facts">
                <div v-for="field in aggregateCountFields" :key="field.key">
                  <dt>{{ field.label }}</dt>
                  <dd>{{ scoringOverallAggregate[field.key] }}</dd>
                </div>
                <div v-for="field in prizeCountFields" :key="field.key">
                  <dt>{{ field.label }}</dt>
                  <dd>{{ scoringOverallAggregate[field.key] }}</dd>
                </div>
              </dl>
            </section>

            <section aria-labelledby="scored-predictions-title">
              <h4 id="scored-predictions-title">Scored predictions</h4>
              <form class="panel filter-panel" @submit.prevent="loadFilteredScoringPredictions">
                <div class="filter-grid">
                  <label>
                    <span>Target draw</span>
                    <input v-model.trim="predictionFilters.targetDraw" name="target_draw" />
                  </label>
                  <label>
                    <span>Strategy ID</span>
                    <input v-model.trim="predictionFilters.strategyId" name="strategy_id" />
                  </label>
                  <label>
                    <span>Status</span>
                    <input v-model.trim="predictionFilters.status" name="status" />
                  </label>
                  <label>
                    <span>Prize tier</span>
                    <input v-model.trim="predictionFilters.tier" name="tier" />
                  </label>
                </div>
                <div class="filter-actions">
                  <button class="button button--primary" type="submit">
                    Apply prediction filters
                  </button>
                </div>
              </form>

              <p v-if="scoringPredictionsState === 'loading'" class="state-panel">
                Loading predictions…
              </p>
              <div v-else-if="scoringPredictionsState === 'error'" class="state-panel state-panel--error">
                <p>{{ scoringPredictionsError }}</p>
                <button class="button button--quiet" type="button" @click="loadFilteredScoringPredictions">
                  Retry predictions
                </button>
              </div>
              <p v-else-if="scoringPredictionsState === 'empty'" class="state-panel">
                No predictions match these filters.
              </p>
              <div v-else-if="scoringPredictionsState === 'ready'" class="table-wrap">
                <table>
                  <caption>Prediction status fields and scoring results are shown independently</caption>
                  <thead>
                    <tr>
                      <th scope="col">Target draw</th>
                      <th scope="col">Strategy</th>
                      <th scope="col">History status / reason</th>
                      <th scope="col">Prediction status / reason</th>
                      <th scope="col">Scoring status / reason</th>
                      <th scope="col">Predicted numbers</th>
                      <th scope="col">Main hits</th>
                      <th scope="col">Special hit</th>
                      <th scope="col">Prize tier</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr
                      v-for="prediction in scoringPredictions"
                      :key="`${prediction.run_payload_sha256}-${prediction.ordinal}`"
                    >
                      <td>{{ prediction.target_draw_number }} · {{ prediction.target_draw_date }}</td>
                      <td>{{ prediction.strategy_id }}</td>
                      <td>
                        {{ prediction.source_history_status }} / {{ nullableText(prediction.source_history_reason_code) }}
                      </td>
                      <td>
                        {{ nullableText(prediction.source_prediction_status) }} /
                        {{ nullableText(prediction.source_prediction_reason_code) }}
                      </td>
                      <td>{{ prediction.scoring_status }} / {{ nullableText(prediction.scoring_reason_code) }}</td>
                      <td>{{ predictedNumbers(prediction.predicted_main_numbers) }}</td>
                      <td>{{ prediction.main_number_hit_count ?? '—' }}</td>
                      <td>
                        {{ prediction.special_number_hit === null || prediction.special_number_hit === undefined
                          ? '—'
                          : prediction.special_number_hit ? 'Yes' : 'No' }}
                      </td>
                      <td>
                        {{ nullableText(prediction.prize_tier_id) }}
                        <span v-if="prediction.prize_official_label">· {{ prediction.prize_official_label }}</span>
                        <span v-if="prediction.no_prize_result">· {{ prediction.no_prize_result }}</span>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </section>
          </template>
        </section>

        <section v-for="group in optimalResult.groups" :key="group.ticket_count">
          <h3>{{ group.ticket_count }}-ticket portfolios — {{ group.status }}</h3>
          <div v-if="group.candidates.length" class="table-wrap">
            <table>
              <caption>Rank-ordered {{ group.ticket_count }}-ticket portfolio candidates</caption>
              <thead>
                <tr>
                  <th scope="col">Rank</th>
                  <th scope="col">Strategies</th>
                  <th scope="col">Winning tickets</th>
                  <th scope="col">No-prize tickets</th>
                  <th scope="col">Scored</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="candidate in group.candidates" :key="candidate.candidate_sha256">
                  <td>{{ candidate.rank }}</td>
                  <td>{{ candidate.members.map((member) => member.strategy_id).join(', ') }}</td>
                  <td>{{ candidate.winning_ticket_count }} / {{ candidate.total_ticket_count }}</td>
                  <td>{{ candidate.no_prize_count }}</td>
                  <td>{{ candidate.scored_count }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p v-else class="state-panel">No candidates in this group.</p>
        </section>
      </template>
    </section>
  </section>
</template>
