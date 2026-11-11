<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import {
  B649_RESEARCH_BACKTEST_GROUP_SCAN_SIZE,
  B649_RESEARCH_BACKTEST_PAGE_SIZE,
  EXPECTED_B649_RESEARCH_V2_SOURCE,
  fetchB649ResearchBacktestMethods,
  fetchB649ResearchBacktestRankings,
  fetchB649ResearchBacktestSummary,
  isExpectedB649ResearchV2Source,
  type B649ResearchBacktestMethod,
  type B649ResearchBacktestMethodsPage,
  type B649ResearchBacktestRankingsPage,
  type B649ResearchBacktestSummary,
  type B649ResearchBacktestWindow,
  type B649ResearchBacktestsRequestError,
  type B649ResearchBacktestRankingsQuery,
} from '../../api/b649ResearchBacktests'

type BoardTab = 'methods' | 'rankings'
type LoadState = 'idle' | 'loading' | 'ready' | 'empty' | 'error'

interface RankingSelection {
  cohort: string
  K: number
  window: B649ResearchBacktestWindow
  prize_metric: string
}

interface ComparisonGroup {
  key: string
  targetDrawSetIdentity: string
  eligibleDraws: number
  lotteryType: string
  rowCount: number
}

const summary = ref<B649ResearchBacktestSummary | null>(null)
const summaryState = ref<LoadState>('loading')
const summaryError = ref('')
const activeTab = ref<BoardTab>('rankings')

const selectedCohort = ref('')
const selectedK = ref<number | null>(null)
const selectedWindow = ref<B649ResearchBacktestWindow | ''>('')
const selectedPrizeMetric = ref('')

const groupState = ref<LoadState>('idle')
const groupError = ref('')
const comparisonGroups = ref<ComparisonGroup[]>([])
const selectedGroupKey = ref('')
const rankingsState = ref<LoadState>('idle')
const rankingsError = ref('')
const rankingsPage = ref<B649ResearchBacktestRankingsPage | null>(null)
const rankingsOffset = ref(0)

const methodsState = ref<LoadState>('idle')
const methodsError = ref('')
const methodsPage = ref<B649ResearchBacktestMethodsPage | null>(null)
const methodsOffset = ref(0)
const methodIdFilter = ref('')
const methodStatusFilter = ref('ALL')

let summaryController: AbortController | null = null
let groupController: AbortController | null = null
let rankingsController: AbortController | null = null
let methodsController: AbortController | null = null
let summaryGeneration = 0
let groupGeneration = 0
let rankingsGeneration = 0
let methodsGeneration = 0

const selectedGroup = computed(() =>
  comparisonGroups.value.find((group) => group.key === selectedGroupKey.value) ?? null,
)

const rankingSelection = computed<RankingSelection | null>(() => {
  const current = summary.value
  const window = selectedWindow.value
  const K = selectedK.value
  if (!current || !selectedCohort.value || K === null || !window || !selectedPrizeMetric.value) {
    return null
  }
  if (
    !current.cohorts.includes(selectedCohort.value) ||
    !current.K_values.includes(K) ||
    !current.windows.includes(window) ||
    !current.prize_metrics.includes(selectedPrizeMetric.value)
  ) {
    return null
  }
  return {
    cohort: selectedCohort.value,
    K,
    window,
    prize_metric: selectedPrizeMetric.value,
  }
})

const methods = computed(() => methodsPage.value?.items ?? [])
const rankings = computed(() => rankingsPage.value?.items ?? [])
const methodStatuses = computed(() =>
  Object.entries(summary.value?.research_status_counts ?? {}).sort(([left], [right]) => left.localeCompare(right)),
)
const methodsPreviousOffset = computed(() => Math.max(0, methodsOffset.value - B649_RESEARCH_BACKTEST_PAGE_SIZE))
const methodsNextOffset = computed(() => methodsOffset.value + B649_RESEARCH_BACKTEST_PAGE_SIZE)
const rankingsPreviousOffset = computed(() => Math.max(0, rankingsOffset.value - B649_RESEARCH_BACKTEST_PAGE_SIZE))
const rankingsNextOffset = computed(() => rankingsOffset.value + B649_RESEARCH_BACKTEST_PAGE_SIZE)

async function loadSummary(): Promise<void> {
  summaryController?.abort()
  const controller = new AbortController()
  summaryController = controller
  const generation = ++summaryGeneration
  summary.value = null
  summaryError.value = ''
  summaryState.value = 'loading'

  try {
    const result = await fetchB649ResearchBacktestSummary(controller.signal)
    if (generation !== summaryGeneration) return
    if (!isExpectedB649ResearchV2Source(result)) {
      throw new Error(
        `來源身份與已核定的 V2 來源不符（預期 ${EXPECTED_B649_RESEARCH_V2_SOURCE.taskId}）。`,
      )
    }
    if (
      result.method_version_count !== 305 ||
      result.inventory_count !== 2968 ||
      result.ranking_count !== 2818 ||
      result.unavailable_count !== 60 ||
      result.not_applicable_count !== 90 ||
      result.duplicate_output_groups !== 48
    ) {
      throw new Error('來源筆數與已核對的 V2 manifest 不一致，已停止顯示比較結果。')
    }
    summary.value = result
    selectedCohort.value = result.cohorts[0] ?? ''
    selectedK.value = result.K_values[0] ?? null
    selectedWindow.value = result.windows[0] ?? ''
    selectedPrizeMetric.value = result.prize_metrics[0] ?? ''
    summaryState.value = 'ready'
    methodsOffset.value = 0
    void loadMethods()
  } catch (error) {
    if (controller.signal.aborted || isAbortError(error) || generation !== summaryGeneration) return
    summary.value = null
    summaryError.value = errorMessage(error)
    summaryState.value = 'error'
  } finally {
    if (summaryController === controller) summaryController = null
  }
}

