<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import {
  getK3Comparison,
  type K3Comparison,
  type K3ComparisonStrategy,
  type ReplayBackfillPredictionItem,
} from '../../api/replayBackfill'

const strategy = ref<K3ComparisonStrategy>('optimizer')
const result = ref<K3Comparison | null>(null)
const loading = ref(false)
const error = ref('')
const page = ref(1)
const pageSize = 50
const pageCount = computed(() => Math.max(1, Math.ceil((result.value?.rows.length ?? 0) / pageSize)))
const visibleRows = computed(() => result.value?.rows.slice((page.value - 1) * pageSize, page.value * pageSize) ?? [])
let controller: AbortController | undefined
let generation = 0

async function load(): Promise<void> {
  controller?.abort()
  const current = new AbortController()
  controller = current
  const request = ++generation
  const selected = strategy.value
  result.value = null
  page.value = 1
  loading.value = true
  error.value = ''
  try {
    const data = await getK3Comparison(selected, current.signal)
    if (!current.signal.aborted && request === generation) result.value = data
  } catch {
    if (!current.signal.aborted && request === generation) error.value = '無法讀取比較資料，請稍後重試。'
  } finally {
    if (!current.signal.aborted && request === generation) loading.value = false
  }
}

function rate(wins: number, count: number): string {
  return count ? `${(wins * 100 / count).toFixed(2)}%` : '—'
}

function signed(value: number | null, digits = 2): string {
  if (value === null) return '資料不足'
  return `${value > 0 ? '+' : ''}${value.toFixed(digits)}`
}

function prize(value: ReplayBackfillPredictionItem | null): string {
  if (!value || value.portfolio_any_prize === null) return '無法判定'
  return value.portfolio_any_prize ? '中獎' : '未命中'
}

onMounted(load)
onBeforeUnmount(() => { controller?.abort(); generation++ })
</script>

