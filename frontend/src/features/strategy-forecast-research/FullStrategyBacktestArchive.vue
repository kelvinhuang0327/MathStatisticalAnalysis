<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import {
  countArchiveStatuses,
  fetchFullStrategyBacktestArchive,
  filterFullStrategyArchiveRecords,
  formatFullStrategyArchiveCount,
  formatFullStrategyArchiveDelta,
  formatFullStrategyArchiveRate,
  getFullStrategyArchiveMetrics,
  isFullStrategyArchiveLowCoverage,
  isFullStrategyArchiveLowSample,
  type FullStrategyArchivePerformanceFilter,
  type FullStrategyArchiveStatusFilter,
} from './fullStrategyArchive'
import type { B649MultiTicketRecord } from '../../api/b649MultiTicketRecords'

const records = ref<B649MultiTicketRecord[]>([])
const total = ref(0)
const state = ref<'loading' | 'ready' | 'empty' | 'error'>('loading')
const errorMessage = ref('')
const statusFilter = ref<FullStrategyArchiveStatusFilter>('ALL')
const performanceFilter = ref<FullStrategyArchivePerformanceFilter>('ALL')

let requestController: AbortController | null = null
let requestGeneration = 0

const visibleRecords = computed(() =>
  filterFullStrategyArchiveRecords(
    records.value,
    statusFilter.value,
    performanceFilter.value,
  ),
)
const statusCounts = computed(() => countArchiveStatuses(records.value))

async function loadArchive(): Promise<void> {
  requestController?.abort()
  const controller = new AbortController()
  requestController = controller
  const generation = ++requestGeneration
  records.value = []
  total.value = 0
  errorMessage.value = ''
  state.value = 'loading'

  try {
    const snapshot = await fetchFullStrategyBacktestArchive(controller.signal)
    if (generation !== requestGeneration) return
    records.value = snapshot.records
    total.value = snapshot.total
    state.value = snapshot.total === 0 ? 'empty' : 'ready'
  } catch (error) {
    if (controller.signal.aborted || (error instanceof Error && error.name === 'AbortError')) {
      return
    }
    if (generation !== requestGeneration) return
    records.value = []
    total.value = 0
    errorMessage.value = error instanceof Error ? error.message : '未知查詢錯誤。'
    state.value = 'error'
  } finally {
    if (requestController === controller) requestController = null
  }
}

function statusDescription(record: B649MultiTicketRecord): string {
  if (record.reproduction_status === 'BACKTESTED') return '已完成歷史回測'
  if (record.reproduction_status === 'CLOSED_UNEXECUTABLE') return '無法執行；不是回測失敗'
  return '重複別名；不列為獨立回測'
}

function metricUnavailableReason(record: B649MultiTicketRecord): string {
  if (record.metrics_unavailable_reason) return record.metrics_unavailable_reason
  if (record.reproduction_status === 'CLOSED_UNEXECUTABLE') {
    return '未完成可執行回測；來源沒有獨立成功率。'
  }
  if (record.reproduction_status === 'DUPLICATE_ALIAS') {
    return '此方法是重複別名，不作為獨立回測。'
  }
  return '來源未提供完整數值或有效成功執行分母。'
}

function unavailableExecutionReason(record: B649MultiTicketRecord): string {
  if (record.unranked_reason) return record.unranked_reason
  if (record.reproduction_status === 'CLOSED_UNEXECUTABLE') return 'API 未提供無法執行原因。'
  if (record.reproduction_status === 'DUPLICATE_ALIAS') return 'API 未提供重複原因。'
  return '無來源未排名原因。'
}

function windowStatus(record: B649MultiTicketRecord): string {
  if (record.window_complete === true) return '完整'
  if (record.window_complete === false) return '不完整'
  return 'API 未提供'
}

function isPositiveDelta(record: B649MultiTicketRecord): boolean {
  const metrics = getFullStrategyArchiveMetrics(record)
  return metrics !== null && metrics.delta > 0
}

onMounted(() => {
  void loadArchive()
})

