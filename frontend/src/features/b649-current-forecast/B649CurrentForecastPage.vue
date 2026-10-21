<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import LotteryNumberBall from '../../components/LotteryNumberBall.vue'
import {
  B649CanonicalForecastRequestError,
  fetchB649CanonicalForecast,
  type B649CanonicalForecast,
} from '../../api/b649CanonicalForecast'

type PortfolioSize = 5 | 10 | 20
type DisplayMode = 'balls' | 'table'
type CopyFeedback = { kind: 'success' | 'error'; message: string }
type ForecastTicket = B649CanonicalForecast['k5_tickets'][number]

const forecast = ref<B649CanonicalForecast | null>(null)
const loading = ref(false)
const selectedPortfolio = ref<PortfolioSize>(5)
const portfolioOptions: PortfolioSize[] = [5, 10, 20]
const displayMode = ref<DisplayMode>('balls')
const loadError = ref<string | null>(null)
const copyFeedback = ref<CopyFeedback | null>(null)
const unavailableMessage =
  '目前沒有可驗證且未過期的排程器預測；本頁不會顯示舊票券或啟用複製。'

const selectedTickets = computed(() => {
  const current = forecast.value
  if (!current) return []
  if (selectedPortfolio.value === 5) return current.k5_tickets
  if (selectedPortfolio.value === 10) return current.k10_tickets
  return current.k20_tickets
})

const canCopyPortfolio = computed(
  () => !loading.value && selectedTickets.value.length === selectedPortfolio.value,
)

let requestController: AbortController | null = null
let expiryTimer: number | null = null
const MAX_TIMEOUT_MS = 2_147_483_647

function clearForecastExpiryTimer(): void {
  if (expiryTimer !== null) {
    window.clearTimeout(expiryTimer)
    expiryTimer = null
  }
}

function expireForecastWhenDue(): void {
  const current = forecast.value
  if (!current) return

  const remaining = Date.parse(current.current_target.scheduled_at) - Date.now()
  if (!Number.isFinite(remaining) || remaining <= 0) {
    forecast.value = null
    loadError.value = '排程器預測的目標期別已過期；票券已隱藏，請重新載入。'
    copyFeedback.value = null
    clearForecastExpiryTimer()
    return
  }

  expiryTimer = window.setTimeout(
    expireForecastWhenDue,
    Math.min(remaining, MAX_TIMEOUT_MS),
  )
}

function scheduleForecastExpiry(): void {
  clearForecastExpiryTimer()
  if (!forecast.value) return

  const remaining = Date.parse(forecast.value.current_target.scheduled_at) - Date.now()
  expiryTimer = window.setTimeout(
    expireForecastWhenDue,
    Math.min(Math.max(remaining, 0), MAX_TIMEOUT_MS),
  )
}

function getForecastDisplayProblem(value: B649CanonicalForecast): string | null {
  const scheduledAt = Date.parse(value.current_target.scheduled_at)
  if (!Number.isFinite(scheduledAt)) {
    return '排程器預測的預定開獎時間格式無效；票券已隱藏。'
  }
  if (scheduledAt <= Date.now()) {
    return '排程器預測的目標期別已過期；票券已隱藏。'
  }

  const groups = [value.k5_tickets, value.k10_tickets, value.k20_tickets]
  for (const tickets of groups) {
    const positions = new Set<number>()
    for (const ticket of tickets) {
      if (positions.has(ticket.ticket_position)) {
        return '排程器預測包含重複票券位置；票券已隱藏。'
      }
      positions.add(ticket.ticket_position)

      const numbers = ticket.predicted_numbers
      if (
        numbers.length !== 6 ||
        numbers.some((number) => !Number.isInteger(number) || number < 1 || number > 49) ||
        new Set(numbers).size !== 6
      ) {
        return '排程器預測的票券必須各含六個互異的 1–49 號碼；票券已隱藏。'
      }
    }
  }

  return null
}

