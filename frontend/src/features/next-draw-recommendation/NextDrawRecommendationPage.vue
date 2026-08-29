<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import {
  NATIVE_TICKET_COUNT_BUCKETS,
  getNextDrawRecommendation,
  getNextDrawRecommendationLifecycle,
  type NativeTicketCount,
  type NextDrawRecommendationLifecycleResponse,
  type NextDrawRecommendationResponse,
  type RecommendationCandidateView,
  type SealedTicketSetView,
} from '../../api/nextDrawRecommendation'

type LoadState = 'loading' | 'ready' | 'error'

const nativeTicketCount = ref<NativeTicketCount>(2)
const data = ref<NextDrawRecommendationResponse | null>(null)
const loadState = ref<LoadState>('loading')
const errorMessage = ref('')
const showFullRanking = ref(false)
let controller: AbortController | null = null
let generation = 0

const lifecycle = ref<NextDrawRecommendationLifecycleResponse | null>(null)
const lifecycleLoadState = ref<LoadState>('loading')
let lifecycleController: AbortController | null = null

const WINDOW_LABELS: Record<string, string> = {
  WINDOW_50: 'Last 50',
  WINDOW_300: 'Last 300',
  WINDOW_750: 'Last 750',
}

const AVAILABILITY_LABELS: Record<string, string> = {
  AVAILABLE: 'Sufficient candidate pool',
  LIMITED_POOL: 'Small candidate pool · showing every candidate',
  UNAVAILABLE: 'No strategy natively produces this ticket count',
}

const LIFECYCLE_LABELS: Record<string, string> = {
  WAITING_FOR_ELIGIBLE_TARGET: 'Waiting for next draw',
  TARGET_AVAILABLE: 'Target available · not sealed yet',
  PREDICTIONS_SEALED: 'Predictions sealed',
  OUTCOME_AVAILABLE: 'Outcome available',
}

const LIFECYCLE_DESCRIPTIONS: Record<string, string> = {
  WAITING_FOR_ELIGIBLE_TARGET:
    'No upcoming draw is currently eligible for sealing. The tickets below remain a live, unsealed preview.',
  TARGET_AVAILABLE:
    'A future draw is eligible for sealing, but no predictions have been sealed against it yet. The tickets below remain a live, unsealed preview.',
  PREDICTIONS_SEALED:
    'Predictions were frozen and durably sealed against the target draw below before it was drawn.',
  OUTCOME_AVAILABLE:
    'The target draw this seal was bound to has now completed. Sealed predictions are shown below; scoring is a separate, later step.',
}

const MEDALS = ['🥇', '🥈', '🥉']

async function load(): Promise<void> {
  controller?.abort()
  controller = new AbortController()
  const requestGeneration = ++generation
  loadState.value = 'loading'
  errorMessage.value = ''
  try {
    const response = await getNextDrawRecommendation(nativeTicketCount.value, controller.signal)
    if (requestGeneration !== generation) return
    data.value = response
    loadState.value = 'ready'
  } catch (error) {
    if (requestGeneration !== generation) return
    if (error instanceof DOMException && error.name === 'AbortError') return
    data.value = null
    loadState.value = 'error'
    errorMessage.value = error instanceof Error ? error.message : String(error)
  }
}

async function loadLifecycle(): Promise<void> {
  lifecycleController?.abort()
  lifecycleController = new AbortController()
  lifecycleLoadState.value = 'loading'
  try {
    const response = await getNextDrawRecommendationLifecycle(lifecycleController.signal)
    lifecycle.value = response
    lifecycleLoadState.value = 'ready'
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') return
    lifecycle.value = null
    lifecycleLoadState.value = 'error'
  }
}

watch(nativeTicketCount, () => {
  showFullRanking.value = false
  void load()
})
onMounted(() => {
  void load()
  // The lifecycle/seal state does not depend on the selected ticket-count
  // tab -- one seal covers every supported bucket -- so it loads once.
  void loadLifecycle()
})
onBeforeUnmount(() => {
  controller?.abort()
  lifecycleController?.abort()
})