onBeforeUnmount(() => {
  requestController?.abort()
})
</script>

<template>
  <section class="archive-panel" aria-labelledby="full-strategy-archive-title">
    <div class="archive-heading">
      <div>
        <p class="archive-eyebrow">獨立回測紀錄索引</p>
        <h2 id="full-strategy-archive-title">全策略回測紀錄</h2>
      </div>
      <span class="archive-source-chip">B649 · K15 · FULL · M3_PLUS</span>
    </div>

    <p class="archive-note">
      預設列出此來源維度的全部策略，不按表現刪除紀錄。M3_PLUS 數值直接採用同一歷史事件來源；成功數 / 成功執行期數使用
      <code>success_count / successful_execution_count</code>。<code>effective_backtest_draw_count</code>
      另列為來源的縮減比率分母，不代表官方事件原始觀測期數。表現篩選只作描述性查詢，不代表正式策略資格或 OOS 預測增益。
    </p>

    <div class="archive-controls">
      <label>
        <span>回測狀態</span>
        <select v-model="statusFilter" aria-label="全策略回測狀態篩選">
          <option value="ALL">ALL</option>
          <option value="BACKTESTED">BACKTESTED</option>
          <option value="CLOSED_UNEXECUTABLE">CLOSED_UNEXECUTABLE</option>
          <option value="DUPLICATE_ALIAS">DUPLICATE_ALIAS</option>
        </select>
      </label>
      <label>
        <span>描述性表現</span>
        <select v-model="performanceFilter" aria-label="全策略描述性表現篩選">
          <option value="ALL">ALL</option>
          <option value="ABOVE_RANDOM">ABOVE_RANDOM</option>
          <option value="AT_RANDOM">AT_RANDOM</option>
          <option value="BELOW_RANDOM">BELOW_RANDOM</option>
          <option value="METRIC_UNAVAILABLE">METRIC_UNAVAILABLE</option>
        </select>
      </label>
      <button class="archive-button" type="button" :disabled="state === 'loading'" @click="loadArchive">
        {{ state === 'loading' ? '讀取中…' : '重新查詢' }}
      </button>
      <a class="archive-history-link" href="#/b649-multi-ticket-records">
        查詢其他 K／窗口／criterion
      </a>
    </div>

    <p v-if="state === 'loading'" class="archive-state" role="status">
      正在讀取全策略回測紀錄並完成所有分頁…
    </p>
    <div v-else-if="state === 'error'" class="archive-state archive-state--error" role="group" aria-live="assertive">
      回測紀錄查詢失敗：{{ errorMessage }}目前沒有顯示先前查詢的資料。
    </div>
    <p v-else-if="state === 'empty'" class="archive-state" role="status">
      查詢成功，但 B649 · K15 · FULL · M3_PLUS 來源目前沒有策略紀錄。
    </p>

    <template v-else-if="state === 'ready'">
      <div class="archive-summary" aria-live="polite">
        <span>顯示 {{ visibleRecords.length }} / {{ total }} 筆，保留 API 原始順序。</span>
        <span>已回測 {{ statusCounts.BACKTESTED }}</span>
        <span>無法執行 {{ statusCounts.CLOSED_UNEXECUTABLE }}</span>
        <span>重複別名 {{ statusCounts.DUPLICATE_ALIAS }}</span>
      </div>
      <p v-if="visibleRecords.length === 0" class="archive-state" role="status">
        目前篩選沒有符合的紀錄；來源仍完整載入 {{ records.length }} / {{ total }} 筆。
      </p>

      <div v-else class="archive-table-scroll" tabindex="0" aria-label="全策略回測紀錄表格，可水平捲動">
        <table>
          <thead>
            <tr>
              <th scope="col">Strategy ID / Version</th>
              <th scope="col">Reproduction Status</th>
              <th scope="col">Source</th>
              <th scope="col">Historical Event</th>
              <th scope="col">Numerator / Denominator</th>
              <th scope="col">Actual Rate</th>
              <th scope="col">Random Baseline</th>
              <th scope="col">Delta</th>
              <th scope="col">Coverage</th>
              <th scope="col">Sample / Execution</th>
              <th scope="col">Unavailable Reason</th>
              <th scope="col">Alias Target</th>
              <th scope="col">Report Identity</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="record in visibleRecords"
              :key="`${record.strategy_id}@${record.strategy_version}`"
              :data-testid="`archive-row-${record.strategy_id}`"
            >
              <td class="archive-identity">
                <strong>{{ record.strategy_id }}</strong>
                <code>Version {{ record.strategy_version }}</code>
                <span>{{ record.legacy_method_id }}</span>
              </td>
              <td class="archive-status">
                <strong>{{ record.reproduction_status }}</strong>
                <small>{{ statusDescription(record) }}</small>
                <small>成功執行期數：{{ formatFullStrategyArchiveCount(record.successful_execution_count) }}</small>
              </td>
              <td class="archive-source">
                <code>{{ record.source_path }}</code>
                <span>Method family: {{ record.method_family }}</span>
                <small>Authority: {{ record.authority_mode ?? '不可用' }}</small>
              </td>
              <td>
                <strong>B649 · K{{ record.prefix_count }}</strong>
                <code>{{ record.window }} · {{ record.criterion }}</code>
              </td>
              <td>
                <strong v-if="getFullStrategyArchiveMetrics(record)">
                  {{ getFullStrategyArchiveMetrics(record)?.numerator }} /
                  {{ getFullStrategyArchiveMetrics(record)?.denominator }}
                </strong>
                <strong v-else class="unavailable">不可用</strong>
                <small>success_count / successful_execution_count</small>
                <small>
                  縮減比率分母：{{ formatFullStrategyArchiveCount(record.effective_backtest_draw_count) }}
                  （非原始觀測期數）
                </small>
              </td>
              <td>
                <span v-if="getFullStrategyArchiveMetrics(record)">
                  {{ formatFullStrategyArchiveRate(record.historical_success_rate) }}
                </span>
                <span v-else class="unavailable">不可用</span>
              </td>
              <td>
                <span v-if="getFullStrategyArchiveMetrics(record)">
                  {{ formatFullStrategyArchiveRate(record.random_baseline_success_rate) }}
                </span>
                <span v-else class="unavailable">不可用</span>
              </td>
              <td :class="{ 'archive-positive': isPositiveDelta(record) }">
                <span v-if="getFullStrategyArchiveMetrics(record)">
                  {{ formatFullStrategyArchiveDelta(record.random_baseline_rate_difference) }}
                </span>
                <span v-else class="unavailable">不可用</span>
                <small v-if="getFullStrategyArchiveMetrics(record)" class="descriptive-label">
                  描述性比較
                </small>
              </td>
              <td>
                {{ formatFullStrategyArchiveRate(record.coverage) }}
                <small v-if="isFullStrategyArchiveLowCoverage(record)" class="warning-label">低覆蓋率 (&lt;10%)</small>
              </td>
              <td class="archive-sample">
                <span>
                  成功執行：{{ formatFullStrategyArchiveCount(record.successful_execution_count) }}
                </span>
                <span>
                  來源可用 / 要求期數：{{ formatFullStrategyArchiveCount(record.window_available_draws) }} /
                  {{ formatFullStrategyArchiveCount(record.window_requested_draws) }}
                </span>
                <span>窗口：{{ windowStatus(record) }}</span>
                <span v-if="isFullStrategyArchiveLowSample(record)" class="warning-label">
                  低樣本（成功執行期數 &lt; 50）
                </span>
              </td>
              <td class="archive-reasons">
                <span><strong>指標：</strong>{{ metricUnavailableReason(record) }}</span>
                <span><strong>未排名／執行：</strong>{{ unavailableExecutionReason(record) }}</span>
              </td>
              <td>
                <code v-if="record.duplicate_alias_target">{{ record.duplicate_alias_target }}</code>
                <span v-else>—</span>
                <small v-if="record.reproduction_status === 'DUPLICATE_ALIAS'">
                  非獨立回測
                </small>
              </td>
              <td class="archive-report-identity">
                <small>report_sha256</small>
                <code>{{ record.report_sha256 ?? '不可用' }}</code>
                <small>report_file_sha256</small>
                <code>{{ record.report_file_sha256 ?? '不可用' }}</code>
                <small>catalog_sha256</small>
                <code>{{ record.catalog_sha256 }}</code>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
  </section>
