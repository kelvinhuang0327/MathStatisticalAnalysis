<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'

import {
  B649NativeForecastRequestError,
  fetchB649NativeForecast,
  type B649NativeForecastResponse,
  type NativeCandidate,
  type NativeMetric,
} from '../../api/b649NativeForecast'

const targetDrawNumber = ref('')
const targetDrawDate = ref('')
const forecast = ref<B649NativeForecastResponse | null>(null)
const loading = ref(false)
const errorMessage = ref<string | null>(null)

let requestController: AbortController | null = null
let requestSequence = 0

const nativePayload = computed(() => forecast.value?.payload ?? null)

const k5Bucket = computed(
  () => nativePayload.value?.buckets.find((bucket) => bucket.native_k === 5) ?? null,
)

const nativeStrategyTotals = computed(() => {
  const strategies = nativePayload.value?.native_strategies
  if (!strategies) return null
  return {
    strategies: strategies.length,
    tickets: strategies.reduce((total, strategy) => total + strategy.native_positions.length, 0),
  }
})

function isCalendarDate(value: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false
  const parsed = new Date(value + 'T00:00:00.000Z')
  return Number.isFinite(parsed.getTime()) && parsed.toISOString().slice(0, 10) === value
}

async function loadNativeForecast(): Promise<void> {
  const target = {
    target_draw_number: targetDrawNumber.value.trim(),
    target_draw_date: targetDrawDate.value,
  }
  const sequence = ++requestSequence
  requestController?.abort()
  requestController = null
  forecast.value = null
  errorMessage.value = null

  if (!/^[0-9]{9}$/.test(target.target_draw_number) || !isCalendarDate(target.target_draw_date)) {
    loading.value = false
    errorMessage.value = '請輸入 9 位數期別和有效日期，再查詢 Native Forecast。'
    return
  }

  const controller = new AbortController()
  requestController = controller
  loading.value = true
  try {
    const result = await fetchB649NativeForecast(target, controller.signal)
    if (sequence === requestSequence) forecast.value = result
  } catch (error) {
    if (sequence !== requestSequence || isAbortError(error)) return
    errorMessage.value =
      error instanceof B649NativeForecastRequestError
        ? error.message
        : 'Native 查詢失敗，未保留舊結果。'
  } finally {
    if (sequence === requestSequence) {
      requestController = null
      loading.value = false
    }
  }
}

function metricText(metric: NativeMetric | undefined): string {
  if (metric === undefined) return '未提供'
  const numerator = metric?.numerator
  const denominator = metric?.denominator
  if (
    !metric ||
    numerator === null ||
    denominator === null ||
    !Number.isSafeInteger(numerator) ||
    !Number.isSafeInteger(denominator) ||
    Number(denominator) <= 0 ||
    Number(numerator) < 0 ||
    Number(numerator) > Number(denominator)
  ) {
    return '無法評估（分母為 0 或來源未提供有效分子／分母）'
  }
  const percentage = ((Number(numerator) / Number(denominator)) * 100).toFixed(2)
  return numerator + ' / ' + denominator + '（' + percentage + '%）'
}

function statusText(candidate: NativeCandidate): string {
  if (typeof candidate.status === 'string') return candidate.status
  return 'API 未提供單一策略狀態'
}

function coverageText(candidate: NativeCandidate): string {
  const coverage = candidate.coverage
  if (!coverage || typeof coverage.requested !== 'number') return '未提供'
  const counts = Object.entries(coverage.counts ?? {}).map(
    ([status, count]) => status + ': ' + String(count),
  )
  const stateSummary = counts.length > 0 ? '；' + counts.join('、') : ''
  return 'requested ' + coverage.requested + stateSummary
}

function isAbortError(value: unknown): boolean {
  return value instanceof Error && value.name === 'AbortError'
}

onBeforeUnmount(() => {
  requestSequence += 1
  requestController?.abort()
  requestController = null
})
</script>

