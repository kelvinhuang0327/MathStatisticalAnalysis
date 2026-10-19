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

async function loadOptimalRankings(): Promise<void> {
  if (!isValidScoringArtifactSha256(scoringArtifactSha256.value)) {
    shaInputInvalid.value = true
    return
  }
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
})
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
            />
          </label>
          <label>
            <span>Top K</span>
            <input v-model.number="topK" type="number" name="top_k" min="1" max="50" />
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
          <div><dt>Lottery</dt><dd>{{ lotteryLabel(optimalResult.lottery_type) }}</dd></div>
          <div><dt>Ranking policy</dt><dd>{{ optimalResult.ranking_policy_id }}</dd></div>
          <div><dt>Strategy count</dt><dd>{{ optimalResult.strategy_count }}</dd></div>
        </dl>
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
