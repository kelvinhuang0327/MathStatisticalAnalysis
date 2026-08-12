<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import {
  B649AnalyticsRequestError,
  fetchB649CombinationSummary,
  fetchB649Combinations,
  fetchB649EvidenceStatus,
  fetchB649StrategyK,
  fetchB649StrategyKSummary,
  type B649CombinationCriterion,
  type B649CombinationPage,
  type B649CombinationProxyMode,
  type B649CombinationSort,
  type B649CombinationSummary,
  type B649CombinationWindow,
  type B649EvidenceStatus,
  type B649StrategyAvailability,
  type B649StrategyKCriterion,
  type B649StrategyKPage,
  type B649StrategyKSort,
  type B649StrategyKSummary,
  type B649StrategyKWindowKind,
} from '../../api/b649StrategyKCombinations'

type Tab = 'strategy-k' | 'combinations' | 'evidence'
type LoadState = 'loading' | 'success' | 'empty' | 'unavailable' | 'error'
type QueryState = 'idle' | LoadState

const activeTab = ref<Tab>('strategy-k')
const strategySummaryState = ref<LoadState>('loading')
const strategySummary = ref<B649StrategyKSummary | null>(null)
const strategySummaryMessage = ref('')
const strategyQueryState = ref<QueryState>('idle')
const strategyPage = ref<B649StrategyKPage | null>(null)
const strategyQueryMessage = ref('')
const requestedK = ref<number | ''>('')
const strategyWindow = ref<B649StrategyKWindowKind | ''>('')
const strategyCriterion = ref<B649StrategyKCriterion | ''>('')
const strategySort = ref<B649StrategyKSort>('STRATEGY_ID_ASC')
const strategySearch = ref('')
const availabilitySearch = ref('')
const availabilityFilter = ref<'ALL' | B649StrategyAvailability>('ALL')

const combinationSummaryState = ref<LoadState>('loading')
const combinationSummary = ref<B649CombinationSummary | null>(null)
const combinationSummaryMessage = ref('')
const combinationQueryState = ref<QueryState>('idle')
const combinationPage = ref<B649CombinationPage | null>(null)
const combinationQueryMessage = ref('')
const proxyMode = ref<B649CombinationProxyMode | ''>('')
const memberCount = ref<2 | 3 | ''>('')
const combinationWindow = ref<B649CombinationWindow | ''>('')
const combinationCriterion = ref<B649CombinationCriterion | ''>('')
const combinationSort = ref<B649CombinationSort>('SEALED_RANK_ASC')
const memberSearch = ref('')

const evidenceState = ref<LoadState>('loading')
const evidence = ref<B649EvidenceStatus | null>(null)
const evidenceMessage = ref('')

let mounted = true
let strategySummaryController: AbortController | undefined
let strategyQueryController: AbortController | undefined
let combinationSummaryController: AbortController | undefined
let combinationQueryController: AbortController | undefined
let evidenceController: AbortController | undefined
let strategyGeneration = 0
let combinationGeneration = 0

const displayedStrategies = computed(() => {
  const search = availabilitySearch.value.trim().toLocaleLowerCase()
  return (strategySummary.value?.strategies ?? []).filter(
    (strategy) =>
      (availabilityFilter.value === 'ALL' || strategy.availability === availabilityFilter.value) &&
      (!search || strategy.strategy_id.toLocaleLowerCase().includes(search)),
  )
})

const canQueryStrategy = computed(
  () => requestedK.value !== '' && strategyWindow.value !== '' && strategyCriterion.value !== '',
)
const canQueryCombination = computed(
  () =>
    proxyMode.value !== '' &&
    memberCount.value !== '' &&
    combinationWindow.value !== '' &&
    combinationCriterion.value !== '',
)

async function loadStrategySummary(): Promise<void> {
  strategySummaryController?.abort()
  const controller = new AbortController()
  strategySummaryController = controller
  strategySummaryState.value = 'loading'
  strategySummaryMessage.value = ''
  try {
    const summary = await fetchB649StrategyKSummary(controller.signal)
    if (!mounted || controller.signal.aborted) return
    strategySummary.value = summary
    strategySummaryState.value = summary.strategies.length ? 'success' : 'empty'
    const primary = summary.windows.find((window) => window.default_emphasis)
    if (primary) strategyWindow.value = primary.window_kind as B649StrategyKWindowKind
  } catch (error) {
    if (!mounted || isAbort(error)) return
    strategySummary.value = null
    strategySummaryState.value = stateFor(error)
    strategySummaryMessage.value = messageFor(error)
  }
}

