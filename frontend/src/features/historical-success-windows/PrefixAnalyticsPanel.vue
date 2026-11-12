<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import {
  getHistoricalPrefixAnalyticsRankings,
  getHistoricalPrefixAnalyticsReplay,
  getHistoricalPrefixAnalyticsStrategies,
  HISTORICAL_PREFIX_ANALYTICS_OVERVIEW_PREFIX_COUNTS,
  HISTORICAL_PREFIX_ANALYTICS_REPLAY_PREFIX_COUNTS,
  HistoricalPrefixAnalyticsRequestError,
  type HistoricalPrefixAnalyticsOverviewPrefixCount,
  type HistoricalPrefixAnalyticsOverviewResponse,
  type HistoricalPrefixAnalyticsRankingsResponse,
  type HistoricalPrefixAnalyticsReplayPrefixCount,
  type HistoricalPrefixAnalyticsReplayResponse,
  type HistoricalPrefixAnalyticsStrategyIdentity,
} from '../../api/historicalPrefixAnalytics'

type QueryState = 'idle' | 'loading' | 'ready' | 'empty' | 'error'

const isOpen = ref(false)
const overviewPrefixCount = ref<HistoricalPrefixAnalyticsOverviewPrefixCount>(10)
const replayPrefixCount = ref<HistoricalPrefixAnalyticsReplayPrefixCount>(10)
const replayLimit = ref(20)

const rankingsState = ref<QueryState>('idle')
const rankings = ref<HistoricalPrefixAnalyticsRankingsResponse | null>(null)
const rankingsError = ref<unknown>(null)
const overviewState = ref<QueryState>('idle')
const overview = ref<HistoricalPrefixAnalyticsOverviewResponse | null>(null)
const overviewError = ref<unknown>(null)
const selectedStrategy = ref<HistoricalPrefixAnalyticsStrategyIdentity | null>(null)
const replayState = ref<QueryState>('idle')
const replay = ref<HistoricalPrefixAnalyticsReplayResponse | null>(null)
const replayError = ref<unknown>(null)

const hasStarted = ref(false)
const canReplayPrevious = computed(() => (replay.value?.offset ?? 0) > 0)
const canReplayNext = computed(
  () =>
    replay.value !== null &&
    replay.value.offset + replay.value.limit < replay.value.total_count,
)
const replayPageLabel = computed(() => {
  if (replay.value === null || replay.value.total_count === 0) return ''
  const first = replay.value.offset + 1
  const last = Math.min(replay.value.offset + replay.value.items.length, replay.value.total_count)
  return `${first}–${last} of ${replay.value.total_count}`
})

let mounted = false
let rankingsGeneration = 0
let overviewGeneration = 0
let replayGeneration = 0
let rankingsController: AbortController | null = null
let overviewController: AbortController | null = null
let replayController: AbortController | null = null

function toggleOpen(): void {
  isOpen.value = !isOpen.value
  if (!isOpen.value || hasStarted.value) return
  hasStarted.value = true
  void loadRankings()
  void loadOverview(overviewPrefixCount.value)
}

async function loadRankings(): Promise<void> {
  const generation = ++rankingsGeneration
  rankingsController?.abort()
  const controller = new AbortController()
  rankingsController = controller
  rankingsState.value = 'loading'
  rankingsError.value = null
  rankings.value = null

  try {
    const response = await getHistoricalPrefixAnalyticsRankings(controller.signal)
    if (!mounted || generation !== rankingsGeneration || controller.signal.aborted) return
    rankings.value = response
    rankingsState.value = response.groups.length === 0 ? 'empty' : 'ready'
  } catch (error: unknown) {
    if (!mounted || generation !== rankingsGeneration || controller.signal.aborted) return
    rankingsError.value = error
    rankingsState.value = 'error'
  }
}

