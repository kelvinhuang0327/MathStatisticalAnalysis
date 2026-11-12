<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'

import {
  B649Sealed084RequestError,
  fetchB649Sealed084ReplayStatus,
  fetchB649Sealed084Replays,
  formatRatePercentage,
  type B649Sealed084ReplayResponse,
  type B649Sealed084ReplayStatus,
} from '../../api/rankingMatrix'
import {
  getSealed084CommonComparison,
  getSealed084NativeCell,
  SEALED_084_STRATEGIES,
  SEALED_084_WINDOWS,
  serializeSealed084ManualReviewCsv,
  type Sealed084NativeCell,
} from './sealed084Research'
import { SEALED_084_COMMON_COMPARISON_SOURCE } from './sealed084ComparisonEvidence'

type PanelState = 'loading' | 'ready' | 'source_unavailable' | 'error'

const props = defineProps<{ enabled: boolean }>()
const panelState = ref<PanelState>('loading')
const sourceStatus = ref<B649Sealed084ReplayStatus | null>(null)
const replayResponse = ref<B649Sealed084ReplayResponse | null>(null)
const errorMessage = ref('')
let requestController: AbortController | undefined
let loadedOnce = false

const sourceReady = computed(() =>
  panelState.value === 'ready' &&
  sourceStatus.value?.status === 'READY' &&
  replayResponse.value?.status === 'READY',
)

const strategyRows = computed(() => SEALED_084_STRATEGIES.map((strategy) => ({
  strategy,
  cells: SEALED_084_WINDOWS.map((window) => ({
    window,
    native: getSealed084NativeCell(
      replayResponse.value?.results ?? [],
      strategy,
      window.key,
      sourceReady.value,
      sourceStatus.value,
    ),
    common: getSealed084CommonComparison(strategy, window.key),
  })),
})))

const unavailableCellCount = computed(() => strategyRows.value.reduce(
  (count, row) => count + row.cells.filter((cell) => cell.native.status !== 'READY').length,
  0,
))

const unexpectedRowCount = computed(() => {
  const results = replayResponse.value?.results ?? []
  return results.filter((result) => !SEALED_084_STRATEGIES.some((strategy) =>
    strategy.strategyId === result.strategy_id &&
    strategy.ticketCount === result.ticket_count &&
    strategy.strategyVersion === result.strategy_version,
  )).length
})

async function loadReplay(): Promise<void> {
  requestController?.abort()
  requestController = new AbortController()
  const controller = requestController
  panelState.value = 'loading'
  errorMessage.value = ''

  const [statusResult, replayResult] = await Promise.allSettled([
    fetchB649Sealed084ReplayStatus(controller.signal),
    fetchB649Sealed084Replays(controller.signal),
  ])
  if (controller.signal.aborted) return

  sourceStatus.value = statusResult.status === 'fulfilled' ? statusResult.value : null
  replayResponse.value = replayResult.status === 'fulfilled' ? replayResult.value : null

  if (statusResult.status === 'rejected' || replayResult.status === 'rejected') {
    const errors = [statusResult, replayResult]
      .filter((result): result is PromiseRejectedResult => result.status === 'rejected')
      .map((result) => result.reason)
    const unavailable = errors.some((error) =>
      error instanceof B649Sealed084RequestError && error.kind === 'SOURCE_UNAVAILABLE',
    )
    errorMessage.value = errors[0] instanceof Error
      ? errors[0].message
      : '084 封存研究來源狀態無法讀取。'
    panelState.value = unavailable ? 'source_unavailable' : 'error'
    return
  }

  if (sourceStatus.value?.status !== 'READY' || replayResponse.value?.status !== 'READY') {
    errorMessage.value = '084 封存研究來源尚未就緒；原生指標暫不顯示。'
    panelState.value = 'source_unavailable'
    return
  }

  panelState.value = 'ready'
}

function cellStatusLabel(cell: Sealed084NativeCell): string {
  switch (cell.status) {
    case 'SOURCE_UNAVAILABLE': return panelState.value === 'loading' ? '讀取來源中' : '來源不可用／未核實'
    case 'NO_DATA': return '此窗口無資料'
    case 'VERSION_MISMATCH': return '版本不符；指標不顯示'
    case 'INVALID_DATA': return '指標資料無效；指標不顯示'
    case 'DUPLICATE_DATA': return '窗口重複；指標不顯示'
    case 'READY': return '可用'
  }
}

