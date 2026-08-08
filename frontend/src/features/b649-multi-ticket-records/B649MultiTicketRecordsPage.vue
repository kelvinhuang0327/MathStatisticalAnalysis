<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import {
  B649_HISTORY_WINDOWS,
  B649_PREFIX_COUNTS,
  B649_REPRODUCTION_STATUSES,
  B649_RESEARCH_DISCLAIMER,
  B649_SUCCESS_CRITERIA,
  B649RecordsRequestError,
  fetchB649MultiTicketRecords,
  fetchB649MultiTicketSummary,
  type B649HistoryWindow,
  type B649MultiTicketRecord,
  type B649MultiTicketRecordPage,
  type B649MultiTicketSummary,
  type B649PrefixCount,
  type B649ReproductionStatus,
  type B649SuccessCriterion,
} from '../../api/b649MultiTicketRecords'

type LoadState = 'loading' | 'ready' | 'error'
type QueryState = 'idle' | 'loading' | 'success' | 'empty' | 'unavailable' | 'error'

interface SubmittedSelection {
  prefixCount: B649PrefixCount
  window: B649HistoryWindow
  criterion: B649SuccessCriterion
  q?: string
  methodFamily?: string
  reproductionStatus?: B649ReproductionStatus
}

const PAGE_SIZE = 25

const summary = ref<B649MultiTicketSummary | null>(null)
const summaryState = ref<LoadState>('loading')
const summaryError = ref('')
const queryState = ref<QueryState>('idle')
const queryError = ref('')
const page = ref<B649MultiTicketRecordPage | null>(null)
const prefixCount = ref<B649PrefixCount | ''>('')
const windowKind = ref<B649HistoryWindow | ''>('')
const criterion = ref<B649SuccessCriterion | ''>('')
const search = ref('')
const methodFamily = ref('')
const reproductionStatus = ref<B649ReproductionStatus | ''>('')
const submittedSelection = ref<SubmittedSelection | null>(null)
let summaryController: AbortController | null = null
let recordsController: AbortController | null = null
let recordsGeneration = 0

const recordsAvailable = computed(() => summary.value?.records_available === true)
const canQuery = computed(
  () =>
    recordsAvailable.value &&
    prefixCount.value !== '' &&
    windowKind.value !== '' &&
    criterion.value !== '',
)
const displayedRange = computed(() => {
  if (!page.value || page.value.total === 0) return '0'
  const start = page.value.offset + 1
  const end = Math.min(page.value.offset + page.value.items.length, page.value.total)
  return `${start}–${end} / ${page.value.total}`
})
const hasPrevious = computed(() => (page.value?.offset ?? 0) > 0)
const hasNext = computed(
  () =>
    page.value !== null &&
    page.value.offset + page.value.items.length < page.value.total,
)

async function loadSummary(): Promise<void> {
  summaryController?.abort()
  summaryController = new AbortController()
  summaryState.value = 'loading'
  summaryError.value = ''
  try {
    const result = await fetchB649MultiTicketSummary(summaryController.signal)
    summary.value = result
    summaryState.value = 'ready'
    if (!result.records_available) {
      queryState.value = 'unavailable'
    } else if (queryState.value === 'unavailable' && page.value === null) {
      queryState.value = 'idle'
    }
  } catch (error) {
    if (isAbortError(error)) return
    summaryState.value = 'error'
    summaryError.value =
      error instanceof Error ? error.message : '研究摘要目前無法載入。'
  }
}

function currentSelection(): SubmittedSelection | null {
  if (
    prefixCount.value === '' ||
    windowKind.value === '' ||
    criterion.value === ''
  ) {
    return null
  }
  return {
    prefixCount: prefixCount.value,
    window: windowKind.value,
    criterion: criterion.value,
    q: search.value.trim() || undefined,
    methodFamily: methodFamily.value || undefined,
    reproductionStatus: reproductionStatus.value || undefined,
  }
}

async function submitQuery(): Promise<void> {
  const selection = currentSelection()
  if (selection === null || !recordsAvailable.value) return
  submittedSelection.value = selection
  await runQuery(selection, 0)
}