async function loadOverview(
  prefixCount: HistoricalPrefixAnalyticsOverviewPrefixCount,
): Promise<void> {
  const generation = ++overviewGeneration
  overviewController?.abort()
  const controller = new AbortController()
  overviewController = controller
  overviewState.value = 'loading'
  overviewError.value = null
  overview.value = null

  try {
    const response = await getHistoricalPrefixAnalyticsStrategies(prefixCount, controller.signal)
    if (!mounted || generation !== overviewGeneration || controller.signal.aborted) return
    overview.value = response
    overviewState.value = response.summaries.length === 0 ? 'empty' : 'ready'
  } catch (error: unknown) {
    if (!mounted || generation !== overviewGeneration || controller.signal.aborted) return
    overviewError.value = error
    overviewState.value = 'error'
  }
}

function overviewPrefixChanged(): void {
  void loadOverview(overviewPrefixCount.value)
}

function chooseStrategy(identity: HistoricalPrefixAnalyticsStrategyIdentity): void {
  selectedStrategy.value = identity
  clearReplay()
}

function clearReplay(): void {
  replayGeneration += 1
  replayController?.abort()
  replay.value = null
  replayError.value = null
  replayState.value = 'idle'
}

function replayControlsChanged(): void {
  clearReplay()
}

async function loadReplay(offset = 0): Promise<void> {
  const strategy = selectedStrategy.value
  if (strategy === null) return

  const generation = ++replayGeneration
  replayController?.abort()
  const controller = new AbortController()
  replayController = controller
  replayState.value = 'loading'
  replayError.value = null
  replay.value = null

  try {
    const response = await getHistoricalPrefixAnalyticsReplay(
      strategy,
      {
        prefix_count: replayPrefixCount.value,
        limit: replayLimit.value,
        offset,
      },
      controller.signal,
    )
    if (!mounted || generation !== replayGeneration || controller.signal.aborted) return
    replay.value = response
    replayState.value = response.items.length === 0 ? 'empty' : 'ready'
  } catch (error: unknown) {
    if (!mounted || generation !== replayGeneration || controller.signal.aborted) return
    replayError.value = error
    replayState.value = 'error'
  }
}

function errorMessage(error: unknown, label: string): string {
  if (error instanceof HistoricalPrefixAnalyticsRequestError) {
    if (error.errorCode?.toUpperCase().includes('NOT_CONFIGURED')) {
      return 'SOURCE_NOT_CONFIGURED (HTTP ' + error.status + '): ' + error.message
    }
    if (error.status === 404) {
      return 'HTTP_ERROR (404): That exact strategy, version, and replicate was not found.'
    }
    if (error.status === 422) {
      return 'HTTP_ERROR (422): The API rejected these prefix or pagination values.'
    }
    if (error.status === 503) {
      return 'API_UNAVAILABLE (503): ' + error.message
    }
    return 'HTTP_ERROR (HTTP ' + error.status + '): ' + label + ' failed: ' + error.message
  }
  const detail = error instanceof Error ? error.message : label + ' request failed.'
  return 'API_UNAVAILABLE: ' + detail
}
function errorCode(error: unknown): string | null {
  return error instanceof HistoricalPrefixAnalyticsRequestError ? error.errorCode : null
}

function exactRatio(value: { numerator: number; denominator: number; is_available: boolean }): string {
  if (value.denominator === 0) return 'Unavailable (ZERO_DENOMINATOR)'
  return value.is_available ? value.numerator + ' / ' + value.denominator : 'Unavailable'
}

function sourceValue(value: string | null | undefined): string {
  return typeof value === 'string' && value.trim().length > 0
    ? value
    : 'Not provided by API'
}
function strategyKey(identity: HistoricalPrefixAnalyticsStrategyIdentity): string {
  return JSON.stringify([identity.strategy_id, identity.strategy_version, identity.replicate])
}

function isSelected(identity: HistoricalPrefixAnalyticsStrategyIdentity): boolean {
  return selectedStrategy.value !== null && strategyKey(selectedStrategy.value) === strategyKey(identity)
}

