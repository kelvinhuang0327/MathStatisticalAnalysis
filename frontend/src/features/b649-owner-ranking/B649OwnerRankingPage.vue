<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import {
  R2_BASELINE_SNAPSHOT,
  R2_CORE_OBSERVATIONS,
  R2_OWNER_MATRIX,
  R2_PORTFOLIO_SNAPSHOT,
  R2_REGIME_CANDIDATES,
  R2_SHORT_TERM_HIGH_COVERAGE_LEADERS,
  fetchB649OwnerRankingData,
  type B649OwnerMetadata,
  type B649OwnerRankingData,
} from '../../api/b649OwnerRanking'
import type {
  B649HistoryWindow,
  B649MultiTicketRecord,
  B649PrefixCount,
} from '../../api/b649MultiTicketRecords'
import {
  B649_HISTORY_WINDOWS,
  B649_PREFIX_COUNTS,
} from '../../api/b649MultiTicketRecords'

type LoadState = 'loading' | 'ready' | 'error' | 'empty'
type B649OwnerRecord = Pick<
  B649MultiTicketRecord,
  | 'strategy_id'
  | 'method_family'
  | 'prefix_count'
  | 'window'
  | 'official_rank'
  | 'official_any_prize_rate'
  | 'official_random_baseline_probability'
  | 'official_random_baseline_delta'
  | 'coverage'
  | 'successful_execution_count'
>

const data = ref<B649OwnerRankingData | null>(null)
const loadState = ref<LoadState>('loading')
const errorMessage = ref('')
const ticketCount = ref<B649PrefixCount>(5)
const detailWindow = ref<B649HistoryWindow>('FULL')
let controller: AbortController | null = null
let generation = 0

const currentRecords = computed(() =>
  data.value?.records.filter((record) => record.prefix_count === ticketCount.value) ?? [],
)

const shortTermRows = computed(() =>
  rankedRows(currentRecords.value.filter((record) => record.window === 'RECENT_50')),
)

const shortTermRankLeader = computed(() => shortTermRows.value[0] ?? null)
const highCoverageDefinition = computed(
  () => R2_SHORT_TERM_HIGH_COVERAGE_LEADERS[ticketCount.value],
)
const highCoverageLeader = computed(() =>
  findRecord(highCoverageDefinition.value.strategyToken, 'RECENT_50'),
)

const coreObservationRows = computed(() =>
  R2_CORE_OBSERVATIONS[ticketCount.value].map((metadata) => ({
    metadata,
    record: findRecord(metadata.strategyToken, 'FULL'),
  })),
)

const stableRows = computed(() =>
  R2_CORE_OBSERVATIONS[ticketCount.value]
    .filter((metadata) => metadata.role === 'STABLE_CORE' || metadata.role === 'CORE_REGIME')
    .map((metadata) => ({ metadata, record: findRecord(metadata.strategyToken, 'FULL') })),
)

const matrixRows = computed(() =>
  R2_OWNER_MATRIX.filter((definition) => definition.prefixCount === ticketCount.value).map(
    (definition) => ({
      definition,
      full: findRecord(definition.strategyToken, 'FULL'),
      recent750: findRecord(definition.strategyToken, 'RECENT_750'),
      recent300: findRecord(definition.strategyToken, 'RECENT_300'),
      recent50: findRecord(definition.strategyToken, 'RECENT_50'),
    }),
  ),
)

const detailRows = computed(() =>
  rankedRows(
    currentRecords.value.filter((record) => record.window === detailWindow.value),
  ).slice(0, 20),
)

const warningRows = computed(() => [
  {
    badge: 'HIGH_RANK_LOW_COVERAGE',
    title: 'quick_ml_predict',
    detail:
      'FULL #1 / 50%, but only 4 Obs., ~0.19% coverage; no successful observations in the three recent windows.',
    record: findRecord('quick_ml_predict', 'FULL'),
  },
  {
    badge: 'RECENT_NO_OBS',
    title: 'Recent windows',
    detail:
      'Recent rank must be evaluated alongside successful observations, coverage, and FULL context.',
    record: findRecord('quick_ml_predict', 'RECENT_50'),
  },
  {
    badge: 'LOW_COVERAGE_CONTROL',
    title: 'research_cluster_enhancements',
    detail:
      'R2 retains its recent movement, but coverage is ~4%–9%, serving only as a sparse comparison.',
    record: findRecord('research_cluster_enhancements', 'RECENT_50'),
  },
])