</template>

<style scoped>
.archive-panel { display: grid; gap: 15px; min-width: 0; padding: 20px; border: 1px solid var(--border-color); border-radius: var(--radius-lg); background: var(--bg-card); }
.archive-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 18px; }
.archive-eyebrow { margin: 0 0 7px; color: var(--text-accent); font-size: 12px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; }
.archive-heading h2 { margin: 0; font-size: 21px; }
.archive-source-chip { padding: 7px 10px; border: 1px solid var(--border-color); border-radius: 999px; color: var(--text-secondary); font-size: 13px; white-space: nowrap; }
.archive-note { margin: 0; color: var(--text-secondary); font-size: 13px; line-height: 1.6; }
.archive-note code { overflow-wrap: anywhere; }
.archive-controls { display: flex; align-items: flex-end; flex-wrap: wrap; gap: 12px; }
.archive-controls label { display: grid; gap: 5px; color: var(--text-secondary); font-size: 12px; }
.archive-controls select, .archive-button, .archive-history-link { min-height: 38px; padding: 9px 11px; border: 1px solid var(--border-color); border-radius: var(--radius-md); background: var(--bg-tertiary); color: var(--text-primary); font: inherit; }
.archive-controls select { min-width: 210px; }
.archive-button { cursor: pointer; }
.archive-button:disabled { cursor: wait; opacity: .65; }
.archive-history-link { display: inline-flex; align-items: center; color: var(--text-accent); text-decoration: none; }
.archive-history-link:hover { text-decoration: underline; }
.archive-state { margin: 0; padding: 13px 15px; border: 1px solid var(--border-subtle); border-radius: var(--radius-md); background: rgba(148, 163, 184, .07); color: var(--text-secondary); }
.archive-state--error { border-color: var(--color-warning-border); background: var(--color-warning-bg); }
.archive-summary { display: flex; flex-wrap: wrap; gap: 8px 16px; color: var(--text-secondary); font-size: 12px; }
.archive-table-scroll { max-width: 100%; overflow: auto; border: 1px solid var(--border-subtle); border-radius: var(--radius-md); }
table { width: 100%; min-width: 2050px; border-collapse: collapse; font-size: 12px; }
th, td { max-width: 290px; padding: 10px 11px; border-bottom: 1px solid var(--border-subtle); text-align: left; vertical-align: top; overflow-wrap: anywhere; }
th { position: sticky; top: 0; z-index: 1; background: var(--bg-tertiary); color: var(--text-secondary); white-space: nowrap; }
tbody tr:last-child td { border-bottom: 0; }
.archive-identity, .archive-source, .archive-status, .archive-sample, .archive-reasons, .archive-report-identity { display: table-cell; }
.archive-identity strong, .archive-identity code, .archive-identity span, .archive-source code, .archive-source span, .archive-source small, .archive-status small, .archive-sample span, .archive-reasons span, .archive-report-identity small, .archive-report-identity code { display: block; margin-top: 4px; }
.archive-identity strong, .archive-source code, .archive-report-identity code { overflow-wrap: anywhere; }
.archive-status small, .archive-source small, td small { color: var(--text-secondary); }
.unavailable { color: var(--text-tertiary); }
.warning-label { display: block; margin-top: 4px; color: var(--color-warning, #fcd34d); }
.archive-positive { color: var(--color-success, #86efac); }
.descriptive-label { display: block; color: var(--text-accent); }
@media (max-width: 700px) {
  .archive-heading { flex-direction: column; }
  .archive-source-chip { white-space: normal; }
  .archive-controls, .archive-controls label, .archive-controls select, .archive-button, .archive-history-link { width: 100%; }
}
</style>
