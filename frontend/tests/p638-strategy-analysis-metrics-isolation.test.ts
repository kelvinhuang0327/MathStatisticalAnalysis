// @vitest-environment jsdom

import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import P638StrategyAnalysisPage from '../src/features/p638-strategy-analysis/P638StrategyAnalysisPage.vue'

type MetricRequest = {
  runId: string
  strategyId: string | undefined
  signal: AbortSignal | undefined
  resolve: (value: unknown) => void
  reject: (reason: unknown) => void
}

const api = vi.hoisted(() => ({
  metricRequests: [] as MetricRequest[],
  getP638Metrics: vi.fn(),
  getP638Rankings: vi.fn(),
  listP638Runs: vi.fn(),
  listP638Strategies: vi.fn(),
}))

vi.mock('../src/api/p638Historical', () => ({
  getP638Metrics: api.getP638Metrics,
  getP638Rankings: api.getP638Rankings,
  listP638Runs: api.listP638Runs,
  listP638Strategies: api.listP638Strategies,
  P638HistoricalRequestError: class P638HistoricalRequestError extends Error {
    kind = 'UNAVAILABLE'
  },
}))

vi.mock('../src/features/multiwindow-success/MultiWindowSuccessWindowsPanel.vue', () => ({
  default: {
    name: 'MultiWindowSuccessWindowsPanelStub',
    props: ['lottery', 'runId'],
    template: '<div />',
  },
}))

function metrics(runId: string, targetCount: number): Record<string, unknown> {
  return {
    run_id: runId,
    target_count: targetCount,
    complete_target_count: targetCount,
    excluded_target_count: 0,
    failed_target_count: 0,
    ticket_count: targetCount * 2,
    combined_zone1_4plus_zone2_hit_count: 1,
    zone1_hit_distribution: [{ value: 4, count: targetCount }],
    zone2_hit_distribution: [{ value: 1, count: targetCount }],
    first_draw_number: `${runId}-first`,
    last_draw_number: `${runId}-last`,
  }
}

function strategyPage(runId: string): Record<string, unknown> {
  const ids = runId === 'run-y' ? ['strategy-b'] : ['strategy-a', 'strategy-b']
  return {
    run_id: runId,
    total_count: ids.length,
    limit: 10,
    offset: 0,
    items: ids.map((strategyId) => ({
      strategy_snapshot_id: `${runId}-${strategyId}`,
      strategy_id: strategyId,
      display_label: `${strategyId} label`,
      strategy_version: 'v1',
      lifecycle_status: 'ACTIVE',
      replay_status: 'COMPLETE',
      zone1_contract: '4 of 6',
      zone2_contract: '1 of 2',
      complete_target_count: 20,
      excluded_target_count: 0,
      ticket_count: 40,
      source_paths: [],
      provenance: 'fixture',
    })),
  }
}

function aggregateMetricsText(wrapper: ReturnType<typeof mount>): string {
  const heading = wrapper.findAll('h2').find((item) => item.text() === 'Descriptive coverage')
  return heading?.element.closest('.section-heading')?.nextElementSibling?.textContent ?? ''
}

function selectedMetricsText(wrapper: ReturnType<typeof mount>): string {
  return wrapper.find('.p638-detail-panel .metric-grid--p638').text()
}

async function flushPage(): Promise<void> {
  await flushPromises()
  await flushPromises()
  await flushPromises()
}

async function openPage(): Promise<ReturnType<typeof mount>> {
  const wrapper = mount(P638StrategyAnalysisPage)
  wrappers.push(wrapper)
  await flushPage()
  return wrapper
}

async function selectStrategy(wrapper: ReturnType<typeof mount>, strategyId: string): Promise<void> {
  const row = wrapper.findAll('tbody tr').find((item) => item.text().includes(strategyId))
  if (!row) throw new Error(`Strategy ${strategyId} was not rendered.`)
  await row.get('button').trigger('click')
  await flushPage()
}

function requestFor(strategyId: string | undefined, runId = 'run-x'): MetricRequest {
  const request = api.metricRequests.find((item) => item.runId === runId && item.strategyId === strategyId)
  if (!request) throw new Error(`Missing metrics request for ${runId}/${strategyId ?? 'aggregate'}.`)
  return request
}

