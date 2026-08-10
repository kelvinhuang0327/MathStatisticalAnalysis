<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import {
  getP638StrategyTarget,
  listP638Draws,
  listP638Runs,
  listP638Strategies,
  P638HistoricalRequestError,
  type P638Draw,
  type P638Replay,
  type P638Run,
  type P638Strategy,
} from '../../api/p638Historical'
import {
  getT539StrategyTarget,
  listT539Draws,
  listT539Runs,
  listT539Strategies,
  T539HistoricalRequestError,
  type T539Draw,
  type T539Replay,
  type T539Run,
  type T539Strategy,
} from '../../api/t539Historical'

type Lottery = 'DAILY_539' | 'POWER_LOTTO'
type State =
  | 'idle'
  | 'loading'
  | 'ready'
  | 'empty'
  | 'not-configured'
  | 'unavailable'
  | 'not-found'
  | 'malformed'
  | 'error'

type HistoricalRun = T539Run | P638Run
type HistoricalDraw = T539Draw | P638Draw
type HistoricalStrategy = T539Strategy | P638Strategy
type HistoricalTarget = T539Replay | P638Replay

interface PageWindow<T> {
  items: T[]
  total_count: number
  limit: number
  offset: number
}

interface RunRow {
  id: string
  status: string
  drawCount: number
  strategyCount: number
  ticketCount: number
  range: string
  source: HistoricalRun
}

interface DrawRow {
  id: string
  date: string
  firstZoneNumbers: number[]
  secondZoneNumber: number | null
  source: HistoricalDraw
}

interface StrategyRow {
  key: string
  id: string
  version: string
  label: string
  nativeTicketCount: number | null
  status: string
  ticketCount: number
  source: HistoricalStrategy
}

interface TicketRow {
  position: number
  firstZoneNumbers: number[]
  secondZoneNumber: number | null
  actualFirstZoneNumbers: number[]
  actualSecondZoneNumber: number | null
  hitSummary: string
  isWinner: boolean
  prizeTier: string | null
  prizeAmount: number | null
  resultStatus: string | null
}

interface TargetView {
  targetId: string
  drawId: string
  drawDate: string
  strategyId: string
  strategyVersion: string
  status: string
  reasonType: string | null
  reason: string | null
  targetSuccess: boolean | null
  historyLength: number | null
  expectedTicketCount: number
  actualFirstZoneNumbers: number[]
  actualSecondZoneNumber: number | null
  tickets: TicketRow[]
}

const RUN_PAGE_SIZE = 25
const DRAW_PAGE_SIZE = 25
const STRATEGY_PAGE_SIZE = 25

const lottery = ref<Lottery>('DAILY_539')
const runsState = ref<State>('loading')
const runsMessage = ref('')
const runsPage = ref<PageWindow<RunRow> | null>(null)
const selectedRunId = ref('')

const drawsState = ref<State>('idle')
const drawsMessage = ref('')
const drawsPage = ref<PageWindow<DrawRow> | null>(null)
const selectedDrawId = ref('')

const strategiesState = ref<State>('idle')
const strategiesMessage = ref('')
const strategiesPage = ref<PageWindow<StrategyRow> | null>(null)
const selectedStrategyKey = ref('')

const detailState = ref<State>('idle')
const detailMessage = ref('')
const detail = ref<HistoricalTarget | null>(null)

let mounted = false
let runsController: AbortController | undefined
let drawsController: AbortController | undefined
let strategiesController: AbortController | undefined
let detailController: AbortController | undefined
let runsGeneration = 0
let drawsGeneration = 0
let strategiesGeneration = 0
let detailGeneration = 0

