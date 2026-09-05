// @vitest-environment jsdom

import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import HistoryPage from '../src/features/history/HistoryPage.vue'
import StrategyEvidencePage from '../src/features/strategy-evidence/StrategyEvidencePage.vue'

let fetchMock: ReturnType<typeof vi.fn<typeof fetch>>

function apiResponse(payload: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: vi.fn().mockResolvedValue(payload),
  } as unknown as Response
}

interface Deferred<T> {
  promise: Promise<T>
  resolve: (value: T | PromiseLike<T>) => void
}

function deferred<T>(): Deferred<T> {
  let resolve!: Deferred<T>['resolve']
  const promise = new Promise<T>((promiseResolve) => {
    resolve = promiseResolve
  })
  return { promise, resolve }
}

const run = {
  run_id: 'run-1',
  operation_type: 'MANUAL_SYNC',
  status: 'FAILED',
  lottery_type: 'BIG_LOTTO',
  source_filename: 'fixture-provider',
  source_sha256: 'a'.repeat(64),
  parser_version: 'AUTOMATION_AUDIT_V1',
  trigger: 'MANUAL_SYNC',
  provider: 'fixture-provider',
  provider_version: 'fixture-v1',
  requested_start: '2026-07-29',
  requested_end: '2026-07-29',
  resolved_start: null,
  resolved_end: null,
  fetched_count: 1,
  total_count: 1,
  inserted_count: 0,
  skipped_count: 0,
  conflict_count: 0,
  failed_count: 1,
  first_draw_number: null,
  last_draw_number: null,
  started_at: '2026-07-29T01:00:00Z',
  completed_at: '2026-07-29T01:00:00Z',
  error_summary: 'PROVIDER_CONTRACT_INVALID',
}

const successfulRun = {
  ...run,
  run_id: 'run-success',
  status: 'SUCCESS',
  inserted_count: 1,
  failed_count: 0,
  error_summary: null,
}

const failedRunWithoutSummary = {
  ...run,
  run_id: 'run-without-summary',
  error_summary: null,
}

const evidence = {
  items: [
    {
      strategy_id: '<unsafe-strategy>',
      strategy_version: 'v1',
      replicate: 'NOT_APPLICABLE',
      display_name: 'Fixture Strategy',
      lifecycle_status: 'OBSERVATION',
      executable: false,
      supported_lottery_types: ['BIG_LOTTO'],
      minimum_history: 12,
      provenance: ['fixture:ssot'],
      adapter_available: false,
      registration_status: 'CANONICAL_EVIDENCE_MISSING',
      definition_status: 'DEFINITION_AVAILABLE',
      verification_status: 'EVIDENCE_MISSING',
      unavailable_reason_code: 'NO_CANONICAL_STRATEGY_EVALUATION_EVIDENCE',
    },
  ],
  best_strategy: {
    status: 'UNAVAILABLE',
    reason: 'NO_CANONICAL_STRATEGY_EVALUATION_EVIDENCE',
  },
  strategy_combination_hit_rate: {
    status: 'EXCLUDED_ACTIVE_MULTITICKET_SCOPE',
    value: 'NOT_AVAILABLE',
    owner: 'ACTIVE_MULTITICKET_AGENT',
  },
  d3: {
    status: 'RESERVED_UNAVAILABLE',
    value: 'NOT_AVAILABLE',
    definition: {
      metric_id: 'D3',
      metric_version: 'v1',
      schema_id: 'lottolab.evidence.metric_definition',
      schema_version: '1.0.0',
      formula_status: 'RESERVED_UNAVAILABLE',
      direction: 'DESCRIPTIVE_ONLY',
      aggregation: 'NONE',
      sample_unit: 'DRAWS',
      decimal_scale: 4,
      rounding_mode: 'ROUND_HALF_EVEN',
      unit: 'UNITLESS',
      definition_prose: 'fixture prose',
      authority_path: 'contracts/evidence/metric_definitions/d3.json',
    },
  },
}

