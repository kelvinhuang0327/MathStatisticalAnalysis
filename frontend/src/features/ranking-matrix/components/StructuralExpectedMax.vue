<script setup lang="ts">
import type { StructuralLottery, StructuralMatrixCell, StructuralTicketCount } from '../../../api/strategyMatrixStructural'
import EmptyState from '../../../components/EmptyState.vue'
import ErrorState from '../../../components/ErrorState.vue'
import SkeletonLoader from '../../../components/SkeletonLoader.vue'
import type { PageLoadState } from '../types'

defineProps<{
  cells: StructuralMatrixCell[]
  state: PageLoadState
  errorMessage: string
  lottery: StructuralLottery
  ticketCount: StructuralTicketCount
}>()
defineEmits<{ retry: [] }>()
</script>

<template>
  <section class="structural-section" aria-labelledby="structural-heading" data-testid="structural-section">
    <h2 id="structural-heading">結構期望最大主號命中數 (Structural expected-max)</h2>
    <p>
      均勻合法主號開獎空間下，每組投資組合的最大主號命中數期望值，單位為主號命中數 (main matches)。
      此區以研究 method_id 呈現，與歷史 strategy_id 不自動配對；不代表歷史成功率或排名分數。
      僅依彩種與注數選擇，歷史窗口與策略篩選不適用。
    </p>
    <p data-testid="structural-scope">
      {{ lottery === 'POWER_LOTTO_ZONE1' ? '威力彩 Zone 1 / 第一區主號（僅第一區）' : lottery === 'BIG_LOTTO' ? '大樂透主號' : '今彩 539 主號' }} · K{{ ticketCount }}
    </p>
    <SkeletonLoader v-if="state === 'loading'" :lines="3" data-testid="structural-loading" />
    <ErrorState
      v-else-if="state === 'error'"
      title="無法載入結構期望值資料"
      :message="errorMessage"
      data-testid="structural-error-state"
      @retry="$emit('retry')"
    />
    <EmptyState
      v-else-if="cells.length === 0"
      title="結構期望值 Unavailable"
      message="此彩種與注數未回傳結構方法資料。"
      data-testid="structural-empty-state"
    />
    <div v-else class="structural-table-wrap">
      <table data-testid="structural-table">
        <caption>Structural expected-max · 主號命中數 (main matches) · 依來源順序列示</caption>
        <thead>
          <tr><th scope="col">研究方法 (method_id)</th><th scope="col">測量狀態</th><th scope="col">期望最大主號命中數 / 不可用原因</th><th scope="col">來源提供的局部最優狀態</th></tr>
        </thead>
        <tbody>
          <tr v-for="cell in cells" :key="cell.row_id" data-testid="structural-method-row">
            <th scope="row">{{ cell.method_id }}</th>
            <td>{{ cell.measurement_status }}</td>
            <td>
              <span v-if="cell.measurement_status === 'MEASURED' && cell.value !== null" data-testid="structural-value">
                {{ cell.value.numerator }} / {{ cell.value.denominator }} 主號命中數 (main matches)
              </span>
              <span v-else data-testid="structural-unavailable">
                {{ cell.measurement_status === 'NOT_APPLICABLE' ? 'NOT_APPLICABLE / 不適用' : 'UNAVAILABLE / 無可用測量' }} · {{ cell.unavailable_reason ?? '未提供數值或原因' }}
              </span>
            </td>
            <td><span v-if="cell.local_optimum_status !== null">{{ cell.local_optimum_status }}</span></td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<style scoped>
.structural-section {
  padding: 16px 20px;
  border: 1px solid var(--border-color, rgba(255, 255, 255, 0.09));
  border-radius: var(--radius-md, 10px);
  background: var(--bg-card, rgba(18, 24, 38, 0.72));
}
h2 { margin: 0; }
p, caption { color: var(--text-secondary, #94a3b8); line-height: 1.5; }
.structural-table-wrap { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
caption { text-align: left; padding-bottom: 12px; }
th, td { padding: 10px; text-align: left; vertical-align: top; border-bottom: 1px solid var(--border-color, rgba(255, 255, 255, 0.09)); overflow-wrap: anywhere; }
</style>