const lotteryLabel = computed(() => (lottery.value === 'DAILY_539' ? 'T539 / Daily 539' : 'P638 / Power Lotto'))
const selectedRun = computed<RunRow | null>(
  () => runsPage.value?.items.find((run) => run.id === selectedRunId.value) ?? null,
)
const selectedDraw = computed<DrawRow | null>(
  () => drawsPage.value?.items.find((draw) => draw.id === selectedDrawId.value) ?? null,
)
const selectedStrategy = computed<StrategyRow | null>(
  () => strategiesPage.value?.items.find((strategy) => strategy.key === selectedStrategyKey.value) ?? null,
)
const targetView = computed<TargetView | null>(() => {
  if (!detail.value) return null

  if (lottery.value === 'DAILY_539') {
    const target = detail.value as T539Replay
    return {
      targetId: target.target_id,
      drawId: target.target_draw_id,
      drawDate: target.target_draw_date ?? selectedDraw.value?.date ?? '—',
      strategyId: target.strategy_id,
      strategyVersion: target.strategy_version,
      status: target.status,
      reasonType: target.reason_type,
      reason: target.reason,
      targetSuccess: target.target_success,
      historyLength: target.history_length,
      expectedTicketCount: target.native_ticket_count,
      actualFirstZoneNumbers: selectedDraw.value?.firstZoneNumbers ?? [],
      actualSecondZoneNumber: null,
      tickets: target.tickets.map((ticket) => ({
        position: ticket.ticket_position,
        firstZoneNumbers: ticket.predicted_numbers,
        secondZoneNumber: null,
        actualFirstZoneNumbers: ticket.actual_numbers,
        actualSecondZoneNumber: null,
        hitSummary: `${ticket.hits} hits · ${ticket.hit_numbers.join(', ') || 'no matching numbers'}`,
        isWinner: ticket.is_winner,
        prizeTier: ticket.prize_tier,
        prizeAmount: ticket.prize_amount,
        resultStatus: null,
      })),
    }
  }

  const target = detail.value as P638Replay
  return {
    targetId: target.target_id,
    drawId: target.target_draw_number,
    drawDate: target.target_draw_date,
    strategyId: target.strategy_id,
    strategyVersion: target.strategy_version,
    status: target.status,
    reasonType: target.reason_type ?? target.exclusion_reason,
    reason: target.reason ?? target.failure_reason,
    targetSuccess: target.target_success,
    historyLength: target.history_length,
    expectedTicketCount: target.expected_ticket_count,
    actualFirstZoneNumbers: target.actual_zone1_numbers,
    actualSecondZoneNumber: target.actual_zone2_number,
    tickets: target.tickets.map((ticket) => ({
      position: ticket.ticket_position,
      firstZoneNumbers: ticket.predicted_zone1_numbers,
      secondZoneNumber: ticket.predicted_zone2_number,
      actualFirstZoneNumbers: ticket.actual_zone1_numbers,
      actualSecondZoneNumber: ticket.actual_zone2_number,
      hitSummary: `${ticket.zone1_hit_count} first-zone hits · second zone ${ticket.zone2_hit ? 'HIT' : 'MISS'}`,
      isWinner: ticket.is_winner,
      prizeTier: ticket.prize_tier,
      prizeAmount: ticket.prize_amount,
      resultStatus: ticket.status,
    })),
  }
})

function isCurrent(generation: number, currentGeneration: number, requestLottery: Lottery): boolean {
  return mounted && generation === currentGeneration && requestLottery === lottery.value
}

function resetRunData(): void {
  selectedDrawId.value = ''
  selectedStrategyKey.value = ''
  drawsPage.value = null
  strategiesPage.value = null
  drawsState.value = 'idle'
  strategiesState.value = 'idle'
  drawsMessage.value = ''
  strategiesMessage.value = ''
  closeDetail()
}

function selectLottery(nextLottery: Lottery): void {
  if (lottery.value === nextLottery && runsPage.value) return
  lottery.value = nextLottery
  runsController?.abort()
  drawsController?.abort()
  strategiesController?.abort()
  resetRunData()
  runsPage.value = null
  selectedRunId.value = ''
  void loadRuns(0)
}

async function loadRuns(offset: number): Promise<void> {
  runsController?.abort()
  const controller = new AbortController()
  runsController = controller
  const generation = ++runsGeneration
  const requestLottery = lottery.value
  runsState.value = 'loading'
  runsMessage.value = ''

  try {
    const page =
      requestLottery === 'DAILY_539'
        ? await listT539Runs({ limit: RUN_PAGE_SIZE, offset }, controller.signal)
        : await listP638Runs({ limit: RUN_PAGE_SIZE, offset }, controller.signal)
    if (!isCurrent(generation, runsGeneration, requestLottery)) return

    runsPage.value = {
      items: page.items.map((run) => normalizeRun(requestLottery, run)),
      total_count: page.total_count,
      limit: page.limit,
      offset: page.offset,
    }
    runsState.value = page.items.length ? 'ready' : 'empty'
    const nextRunId = page.items.some((run) => run.run_id === selectedRunId.value)
      ? selectedRunId.value
      : (page.items[0]?.run_id ?? '')
    selectedRunId.value = nextRunId
    resetRunData()
    if (nextRunId) await selectRun(nextRunId)
  } catch (error: unknown) {
    if (!isCurrent(generation, runsGeneration, requestLottery) || isAbort(error)) return
    runsPage.value = null
    runsState.value = mapState(error)
    runsMessage.value = errorMessage(error, `${lotteryLabel.value} historical runs could not load.`)
  }
}