beforeEach(() => {
  fetchMock = vi.fn<typeof fetch>()
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('History workspace', () => {
  it('keeps draws, ingestion audit, and historical import metadata read-only', async () => {
    fetchMock.mockImplementation((input) => {
      const url = String(input)
      if (url.includes('/api/v1/draws?')) {
        return Promise.resolve(
          apiResponse({
            records: [],
            page: 1,
            page_size: 25,
            total_count: 0,
            total_pages: 0,
            sort: ['draw_date:desc', 'draw_number:string_desc', 'id:desc'],
          }),
        )
      }
      if (url.endsWith('/api/v1/ingestion-runs/run-1')) {
        return Promise.resolve(
          apiResponse({
            run,
            items: [
              {
                source_row_number: 2,
                lottery_type: 'BIG_LOTTO',
                draw_number: '1001',
                source: 'fixture-provider',
                disposition: 'FAILED',
                normalized_record_hash: 'b'.repeat(64),
                message: 'Sanitized provider validation failure.',
              },
            ],
            item_count: 2,
            items_truncated: true,
          }),
        )
      }
      if (url.includes('/api/v1/ingestion-runs?')) {
        return Promise.resolve(
          apiResponse({
            records: [run],
            page: 1,
            page_size: 25,
            total_count: 1,
            total_pages: 1,
            sort: ['started_at:desc', 'id:desc'],
          }),
        )
      }
      return Promise.resolve(
        apiResponse(
          {
            error_code: 'HISTORICAL_RESULTS_NOT_CONFIGURED',
            message: 'Historical Results storage is not configured.',
          },
          503,
        ),
      )
    })
    const wrapper = mount(HistoryPage)
    await flushPromises()

    expect(wrapper.get('#history-title').text()).toBe('History')
    expect(wrapper.text()).toContain('no edit, delete, replay, prediction, ranking')
    const tabs = wrapper
      .get('nav[aria-label="History sections"]')
      .findAll('button')
      .map((button) => button.text())
    expect(tabs).toEqual(['Draw History', 'Ingestion History', 'Historical Import Runs'])

    await wrapper
      .get('nav[aria-label="History sections"]')
      .findAll('button')[1]
      ?.trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('fixture-provider')
    expect(wrapper.text()).toContain('1 fetched · 0 inserted')
    await wrapper.findAll('button').find((button) => button.text() === 'Open')?.trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('Partial result')
    expect(wrapper.get('[data-testid="run-error-summary"]').text()).toContain(
      'PROVIDER_CONTRACT_INVALID',
    )
    expect(wrapper.text()).toContain('Sanitized provider validation failure')

    await wrapper
      .get('nav[aria-label="History sections"]')
      .findAll('button')[2]
      ?.trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('Historical Results storage is not configured')
    expect(wrapper.text()).not.toContain('Run replay')
    expect(wrapper.text()).not.toContain('Delete')
    wrapper.unmount()
  })

  it('renders a neutral fallback when a failed run has no error summary', async () => {
    fetchMock.mockImplementation((input) => {
      const url = String(input)
      if (url.includes('/api/v1/draws?')) {
        return Promise.resolve(
          apiResponse({
            records: [],
            page: 1,
            page_size: 25,
            total_count: 0,
            total_pages: 0,
            sort: ['draw_date:desc', 'draw_number:string_desc', 'id:desc'],
          }),
        )
      }
      if (url.endsWith('/api/v1/ingestion-runs/run-without-summary')) {
        return Promise.resolve(
          apiResponse({
            run: failedRunWithoutSummary,
            items: [],
            item_count: 0,
            items_truncated: false,
          }),
        )
      }
      if (url.includes('/api/v1/ingestion-runs?')) {
        return Promise.resolve(
          apiResponse({
            records: [failedRunWithoutSummary],
            page: 1,
            page_size: 25,
            total_count: 1,
            total_pages: 1,
            sort: ['started_at:desc', 'id:desc'],
          }),
        )
      }
      return Promise.resolve(apiResponse({ items: [], total_count: 0, limit: 50, offset: 0 }))
    })
    const wrapper = mount(HistoryPage)
    await flushPromises()

    await wrapper
      .get('nav[aria-label="History sections"]')
      .findAll('button')[1]
      ?.trigger('click')
    await wrapper.findAll('button').find((button) => button.text() === 'Open')?.trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-testid="run-error-summary"]').text()).toContain(
      'No error summary provided.',
    )
    expect(wrapper.text()).not.toContain('/Users/')
    expect(wrapper.text()).not.toContain('SELECT ')
    wrapper.unmount()
  })

  it('keeps a successful current detail when an older failed response arrives late', async () => {
    const pendingFailedDetail = deferred<Response>()
    fetchMock.mockImplementation((input) => {
      const url = String(input)
      if (url.includes('/api/v1/draws?')) {
        return Promise.resolve(
          apiResponse({
            records: [],
            page: 1,
            page_size: 25,
            total_count: 0,
            total_pages: 0,
            sort: ['draw_date:desc', 'draw_number:string_desc', 'id:desc'],
          }),
        )
      }
      if (url.endsWith('/api/v1/ingestion-runs/run-1')) return pendingFailedDetail.promise
      if (url.endsWith('/api/v1/ingestion-runs/run-success')) {
        return Promise.resolve(
          apiResponse({
            run: successfulRun,
            items: [],
            item_count: 0,
            items_truncated: false,
          }),
        )
      }
      if (url.includes('/api/v1/ingestion-runs?')) {
        return Promise.resolve(
          apiResponse({
            records: [run, successfulRun],
            page: 1,
            page_size: 25,
            total_count: 2,
            total_pages: 1,
            sort: ['started_at:desc', 'id:desc'],
          }),
        )
      }
      return Promise.resolve(apiResponse({ items: [], total_count: 0, limit: 50, offset: 0 }))
    })
    const wrapper = mount(HistoryPage)
    await flushPromises()

    await wrapper
      .get('nav[aria-label="History sections"]')
      .findAll('button')[1]
      ?.trigger('click')
    const openButtons = wrapper.findAll('button').filter((button) => button.text() === 'Open')
    await openButtons[0]?.trigger('click')
    await flushPromises()
    const failedSignal = (fetchMock.mock.calls.find((call) =>
      String(call[0]).endsWith('/api/v1/ingestion-runs/run-1'),
    )?.[1] as RequestInit).signal
    await openButtons[1]?.trigger('click')
    await flushPromises()

    expect(failedSignal?.aborted).toBe(true)
    expect(wrapper.get('#run-detail-title').text()).toContain('run-success')
    expect(wrapper.get('[data-testid="run-error-summary"]').text()).toContain(
      'No error summary provided.',
    )
    expect(wrapper.text()).not.toContain('PROVIDER_CONTRACT_INVALID')

    pendingFailedDetail.resolve(
      apiResponse({
        run,
        items: [],
        item_count: 0,
        items_truncated: false,
      }),
    )
    await flushPromises()

    expect(wrapper.get('#run-detail-title').text()).toContain('run-success')
    expect(wrapper.text()).not.toContain('PROVIDER_CONTRACT_INVALID')
    wrapper.unmount()
  })

  it('aborts all workspace reads when unmounted', async () => {
    fetchMock.mockImplementation(() => new Promise<Response>(() => undefined))
    const wrapper = mount(HistoryPage)
    await flushPromises()
    const signals = fetchMock.mock.calls.map(
      (call) => (call[1] as RequestInit | undefined)?.signal,
    )

    wrapper.unmount()

    expect(signals).toHaveLength(3)
    expect(signals.every((signal) => signal?.aborted)).toBe(true)
  })

  it('invalidates a pending run detail when the filtered run list changes', async () => {
    const pendingDetail = deferred<Response>()
    fetchMock.mockImplementation((input) => {
      const url = String(input)
      if (url.includes('/api/v1/draws?')) {
        return Promise.resolve(
          apiResponse({
            records: [],
            page: 1,
            page_size: 25,
            total_count: 0,
            total_pages: 0,
            sort: ['draw_date:desc', 'draw_number:string_desc', 'id:desc'],
          }),
        )
      }
      if (url.endsWith('/api/v1/ingestion-runs/run-1')) return pendingDetail.promise
      if (url.includes('/api/v1/ingestion-runs?')) {
        return Promise.resolve(
          apiResponse({
            records: url.includes('status=SUCCESS') ? [] : [run],
            page: 1,
            page_size: 25,
            total_count: url.includes('status=SUCCESS') ? 0 : 1,
            total_pages: url.includes('status=SUCCESS') ? 0 : 1,
            sort: ['started_at:desc', 'id:desc'],
          }),
        )
      }
      return Promise.resolve(apiResponse({ items: [], total_count: 0, limit: 50, offset: 0 }))
    })
    const wrapper = mount(HistoryPage)
    await flushPromises()
    await wrapper
      .get('nav[aria-label="History sections"]')
      .findAll('button')[1]
      ?.trigger('click')
    await wrapper.findAll('button').find((button) => button.text() === 'Open')?.trigger('click')
    await flushPromises()
    const detailSignal = (fetchMock.mock.calls.find((call) =>
      String(call[0]).endsWith('/api/v1/ingestion-runs/run-1'),
    )?.[1] as RequestInit).signal

    await wrapper.get('select').setValue('SUCCESS')
    await wrapper.get('form').trigger('submit')
    pendingDetail.resolve(
      apiResponse({
        run,
        items: [],
        item_count: 0,
        items_truncated: false,
      }),
    )
    await flushPromises()

    expect(detailSignal?.aborted).toBe(true)
    expect(wrapper.text()).toContain('No ingestion runs match this query')
    expect(wrapper.text()).not.toContain('Run Detail')
    wrapper.unmount()
  })
})

