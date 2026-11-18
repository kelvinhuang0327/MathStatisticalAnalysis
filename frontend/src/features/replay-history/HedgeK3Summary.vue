<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { getHedgeK3StoredResults } from '../../api/replayBackfill'

const props = defineProps<{ runId: string; strategyVersion: string }>()
const rows = ref<Awaited<ReturnType<typeof getHedgeK3StoredResults>>>([])
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

function successCount(
  scope: typeof rows.value,
  field: typeof metrics[number]['field'],
): string {
  const missing = scope.filter((row) => typeof row[field] !== 'boolean').length
  if (missing) return `API 缺少有效的 ${field}（${formatCount.format(missing)} 期）`
  if (!scope.length) return '無可評估期數'
  return `${formatCount.format(scope.filter((row) => row[field] === true).length)}/${formatCount.format(scope.length)}`
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
              <td>{{ successCount(rows, metric.field) }}</td>
              <td>{{ missingPhase ? 'API 缺少有效的 hedge_phase' : successCount(evaluation, metric.field) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
  </section>
</template>