const evidenceComparisons = computed(() => [
  {
    label: 'quick_ml_predict',
    caption: 'Official rank retained; evidence strength evaluated separately',
    record: findRecord('quick_ml_predict', 'FULL'),
  },
  {
    label: '6bet_ewma',
    caption: 'broad-coverage comparison',
    record: findRecord('backtest_biglotto_6bet_ewma', 'FULL'),
  },
])

async function load(): Promise<void> {
  controller?.abort()
  controller = new AbortController()
  const currentGeneration = ++generation
  loadState.value = 'loading'
  errorMessage.value = ''
  try {
    const result = await fetchB649OwnerRankingData(controller.signal)
    if (currentGeneration !== generation) return
    data.value = result
    loadState.value = result.records.length > 0 ? 'ready' : 'empty'
  } catch (error: unknown) {
    if (isAbortError(error) || currentGeneration !== generation) return
    loadState.value = 'error'
    errorMessage.value =
      error instanceof Error ? error.message : 'B649 R2 data could not be loaded.'
  }
}

function findRecord(strategyToken: string, window: B649HistoryWindow): B649OwnerRecord | null {
  if (strategyToken === 'portfolio_optimizer') {
    const snapshot = R2_PORTFOLIO_SNAPSHOT[ticketCount.value]?.[window]
    if (snapshot) {
      return {
        strategy_id: 'legacy_biglotto__portfolio_optimizer__1a6efc7959b6',
        method_family: 'statistical',
        prefix_count: ticketCount.value,
        window,
        official_rank: snapshot.rank,
        official_any_prize_rate: snapshot.rate,
        official_random_baseline_probability: null,
        official_random_baseline_delta: snapshot.delta,
        successful_execution_count: snapshot.observations,
        coverage: snapshot.coverage,
      }
    }
  }
  return (
    currentRecords.value.find(
      (record) => record.window === window && record.strategy_id.includes(strategyToken),
    ) ?? null
  )
}

function rankedRows(records: B649OwnerRecord[]): B649OwnerRecord[] {
  return [...records].sort((left, right) => {
    if (left.official_rank === null && right.official_rank === null) return 0
    if (left.official_rank === null) return 1
    if (right.official_rank === null) return -1
    return left.official_rank - right.official_rank
  })
}

function selectTicketCount(value: B649PrefixCount): void {
  ticketCount.value = value
  detailWindow.value = 'FULL'
}

function formatRank(record: B649OwnerRecord | null): string {
  if (record === null) return '—'
  return record.official_rank === null ? '—' : `#${record.official_rank}`
}

function formatRate(value: string | null): string {
  if (value === null) return '—'
  return `${(Number(value) * 100).toFixed(2)}%`
}

function formatDelta(value: string | null): string {
  if (value === null) return '—'
  const percentage = Number(value) * 100
  return `${percentage > 0 ? '+' : ''}${percentage.toFixed(2)} pp`
}

function formatObservations(record: B649OwnerRecord | null): string {
  return record?.successful_execution_count === null || record === null
    ? '—'
    : String(record.successful_execution_count)
}

function formatWindow(window: B649HistoryWindow): string {
  if (window === 'FULL') return 'FULL · Full History Reference'
  if (window === 'RECENT_750') return '750 · Long-Term Regime'
  if (window === 'RECENT_300') return '300 · Mid-Term Regime'
  return '50 · Short-Term Regime'
}

function roleClass(role: B649OwnerMetadata['role']): string {
  return `role-badge role-badge--${role.toLowerCase()}`
}