function getErrorMessage(error: unknown): string {
  if (error instanceof Error) return error.message
  if (typeof error === 'string') return error
  if (
    typeof error === 'object' &&
    error !== null &&
    'message' in error &&
    typeof error.message === 'string'
  ) {
    return error.message
  }
  return String(error)
}

function getLoadErrorDetail(error: unknown): string {
  if (error instanceof B649CanonicalForecastRequestError) {
    if (error.status > 0) return 'HTTP ' + error.status + ': ' + error.message
    return error.kind + ': ' + error.message
  }
  return getErrorMessage(error)
}

async function loadCurrentForecast(): Promise<void> {
  requestController?.abort()
  clearForecastExpiryTimer()
  const controller = new AbortController()
  requestController = controller
  forecast.value = null
  loadError.value = null
  copyFeedback.value = null
  loading.value = true

  try {
    const nextForecast = await fetchB649CanonicalForecast(controller.signal)
    if (controller.signal.aborted || requestController !== controller) return

    const displayProblem = getForecastDisplayProblem(nextForecast)
    if (displayProblem) throw new Error(displayProblem)

    forecast.value = nextForecast
    scheduleForecastExpiry()
  } catch (error) {
    if (
      controller.signal.aborted ||
      requestController !== controller ||
      (error instanceof Error && error.name === 'AbortError')
    ) {
      return
    }
    forecast.value = null
    loadError.value = getLoadErrorDetail(error)
  } finally {
    if (requestController === controller) {
      requestController = null
      loading.value = false
    }
  }
}

function choosePortfolio(size: PortfolioSize): void {
  selectedPortfolio.value = size
  copyFeedback.value = null
}

function chooseDisplayMode(mode: DisplayMode): void {
  displayMode.value = mode
  copyFeedback.value = null
}

function formatNumbers(numbers: number[]): string {
  return numbers.join(' ')
}

function formatTicketCopy(target: string, ticket: ForecastTicket): string {
  return 'B649 第 ' + target + ' 期\n票券 ' + ticket.ticket_position + '：' +
    formatNumbers(ticket.predicted_numbers)
}

async function writeClipboard(text: string, successMessage: string): Promise<void> {
  copyFeedback.value = null
  try {
    if (typeof navigator === 'undefined' || typeof navigator.clipboard?.writeText !== 'function') {
      throw new Error('此瀏覽器目前沒有可用的 Clipboard API。')
    }
    await navigator.clipboard.writeText(text)
    copyFeedback.value = { kind: 'success', message: '已複製' + successMessage }
  } catch (error) {
    copyFeedback.value = { kind: 'error', message: '複製失敗：' + getErrorMessage(error) }
  }
}

async function copyTicket(ticket: ForecastTicket): Promise<void> {
  const target = forecast.value?.current_target.draw_number
  if (!target || !canCopyPortfolio.value) return
  await writeClipboard(formatTicketCopy(target, ticket), '票券 ' + ticket.ticket_position)
}

async function copySelectedPortfolio(): Promise<void> {
  const current = forecast.value
  if (!current || !canCopyPortfolio.value) return
  const lines = selectedTickets.value.map((ticket) =>
    '票券 ' + ticket.ticket_position + '：' + formatNumbers(ticket.predicted_numbers),
  )
  const text = [
    'B649 第 ' + current.current_target.draw_number + ' 期 K' + selectedPortfolio.value + ' 組合',
    ...lines,
  ].join('\n')
  await writeClipboard(text, 'K' + selectedPortfolio.value + ' 組合')
}

onMounted(() => {
  void loadCurrentForecast()
})

onBeforeUnmount(() => {
  requestController?.abort()
  requestController = null
  clearForecastExpiryTimer()
})
</script>