async function selectRun(runId: string): Promise<void> {
  if (!runId) return
  selectedRunId.value = runId
  selectedDrawId.value = ''
  selectedStrategyKey.value = ''
  drawsPage.value = null
  strategiesPage.value = null
  drawsState.value = 'loading'
  strategiesState.value = 'loading'
  drawsMessage.value = ''
  strategiesMessage.value = ''
  closeDetail()
  await Promise.all([loadDraws(runId, 0), loadStrategies(runId, 0)])
}

async function loadDraws(runId: string, offset: number): Promise<void> {
  drawsController?.abort()
  const controller = new AbortController()
  drawsController = controller
  const generation = ++drawsGeneration
  const requestLottery = lottery.value
  drawsState.value = 'loading'
  drawsMessage.value = ''

  try {
    const page =
      requestLottery === 'DAILY_539'
        ? await listT539Draws(runId, { limit: DRAW_PAGE_SIZE, offset }, controller.signal)
        : await listP638Draws(runId, { limit: DRAW_PAGE_SIZE, offset }, controller.signal)
    if (!isCurrent(generation, drawsGeneration, requestLottery) || selectedRunId.value !== runId) return

    drawsPage.value = {
      items: page.items.map((draw) => normalizeDraw(requestLottery, draw)),
      total_count: page.total_count,
      limit: page.limit,
      offset: page.offset,
    }
    drawsState.value = page.items.length ? 'ready' : 'empty'
    if (!page.items.some((draw) => drawId(requestLottery, draw) === selectedDrawId.value)) {
      selectedDrawId.value = ''
      closeDetail()
    }
  } catch (error: unknown) {
    if (!isCurrent(generation, drawsGeneration, requestLottery) || isAbort(error)) return
    drawsPage.value = null
    drawsState.value = mapState(error)
    drawsMessage.value = errorMessage(error, 'Official draw history could not load.')
  }
}

async function loadStrategies(runId: string, offset: number): Promise<void> {
  strategiesController?.abort()
  const controller = new AbortController()
  strategiesController = controller
  const generation = ++strategiesGeneration
  const requestLottery = lottery.value
  strategiesState.value = 'loading'
  strategiesMessage.value = ''

  try {
    const page =
      requestLottery === 'DAILY_539'
        ? await listT539Strategies(runId, { limit: STRATEGY_PAGE_SIZE, offset }, controller.signal)
        : await listP638Strategies(runId, { limit: STRATEGY_PAGE_SIZE, offset }, controller.signal)
    if (!isCurrent(generation, strategiesGeneration, requestLottery) || selectedRunId.value !== runId) return

    strategiesPage.value = {
      items: page.items.map((strategy) => normalizeStrategy(requestLottery, strategy)),
      total_count: page.total_count,
      limit: page.limit,
      offset: page.offset,
    }
    strategiesState.value = page.items.length ? 'ready' : 'empty'
    if (!page.items.some((strategy) => strategyKey(requestLottery, strategy) === selectedStrategyKey.value)) {
      selectedStrategyKey.value = ''
      closeDetail()
    }
  } catch (error: unknown) {
    if (!isCurrent(generation, strategiesGeneration, requestLottery) || isAbort(error)) return
    strategiesPage.value = null
    strategiesState.value = mapState(error)
    strategiesMessage.value = errorMessage(error, 'Strategy history could not load.')
  }
}

function chooseDraw(drawIdValue: string): void {
  selectedDrawId.value = drawIdValue
  void loadSelectedTarget()
}

function chooseStrategy(strategyKeyValue: string): void {
  selectedStrategyKey.value = strategyKeyValue
  void loadSelectedTarget()
}

