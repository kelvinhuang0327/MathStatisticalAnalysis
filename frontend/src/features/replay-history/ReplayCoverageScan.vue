<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import { scanReplayCoverage, type CoverageScan, type CoverageScanQuery, type ReplayBackfillLotteryType } from '../../api/replayBackfill'

const props = defineProps<{ lotteryType: ReplayBackfillLotteryType }>()
const startDate = ref('')
const endDate = ref('')
const strategies = ref(Array.from({ length: 5 }, () => ({ id: '', version: '' })))
const result = ref<CoverageScan | null>(null)
const state = ref<'idle' | 'loading' | 'ready' | 'error'>('idle')
const error = ref('')
const limit = 20
let sequence = 0
let controller: AbortController | undefined
function invalidate() {
  sequence++
  controller?.abort()
  result.value = null
  state.value = 'idle'
  error.value = ''
}
watch([() => props.lotteryType, startDate, endDate, strategies], invalidate, { deep: true, flush: 'sync' })
onBeforeUnmount(invalidate)
async function load(offset = 0) {
  const token = ++sequence
  controller?.abort()
  controller = new AbortController()
  state.value = 'loading'
  error.value = ''
  const query: CoverageScanQuery = { lotteryType: props.lotteryType, startDate: startDate.value, endDate: endDate.value, strategies: strategies.value.map(s => ({ ...s })), limit, offset }
  try {
    const response = await scanReplayCoverage(query, controller.signal)
    if (token !== sequence) return
    result.value = response
    state.value = 'ready'
  } catch (e) {
    if (token !== sequence) return
    result.value = null
    error.value = e instanceof Error ? e.message : '掃描失敗'
    state.value = 'error'
  }
}
</script>
<template>
  <section class="panel replay-backfill-section" aria-labelledby="scan-title" data-testid="coverage-scan">
    <h3 id="scan-title">缺期掃描</h3>
    <p>彩種：{{ lotteryType }}；每組策略以來源期數為分母。</p>
    <form @submit.prevent="load(0)">
      <label>開始日期 <input v-model="startDate" type="date" aria-label="掃描開始日期"></label>
      <label>結束日期 <input v-model="endDate" type="date" aria-label="掃描結束日期"></label>
      <div v-for="(strategy, index) in strategies" :key="index">
        <label>策略 {{ index + 1 }} ID <input v-model="strategy.id" :aria-label="`策略 ${index + 1} ID`"></label>
        <label>版本 <input v-model="strategy.version" :aria-label="`策略 ${index + 1} 版本`"></label>
      </div>
      <button type="submit">掃描</button>
    </form>
    <p v-if="state === 'loading'" role="status">正在掃描…</p>
    <p v-if="state === 'error'" role="alert">{{ error }}</p>
    <template v-if="result && state === 'ready'">
      <p>來源期數 {{ result.source_target_count }}；預期 cell {{ result.expected_cell_count }}；完成 {{ result.complete_cell_count }}／{{ result.expected_cell_count }}；未完成 {{ result.incomplete_cell_count }}／{{ result.expected_cell_count }}；覆蓋 {{ result.complete_coverage_percent.toFixed(1) }}%；orphan {{ result.orphan_replay_row_count }}。</p>
      <ul><li v-for="(counts, key) in result.strategy_counts" :key="key">{{ key }}：完成 {{ counts.complete }}／{{ result.source_target_count }}，缺口 {{ counts.incomplete }}／{{ result.source_target_count }}</li></ul>
      <p v-if="!result.items.length">此頁沒有缺口。</p>
      <table v-else><thead><tr><th>期號</th><th>日期</th><th>策略</th><th>版本</th><th>狀態</th><th>原因</th></tr></thead><tbody><tr v-for="item in result.items" :key="`${item.target_draw_id}-${item.strategy_id}`"><td>{{ item.target_draw_id }}</td><td>{{ item.target_draw_date }}</td><td>{{ item.strategy_id }}</td><td>{{ item.strategy_version }}</td><td>{{ item.status }}</td><td>{{ item.reason }}</td></tr></tbody></table>
      <p>缺口 {{ result.total_count }} 筆；位移 {{ result.offset }}；本頁 {{ result.items.length }} 筆。</p>
      <button type="button" :disabled="result.offset === 0" @click="load(Math.max(0, result.offset - limit))">上一頁</button>
      <button type="button" :disabled="result.next_offset === null" @click="load(result.next_offset ?? 0)">下一頁</button>
    </template>
  </section>
</template>
<style scoped>
form { display: grid; gap: 0.5rem; }
form div { display: flex; flex-wrap: wrap; gap: 1rem; }
input { color: #172033; background: #fff; border: 1px solid #aab4c4; border-radius: 4px; padding: 0.35rem; }
button { color: #172033; background: #fff; border: 1px solid #aab4c4; border-radius: 4px; padding: 0.4rem 0.8rem; }
button:disabled { color: #616a78; background: #d5dbe3; }
</style>
