// @vitest-environment jsdom
import { flushPromises, shallowMount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { unref } from 'vue'

import * as rankingMatrixApi from '../src/api/rankingMatrix'
import * as structuralMatrixApi from '../src/api/strategyMatrixStructural'
import type { CrossWindowData, LotteryType, RankingRow, TicketCount } from '../src/api/rankingMatrix'
import CrossWindowChart from '../src/features/ranking-matrix/components/CrossWindowChart.vue'
import RankingTable from '../src/features/ranking-matrix/components/RankingTable.vue'
import RankingMatrixPage from '../src/features/ranking-matrix/RankingMatrixPage.vue'

interface Deferred<T> {
  promise: Promise<T>
  resolve: (value: T) => void
  reject: (reason?: unknown) => void
}

interface PendingChartRequest extends Deferred<CrossWindowData> {
  lotteryType: LotteryType
  ticketCount: TicketCount
  strategyId: string
  displayName: string
  signal?: AbortSignal
}

function deferred<T>(): Deferred<T> {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise
    reject = rejectPromise
  })
  return { promise, resolve, reject }
}

const strategyAlpha = {
  strategyId: 'strategy-alpha',
  displayName: 'Strategy Alpha',
  methodFamily: 'test',
  lifecycleStatus: 'ACTIVE',
  officialRank: 1,
  officialAnyPrizeRate: 0.2,
  baselineDelta: 0.01,
  isAvailable: true,
  warningCodes: [],
} as RankingRow

const strategyBeta = {
  ...strategyAlpha,
  strategyId: 'strategy-beta',
  displayName: 'Strategy Beta',
  officialRank: 2,
} as RankingRow

let requests: PendingChartRequest[]
let wrapper: ReturnType<typeof shallowMount> | undefined

function chartData(
  request: Pick<PendingChartRequest, 'lotteryType' | 'ticketCount' | 'strategyId' | 'displayName'>,
): CrossWindowData {
  return {
    lotteryType: request.lotteryType,
    ticketCount: request.ticketCount,
    strategyId: request.strategyId,
    displayName: request.displayName,
    points: [],
  }
}

function chartState(): { data: CrossWindowData | null; loading: boolean } {
  const chart = wrapper!.getComponent(CrossWindowChart)
  return {
    data: chart.props('data') as CrossWindowData | null,
    loading: chart.props('loading') as boolean,
  }
}

function selectStrategy(row: RankingRow): void {
  wrapper!.getComponent(RankingTable).vm.$emit('select-strategy', row)
}

async function mountPage(): Promise<void> {
  wrapper = shallowMount(RankingMatrixPage)
  await flushPromises()
}

beforeEach(() => {
  requests = []
  vi.spyOn(rankingMatrixApi, 'fetchRankingData').mockResolvedValue([strategyAlpha, strategyBeta])
  vi.spyOn(rankingMatrixApi, 'fetchMultiTicketMatrix').mockResolvedValue([])
  vi.spyOn(rankingMatrixApi, 'fetchCrossWindowData').mockImplementation(
    (lotteryType, ticketCount, strategyId, displayName, signal) => {
      const pending = deferred<CrossWindowData>()
      requests.push({ lotteryType, ticketCount, strategyId, displayName, signal, ...pending })
      return pending.promise
    },
  )
  vi.spyOn(structuralMatrixApi, 'queryStrategyMatrixStructural').mockResolvedValue({ cells: [] })
})

afterEach(() => {
  wrapper?.unmount()
  wrapper = undefined
  vi.restoreAllMocks()
})

describe('RankingMatrixPage cross-window chart request identity', () => {
  it('keeps the newest same-strategy success when an older success arrives later', async () => {
    await mountPage()
    expect(requests).toHaveLength(1)

    selectStrategy(strategyAlpha)
    await flushPromises()
    expect(requests).toHaveLength(2)
    expect(requests[0]?.signal?.aborted).toBe(true)
    expect(requests[1]?.signal?.aborted).toBe(false)

    const latest = chartData(requests[1]!)
    requests[1]!.resolve(latest)
    await flushPromises()
    expect(chartState()).toEqual({ data: latest, loading: false })

    const stale = { ...chartData(requests[0]!), displayName: 'Stale Alpha' }
    requests[0]!.resolve(stale)
    await flushPromises()
    expect(chartState()).toEqual({ data: latest, loading: false })
  })

  it('does not let a stale rejection or finally end a newer same-strategy load', async () => {
    await mountPage()
    selectStrategy(strategyAlpha)
    await flushPromises()
    expect(requests).toHaveLength(2)

    requests[0]!.reject(new Error('stale chart request failed'))
    await flushPromises()
    expect(chartState()).toEqual({ data: null, loading: true })

    const latest = chartData(requests[1]!)
    requests[1]!.resolve(latest)
    await flushPromises()
    expect(chartState()).toEqual({ data: latest, loading: false })
  })

  it('keeps the newest chart after an older request fails later', async () => {
    await mountPage()
    selectStrategy(strategyAlpha)
    await flushPromises()

    const latest = chartData(requests[1]!)
    requests[1]!.resolve(latest)
    await flushPromises()
    requests[0]!.reject(new Error('late stale chart failure'))
    await flushPromises()

    expect(chartState()).toEqual({ data: latest, loading: false })
  })

  it.each(['lottery', 'ticket count', 'window', 'strategy'] as const)(
    'invalidates chart results after changing %s',
    async (selection) => {
      await mountPage()
      const old = requests[0]!

      if (selection === 'lottery') {
        await wrapper!.get('[data-testid="lottery-selector"]').setValue('POWER_LOTTO')
      } else if (selection === 'ticket count') {
        await wrapper!.get('[data-testid="ticket-btn-10"]').trigger('click')
      } else if (selection === 'window') {
        await wrapper!.get('[data-testid="window-btn-50"]').trigger('click')
      } else {
        selectStrategy(strategyBeta)
      }
      await flushPromises()

      expect(requests).toHaveLength(2)
      expect(old.signal?.aborted).toBe(true)
      expect(requests[1]?.signal?.aborted).toBe(false)
      expect(chartState()).toEqual({ data: null, loading: true })

      old.resolve(chartData(old))
      await flushPromises()
      expect(chartState()).toEqual({ data: null, loading: true })

      const latest = chartData(requests[1]!)
      requests[1]!.resolve(latest)
      await flushPromises()
      expect(chartState()).toEqual({ data: latest, loading: false })
    },
  )

  it('aborts and ignores a late chart completion after unmount', async () => {
    await mountPage()
    const request = requests[0]!
    const setupState = wrapper!.vm.$.setupState as Record<string, unknown>

    expect(unref(setupState.chartLoading)).toBe(true)
    wrapper!.unmount()
    expect(request.signal?.aborted).toBe(true)

    request.resolve(chartData(request))
    await flushPromises()
    expect(unref(setupState.crossWindowData)).toBeNull()
    expect(unref(setupState.chartLoading)).toBe(true)
  })

  it('finishes loading and displays the current chart when the latest request succeeds', async () => {
    await mountPage()
    const latest = chartData(requests[0]!)

    requests[0]!.resolve(latest)
    await flushPromises()

    expect(chartState()).toEqual({ data: latest, loading: false })
  })
})