<template>
  <section class="b649-current-forecast" aria-labelledby="b649-current-forecast-title">
    <header class="b649-current-forecast__header">
      <div>
        <p class="b649-current-forecast__eyebrow">B649 · 目前預測</p>
        <h1 id="b649-current-forecast-title">B649 目前預測</h1>
        <p class="b649-current-forecast__intro">
          只呈現目前 Forecast API 回傳且可驗證、未過期的票券，不補票或重排號碼。
        </p>
      </div>
      <button
        class="b649-current-forecast__refresh"
        type="button"
        aria-label="重新載入目前預測"
        @click="loadCurrentForecast"
      >
        {{ loading ? '取消並重新載入' : '重新載入' }}
      </button>
    </header>

    <p v-if="loading" class="b649-current-forecast__loading" role="status">
      正在讀取目前排程器預測…
    </p>

    <div v-else-if="!forecast" class="b649-current-forecast__unavailable" role="alert">
      <strong>目前預測暫不可用</strong>
      <p>{{ unavailableMessage }}</p>
      <p v-if="loadError" class="b649-current-forecast__error-detail">
        資料異常：{{ loadError }}
      </p>
    </div>

    <template v-else>
      <section class="b649-current-forecast__panel" aria-labelledby="b649-current-target-title">
        <h2 id="b649-current-target-title">目前目標</h2>
        <dl class="b649-current-forecast__target-grid">
          <div>
            <dt>期別</dt>
            <dd>{{ forecast.current_target.draw_number }}</dd>
          </div>
          <div>
            <dt>開獎日期</dt>
            <dd>{{ forecast.current_target.draw_date }}</dd>
          </div>
          <div>
            <dt>預定開獎時間</dt>
            <dd>
              <time :datetime="forecast.current_target.scheduled_at">
                {{ forecast.current_target.scheduled_at }}
              </time>
            </dd>
          </div>
          <div>
            <dt>資料生成時間</dt>
            <dd>未提供</dd>
          </div>
        </dl>
      </section>

      <section class="b649-current-forecast__controls" aria-label="票券顯示控制">
        <div class="b649-current-forecast__control-group" role="group" aria-label="選擇票券組合">
          <button
            v-for="size in portfolioOptions"
            :key="size"
            type="button"
            class="b649-current-forecast__choice"
            :aria-pressed="selectedPortfolio === size"
            :data-testid="'b649-size-k' + size"
            @click="choosePortfolio(size)"
          >
            K{{ size }}
            <span>{{ size }} 注</span>
          </button>
        </div>
        <div class="b649-current-forecast__control-group" role="group" aria-label="選擇顯示方式">
          <button
            type="button"
            class="b649-current-forecast__choice"
            :aria-pressed="displayMode === 'balls'"
            data-testid="b649-display-balls"
            @click="chooseDisplayMode('balls')"
          >
            樂透球
          </button>
          <button
            type="button"
            class="b649-current-forecast__choice"
            :aria-pressed="displayMode === 'table'"
            data-testid="b649-display-table"
            @click="chooseDisplayMode('table')"
          >
            表格
          </button>
        </div>
      </section>

      <section class="b649-current-forecast__panel b649-current-forecast__tickets" aria-labelledby="b649-current-tickets-title">
        <header class="b649-current-forecast__tickets-header">
          <div>
            <h2 id="b649-current-tickets-title">K{{ selectedPortfolio }} 目前組合</h2>
            <p>共 {{ selectedTickets.length }} 注；票券位置與號碼依 API 回傳順序顯示。</p>
          </div>
          <button
            class="b649-current-forecast__copy b649-current-forecast__copy--primary"
            type="button"
            data-testid="b649-copy-portfolio"
            :disabled="!canCopyPortfolio"
            @click="copySelectedPortfolio"
          >
            複製本組 K{{ selectedPortfolio }}
          </button>
        </header>

        <ol v-if="displayMode === 'balls'" class="b649-current-forecast__ticket-list">
          <li
            v-for="ticket in selectedTickets"
            :key="ticket.ticket_position"
            class="b649-current-forecast__ticket"
            data-testid="b649-ticket-row"
          >
            <div class="b649-current-forecast__ticket-main">
              <span class="b649-current-forecast__ticket-position" data-testid="b649-ticket-position">
                票券 {{ ticket.ticket_position }}
              </span>
              <div class="b649-current-forecast__balls" aria-label="票券號碼">
                <LotteryNumberBall
                  v-for="(number, index) in ticket.predicted_numbers"
                  :key="index"
                  :value="number"
                  size="md"
                  :aria-label="'第 ' + ticket.ticket_position + ' 注，號碼 ' + number"
                />
              </div>
            </div>
            <button
              class="b649-current-forecast__copy"
              type="button"
              :data-testid="'b649-copy-ticket-' + ticket.ticket_position"
              :disabled="!canCopyPortfolio"
              @click="copyTicket(ticket)"
            >
              複製此注
            </button>
          </li>
        </ol>

        <div v-else class="b649-current-forecast__table-wrap">
          <table class="b649-current-forecast__table">
            <thead>
              <tr>
                <th scope="col">票券位置</th>
                <th scope="col">六個號碼</th>
                <th scope="col">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="ticket in selectedTickets"
                :key="ticket.ticket_position"
                data-testid="b649-ticket-row"
              >
                <th scope="row" data-testid="b649-ticket-position">
                  票券 {{ ticket.ticket_position }}
                </th>
                <td data-testid="b649-ticket-numbers">{{ ticket.predicted_numbers.join(' · ') }}</td>
                <td>
                  <button
                    class="b649-current-forecast__copy"
                    type="button"
                    :data-testid="'b649-copy-ticket-' + ticket.ticket_position"
                    :disabled="!canCopyPortfolio"
                    @click="copyTicket(ticket)"
                  >
                    複製此注
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <p
        v-if="copyFeedback"
        class="b649-current-forecast__copy-feedback"
        :class="{ 'is-error': copyFeedback.kind === 'error' }"
        :role="copyFeedback.kind === 'error' ? 'alert' : 'status'"
        aria-live="polite"
      >
        {{ copyFeedback.message }}
      </p>

      <section class="b649-current-forecast__panel" aria-labelledby="b649-current-authority-title">
        <h2 id="b649-current-authority-title">權威方法</h2>
        <dl class="b649-current-forecast__method-grid">
          <div>
            <dt>預測方法</dt>
            <dd>
              <code>{{ forecast.forecast_method_id }}</code>
              <span>版本 {{ forecast.forecast_method_version }}</span>
            </dd>
          </div>
          <div>
            <dt>票券組合方法</dt>
            <dd>
              <code>{{ forecast.portfolio_method_id }}</code>
              <span>版本 {{ forecast.portfolio_method_version }}</span>
            </dd>
          </div>
        </dl>
        <details class="b649-current-forecast__details">
          <summary>資料來源與摘要</summary>
          <dl class="b649-current-forecast__provenance-grid">
            <div>
              <dt>Authority</dt>
              <dd>{{ forecast.authority }}</dd>
            </div>
            <div>
              <dt>來源串流數</dt>
              <dd>{{ forecast.source_stream_count }}</dd>
            </div>
            <div>
              <dt>預測資料 SHA-256</dt>
              <dd><code>{{ forecast.forecast_actual_sha256 }}</code></dd>
            </div>
            <div>
              <dt>票券組合 SHA-256</dt>
              <dd><code>{{ forecast.portfolio_actual_sha256 }}</code></dd>
            </div>
          </dl>
        </details>
      </section>

      <p class="b649-current-forecast__evidence-boundary">
        這些票券組合來自目前排程器權威。精確或模型幾何與已驗證的預測樣本外（OOS）提升是不同的證據。
      </p>
    </template>

    <section class="b649-current-forecast__panel b649-current-forecast__strategy-boundary" aria-labelledby="b649-strategy-boundary-title">
      <h2 id="b649-strategy-boundary-title">三種策略各一注</h2>
      <p>
        尚無可驗證的三策略單注選號資料。Current Forecast API 提供 K5、K10、K20 組合，
        不代表三種獨立策略的最佳預測；本頁不會以 K5 前三注代替。
      </p>
    </section>
  </section>
