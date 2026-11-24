<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { fetchOfficialRanking, type OfficialRankingRow, type LotteryType, type RankingWindow } from '../../api/rankingMatrix'

const lottery = ref<LotteryType>('BIG_LOTTO')
const windowSize = ref<RankingWindow>('RECENT_300')
const ticketFilter = ref('ALL')
const rows = ref<OfficialRankingRow[]>([])
const error = ref('')
const loading = ref(false)
let generation = 0
watch([lottery, windowSize], async () => {
  const current = ++generation
  loading.value = true
  error.value = ''
  rows.value = []
  try {
    const result = await fetchOfficialRanking(lottery.value, windowSize.value)
    if (current === generation) rows.value = result.items
  } catch (e) {
    if (current === generation) error.value = e instanceof Error ? e.message : '載入失敗'
  } finally {
    if (current === generation) loading.value = false
  }
}, { immediate: true })
const ticketCounts = computed(() => [...new Set(rows.value.flatMap(row => row.ticket_count === null ? [] : [row.ticket_count]))].sort((a, b) => a - b))
const visibleRows = computed(() => rows.value.filter(row => ticketFilter.value === 'ALL' || String(row.ticket_count) === ticketFilter.value).slice().sort((a, b) => {
  const key = (r: OfficialRankingRow) => JSON.stringify([r.ticket_count, r.dataset_identity, r.execution_version, r.run_id, r.target_ids])
  return key(a).localeCompare(key(b)) || (a.rank ?? Number.MAX_SAFE_INTEGER) - (b.rank ?? Number.MAX_SAFE_INTEGER) || a.strategy_id.localeCompare(b.strategy_id)
}))
function percent(n: number | null): string { return n === null ? 'UNKNOWN' : `${(n * 100).toFixed(2)}%` }
function delta(n: number | null): string { return n === null ? 'UNKNOWN' : `${(n * 100).toFixed(2)} pp` }
</script>

<template>
  <section data-testid="official-ranking-panel">
    <h2>正式庫排行</h2>
    <p>同彩種、相同注數、執行版本、Run、資料身份及目標期別才可比較。基準：合法票券均勻獨立有放回，按期平均；差值僅描述歷史。</p>
    <p v-if="lottery === 'BIG_LOTTO'">依現行獎規計算；歷史獎規變更未追溯。</p>
    <p v-if="lottery === 'POWER_LOTTO'">威力彩現行獎規來源未核實，成功率、基準及差值為 UNKNOWN，不列入排名。</p>
    <label>彩種 <select v-model="lottery" data-testid="official-lottery"><option value="BIG_LOTTO">大樂透</option><option value="POWER_LOTTO">威力彩</option><option value="DAILY_539">今彩539</option></select></label>
    <label>窗口 <select v-model="windowSize" data-testid="official-window"><option value="FULL">全期</option><option value="RECENT_750">近750期</option><option value="RECENT_300">近300期</option><option value="RECENT_50">近50期</option></select></label>
    <label>注數 <select v-model="ticketFilter"><option value="ALL">全部</option><option v-for="count in ticketCounts" :key="count" :value="String(count)">{{ count }}</option></select></label>
    <p v-if="loading">載入中…</p><p v-else-if="error" role="alert">{{ error }}</p>
    <div v-else class="table-wrap"><table><thead><tr><th>排名</th><th>策略</th><th>注數</th><th>策略版本</th><th>執行版本</th><th>資料身份</th><th>Run / 期別</th><th>成功</th><th>可評估</th><th>缺漏</th><th>UNKNOWN</th><th>成功率</th><th>基準</th><th>差值</th><th>未知原因</th></tr></thead><tbody>
      <tr v-for="row in visibleRows" :key="JSON.stringify([row.strategy_id,row.strategy_version,row.execution_version,row.dataset_identity,row.run_id,row.scope_status,row.ticket_count])"><td>{{ row.rank ?? '—' }}</td><td>{{ row.strategy_name }} ({{ row.strategy_id }}) <strong v-if="!row.registered">未登記</strong></td><td>{{ row.ticket_count ?? 'UNKNOWN' }}</td><td>{{ row.strategy_version }}</td><td>{{ row.execution_version }}</td><td>{{ row.dataset_identity }}</td><td>{{ row.run_id }}<br>{{ row.scope_status }}<br>缺開獎證據 {{ row.missing_target_evidence }} 期；號碼衝突 {{ row.conflicting_target_evidence }} 期<br>{{ row.start_date }}–{{ row.end_date }}</td><td>{{ row.evaluated === 0 ? 'UNKNOWN' : row.successes }}</td><td>{{ row.evaluated }}</td><td>{{ row.missing }}</td><td>{{ row.unknown }}</td><td>{{ percent(row.rate) }}</td><td>{{ percent(row.baseline) }}</td><td>{{ delta(row.delta) }}</td><td>{{ row.unknown_reason ?? '—' }}</td></tr>
    </tbody></table><p v-if="!visibleRows.length">沒有結果。</p></div>
  </section>
</template>
<style scoped>
label { display: inline-flex; gap: .4rem; margin: .5rem 1rem .5rem 0; }
.table-wrap { overflow-x: auto; }
table { border-collapse: collapse; width: 100%; font-size: .85rem; }
th, td { border-bottom: 1px solid #ccd3dd; padding: .5rem; text-align: left; vertical-align: top; overflow-wrap: anywhere; }
</style>
