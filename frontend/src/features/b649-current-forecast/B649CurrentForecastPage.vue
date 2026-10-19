<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'

import {
  fetchB649CanonicalForecast,
  type B649CanonicalForecast,
} from '../../api/b649CanonicalForecast'

const forecast = ref<B649CanonicalForecast | null>(null)
const loading = ref(false)
const unavailableMessage =
  '目前無法取得排程器提供的 B649 預測；本頁不會顯示舊票券。請稍後重新載入。'

let requestController: AbortController | null = null

async function loadCurrentForecast(): Promise<void> {
  requestController?.abort()
  const controller = new AbortController()
  requestController = controller
  forecast.value = null
  loading.value = true

  try {
    forecast.value = await fetchB649CanonicalForecast(controller.signal)
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError') return
    forecast.value = null
  } finally {
    if (requestController === controller) {
      requestController = null
      loading.value = false
    }
  }
}

onMounted(() => {
  void loadCurrentForecast()
})

onBeforeUnmount(() => {
  requestController?.abort()
})
</script>

<template>
  <section class="b649-current-forecast" aria-labelledby="b649-current-forecast-title">
    <header class="b649-current-forecast__header">
      <div>
        <p class="b649-current-forecast__eyebrow">B649 · 目前預測</p>
        <h1 id="b649-current-forecast-title">B649 目前預測</h1>
        <p class="b649-current-forecast__intro">
          顯示目前排程器提供的 K5、K10 與 K20 票券組合。
        </p>
      </div>
      <button
        class="b649-current-forecast__refresh"
        type="button"
        :disabled="loading"
        @click="loadCurrentForecast"
      >
        {{ loading ? '讀取中…' : '重新載入' }}
      </button>
    </header>

    <p v-if="loading" class="b649-current-forecast__loading" role="status">
      正在讀取目前排程器預測…
    </p>

    <div v-else-if="!forecast" class="b649-current-forecast__unavailable" role="alert">
      <strong>目前預測暫不可用</strong>
      <p>{{ unavailableMessage }}</p>
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

      <section class="b649-current-forecast__tickets" aria-label="目前票券組合">
        <section class="b649-current-forecast__panel" aria-labelledby="b649-current-k5-title">
          <h2 id="b649-current-k5-title">K5</h2>
          <ol class="b649-current-forecast__ticket-list">
            <li
              v-for="(ticket, index) in forecast.k5_tickets"
              :key="`${ticket.ticket_position}-${index}`"
              class="b649-current-forecast__ticket"
              data-testid="b649-ticket-k5"
            >
              <span>票券 {{ ticket.ticket_position }}</span>
              <strong>{{ ticket.predicted_numbers.join(' · ') }}</strong>
            </li>
          </ol>
        </section>

        <section class="b649-current-forecast__panel" aria-labelledby="b649-current-k10-title">
          <h2 id="b649-current-k10-title">K10</h2>
          <ol class="b649-current-forecast__ticket-list">
            <li
              v-for="(ticket, index) in forecast.k10_tickets"
              :key="`${ticket.ticket_position}-${index}`"
              class="b649-current-forecast__ticket"
              data-testid="b649-ticket-k10"
            >
              <span>票券 {{ ticket.ticket_position }}</span>
              <strong>{{ ticket.predicted_numbers.join(' · ') }}</strong>
            </li>
          </ol>
        </section>

        <section class="b649-current-forecast__panel" aria-labelledby="b649-current-k20-title">
          <h2 id="b649-current-k20-title">K20</h2>
          <ol class="b649-current-forecast__ticket-list">
            <li
              v-for="(ticket, index) in forecast.k20_tickets"
              :key="`${ticket.ticket_position}-${index}`"
              class="b649-current-forecast__ticket"
              data-testid="b649-ticket-k20"
            >
              <span>票券 {{ ticket.ticket_position }}</span>
              <strong>{{ ticket.predicted_numbers.join(' · ') }}</strong>
            </li>
          </ol>
        </section>
      </section>

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
  </section>
</template>

<style scoped>
.b649-current-forecast {
  display: grid;
  gap: 20px;
  padding: 32px 0 48px;
}

.b649-current-forecast__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
}

.b649-current-forecast__eyebrow {
  margin-bottom: 8px;
  color: var(--text-accent);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.b649-current-forecast__header h1 {
  margin-bottom: 8px;
  font-size: clamp(28px, 4vw, 40px);
  line-height: 1.15;
}

.b649-current-forecast__intro {
  margin-bottom: 0;
  color: var(--text-secondary);
}

.b649-current-forecast__refresh {
  flex: 0 0 auto;
  padding: 10px 16px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  background: var(--bg-tertiary);
  color: var(--text-primary);
  cursor: pointer;
}

.b649-current-forecast__panel {
  min-width: 0;
  padding: 20px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  background: var(--bg-card);
}

.b649-current-forecast__panel h2 {
  margin-bottom: 16px;
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
  color: var(--text-tertiary);
  font-size: 12px;
}

.b649-current-forecast__target-grid dd,
.b649-current-forecast__method-grid dd,
.b649-current-forecast__provenance-grid dd {
  margin: 0;
  overflow-wrap: anywhere;
}

.b649-current-forecast__tickets {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 300px), 1fr));
  gap: 16px;
}

.b649-current-forecast__ticket-list {
  display: grid;
  gap: 8px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.b649-current-forecast__ticket {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  background: rgba(7, 9, 14, 0.45);
}

.b649-current-forecast__ticket span {
  color: var(--text-secondary);
  white-space: nowrap;
}

.b649-current-forecast__ticket strong {
  font-variant-numeric: tabular-nums;
  letter-spacing: 0.04em;
  text-align: right;
}

.b649-current-forecast__method-grid dd {
  display: grid;
  gap: 4px;
}

.b649-current-forecast__method-grid code,
.b649-current-forecast__provenance-grid code {
  overflow-wrap: anywhere;
}

.b649-current-forecast__details {
  margin-top: 20px;
  border-top: 1px solid var(--border-subtle);
  padding-top: 14px;
}

.b649-current-forecast__details summary {
  color: var(--text-accent);
  cursor: pointer;
  font-weight: 600;
}

.b649-current-forecast__provenance-grid {
  margin-top: 16px;
}

.b649-current-forecast__loading,
.b649-current-forecast__unavailable {
  padding: 18px 20px;
  border: 1px solid var(--color-warning-border);
  border-radius: var(--radius-lg);
  background: var(--color-warning-bg);
}

.b649-current-forecast__unavailable p {
  margin: 6px 0 0;
  color: var(--text-secondary);
}

.b649-current-forecast__evidence-boundary {
  margin: 0;
  padding: 14px 16px;
  border-left: 3px solid var(--secondary-color);
  background: rgba(56, 189, 248, 0.08);
  color: var(--text-secondary);
}

@media (max-width: 640px) {
  .b649-current-forecast__header {
    flex-direction: column;
  }

  .b649-current-forecast__refresh {
    width: 100%;
  }

  .b649-current-forecast__ticket {
    align-items: flex-start;
    flex-direction: column;
  }

  .b649-current-forecast__ticket strong {
    text-align: left;
  }
}
</style>
