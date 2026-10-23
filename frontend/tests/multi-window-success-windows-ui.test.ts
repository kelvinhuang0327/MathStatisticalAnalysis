// @vitest-environment jsdom

import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  getP638MultiWindowSuccessWindows,
  getT539MultiWindowSuccessWindows,
} from '../src/api/multiWindowSuccessWindows'
import type { components } from '../src/api/generated/openapi'
import MultiWindowSuccessWindowsPanel from '../src/features/multiwindow-success/MultiWindowSuccessWindowsPanel.vue'

type ResponseBody = components['schemas']['MultiWindowSuccessWindowsResponse']
type Row = components['schemas']['MultiWindowRowView']
type ExactRational = components['schemas']['ExactRationalView']

function exact(numerator: string, denominator: string, decimal: string): ExactRational {
  return { numerator, denominator, decimal_18: decimal }
}

function multiWindowRow(
  runId: string,
  lotteryType: string,
  overrides: Partial<Row> = {},
): Row {
  return {
    lottery_type: lotteryType,
    run_id: runId,
    strategy_id: 'strategy-alpha',
    strategy_version: 'v3',
    native_ticket_count: 2,
    window_kind: 'LONG',
    window_role: 'PRIMARY_EVIDENCE',
    status: 'COMPLETE',
    source_target_count: 8,
    requested_target_count: 8,
    actual_target_count: 8,
    first_target_id: 'target-1',
    first_target_date: '2026-01-01',
    last_target_id: 'target-8',
    last_target_date: '2026-02-01',
    observed_winning_target_count: 1,
    observed_winning_target_rate: exact('1', '8', '0.125000000000000000'),
    observed_ticket_count: 16,
    observed_winning_ticket_count: 3,
    observed_ticket_winning_rate: exact('3', '16', '0.187500000000000000'),
    prize_tier_vector: [],
    highest_prize_tier: null,
    null_single_ticket_probability: exact('1', '100', '0.010000000000000000'),
    null_portfolio_probability: exact('2', '25', '0.080000000000000000'),
    expected_null_target_successes: exact('4', '25', '0.160000000000000000'),
    observed_minus_null_rate: exact('9', '100', '0.090000000000000000'),
    lift_vs_null: exact('9', '8', '1.125000000000000000'),
    raw_p_value: exact('1', '4', '0.250000000000000000'),
    by_adjusted_p_value: exact('1', '2', '0.500000000000000000'),
    evidence_status: 'DESCRIPTIVE_ONLY',
    ...overrides,
  }
}

function response(
  runId: string,
  lotteryType: string,
  rows: Row[] = [multiWindowRow(runId, lotteryType)],
): ResponseBody {
  return {
    lottery_type: lotteryType,
    run_id: runId,
    schema_version: 'multi-window-success-windows-v1',
    source_sha256: 'a'.repeat(64),
    source_commit: 'b'.repeat(40),
    strategy_set_fingerprint: 'c'.repeat(64),
    status: 'COMPLETE',
    draw_count: 8,
    event: 'ANY_PRIZE',
    evidence_status: 'DESCRIPTIVE_ONLY',
    research_only: true,
    promotion_allowed: false,
    window_definitions: [],
    null_contract: {
      lottery_type: lotteryType,
      game_spec: 'fixture game spec',
      sampling_policy: 'WITHOUT_REPLACEMENT',
      official_evaluator: 'official evaluator',
      prize_rule_version: 'v1',
      prize_rule_source_sha256: 'd'.repeat(64),
      legal_ticket_count: 100,
      any_prize_ticket_count: 10,
      single_ticket_any_prize_probability: exact('1', '10', '0.100000000000000000'),
      portfolio_formula: 'fixture formula',
      hit_state_weights: [],
    },
    strategy_count: 1,
    family_size: 1,
    rows,
    stability: [],
    source_authority: 'fixture authority',
  }
}