async function loadMethods(): Promise<void> {
  const current = summary.value
  if (!current) return
  methodsController?.abort()
  const controller = new AbortController()
  methodsController = controller
  const generation = ++methodsGeneration
  methodsPage.value = null
  methodsError.value = ''
  methodsState.value = 'loading'

  try {
    const query = {
      limit: B649_RESEARCH_BACKTEST_PAGE_SIZE,
      offset: methodsOffset.value,
      ...(methodIdFilter.value.trim() ? { method_id: methodIdFilter.value.trim() } : {}),
      ...(methodStatusFilter.value !== 'ALL' ? { research_status: methodStatusFilter.value } : {}),
    }
    const page = await fetchB649ResearchBacktestMethods(query, controller.signal)
    if (generation !== methodsGeneration) return
    if (
      page.offset !== methodsOffset.value ||
      page.limit !== B649_RESEARCH_BACKTEST_PAGE_SIZE ||
      page.items.length > page.limit ||
      page.offset + page.items.length > page.total ||
      page.items.length !== Math.min(page.limit, Math.max(0, page.total - page.offset)) ||
      (!methodIdFilter.value.trim() && methodStatusFilter.value === 'ALL' && page.total !== current.inventory_count) ||
      (methodStatusFilter.value !== 'ALL' && page.items.some((item) => item.research_status !== methodStatusFilter.value)) ||
      (methodIdFilter.value.trim() && page.items.some((item) => item.method_id !== methodIdFilter.value.trim()))
    ) {
      throw new Error('methods 分頁或篩選回應與本次查詢不一致。')
    }
    methodsPage.value = page
    methodsState.value = page.total === 0 ? 'empty' : 'ready'
  } catch (error) {
    if (controller.signal.aborted || isAbortError(error) || generation !== methodsGeneration) return
    methodsPage.value = null
    methodsError.value = errorMessage(error)
    methodsState.value = 'error'
  } finally {
    if (methodsController === controller) methodsController = null
  }
}

async function loadComparisonGroups(selection: RankingSelection): Promise<void> {
  groupController?.abort()
  rankingsController?.abort()
  const controller = new AbortController()
  groupController = controller
  const generation = ++groupGeneration
  ++rankingsGeneration
  comparisonGroups.value = []
  selectedGroupKey.value = ''
  rankingsPage.value = null
  rankingsOffset.value = 0
  rankingsError.value = ''
  rankingsState.value = 'idle'
  groupError.value = ''
  groupState.value = 'loading'

  try {
    const foundGroups = new Map<string, ComparisonGroup>()
    let total: number | null = null
    let expectedGroupCount: number | null = null
    let offset = 0
    do {
      const page = await fetchB649ResearchBacktestRankings({
        ...selection,
        limit: B649_RESEARCH_BACKTEST_GROUP_SCAN_SIZE,
        offset,
      }, controller.signal)
      if (generation !== groupGeneration) return
      assertRankingPageSelection(page, selection)
      if (page.offset !== offset || page.limit !== B649_RESEARCH_BACKTEST_GROUP_SCAN_SIZE) {
        throw new Error('群組目錄分頁位置與請求不一致。')
      }
      if (page.items.length !== Math.min(page.limit, Math.max(0, page.total - offset))) {
        throw new Error('群組目錄未完整回傳本頁資料。')
      }
      if (total !== null && page.total !== total) {
        throw new Error('建立比較群組期間，rankings 總筆數發生變化。')
      }
      if (expectedGroupCount !== null && page.comparison_group_count !== expectedGroupCount) {
        throw new Error('建立比較群組期間，API 回報的群組數發生變化。')
      }
      total = page.total
      expectedGroupCount = page.comparison_group_count
      if (total > 10_000) throw new Error('排名資料超過 API 可安全分頁範圍。')

      for (const row of page.items) {
        if (
          row.evaluation_cohort !== selection.cohort ||
          row.K !== selection.K ||
          row.window !== selection.window ||
          row.prize_metric !== selection.prize_metric
        ) {
          throw new Error('排名資料包含不同 cohort、K、window 或獎項口徑。')
        }
        const key = JSON.stringify([row.target_draw_set_identity, row.eligible_draws])
        const group = foundGroups.get(key)
        if (group) {
          if (group.lotteryType !== row.lottery_type) {
            throw new Error('API 比較群組無法由要求的群組參數唯一隔離。')
          }
          group.rowCount += 1
        } else {
          foundGroups.set(key, {
            key,
            targetDrawSetIdentity: row.target_draw_set_identity,
            eligibleDraws: row.eligible_draws,
            lotteryType: row.lottery_type,
            rowCount: 1,
          })
        }
      }
      offset += page.items.length
      if (offset < page.total && page.items.length === 0) {
        throw new Error('群組目錄在完成分頁前回傳空頁。')
      }
    } while (total !== null && offset < total)

    if (generation !== groupGeneration) return
    const groups = [...foundGroups.values()].sort((left, right) =>
      left.targetDrawSetIdentity.localeCompare(right.targetDrawSetIdentity) ||
      left.eligibleDraws - right.eligibleDraws,
    )
    if (groups.length !== (expectedGroupCount ?? 0)) {
      throw new Error('群組選項數與 API 的 comparison_group_count 不一致。')
    }
    comparisonGroups.value = groups
    groupState.value = groups.length === 0 ? 'empty' : 'ready'
    if (groups.length === 1) selectedGroupKey.value = groups[0]!.key
  } catch (error) {
    if (controller.signal.aborted || isAbortError(error) || generation !== groupGeneration) return
    comparisonGroups.value = []
    groupError.value = errorMessage(error)
    groupState.value = 'error'
  } finally {
    if (groupController === controller) groupController = null
  }
}