function warningBadges(record: B649OwnerRecord | null): string[] {
  if (record === null) return []
  const badges: string[] = []
  if (record.strategy_id.includes('quick_ml_predict')) badges.push('HIGH_RANK_LOW_COVERAGE')
  if (record.strategy_id.includes('research_cluster_enhancements')) badges.push('LOW_COVERAGE_CONTROL')
  if (record.window === 'RECENT_50' && record.successful_execution_count === 0) badges.push('RECENT_NO_OBS')
  return badges
}

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === 'AbortError'
}

onMounted(load)
onBeforeUnmount(() => {
  controller?.abort()
  generation += 1
})
</script>

<template>
  <section class="b649-owner" aria-labelledby="b649-owner-title">
    <header class="b649-owner__heading">
      <div>
        <p class="eyebrow">B649 · R2 Owner Ranking</p>
        <h1 id="b649-owner-title">B649 Owner Ranking</h1>
        <p class="b649-owner__intro">
          Review official rank, coverage, observations, random baseline, and recent movement separately across 4 ticket counts for FULL, 750, 300, and 50 windows. This is a read-only descriptive research interface, not a new ranking system.
        </p>
      </div>
      <div class="b649-owner__badges" aria-label="B649 page status">
        <span class="readonly-badge">READ ONLY</span>
        <span class="source-badge">R2 AUTHORITY</span>
      </div>
    </header>

    <div v-if="loadState === 'loading'" class="records-state" role="status" aria-live="polite">
      Loading B649 R2 ranking projection…
    </div>
    <div v-else-if="loadState === 'error'" class="records-state records-state--error" role="alert">
      <strong>B649 R2 ranking projection could not be loaded</strong>
      <p>{{ errorMessage }}</p>
      <button type="button" @click="load">Retry</button>
    </div>
    <div v-else-if="loadState === 'empty'" class="records-state" role="status">
      <strong>No B649 ranking records available to display</strong>
      <p>The page does not recalculate or synthesize ranking data.</p>
      <button type="button" @click="load">Retry</button>
    </div>

    <template v-else-if="data">
      <aside class="research-disclaimer" role="note">
        Historical success rates, rankings, and random baseline deltas are for descriptive research only and do not constitute future predictions, recommendations, deployment decisions, or prize guarantees. All research roles are exploratory designations, not lifecycle states, deployment statuses, or production recommendations.
      </aside>

      <div class="b649-owner__tabs" role="tablist" aria-label="B649 ticket count">
        <button
          v-for="value in B649_PREFIX_COUNTS"
          :key="value"
          type="button"
          role="tab"
          :aria-selected="ticketCount === value"
          :class="{ 'is-active': ticketCount === value }"
          @click="selectTicketCount(value)"
        >
          {{ value }} Tickets
        </button>
        <p>Ticket counts are compared independently; there is no cross-ticket overall ranking.</p>
      </div>

      <section class="owner-summary-grid" aria-label="B649 owner summary">
        <article class="owner-summary-card owner-summary-card--accent">
          <span class="eyebrow">Current view</span>
          <strong>{{ ticketCount }} Tickets</strong>
          <small>Viewing R2 evidence for this ticket count only.</small>
        </article>
        <article class="owner-summary-card">
          <span class="eyebrow">Official criterion</span>
          <strong>OFFICIAL_ANY_PRIZE</strong>
          <small>Any official prize tier match counts as an official win.</small>
        </article>
        <article class="owner-summary-card">
          <span class="eyebrow">Metric-bearing</span>
          <strong>{{ data.summary.metrics_available_strategy_count ?? '—' }}</strong>
          <small>The 133-strategy universe forming official rankings in R2.</small>
        </article>
        <article class="owner-summary-card">
          <span class="eyebrow">Window semantics</span>
          <strong>FULL ≠ Long-Term</strong>
          <small>750 / 300 / 50 are the long-, mid-, and short-term regime observations.</small>
        </article>
      </section>

      <section class="owner-section" aria-labelledby="owner-observation-title">
        <div class="owner-section__heading">
          <div>
            <p class="eyebrow">First-screen decision summary</p>
            <h2 id="owner-observation-title">Core Observation</h2>
          </div>
          <span class="section-note">Evaluate evidence before rank</span>
        </div>
        <div class="owner-card-grid">
          <article class="owner-panel owner-panel--leader">
            <div class="owner-panel__heading">
              <div>
                <p class="eyebrow">RECENT_50</p>
                <h3>Short-Term Leaders</h3>
              </div>
              <span class="window-chip">50 · Short-Term</span>
            </div>
            <div v-if="shortTermRankLeader" class="leader-block">
              <span class="metric-label">official rank leader</span>
              <strong>{{ shortTermRankLeader.strategy_id }}</strong>
              <div class="metric-line">
                <span>{{ formatRank(shortTermRankLeader) }}</span>
                <span>{{ formatRate(shortTermRankLeader.official_any_prize_rate) }}</span>
                <span>{{ formatObservations(shortTermRankLeader) }} Obs.</span>
                <span>{{ formatRate(shortTermRankLeader.coverage) }} cov</span>
              </div>
              <span
                v-for="badge in warningBadges(shortTermRankLeader)"
                :key="badge"
                class="warning-badge"
              >{{ badge }}</span>
            </div>
            <div v-if="highCoverageLeader" class="leader-block leader-block--comparison">
              <span class="metric-label">high-coverage comparison</span>
              <strong>{{ highCoverageLeader.strategy_id }}</strong>
              <div class="metric-line">
                <span>{{ formatRank(highCoverageLeader) }}</span>
                <span>{{ formatRate(highCoverageLeader.official_any_prize_rate) }}</span>
                <span>{{ formatObservations(highCoverageLeader) }} Obs.</span>
                <span>{{ formatRate(highCoverageLeader.coverage) }} cov</span>
              </div>
              <small>{{ highCoverageDefinition.note }}</small>
            </div>
          </article>

          <article class="owner-panel">
            <div class="owner-panel__heading">
              <div>
                <p class="eyebrow">R2 source-derived set</p>
                <h3>Core Strategies</h3>
              </div>
            </div>
            <ul class="compact-list">
              <li v-for="item in coreObservationRows" :key="item.metadata.strategyToken">
                <div>
                  <strong>{{ item.metadata.label }}</strong>
                  <small>{{ item.metadata.recentDirection }}</small>
                </div>
                <span class="compact-metric">
                  {{ formatRank(item.record) }} · {{ formatRate(item.record?.official_any_prize_rate ?? null) }}
                </span>
              </li>
            </ul>
          </article>

          <article class="owner-panel">
            <div class="owner-panel__heading">
              <div>
                <p class="eyebrow">Four-window Top 20</p>
                <h3>Stable Strategies</h3>
              </div>
              <span class="section-note">stable ≠ guaranteed</span>
            </div>
            <ul class="compact-list">
              <li v-for="item in stableRows" :key="item.metadata.strategyToken">
                <div>
                  <strong>{{ item.metadata.label }}</strong>
                  <small>{{ item.metadata.recentDirection }}</small>
                </div>
                <span class="role-badge role-badge--stable_core">STABLE_CORE</span>
              </li>
            </ul>
          </article>

          <article class="owner-panel owner-panel--warning">
            <div class="owner-panel__heading">
              <div>
                <p class="eyebrow">Evidence warnings</p>
                <h3>Rank ≠ Evidence Strength</h3>
              </div>
            </div>
            <ul class="warning-list">
              <li v-for="warning in warningRows" :key="warning.badge">
                <span class="warning-badge">{{ warning.badge }}</span>
                <strong>{{ warning.title }}</strong>
                <p>{{ warning.detail }}</p>
              </li>
            </ul>
          </article>

          <article class="owner-panel owner-panel--regime">
            <div class="owner-panel__heading">
              <div>
                <p class="eyebrow">Descriptive only</p>
                <h3>REGIME Candidates</h3>
              </div>
              <span class="role-badge role-badge--recent_mover">RESEARCH</span>
            </div>
            <p class="owner-panel__copy">These are exploratory research candidates identified by R2, not production recommendations.</p>
            <div class="tag-list">
              <span v-for="candidate in R2_REGIME_CANDIDATES[ticketCount]" :key="candidate">{{ candidate }}</span>
            </div>
          </article>
        </div>
      </section>

      <section class="owner-section" aria-labelledby="evidence-strength-title">
        <div class="owner-section__heading">
          <div>
            <p class="eyebrow">Evidence strength</p>
            <h2 id="evidence-strength-title">Joint Evaluation: Rank, Observations, Coverage & Delta</h2>
          </div>
          <span class="section-note">Official rank is preserved without UI modification</span>
        </div>
        <div class="evidence-compare-grid">
          <article v-for="item in evidenceComparisons" :key="item.label" class="evidence-card">
            <div class="evidence-card__heading">
              <h3>{{ item.label }}</h3>
              <span v-if="item.record" :class="roleClass(item.label === 'quick_ml_predict' ? 'LOW_COVERAGE_CONTROL' : 'STABLE_CORE')">
                {{ item.label === 'quick_ml_predict' ? 'LOW_COVERAGE_CONTROL' : 'BROAD-COVERAGE CONTROL' }}
              </span>
            </div>
            <p>{{ item.caption }}</p>
            <dl class="metric-grid">
              <div><dt>FULL rank</dt><dd>{{ formatRank(item.record) }}</dd></div>
              <div><dt>rate</dt><dd>{{ formatRate(item.record?.official_any_prize_rate ?? null) }}</dd></div>
              <div><dt>Obs.</dt><dd>{{ formatObservations(item.record) }}</dd></div>
              <div><dt>coverage</dt><dd>{{ formatRate(item.record?.coverage ?? null) }}</dd></div>
              <div><dt>delta</dt><dd>{{ formatDelta(item.record?.official_random_baseline_delta ?? null) }}</dd></div>
            </dl>
          </article>
        </div>
      </section>

      <section class="owner-section" aria-labelledby="baseline-title">
        <div class="owner-section__heading">
          <div>
            <p class="eyebrow">Random baseline snapshot</p>
            <h2 id="baseline-title">Top 20 Strategies Outperforming Random Baseline</h2>
          </div>
          <span class="section-note">Descriptive comparison, not future win rate</span>
        </div>
        <div class="owner-table-scroll" role="region" aria-label="Random baseline snapshot table" tabindex="0">
          <table class="owner-table baseline-table">
            <caption>R2 source-derived baseline comparison displayed by ticket count.</caption>
            <thead>
              <tr><th scope="col">Ticket</th><th scope="col">FULL</th><th scope="col">750</th><th scope="col">300</th><th scope="col">50</th></tr>
            </thead>
            <tbody>
              <tr v-for="value in B649_PREFIX_COUNTS" :key="value" :class="{ 'is-current': value === ticketCount }">
                <th scope="row">{{ value }} Tickets</th>
                <td>{{ R2_BASELINE_SNAPSHOT[value].full }}</td>
                <td>{{ R2_BASELINE_SNAPSHOT[value].recent750 }}</td>
                <td>{{ R2_BASELINE_SNAPSHOT[value].recent300 }}</td>
                <td>{{ R2_BASELINE_SNAPSHOT[value].recent50 }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="owner-section" aria-labelledby="decision-matrix-title">
        <div class="owner-section__heading">
          <div>
            <p class="eyebrow">Owner Decision Matrix</p>
            <h2 id="decision-matrix-title">R2 Shortlist · {{ ticketCount }} Tickets</h2>
          </div>
          <span class="section-note">Coverage, Obs., and Delta fully disclosed</span>
        </div>
        <div class="owner-table-scroll" role="region" aria-label="B649 Owner Decision Matrix table" tabindex="0">
          <table class="owner-table decision-table">
            <caption>Research labels are descriptive and do not alter official rank or strategy lifecycle.</caption>
            <thead>
              <tr>
                <th scope="col">Strategy</th><th scope="col">750 rank</th><th scope="col">300 rank</th><th scope="col">50 rank</th>
                <th scope="col">750 rate</th><th scope="col">300 rate</th><th scope="col">50 rate</th>
                <th scope="col">Coverage F/750/300/50</th><th scope="col">FULL Obs.</th><th scope="col">FULL Δ</th>
                <th scope="col">Stability</th><th scope="col">Recent direction</th><th scope="col">Research role</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in matrixRows" :key="`${item.definition.prefixCount}-${item.definition.strategyToken}`">
                <th scope="row">
                  <strong>{{ item.definition.label }}</strong>
                  <small>{{ item.full?.method_family ?? '—' }}</small>
                </th>
                <td>{{ formatRank(item.recent750) }}</td><td>{{ formatRank(item.recent300) }}</td><td>{{ formatRank(item.recent50) }}</td>
                <td>{{ formatRate(item.recent750?.official_any_prize_rate ?? null) }}</td>
                <td>{{ formatRate(item.recent300?.official_any_prize_rate ?? null) }}</td>
                <td>{{ formatRate(item.recent50?.official_any_prize_rate ?? null) }}</td>
                <td>{{ formatRate(item.full?.coverage ?? null) }} / {{ formatRate(item.recent750?.coverage ?? null) }} / {{ formatRate(item.recent300?.coverage ?? null) }} / {{ formatRate(item.recent50?.coverage ?? null) }}</td>
                <td>{{ formatObservations(item.full) }}</td>
                <td>{{ formatDelta(item.full?.official_random_baseline_delta ?? null) }}</td>
                <td>{{ formatRank(item.full) }}/{{ formatRank(item.recent750) }}/{{ formatRank(item.recent300) }}/{{ formatRank(item.recent50) }}</td>
                <td>{{ item.definition.recentDirection }}</td>
                <td><span :class="roleClass(item.definition.role)">{{ item.definition.role }}</span></td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="owner-section" aria-labelledby="ranking-detail-title">
        <div class="owner-section__heading">
          <div>
            <p class="eyebrow">Ranking detail</p>
            <h2 id="ranking-detail-title">{{ ticketCount }} Tickets · Top 20</h2>
          </div>
          <div class="window-tabs" role="tablist" aria-label="B649 ranking windows">
            <button
              v-for="window in B649_HISTORY_WINDOWS"
              :key="window"
              type="button"
              role="tab"
              :aria-selected="detailWindow === window"
              :class="{ 'is-active': detailWindow === window }"
              @click="detailWindow = window"
            >
              {{ window === 'FULL' ? 'FULL' : window.replace('RECENT_', '') }}
            </button>
          </div>
        </div>
        <p class="window-explanation">{{ formatWindow(detailWindow) }}. Ranking follows official_rank in data without composite scoring.</p>
        <div class="owner-table-scroll" role="region" aria-label="B649 ranking detail table" tabindex="0">
          <table class="owner-table ranking-table">
            <caption>Official ranking detail；rare high-prize occurrence remains a secondary research dimension。</caption>
            <thead>
              <tr><th scope="col">Rank</th><th scope="col">Strategy / family</th><th scope="col">Official rate</th><th scope="col">Random baseline</th><th scope="col">Delta</th><th scope="col">Coverage</th><th scope="col">Obs.</th><th scope="col">Warnings</th></tr>
            </thead>
            <tbody>
              <tr v-for="record in detailRows" :key="record.strategy_id">
                <td><strong>{{ formatRank(record) }}</strong></td>
                <th scope="row"><strong>{{ record.strategy_id }}</strong><small>{{ record.method_family }}</small></th>
                <td>{{ formatRate(record.official_any_prize_rate) }}</td>
                <td>{{ formatRate(record.official_random_baseline_probability) }}</td>
                <td>{{ formatDelta(record.official_random_baseline_delta) }}</td>
                <td>{{ formatRate(record.coverage) }}</td>
                <td>{{ formatObservations(record) }}</td>
                <td>
                  <span v-if="warningBadges(record).length === 0">—</span>
                  <span v-for="badge in warningBadges(record)" v-else :key="badge" class="warning-badge">{{ badge }}</span>
                </td>
              </tr>
              <tr v-if="detailRows.length === 0"><td colspan="8">No ranking rows available for this window; data is not synthesized.</td></tr>
            </tbody>
          </table>
        </div>
      </section>

      <footer class="owner-footer-note">
        Support robustness remains designated <code>PROVISIONAL_SELF_VALIDATED_RESEARCH</code>; rare high-prize occurrence ≠ stable predictive edge.
      </footer>
    </template>
  </section>
</template>