async function queryStrategy(offset = 0): Promise<void> {
  if (!canQueryStrategy.value) return
  strategyQueryController?.abort()
  const controller = new AbortController()
  strategyQueryController = controller
  const generation = ++strategyGeneration
  strategyQueryState.value = 'loading'
  strategyQueryMessage.value = ''
  try {
    const page = await fetchB649StrategyK(
      {
        requestedK: requestedK.value as number,
        windowKind: strategyWindow.value as B649StrategyKWindowKind,
        criterion: strategyCriterion.value as B649StrategyKCriterion,
        q: strategySearch.value.trim() || undefined,
        sort: strategySort.value,
        limit: 25,
        offset,
      },
      controller.signal,
    )
    if (!mounted || generation !== strategyGeneration) return
    strategyPage.value = page
    strategyQueryState.value = page.items.length ? 'success' : 'empty'
  } catch (error) {
    if (!mounted || generation !== strategyGeneration || isAbort(error)) return
    strategyPage.value = null
    strategyQueryState.value = stateFor(error)
    strategyQueryMessage.value = messageFor(error)
  }
}

async function loadCombinationSummary(): Promise<void> {
  combinationSummaryController?.abort()
  const controller = new AbortController()
  combinationSummaryController = controller
  combinationSummaryState.value = 'loading'
  combinationSummaryMessage.value = ''
  try {
    const summary = await fetchB649CombinationSummary(controller.signal)
    if (!mounted || controller.signal.aborted) return
    combinationSummary.value = summary
    combinationSummaryState.value = summary.sealed_top_candidate_count ? 'success' : 'empty'
    const primary = summary.windows.find((window) => window.default_emphasis)
    if (primary) combinationWindow.value = primary.window_kind as B649CombinationWindow
  } catch (error) {
    if (!mounted || isAbort(error)) return
    combinationSummary.value = null
    combinationSummaryState.value = stateFor(error)
    combinationSummaryMessage.value = messageFor(error)
  }
}

async function queryCombination(offset = 0): Promise<void> {
  if (!canQueryCombination.value) return
  combinationQueryController?.abort()
  const controller = new AbortController()
  combinationQueryController = controller
  const generation = ++combinationGeneration
  combinationQueryState.value = 'loading'
  combinationQueryMessage.value = ''
  try {
    const page = await fetchB649Combinations(
      {
        proxyMode: proxyMode.value as B649CombinationProxyMode,
        memberCount: memberCount.value as 2 | 3,
        window: combinationWindow.value as B649CombinationWindow,
        criterion: combinationCriterion.value as B649CombinationCriterion,
        memberSearch: memberSearch.value.trim() || undefined,
        sort: combinationSort.value,
        limit: 25,
        offset,
      },
      controller.signal,
    )
    if (!mounted || generation !== combinationGeneration) return
    combinationPage.value = page
    combinationQueryState.value = page.items.length ? 'success' : 'empty'
  } catch (error) {
    if (!mounted || generation !== combinationGeneration || isAbort(error)) return
    combinationPage.value = null
    combinationQueryState.value = stateFor(error)
    combinationQueryMessage.value = messageFor(error)
  }
}

async function loadEvidence(): Promise<void> {
  evidenceController?.abort()
  const controller = new AbortController()
  evidenceController = controller
  evidenceState.value = 'loading'
  evidenceMessage.value = ''
  try {
    const status = await fetchB649EvidenceStatus(controller.signal)
    if (!mounted || controller.signal.aborted) return
    evidence.value = status
    evidenceState.value = 'success'
  } catch (error) {
    if (!mounted || isAbort(error)) return
    evidence.value = null
    evidenceState.value = stateFor(error)
    evidenceMessage.value = messageFor(error)
  }
}

function stateFor(error: unknown): 'unavailable' | 'error' {
  return error instanceof B649AnalyticsRequestError && error.kind === 'UNAVAILABLE'
    ? 'unavailable'
    : 'error'
}

function messageFor(error: unknown): string {
  return error instanceof Error ? error.message : 'Unknown request failure.'
}

function isAbort(error: unknown): boolean {
  return error instanceof DOMException && error.name === 'AbortError'
}