function formatRateDifference(nativeRate: number, commonRateText: string): string {
  const commonRate = Number(commonRateText)
  if (!Number.isFinite(commonRate)) return 'Unavailable'
  const points = (nativeRate - commonRate) * 100
  return `${points > 0 ? '+' : ''}${points.toFixed(2)} 個百分點`
}

function formatStaticRateDifference(rateText: string): string {
  const points = Number(rateText) * 100
  if (!Number.isFinite(points)) return 'Unavailable'
  return `${points > 0 ? '+' : ''}${points.toFixed(2)} 個百分點`
}

function downloadManualReviewCsv(): void {
  const csv = serializeSealed084ManualReviewCsv(
    replayResponse.value?.results ?? [],
    sourceStatus.value,
    sourceReady.value,
  )
  const blob = new Blob([`\uFEFF${csv}`], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = 'b649-sealed-084-manual-review.csv'
  link.click()
  window.setTimeout(() => URL.revokeObjectURL(url), 0)
}

watch(() => props.enabled, (enabled) => {
  if (!enabled || loadedOnce) return
  loadedOnce = true
  void loadReplay()
}, { immediate: true })

onBeforeUnmount(() => {
  requestController?.abort()
})
</script>

<template>
  <section class="sealed-084-panel" aria-labelledby="sealed-084-heading" data-testid="sealed-084-panel">
    <header class="sealed-084-panel__header">
      <div>
        <p class="sealed-084-panel__eyebrow">獨立研究回放 · BIG_LOTTO</p>
        <h2 id="sealed-084-heading">084 封存歷史研究回放</h2>
        <p class="sealed-084-panel__intro">
          本區讀取封存 084 研究資料，與 099 正式標準排名分開。這些回測描述歷史結果，不會自動產生正式名次、冠軍或採納決定。
        </p>
      </div>
      <div class="sealed-084-panel__actions">
        <button type="button" data-testid="sealed-084-retry" @click="loadReplay">重新讀取來源</button>
        <button type="button" data-testid="sealed-084-export" @click="downloadManualReviewCsv">匯出人工審閱 CSV</button>
      </div>
    </header>

    <section class="sealed-084-source" aria-label="084 API 來源狀態" data-testid="sealed-084-source-status">
      <div class="sealed-084-source__summary">
        <strong>API 來源狀態：</strong>
        <span v-if="panelState === 'loading'">讀取中</span>
        <span v-else-if="panelState === 'ready'">{{ sourceStatus?.status }} · {{ sourceStatus?.game }} · 截止 {{ sourceStatus?.source_cutoff }} · {{ sourceStatus?.source_tier }}</span>
        <span v-else>SOURCE_UNAVAILABLE · 084 原生指標不會填入 099 正式排名</span>
        <span v-if="sourceStatus?.status === 'READY'"> · {{ sourceStatus.strategy_count }} 個策略／{{ sourceStatus.returned_window_rows }} 個窗口結果</span>
      </div>
      <p v-if="errorMessage" class="sealed-084-state-message" role="status">{{ errorMessage }}</p>
      <p v-if="panelState === 'ready' && unavailableCellCount" class="sealed-084-state-message" role="status">
        {{ unavailableCellCount }} / 28 個原生窗口格目前沒有可驗證數值；空格不會顯示成 0%。
      </p>
      <p v-if="unexpectedRowCount" class="sealed-084-state-message" role="status">
        API 回傳 {{ unexpectedRowCount }} 筆不符合本頁策略版本的資料，已排除其指標。
      </p>
      <details v-if="sourceStatus?.sources.length" class="sealed-084-source__details">
        <summary>來源核驗狀態與限制</summary>
        <ul>
          <li v-for="source in sourceStatus.sources" :key="source.source_task_id">
            <strong>{{ source.source_task_id }}</strong>
            <span>來源核驗：{{ source.source_validation_status }}</span>
            <span>開獎來源：{{ source.draw_source_status }}</span>
            <span>DRAW_DATA_V3：{{ source.original_draw_data_v3_status }}</span>
            <span v-if="source.source_gaps">來源缺口：{{ source.source_gaps }}</span>
          </li>
        </ul>
      </details>
    </section>

    <div class="sealed-084-table-wrap">
      <table class="sealed-084-table">
        <caption>7 個封存策略 × 4 個原生窗口；每格同時列出 API 原生結果與共同 issue 集合的靜態比較證據。</caption>
        <thead>
          <tr>
            <th scope="col">研究策略／K／版本</th>
            <th v-for="window in SEALED_084_WINDOWS" :key="window.key" scope="col">
              {{ window.label }}
              <span v-if="window.key === 'FULL'">（原生 FULL）</span>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="strategyRow in strategyRows" :key="strategyRow.strategy.strategyId" :data-testid="`sealed-084-strategy-${strategyRow.strategy.strategyId}`">
            <th scope="row" class="sealed-084-strategy">
              <code>{{ strategyRow.strategy.strategyId }}</code>
              <span>K{{ strategyRow.strategy.ticketCount }} · {{ strategyRow.strategy.strategyVersion }}</span>
            </th>
            <td v-for="cell in strategyRow.cells" :key="cell.window.key">
              <div class="sealed-084-cell" :data-testid="`sealed-084-cell-${strategyRow.strategy.strategyId}-${cell.window.key}`">
                <template v-if="cell.native.status === 'READY'">
                  <div class="sealed-084-native-metric">
                    <strong>原生</strong>
                    <span>{{ cell.native.result.successful_issues }} / {{ cell.native.result.evaluated_issues }}</span>
                    <span>{{ formatRatePercentage(cell.native.result.success_rate) }}</span>
                  </div>
                  <p class="sealed-084-comparability">API 比較狀態：{{ cell.native.result.comparability_status }}</p>
                  <template v-if="cell.common">
                    <div class="sealed-084-common-metric">
                      <strong>同 K 同期靜態比較</strong>
                      <span>{{ cell.common.successfulIssues }} / {{ cell.common.comparableIssueCount }}</span>
                      <span>{{ formatRatePercentage(Number(cell.common.successRate)) }}</span>
                      <small>共同窗口：{{ cell.common.comparisonWindow }}</small>
                    </div>
                    <p class="sealed-084-comparability">靜態比較口徑：{{ cell.common.comparabilityStatus }}</p>
                    <p class="sealed-084-period-note">
                      原生分母 {{ cell.native.result.evaluated_issues }} 期；共同 issue 集合 {{ cell.common.comparableIssueCount }} 期。
                      原生率 − 同期率：{{ formatRateDifference(cell.native.result.success_rate, cell.common.successRate) }}。
                    </p>
                    <details v-if="cell.common.peers.length" class="sealed-084-peers">
                      <summary>配對差異（{{ cell.common.peers.length }} 組）</summary>
                      <ul>
                        <li v-for="peer in cell.common.peers" :key="peer.strategyId">
                          本策略 {{ cell.common.successfulIssues }} / {{ cell.common.comparableIssueCount }}；
                          {{ peer.strategyId }} {{ peer.successfulIssues }} / {{ cell.common.comparableIssueCount }}；
                          計數差 {{ peer.successCountDifference > 0 ? '+' : '' }}{{ peer.successCountDifference }}，率差 {{ formatStaticRateDifference(peer.successRateDifference) }}。
                        </li>
                      </ul>
                    </details>
                  </template>
                </template>
                <span v-else class="sealed-084-cell-state">{{ cellStatusLabel(cell.native) }}</span>
                <div v-if="cell.common && cell.native.status !== 'READY'" class="sealed-084-common-metric">
                  <strong>同 K 同期靜態比較</strong>
                  <span>{{ cell.common.successfulIssues }} / {{ cell.common.comparableIssueCount }}</span>
                  <span>{{ formatRatePercentage(Number(cell.common.successRate)) }}</span>
                  <small>共同窗口：{{ cell.common.comparisonWindow }}</small>
                </div>
                <p v-if="cell.common && cell.native.status !== 'READY'" class="sealed-084-comparability">靜態比較口徑：{{ cell.common.comparabilityStatus }}</p>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <footer class="sealed-084-footnote">
      <p>
        同期比較取自靜態人工比較快照 {{ SEALED_084_COMMON_COMPARISON_SOURCE.file }}（SHA-256 {{ SEALED_084_COMMON_COMPARISON_SOURCE.sha256 }}）；它不代表 API 即時重算或綜合排名。
      </p>
      <p>K2 Horizon 的原生 FULL 為 1966 期；K2 Renewal、Conditional TE 原生 FULL 為 1416 期。FULL 期別集合不同時不可直接視為同期 FULL；表格保留原生分母並另列共同 issue 交集。</p>
      <p>CSV 只供人工檢視與自行填寫；Owner 名次、理由及採納欄位保持空白，本頁沒有排名儲存功能。</p>
    </footer>
  </section>
</template>

<style scoped>
.sealed-084-panel {
  display: grid;
  gap: 1rem;
  margin: 1.5rem 0;
  padding: 1.25rem;
  border: 1px solid #c7d2fe;
  border-radius: 1rem;
  background: #f8faff;
  color: #172033;
}

.sealed-084-panel__header,
.sealed-084-source__summary {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
}

.sealed-084-panel__eyebrow {
  margin: 0 0 0.25rem;
  color: #4338ca;
  font-size: 0.78rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.sealed-084-panel h2 {
  margin: 0;
  font-size: 1.25rem;
}

.sealed-084-panel__intro,
.sealed-084-footnote p {
  margin: 0.4rem 0 0;
  color: #475569;
  font-size: 0.88rem;
  line-height: 1.5;
}

.sealed-084-panel__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.sealed-084-panel button {
  padding: 0.55rem 0.75rem;
  border: 1px solid #6366f1;
  border-radius: 0.55rem;
  background: #fff;
  color: #3730a3;
  font: inherit;
  font-size: 0.85rem;
  font-weight: 650;
  cursor: pointer;
}

.sealed-084-panel button:hover {
  background: #eef2ff;
}

.sealed-084-source {
  padding: 0.8rem 1rem;
  border-left: 4px solid #4f46e5;
  border-radius: 0.35rem;
  background: #eef2ff;
  font-size: 0.87rem;
}

.sealed-084-source__summary {
  justify-content: flex-start;
  flex-wrap: wrap;
}

.sealed-084-state-message {
  margin: 0.55rem 0 0;
  color: #9a3412;
}

.sealed-084-source__details {
  margin-top: 0.65rem;
}

.sealed-084-source__details ul,
.sealed-084-peers ul {
  display: grid;
  gap: 0.45rem;
  margin: 0.6rem 0 0;
  padding-left: 1.2rem;
}

.sealed-084-source__details li {
  display: grid;
  gap: 0.18rem;
  overflow-wrap: anywhere;
}

.sealed-084-table-wrap {
  overflow-x: auto;
}

.sealed-084-table {
  width: 100%;
  min-width: 1120px;
  border-collapse: collapse;
  font-size: 0.82rem;
}

.sealed-084-table caption {
  padding: 0.5rem;
  color: #475569;
  text-align: left;
}

.sealed-084-table th,
.sealed-084-table td {
  padding: 0.65rem;
  border: 1px solid #dbe2ef;
  vertical-align: top;
  text-align: left;
}

.sealed-084-table thead th {
  background: #e8edff;
  color: #312e81;
}

.sealed-084-strategy {
  width: 210px;
  min-width: 210px;
  background: #f1f5f9;
}

.sealed-084-strategy code {
  display: block;
  overflow-wrap: anywhere;
  font-size: 0.76rem;
}

.sealed-084-strategy span,
.sealed-084-common-metric small {
  display: block;
  margin-top: 0.25rem;
  color: #64748b;
  font-weight: 400;
}

.sealed-084-cell {
  display: grid;
  min-width: 195px;
  gap: 0.35rem;
}

.sealed-084-native-metric,
.sealed-084-common-metric {
  display: grid;
  grid-template-columns: auto 1fr auto;
  gap: 0.3rem 0.5rem;
  align-items: baseline;
}

.sealed-084-native-metric strong {
  color: #1e3a8a;
}

.sealed-084-common-metric {
  padding-top: 0.4rem;
  border-top: 1px dashed #cbd5e1;
}

.sealed-084-common-metric strong {
  grid-column: 1 / -1;
  color: #475569;
  font-size: 0.76rem;
}

.sealed-084-common-metric small {
  grid-column: 1 / -1;
}

.sealed-084-comparability,
.sealed-084-period-note {
  margin: 0;
  color: #64748b;
  font-size: 0.74rem;
  overflow-wrap: anywhere;
}

.sealed-084-cell-state {
  color: #9a3412;
  font-weight: 650;
}

.sealed-084-peers {
  color: #334155;
  font-size: 0.75rem;
}

.sealed-084-footnote {
  display: grid;
  gap: 0.2rem;
  border-top: 1px solid #dbe2ef;
  padding-top: 0.65rem;
}

@media (max-width: 760px) {
  .sealed-084-panel__header {
    display: grid;
  }
}
</style>
