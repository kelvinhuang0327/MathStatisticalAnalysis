<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import {
  fetchB649CanonicalForecast,
  type B649CanonicalForecast,
} from '../../api/b649CanonicalForecast'
import {
  filterStrategyResearchRows,
  fetchStrategyResearchRows,
  formatActualRateForDisplay,
  formatResearchCount,
  formatResearchDelta,
  formatResearchRate,
  isAboveRandomBaseline,
  STRATEGY_RESEARCH_K_VALUES,
  STRATEGY_RESEARCH_WINDOWS,
  type StrategyResearchK,
  type StrategyResearchRow,
  type StrategyResearchWindow,
} from './model'

const selectedK = ref<StrategyResearchK>(5)
const selectedWindow = ref<StrategyResearchWindow>('FULL')
const historyRows = ref<StrategyResearchRow[]>([])
const historyState = ref<'loading' | 'ready' | 'empty' | 'error'>('loading')
const historyError = ref('')
const strategyIdSearch = ref('')
const aboveRandomOnly = ref(false)
const selectedStrategy = ref<StrategyResearchRow | null>(null)

const forecast = ref<B649CanonicalForecast | null>(null)
const forecastState = ref<'loading' | 'available' | 'unavailable'>('loading')

let historyController: AbortController | null = null
let forecastController: AbortController | null = null
let historyGeneration = 0

const visibleRows = computed(() =>
  filterStrategyResearchRows(historyRows.value, strategyIdSearch.value, aboveRandomOnly.value),
)

const windowLabels: Record<StrategyResearchWindow, string> = {
  FULL: 'FULL',
  RECENT_750: 'RECENT_750',
  RECENT_300: 'RECENT_300',
  RECENT_50: 'RECENT_50',
}

function sourceWarningLabel(code: string): string {
  const labels: Record<string, string> = {
    CLOSED_UNEXECUTABLE: '已封存，無法重算',
    DUPLICATE_ALIAS: '重複別名',
    HIGH_RANK_LOW_COVERAGE: '來源警示：高排名但覆蓋率低',
    INSUFFICIENT_WINDOW: '窗口樣本不足',
    LOW_SAMPLE_SIZE: '低樣本數',
    NOT_HISTORICALLY_COMPARABLE: '歷史不可直接比較',
    NO_RECENT_OBSERVATIONS: '近期沒有成功樣本',
  }
  return labels[code] ?? code
}

async function loadHistory(): Promise<void> {
  historyController?.abort()
  const controller = new AbortController()
  historyController = controller
  const generation = ++historyGeneration
  historyRows.value = []
  selectedStrategy.value = null
  historyError.value = ''
  historyState.value = 'loading'

  try {
    const rows = await fetchStrategyResearchRows(selectedK.value, selectedWindow.value, controller.signal)
    if (generation !== historyGeneration) return
    historyRows.value = rows
    historyState.value = rows.length === 0 ? 'empty' : 'ready'
  } catch (error) {
    if (controller.signal.aborted || (error instanceof Error && error.name === 'AbortError')) return
    if (generation !== historyGeneration) return
    historyRows.value = []
    historyError.value = '歷史資料查詢失敗。請稍後重試；目前沒有顯示先前查詢的資料。'
    historyState.value = 'error'
  } finally {
    if (historyController === controller) historyController = null
  }
}

async function loadCurrentConsensus(): Promise<void> {
  forecastController?.abort()
  const controller = new AbortController()
  forecastController = controller
  forecast.value = null
  forecastState.value = 'loading'
  try {
    forecast.value = await fetchB649CanonicalForecast(controller.signal)
    forecastState.value = 'available'
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError') return
    forecast.value = null
    forecastState.value = 'unavailable'
  } finally {
    if (forecastController === controller) forecastController = null
  }
}

watch([selectedK, selectedWindow], () => {
  void loadHistory()
})

onMounted(() => {
  void loadHistory()
  void loadCurrentConsensus()
})

onBeforeUnmount(() => {
  historyController?.abort()
  forecastController?.abort()
})
</script>