async function loadSelectedTarget(): Promise<void> {
  const runId = selectedRunId.value
  const draw = selectedDraw.value
  const strategy = selectedStrategy.value
  if (!runId || !draw || !strategy) {
    closeDetail()
    return
  }

  detailController?.abort()
  const controller = new AbortController()
  detailController = controller
  const generation = ++detailGeneration
  const requestLottery = lottery.value
  detailState.value = 'loading'
  detailMessage.value = ''
  detail.value = null

  try {
    const target =
      requestLottery === 'DAILY_539'
        ? await getT539StrategyTarget(runId, strategy.id, strategy.version, draw.id, controller.signal)
        : await getP638StrategyTarget(runId, strategy.id, strategy.version, draw.id, controller.signal)
    if (
      !isCurrent(generation, detailGeneration, requestLottery) ||
      selectedRunId.value !== runId ||
      selectedDrawId.value !== draw.id ||
      selectedStrategyKey.value !== strategy.key
    ) {
      return
    }
    detail.value = target
    detailState.value = 'ready'
  } catch (error: unknown) {
    if (!isCurrent(generation, detailGeneration, requestLottery) || isAbort(error)) return
    detail.value = null
    detailState.value = mapState(error)
    detailMessage.value = errorMessage(error, 'The selected strategy target could not load.')
  }
}

function closeDetail(): void {
  detailController?.abort()
  detailController = undefined
  detailGeneration += 1
  detail.value = null
  detailState.value = 'idle'
  detailMessage.value = ''
}

function changeRunPage(direction: -1 | 1): void {
  const page = runsPage.value
  if (!page) return
  const nextOffset = page.offset + direction * page.limit
  if (nextOffset < 0 || nextOffset >= page.total_count) return
  void loadRuns(nextOffset)
}

function changeDrawPage(direction: -1 | 1): void {
  const page = drawsPage.value
  if (!page || !selectedRunId.value) return
  const nextOffset = page.offset + direction * page.limit
  if (nextOffset < 0 || nextOffset >= page.total_count) return
  void loadDraws(selectedRunId.value, nextOffset)
}

function changeStrategyPage(direction: -1 | 1): void {
  const page = strategiesPage.value
  if (!page || !selectedRunId.value) return
  const nextOffset = page.offset + direction * page.limit
  if (nextOffset < 0 || nextOffset >= page.total_count) return
  void loadStrategies(selectedRunId.value, nextOffset)
}

function normalizeRun(kind: Lottery, run: HistoricalRun): RunRow {
  if (kind === 'DAILY_539') {
    const value = run as T539Run
    return {
      id: value.run_id,
      status: value.status,
      drawCount: value.draw_count,
      strategyCount: value.strategy_count,
      ticketCount: value.ticket_count,
      range: `${value.first_draw_id ?? '—'} → ${value.last_draw_id ?? '—'}`,
      source: value,
    }
  }

  const value = run as P638Run
  return {
    id: value.run_id,
    status: value.status,
    drawCount: value.draw_count,
    strategyCount: value.strategy_count,
    ticketCount: value.ticket_count,
    range: `${value.first_draw_number} → ${value.last_draw_number}`,
    source: value,
  }
}

function normalizeDraw(kind: Lottery, draw: HistoricalDraw): DrawRow {
  if (kind === 'DAILY_539') {
    const value = draw as T539Draw
    return {
      id: value.draw_id,
      date: value.draw_date,
      firstZoneNumbers: value.winning_numbers,
      secondZoneNumber: null,
      source: value,
    }
  }

  const value = draw as P638Draw
  return {
    id: value.draw_number,
    date: value.draw_date,
    firstZoneNumbers: value.winning_zone1_numbers,
    secondZoneNumber: value.winning_zone2_number,
    source: value,
  }
}

function normalizeStrategy(kind: Lottery, strategy: HistoricalStrategy): StrategyRow {
  if (kind === 'DAILY_539') {
    const value = strategy as T539Strategy
    return {
      key: strategyKey(kind, value),
      id: value.strategy_id,
      version: value.strategy_version,
      label: value.strategy_id,
      nativeTicketCount: value.native_ticket_count,
      status: value.status,
      ticketCount: value.ticket_count,
      source: value,
    }
  }

  const value = strategy as P638Strategy
  return {
    key: strategyKey(kind, value),
    id: value.strategy_id,
    version: value.strategy_version,
    label: value.display_label,
    nativeTicketCount: value.native_ticket_count,
    status: value.replay_status,
    ticketCount: value.ticket_count,
    source: value,
  }
}