async function loadRankingPage(): Promise<void> {
  const selection = rankingSelection.value
  const group = selectedGroup.value
  if (!selection || !group) return
  rankingsController?.abort()
  const controller = new AbortController()
  rankingsController = controller
  const generation = ++rankingsGeneration
  rankingsPage.value = null
  rankingsError.value = ''
  rankingsState.value = 'loading'

  try {
    const query: B649ResearchBacktestRankingsQuery = {
      ...selection,
      target_draw_set_identity: group.targetDrawSetIdentity,
      eligible_draws: group.eligibleDraws,
      limit: B649_RESEARCH_BACKTEST_PAGE_SIZE,
      offset: rankingsOffset.value,
    }
    const page = await fetchB649ResearchBacktestRankings(query, controller.signal)
    if (generation !== rankingsGeneration) return
    assertRankingPageSelection(page, selection)
    if (
      page.offset !== rankingsOffset.value ||
      page.limit !== B649_RESEARCH_BACKTEST_PAGE_SIZE ||
      page.target_draw_set_identity !== group.targetDrawSetIdentity ||
      page.eligible_draws !== group.eligibleDraws ||
      (page.total > 0 && page.comparison_group_count !== 1) ||
      page.items.length > page.limit ||
      page.offset + page.items.length > page.total ||
      page.items.length !== Math.min(page.limit, Math.max(0, page.total - page.offset)) ||
      page.items.some((row) =>
        row.target_draw_set_identity !== group.targetDrawSetIdentity ||
        row.eligible_draws !== group.eligibleDraws ||
        row.lottery_type !== group.lotteryType,
      )
    ) {
      throw new Error('rankings 回應未保持單一比較群組或分頁位置與查詢不一致。')
    }
    rankingsPage.value = page
    rankingsState.value = page.total === 0 ? 'empty' : 'ready'
  } catch (error) {
    if (controller.signal.aborted || isAbortError(error) || generation !== rankingsGeneration) return
    rankingsPage.value = null
    rankingsError.value = errorMessage(error)
    rankingsState.value = 'error'
  } finally {
    if (rankingsController === controller) rankingsController = null
  }
}

function assertRankingPageSelection(
  page: B649ResearchBacktestRankingsPage,
  selection: RankingSelection,
): void {
  if (
    page.cohort !== selection.cohort ||
    page.K !== selection.K ||
    page.window !== selection.window ||
    page.prize_metric !== selection.prize_metric
  ) {
    throw new Error('rankings 回應的 cohort、K、window 或獎項口徑與查詢不一致。')
  }
}

function retryMethods(): void {
  void loadMethods()
}

function retryRankings(): void {
  if (rankingSelection.value) void loadComparisonGroups(rankingSelection.value)
}

function formatRate(value: string | null | undefined): string {
  if (value === null || value === undefined || value.trim() === '') return '不可用'
  const parsed = Number(value)
  return Number.isFinite(parsed) ? `${(parsed * 100).toFixed(2)}%` : '不可用'
}

function formatDelta(value: string | null | undefined): string {
  if (value === null || value === undefined || value.trim() === '') return '不可用'
  const parsed = Number(value)
  if (!Number.isFinite(parsed)) return '不可用'
  return `${parsed > 0 ? '+' : ''}${(parsed * 100).toFixed(2)}%`
}

function formatCount(value: number | null | undefined): string {
  return value === null || value === undefined || !Number.isInteger(value) || value < 0
    ? '不可用'
    : String(value)
}

function formatDecision(value: string): string {
  if (value === 'DO_NOT_ADVANCE') return 'DO_NOT_ADVANCE（仍保留檢視）'
  return value || '來源未提供'
}

function formatResearchClass(value: string): string {
  const normalized = value.toUpperCase()
  if (normalized.includes('EXPLOR')) return `探索性研究 · ${value}`
  if (normalized.includes('FORMAL') || normalized.includes('CONFIRM')) return `正式回測 · ${value}`
  return value || '來源未提供'
}

function isSharedOutput(row: B649ResearchBacktestMethod | B649ResearchBacktestRankingsPage['items'][number]): boolean {
  return Boolean(row.shared_output_identity) || row.source_shared_output_identities.length > 0
}

function formatIdentity(value: unknown): string {
  if (typeof value === 'string') return value
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return '來源身份無法呈現'
  }
}

function ownerField(value: string): string {
  return value === '' ? '（空白）' : value
}

function errorMessage(error: unknown): string {
  if (error instanceof Error) return error.message
  return '未知查詢錯誤。'
}

function isAbortError(error: unknown): error is DOMException {
  return error instanceof Error && error.name === 'AbortError'
}