</template>

<style scoped>
.b649-current-forecast {
  display: grid;
  gap: 20px;
  min-height: 100%;
  padding: 32px 24px 48px;
  border-radius: 20px;
  background: #f4f8ff;
  color: #16324f;
}

.b649-current-forecast__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
}

.b649-current-forecast__eyebrow {
  margin-bottom: 8px;
  color: #2563a8;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.b649-current-forecast__header h1 {
  margin-bottom: 8px;
  color: #14345a;
  font-size: clamp(28px, 4vw, 40px);
  line-height: 1.15;
}

.b649-current-forecast__intro {
  margin-bottom: 0;
  color: #526d87;
}

.b649-current-forecast__refresh,
.b649-current-forecast__choice,
.b649-current-forecast__copy {
  flex: 0 0 auto;
  border: 1px solid #bfd3ec;
  border-radius: 10px;
  background: #ffffff;
  color: #16477e;
  cursor: pointer;
  font: inherit;
  font-weight: 650;
  transition: background-color 0.15s ease, border-color 0.15s ease;
}

.b649-current-forecast__refresh {
  padding: 10px 16px;
}

.b649-current-forecast__choice,
.b649-current-forecast__copy {
  padding: 9px 13px;
}

.b649-current-forecast__refresh:hover,
.b649-current-forecast__choice:hover:not(:disabled),
.b649-current-forecast__copy:hover:not(:disabled) {
  border-color: #2d6db2;
  background: #edf5ff;
}