async function runQuery(
  selection: SubmittedSelection,
  offset: number,
): Promise<void> {
  recordsController?.abort()
  recordsController = new AbortController()
  const generation = ++recordsGeneration
  queryState.value = 'loading'
  queryError.value = ''
  try {
    const result = await fetchB649MultiTicketRecords(
      {
        ...selection,
        limit: PAGE_SIZE,
        offset,
      },
      recordsController.signal,
    )
    if (generation !== recordsGeneration) return
    page.value = result
    queryState.value = result.items.length === 0 ? 'empty' : 'success'
  } catch (error) {
    if (isAbortError(error) || generation !== recordsGeneration) return
    page.value = null
    if (
      error instanceof B649RecordsRequestError &&
      error.kind === 'UNAVAILABLE'
    ) {
      queryState.value = 'unavailable'
      queryError.value = error.message
      return
    }
    queryState.value = 'error'
    queryError.value =
      error instanceof Error ? error.message : '查詢目前無法完成。'
  }
}

async function retryQuery(): Promise<void> {
  if (submittedSelection.value !== null) {
    await runQuery(submittedSelection.value, page.value?.offset ?? 0)
    return
  }
  await loadSummary()
}

async function previousPage(): Promise<void> {
  if (submittedSelection.value === null || page.value === null) return
  await runQuery(
    submittedSelection.value,
    Math.max(0, page.value.offset - PAGE_SIZE),
  )
}

async function nextPage(): Promise<void> {
  if (submittedSelection.value === null || page.value === null) return
  await runQuery(submittedSelection.value, page.value.offset + PAGE_SIZE)
}

function percentage(value: string | null): string {
  if (value === null) return '—'
  return `${(Number(value) * 100).toFixed(6)}%`
}

function signedPercentage(value: string | null): string {
  if (value === null) return '—'
  const percentageValue = Number(value) * 100
  const sign = percentageValue > 0 ? '+' : ''
  return `${sign}${percentageValue.toFixed(6)} pp`
}

function shortSha(value: string | null): string {
  return value === null ? '—' : `${value.slice(0, 12)}…`
}

function rankText(record: B649MultiTicketRecord): string {
  return record.rank === null ? record.unranked_reason ?? '—' : `#${record.rank}`
}

function officialRankText(record: B649MultiTicketRecord): string {
  return record.official_rank === null
    ? record.unranked_reason ?? '—'
    : `#${record.official_rank}`
}

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === 'AbortError'
}

onMounted(loadSummary)
onBeforeUnmount(() => {
  summaryController?.abort()
  recordsController?.abort()
  recordsGeneration += 1
})
</script>