function strategyKey(kind: Lottery, strategy: HistoricalStrategy): string {
  const value = strategy as T539Strategy | P638Strategy
  return `${value.strategy_id}::${value.strategy_version}::${kind}`
}

function drawId(kind: Lottery, draw: HistoricalDraw): string {
  return kind === 'DAILY_539' ? (draw as T539Draw).draw_id : (draw as P638Draw).draw_number
}

function pageRange<T>(page: PageWindow<T> | null): string {
  if (!page || page.total_count === 0) return '0–0 of 0'
  return `${page.offset + 1}–${Math.min(page.offset + page.limit, page.total_count)} of ${page.total_count}`
}

function hasPrevious<T>(page: PageWindow<T> | null): boolean {
  return Boolean(page && page.offset > 0)
}

function hasNext<T>(page: PageWindow<T> | null): boolean {
  return Boolean(page && page.offset + page.limit < page.total_count)
}

function isCompleteStatus(status: string): boolean {
  return status === 'COMPLETE_CAUSAL_REPLAY' || status === 'COMPLETE'
}

function statusExplanation(status: string): string {
  if (isCompleteStatus(status)) {
    return 'COMPLETE_CAUSAL_REPLAY — stored native ticket rows are shown below as historical replay evidence.'
  }
  if (status === 'PRE_ELIGIBILITY') {
    return 'PRE_ELIGIBILITY — this target is a historical pre-eligibility state, not a generated prediction.'
  }
  if (status === 'SOURCE_NATIVE_TYPED_CLOSURE') {
    return 'SOURCE_NATIVE_TYPED_CLOSURE — an accepted source-native historical closure; no synthetic ticket is created.'
  }
  return `${status} — no generated ticket interpretation is applied to this historical record.`
}

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback
}

function mapState(error: unknown): State {
  if (error instanceof T539HistoricalRequestError || error instanceof P638HistoricalRequestError) {
    if (error.kind === 'NOT_CONFIGURED') return 'not-configured'
    if (error.kind === 'UNAVAILABLE') return 'unavailable'
    if (error.kind === 'NOT_FOUND') return 'not-found'
    if (error.kind === 'MALFORMED_RESPONSE') return 'malformed'
  }
  return 'error'
}

function isAbort(error: unknown): boolean {
  return (error instanceof DOMException || error instanceof Error) && error.name === 'AbortError'
}

function formatCount(value: number | null): string {
  return value === null ? '—' : value.toLocaleString()
}

function formatNumbers(numbers: number[]): string {
  return numbers.length ? numbers.join(', ') : '—'
}

function prizeText(ticket: TicketRow): string {
  if (!ticket.prizeTier && ticket.prizeAmount === null) return 'No prize result'
  const tier = ticket.prizeTier ?? 'Prize recorded'
  return ticket.prizeAmount === null ? tier : `${tier} · ${ticket.prizeAmount.toLocaleString()}`
}

onMounted(() => {
  mounted = true
  void loadRuns(0)
})

onBeforeUnmount(() => {
  mounted = false
  runsController?.abort()
  drawsController?.abort()
  strategiesController?.abort()
  detailController?.abort()
})
</script>

