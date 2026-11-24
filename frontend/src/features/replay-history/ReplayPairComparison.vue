<script setup lang="ts">
import { onBeforeUnmount, ref } from 'vue'
import { compareReplayRuns, type PairComparison, type ReplaySelection } from './replayPairComparison'

const left = ref<ReplaySelection>({ runId: '', strategyId: 'research_biglotto__quick_ml_pattern_bounds_v1', strategyVersion: 'v0.1-research' })
const right = ref<ReplaySelection>({ runId: '', strategyId: 'legacy_biglotto__biglotto_2bet_final__7eaedb330a07', strategyVersion: 'v0.1' })
const windowSize = ref<50 | 300 | 750 | 'ALL'>('ALL')
const loading = ref(false)
const result = ref<PairComparison | null>(null)
const error = ref('')
let controller: AbortController | undefined

async function compare(): Promise<void> {
  controller?.abort()
  const current = new AbortController()
  controller = current
  loading.value = true
  result.value = null
  error.value = ''
  try {
    const value = await compareReplayRuns({ ...left.value }, { ...right.value }, windowSize.value, current.signal)
    if (!current.signal.aborted) result.value = value
  } catch (cause) {
    if (!current.signal.aborted) error.value = cause instanceof Error ? cause.message : '無法讀取比較資料。'
  } finally {
    if (!current.signal.aborted) loading.value = false
  }
}

onBeforeUnmount(() => controller?.abort())
</script>

<template>
  <section class="panel" aria-labelledby="replay-pair-title" data-testid="replay-pair-comparison">
    <h3 id="replay-pair-title">兩注策略共同期別比較</h3>
    <p>使用兩個指定 Run 的大樂透結果；只比較同一期、相同歷史與已驗證資料，任一策略失敗的期別會列為缺漏。</p>
    <form class="filter-panel" @submit.prevent="compare">
      <div class="filter-grid">
        <fieldset v-for="(selection, index) in [left, right]" :key="index">
          <legend>{{ index === 0 ? '候選策略' : '比較基準' }}</legend>
          <label><span>策略 ID</span><input v-model.trim="selection.strategyId" required /></label>
          <label><span>版本</span><input v-model.trim="selection.strategyVersion" required /></label>
          <label><span>Run ID</span><input v-model.trim="selection.runId" required /></label>
        </fieldset>
        <label><span>共同期別範圍</span>
          <select v-model="windowSize"><option value="ALL">全部</option><option :value="750">最近 750</option><option :value="300">最近 300</option><option :value="50">最近 50</option></select>
        </label>
      </div>
      <button class="button button--primary" type="submit" :disabled="loading">{{ loading ? '比較中…' : '比較成功率' }}</button>
    </form>
    <p v-if="error" role="alert">{{ error }}</p>
    <div v-if="result" data-testid="replay-pair-results">
      <p>{{ result.firstDate }} 至 {{ result.lastDate }}：共同 {{ result.sharedTargets }} 期，可評估 {{ result.evaluated }} 期，排除 {{ result.excluded }} 期；候選單獨 {{ result.leftOnlyTargets }} 期、基準單獨 {{ result.rightOnlyTargets }} 期。</p>
      <p v-if="result.excluded">排除原因：{{ Object.entries(result.reasons).map(([reason, count]) => `${reason} ${count} 期`).join('、') }}</p>
      <table><caption>每期兩注、任一注中任一獎項；排名僅限這兩個指定 Run</caption>
        <thead><tr><th scope="col">名次</th><th scope="col">策略與版本</th><th scope="col">成功期數／評估期數</th><th scope="col">成功率</th></tr></thead>
        <tbody><tr v-for="row in result.rows" :key="`${row.strategyId}@${row.strategyVersion}`"><td>{{ row.rank }}</td><td>{{ row.strategyId }} @ {{ row.strategyVersion }}</td><td>{{ row.successes }} / {{ row.evaluated }}</td><td>{{ (row.rate * 100).toFixed(2) }}%</td></tr></tbody>
      </table>
      <p>與基準差：{{ result.differencePercentagePoints.toFixed(3) }} 個百分點。</p>
    </div>
  </section>
</template>