function errorKind(error: unknown): string {
  if (typeof error === 'string') {
    if (error.includes('HTTP 503')) return '服務不可用（HTTP 503）'
    if (error.includes('HTTP 422')) return '查詢條件不合法'
    if (error.includes('網路連線失敗')) return '網路錯誤'
    if (error.includes('OpenAPI 契約')) return '回應契約錯誤'
    return '查詢錯誤'
  }
  if (typeof error !== 'object' || error === null) return '查詢錯誤'
  const requestError = error as Partial<B649ResearchBacktestsRequestError>
  if (requestError.kind === 'UNAVAILABLE' || requestError.status === 503) return '服務不可用（HTTP 503）'
  if (requestError.kind === 'NETWORK') return '網路錯誤'
  if (requestError.kind === 'INVALID_REQUEST' || requestError.status === 422) return '查詢條件不合法'
  if (requestError.kind === 'MALFORMED_RESPONSE') return '回應契約錯誤'
  return '查詢錯誤'
}

watch(rankingSelection, (selection) => {
  selectedGroupKey.value = ''
  comparisonGroups.value = []
  rankingsPage.value = null
  rankingsOffset.value = 0
  groupState.value = 'idle'
  rankingsState.value = 'idle'
  if (selection) void loadComparisonGroups(selection)
})

watch([selectedGroupKey, rankingsOffset], ([key, offset], [previousKey]) => {
  if (key !== previousKey && offset !== 0) {
    rankingsOffset.value = 0
    return
  }
  rankingsPage.value = null
  if (key && selectedGroup.value) void loadRankingPage()
  else rankingsState.value = 'idle'
})

watch(
  [methodIdFilter, methodStatusFilter, methodsOffset],
  ([methodId, status, offset], [previousMethodId, previousStatus]) => {
    if ((methodId !== previousMethodId || status !== previousStatus) && offset !== 0) {
      methodsOffset.value = 0
      return
    }
    if (summary.value) void loadMethods()
  },
)

onMounted(() => {
  void loadSummary()
})

onBeforeUnmount(() => {
  summaryController?.abort()
  groupController?.abort()
  rankingsController?.abort()
  methodsController?.abort()
})
</script>

