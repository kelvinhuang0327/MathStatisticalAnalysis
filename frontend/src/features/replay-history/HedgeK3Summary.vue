<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import {
  getHedgeK3StoredResults,
  computeHedgeK3ProvenanceMetricSummary,
  type HedgeK3StoredResult,
} from '../../api/replayBackfill'

const props = defineProps<{ runId: string; strategyVersion: string }>()
const rows = ref<HedgeK3StoredResult[]>([])
const loading = ref(false)
const error = ref('')
const retry = ref(0)

const metrics = [
  { field: 'reference_any_prize', label: '統一八獎級（研究參考）' },
  { field: 'combination_success', label: '沿用來源策略的成功旗標' },
] as const

const missingPhase = computed(() => rows.value.some(
  (row) => row.hedge_phase !== 'warmup' && row.hedge_phase !== 'evaluation',
))
const evaluation = computed(() => rows.value.filter((row) => row.hedge_phase === 'evaluation'))
const formatCount = new Intl.NumberFormat('zh-TW')
const warmupLabel = computed(() => missingPhase.value
  ? '暖機範圍未確認（API 缺少有效的 hedge_phase）'
  : `包含前 ${formatCount.format(rows.value.length - evaluation.value.length)} 期暖機`)

function metricSummary(
  scope: readonly HedgeK3StoredResult[],
  field: typeof metrics[number]['field'],
) {
  return computeHedgeK3ProvenanceMetricSummary(scope, field)
}

watch([() => props.runId, () => props.strategyVersion, retry],
  async ([runId, strategyVersion], _, onCleanup) => {
    const controller = new AbortController()
    onCleanup(() => controller.abort())
    rows.value = []
    error.value = ''
    loading.value = true
    try {
      const result = await getHedgeK3StoredResults(runId, strategyVersion, controller.signal)
      if (!controller.signal.aborted) rows.value = result
    } catch (reason) {
      if (!controller.signal.aborted) error.value = reason instanceof Error ? reason.message : '無法讀取 K3 Hedge 成功旗標。'
    } finally {
      if (!controller.signal.aborted) loading.value = false
    }
  }, { immediate: true })
</script>

<template>
  <section aria-label="K3 Hedge 成功旗標" data-testid="hedge-k3-summary">
    <h4>K3 Hedge 成功旗標</h4>
    <p v-if="loading" role="status">正在讀取這個 Run 的 K3 Hedge 成功旗標…</p>
    <p v-else-if="error" role="alert">
      {{ error }} <button class="button button--quiet" type="button" @click="retry++">重試</button>
    </p>
    <template v-else-if="rows.length">
      <p>下表涵蓋所選 Run 與版本的全部期別，兩種成功定義分開顯示。</p>
      <p class="provenance-note">
        來源驗證說明：已驗證來源單獨計算成功期數及分母；UNKNOWN 及 UNVERIFIED 來源另列數量，不得混入已驗證分母。研究參考指標不代表正式中獎認證，歷史描述不宣稱未來預測增益。
      </p>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th scope="col">成功定義</th>
              <th scope="col">全期（{{ warmupLabel }}）</th>
              <th scope="col">排除暖機後</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="metric in metrics" :key="metric.field">
              <th scope="row">{{ metric.label }}</th>
              <td :data-testid="`k3-all-${metric.field}`">
                <div class="k3-provenance-cell">
                  <div class="k3-provenance-verified">
                    <span class="label">已驗證成功率：</span>
                    <strong class="value" :data-testid="`k3-all-${metric.field}-verified`">{{ metricSummary(rows, metric.field).verified_rate_display }}</strong>
                  </div>
                  <div class="k3-provenance-raw">
                    <span class="label">原始儲存旗標：</span>
                    <span class="value" :data-testid="`k3-all-${metric.field}-raw`">{{ metricSummary(rows, metric.field).raw_flag_display }}</span>
                  </div>
                  <div class="k3-provenance-counts" :data-testid="`k3-all-${metric.field}-counts`">
                    <small>
                      來源狀態：已驗證 {{ formatCount.format(metricSummary(rows, metric.field).verified_count) }} 期 · UNKNOWN {{ formatCount.format(metricSummary(rows, metric.field).unknown_count) }} 期 · UNVERIFIED {{ formatCount.format(metricSummary(rows, metric.field).unverified_count) }} 期
                    </small>
                  </div>
                  <div v-if="metricSummary(rows, metric.field).missing_flag_count > 0" class="k3-provenance-warning">
                    <small>API 缺少有效的 {{ metric.field }}（{{ formatCount.format(metricSummary(rows, metric.field).missing_flag_count) }} 期）</small>
                  </div>
                </div>
              </td>
              <td :data-testid="`k3-eval-${metric.field}`">
                <div v-if="missingPhase" class="k3-provenance-missing-phase">
                  API 缺少有效的 hedge_phase
                </div>
                <div v-else-if="!evaluation.length" class="k3-provenance-empty">
                  無可評估期數
                </div>
                <div v-else class="k3-provenance-cell">
                  <div class="k3-provenance-verified">
                    <span class="label">已驗證成功率：</span>
                    <strong class="value" :data-testid="`k3-eval-${metric.field}-verified`">{{ metricSummary(evaluation, metric.field).verified_rate_display }}</strong>
                  </div>
                  <div class="k3-provenance-raw">
                    <span class="label">原始儲存旗標：</span>
                    <span class="value" :data-testid="`k3-eval-${metric.field}-raw`">{{ metricSummary(evaluation, metric.field).raw_flag_display }}</span>
                  </div>
                  <div class="k3-provenance-counts" :data-testid="`k3-eval-${metric.field}-counts`">
                    <small>
                      來源狀態：已驗證 {{ formatCount.format(metricSummary(evaluation, metric.field).verified_count) }} 期 · UNKNOWN {{ formatCount.format(metricSummary(evaluation, metric.field).unknown_count) }} 期 · UNVERIFIED {{ formatCount.format(metricSummary(evaluation, metric.field).unverified_count) }} 期
                    </small>
                  </div>
                  <div v-if="metricSummary(evaluation, metric.field).missing_flag_count > 0" class="k3-provenance-warning">
                    <small>API 缺少有效的 {{ metric.field }}（{{ formatCount.format(metricSummary(evaluation, metric.field).missing_flag_count) }} 期）</small>
                  </div>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
  </section>
</template>

<style scoped>
.provenance-note {
  color: var(--text-tertiary, #666);
  font-size: 13px;
  margin: 4px 0 12px;
  line-height: 1.4;
}

.k3-provenance-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.k3-provenance-verified {
  font-size: 14px;
}

.k3-provenance-verified .value {
  font-size: 15px;
  color: var(--text-primary, inherit);
}

.k3-provenance-raw {
  font-size: 13px;
  color: var(--text-secondary, #555);
}

.k3-provenance-counts {
  font-size: 12px;
  color: var(--text-tertiary, #777);
}

.k3-provenance-warning {
  font-size: 12px;
  color: var(--color-warning, #d97706);
}

.k3-provenance-missing-phase,
.k3-provenance-empty {
  font-size: 13px;
  color: var(--text-tertiary, #777);
}
</style>