<template>
  <section class="strategy-forecast-research" aria-labelledby="strategy-forecast-research-title">
    <header class="research-header">
      <div>
        <p class="research-eyebrow">B649 · 唯讀研究查詢</p>
        <h1 id="strategy-forecast-research-title">策略歷史表現與目前預測</h1>
        <p class="research-intro">
          歷史表現與排程器共識預測分開呈現。描述性正差值不代表統計顯著、未來增益或策略適用性。
        </p>
      </div>
    </header>

    <section class="research-panel history-panel" aria-labelledby="history-performance-title">
      <div class="panel-heading">
        <div>
          <p class="section-eyebrow">區域一</p>
          <h2 id="history-performance-title">歷史策略表現</h2>
        </div>
        <span class="group-chip">B649 · K{{ selectedK }} · {{ windowLabels[selectedWindow] }}</span>
      </div>

      <div class="history-controls">
        <label>
          <span>票券數 K</span>
          <select v-model.number="selectedK" aria-label="票券數 K">
            <option v-for="k in STRATEGY_RESEARCH_K_VALUES" :key="k" :value="k">K{{ k }}</option>
          </select>
        </label>
        <label>
          <span>歷史窗口</span>
          <select v-model="selectedWindow" aria-label="歷史窗口">
            <option v-for="window in STRATEGY_RESEARCH_WINDOWS" :key="window" :value="window">
              {{ windowLabels[window] }}
            </option>
          </select>
        </label>
        <label class="search-control">
          <span>策略 ID 搜尋</span>
          <input v-model="strategyIdSearch" type="search" placeholder="輸入策略 ID" />
        </label>
        <label class="checkbox-control">
          <input v-model="aboveRandomOnly" type="checkbox" />
          <span>只看高於隨機基準</span>
        </label>
        <button class="quiet-button" type="button" :disabled="historyState === 'loading'" @click="loadHistory">
          {{ historyState === 'loading' ? '讀取中…' : '重新查詢' }}
        </button>
      </div>

      <p class="research-note">
        高於基準只表示同一事件來源中的 delta &gt; 0，且成功率與基準均有有效來源。這是描述性比較，不是顯著性或 OOS 預測證據。
      </p>

      <p v-if="historyState === 'loading'" class="state-message" role="status">
        正在查詢 B649 K{{ selectedK }} / {{ windowLabels[selectedWindow] }} 歷史資料…
      </p>
      <div v-else-if="historyState === 'error'" class="state-message state-message--error" role="alert">
        {{ historyError }}
      </div>
      <p v-else-if="historyState === 'empty'" class="state-message" role="status">
        此 K 與歷史窗口沒有可用的策略資料。這是成功查詢後的空資料結果。
      </p>
      <p v-else-if="visibleRows.length === 0" class="state-message" role="status">
        目前篩選條件沒有符合的策略；已載入 {{ historyRows.length }} 筆來源資料。
      </p>

      <div v-if="historyState === 'ready'" class="table-summary" aria-live="polite">
        顯示 {{ visibleRows.length }} / {{ historyRows.length }} 筆，依來源排名順序；不截斷符合條件的策略。
      </div>

      <div
        v-if="historyState === 'ready' && visibleRows.length > 0"
        class="table-scroll"
        tabindex="0"
        aria-label="B649 歷史策略表現表格，可水平捲動"
      >
        <table :data-k="selectedK" :data-window="selectedWindow">
          <thead>
            <tr>
              <th scope="col">策略身份</th>
              <th scope="col">事件</th>
              <th scope="col">來源排名</th>
              <th scope="col">成功率</th>
              <th scope="col">成功數 / 觀測數</th>
              <th scope="col">隨機基準</th>
              <th scope="col">差值</th>
              <th scope="col">覆蓋率</th>
              <th scope="col">可比較性</th>
              <th scope="col">來源警示</th>
              <th scope="col">正式 OOS 證據</th>
              <th scope="col">選取策略</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="row in visibleRows"
              :key="`${row.strategyId}@${row.strategyVersion}`"
              :data-testid="`history-row-${row.strategyId}`"
            >
              <td class="identity-cell">
                <strong>{{ row.strategyId }}</strong>
                <span>{{ row.displayName }}</span>
                <code>版本 {{ row.strategyVersion }}</code>
              </td>
              <td><code>{{ row.eventCriterion }}</code></td>
              <td>{{ row.officialRank ?? '未排名' }}</td>
              <td>
                <span v-if="row.denominator === 0" class="unavailable-text">不可用（0 / 0）</span>
                <span v-else>{{ formatActualRateForDisplay(row) }}</span>
              </td>
              <td>{{ formatResearchCount(row.numerator) }} / {{ formatResearchCount(row.denominator) }}</td>
              <td>{{ formatResearchRate(row.baselineRate) }}</td>
              <td :class="{ 'positive-delta': isAboveRandomBaseline(row) }">
                {{ formatResearchDelta(row.baselineDelta) }}
                <span v-if="isAboveRandomBaseline(row)" class="descriptive-tag">描述性正差值</span>
              </td>
              <td>
                {{ formatResearchRate(row.coverage) }}
                <span v-if="row.coverage !== null && row.coverage < 0.1" class="warning-tag">低覆蓋率</span>
              </td>
              <td>
                <span :class="['status-tag', row.isAvailable ? 'status-tag--available' : 'status-tag--unavailable']">
                  {{ row.isAvailable ? '指標可用' : '指標不可用' }}
                </span>
                <small>{{ row.comparabilityLabel }} · {{ row.comparabilityStatus }}</small>
              </td>
              <td>
                <ul v-if="row.warningCodes.length" class="warning-list">
                  <li v-for="code in row.warningCodes" :key="code">{{ sourceWarningLabel(code) }}</li>
                </ul>
                <span v-else>無來源警示</span>
              </td>
              <td>
                <span v-if="row.hasFormalOosEvidence">來源含正式 OOS 證據</span>
                <span v-else>此歷史來源未提供；不宣稱預測優勢</span>
              </td>
              <td>
                <button
                  class="select-strategy-button"
                  type="button"
                  :aria-pressed="selectedStrategy?.strategyId === row.strategyId && selectedStrategy?.strategyVersion === row.strategyVersion"
                  @click="selectedStrategy = row"
                >
                  {{ selectedStrategy?.strategyId === row.strategyId && selectedStrategy?.strategyVersion === row.strategyVersion ? '已選取' : '選取' }}
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <section class="strategy-linkage" aria-labelledby="strategy-linkage-title">
        <div>
          <p class="section-eyebrow">策略專屬預測</p>
          <h3 id="strategy-linkage-title">所選策略的下一期預測</h3>
        </div>
        <p v-if="selectedStrategy" class="selected-identity">
          {{ selectedStrategy.strategyId }} <code>版本 {{ selectedStrategy.strategyVersion }}</code>
        </p>
        <p v-else class="selected-identity">尚未選取歷史策略。</p>
        <strong class="unavailable-code">PER_STRATEGY_FORECAST_NOT_AVAILABLE</strong>
        <p>目前沒有具備完整策略 ID 與版本關聯的專屬預測來源。共識票券不會指派給所選策略。</p>
      </section>
    </section>

    <section class="research-panel consensus-panel" aria-labelledby="consensus-forecast-title">
      <div class="panel-heading">
        <div>
          <p class="section-eyebrow">區域二</p>
          <h2 id="consensus-forecast-title">B649 目前共識預測</h2>
        </div>
        <button class="quiet-button" type="button" :disabled="forecastState === 'loading'" @click="loadCurrentConsensus">
          {{ forecastState === 'loading' ? '讀取中…' : '重新載入預測' }}
        </button>
      </div>

      <div class="forecast-kind-labels">
        <strong>CURRENT_CONSENSUS_FORECAST</strong>
        <strong>NOT_PER_STRATEGY_FORECAST</strong>
      </div>
      <p class="research-note">
        以下只顯示既有排程器共識 API 的有效 AVAILABLE 回應；票券不代表任何單一歷史策略，也不構成 OOS 增益證據。
      </p>

      <p v-if="forecastState === 'loading'" class="state-message" role="status">
        正在讀取排程器目前預測…
      </p>
      <div v-else-if="forecastState === 'unavailable' || !forecast" class="state-message state-message--error" role="alert">
        目前預測不可用。API 回傳錯誤或無有效 AVAILABLE 資料；目前不顯示任何舊票券。
      </div>
      <template v-else>
        <dl class="forecast-target-grid">
          <div><dt>目標期別</dt><dd>{{ forecast.current_target.draw_number }}</dd></div>
          <div><dt>開獎日期</dt><dd>{{ forecast.current_target.draw_date }}</dd></div>
          <div>
            <dt>預定開獎日期與時間</dt>
            <dd><time :datetime="forecast.current_target.scheduled_at">{{ forecast.current_target.scheduled_at }}</time></dd>
          </div>
        </dl>

        <div class="forecast-ticket-grid">
          <section v-for="k in [5, 10, 20] as const" :key="k" class="ticket-group">
            <h3>K{{ k }}</h3>
            <ol>
              <li v-for="ticket in forecast[`k${k}_tickets`]" :key="ticket.ticket_position">
                <span>票券 {{ ticket.ticket_position }}</span>
                <strong>{{ ticket.predicted_numbers.join(' · ') }}</strong>
              </li>
            </ol>
          </section>
        </div>

        <div class="forecast-provenance-grid">
          <section>
            <h3>預測方法</h3>
            <code>{{ forecast.forecast_method_id }}</code>
            <span>版本 {{ forecast.forecast_method_version }}</span>
            <small>Artifact SHA-256</small>
            <code>{{ forecast.forecast_actual_sha256 }}</code>
          </section>
          <section>
            <h3>票券組合方法</h3>
            <code>{{ forecast.portfolio_method_id }}</code>
            <span>版本 {{ forecast.portfolio_method_version }}</span>
            <small>Artifact SHA-256</small>
            <code>{{ forecast.portfolio_actual_sha256 }}</code>
          </section>
        </div>
      </template>
    </section>
  </section>