<template>
  <section class="v2-board" aria-labelledby="v2-board-title">
    <div class="v2-heading">
      <div>
        <p class="v2-eyebrow">唯讀研究資料 · V2</p>
        <h2 id="v2-board-title">歷史研究排名與成功率</h2>
      </div>
      <span class="v2-source-chip">API：B649 Research Backtests V2</span>
    </div>

    <p class="v2-note">
      本區直接呈現已保存的歷史研究。名次、同分與成功率沿用 API 原值；不同 cohort、K、窗口、獎項口徑或有效分母不會合併。
      歷史結果不代表前瞻增益；本區不會推薦、淘汰或替 Owner 選擇方法。
    </p>

    <p v-if="summaryState === 'loading'" class="v2-state" role="status">
      正在讀取並核對 V2 來源身份…
    </p>
    <div v-else-if="summaryState === 'error'" class="v2-state v2-state--error" role="group" aria-live="assertive">
      <strong>{{ errorKind(summaryError) }}</strong>
      <span>{{ summaryError }}</span>
      <button type="button" class="v2-button" @click="loadSummary">重新讀取 V2 摘要</button>
    </div>

    <template v-else-if="summary">
      <div class="v2-source-identity" aria-label="V2 來源身份">
        <span><strong>來源任務</strong><code>{{ summary.source_task_id }}</code></span>
        <span><strong>Canonical authority</strong><code>{{ summary.source_authority_commit }}</code></span>
        <span><strong>來源 checkout HEAD</strong><code>{{ summary.observed_checkout_head }}</code></span>
        <span><strong>Source manifest SHA-256</strong><code>{{ summary.source_manifest_sha256 }}</code></span>
        <span class="v2-identity-verified">來源身份已核對</span>
      </div>

      <dl class="v2-summary">
        <div><dt>Method / version</dt><dd>{{ summary.method_version_count }}</dd></div>
        <div><dt>Inventory</dt><dd>{{ summary.inventory_count }}</dd></div>
        <div><dt>Rankings</dt><dd>{{ summary.ranking_count }}</dd></div>
        <div><dt>UNAVAILABLE</dt><dd>{{ summary.unavailable_count }}</dd></div>
        <div><dt>NOT_APPLICABLE</dt><dd>{{ summary.not_applicable_count }}</dd></div>
        <div><dt>Comparable groups</dt><dd>{{ summary.comparable_group_count }}</dd></div>
        <div><dt>Shared-output groups</dt><dd>{{ summary.duplicate_output_groups }}</dd></div>
      </dl>

      <div class="v2-tabs" role="tablist" aria-label="V2 研究資料檢視方式">
        <button
          id="v2-methods-tab"
          type="button"
          role="tab"
          :aria-selected="activeTab === 'methods'"
          aria-controls="v2-methods-panel"
          @click="activeTab = 'methods'"
        >
          方法與來源狀態
        </button>
        <button
          id="v2-rankings-tab"
          type="button"
          role="tab"
          :aria-selected="activeTab === 'rankings'"
          aria-controls="v2-rankings-panel"
          @click="activeTab = 'rankings'"
        >
          歷史排名比較
        </button>
      </div>

      <section
        v-if="activeTab === 'methods'"
        id="v2-methods-panel"
        class="v2-panel"
        role="tabpanel"
        aria-labelledby="v2-methods-tab"
      >
        <div class="v2-controls">
          <label>
            <span>Method ID（完全相符）</span>
            <input
              v-model="methodIdFilter"
              aria-label="V2 方法 ID 篩選"
              type="search"
              placeholder="輸入完整 method_id"
            >
          </label>
          <label>
            <span>研究狀態</span>
            <select v-model="methodStatusFilter" aria-label="V2 研究狀態篩選">
              <option value="ALL">全部狀態</option>
              <option v-for="[status, count] in methodStatuses" :key="status" :value="status">
                {{ status }}（{{ count }}）
              </option>
            </select>
          </label>
          <button type="button" class="v2-button" :disabled="methodsState === 'loading'" @click="retryMethods">
            {{ methodsState === 'loading' ? '讀取中…' : '重新查詢方法' }}
          </button>
        </div>

        <p v-if="methodsState === 'loading'" class="v2-state" role="status">
          正在讀取 methods 第 {{ Math.floor(methodsOffset / B649_RESEARCH_BACKTEST_PAGE_SIZE) + 1 }} 頁…
        </p>
        <div v-else-if="methodsState === 'error'" class="v2-state v2-state--error" role="group" aria-live="assertive">
          <strong>{{ errorKind(methodsError) }}</strong>
          <span>{{ methodsError }}</span>
          <button type="button" class="v2-button" @click="retryMethods">重試 methods</button>
        </div>
        <p v-else-if="methodsState === 'empty'" class="v2-state" role="status">
          查詢成功，但這組 method ID／研究狀態沒有資料。
        </p>

        <template v-else-if="methodsPage && methodsState === 'ready'">
          <div class="v2-page-summary" aria-live="polite">
            <span>方法目錄 {{ methodsPage.offset + 1 }}–{{ methodsPage.offset + methodsPage.items.length }} / {{ methodsPage.total }}</span>
            <span>本頁保留 API 原始順序；未依成功率或 advance decision 篩除。</span>
          </div>
          <div class="v2-table-scroll" tabindex="0" aria-label="V2 歷史方法表格，可水平捲動">
            <table class="v2-table v2-method-table">
              <thead>
                <tr>
                  <th scope="col">Method / Version / Source record</th>
                  <th scope="col">Cohort / K / Window / Metric</th>
                  <th scope="col">歷史成功數 / 有效分母 / 成功率</th>
                  <th scope="col">研究狀態 / 原始決策</th>
                  <th scope="col">方法類型 / 研究分類</th>
                  <th scope="col">指標來源狀態</th>
                  <th scope="col">共享輸出</th>
                  <th scope="col">Owner 人工欄位（唯讀）</th>
                  <th scope="col">Source identity / lineage</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="method in methods" :key="`${method.source_record_id}:${method.method_id}@${method.method_version}`">
                  <td class="v2-identity-cell">
                    <strong>{{ method.method_id }}</strong>
                    <code>{{ method.method_version }}</code>
                    <small>Task: {{ method.task_id }}</small>
                    <small>Record: {{ method.source_record_id }}</small>
                    <small>Rank: {{ method.comparison_rank ?? '—' }} · Group: {{ method.comparison_group_id || '—' }}</small>
                  </td>
                  <td>
                    <strong>{{ method.evaluation_cohort || '來源未提供' }}</strong>
                    <span>K{{ method.K ?? '—' }} · {{ method.history_window || '—' }}</span>
                    <small>{{ method.official_prize_metric || '來源未提供' }}</small>
                    <small>Ranking row: {{ method.window || '—' }} · {{ method.prize_metric || '—' }}</small>
                  </td>
                  <td>
                    <strong>{{ formatCount(method.successful_draws ?? method.wins) }} / {{ formatCount(method.eligible_draws) }}</strong>
                    <span>{{ formatRate(method.success_rate) }}</span>
                    <small>Baseline: {{ formatRate(method.baseline_success_rate ?? method.baseline_rate) }}</small>
                    <small>Delta: {{ formatDelta(method.paired_difference ?? method.delta_percentage_points) }}</small>
                  </td>
                  <td>
                    <strong>{{ method.research_status || '來源未提供' }}</strong>
                    <span>{{ formatDecision(method.original_advance_decision) }}</span>
                    <small>Board 原始決策：{{ formatDecision(method.board_original_advance_decision) }}</small>
                  </td>
                  <td>
                    <span>{{ method.method_family || '來源未提供' }} · {{ method.method_type || '來源未提供' }}</span>
                    <strong>{{ formatResearchClass(method.research_class) }}</strong>
                    <small>{{ method.comparison_status || '來源未提供' }}</small>
                  </td>
                  <td>
                    <strong>{{ method.metrics_availability || '來源未提供' }}</strong>
                    <small>{{ method.metrics_unavailable_reason || '來源未附指標缺失原因' }}</small>
                    <small>原研究板：{{ method.original_board_metrics_availability || '來源未提供' }}</small>
                    <small>{{ method.original_board_metrics_unavailable_reason || '來源未附原研究板缺失原因' }}</small>
                  </td>
                  <td>
                    <strong v-if="isSharedOutput(method)" class="v2-shared">共享輸出 · 非獨立研究</strong>
                    <span v-else>來源未標示共享輸出</span>
                    <code v-if="method.shared_output_identity">{{ method.shared_output_identity }}</code>
                    <code v-for="identity in method.source_shared_output_identities" :key="identity">{{ identity }}</code>
                  </td>
                  <td class="v2-owner-fields">
                    <span>長名次：<code>{{ ownerField(method.owner_long_rank) }}</code></span>
                    <span>中名次：<code>{{ ownerField(method.owner_middle_rank) }}</code></span>
                    <span>短名次：<code>{{ ownerField(method.owner_short_rank) }}</code></span>
                    <span>已選擇：<code>{{ ownerField(method.owner_selected) }}</code></span>
                    <span>Owner 原因：<code>{{ ownerField(method.owner_reason) }}</code></span>
                  </td>
                  <td class="v2-source-cell">
                    <details>
                      <summary>查看來源身份與 lineage</summary>
                      <strong>source_identity</strong>
                      <pre>{{ formatIdentity(method.source_identity) }}</pre>
                      <strong>source_identity_chain</strong>
                      <pre>{{ formatIdentity(method.source_identity_chain) }}</pre>
                      <strong>source_lineage</strong>
                      <pre>{{ formatIdentity(method.source_lineage) }}</pre>
                      <strong>Artifact SHA-256</strong>
                      <code>{{ method.artifact_sha256 }}</code>
                      <strong>Backtest SHA-256</strong>
                      <code>{{ method.backtest_artifact_sha256 }}</code>
                    </details>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <div class="v2-pagination" aria-label="methods 分頁">
            <button type="button" class="v2-button" :disabled="methodsOffset === 0" @click="methodsOffset = methodsPreviousOffset">
              上一頁
            </button>
            <span>offset {{ methodsPage.offset }} · limit {{ methodsPage.limit }} · total {{ methodsPage.total }}</span>
            <button type="button" class="v2-button" :disabled="methodsNextOffset >= methodsPage.total" @click="methodsOffset = methodsNextOffset">
              下一頁
            </button>
          </div>
        </template>
      </section>

      <section
        v-else
        id="v2-rankings-panel"
        class="v2-panel"
        role="tabpanel"
        aria-labelledby="v2-rankings-tab"
      >
        <div class="v2-controls v2-ranking-controls">
          <label>
            <span>歷史 cohort</span>
            <select v-model="selectedCohort" aria-label="V2 歷史 cohort">
              <option v-for="cohort in summary.cohorts" :key="cohort" :value="cohort">{{ cohort }}</option>
            </select>
          </label>
          <label>
            <span>K 注數</span>
            <select v-model.number="selectedK" aria-label="V2 K 注數">
              <option v-for="K in summary.K_values" :key="K" :value="K">K{{ K }}</option>
            </select>
          </label>
          <label>
            <span>歷史窗口</span>
            <select v-model="selectedWindow" aria-label="V2 歷史窗口">
              <option v-for="window in summary.windows" :key="window" :value="window">{{ window }}</option>
            </select>
          </label>
          <label>
            <span>官方獎項口徑</span>
            <select v-model="selectedPrizeMetric" aria-label="V2 官方獎項口徑">
              <option v-for="metric in summary.prize_metrics" :key="metric" :value="metric">{{ metric }}</option>
            </select>
          </label>
          <label class="v2-group-select">
            <span>比較群組（draw set + 有效分母）</span>
            <select v-model="selectedGroupKey" aria-label="V2 必要比較群組" :disabled="groupState !== 'ready' || comparisonGroups.length === 0">
              <option value="">請選擇單一比較群組</option>
              <option v-for="group in comparisonGroups" :key="group.key" :value="group.key">
                {{ group.targetDrawSetIdentity }} · 有效分母 {{ group.eligibleDraws }} · {{ group.lotteryType }} · {{ group.rowCount }} 筆
              </option>
            </select>
          </label>
        </div>

        <p v-if="groupState === 'loading'" class="v2-state" role="status">
          正在逐頁讀取此 cohort／K／窗口／獎項口徑的比較群組目錄…
        </p>
        <div v-else-if="groupState === 'error'" class="v2-state v2-state--error" role="group" aria-live="assertive">
          <strong>{{ errorKind(groupError) }}</strong>
          <span>{{ groupError }}</span>
          <button type="button" class="v2-button" @click="retryRankings">重試群組目錄</button>
        </div>
        <p v-else-if="groupState === 'empty'" class="v2-state" role="status">
          此組 cohort、K、窗口及獎項口徑沒有排名資料，因此沒有可比較群組。
        </p>
        <p v-else-if="groupState === 'ready' && !selectedGroupKey" class="v2-state" role="status">
          找到 {{ comparisonGroups.length }} 個不同比較群組。請選定一個 draw set 與有效分母後再查看排名。
        </p>

        <p v-if="selectedGroup" class="v2-selected-group" aria-live="polite">
          單一群組：{{ selectedGroup.targetDrawSetIdentity }} · {{ selectedGroup.lotteryType }} ·
          有效分母 {{ selectedGroup.eligibleDraws }}。名次保留 API 原始值與順序。
        </p>

        <p v-if="rankingsState === 'loading'" class="v2-state" role="status">
          正在讀取所選比較群組的歷史排名…
        </p>
        <div v-else-if="rankingsState === 'error'" class="v2-state v2-state--error" role="group" aria-live="assertive">
          <strong>{{ errorKind(rankingsError) }}</strong>
          <span>{{ rankingsError }}</span>
          <button type="button" class="v2-button" @click="loadRankingPage">重試排名查詢</button>
        </div>
        <p v-else-if="rankingsState === 'empty'" class="v2-state" role="status">
          所選比較群組目前沒有排名資料。
        </p>

        <template v-else-if="rankingsPage && rankingsState === 'ready'">
          <div class="v2-page-summary" aria-live="polite">
            <span>排名 {{ rankingsPage.offset + 1 }}–{{ rankingsPage.offset + rankingsPage.items.length }} / {{ rankingsPage.total }}</span>
            <span>{{ rankingsPage.cohort }} · K{{ rankingsPage.K }} · {{ rankingsPage.window }} · {{ rankingsPage.prize_metric }}</span>
            <span>單一比較群組數：{{ rankingsPage.comparison_group_count }}</span>
          </div>
          <div class="v2-table-scroll" tabindex="0" aria-label="V2 歷史排名表格，可水平捲動">
            <table class="v2-table v2-ranking-table">
              <thead>
                <tr>
                  <th scope="col">API 原始名次</th>
                  <th scope="col">Method / Version / Arm</th>
                  <th scope="col">成功數 / 有效分母</th>
                  <th scope="col">歷史成功率</th>
                  <th scope="col">官方基準 / 差值</th>
                  <th scope="col">研究身份 / 決策</th>
                  <th scope="col">指標狀態</th>
                  <th scope="col">共享輸出</th>
                  <th scope="col">來源身份 / Artifact</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in rankings" :key="`${row.comparison_rank}:${row.method_id}@${row.method_version}:${row.arm_identity}`">
                  <td>
                    <strong>{{ row.comparison_rank }}</strong>
                    <small>原始來源名次：{{ row.source_rank ?? '—' }}</small>
                    <small>排名基礎身份數：{{ row.rank_basis_identity_count }}</small>
                  </td>
                  <td class="v2-identity-cell">
                    <strong>{{ row.method_id }}</strong>
                    <code>{{ row.method_version }}</code>
                    <small>{{ row.arm_identity }}</small>
                    <small>Family: {{ row.method_family }}</small>
                  </td>
                  <td><strong>{{ formatCount(row.wins) }} / {{ formatCount(row.eligible_draws) }}</strong></td>
                  <td><strong>{{ formatRate(row.success_rate) }}</strong></td>
                  <td>
                    <span>{{ row.baseline_identity || '來源未提供' }}</span>
                    <strong>基準 {{ formatRate(row.baseline_rate) }}</strong>
                    <small>差值 {{ formatDelta(row.delta_percentage_points) }}</small>
                  </td>
                  <td>
                    <strong>{{ row.research_status || '來源未提供' }}</strong>
                    <span>{{ formatResearchClass(row.research_class) }}</span>
                    <small>{{ formatDecision(row.original_advance_decision) }}</small>
                    <small>研究板原始決策：{{ formatDecision(row.board_original_advance_decision) }}</small>
                  </td>
                  <td>
                    <strong>{{ row.original_board_metrics_availability || '來源未提供' }}</strong>
                    <small>{{ row.original_board_metrics_unavailable_reason || '來源未附缺失原因' }}</small>
                    <small>{{ row.comparison_status || '來源未提供' }}</small>
                    <small>{{ row.comparison_notes || '來源未附比較備註' }}</small>
                  </td>
                  <td>
                    <strong v-if="isSharedOutput(row)" class="v2-shared">共享輸出 · 非獨立研究</strong>
                    <span v-else>來源未標示共享輸出</span>
                    <code v-if="row.shared_output_identity">{{ row.shared_output_identity }}</code>
                    <code v-for="identity in row.source_shared_output_identities" :key="identity">{{ identity }}</code>
                  </td>
                  <td class="v2-source-cell">
                    <small>來源任務：{{ row.task_id }}</small>
                    <small>Draw set：{{ row.target_draw_set_identity }}</small>
                    <small>Group：{{ selectedGroup?.targetDrawSetIdentity }} · {{ selectedGroup?.eligibleDraws }}</small>
                    <details>
                      <summary>查看 identity / lineage</summary>
                      <strong>source_identity</strong>
                      <pre>{{ formatIdentity(row.source_identity) }}</pre>
                      <strong>source_identity_chain</strong>
                      <pre>{{ formatIdentity(row.source_identity_chain) }}</pre>
                      <strong>source_lineage</strong>
                      <pre>{{ formatIdentity(row.source_lineage) }}</pre>
                      <strong>Artifact SHA-256</strong>
                      <code>{{ row.artifact_sha256 }}</code>
                    </details>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <div class="v2-pagination" aria-label="rankings 分頁">
            <button type="button" class="v2-button" :disabled="rankingsOffset === 0" @click="rankingsOffset = rankingsPreviousOffset">
              上一頁
            </button>
            <span>offset {{ rankingsPage.offset }} · limit {{ rankingsPage.limit }} · total {{ rankingsPage.total }}</span>
            <button type="button" class="v2-button" :disabled="rankingsNextOffset >= rankingsPage.total" @click="rankingsOffset = rankingsNextOffset">
              下一頁
            </button>
          </div>
        </template>
      </section>
    </template>
  </section>