<template>
  <section class="workspace-page historical-base-data-page" aria-labelledby="historical-base-data-title">
    <header class="page-heading">
      <div>
        <p class="eyebrow">Read-only historical inspection</p>
        <h1 id="historical-base-data-title">Historical Base Data</h1>
        <p class="page-intro">
          Browse the frozen lottery run, official draw, strategy identity, exact target state, and
          every native ticket returned by the T539/P638 base-data APIs. This workspace does not
          generate, rank, or recommend tickets.
        </p>
      </div>
      <div class="scope-card">
        <span>Current source</span>
        <strong>{{ lotteryLabel }}</strong>
        <small>GET-only historical records</small>
      </div>
    </header>

    <section class="panel historical-base-data-controls" aria-labelledby="historical-lottery-title">
      <div class="panel__heading">
        <div>
          <p class="step-label">1 · Select lottery</p>
          <h2 id="historical-lottery-title">Historical source</h2>
        </div>
        <span class="table-note">No database writes</span>
      </div>
      <fieldset class="lottery-switch">
        <legend class="sr-only">Lottery</legend>
        <label>
          <input
            type="radio"
            name="historical-lottery"
            value="DAILY_539"
            :checked="lottery === 'DAILY_539'"
            @change="selectLottery('DAILY_539')"
          />
          <span>DAILY_539 · T539</span>
        </label>
        <label>
          <input
            type="radio"
            name="historical-lottery"
            value="POWER_LOTTO"
            :checked="lottery === 'POWER_LOTTO'"
            @change="selectLottery('POWER_LOTTO')"
          />
          <span>POWER_LOTTO · P638</span>
        </label>
      </fieldset>
    </section>

    <section class="panel" aria-labelledby="historical-runs-title">
      <div class="panel__heading">
        <div>
          <p class="step-label">2 · Select run</p>
          <h2 id="historical-runs-title">Available historical runs</h2>
        </div>
        <button class="button button--quiet" type="button" data-testid="historical-refresh-runs" @click="loadRuns(0)">
          Refresh
        </button>
      </div>
      <p v-if="runsState === 'loading'" class="state-panel" data-testid="historical-runs-loading">
        Loading {{ lotteryLabel }} historical runs…
      </p>
      <div v-else-if="runsState === 'empty'" class="state-panel">No historical run is available.</div>
      <div v-else-if="runsState !== 'ready'" class="state-panel state-panel--error">
        <p>{{ runsMessage }}</p>
        <button class="button button--quiet" type="button" data-testid="historical-retry-runs" @click="loadRuns(0)">
          Retry
        </button>
      </div>
      <template v-else-if="runsPage">
        <div class="table-wrap">
          <table>
            <caption>Historical runs — server response order</caption>
            <thead>
              <tr>
                <th>Run</th>
                <th>Status</th>
                <th>Draw range</th>
                <th>Strategies</th>
                <th>Draws</th>
                <th>Tickets</th>
                <th>Select</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="run in runsPage.items" :key="run.id" :data-testid="`historical-run-row-${run.id}`">
                <td><code>{{ run.id }}</code></td>
                <td><span class="status-pill status-pill--complete">{{ run.status }}</span></td>
                <td>{{ run.range }}</td>
                <td>{{ formatCount(run.strategyCount) }}</td>
                <td>{{ formatCount(run.drawCount) }}</td>
                <td>{{ formatCount(run.ticketCount) }}</td>
                <td>
                  <button
                    class="button button--quiet"
                    type="button"
                    :data-testid="`historical-select-run-${run.id}`"
                    :aria-pressed="selectedRunId === run.id"
                    @click="selectRun(run.id)"
                  >
                    {{ selectedRunId === run.id ? 'Selected' : 'Inspect' }}
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="pagination historical-pagination" data-testid="historical-runs-pagination">
          <button class="button button--quiet" type="button" :disabled="!hasPrevious(runsPage)" @click="changeRunPage(-1)">
            Previous
          </button>
          <span>Showing {{ pageRange(runsPage) }}</span>
          <button class="button button--quiet" type="button" :disabled="!hasNext(runsPage)" @click="changeRunPage(1)">
            Next
          </button>
        </div>
      </template>
    </section>

    <template v-if="selectedRun">
      <div class="historical-base-data-selection-note">
        <strong>Selected run:</strong> <code>{{ selectedRun.id }}</code>
        <span>{{ selectedRun.status }} · {{ selectedRun.range }}</span>
      </div>

      <div class="historical-base-data-columns">
        <section class="panel" aria-labelledby="historical-draws-title">
          <div class="panel__heading">
            <div>
              <p class="step-label">3 · Select official draw</p>
              <h2 id="historical-draws-title">Official draw history</h2>
            </div>
            <span class="table-note">{{ drawsPage ? pageRange(drawsPage) : '—' }}</span>
          </div>
          <p v-if="drawsState === 'loading'" class="state-panel">Loading official draws…</p>
          <p v-else-if="drawsState === 'empty'" class="state-panel">No official draw is available for this run.</p>
          <div v-else-if="drawsState !== 'ready'" class="state-panel state-panel--error">
            <p>{{ drawsMessage }}</p>
            <button class="button button--quiet" type="button" @click="loadDraws(selectedRunId, drawsPage?.offset ?? 0)">
              Retry
            </button>
          </div>
          <template v-else-if="drawsPage">
            <div class="table-wrap">
              <table>
                <caption>Official winning numbers</caption>
                <thead><tr><th>Draw</th><th>Date</th><th>Winning numbers</th><th>Target</th></tr></thead>
                <tbody>
                  <tr v-for="draw in drawsPage.items" :key="draw.id" :data-testid="`historical-draw-row-${draw.id}`">
                    <td><code>{{ draw.id }}</code></td>
                    <td>{{ draw.date }}</td>
                    <td>
                      {{ formatNumbers(draw.firstZoneNumbers) }}
                      <small v-if="draw.secondZoneNumber !== null">Second zone: {{ draw.secondZoneNumber }}</small>
                    </td>
                    <td>
                      <button
                        class="button button--quiet"
                        type="button"
                        :data-testid="`historical-select-draw-${draw.id}`"
                        :aria-pressed="selectedDrawId === draw.id"
                        @click="chooseDraw(draw.id)"
                      >
                        {{ selectedDrawId === draw.id ? 'Selected' : 'Inspect' }}
                      </button>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div class="pagination historical-pagination" data-testid="historical-draws-pagination">
              <button class="button button--quiet" type="button" :disabled="!hasPrevious(drawsPage)" @click="changeDrawPage(-1)">Previous</button>
              <span>Showing {{ pageRange(drawsPage) }}</span>
              <button class="button button--quiet" type="button" :disabled="!hasNext(drawsPage)" @click="changeDrawPage(1)">Next</button>
            </div>
          </template>
        </section>

        <section class="panel" aria-labelledby="historical-strategies-title">
          <div class="panel__heading">
            <div>
              <p class="step-label">4 · Select strategy</p>
              <h2 id="historical-strategies-title">Native strategy records</h2>
            </div>
            <span class="table-note">{{ strategiesPage ? pageRange(strategiesPage) : '—' }}</span>
          </div>
          <p v-if="strategiesState === 'loading'" class="state-panel">Loading strategy records…</p>
          <p v-else-if="strategiesState === 'empty'" class="state-panel">No strategy record is available for this run.</p>
          <div v-else-if="strategiesState !== 'ready'" class="state-panel state-panel--error">
            <p>{{ strategiesMessage }}</p>
            <button class="button button--quiet" type="button" @click="loadStrategies(selectedRunId, strategiesPage?.offset ?? 0)">
              Retry
            </button>
          </div>
          <template v-else-if="strategiesPage">
            <div class="table-wrap">
              <table>
                <caption>Strategy identity and native ticket count</caption>
                <thead><tr><th>Strategy</th><th>Version</th><th>Status</th><th>Native tickets</th><th>Stored rows</th><th>Target</th></tr></thead>
                <tbody>
                  <tr v-for="strategy in strategiesPage.items" :key="strategy.key" :data-testid="`historical-strategy-row-${strategy.key}`">
                    <td><strong>{{ strategy.label }}</strong><small><code>{{ strategy.id }}</code></small></td>
                    <td><code>{{ strategy.version }}</code></td>
                    <td>{{ strategy.status }}</td>
                    <td>{{ formatCount(strategy.nativeTicketCount) }}</td>
                    <td>{{ formatCount(strategy.ticketCount) }}</td>
                    <td>
                      <button
                        class="button button--quiet"
                        type="button"
                        :data-testid="`historical-select-strategy-${strategy.id}-${strategy.version}`"
                        :aria-pressed="selectedStrategyKey === strategy.key"
                        @click="chooseStrategy(strategy.key)"
                      >
                        {{ selectedStrategyKey === strategy.key ? 'Selected' : 'Inspect' }}
                      </button>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div class="pagination historical-pagination" data-testid="historical-strategies-pagination">
              <button class="button button--quiet" type="button" :disabled="!hasPrevious(strategiesPage)" @click="changeStrategyPage(-1)">Previous</button>
              <span>Showing {{ pageRange(strategiesPage) }}</span>
              <button class="button button--quiet" type="button" :disabled="!hasNext(strategiesPage)" @click="changeStrategyPage(1)">Next</button>
            </div>
          </template>
        </section>
      </div>

      <section class="panel historical-target-panel" aria-labelledby="historical-target-title">
        <div class="panel__heading">
          <div>
            <p class="step-label">5 · Exact strategy-target detail</p>
            <h2 id="historical-target-title">Selected historical target</h2>
          </div>
          <span v-if="selectedDraw && selectedStrategy" class="table-note">{{ selectedDraw.id }} · {{ selectedStrategy.id }} · {{ selectedStrategy.version }}</span>
        </div>
        <p v-if="!selectedDraw || !selectedStrategy" class="state-panel" data-testid="historical-target-empty">
          Select one official draw and one strategy to request the exact strategy-target record.
        </p>
        <p v-else-if="detailState === 'loading'" class="state-panel" data-testid="historical-target-loading">
          Loading the exact strategy-target record…
        </p>
        <div v-else-if="detailState !== 'ready'" class="state-panel state-panel--error">
          <p>{{ detailMessage }}</p>
          <button class="button button--quiet" type="button" data-testid="historical-retry-target" @click="loadSelectedTarget">
            Retry
          </button>
        </div>
        <template v-else-if="targetView">
          <div class="historical-target-identity">
            <div><span>Target ID</span><strong><code>{{ targetView.targetId }}</code></strong></div>
            <div><span>Draw</span><strong>{{ targetView.drawId }} · {{ targetView.drawDate }}</strong></div>
            <div><span>Strategy</span><strong>{{ targetView.strategyId }} · {{ targetView.strategyVersion }}</strong></div>
            <div><span>Target success</span><strong>{{ targetView.targetSuccess === null ? '—' : targetView.targetSuccess ? 'YES' : 'NO' }}</strong></div>
            <div><span>History length</span><strong>{{ formatCount(targetView.historyLength) }}</strong></div>
            <div><span>Expected native tickets</span><strong>{{ formatCount(targetView.expectedTicketCount) }}</strong></div>
          </div>
          <p class="historical-target-status" data-testid="historical-target-status">{{ statusExplanation(targetView.status) }}</p>
          <p v-if="targetView.reason || targetView.reasonType" class="panel__note historical-target-reason">
            <strong>{{ targetView.reasonType ?? 'Historical reason' }}:</strong> {{ targetView.reason ?? '—' }}
          </p>
          <div class="historical-official-result">
            <span>Official draw result</span>
            <strong>{{ formatNumbers(targetView.actualFirstZoneNumbers) }}</strong>
            <strong v-if="targetView.actualSecondZoneNumber !== null">+ second zone {{ targetView.actualSecondZoneNumber }}</strong>
          </div>

          <template v-if="isCompleteStatus(targetView.status)">
            <div class="panel__heading historical-ticket-heading">
              <div>
                <p class="step-label">Native ticket rows</p>
                <h3>Every stored ticket</h3>
              </div>
              <span class="table-note">{{ targetView.tickets.length }} returned · expected {{ targetView.expectedTicketCount }}</span>
            </div>
            <p v-if="!targetView.tickets.length" class="state-panel">No native ticket rows were returned for this complete record.</p>
            <div v-else class="table-wrap">
              <table>
                <caption>All native tickets — server response order</caption>
                <thead>
                  <tr>
                    <th>Position</th>
                    <th>First-zone generated numbers</th>
                    <th v-if="lottery === 'POWER_LOTTO'">Second-zone generated</th>
                    <th>Hits / result</th>
                    <th>Prize result</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="ticket in targetView.tickets" :key="ticket.position">
                    <td><strong>#{{ ticket.position }}</strong></td>
                    <td>{{ formatNumbers(ticket.firstZoneNumbers) }}</td>
                    <td v-if="lottery === 'POWER_LOTTO'">{{ ticket.secondZoneNumber ?? '—' }}</td>
                    <td>
                      {{ ticket.hitSummary }}
                      <small v-if="ticket.actualFirstZoneNumbers.length">Official: {{ formatNumbers(ticket.actualFirstZoneNumbers) }}</small>
                      <small v-if="ticket.actualSecondZoneNumber !== null">Official second zone: {{ ticket.actualSecondZoneNumber }}</small>
                    </td>
                    <td>
                      {{ prizeText(ticket) }}
                      <small>{{ ticket.isWinner ? 'Target winner' : 'No winning result' }}<span v-if="ticket.resultStatus"> · {{ ticket.resultStatus }}</span></small>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </template>
          <p v-else class="state-panel historical-non-ticket-state" data-testid="historical-non-ticket-state">
            This record is {{ targetView.status }}. No ticket rows are fabricated or presented as a generated prediction.
          </p>
        </template>
      </section>
    </template>
  </section>
</template>