.b649-current-forecast__panel {
  min-width: 0;
  padding: 20px;
  border: 1px solid #d7e5f5;
  border-radius: 16px;
  background: #ffffff;
  box-shadow: 0 8px 24px rgba(31, 83, 137, 0.06);
}

.b649-current-forecast__panel h2 {
  margin-bottom: 16px;
  color: #173e68;
  font-size: 18px;
}

.b649-current-forecast__target-grid,
.b649-current-forecast__method-grid,
.b649-current-forecast__provenance-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 220px), 1fr));
  gap: 16px;
  margin: 0;
}

.b649-current-forecast__target-grid dt,
.b649-current-forecast__method-grid dt,
.b649-current-forecast__provenance-grid dt {
  margin-bottom: 4px;
  color: #617992;
  font-size: 12px;
}

.b649-current-forecast__target-grid dd,
.b649-current-forecast__method-grid dd,
.b649-current-forecast__provenance-grid dd {
  margin: 0;
  overflow-wrap: anywhere;
  color: #183b60;
}

.b649-current-forecast__controls {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
}

.b649-current-forecast__control-group {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.b649-current-forecast__choice {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.b649-current-forecast__choice span {
  color: #67819b;
  font-size: 12px;
}

.b649-current-forecast__choice[aria-pressed='true'] {
  border-color: #1f63a5;
  background: #1f63a5;
  color: #ffffff;
  box-shadow: 0 4px 10px rgba(31, 99, 165, 0.18);
}

.b649-current-forecast__choice[aria-pressed='true'] span {
  color: #e4f0ff;
}

.b649-current-forecast__tickets {
  display: grid;
  gap: 16px;
}

.b649-current-forecast__tickets-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
}

.b649-current-forecast__tickets-header h2 {
  margin: 0 0 5px;
}

.b649-current-forecast__tickets-header p {
  margin: 0;
  color: #627b94;
  font-size: 13px;
}

.b649-current-forecast__copy--primary {
  padding: 10px 16px;
  border-color: #1f63a5;
  background: #1f63a5;
  color: #ffffff;
  white-space: nowrap;
}

.b649-current-forecast__copy--primary:hover:not(:disabled) {
  border-color: #174e86;
  background: #174e86;
}

.b649-current-forecast__copy:disabled,
.b649-current-forecast__choice:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.b649-current-forecast__ticket-list {
  display: grid;
  gap: 10px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.b649-current-forecast__ticket {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 12px 14px;
  border: 1px solid #e0ebf7;
  border-radius: 12px;
  background: #f9fbff;
}

.b649-current-forecast__ticket-main {
  display: flex;
  align-items: center;
  gap: 18px;
  min-width: 0;
}

.b649-current-forecast__ticket-position {
  min-width: 64px;
  color: #56718e;
  font-size: 13px;
  font-weight: 700;
  white-space: nowrap;
}

.b649-current-forecast__balls {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.b649-current-forecast__table-wrap {
  overflow-x: auto;
}

.b649-current-forecast__table {
  width: 100%;
  border-collapse: collapse;
  color: #183b60;
  text-align: left;
}

.b649-current-forecast__table th,
.b649-current-forecast__table td {
  padding: 11px 12px;
  border-bottom: 1px solid #e4edf8;
}

.b649-current-forecast__table thead th {
  background: #f2f7fd;
  color: #496987;
  font-size: 12px;
}

.b649-current-forecast__table tbody th {
  color: #294e73;
  font-weight: 700;
  white-space: nowrap;
}

.b649-current-forecast__table td[data-testid='b649-ticket-numbers'] {
  font-variant-numeric: tabular-nums;
  letter-spacing: 0.05em;
  white-space: nowrap;
}

.b649-current-forecast__copy-feedback {
  margin: 0;
  padding: 11px 14px;
  border: 1px solid #a9d8ba;
  border-radius: 10px;
  background: #effaf2;
  color: #176236;
}

.b649-current-forecast__copy-feedback.is-error,
.b649-current-forecast__unavailable {
  border-color: #edc1c1;
  background: #fff5f5;
  color: #842d2d;
}

.b649-current-forecast__loading,
.b649-current-forecast__unavailable {
  padding: 18px 20px;
  border: 1px solid #edc1c1;
  border-radius: 14px;
}

.b649-current-forecast__unavailable p {
  margin: 6px 0 0;
  color: #783d3d;
}

.b649-current-forecast__error-detail {
  overflow-wrap: anywhere;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 13px;
}

.b649-current-forecast__method-grid dd {
  display: grid;
  gap: 4px;
}

.b649-current-forecast__method-grid code,
.b649-current-forecast__provenance-grid code {
  overflow-wrap: anywhere;
  color: #1b5489;
}

.b649-current-forecast__details {
  margin-top: 20px;
  border-top: 1px solid #e3edf8;
  padding-top: 14px;
}

.b649-current-forecast__details summary {
  color: #205f9d;
  cursor: pointer;
  font-weight: 700;
}

.b649-current-forecast__provenance-grid {
  margin-top: 16px;
}

.b649-current-forecast__evidence-boundary {
  margin: 0;
  padding: 14px 16px;
  border-left: 3px solid #2876ba;
  border-radius: 0 9px 9px 0;
  background: #eaf4ff;
  color: #405f7c;
}

.b649-current-forecast__strategy-boundary p {
  margin: 0;
  color: #526d87;
  line-height: 1.6;
}

@media (max-width: 640px) {
  .b649-current-forecast {
    padding: 22px 14px 32px;
  }

  .b649-current-forecast__header,
  .b649-current-forecast__tickets-header {
    align-items: stretch;
    flex-direction: column;
  }

  .b649-current-forecast__refresh,
  .b649-current-forecast__copy--primary {
    width: 100%;
  }

  .b649-current-forecast__ticket {
    align-items: flex-start;
    flex-direction: column;
  }

  .b649-current-forecast__ticket-main {
    align-items: flex-start;
    flex-direction: column;
    gap: 10px;
  }

  .b649-current-forecast__balls {
    gap: 6px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .b649-current-forecast__refresh,
  .b649-current-forecast__choice,
  .b649-current-forecast__copy {
    transition: none;
  }
}
</style>