</template>

<style scoped>
.strategy-forecast-research { display: grid; gap: 20px; padding: 32px 0 48px; }
.research-header, .panel-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 20px; }
.research-eyebrow, .section-eyebrow { margin: 0 0 7px; color: var(--text-accent); font-size: 12px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; }
.research-header h1 { margin: 0 0 8px; font-size: clamp(28px, 4vw, 40px); line-height: 1.15; }
.research-intro { max-width: 900px; margin: 0; color: var(--text-secondary); }
.research-panel { display: grid; gap: 16px; min-width: 0; padding: 20px; border: 1px solid var(--border-color); border-radius: var(--radius-lg); background: var(--bg-card); }
.panel-heading h2 { margin: 0; font-size: 21px; }
.group-chip { padding: 7px 10px; border: 1px solid var(--border-color); border-radius: 999px; color: var(--text-secondary); font-size: 13px; white-space: nowrap; }
.history-controls { display: flex; align-items: flex-end; flex-wrap: wrap; gap: 12px; }
.history-controls label { display: grid; gap: 5px; color: var(--text-secondary); font-size: 12px; }
.history-controls select, .history-controls input[type="search"] { min-width: 140px; padding: 9px 11px; border: 1px solid var(--border-color); border-radius: var(--radius-md); background: var(--bg-tertiary); color: var(--text-primary); font: inherit; }
.history-controls .search-control input { min-width: 210px; }
.history-controls .checkbox-control { display: flex; align-items: center; gap: 8px; min-height: 38px; font-size: 13px; }
.quiet-button, .select-strategy-button { padding: 9px 12px; border: 1px solid var(--border-color); border-radius: var(--radius-md); background: var(--bg-tertiary); color: var(--text-primary); font: inherit; cursor: pointer; }
.quiet-button:disabled { cursor: wait; opacity: .65; }
.research-note { margin: 0; color: var(--text-secondary); font-size: 13px; line-height: 1.55; }
.state-message { margin: 0; padding: 14px 16px; border: 1px solid var(--border-subtle); border-radius: var(--radius-md); background: rgba(148, 163, 184, .07); color: var(--text-secondary); }
.state-message--error { border-color: var(--color-warning-border); background: var(--color-warning-bg); }
.table-summary { color: var(--text-secondary); font-size: 12px; }
.table-scroll { max-width: 100%; overflow: auto; border: 1px solid var(--border-subtle); border-radius: var(--radius-md); }
table { width: 100%; min-width: 1700px; border-collapse: collapse; font-size: 12px; }
th, td { padding: 10px 11px; border-bottom: 1px solid var(--border-subtle); text-align: left; vertical-align: top; }
th { position: sticky; top: 0; z-index: 1; background: var(--bg-tertiary); color: var(--text-secondary); white-space: nowrap; }
tbody tr:last-child td { border-bottom: 0; }
td { max-width: 280px; overflow-wrap: anywhere; }
.identity-cell { display: grid; gap: 4px; min-width: 185px; }
.identity-cell span, td small { color: var(--text-secondary); }
code { overflow-wrap: anywhere; }
.status-tag, .warning-tag, .descriptive-tag { display: inline-block; margin-top: 4px; padding: 3px 6px; border-radius: 999px; font-size: 10px; line-height: 1.35; }
.status-tag--available { background: rgba(34, 197, 94, .12); color: var(--color-success, #86efac); }
.status-tag--unavailable, .warning-tag { background: rgba(245, 158, 11, .14); color: var(--color-warning, #fcd34d); }
.descriptive-tag { background: rgba(56, 189, 248, .13); color: var(--text-accent); white-space: nowrap; }
.positive-delta { color: var(--color-success, #86efac); }
.warning-list { margin: 0; padding-left: 15px; color: var(--text-secondary); }
.warning-list li + li { margin-top: 4px; }
.unavailable-text { color: var(--text-tertiary); }
.strategy-linkage { display: grid; gap: 7px; padding: 16px; border: 1px solid var(--border-subtle); border-radius: var(--radius-md); background: rgba(148, 163, 184, .05); }
.strategy-linkage h3 { margin: 0; font-size: 16px; }
.strategy-linkage p { margin: 0; color: var(--text-secondary); }
.selected-identity { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }
.unavailable-code { color: var(--color-warning, #fcd34d); font-size: 12px; overflow-wrap: anywhere; }
.forecast-kind-labels { display: flex; flex-wrap: wrap; gap: 8px; }
.forecast-kind-labels strong { padding: 6px 9px; border-radius: 999px; background: rgba(56, 189, 248, .12); color: var(--text-accent); font-size: 11px; letter-spacing: .02em; }
.forecast-target-grid, .forecast-provenance-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 220px), 1fr)); gap: 14px; margin: 0; }
.forecast-target-grid > div, .forecast-provenance-grid > section { display: grid; gap: 5px; min-width: 0; }
.forecast-target-grid dt, .forecast-provenance-grid small { color: var(--text-tertiary); font-size: 12px; }
.forecast-target-grid dd { margin: 0; overflow-wrap: anywhere; }
.forecast-ticket-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 280px), 1fr)); gap: 12px; }
.ticket-group { min-width: 0; padding: 15px; border: 1px solid var(--border-subtle); border-radius: var(--radius-md); }
.ticket-group h3, .forecast-provenance-grid h3 { margin: 0 0 10px; font-size: 16px; }
.ticket-group ol { display: grid; gap: 6px; margin: 0; padding: 0; list-style: none; }
.ticket-group li { display: flex; justify-content: space-between; gap: 10px; padding: 8px; border-radius: var(--radius-md); background: rgba(7, 9, 14, .35); font-size: 12px; }
.ticket-group li span { color: var(--text-secondary); white-space: nowrap; }
.ticket-group li strong { text-align: right; letter-spacing: .03em; }
.forecast-provenance-grid > section { align-content: start; padding: 14px; border: 1px solid var(--border-subtle); border-radius: var(--radius-md); }
@media (max-width: 700px) { .research-header, .panel-heading { flex-direction: column; } .group-chip { white-space: normal; } .history-controls > label, .history-controls select, .history-controls input[type="search"], .quiet-button { width: 100%; } .ticket-group li { align-items: flex-start; flex-direction: column; } .ticket-group li strong { text-align: left; } }
</style>