const wrappers: Array<ReturnType<typeof mount>> = []

beforeEach(() => {
  api.metricRequests.length = 0
  api.getP638Metrics.mockReset()
  api.getP638Rankings.mockReset()
  api.listP638Runs.mockReset()
  api.listP638Strategies.mockReset()

  api.listP638Runs.mockResolvedValue({
    items: [
      { run_id: 'run-x', status: 'COMPLETE' },
      { run_id: 'run-y', status: 'COMPLETE' },
    ],
    total_count: 2,
    limit: 25,
    offset: 0,
  })
  api.listP638Strategies.mockImplementation((runId: string) => Promise.resolve(strategyPage(runId)))
  api.getP638Rankings.mockResolvedValue({ run_id: 'latest', items: [] })
  api.getP638Metrics.mockImplementation(
    (runId: string, strategyId: string | undefined, signal: AbortSignal | undefined) =>
      new Promise((resolve, reject) => {
        api.metricRequests.push({ runId, strategyId, signal, resolve, reject })
      }),
  )
})

afterEach(() => {
  wrappers.splice(0).forEach((wrapper) => wrapper.unmount())
  vi.clearAllMocks()
})

describe('P638 Strategy Analysis metrics request isolation', () => {
  it('keeps aggregate and selected requests active together and renders each result in its own section', async () => {
    const wrapper = await openPage()
    const aggregate = requestFor(undefined)

    await selectStrategy(wrapper, 'strategy-a')
    const selected = requestFor('strategy-a')

    expect(aggregate.signal?.aborted).toBe(false)
    expect(selected.signal).not.toBe(aggregate.signal)

    aggregate.resolve(metrics('run-x', 100))
    selected.resolve(metrics('run-x', 10))
    await flushPage()

    expect(aggregateMetricsText(wrapper)).toContain('100')
    expect(selectedMetricsText(wrapper)).toContain('10')
  })

  it('keeps the newest selected strategy when an aborted older request resolves last', async () => {
    const wrapper = await openPage()
    requestFor(undefined).resolve(metrics('run-x', 100))
    await flushPage()

    await selectStrategy(wrapper, 'strategy-a')
    const strategyA = requestFor('strategy-a')
    await selectStrategy(wrapper, 'strategy-b')
    const strategyB = [...api.metricRequests].reverse().find((item) => item.strategyId === 'strategy-b')
    if (!strategyB) throw new Error('Missing strategy B metrics request.')

    expect(strategyA.signal?.aborted).toBe(true)
    strategyB.resolve(metrics('run-x', 22))
    await flushPage()
    strategyA.resolve(metrics('run-x', 11))
    await flushPage()

    expect(selectedMetricsText(wrapper)).toContain('22')
    expect(selectedMetricsText(wrapper)).not.toContain('11')
  })

  it('does not let selected loading hide an already loaded aggregate result', async () => {
    const wrapper = await openPage()
    requestFor(undefined).resolve(metrics('run-x', 100))
    await flushPage()

    await selectStrategy(wrapper, 'strategy-a')

    expect(aggregateMetricsText(wrapper)).toContain('100')
    expect(wrapper.text()).toContain('Loading identity metrics…')
  })

  it('keeps aggregate errors visible during selected loading and retries only aggregate metrics', async () => {
    const wrapper = await openPage()
    const firstAggregate = requestFor(undefined)
    firstAggregate.reject(new Error('aggregate unavailable'))
    await flushPage()
    expect(wrapper.text()).toContain('aggregate unavailable')

    await selectStrategy(wrapper, 'strategy-a')
    const selected = requestFor('strategy-a')
    expect(wrapper.text()).toContain('aggregate unavailable')

    const strategyCallsBeforeRetry = api.listP638Strategies.mock.calls.length
    const aggregateRetry = wrapper
      .findAll('button')
      .find((button) => button.text() === 'Retry' && !button.element.closest('.p638-detail-panel'))
    if (!aggregateRetry) throw new Error('Missing aggregate metrics retry button.')
    await aggregateRetry.trigger('click')
    await flushPage()

    const aggregateRetryRequest = [...api.metricRequests].reverse().find((item) => item.strategyId === undefined)
    if (!aggregateRetryRequest) throw new Error('Aggregate retry did not start an aggregate request.')
    expect(firstAggregate.signal?.aborted).toBe(true)
    expect(selected.signal?.aborted).toBe(false)
    expect(api.listP638Strategies.mock.calls.length).toBe(strategyCallsBeforeRetry)
    expect(wrapper.text()).toContain('Loading identity metrics…')
  })

  it('shows a selected retry and does not let a late old failure erase the newer strategy', async () => {
    const wrapper = await openPage()
    requestFor(undefined).resolve(metrics('run-x', 100))
    await flushPage()

    await selectStrategy(wrapper, 'strategy-a')
    const strategyA = requestFor('strategy-a')
    await selectStrategy(wrapper, 'strategy-b')
    const strategyB = [...api.metricRequests].reverse().find((item) => item.strategyId === 'strategy-b')
    if (!strategyB) throw new Error('Missing strategy B metrics request.')
    strategyB.resolve(metrics('run-x', 22))
    await flushPage()
    strategyA.reject(new Error('late strategy A failure'))
    await flushPage()

    expect(selectedMetricsText(wrapper)).toContain('22')
    expect(wrapper.text()).not.toContain('late strategy A failure')

    await selectStrategy(wrapper, 'strategy-a')
    const latestA = [...api.metricRequests].reverse().find((item) => item.strategyId === 'strategy-a')
    if (!latestA) throw new Error('Missing retryable strategy A request.')
    latestA.reject(new Error('strategy A unavailable'))
    await flushPage()

    const selectedRetry = wrapper
      .find('.p638-detail-panel')
      .findAll('button')
      .find((button) => button.text() === 'Retry')
    expect(selectedRetry).toBeDefined()
    await selectedRetry?.trigger('click')
    await flushPage()

    const retriedA = [...api.metricRequests].reverse().find((item) => item.strategyId === 'strategy-a')
    expect(retriedA).toBeDefined()
    expect(retriedA?.runId).toBe('run-x')
  })

  it('invalidates both old run requests and keeps late Run X results out of Run Y', async () => {
    const wrapper = await openPage()
    const aggregateX = requestFor(undefined, 'run-x')
    await selectStrategy(wrapper, 'strategy-a')
    const selectedX = requestFor('strategy-a', 'run-x')

    await wrapper.get('select').setValue('run-y')
    await flushPage()
    expect(aggregateX.signal?.aborted).toBe(true)
    expect(selectedX.signal?.aborted).toBe(true)

    const aggregateY = requestFor(undefined, 'run-y')
    await selectStrategy(wrapper, 'strategy-b')
    const selectedY = requestFor('strategy-b', 'run-y')
    aggregateY.resolve(metrics('run-y', 200))
    selectedY.resolve(metrics('run-y', 201))
    await flushPage()

    aggregateX.resolve(metrics('run-x', 100))
    selectedX.resolve(metrics('run-x', 101))
    await flushPage()

    expect(aggregateMetricsText(wrapper)).toContain('200')
    expect(aggregateMetricsText(wrapper)).not.toContain('100')
    expect(selectedMetricsText(wrapper)).toContain('201')
    expect(selectedMetricsText(wrapper)).not.toContain('101')
  })

  it('aborts both active metrics requests when the page unmounts', async () => {
    const wrapper = await openPage()
    const aggregate = requestFor(undefined)
    await selectStrategy(wrapper, 'strategy-a')
    const selected = requestFor('strategy-a')

    wrapper.unmount()

    expect(aggregate.signal?.aborted).toBe(true)
    expect(selected.signal?.aborted).toBe(true)
    aggregate.resolve(metrics('run-x', 9876))
    selected.resolve(metrics('run-x', 4321))
    await flushPage()
    expect(wrapper.element.textContent).not.toContain('9876')
    expect(wrapper.element.textContent).not.toContain('4321')
  })
})
