<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import {
  NATIVE_TICKET_COUNT_BUCKETS,
  getNextDrawRecommendation,
  type NativeTicketCount,
  type NextDrawRecommendationResponse,
  type RecommendationCandidateView,
} from '../../api/nextDrawRecommendation'

type LoadState = 'loading' | 'ready' | 'error'

const nativeTicketCount = ref<NativeTicketCount>(2)
const data = ref<NextDrawRecommendationResponse | null>(null)
const loadState = ref<LoadState>('loading')
const errorMessage = ref('')
const showFullRanking = ref(false)
let controller: AbortController | null = null
let generation = 0

const WINDOW_LABELS: Record<string, string> = {
  WINDOW_50: '50 期',
  WINDOW_300: '300 期',
  WINDOW_750: '750 期',
}

const AVAILABILITY_LABELS: Record<string, string> = {
  AVAILABLE: '候選充足',
  LIMITED_POOL: '候選池較小 · 顯示全部',
  UNAVAILABLE: '目前無此注數策略',
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

watch(nativeTicketCount, () => {
  showFullRanking.value = false
  void load()
})
onMounted(() => void load())
onBeforeUnmount(() => controller?.abort())

const topCandidates = computed(() => data.value?.ranked.slice(0, 3) ?? [])
const remainingCandidates = computed(() => data.value?.ranked.slice(3) ?? [])

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
</script>

<template>
  <section class="next-draw">
    <div class="page-heading">
      <div>
        <h1>大樂透｜下一期推薦</h1>
        <p class="page-intro">
          依 <code>NEXT_DRAW_ROBUSTNESS_V1</code> 政策，在同一注數下比較各策略「自身原生投注」的真實回測表現。
          排名是描述性結果，不是未來中獎的保證或機率主張。
        </p>
      </div>
    </div>

    <div class="ticket-selector" role="tablist" aria-label="選擇注數">
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
        {{ count }} 注
      </button>
    </div>

    <p v-if="loadState === 'loading'" class="status-copy">載入中…</p>
    <p v-else-if="loadState === 'error'" class="status-copy status-copy--error">
      載入失敗：{{ errorMessage }}
    </p>

    <template v-else-if="data">
      <p class="availability-line" :class="`availability-line--${data.availability.toLowerCase()}`">
        {{ AVAILABILITY_LABELS[data.availability] ?? data.availability }}
        · 候選策略 {{ data.total_candidate_count }} 個
        <span v-if="data.excluded.length"> · {{ data.excluded.length }} 個因缺乏證據或無法執行而排除</span>
      </p>

      <p v-if="data.availability === 'UNAVAILABLE'" class="empty-copy">
        目前沒有原生 {{ data.native_ticket_count }} 注的策略。
      </p>

      <div v-else class="candidate-grid">
        <article v-for="(candidate, index) in topCandidates" :key="candidate.strategy_id" class="candidate-card">
          <header class="candidate-card__header">
            <span class="candidate-card__medal">{{ MEDALS[index] ?? `#${candidate.rank}` }}</span>
            <div>
              <h2>{{ candidate.strategy_name }}</h2>
              <p class="candidate-card__meta">
                #{{ candidate.rank }} · 跨窗口排名分數 {{ candidate.cross_window_rank_sum ?? '—' }}
              </p>
            </div>
          </header>

          <table class="metric-table">
            <thead>
              <tr>
                <th scope="col">窗口</th>
                <th scope="col">觀察值</th>
                <th scope="col">隨機基準</th>
                <th scope="col">Δ</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="windowKind in ['WINDOW_50', 'WINDOW_300', 'WINDOW_750']" :key="windowKind">
                <td>{{ WINDOW_LABELS[windowKind] }}</td>
                <template v-if="windowMetric(candidate, windowKind)">
                  <td>{{ formatPercent(windowMetric(candidate, windowKind)!.observed_rate) }}</td>
                  <td>{{ formatPercent(windowMetric(candidate, windowKind)!.random_baseline_rate) }}</td>
                  <td
                    class="delta-cell"
                    :class="{
                      'delta-cell--positive': (windowMetric(candidate, windowKind)!.delta_vs_random ?? 0) > 0,
                      'delta-cell--negative': (windowMetric(candidate, windowKind)!.delta_vs_random ?? 0) < 0,
                    }"
                  >
                    {{ formatDelta(windowMetric(candidate, windowKind)!.delta_vs_random) }}
                  </td>
                </template>
                <template v-else>
                  <td colspan="3">歷史不足</td>
                </template>
              </tr>
            </tbody>
          </table>

          <div class="candidate-card__tickets">
            <p class="candidate-card__tickets-label">
              目前投注建議（以最新 {{ data.evidence_last_causal_draw_id }} 期為止的因果歷史即時產生）
            </p>
            <template v-if="candidate.ticket_generation_status === 'OK' && candidate.tickets">
              <div v-for="(ticket, ticketIndex) in candidate.tickets" :key="ticketIndex" class="ticket-row">
                <span class="ticket-row__label">第 {{ ticketIndex + 1 }} 注</span>
                <span class="number-chips">
                  <span v-for="number in ticket" :key="number" class="number-chip">
                    {{ String(number).padStart(2, '0') }}
                  </span>
                </span>
              </div>
            </template>
            <p v-else class="ticket-row__unavailable">
              尚無法產生投注號碼（{{ candidate.ticket_generation_status ?? 'UNKNOWN' }}<template v-if="candidate.ticket_generation_detail">：{{ candidate.ticket_generation_detail }}</template>）
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
        {{ showFullRanking ? '收合完整排名' : `查看完整排名（其餘 ${remainingCandidates.length} 個 + ${data.excluded.length} 個已排除）` }}
      </button>

      <div v-if="showFullRanking" class="full-ranking">
        <table v-if="remainingCandidates.length" class="owner-table">
          <thead>
            <tr>
              <th scope="col">排名</th>
              <th scope="col">策略</th>
              <th scope="col">50期 Δ</th>
              <th scope="col">300期 Δ</th>
              <th scope="col">750期 Δ</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="candidate in remainingCandidates" :key="candidate.strategy_id">
              <td>#{{ candidate.rank }}</td>
              <td>{{ candidate.strategy_name }}</td>
              <td>{{ formatDelta(windowMetric(candidate, 'WINDOW_50')?.delta_vs_random ?? null) }}</td>
              <td>{{ formatDelta(windowMetric(candidate, 'WINDOW_300')?.delta_vs_random ?? null) }}</td>
              <td>{{ formatDelta(windowMetric(candidate, 'WINDOW_750')?.delta_vs_random ?? null) }}</td>
            </tr>
          </tbody>
        </table>

        <table v-if="data.excluded.length" class="owner-table excluded-table">
          <caption>已排除策略與原因</caption>
          <thead>
            <tr>
              <th scope="col">策略 ID</th>
              <th scope="col">原因</th>
              <th scope="col">說明</th>
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
          Evidence status: <strong>{{ data.evidence_computation_status }}</strong>
          <template v-if="data.evidence_computation_status === 'FRESH_UNREVIEWED'">
            — 此回測證據為本次新產生的計算結果，尚未經過人工審查/正式採用為 CANONICAL_CURRENT 權威來源。
          </template>
        </p>
        <p class="evidence-footer__hash">
          artifact_sha256: <code>{{ data.evidence_artifact_sha256 }}</code>
          · hit_tier: {{ data.hit_tier_id }}
          · 最新已收錄開獎期別: {{ data.evidence_last_causal_draw_id }}
        </p>
      </footer>
    </template>
  </section>
</template>

<style scoped>
.next-draw {
  padding: 0 0 48px;
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
  min-width: 56px;
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