// Never pad to a fixed card count: a bucket with two eligible strategies
// shows exactly two cards rather than inventing a third.
const topCandidates = computed(() => data.value?.ranked.slice(0, 3) ?? [])
const remainingCandidates = computed(() => data.value?.ranked.slice(3) ?? [])

const isSealed = computed(
  () =>
    lifecycle.value?.lifecycle_state === 'PREDICTIONS_SEALED' ||
    lifecycle.value?.lifecycle_state === 'OUTCOME_AVAILABLE',
)

const sealedBucket = computed(() => {
  if (!isSealed.value || !lifecycle.value) return null
  return (
    lifecycle.value.sealed_buckets.find(
      (bucket) => bucket.native_ticket_count === nativeTicketCount.value,
    ) ?? null
  )
})

function sealedTicketFor(strategyId: string): SealedTicketSetView | null {
  return sealedBucket.value?.sealed_tickets.find((ticket) => ticket.strategy_id === strategyId) ?? null
}

function windowMetric(candidate: RecommendationCandidateView, windowKind: string) {
  return candidate.windows.find((window) => window.window_kind === windowKind) ?? null
}

function formatPercent(value: number | null): string {
  return value === null ? '—' : `${(value * 100).toFixed(2)}%`
}

function formatDelta(value: number | null): string {
  if (value === null) return '—'
  const pct = value * 100
  return `${pct >= 0 ? '+' : ''}${pct.toFixed(2)} pp`
}

function formatSealedTimestamp(value: string | null): string {
  if (!value) return '—'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return parsed.toLocaleString(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  })
}
</script>