function percent(numerator: number, denominator: number): string {
  return denominator > 0 ? `${((numerator / denominator) * 100).toFixed(4)}%` : '—'
}

function decimalPercent(value: string): string {
  return `${(Number(value) * 100).toFixed(4)}%`
}

function signedPoints(value: string): string {
  const points = Number(value) * 100
  return `${points >= 0 ? '+' : ''}${points.toFixed(4)} pp`
}

function effectiveKText(record: B649StrategyKPage['items'][number]): string {
  return record.effective_unique_k_counts
    .map((item) => `K${item.effective_unique_k} × ${item.observation_count}`)
    .join(' · ')
}

function windowText(window: { window_kind: string; window_role: string; requested_draw_count: number | null }): string {
  const draws = window.requested_draw_count === null ? '全部歷史' : `${window.requested_draw_count} 期`
  return `${window.window_kind} · ${draws} · ${window.window_role}`
}

onMounted(() => {
  void loadStrategySummary()
  void loadCombinationSummary()
  void loadEvidence()
})

onBeforeUnmount(() => {
  mounted = false
  strategySummaryController?.abort()
  strategyQueryController?.abort()
  combinationSummaryController?.abort()
  combinationQueryController?.abort()
  evidenceController?.abort()
})
</script>

<template>
  <section class="b649-analytics-page" aria-labelledby="b649-analytics-title">
    <header class="analytics-hero">
      <div>
        <p class="analytics-eyebrow">Sealed evidence · read only</p>
        <h1 id="b649-analytics-title">B649 Strategy × K 與策略組合</h1>
        <p>
          直接讀取封存研究矩陣、pair/triple 歷史 Top-20 與前瞻觀察狀態；不重算、不推薦、不宣稱預測優勢。
        </p>
      </div>
      <span class="analytics-badge">PREDICTIVE ADVANTAGE: NO</span>
    </header>

    <nav class="analytics-tabs" role="tablist" aria-label="B649 analytics sections">
      <button
        type="button"
        role="tab"
        :aria-selected="activeTab === 'strategy-k'"
        @click="activeTab = 'strategy-k'"
      >
        Strategy × K
      </button>
      <button
        type="button"
        role="tab"
        :aria-selected="activeTab === 'combinations'"
        @click="activeTab = 'combinations'"
      >
        Strategy Combinations
      </button>
      <button
        type="button"
        role="tab"
        :aria-selected="activeTab === 'evidence'"
        @click="activeTab = 'evidence'"
      >
        Evidence Status
      </button>
    </nav>

    <section v-if="activeTab === 'strategy-k'" role="tabpanel" class="analytics-panel">
      <div v-if="strategySummaryState === 'loading'" class="state-card" role="status">
        正在讀取封存 Strategy-K authority…
      </div>
      <div v-else-if="strategySummaryState === 'unavailable'" class="state-card warning" role="status">
        <strong>Strategy-K authority 目前不可用</strong>
        <p>{{ strategySummaryMessage }}</p>
        <button type="button" @click="loadStrategySummary">重試</button>
      </div>
      <div v-else-if="strategySummaryState === 'error'" class="state-card error" role="alert">
        <strong>Strategy-K 回應無法驗證</strong>
        <p>{{ strategySummaryMessage }}</p>
        <button type="button" @click="loadStrategySummary">重試</button>
      </div>
      <div v-else-if="strategySummaryState === 'empty'" class="state-card" role="status">
        封存策略 universe 沒有可顯示的 identity。
      </div>
      <template v-else-if="strategySummary">
        <div class="metric-grid" data-testid="strategy-k-summary">
          <article><span>Matrix rows</span><strong>{{ strategySummary.matrix_row_count }}</strong></article>
          <article><span>Matrix available</span><strong>{{ strategySummary.matrix_available_strategy_count }}</strong></article>
          <article><span>Portfolio unavailable</span><strong>{{ strategySummary.matrix_unavailable_strategy_count }}</strong></article>
          <article><span>Executable universe</span><strong>{{ strategySummary.current_executable_strategy_count }}</strong></article>
        </div>
        <aside class="semantic-note" role="note">
          <strong>Historical candidate coverage</strong>
          <p>{{ strategySummary.research_disclaimer }}</p>
          <p>
            750 = PRIMARY_EVIDENCE；300 = STABILITY_CONFIRMATION；50 = DEGRADATION_VETO；FULL = REFERENCE_ONLY。
            這些巢狀視窗不是獨立實驗。
          </p>
        </aside>

        <section class="availability-section" aria-labelledby="availability-title">
          <div class="section-heading">
            <div>
              <p class="analytics-eyebrow">Authority-driven availability</p>
              <h2 id="availability-title">策略可用性</h2>
            </div>
            <span>{{ displayedStrategies.length }} / {{ strategySummary.strategies.length }}</span>
          </div>
          <div class="compact-controls">
            <label>
              <span>搜尋策略</span>
              <input v-model="availabilitySearch" type="search" placeholder="strategy_id" />
            </label>
            <label>
              <span>可用性</span>
              <select v-model="availabilityFilter">
                <option value="ALL">ALL</option>
                <option value="MATRIX_AVAILABLE">MATRIX_AVAILABLE</option>
                <option value="PORTFOLIO_ORDER_AGGREGATION_NOT_DEFINED">
                  PORTFOLIO_ORDER_AGGREGATION_NOT_DEFINED
                </option>
              </select>
            </label>
          </div>
          <div class="table-scroll" tabindex="0" role="region" aria-label="Strategy-K availability table">
            <table>
              <thead><tr><th>Strategy</th><th>Status</th><th>Native tickets</th><th>Explanation</th></tr></thead>
              <tbody>
                <tr v-for="strategy in displayedStrategies" :key="`${strategy.strategy_id}-${strategy.strategy_version}`">
                  <td><strong>{{ strategy.strategy_id }}</strong><small>{{ strategy.strategy_version }}</small></td>
                  <td><span class="status-chip">{{ strategy.availability }}</span></td>
                  <td>{{ strategy.native_ticket_count }} · {{ strategy.response_shape }}</td>
                  <td>{{ strategy.availability_reason }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <form class="query-card" data-testid="strategy-k-form" @submit.prevent="queryStrategy(0)">
          <div class="section-heading">
            <div><p class="analytics-eyebrow">Comparable filter set</p><h2>Strategy × K 查詢</h2></div>
            <span>不自動選擇「推薦」策略</span>
          </div>
          <div class="query-grid">
            <label><span>Requested K</span><select v-model.number="requestedK" required><option value="" disabled>請選擇</option><option v-for="value in strategySummary.supported_k_values" :key="value" :value="value">K = {{ value }}</option></select></label>
            <label><span>History window</span><select v-model="strategyWindow" required><option v-for="window in strategySummary.windows" :key="window.window_kind" :value="window.window_kind">{{ windowText(window) }}</option></select></label>
            <label><span>Criterion</span><select v-model="strategyCriterion" required><option value="" disabled>請選擇</option><option v-for="value in strategySummary.supported_criteria" :key="value" :value="value">{{ value }}</option></select></label>
            <label><span>Strategy search</span><input v-model="strategySearch" type="search" maxlength="200" placeholder="可選" /></label>
            <label><span>Deterministic sort</span><select v-model="strategySort"><option value="STRATEGY_ID_ASC">Strategy ID</option><option value="OBSERVED_RATE_DESC">Historical coverage rate</option><option value="OBSERVED_MINUS_BASELINE_DESC">Historical relation vs baseline</option></select></label>
          </div>
          <button type="submit" :disabled="!canQueryStrategy || strategyQueryState === 'loading'">{{ strategyQueryState === 'loading' ? '查詢中…' : '查詢封存矩陣' }}</button>
        </form>

        <div v-if="strategyQueryState === 'idle'" class="state-card" role="status">請選擇 K 與 criterion；750 primary window 已明確標示，但不會自動排名。</div>
        <div v-else-if="strategyQueryState === 'loading'" class="state-card" role="status">正在讀取相同 K／criterion／window 的矩陣 cells…</div>
        <div v-else-if="strategyQueryState === 'empty'" class="state-card" role="status"><strong>沒有符合條件的矩陣列</strong><p>不可用 portfolio strategy 不會被合成 Candidate-K。</p></div>
        <div v-else-if="strategyQueryState === 'unavailable'" class="state-card warning" role="status"><strong>矩陣查詢目前不可用</strong><p>{{ strategyQueryMessage }}</p><button type="button" @click="queryStrategy(strategyPage?.offset ?? 0)">重試</button></div>
        <div v-else-if="strategyQueryState === 'error'" class="state-card error" role="alert"><strong>矩陣查詢失敗</strong><p>{{ strategyQueryMessage }}</p><button type="button" @click="queryStrategy(0)">重試</button></div>
        <section v-else-if="strategyPage" class="results-section">
          <div class="section-heading"><div><p class="analytics-eyebrow">{{ strategyPage.ranking_label }}</p><h2>歷史候選覆蓋結果</h2></div><span>{{ strategyPage.total }} cells · {{ strategyPage.window_role }}</span></div>
          <div class="table-scroll" tabindex="0" role="region" aria-label="Strategy-K results table">
            <table>
              <thead><tr><th>Strategy</th><th>Filter identity</th><th>Observed exact</th><th>Exact random baseline</th><th>Relation</th><th>Effective unique K</th><th>Observation accounting</th><th>Target range</th></tr></thead>
              <tbody>
                <tr v-for="record in strategyPage.items" :key="`${record.strategy_id}-${record.requested_k}-${record.criterion}-${record.window_kind}`">
                  <td><strong>{{ record.strategy_id }}</strong><small>{{ record.strategy_version }}</small></td>
                  <td>K{{ record.requested_k }} · {{ record.criterion }} · {{ record.window_kind }}</td>
                  <td><strong>{{ percent(record.success_numerator, record.success_denominator) }}</strong><code>{{ record.success_numerator }} / {{ record.success_denominator }}</code></td>
                  <td><strong>{{ percent(record.random_baseline_numerator, record.random_baseline_denominator) }}</strong><code>{{ record.random_baseline_numerator }} / {{ record.random_baseline_denominator }}</code></td>
                  <td>{{ record.observed_minus_baseline }}</td>
                  <td>{{ effectiveKText(record) }}</td>
                  <td>{{ record.eligible_observation_count }} eligible · {{ record.excluded_observation_count }} excluded · {{ record.source_observation_count }} source</td>
                  <td>{{ record.first_target_draw }} → {{ record.last_target_draw }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <nav class="pagination" aria-label="Strategy-K pagination"><button type="button" :disabled="strategyPage.offset === 0" @click="queryStrategy(Math.max(0, strategyPage.offset - strategyPage.limit))">上一頁</button><span>{{ strategyPage.offset + 1 }}–{{ Math.min(strategyPage.offset + strategyPage.items.length, strategyPage.total) }} / {{ strategyPage.total }}</span><button type="button" :disabled="strategyPage.offset + strategyPage.limit >= strategyPage.total" @click="queryStrategy(strategyPage.offset + strategyPage.limit)">下一頁</button></nav>
        </section>
      </template>
    </section>

    <section v-else-if="activeTab === 'combinations'" role="tabpanel" class="analytics-panel">
      <div v-if="combinationSummaryState === 'loading'" class="state-card" role="status">正在讀取封存 pair/triple projection…</div>
      <div v-else-if="combinationSummaryState === 'unavailable'" class="state-card warning" role="status"><strong>組合 authority 目前不可用</strong><p>{{ combinationSummaryMessage }}</p><button type="button" @click="loadCombinationSummary">重試</button></div>
      <div v-else-if="combinationSummaryState === 'error'" class="state-card error" role="alert"><strong>組合回應無法驗證</strong><p>{{ combinationSummaryMessage }}</p><button type="button" @click="loadCombinationSummary">重試</button></div>
      <div v-else-if="combinationSummaryState === 'empty'" class="state-card" role="status">封存 Top-20 pool 沒有可顯示的列。</div>
      <template v-else-if="combinationSummary">
        <div class="metric-grid"><article><span>Sealed Top-pool rows</span><strong>{{ combinationSummary.sealed_top_candidate_count }}</strong></article><article><span>Member scope</span><strong>Pair + Triple</strong></article><article><span>Browser full projection</span><strong>NO</strong></article><article><span>Predictive advantage</span><strong>NO</strong></article></div>
        <aside class="semantic-note" role="note"><strong>Historical descriptive ranking only</strong><p>{{ combinationSummary.research_disclaimer }}</p><p>API 僅分頁傳回已封存的相同比較條件 Top-20；1.3 GB 完整 projection 不送進瀏覽器。組合 candidate size 會隨 draw 改變，這個 Top-pool contract 沒有 requested-K 欄位。</p></aside>
        <form class="query-card" data-testid="combination-form" @submit.prevent="queryCombination(0)">
          <div class="section-heading"><div><p class="analytics-eyebrow">Bounded server-side query</p><h2>Pair / Triple 組合查詢</h2></div><span>{{ combinationSummary.source_scope }}</span></div>
          <div class="query-grid">
            <label><span>A / C proxy</span><select v-model="proxyMode" required><option value="" disabled>請選擇</option><option v-for="proxy in combinationSummary.proxy_modes" :key="proxy.proxy_mode" :value="proxy.proxy_mode">{{ proxy.proxy_mode }} · {{ proxy.proxy_label }}</option></select></label>
            <label><span>Pair / Triple</span><select v-model.number="memberCount" required><option value="" disabled>請選擇</option><option v-for="count in combinationSummary.member_counts" :key="count" :value="count">{{ count === 2 ? 'Pair' : 'Triple' }}</option></select></label>
            <label><span>History window</span><select v-model="combinationWindow" required><option v-for="window in combinationSummary.windows" :key="window.window_kind" :value="window.window_kind">{{ windowText(window) }}</option></select></label>
            <label><span>Criterion</span><select v-model="combinationCriterion" required><option value="" disabled>請選擇</option><option v-for="value in combinationSummary.supported_criteria" :key="value" :value="value">{{ value }}</option></select></label>
            <label><span>Member strategy search</span><input v-model="memberSearch" type="search" maxlength="200" placeholder="可選" /></label>
            <label><span>Display order</span><select v-model="combinationSort"><option value="SEALED_RANK_ASC">Sealed historical rank</option><option value="COMBINATION_ID_ASC">Combination ID</option></select></label>
          </div>
          <button type="submit" :disabled="!canQueryCombination || combinationQueryState === 'loading'">{{ combinationQueryState === 'loading' ? '查詢中…' : '查詢封存 Top-20' }}</button>
        </form>
        <div v-if="combinationQueryState === 'idle'" class="state-card" role="status">請明確選擇 proxy、pair/triple 與 criterion；不會自動挑選組合。</div>
        <div v-else-if="combinationQueryState === 'loading'" class="state-card" role="status">正在執行 bounded server-side filter / sort / pagination…</div>
        <div v-else-if="combinationQueryState === 'empty'" class="state-card" role="status"><strong>目前 filter 沒有封存 Top-20 列</strong><p>空 pool 不會補零或重新搜尋 392,084 個組合。</p></div>
        <div v-else-if="combinationQueryState === 'unavailable'" class="state-card warning" role="status"><strong>組合查詢目前不可用</strong><p>{{ combinationQueryMessage }}</p><button type="button" @click="queryCombination(0)">重試</button></div>
        <div v-else-if="combinationQueryState === 'error'" class="state-card error" role="alert"><strong>組合查詢失敗</strong><p>{{ combinationQueryMessage }}</p><button type="button" @click="queryCombination(0)">重試</button></div>
        <section v-else-if="combinationPage" class="results-section">
          <div class="section-heading"><div><p class="analytics-eyebrow">{{ combinationPage.ranking_label }}</p><h2>封存組合結果</h2></div><span>{{ combinationPage.total }} rows · {{ combinationPage.window_role }}</span></div>
          <div class="table-scroll" tabindex="0" role="region" aria-label="B649 combination results table"><table><thead><tr><th>Sealed rank</th><th>Combination</th><th>Members</th><th>Observed exact</th><th>Exact random baseline</th><th>Historical delta</th><th>Evidence status</th><th>Cross-window context</th></tr></thead><tbody><tr v-for="record in combinationPage.items" :key="`${record.proxy_mode}-${record.combination_id}-${record.evaluation_window}-${record.criterion}`"><td><strong>#{{ record.sealed_rank }}</strong></td><td><strong>{{ record.combination_id }}</strong><small>{{ record.proxy_mode }} · {{ record.proxy_label }} · {{ record.member_count }} members</small></td><td><code v-for="member in record.member_strategy_ids" :key="member">{{ member }}</code></td><td><strong>{{ decimalPercent(record.observed_rate) }}</strong><code>{{ record.success_numerator }} / {{ record.success_denominator }}</code></td><td><strong>{{ decimalPercent(record.random_baseline_rate) }}</strong><code>{{ record.exact_random_baseline_numerator }} / {{ record.exact_random_baseline_denominator }}</code></td><td>{{ signedPoints(record.descriptive_delta) }}</td><td>{{ record.evaluation_status }} · {{ record.evaluation_reason }}</td><td>{{ record.long_delta_sign ?? '—' }} / {{ record.mid_delta_sign ?? '—' }} / {{ record.short_delta_sign ?? '—' }} · positive {{ record.positive_window_count }}</td></tr></tbody></table></div>
          <nav class="pagination" aria-label="Combination pagination"><button type="button" :disabled="combinationPage.offset === 0" @click="queryCombination(Math.max(0, combinationPage.offset - combinationPage.limit))">上一頁</button><span>{{ combinationPage.offset + 1 }}–{{ Math.min(combinationPage.offset + combinationPage.items.length, combinationPage.total) }} / {{ combinationPage.total }}</span><button type="button" :disabled="combinationPage.offset + combinationPage.limit >= combinationPage.total" @click="queryCombination(combinationPage.offset + combinationPage.limit)">下一頁</button></nav>
        </section>
      </template>
    </section>

    <section v-else role="tabpanel" class="analytics-panel evidence-panel">
      <div v-if="evidenceState === 'loading'" class="state-card" role="status">正在讀取 observer authority…</div>
      <div v-else-if="evidenceState === 'unavailable'" class="state-card warning" role="status"><strong>Observer evidence 目前不可用</strong><p>{{ evidenceMessage }}</p><p>Strategy-K 與組合歷史 views 仍可獨立使用。</p><button type="button" @click="loadEvidence">重試</button></div>
      <div v-else-if="evidenceState === 'error'" class="state-card error" role="alert"><strong>Observer 回應無法驗證</strong><p>{{ evidenceMessage }}</p><button type="button" @click="loadEvidence">重試</button></div>
      <div v-else-if="evidenceState === 'empty'" class="state-card" role="status">Observer 尚無 evidence。</div>
      <template v-else-if="evidence">
        <div class="metric-grid" data-testid="evidence-summary"><article><span>Historical evidence</span><strong>{{ evidence.historical_evidence_status }}</strong></article><article><span>Pre-freeze unseen holdout</span><strong>{{ evidence.pre_freeze_date_unseen_holdout_count }}</strong></article><article><span>Post-freeze prospective</span><strong>{{ evidence.post_freeze_date_prospective_count }}</strong></article><article><span>Checkpoint reached</span><strong>{{ evidence.checkpoints_reached.length ? evidence.checkpoints_reached.join(', ') : 'NONE' }}</strong></article></div>
        <section class="evidence-card"><p class="analytics-eyebrow">Temporal provenance</p><h2>Holdout 與 prospective 分開呈現</h2><dl><div><dt>Observation range</dt><dd>{{ evidence.observation_start_draw }} → {{ evidence.latest_observed_draw ?? 'NONE' }}</dd></div><div><dt>Primary outcome</dt><dd>{{ evidence.primary_outcome }}</dd></div><div><dt>Scheduled checkpoints</dt><dd>{{ evidence.checkpoints.join(' / ') }}</dd></div><div><dt>Holdout reranked historical results</dt><dd>{{ evidence.holdout_used_to_rerank_historical_results ? 'YES' : 'NO' }}</dd></div></dl></section>
        <section class="evidence-card warning"><p class="analytics-eyebrow">C forward evidence</p><h2>{{ evidence.c_forward_status }}</h2><p>{{ evidence.c_forward_reason }}</p><p>Observer 未選擇 C horizon，也沒有替換 strategy 或改變 cohort。</p></section>
        <aside class="semantic-note" role="note">
          <strong>PREDICTIVE_ADVANTAGE_CLAIMED = {{ evidence.predictive_advantage_claimed ? 'YES' : 'NO' }}</strong>
          <p>
            {{ evidence.pre_freeze_date_unseen_holdout_count }} 個 observation 屬
            PRE_FREEZE_DATE_UNSEEN_HOLDOUT；{{ evidence.post_freeze_date_prospective_count }} 個
            observation 屬 POST_FREEZE_DATE_PROSPECTIVE。
          </p>
          <p v-if="evidence.checkpoints_reached.length">
            已達 checkpoint：{{ evidence.checkpoints_reached.join(' / ') }}。
          </p>
          <p v-else>尚未達 checkpoint。</p>
        </aside>
      </template>
    </section>
  </section>
</template>

<style scoped>
.b649-analytics-page { display: grid; gap: 1.25rem; color: #18222d; }
.analytics-hero { display: flex; justify-content: space-between; gap: 1.5rem; padding: 1.6rem; border: 1px solid #cad7dd; border-radius: 20px; background: linear-gradient(135deg, #f4fbf8 0%, #eef4fa 100%); }
.analytics-hero h1, .section-heading h2, .evidence-card h2 { margin: .2rem 0 .5rem; }
.analytics-hero p { max-width: 70ch; margin: 0; line-height: 1.7; }
.analytics-eyebrow { margin: 0; color: #27665a; font-size: .75rem; font-weight: 800; letter-spacing: .11em; text-transform: uppercase; }
.analytics-badge, .status-chip { align-self: flex-start; padding: .45rem .7rem; border-radius: 999px; background: #d8efe7; color: #195449; font-size: .74rem; font-weight: 800; }
.analytics-tabs { display: flex; flex-wrap: wrap; gap: .5rem; }
.analytics-tabs button { padding: .7rem 1rem; border: 1px solid #b8c9cf; border-radius: 999px; background: white; cursor: pointer; }
.analytics-tabs button[aria-selected="true"] { border-color: #1e6d60; background: #1e6d60; color: white; }
.analytics-panel { display: grid; gap: 1.2rem; }
.metric-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: .8rem; }
.metric-grid article { padding: 1rem; border: 1px solid #d2dde1; border-radius: 14px; background: white; }
.metric-grid span { display: block; color: #5d6972; font-size: .78rem; }
.metric-grid strong { display: block; margin-top: .35rem; font-size: 1.35rem; }
.semantic-note, .state-card, .query-card, .availability-section, .results-section, .evidence-card { padding: 1rem; border: 1px solid #d2dde1; border-radius: 14px; background: white; }
.semantic-note { border-left: 4px solid #27786a; background: #f4fbf8; }
.semantic-note p, .state-card p, .evidence-card p { margin: .4rem 0 0; line-height: 1.6; }
.warning { border-color: #d5a63f; background: #fff9ea; }
.error { border-color: #bf5b5b; background: #fff3f3; }
.section-heading { display: flex; justify-content: space-between; gap: 1rem; align-items: flex-start; margin-bottom: .9rem; }
.section-heading span { color: #62717a; font-size: .8rem; text-align: right; }
.compact-controls, .query-grid { display: grid; gap: .8rem; margin-bottom: .9rem; }
.compact-controls { grid-template-columns: minmax(0, 2fr) minmax(0, 1fr); }
.query-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
label { display: grid; gap: .35rem; font-size: .82rem; font-weight: 700; }
input, select, button { font: inherit; }
input, select { min-width: 0; padding: .62rem .7rem; border: 1px solid #b8c7cd; border-radius: 9px; background: white; }
button { padding: .58rem .8rem; border: 1px solid #2b7165; border-radius: 9px; background: #2b7165; color: white; cursor: pointer; }
button:disabled { cursor: not-allowed; opacity: .5; }
.table-scroll { overflow-x: auto; border: 1px solid #d5dfe3; border-radius: 10px; }
table { width: 100%; border-collapse: collapse; min-width: 980px; font-size: .8rem; }
th, td { padding: .7rem; border-bottom: 1px solid #e2e8eb; text-align: left; vertical-align: top; }
th { background: #f3f6f7; color: #4f5f68; white-space: nowrap; }
td small, td code { display: block; margin-top: .25rem; }
td code { max-width: 32rem; overflow-wrap: anywhere; color: #42535c; }
.pagination { display: flex; justify-content: flex-end; align-items: center; gap: .7rem; margin-top: .8rem; }
.evidence-panel { max-width: 1100px; }
.evidence-card dl { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: .7rem; }
.evidence-card dl div { padding: .7rem; background: #f4f7f8; border-radius: 9px; }
.evidence-card dt { color: #63727a; font-size: .75rem; }
.evidence-card dd { margin: .25rem 0 0; font-weight: 750; }
@media (max-width: 900px) { .metric-grid, .query-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } .analytics-hero { flex-direction: column; } }
@media (max-width: 620px) { .metric-grid, .query-grid, .compact-controls, .evidence-card dl { grid-template-columns: 1fr; } .section-heading { flex-direction: column; } }
</style>