<template>
  <section
    class="b649-native-forecast"
    aria-labelledby="b649-native-forecast-title"
    :aria-busy="loading"
  >
    <header class="b649-native-forecast__header">
      <div>
        <p class="b649-native-forecast__eyebrow">Native · 獨立來源</p>
        <h2 id="b649-native-forecast-title">Native Forecast</h2>
        <p>請明確輸入期別與日期；此區不沿用 Canonical 目標，也不推算下一期。</p>
      </div>
    </header>

    <form class="b649-native-forecast__query" @submit.prevent="loadNativeForecast">
      <label>
        <span>目標期別</span>
        <input
          v-model="targetDrawNumber"
          inputmode="numeric"
          pattern="[0-9]{9}"
          maxlength="9"
          autocomplete="off"
          aria-label="Native 目標期別"
          data-testid="native-target-draw-number"
          required
        />
      </label>
      <label>
        <span>目標日期</span>
        <input
          v-model="targetDrawDate"
          type="date"
          aria-label="Native 目標日期"
          data-testid="native-target-draw-date"
          required
        />
      </label>
      <button type="submit" data-testid="native-query-button">
        {{ loading ? '查詢此期別' : '查詢 Native' }}
      </button>
    </form>

    <p v-if="loading" class="b649-native-forecast__status" role="status">
      正在讀取所選期別的 Native 資料…
    </p>
    <div v-else-if="errorMessage" class="b649-native-forecast__error" role="alert">
      {{ errorMessage }}
    </div>

    <template v-else-if="forecast && nativePayload && k5Bucket">
      <section class="b649-native-forecast__panel" aria-labelledby="native-scope-title">
        <h3 id="native-scope-title">API 回傳範圍與資料身份</h3>
        <dl class="b649-native-forecast__grid">
          <div>
            <dt>彩種</dt>
            <dd data-testid="native-scope-lottery">{{ forecast.scope.lottery_type }}</dd>
          </div>
          <div>
            <dt>API 目標期別</dt>
            <dd data-testid="native-scope-draw-number">{{ forecast.scope.target_draw_number }}</dd>
          </div>
          <div>
            <dt>API 目標日期</dt>
            <dd data-testid="native-scope-draw-date">{{ forecast.scope.target_draw_date }}</dd>
          </div>
          <div>
            <dt>Forecast stream</dt>
            <dd><code>{{ forecast.scope.forecast_stream_id }}</code></dd>
          </div>
          <div>
            <dt>Stream 版本</dt>
            <dd><code>{{ forecast.scope.forecast_stream_version }}</code></dd>
          </div>
          <div>
            <dt>歷史資料 cutoff 期別</dt>
            <dd data-testid="native-history-cutoff">{{ nativePayload.identity.history_cutoff }}</dd>
          </div>
          <div>
            <dt>歷史資料 cutoff 日期</dt>
            <dd data-testid="native-history-cutoff-date">{{ nativePayload.history.last_draw_date ?? '未提供' }}</dd>
          </div>
          <div>
            <dt>原始生成開始時間</dt>
            <dd><time :datetime="forecast.request_identity.generation_started_at">{{ forecast.request_identity.generation_started_at }}</time></dd>
          </div>
          <div>
            <dt>原始生成完成時間</dt>
            <dd><time :datetime="forecast.request_identity.generation_finished_at">{{ forecast.request_identity.generation_finished_at }}</time></dd>
          </div>
          <div>
            <dt>提交時間</dt>
            <dd><time :datetime="forecast.request_identity.committed_at">{{ forecast.request_identity.committed_at }}</time></dd>
          </div>
          <div>
            <dt>Request ID / 版本</dt>
            <dd><code>{{ forecast.request_identity.request_id }}</code> / {{ forecast.request_identity.version }}</dd>
          </div>
          <div>
            <dt>Run ID</dt>
            <dd><code>{{ forecast.request_identity.run_id }}</code></dd>
          </div>
          <div>
            <dt>Request SHA-256</dt>
            <dd><code>{{ forecast.request_identity.request_sha256 }}</code></dd>
          </div>
          <div>
            <dt>Payload SHA-256</dt>
            <dd><code>{{ forecast.request_identity.payload_sha256 }}</code></dd>
          </div>
          <div>
            <dt>issued_at</dt>
            <dd>未提供</dd>
          </div>
        </dl>
        <p class="b649-native-forecast__evidence" data-testid="native-evidence-boundary">
          資料證明狀態：未確認。來源 fixture_only={{ nativePayload.fixture_only }} 只描述 fixture 狀態，不是外部事前證明。固定 API 契約沒有外部事前證明欄位；LOCAL_ONLY 只代表本機合成驗收，不能證明正式環境的事前預測。歷史重播也不會標示為事前預測。
        </p>
      </section>

      <section class="b649-native-forecast__panel" aria-labelledby="native-k5-title">
        <h3 id="native-k5-title">K5 主 Bucket</h3>
        <p>後端狀態：<strong data-testid="native-k5-status">{{ k5Bucket.status }}</strong></p>
        <div v-if="k5Bucket.selected" class="b649-native-forecast__selection" data-testid="native-k5-selection">
          <h4>後端實際選定結果</h4>
          <p><code>{{ k5Bucket.selected.strategy_id }}</code> · {{ k5Bucket.selected.strategy_version }}</p>
          <ol v-if="k5Bucket.tickets.length" class="b649-native-forecast__tickets">
            <li v-for="(ticket, index) in k5Bucket.tickets" :key="index" data-testid="native-selected-ticket">
              <span>票券 {{ index + 1 }}</span>
              <strong>{{ ticket.join(' · ') }}</strong>
            </li>
          </ol>
        </div>
        <p v-else>後端未回傳 K5 選定結果或票券。</p>
      </section>

      <section class="b649-native-forecast__panel" aria-labelledby="native-strategy-title">
        <h3 id="native-strategy-title">K5 原生策略明細</h3>
        <p v-if="nativeStrategyTotals" data-testid="native-position-totals">
          原生產票共 {{ nativeStrategyTotals.strategies }} 組策略、{{ nativeStrategyTotals.tickets }} 注。
        </p>
        <p data-testid="native-strategy-count">K5 主 Bucket 回傳 {{ k5Bucket.candidates.length }} 筆候選策略明細。</p>
        <ul v-if="k5Bucket.candidates.length" class="b649-native-forecast__candidate-list">
          <li v-for="candidate in k5Bucket.candidates" :key="candidate.strategy_id + ':' + candidate.strategy_version" data-testid="native-strategy-candidate">
            <h4><code>{{ candidate.strategy_id }}</code></h4>
            <dl class="b649-native-forecast__grid">
              <div><dt>策略版本</dt><dd>{{ candidate.strategy_version }}</dd></div>
              <div><dt>原生 K</dt><dd>{{ candidate.native_k }}</dd></div>
              <div><dt>歷史成功率</dt><dd>{{ metricText(candidate.metric) }}</dd></div>
              <div><dt>來源狀態與評估狀態計數</dt><dd>{{ statusText(candidate) }}</dd></div>
              <div><dt>Coverage</dt><dd>{{ coverageText(candidate) }}</dd></div>
            </dl>
          </li>
        </ul>
        <p v-else>API 未提供 K5 原生策略明細。</p>
      </section>
    </template>
  </section>