function apiResponse(payload: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: vi.fn().mockResolvedValue(payload),
  } as unknown as Response
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('multi-window success windows API and UI', () => {
  it('uses each generated-contract GET endpoint and retains its exact rational strings', async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(apiResponse(response('run/p638', 'POWER_LOTTO')))
      .mockResolvedValueOnce(apiResponse(response('run/t539', 'DAILY_539')))
    vi.stubGlobal('fetch', fetchMock)

    const p638 = await getP638MultiWindowSuccessWindows('run/p638')
    const t539 = await getT539MultiWindowSuccessWindows('run/t539')

    expect(fetchMock.mock.calls[0]?.[0]).toBe(
      '/api/v1/p638-historical/current-runs/run%2Fp638/success-windows',
    )
    expect(fetchMock.mock.calls[1]?.[0]).toBe('/api/v1/t539-historical/runs/run%2Ft539/success-windows')
    expect(fetchMock.mock.calls.every(([, init]) => init?.method === 'GET')).toBe(true)
    expect(p638.rows[0]?.observed_winning_target_rate).toEqual(
      exact('1', '8', '0.125000000000000000'),
    )
    expect(t539.rows[0]?.observed_ticket_winning_rate).toEqual(
      exact('3', '16', '0.187500000000000000'),
    )
  })

  it('loads only the selected run and removes an older result after switching runs', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockImplementation((input) => {
      const runId = String(input).includes('/run-two/') ? 'run-two' : 'run-one'
      const strategyId = runId === 'run-one' ? 'old-strategy' : 'selected-strategy'
      return Promise.resolve(
        apiResponse(
          response(runId, 'POWER_LOTTO', [
            multiWindowRow(runId, 'POWER_LOTTO', { strategy_id: strategyId }),
          ]),
        ),
      )
    })
    vi.stubGlobal('fetch', fetchMock)

    const wrapper = mount(MultiWindowSuccessWindowsPanel, {
      props: { lottery: 'P638', runId: 'run-one' },
    })
    await flushPromises()
    expect(wrapper.text()).toContain('old-strategy')
    expect(wrapper.text()).toContain('0.125000000000000000 (1/8)')
    expect(wrapper.text()).toContain('0.187500000000000000 (3/16)')
    expect(wrapper.text()).toContain('0.500000000000000000 (1/2)')
    expect(wrapper.text()).toContain('Portfolio: 0.080000000000000000 (2/25)')

    await wrapper.setProps({ runId: 'run-two' })
    await flushPromises()

    expect(fetchMock.mock.calls.map(([url]) => String(url))).toEqual([
      '/api/v1/p638-historical/current-runs/run-one/success-windows',
      '/api/v1/p638-historical/current-runs/run-two/success-windows',
    ])
    expect(wrapper.text()).toContain('selected-strategy')
    expect(wrapper.text()).not.toContain('old-strategy')
    expect(wrapper.text()).toContain('run-two')
    wrapper.unmount()
  })

  it('ignores a late response from the previous run even when fetch does not honor abort', async () => {
    let resolveSlow: ((value: Response) => void) | undefined
    const fetchMock = vi.fn<typeof fetch>().mockImplementation((input) => {
      if (String(input).includes('/slow-run/')) {
        return new Promise<Response>((resolve) => {
          resolveSlow = resolve
        })
      }
      return Promise.resolve(
        apiResponse(
          response('fast-run', 'DAILY_539', [
            multiWindowRow('fast-run', 'DAILY_539', { strategy_id: 'fast-result' }),
          ]),
        ),
      )
    })
    vi.stubGlobal('fetch', fetchMock)

    const wrapper = mount(MultiWindowSuccessWindowsPanel, {
      props: { lottery: 'T539', runId: 'slow-run' },
    })
    expect(wrapper.text()).toContain('Loading multi-window results for slow-run')
    await wrapper.setProps({ runId: 'fast-run' })
    await flushPromises()
    resolveSlow?.(apiResponse(response('slow-run', 'DAILY_539', [
      multiWindowRow('slow-run', 'DAILY_539', { strategy_id: 'stale-result' }),
    ])))
    await flushPromises()

    expect(wrapper.text()).toContain('fast-result')
    expect(wrapper.text()).not.toContain('stale-result')
    wrapper.unmount()
  })

  it.each([
    [404, 'P638_CURRENT_RUN_NOT_FOUND', 'HTTP 404'],
    [422, 'REQUEST_VALIDATION_FAILED', 'HTTP 422'],
    [503, 'P638_HISTORICAL_UNAVAILABLE', 'HTTP 503'],
  ])('shows HTTP %s and retries the selected run', async (status, errorCode, expectedText) => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(
        apiResponse({ error_code: errorCode, message: 'The request has no available result.' }, status),
      )
      .mockResolvedValueOnce(apiResponse(response('retry-run', 'POWER_LOTTO')))
    vi.stubGlobal('fetch', fetchMock)

    const wrapper = mount(MultiWindowSuccessWindowsPanel, {
      props: { lottery: 'P638', runId: 'retry-run' },
    })
    await flushPromises()

    expect(wrapper.text()).toContain(expectedText)
    expect(wrapper.text()).toContain(errorCode)
    expect(wrapper.get('[data-testid="p638-multi-window-retry"]').exists()).toBe(true)
    await wrapper.get('[data-testid="p638-multi-window-retry"]').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('strategy-alpha')
    expect(fetchMock).toHaveBeenCalledTimes(2)
    wrapper.unmount()
  })

  it('renders empty, null, target, ticket, baseline, adjusted p-value, and evidence values without inventing numbers', async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(apiResponse(response('empty-run', 'DAILY_539', [])))
      .mockResolvedValueOnce(
        apiResponse(
          response('null-run', 'DAILY_539', [
            multiWindowRow('null-run', 'DAILY_539', {
              observed_winning_target_rate: null,
              observed_ticket_winning_rate: null,
              by_adjusted_p_value: null,
              evidence_status: 'INSUFFICIENT_EVIDENCE',
            }),
          ]),
        ),
      )
    vi.stubGlobal('fetch', fetchMock)

    const wrapper = mount(MultiWindowSuccessWindowsPanel, {
      props: { lottery: 'T539', runId: 'empty-run' },
    })
    await flushPromises()
    expect(wrapper.text()).toContain('No multi-window success-window rows are available')

    await wrapper.setProps({ runId: 'null-run' })
    await flushPromises()
    expect(wrapper.text()).toContain('Unavailable (null)')
    expect(wrapper.text()).toContain('Single ticket: 0.010000000000000000 (1/100)')
    expect(wrapper.text()).toContain('Portfolio: 0.080000000000000000 (2/25)')
    expect(wrapper.text().match(/Unavailable \(null\)/g)).toHaveLength(3)
    expect(wrapper.text()).toContain('INSUFFICIENT_EVIDENCE')
    expect(wrapper.text()).toContain('native_ticket_count: 2')
    expect(wrapper.text()).toContain('LONG')
    expect(wrapper.text()).toContain('PRIMARY_EVIDENCE')
    expect(wrapper.text()).not.toContain('0/0')
    expect(wrapper.text()).not.toContain('0.500000000000000000')
    wrapper.unmount()
  })
})