describe('Strategy Evidence workspace', () => {
  it('renders identity and unavailable evidence states without ranking inference', async () => {
    fetchMock.mockResolvedValue(apiResponse(evidence))
    const wrapper = mount(StrategyEvidencePage)
    await flushPromises()

    expect(wrapper.text()).toContain('NO_CANONICAL_STRATEGY_EVALUATION_EVIDENCE')
    expect(wrapper.text()).toContain('RESERVED_UNAVAILABLE')
    expect(wrapper.text()).toContain('D3_VALUE: NOT_AVAILABLE')
    expect(wrapper.text()).toContain('EXCLUDED_ACTIVE_MULTITICKET_SCOPE')
    expect(wrapper.text()).toContain('replicate: NOT_APPLICABLE')
    expect(wrapper.text()).toContain('<unsafe-strategy>')
    expect(wrapper.find('unsafe-strategy').exists()).toBe(false)

    await wrapper.get('input[type="search"]').setValue('not present')
    expect(wrapper.text()).toContain('No strategy identity matches this filter')
    wrapper.unmount()
  })

  it('sanitizes unavailable errors and aborts retry work on unmount', async () => {
    fetchMock
      .mockResolvedValueOnce(
        apiResponse(
          {
            error_code: 'STRATEGY_EVIDENCE_REGISTRY_UNAVAILABLE',
            message: 'Canonical strategy evidence metadata is unavailable.',
          },
          503,
        ),
      )
      .mockImplementationOnce(() => new Promise<Response>(() => undefined))
    const wrapper = mount(StrategyEvidencePage)
    await flushPromises()

    expect(wrapper.text()).toContain('Canonical strategy evidence metadata is unavailable')
    await wrapper.get('button').trigger('click')
    await flushPromises()
    const retrySignal = (fetchMock.mock.calls[1]?.[1] as RequestInit).signal

    wrapper.unmount()

    expect(retrySignal?.aborted).toBe(true)
  })
})