<template>
  <section class="b649-records" aria-labelledby="b649-records-title">
    <header class="b649-records__heading">
      <div>
        <p class="eyebrow">B649 · checksum-pinned research</p>
        <h1 id="b649-records-title">大樂透多注歷史預測資料</h1>
        <p class="b649-records__intro">
          唯讀查閱 221 個正式策略身分及已完成的聚合歷史回測紀錄。此頁不執行策略、
          不產生票券、不重跑回測，也不選擇最佳策略。
        </p>
      </div>
      <span class="readonly-badge">READ ONLY</span>
    </header>

    <div v-if="summaryState === 'loading'" class="records-state" role="status" aria-live="polite">
      正在載入研究摘要…
    </div>
    <div v-else-if="summaryState === 'error'" class="records-state records-state--error" role="alert">
      <strong>研究摘要無法載入</strong>
      <p>{{ summaryError }}</p>
      <button type="button" @click="loadSummary">重試</button>
    </div>

    <template v-else-if="summary">
      <section class="research-progress" aria-labelledby="research-progress-title">
        <div class="research-progress__heading">
          <div>
            <p class="eyebrow">Formal disposition</p>
            <h2 id="research-progress-title">完整策略研究進度</h2>
          </div>
          <code :title="summary.catalog_sha256">
            catalog {{ shortSha(summary.catalog_sha256) }}
          </code>
        </div>
        <dl class="research-progress__grid">
          <div>
            <dt>全部方法</dt>
            <dd>{{ summary.progress.total_strategy_count }}</dd>
          </div>
          <div>
            <dt>已復現並回測</dt>
            <dd>{{ summary.progress.backtested_count }}</dd>
          </div>
          <div>
            <dt>正式不可執行</dt>
            <dd>{{ summary.progress.closed_count }}</dd>
          </div>
          <div>
            <dt>重複別名</dt>
            <dd>{{ summary.progress.duplicate_alias_count }}</dd>
          </div>
          <div>
            <dt>待 Owner 決策</dt>
            <dd>{{ summary.progress.owner_decision_required_count }}</dd>
          </div>
          <div>
            <dt>未完成</dt>
            <dd>{{ summary.progress.uncompleted_count }}</dd>
          </div>
        </dl>
      </section>

      <aside class="research-disclaimer" role="note">
        {{ B649_RESEARCH_DISCLAIMER }}
      </aside>

      <form class="records-query" aria-labelledby="records-query-title" @submit.prevent="submitQuery">
        <div class="records-query__heading">
          <div>
            <p class="eyebrow">Explicit query</p>
            <h2 id="records-query-title">選擇查詢條件</h2>
          </div>
          <p>注數、歷史區間與成功標準必須由你明確選擇；系統不提供預設贏家。</p>
        </div>
        <div class="records-query__grid">
          <label>
            <span>注數 <strong aria-hidden="true">*</strong></span>
            <select v-model="prefixCount" name="prefix-count" required>
              <option value="" disabled>請選擇</option>
              <option v-for="value in B649_PREFIX_COUNTS" :key="value" :value="value">
                {{ value }} 注
              </option>
            </select>
          </label>
          <label>
            <span>歷史區間 <strong aria-hidden="true">*</strong></span>
            <select v-model="windowKind" name="history-window" required>
              <option value="" disabled>請選擇</option>
              <option v-for="value in B649_HISTORY_WINDOWS" :key="value" :value="value">
                {{ value }}
              </option>
            </select>
          </label>
          <label>
            <span>成功標準 <strong aria-hidden="true">*</strong></span>
            <select v-model="criterion" name="success-criterion" required>
              <option value="" disabled>請選擇</option>
              <option v-for="value in B649_SUCCESS_CRITERIA" :key="value" :value="value">
                {{ value }}
              </option>
            </select>
          </label>
          <label>
            <span>策略搜尋</span>
            <input
              v-model="search"
              name="strategy-search"
              type="search"
              maxlength="200"
              placeholder="策略 ID、舊方法或來源"
            />
          </label>
          <label>
            <span>方法分類</span>
            <select v-model="methodFamily" name="method-family">
              <option value="">全部分類</option>
              <option v-for="family in summary.method_families" :key="family" :value="family">
                {{ family }}
              </option>
            </select>
          </label>
          <label>
            <span>復現狀態</span>
            <select v-model="reproductionStatus" name="reproduction-status">
              <option value="">全部狀態</option>
              <option
                v-for="status in B649_REPRODUCTION_STATUSES"
                :key="status"
                :value="status"
              >
                {{ status }}
              </option>
            </select>
          </label>
        </div>
        <div class="records-query__actions">
          <p v-if="!recordsAvailable" role="status">
            checksum-pinned 聚合 projection 目前不可用；查詢維持關閉。
          </p>
          <p v-else-if="!canQuery">請先選擇三個必填研究條件。</p>
          <p v-else>準備依明確條件讀取聚合紀錄。</p>
          <button type="submit" :disabled="!canQuery || queryState === 'loading'">
            {{ queryState === 'loading' ? '查詢中…' : '查詢' }}
          </button>
        </div>
      </form>

      <div v-if="queryState === 'idle'" class="records-state" role="status">
        尚未送出查詢。頁面不會自動選擇排名、最新資料或最佳策略。
      </div>
      <div v-else-if="queryState === 'loading'" class="records-state" role="status" aria-live="polite">
        正在讀取 checksum-pinned 聚合紀錄…
      </div>
      <div v-else-if="queryState === 'empty'" class="records-state" role="status">
        <strong>沒有符合條件的策略</strong>
        <p>請調整搜尋文字或篩選條件後重新按下「查詢」。</p>
      </div>
      <div
        v-else-if="queryState === 'unavailable'"
        class="records-state records-state--warning"
        role="status"
      >
        <strong>聚合歷史紀錄目前不可用</strong>
        <p>{{ queryError || '系統找不到完整且 checksum-pinned 的正式 projection。' }}</p>
        <button type="button" @click="retryQuery">重試</button>
      </div>
      <div v-else-if="queryState === 'error'" class="records-state records-state--error" role="alert">
        <strong>查詢失敗</strong>
        <p>{{ queryError }}</p>
        <button type="button" @click="retryQuery">重試</button>
      </div>

      <section v-else-if="queryState === 'success' && page" class="records-results">
        <div class="records-results__heading">
          <div>
            <p class="eyebrow">Aggregate records only</p>
            <h2>查詢結果</h2>
          </div>
          <p aria-live="polite">{{ displayedRange }}</p>
        </div>
        <div
          class="records-table-scroll"
          role="region"
          aria-label="B649 多注歷史預測資料表，可水平捲動"
          tabindex="0"
        >
          <table class="records-table">
            <caption>
              聚合歷史紀錄；不包含逐期 ordered-20、native tickets 或 execution audit。
            </caption>
            <thead>
              <tr>
                <th scope="col">策略／版本</th>
                <th scope="col">歷史方法身分</th>
                <th scope="col">復現狀態</th>
                <th scope="col">查詢條件</th>
                <th scope="col">官方任一獎排名</th>
                <th scope="col">官方任一獎率</th>
                <th scope="col">官方隨機基準</th>
                <th scope="col">官方相對差異</th>
                <th scope="col">次要 M 排名／原因</th>
                <th scope="col">成功／有效期數</th>
                <th scope="col">次要 M 成功率</th>
                <th scope="col">次要 M 隨機基準</th>
                <th scope="col">次要 M 相對差異</th>
                <th scope="col">覆蓋率</th>
                <th scope="col">一獎</th>
                <th scope="col">二獎</th>
                <th scope="col">三獎</th>
                <th scope="col">四獎</th>
                <th scope="col">五獎</th>
                <th scope="col">六獎</th>
                <th scope="col">七獎</th>
                <th scope="col">普獎</th>
                <th scope="col">未中獎</th>
                <th scope="col">report SHA-256</th>
                <th scope="col">catalog SHA-256</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="record in page.items" :key="record.strategy_id">
                <td>
                  <strong>{{ record.strategy_id }}</strong>
                  <small>{{ record.strategy_version }}</small>
                </td>
                <td>
                  <strong>{{ record.legacy_method_id }}</strong>
                  <small>{{ record.source_path }}</small>
                  <small>{{ record.method_family }}</small>
                </td>
                <td>
                  <span class="record-status">{{ record.reproduction_status }}</span>
                  <small v-if="record.duplicate_alias_target">
                    alias → {{ record.duplicate_alias_target }}
                  </small>
                </td>
                <td>
                  {{ record.prefix_count }} / {{ record.window }} / {{ record.criterion }}
                </td>
                <td>{{ officialRankText(record) }}</td>
                <td>{{ percentage(record.official_any_prize_rate) }}</td>
                <td>{{ percentage(record.official_random_baseline_probability) }}</td>
                <td>{{ signedPercentage(record.official_random_baseline_delta) }}</td>
                <td>{{ rankText(record) }}</td>
                <td>
                  <template v-if="record.success_count !== null">
                    {{ record.success_count }} / {{ record.effective_backtest_draw_count }}
                  </template>
                  <template v-else>—</template>
                </td>
                <td>{{ percentage(record.historical_success_rate) }}</td>
                <td>{{ percentage(record.random_baseline_success_rate) }}</td>
                <td>{{ signedPercentage(record.random_baseline_rate_difference) }}</td>
                <td>{{ percentage(record.coverage) }}</td>
                <td>{{ record.official_prize_counts?.first ?? '—' }}</td>
                <td>{{ record.official_prize_counts?.second ?? '—' }}</td>
                <td>{{ record.official_prize_counts?.third ?? '—' }}</td>
                <td>{{ record.official_prize_counts?.fourth ?? '—' }}</td>
                <td>{{ record.official_prize_counts?.fifth ?? '—' }}</td>
                <td>{{ record.official_prize_counts?.sixth ?? '—' }}</td>
                <td>{{ record.official_prize_counts?.seventh ?? '—' }}</td>
                <td>{{ record.official_prize_counts?.general ?? '—' }}</td>
                <td>{{ record.no_prize_count ?? '—' }}</td>
                <td><code :title="record.report_sha256 ?? undefined">{{ shortSha(record.report_sha256) }}</code></td>
                <td><code :title="record.catalog_sha256">{{ shortSha(record.catalog_sha256) }}</code></td>
              </tr>
            </tbody>
          </table>
        </div>
        <nav class="records-pagination" aria-label="查詢結果分頁">
          <button type="button" :disabled="!hasPrevious" @click="previousPage">
            上一頁
          </button>
          <span>{{ displayedRange }}</span>
          <button type="button" :disabled="!hasNext" @click="nextPage">
            下一頁
          </button>
        </nav>
      </section>
    </template>
  </section>
</template>