<template>
  <section class="next-draw">
    <div class="page-heading">
      <div>
        <h1 id="next-draw-recommendation-title">Next Draw Recommendation</h1>
        <p class="preview-banner">
          <span class="preview-banner__tag">PREVIEW</span>
          <span>
            The ranking and "as of right now" tickets below are generated from causal history up
            to the latest completed draw. They are <strong>not bound or sealed to any future
            draw</strong>, and this page makes no prediction, probability, or future-performance
            claim.
          </span>
        </p>
        <p
          v-if="lifecycle"
          class="lifecycle-banner"
          :class="`lifecycle-banner--${lifecycle.lifecycle_state.toLowerCase()}`"
        >
          <span class="lifecycle-banner__tag">{{
            LIFECYCLE_LABELS[lifecycle.lifecycle_state] ?? lifecycle.lifecycle_state
          }}</span>
          <span>
            {{ LIFECYCLE_DESCRIPTIONS[lifecycle.lifecycle_state] }}
            <template v-if="lifecycle.target_draw_number">
              Target draw <strong>{{ lifecycle.target_draw_number }}</strong> ({{
                lifecycle.target_draw_date
              }}).
            </template>
            <template v-if="isSealed">
              Sealed {{ formatSealedTimestamp(lifecycle.sealed_at) }}.
            </template>
          </span>
        </p>
        <p v-else-if="lifecycleLoadState === 'error'" class="lifecycle-banner lifecycle-banner--error">
          <span class="lifecycle-banner__tag">Lifecycle unavailable</span>
          <span>The seal/target lifecycle status could not be loaded right now.</span>
        </p>
        <p class="page-intro">
          Under the <code>NEXT_DRAW_ROBUSTNESS_V1</code> policy, strategies are compared on the real
          backtested performance of their own native ticket output, within a single ticket-count
          bucket. The ranking is descriptive only: a higher rank never implies a proven edge.
        </p>
      </div>
    </div>

    <div class="ticket-selector" role="tablist" aria-label="Select native ticket count">
      <button
        v-for="count in NATIVE_TICKET_COUNT_BUCKETS"
        :key="count"
        type="button"
        class="button"
        :class="count === nativeTicketCount ? 'button--primary' : 'button--quiet'"
        role="tab"
        :aria-selected="count === nativeTicketCount"
        @click="nativeTicketCount = count"
      >
        {{ count }} {{ count === 1 ? 'ticket' : 'tickets' }}
      </button>
    </div>

    <p v-if="loadState === 'loading'" class="status-copy">Loading…</p>
    <p v-else-if="loadState === 'error'" class="status-copy status-copy--error">
      Failed to load: {{ errorMessage }}
    </p>

    <template v-else-if="data">
      <p class="availability-line" :class="`availability-line--${data.availability.toLowerCase()}`">
        {{ AVAILABILITY_LABELS[data.availability] ?? data.availability }}
        · {{ data.total_candidate_count }} candidate strategies
        <span v-if="data.excluded.length">
          · {{ data.excluded.length }} excluded for missing evidence or unreachable execution</span
        >
      </p>

      <p v-if="data.availability === 'UNAVAILABLE'" class="empty-copy">
        No strategy currently produces {{ data.native_ticket_count }} native tickets.
      </p>

      <div v-else class="candidate-grid">
        <article
          v-for="(candidate, index) in topCandidates"
          :key="candidate.strategy_id"
          class="candidate-card"
        >
          <header class="candidate-card__header">
            <span class="candidate-card__medal">{{ MEDALS[index] ?? `#${candidate.rank}` }}</span>
            <div>
              <h2>{{ candidate.strategy_name }}</h2>
              <p class="candidate-card__meta">
                #{{ candidate.rank }} · cross-window rank sum
                {{ candidate.cross_window_rank_sum ?? '—' }}
              </p>
            </div>
          </header>

          <table class="metric-table">
            <thead>
              <tr>
                <th scope="col">Window</th>
                <th scope="col">Observed</th>
                <th scope="col">Random baseline</th>
                <th scope="col">Δ</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="windowKind in ['WINDOW_50', 'WINDOW_300', 'WINDOW_750']" :key="windowKind">
                <td>{{ WINDOW_LABELS[windowKind] }}</td>
                <template v-if="windowMetric(candidate, windowKind)">
                  <td>{{ formatPercent(windowMetric(candidate, windowKind)!.observed_rate) }}</td>
                  <td>
                    {{ formatPercent(windowMetric(candidate, windowKind)!.random_baseline_rate) }}
                  </td>
                  <td
                    class="delta-cell"
                    :class="{
                      'delta-cell--positive':
                        (windowMetric(candidate, windowKind)!.delta_vs_random ?? 0) > 0,
                      'delta-cell--negative':
                        (windowMetric(candidate, windowKind)!.delta_vs_random ?? 0) < 0,
                    }"
                  >
                    {{ formatDelta(windowMetric(candidate, windowKind)!.delta_vs_random) }}
                  </td>
                </template>
                <template v-else>
                  <td colspan="3">Insufficient history</td>
                </template>
              </tr>
            </tbody>
          </table>

          <div v-if="isSealed && sealedTicketFor(candidate.strategy_id)" class="candidate-card__tickets">
            <p class="candidate-card__tickets-label candidate-card__tickets-label--sealed">
              🔒 Sealed tickets · frozen for draw {{ lifecycle?.target_draw_number }} on
              {{ lifecycle?.target_draw_date }} · sealed
              {{ formatSealedTimestamp(lifecycle?.sealed_at ?? null) }}
            </p>
            <template v-if="sealedTicketFor(candidate.strategy_id)?.status === 'OK'">
              <div
                v-for="(ticket, ticketIndex) in sealedTicketFor(candidate.strategy_id)?.tickets ?? []"
                :key="ticketIndex"
                class="ticket-row"
              >
                <span class="ticket-row__label">Ticket {{ ticketIndex + 1 }}</span>
                <span class="number-chips">
                  <span v-for="number in ticket" :key="number" class="number-chip">
                    {{ String(number).padStart(2, '0') }}
                  </span>
                </span>
              </div>
            </template>
            <p v-else class="ticket-row__unavailable">
              No tickets were sealed for this strategy ({{
                sealedTicketFor(candidate.strategy_id)?.status ?? 'UNKNOWN'
              }}<template v-if="sealedTicketFor(candidate.strategy_id)?.detail"
                >: {{ sealedTicketFor(candidate.strategy_id)?.detail }}</template
              >)
            </p>
          </div>
          <div v-else-if="isSealed" class="candidate-card__tickets">
            <p class="ticket-row__unavailable">
              This strategy was not among the sealed top candidates for this ticket count.
            </p>
          </div>
          <div v-else class="candidate-card__tickets">
            <p class="candidate-card__tickets-label">
              Preview tickets · generated now from causal history through draw
              {{ data.evidence_last_causal_draw_id }} · not sealed to a future draw
            </p>
            <template v-if="candidate.ticket_generation_status === 'OK' && candidate.tickets">
              <div
                v-for="(ticket, ticketIndex) in candidate.tickets"
                :key="ticketIndex"
                class="ticket-row"
              >
                <span class="ticket-row__label">Ticket {{ ticketIndex + 1 }}</span>
                <span class="number-chips">
                  <span v-for="number in ticket" :key="number" class="number-chip">
                    {{ String(number).padStart(2, '0') }}
                  </span>
                </span>
              </div>
            </template>
            <p v-else class="ticket-row__unavailable">
              No tickets could be generated ({{ candidate.ticket_generation_status ?? 'UNKNOWN' }}<template
                v-if="candidate.ticket_generation_detail"
                >: {{ candidate.ticket_generation_detail }}</template
              >)
            </p>
          </div>
        </article>
      </div>

      <button
        v-if="remainingCandidates.length || data.excluded.length"
        type="button"
        class="button button--quiet full-ranking-toggle"
        @click="showFullRanking = !showFullRanking"
      >
        {{
          showFullRanking
            ? 'Hide full ranking'
            : `View full ranking (${remainingCandidates.length} more + ${data.excluded.length} excluded)`
        }}
      </button>

      <div v-if="showFullRanking" class="full-ranking">
        <table v-if="remainingCandidates.length" class="owner-table">
          <thead>
            <tr>
              <th scope="col">Rank</th>
              <th scope="col">Strategy</th>
              <th scope="col">Δ last 50</th>
              <th scope="col">Δ last 300</th>
              <th scope="col">Δ last 750</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="candidate in remainingCandidates" :key="candidate.strategy_id">
              <td>#{{ candidate.rank }}</td>
              <td>{{ candidate.strategy_name }}</td>
              <td>
                {{ formatDelta(windowMetric(candidate, 'WINDOW_50')?.delta_vs_random ?? null) }}
              </td>
              <td>
                {{ formatDelta(windowMetric(candidate, 'WINDOW_300')?.delta_vs_random ?? null) }}
              </td>
              <td>
                {{ formatDelta(windowMetric(candidate, 'WINDOW_750')?.delta_vs_random ?? null) }}
              </td>
            </tr>
          </tbody>
        </table>

        <table v-if="data.excluded.length" class="owner-table excluded-table">
          <caption>Excluded strategies and reasons</caption>
          <thead>
            <tr>
              <th scope="col">Strategy ID</th>
              <th scope="col">Reason</th>
              <th scope="col">Detail</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="exclusion in data.excluded" :key="exclusion.strategy_id">
              <td>{{ exclusion.strategy_id }}</td>
              <td>{{ exclusion.reason }}</td>
              <td>{{ exclusion.detail }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <footer class="evidence-footer">
        <p>
          Recommendation status: <strong>{{ data.recommendation_status }}</strong>
          · Target binding: <strong>{{ data.target_binding }}</strong>
        </p>
        <p>
          Evidence status: <strong>{{ data.evidence_computation_status }}</strong>
          <template v-if="data.evidence_computation_status === 'FRESH_UNREVIEWED'">
            — this backtest evidence was freshly computed and has not been reviewed or adopted as a
            CANONICAL_CURRENT authority.
          </template>
        </p>
        <p class="evidence-footer__hash">
          artifact_sha256: <code>{{ data.evidence_artifact_sha256 }}</code>
          · hit_tier: {{ data.hit_tier_id }} · last causal draw recorded in evidence:
          {{ data.evidence_last_causal_draw_id }}
        </p>
      </footer>
    </template>
  </section>
</template>

<style scoped>
.next-draw {
  padding: 0 0 48px;
}

.preview-banner {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  margin: 12px 0;
  padding: 12px 14px;
  border: 1px solid var(--amber);
  border-radius: 10px;
  color: var(--ink);
  font-size: 13px;
  line-height: 1.5;
}

.preview-banner__tag {
  flex: none;
  padding: 2px 8px;
  border-radius: 6px;
  background: var(--amber);
  color: var(--surface);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
}

.lifecycle-banner {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  margin: 0 0 12px;
  padding: 12px 14px;
  border: 1px solid var(--line);
  border-radius: 10px;
  color: var(--ink);
  font-size: 13px;
  line-height: 1.5;
}

.lifecycle-banner__tag {
  flex: none;
  padding: 2px 8px;
  border-radius: 6px;
  background: var(--muted);
  color: var(--surface);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  white-space: nowrap;
}

.lifecycle-banner--target_available {
  border-color: var(--amber);
}

.lifecycle-banner--target_available .lifecycle-banner__tag {
  background: var(--amber);
}

.lifecycle-banner--predictions_sealed,
.lifecycle-banner--outcome_available {
  border-color: var(--mint);
}

.lifecycle-banner--predictions_sealed .lifecycle-banner__tag,
.lifecycle-banner--outcome_available .lifecycle-banner__tag {
  background: var(--mint);
}

.lifecycle-banner--error {
  border-color: var(--danger);
}

.lifecycle-banner--error .lifecycle-banner__tag {
  background: var(--danger);
}

.candidate-card__tickets-label--sealed {
  color: var(--mint);
  font-weight: 600;
}

.page-intro code {
  padding: 1px 6px;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: var(--surface-raised);
  color: var(--mint);
}

.ticket-selector {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 24px;
}

.status-copy {
  color: var(--muted);
}

.status-copy--error {
  color: var(--danger);
}

.availability-line {
  margin-bottom: 20px;
  color: var(--muted);
  font-size: 14px;
}

.availability-line--limited_pool {
  color: var(--amber);
}

.availability-line--unavailable {
  color: var(--danger);
}

.candidate-grid {
  display: grid;
  gap: 20px;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  margin-bottom: 20px;
}

.candidate-card {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 20px;
  border: 1px solid var(--line);
  border-radius: 16px;
  background: var(--surface-raised);
}

.candidate-card__header {
  display: flex;
  gap: 12px;
  align-items: flex-start;
}

.candidate-card__medal {
  font-size: 28px;
  line-height: 1;
}

.candidate-card__header h2 {
  margin: 0;
  font-size: 16px;
  color: var(--ink);
}

.candidate-card__meta {
  margin: 4px 0 0;
  color: var(--muted);
  font-size: 12px;
}

.metric-table {
  width: 100%;
  font-size: 13px;
  border-collapse: collapse;
}

.metric-table th,
.metric-table td {
  padding: 6px 8px;
  border-bottom: 1px solid var(--line);
  text-align: left;
}

.delta-cell--positive {
  color: var(--mint);
}

.delta-cell--negative {
  color: var(--danger);
}

.candidate-card__tickets {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding-top: 6px;
  border-top: 1px dashed var(--line);
}

.candidate-card__tickets-label {
  margin: 0;
  color: var(--muted);
  font-size: 11px;
  letter-spacing: 0.04em;
}

.ticket-row {
  display: flex;
  gap: 10px;
  align-items: center;
}

.ticket-row__label {
  min-width: 62px;
  color: var(--muted);
  font-size: 12px;
}

.ticket-row__unavailable {
  margin: 0;
  color: var(--danger);
  font-size: 12px;
}

.number-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.full-ranking-toggle {
  margin-bottom: 16px;
}

.full-ranking {
  display: flex;
  flex-direction: column;
  gap: 24px;
  margin-bottom: 24px;
}

.owner-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.owner-table th,
.owner-table td {
  padding: 8px 10px;
  border-bottom: 1px solid var(--line);
  text-align: left;
}

.excluded-table caption {
  margin-bottom: 8px;
  color: var(--muted);
  font-size: 12px;
  text-align: left;
}

.evidence-footer {
  padding-top: 16px;
  border-top: 1px solid var(--line);
  color: var(--muted);
  font-size: 12px;
}

.evidence-footer__hash code {
  font-family: 'SFMono-Regular', Consolas, monospace;
}
</style>