<template>
  <section class="panel k3-comparison" aria-labelledby="k3-comparison-title">
    <h3 id="k3-comparison-title">Optimizer / ECP 新舊版並排比較</h3>
    <p>同一期、同樣三注，比較已儲存的歷史結果；這是探索性分析，不代表已證明預測增益。</p>
    <label class="strategy-select">
      <span>比較策略</span>
      <select v-model="strategy" aria-label="比較策略" @change="load">
        <option value="optimizer">Optimizer</option>
        <option value="ecp">ECP</option>
      </select>
    </label>
    <p v-if="loading" role="status">正在讀取比較資料…</p>
    <p v-else-if="error" role="alert">{{ error }} <button class="button" type="button" @click="load">重試</button></p>
    <template v-else-if="result">
      <p>歷史範圍：2008-06-10 至 2026-11-13；共 {{ result.target_count }} 期，成功配對 {{ result.paired_count }} 期。
        <strong v-if="result.unmatched_count">{{ result.unmatched_count }} 期無法可靠配對，不計入中獎率。</strong>
      </p>
      <div class="summary-grid" aria-label="新舊版比較摘要">
        <div><span>舊版中獎率</span><strong>{{ rate(result.old_wins, result.paired_count) }}</strong><small>{{ result.old_wins }} / {{ result.paired_count }} 期</small></div>
        <div><span>新版中獎率</span><strong>{{ rate(result.new_wins, result.paired_count) }}</strong><small>{{ result.new_wins }} / {{ result.paired_count }} 期</small></div>
        <div><span>淨增中獎期數</span><strong>{{ signed(result.new_wins - result.old_wins, 0) }} 期</strong><small>新版獨中 {{ result.new_only }}；舊版獨中 {{ result.old_only }}</small></div>
        <div><span>扣除公平結構差後</span><strong>{{ signed(result.observed_minus_fair) }} 期</strong><small>公平結構期望差 {{ signed(result.fair_delta) }} 期</small></div>
      </div>
      <p class="scope-note">僅比較已儲存的固定歷史區間；來源歷史含未驗證資料。逐期配對保留原來源，重複資料不重算。</p>
      <nav class="pagination" aria-label="比較結果分頁（上方）">
        <button class="button" type="button" :disabled="page <= 1" @click="page = 1">最早一頁</button>
        <button class="button" type="button" :disabled="page <= 1" @click="page--">上一頁</button>
        <span>第 {{ page }} / {{ pageCount }} 頁</span>
        <button class="button" type="button" :disabled="page >= pageCount" @click="page++">下一頁</button>
        <button class="button" type="button" :disabled="page >= pageCount" @click="page = pageCount">最新一頁</button>
      </nav>
      <div class="table-scroll">
        <table aria-label="逐期新舊版並排比較">
          <thead><tr><th scope="col">期別 / 開獎號碼</th><th scope="col">舊版三注</th><th scope="col">舊版結果</th><th scope="col">新版三注</th><th scope="col">新版結果</th><th scope="col">來源</th></tr></thead>
          <tbody>
            <tr v-for="row in visibleRows" :key="row.target_draw_number">
              <th scope="row">{{ row.target_draw_number }}<br /><small>{{ row.target_draw_date }}</small><br /><small>{{ row.new.actual_main_numbers.join('、') }} + {{ row.new.actual_special_numbers.join('、') }}</small></th>
              <td><ol v-if="row.old"><li v-for="(ticket, index) in row.old.predicted_tickets" :key="ticket.ticket_position ?? index">{{ ticket.main_numbers?.join('、') ?? '—' }}</li></ol><span v-else>未配對</span></td>
              <td>{{ row.old ? prize(row.old) : '未配對' }}</td>
              <td><ol><li v-for="(ticket, index) in row.new.predicted_tickets" :key="ticket.ticket_position ?? index">{{ ticket.main_numbers?.join('、') ?? '—' }}</li></ol></td>
              <td>{{ prize(row.new) }}</td>
              <td><span v-if="row.match_status === 'ORIGINAL_CELL'">原始紀錄配對</span><span v-else-if="row.match_status === 'SOURCE_EVIDENCE'">來源證據配對</span><strong v-else>未可靠配對：{{ row.match_status }}</strong>
                <details><summary>來源詳情</summary><small>來源段：{{ row.source_segment ?? '未提供' }}<br />原來源 run：{{ row.original_source_run_id ?? '未記錄' }}<br />正式讀取 run：{{ row.old?.run_id ?? '未找到' }}<br />舊紀錄：{{ row.old_cell_identity ?? '未找到' }}</small></details>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <nav class="pagination" aria-label="比較結果分頁">
        <button class="button" type="button" :disabled="page <= 1" @click="page = 1">最早一頁</button>
        <button class="button" type="button" :disabled="page <= 1" @click="page--">上一頁</button>
        <span>第 {{ page }} / {{ pageCount }} 頁</span>
        <button class="button" type="button" :disabled="page >= pageCount" @click="page++">下一頁</button>
        <button class="button" type="button" :disabled="page >= pageCount" @click="page = pageCount">最新一頁</button>
      </nav>
    </template>
  </section>
</template>

<style scoped>
.k3-comparison { margin: 22px 0; padding: 18px; }
.k3-comparison h3 { margin-top: 0; }
.strategy-select { display: flex; align-items: center; gap: 10px; margin: 14px 0; }
.strategy-select select { min-width: 150px; }
.summary-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 10px; }
.summary-grid > div { border: 1px solid var(--border, #d6dce4); border-radius: 8px; padding: 12px; display: grid; gap: 4px; }
.summary-grid strong { font-size: 1.3rem; }
.summary-grid small, .scope-note { color: var(--muted, #586474); }
.table-scroll { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; }
th, td { text-align: left; vertical-align: top; border-bottom: 1px solid var(--border, #d6dce4); padding: 10px; }
td ol { min-width: 145px; margin: 0; padding-left: 18px; }
td details { max-width: 220px; overflow-wrap: anywhere; }
.pagination { display: flex; flex-wrap: wrap; align-items: center; gap: 12px; margin: 16px 0; }
</style>