</template>

<style scoped>
.v2-board { display: grid; gap: 15px; min-width: 0; margin-top: 22px; padding: 20px; border: 1px solid var(--border-color); border-radius: var(--radius-lg); background: var(--bg-card); }
.v2-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 18px; }
.v2-eyebrow { margin: 0 0 7px; color: var(--text-accent); font-size: 12px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; }
.v2-heading h2 { margin: 0; font-size: 21px; }
.v2-source-chip { padding: 7px 10px; border: 1px solid var(--border-color); border-radius: 999px; color: var(--text-secondary); font-size: 13px; white-space: nowrap; }
.v2-note { margin: 0; color: var(--text-secondary); font-size: 13px; line-height: 1.6; }
.v2-source-identity { display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: 8px 14px; padding: 12px; border: 1px solid var(--border-subtle); border-radius: var(--radius-md); background: var(--bg-tertiary); }
.v2-source-identity span { display: grid; gap: 4px; min-width: 0; }
.v2-source-identity strong, .v2-source-identity code { overflow-wrap: anywhere; }
.v2-source-identity strong { color: var(--text-secondary); font-size: 11px; }
.v2-source-identity code { font-size: 11px; }
.v2-source-identity .v2-identity-verified { align-self: center; color: var(--color-success, #86efac); font-weight: 700; }
.v2-summary { display: grid; grid-template-columns: repeat(auto-fit, minmax(115px, 1fr)); gap: 8px; margin: 0; }
.v2-summary div { padding: 10px; border: 1px solid var(--border-subtle); border-radius: var(--radius-md); background: var(--bg-tertiary); }
.v2-summary dt { color: var(--text-secondary); font-size: 11px; }
.v2-summary dd { margin: 4px 0 0; font-size: 18px; font-weight: 700; }
.v2-tabs { display: flex; flex-wrap: wrap; gap: 8px; border-bottom: 1px solid var(--border-subtle); }
.v2-tabs button { min-height: 40px; padding: 9px 13px; border: 1px solid var(--border-color); border-bottom: 0; border-radius: var(--radius-md) var(--radius-md) 0 0; background: var(--bg-tertiary); color: var(--text-secondary); font: inherit; cursor: pointer; }
.v2-tabs button[aria-selected="true"] { background: var(--bg-card); color: var(--text-primary); font-weight: 700; }
.v2-panel { display: grid; gap: 13px; min-width: 0; }
.v2-controls { display: flex; align-items: flex-end; flex-wrap: wrap; gap: 12px; }
.v2-controls label { display: grid; gap: 5px; min-width: 175px; color: var(--text-secondary); font-size: 12px; }
.v2-controls input, .v2-controls select, .v2-button { min-height: 38px; padding: 9px 11px; border: 1px solid var(--border-color); border-radius: var(--radius-md); background: var(--bg-tertiary); color: var(--text-primary); font: inherit; }
.v2-controls input, .v2-controls select { width: 100%; }
.v2-button { cursor: pointer; }
.v2-button:disabled { cursor: wait; opacity: .6; }
.v2-group-select { flex: 1 1 340px; }
.v2-state { display: flex; align-items: center; flex-wrap: wrap; gap: 8px 12px; margin: 0; padding: 13px 15px; border: 1px solid var(--border-subtle); border-radius: var(--radius-md); background: rgba(148, 163, 184, .07); color: var(--text-secondary); }
.v2-state--error { border-color: var(--color-warning-border); background: var(--color-warning-bg); }
.v2-page-summary { display: flex; flex-wrap: wrap; gap: 8px 16px; color: var(--text-secondary); font-size: 12px; }
.v2-selected-group { margin: 0; color: var(--text-accent); font-size: 12px; overflow-wrap: anywhere; }
.v2-table-scroll { max-width: 100%; overflow: auto; border: 1px solid var(--border-subtle); border-radius: var(--radius-md); }
.v2-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.v2-method-table { min-width: 2500px; }
.v2-ranking-table { min-width: 2050px; }
.v2-table th, .v2-table td { max-width: 320px; padding: 10px 11px; border-bottom: 1px solid var(--border-subtle); text-align: left; vertical-align: top; overflow-wrap: anywhere; }
.v2-table th { position: sticky; top: 0; z-index: 1; background: var(--bg-tertiary); color: var(--text-secondary); white-space: nowrap; }
.v2-table tbody tr:last-child td { border-bottom: 0; }
.v2-table td > strong, .v2-table td > span, .v2-table td > small, .v2-table td > code { display: block; margin-top: 4px; }
.v2-table td small { color: var(--text-secondary); }
.v2-identity-cell strong, .v2-identity-cell code, .v2-source-cell code { overflow-wrap: anywhere; }
.v2-owner-fields span { display: block; margin-top: 4px; }
.v2-owner-fields code { overflow-wrap: anywhere; }
.v2-source-cell details { max-width: 400px; }
.v2-source-cell summary { cursor: pointer; color: var(--text-accent); }
.v2-source-cell pre { max-width: 360px; overflow: auto; white-space: pre-wrap; overflow-wrap: anywhere; }
.v2-shared { color: var(--color-warning, #fcd34d); }
.v2-pagination { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 10px; color: var(--text-secondary); font-size: 12px; }
@media (max-width: 700px) {
  .v2-heading { flex-direction: column; }
  .v2-source-chip { white-space: normal; }
  .v2-controls, .v2-controls label, .v2-controls .v2-button { width: 100%; }
  .v2-pagination { justify-content: stretch; }
  .v2-pagination > * { flex: 1 1 100%; text-align: center; }
}
</style>