</template>

<style scoped>
.b649-native-forecast {
  display: grid;
  gap: 16px;
  padding: 24px 0 40px;
  border-top: 2px solid var(--secondary-color);
}

.b649-native-forecast__header h2 {
  margin-bottom: 8px;
}

.b649-native-forecast__eyebrow {
  margin-bottom: 6px;
  color: var(--text-accent);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.b649-native-forecast__query {
  display: flex;
  flex-wrap: wrap;
  align-items: end;
  gap: 12px;
}

.b649-native-forecast__query label {
  display: grid;
  gap: 6px;
  min-width: min(100%, 220px);
}

.b649-native-forecast__query input,
.b649-native-forecast__query button {
  min-height: 40px;
  padding: 8px 12px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  background: var(--bg-tertiary);
  color: var(--text-primary);
}

.b649-native-forecast__query button {
  cursor: pointer;
}

.b649-native-forecast__panel {
  min-width: 0;
  padding: 18px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  background: var(--bg-card);
}

.b649-native-forecast__panel h3 {
  margin-bottom: 14px;
}

.b649-native-forecast__panel h4 {
  margin-bottom: 8px;
}

.b649-native-forecast__grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 220px), 1fr));
  gap: 12px;
  margin: 0;
}

.b649-native-forecast__grid dt {
  margin-bottom: 4px;
  color: var(--text-tertiary);
  font-size: 12px;
}

.b649-native-forecast__grid dd {
  margin: 0;
  overflow-wrap: anywhere;
}

.b649-native-forecast__grid code,
.b649-native-forecast__panel code {
  overflow-wrap: anywhere;
}

.b649-native-forecast__evidence {
  margin: 16px 0 0;
  padding: 12px 14px;
  border-left: 3px solid var(--color-warning-border);
  background: var(--color-warning-bg);
}

.b649-native-forecast__tickets,
.b649-native-forecast__candidate-list {
  display: grid;
  gap: 8px;
  margin: 12px 0 0;
  padding: 0;
  list-style: none;
}

.b649-native-forecast__tickets li,
.b649-native-forecast__candidate-list li {
  min-width: 0;
  padding: 12px;
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  background: rgba(7, 9, 14, 0.35);
}

.b649-native-forecast__tickets li {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.b649-native-forecast__tickets strong {
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.b649-native-forecast__status,
.b649-native-forecast__error {
  padding: 14px 16px;
  border: 1px solid var(--color-warning-border);
  border-radius: var(--radius-md);
  background: var(--color-warning-bg);
}

@media (max-width: 640px) {
  .b649-native-forecast__query label,
  .b649-native-forecast__query button {
    width: 100%;
  }

  .b649-native-forecast__tickets li {
    align-items: flex-start;
    flex-direction: column;
  }

  .b649-native-forecast__tickets strong {
    text-align: left;
  }
}
</style>