function nullableLabel(value: string | null): string {
  return value ?? '—'
}

onMounted(() => {
  mounted = true
})

onBeforeUnmount(() => {
  mounted = false
  rankingsGeneration += 1
  overviewGeneration += 1
  replayGeneration += 1
  rankingsController?.abort()
  overviewController?.abort()
  replayController?.abort()
})
</script>

<template>
  <section class="prefix-analytics" aria-labelledby="prefix-analytics-title">
    <p
      class="prefix-analytics__boundary"
      data-testid="prefix-analytics-provider-status"
      role="status"
    >
      Formal provider: NOT IMPLEMENTED · official source: SOURCE_MISSING. The API contract exists,
      but no formal historical source is wired. Payload fields below are shown as the API returned
      them and are not verified formal historical results.
    </p>
    <button
      class="prefix-analytics__toggle"
      type="button"
      :aria-expanded="isOpen"
      aria-controls="prefix-analytics-content"
      @click="toggleOpen"
    >
      <span>
        <small>Separate historical-prefix-analytics API source</small>
        <strong id="prefix-analytics-title">Historical Prefix Analytics</strong>
      </span>
      <span aria-hidden="true">{{ isOpen ? '−' : '+' }}</span>
    </button>

    <div v-show="isOpen" id="prefix-analytics-content" class="prefix-analytics__content">
      <p class="prefix-analytics__boundary">
        PREFIX_PORTFOLIO_SUCCESS means that, for one valid target draw and this exact strategy
        identity and prefix, at least one selected ticket has main_hit_count &gt;= 1. Its denominator
        is valid target draws for the same identity. OFFICIAL_ANY_PRIZE means at least one ticket
        receives an official prize. OFFICIAL_ANY_PRIZE is a distinct event and is not this prefix
        ratio. These results are separate from the import-based Historical Prefix Success Windows
        results below; the data is never combined and makes no future-performance promise.
      </p>

      <section class="prefix-analytics__section" aria-labelledby="prefix-rankings-title">
        <div class="prefix-analytics__heading">
          <div>
            <p class="prefix-analytics__eyebrow">Server-provided order · no client ranking</p>
            <h3 id="prefix-rankings-title">Prefix strategy ranking</h3>
          </div>
          <button class="prefix-analytics__button" type="button" @click="loadRankings">
            {{ rankingsState === 'loading' ? 'Loading…' : 'Refresh rankings' }}
          </button>
        </div>

        <p v-if="rankingsState === 'loading'" class="prefix-analytics__state" role="status">
          Loading ranking groups…
        </p>
        <div v-else-if="rankingsState === 'error'" class="prefix-analytics__state prefix-analytics__state--error" role="alert">
          <strong>{{ errorMessage(rankingsError, 'Prefix rankings') }}</strong>
          <span v-if="errorCode(rankingsError)">API error code: {{ errorCode(rankingsError) }}</span>
          <button class="prefix-analytics__button" type="button" @click="loadRankings">Retry rankings</button>
        </div>
        <p v-else-if="rankingsState === 'empty'" class="prefix-analytics__state">
          API query: SUCCESS_EMPTY · The API returned no ranking groups.
        </p>

        <template v-else-if="rankingsState === 'ready' && rankings">
          <p class="prefix-analytics__state" data-testid="prefix-rankings-query-success">
            API query: SUCCESS_WITH_DATA · {{ rankings.groups.length }} ranking groups returned.
          </p>
          <dl class="prefix-analytics__source" aria-label="Ranking source identity">
            <div><dt>Dataset</dt><dd>{{ sourceValue(rankings.metadata.dataset_identity) }} · {{ sourceValue(rankings.metadata.lottery_type) }}</dd></div>
            <div><dt>Source import identity</dt><dd><code>{{ sourceValue(rankings.metadata.source_import_identity_sha256) }}</code></dd></div>
            <div><dt>Source manifest</dt><dd><code>{{ sourceValue(rankings.metadata.source_manifest_sha256) }}</code></dd></div>
            <div><dt>Source artifact</dt><dd><code>{{ sourceValue(rankings.metadata.source_artifact_sha256) }}</code></dd></div>
            <div><dt>Dataset SHA-256</dt><dd><code>{{ sourceValue(rankings.metadata.dataset_sha256) }}</code></dd></div>
            <div><dt>Ranking policy</dt><dd>{{ sourceValue(rankings.metadata.ranking_policy_id) }}</dd></div>
          </dl>

          <article v-for="group in rankings.groups" :key="group.prefix_count" class="prefix-analytics__group">
            <div class="prefix-analytics__group-heading">
              <h4>Prefix {{ group.prefix_count }}</h4>
              <span>{{ group.status }} · {{ group.total_candidate_count }} eligible · top {{ group.requested_top_k }}</span>
            </div>
            <p v-if="group.candidates.length === 0" class="prefix-analytics__empty">
              No eligible strategies were returned for this ranking group.
            </p>
            <div v-else class="prefix-analytics__table-wrap">
              <table class="prefix-analytics__table">
                <caption>
                  Rank and eligibility are from the rankings API. Success is
                  PREFIX_PORTFOLIO_SUCCESS; exact ratios use the API numerator and denominator.
                </caption>
                <thead>
                  <tr>
                    <th scope="col">Rank</th>
                    <th scope="col">Exact strategy identity</th>
                    <th scope="col">Eligibility / status</th>
                    <th scope="col">Observed / success counts</th>
                    <th scope="col">PREFIX_PORTFOLIO_SUCCESS (successes / valid target draws)</th>
                    <th scope="col">Replay</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="candidate in group.candidates" :key="strategyKey(candidate.identity)">
                    <td>{{ candidate.rank }}</td>
                    <td>
                      <strong>{{ candidate.identity.strategy_id }}</strong>
                      <small>{{ candidate.identity.strategy_version }} · replicate {{ candidate.identity.replicate }}</small>
                      <small>Effective ID: {{ candidate.identity.effective_strategy_id }}</small>
                    </td>
                    <td>
                      <strong>{{ candidate.summary.ranking_eligible ? 'Eligible' : 'Not eligible' }}</strong>
                      <small>{{ candidate.summary.status }}</small>
                      <small v-if="candidate.summary.ranking_exclusion_reason">
                        {{ candidate.summary.ranking_exclusion_reason }}
                      </small>
                    </td>
                    <td>
                      {{ candidate.summary.distinct_draw_count }} observations ·
                      {{ candidate.summary.portfolio_success_count }} successes
                    </td>
                    <td>{{ exactRatio(candidate.summary.portfolio_success_rate) }}</td>
                    <td>
                      <button class="prefix-analytics__button" type="button" @click="chooseStrategy(candidate.identity)">
                        {{ isSelected(candidate.identity) ? 'Selected' : 'Use in replay' }}
                      </button>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </article>
        </template>
      </section>

      <section class="prefix-analytics__section" aria-labelledby="prefix-overview-title">
        <div class="prefix-analytics__heading">
          <div>
            <p class="prefix-analytics__eyebrow">Common overview prefixes · 10 / 15 / 20</p>
            <h3 id="prefix-overview-title">Strategy overview</h3>
          </div>
          <label class="prefix-analytics__filter">
            <span>Prefix count</span>
            <select v-model.number="overviewPrefixCount" name="prefix-analytics-overview-prefix" @change="overviewPrefixChanged">
              <option v-for="prefix in HISTORICAL_PREFIX_ANALYTICS_OVERVIEW_PREFIX_COUNTS" :key="prefix" :value="prefix">
                {{ prefix }}
              </option>
            </select>
          </label>
        </div>

        <p v-if="overviewState === 'loading'" class="prefix-analytics__state" role="status">
          Loading the prefix {{ overviewPrefixCount }} overview…
        </p>
        <div v-else-if="overviewState === 'error'" class="prefix-analytics__state prefix-analytics__state--error" role="alert">
          <strong>{{ errorMessage(overviewError, 'Strategy overview') }}</strong>
          <span v-if="errorCode(overviewError)">API error code: {{ errorCode(overviewError) }}</span>
          <button class="prefix-analytics__button" type="button" @click="loadOverview(overviewPrefixCount)">Retry overview</button>
        </div>
        <p v-else-if="overviewState === 'empty'" class="prefix-analytics__state">
          API query: SUCCESS_EMPTY · No strategy summaries were returned for prefix {{ overviewPrefixCount }}.
        </p>

        <template v-else-if="overviewState === 'ready' && overview">
          <p class="prefix-analytics__state" data-testid="prefix-overview-query-success">
            API query: SUCCESS_WITH_DATA · {{ overview.summaries.length }} strategy summaries returned.
          </p>
          <dl class="prefix-analytics__source" aria-label="Overview source identity">
            <div><dt>Dataset</dt><dd>{{ sourceValue(overview.metadata.dataset_identity) }} · {{ sourceValue(overview.metadata.lottery_type) }}</dd></div>
            <div><dt>Source import identity</dt><dd><code>{{ sourceValue(overview.metadata.source_import_identity_sha256) }}</code></dd></div>
            <div><dt>Source manifest</dt><dd><code>{{ sourceValue(overview.metadata.source_manifest_sha256) }}</code></dd></div>
            <div><dt>Source artifact</dt><dd><code>{{ sourceValue(overview.metadata.source_artifact_sha256) }}</code></dd></div>
            <div><dt>Dataset SHA-256</dt><dd><code>{{ sourceValue(overview.metadata.dataset_sha256) }}</code></dd></div>
            <div><dt>Ranking policy</dt><dd>{{ sourceValue(overview.metadata.ranking_policy_id) }}</dd></div>
          </dl>

          <p class="prefix-analytics__count">{{ overview.total_count }} strategy summaries returned by the API.</p>
          <div class="prefix-analytics__table-wrap">
            <table class="prefix-analytics__table">
              <caption>
                Counts, eligibility, and PREFIX_PORTFOLIO_SUCCESS numerator/denominator are returned by
                the strategies API for each exact strategy identity and prefix.
              </caption>
              <thead>
                <tr>
                  <th scope="col">Exact strategy identity</th>
                  <th scope="col">Prefix / status</th>
                  <th scope="col">Ranking eligibility</th>
                  <th scope="col">Observed / success counts</th>
                  <th scope="col">PREFIX_PORTFOLIO_SUCCESS (successes / valid target draws)</th>
                  <th scope="col">Replay</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="summary in overview.summaries" :key="strategyKey(summary.identity)">
                  <td>
                    <strong>{{ summary.identity.strategy_id }}</strong>
                    <small>{{ summary.identity.strategy_version }} · replicate {{ summary.identity.replicate }}</small>
                    <small>Effective ID: {{ summary.identity.effective_strategy_id }}</small>
                  </td>
                  <td>Prefix {{ summary.prefix_count }} · {{ summary.status }}</td>
                  <td>
                    <strong>{{ summary.ranking_eligible ? 'Eligible' : 'Not eligible' }}</strong>
                    <small>{{ nullableLabel(summary.ranking_exclusion_reason) }}</small>
                  </td>
                  <td>{{ summary.distinct_draw_count }} observations · {{ summary.portfolio_success_count }} successes</td>
                  <td>{{ exactRatio(summary.portfolio_success_rate) }}</td>
                  <td>
                    <button class="prefix-analytics__button" type="button" @click="chooseStrategy(summary.identity)">
                      {{ isSelected(summary.identity) ? 'Selected' : 'Use in replay' }}
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </template>
      </section>

      <section class="prefix-analytics__section" aria-labelledby="prefix-replay-title">
        <div class="prefix-analytics__heading">
          <div>
            <p class="prefix-analytics__eyebrow">Exact strategy identity · paginated API response</p>
            <h3 id="prefix-replay-title">Strategy replay</h3>
          </div>
        </div>

        <p v-if="selectedStrategy === null" class="prefix-analytics__state">
          Select a strategy identity from the ranking or overview to request its replay.
        </p>
        <template v-else>
          <dl class="prefix-analytics__selected-identity" aria-label="Selected replay identity">
            <div><dt>Strategy ID</dt><dd>{{ selectedStrategy.strategy_id }}</dd></div>
            <div><dt>Version</dt><dd>{{ selectedStrategy.strategy_version }}</dd></div>
            <div><dt>Replicate</dt><dd>{{ selectedStrategy.replicate }}</dd></div>
            <div><dt>Effective strategy</dt><dd>{{ selectedStrategy.effective_strategy_id }}</dd></div>
          </dl>
          <form class="prefix-analytics__replay-controls" @submit.prevent="loadReplay(0)">
            <label class="prefix-analytics__filter">
              <span>Replay prefix count</span>
              <select v-model.number="replayPrefixCount" name="prefix-analytics-replay-prefix" @change="replayControlsChanged">
                <option v-for="prefix in HISTORICAL_PREFIX_ANALYTICS_REPLAY_PREFIX_COUNTS" :key="prefix" :value="prefix">
                  {{ prefix }}
                </option>
              </select>
            </label>
            <label class="prefix-analytics__filter">
              <span>Rows per page</span>
              <select v-model.number="replayLimit" name="prefix-analytics-replay-limit" @change="replayControlsChanged">
                <option :value="10">10</option>
                <option :value="20">20</option>
                <option :value="50">50</option>
              </select>
            </label>
            <button class="prefix-analytics__button" type="submit" :disabled="replayState === 'loading'">
              {{ replayState === 'loading' ? 'Loading replay…' : 'Load replay' }}
            </button>
          </form>

          <p v-if="replayState === 'loading'" class="prefix-analytics__state" role="status">
            Loading replay rows…
          </p>
          <div v-else-if="replayState === 'error'" class="prefix-analytics__state prefix-analytics__state--error" role="alert">
            <strong>{{ errorMessage(replayError, 'Strategy replay') }}</strong>
            <span v-if="errorCode(replayError)">API error code: {{ errorCode(replayError) }}</span>
            <button class="prefix-analytics__button" type="button" @click="loadReplay(replay?.offset ?? 0)">Retry replay</button>
          </div>
          <p v-else-if="replayState === 'empty'" class="prefix-analytics__state">
            API query: SUCCESS_EMPTY · The replay API returned no rows for this page.
          </p>

          <template v-else-if="replayState === 'ready' && replay">
            <p class="prefix-analytics__state" data-testid="prefix-replay-query-success">
              API query: SUCCESS_WITH_DATA · {{ replay.items.length }} replay rows returned.
            </p>
            <dl class="prefix-analytics__source" aria-label="Replay source identity">
              <div><dt>Dataset</dt><dd>{{ sourceValue(replay.metadata.dataset_identity) }} · {{ sourceValue(replay.metadata.lottery_type) }}</dd></div>
              <div><dt>Source import identity</dt><dd><code>{{ sourceValue(replay.metadata.source_import_identity_sha256) }}</code></dd></div>
              <div><dt>Source manifest</dt><dd><code>{{ sourceValue(replay.metadata.source_manifest_sha256) }}</code></dd></div>
              <div><dt>Source artifact</dt><dd><code>{{ sourceValue(replay.metadata.source_artifact_sha256) }}</code></dd></div>
              <div><dt>Dataset SHA-256</dt><dd><code>{{ sourceValue(replay.metadata.dataset_sha256) }}</code></dd></div>
              <div><dt>Ranking policy</dt><dd>{{ sourceValue(replay.metadata.ranking_policy_id) }}</dd></div>
            </dl>
            <nav class="prefix-analytics__pagination" aria-label="Prefix replay pages">
              <button class="prefix-analytics__button" type="button" :disabled="!canReplayPrevious" @click="loadReplay(Math.max(0, replay.offset - replay.limit))">
                Previous
              </button>
              <span>{{ replayPageLabel }}</span>
              <button class="prefix-analytics__button" type="button" :disabled="!canReplayNext" @click="loadReplay(replay.offset + replay.limit)">
                Next
              </button>
            </nav>
            <div class="prefix-analytics__table-wrap">
              <table class="prefix-analytics__table prefix-analytics__replay-table">
                <caption>
                  Per-draw API rows for the selected strategy identity and prefix. PREFIX_PORTFOLIO_SUCCESS
                  is the API boolean; it is distinct from OFFICIAL_ANY_PRIZE.
                </caption>
                <thead>
                  <tr>
                    <th scope="col">Target draw</th>
                    <th scope="col">Exact identity</th>
                    <th scope="col">Prefix</th>
                    <th scope="col">PREFIX_PORTFOLIO_SUCCESS</th>
                    <th scope="col">Best main hits</th>
                    <th scope="col">Total main hits</th>
                    <th scope="col">Included ticket positions</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(item, index) in replay.items" :key="`${item.target.draw_sha256}:${index}`">
                    <td>{{ item.target.draw_number }} · {{ item.target.draw_date }}</td>
                    <td>
                      {{ item.identity.strategy_id }}<br />
                      {{ item.identity.strategy_version }} · replicate {{ item.identity.replicate }}
                    </td>
                    <td>{{ item.prefix_count }} · {{ item.prefix_ticket_count }} tickets</td>
                    <td>{{ item.portfolio_success ? 'Success' : 'No success' }}</td>
                    <td>{{ item.best_single_main_hit_count }}</td>
                    <td>{{ item.total_main_hit_count }}</td>
                    <td>{{ item.included_ticket_positions.join(', ') || '—' }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </template>
        </template>
      </section>
    </div>
  </section>
</template>

<style scoped>
.prefix-analytics { margin: 0 0 20px; border: 1px solid var(--line); border-radius: 18px; background: linear-gradient(145deg, rgb(18 35 31 / 94%), rgb(10 23 20 / 96%)); }
.prefix-analytics__toggle { display: flex; width: 100%; align-items: center; justify-content: space-between; padding: 20px 24px; border: 0; background: transparent; color: var(--ink); text-align: left; cursor: pointer; }
.prefix-analytics__toggle small, .prefix-analytics__toggle strong { display: block; }
.prefix-analytics__toggle small, .prefix-analytics__eyebrow { color: var(--muted); font: 500 10px/1.4 'SFMono-Regular', Consolas, monospace; letter-spacing: .08em; text-transform: uppercase; }
.prefix-analytics__toggle strong { margin-top: 7px; font-size: 20px; }
.prefix-analytics__toggle > span:last-child { color: var(--mint); font-size: 25px; }
.prefix-analytics__content { padding: 0 24px 24px; }
.prefix-analytics__boundary { margin: 0 0 20px; padding: 14px 16px; border: 1px solid rgb(242 197 114 / 30%); border-radius: 12px; color: var(--amber); font-size: 12px; line-height: 1.6; }
.prefix-analytics__section { margin-top: 18px; padding: 20px; border: 1px solid var(--line); border-radius: 15px; background: rgb(6 17 14 / 54%); }
.prefix-analytics__heading, .prefix-analytics__group-heading { display: flex; gap: 16px; align-items: center; justify-content: space-between; }
.prefix-analytics__heading { margin-bottom: 17px; }
.prefix-analytics__eyebrow { margin: 0 0 6px; }
.prefix-analytics__heading h3, .prefix-analytics__group-heading h4 { margin: 0; color: var(--ink); }
.prefix-analytics__heading h3 { font-size: 17px; }
.prefix-analytics__group { margin-top: 18px; padding: 15px; border: 1px solid var(--line); border-radius: 12px; }
.prefix-analytics__group-heading h4 { font-size: 14px; }
.prefix-analytics__group-heading span, .prefix-analytics__count, .prefix-analytics__pagination { color: var(--muted); font-size: 11px; }
.prefix-analytics__source, .prefix-analytics__selected-identity { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 1px; overflow: hidden; margin: 0 0 15px; border: 1px solid var(--line); border-radius: 10px; background: var(--line); }
.prefix-analytics__source div, .prefix-analytics__selected-identity div { min-width: 0; padding: 10px; background: var(--surface); }
.prefix-analytics__source dt, .prefix-analytics__source dd, .prefix-analytics__selected-identity dt, .prefix-analytics__selected-identity dd { margin: 0; }
.prefix-analytics__source dt, .prefix-analytics__selected-identity dt { color: var(--muted); font-size: 9px; text-transform: uppercase; }
.prefix-analytics__source dd, .prefix-analytics__selected-identity dd { margin-top: 6px; color: var(--ink); font-size: 10px; overflow-wrap: anywhere; }
.prefix-analytics__source code { font-size: 9px; }
.prefix-analytics__table-wrap { overflow-x: auto; }
.prefix-analytics__table { width: 100%; min-width: 920px; border-collapse: collapse; color: var(--ink); font-size: 11px; }
.prefix-analytics__table caption { padding: 0 0 10px; color: var(--muted); text-align: left; }
.prefix-analytics__table th, .prefix-analytics__table td { padding: 10px; border: 1px solid var(--line); vertical-align: top; text-align: left; }
.prefix-analytics__table th { background: #0a1714; color: var(--mint); font-size: 9px; text-transform: uppercase; }
.prefix-analytics__table td { overflow-wrap: anywhere; }
.prefix-analytics__table td strong, .prefix-analytics__table td small { display: block; }
.prefix-analytics__table td small { margin-top: 5px; color: var(--muted); font-size: 9px; }
.prefix-analytics__button { min-height: 34px; padding: 7px 10px; border: 1px solid var(--line); border-radius: 8px; background: transparent; color: var(--mint); font: inherit; cursor: pointer; }
.prefix-analytics__button:disabled { opacity: .48; cursor: not-allowed; }
.prefix-analytics__filter { display: grid; gap: 6px; color: var(--muted); font-size: 10px; }
.prefix-analytics__filter select { min-width: 120px; min-height: 36px; padding: 7px 9px; border: 1px solid var(--line); border-radius: 8px; background: #081512; color: var(--ink); }
.prefix-analytics__state, .prefix-analytics__empty { display: flex; gap: 12px; align-items: center; justify-content: space-between; margin: 0; padding: 14px; border: 1px solid var(--line); border-radius: 10px; color: var(--muted); font-size: 12px; line-height: 1.5; }
.prefix-analytics__state--error { flex-wrap: wrap; border-color: rgb(255 154 141 / 42%); color: var(--danger); }
.prefix-analytics__state--error span { width: 100%; font-size: 10px; }
.prefix-analytics__empty { margin-top: 12px; }
.prefix-analytics__count { margin: 0 0 10px; }
.prefix-analytics__selected-identity { margin-bottom: 16px; }
.prefix-analytics__replay-controls { display: flex; flex-wrap: wrap; gap: 12px; align-items: end; margin-bottom: 14px; }
.prefix-analytics__pagination { display: flex; gap: 12px; align-items: center; justify-content: flex-end; margin: 12px 0; }
.prefix-analytics__replay-table { min-width: 1000px; }
@media (max-width: 720px) {
  .prefix-analytics__content { padding: 0 12px 14px; }
  .prefix-analytics__section { padding: 14px; }
  .prefix-analytics__heading, .prefix-analytics__group-heading { align-items: flex-start; flex-direction: column; }
  .prefix-analytics__source, .prefix-analytics__selected-identity { grid-template-columns: 1fr; }
}
</style>
