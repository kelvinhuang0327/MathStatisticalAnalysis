// @vitest-environment jsdom

import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  getP638StrategyTarget,
  listP638Draws,
} from '../src/api/p638Historical'
import {
  getT539StrategyTarget,
  listT539Draws,
} from '../src/api/t539Historical'
import HistoricalBaseDataPage from '../src/features/historical-base-data/HistoricalBaseDataPage.vue'

function apiResponse(payload: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: vi.fn().mockResolvedValue(payload),
  } as unknown as Response
}

const t539Run = {
  run_id: 'run-t539-base',
  schema_version: 't539-base-v1',
  lottery_type: 'DAILY_539',
  source_endpoint: 'fixture:t539',
  source_sha256: 'a'.repeat(64),
  as_of_date: '2026-08-01',
  adapter_source_commit: 'b'.repeat(40),
  strategy_set_fingerprint: 'c'.repeat(64),
  status: 'COMPLETE',
  strategy_count: 1,
  draw_count: 2,
  eligible_target_count: 1,
  ticket_count: 2,
  failure_count: 0,
  first_draw_id: 'draw-t539-complete',
  first_draw_date: '2026-07-01',
  last_draw_id: 'draw-t539-pre',
  last_draw_date: '2026-07-02',
}

const t539Draws = [
  {
    draw_id: 'draw-t539-complete',
    draw_date: '2026-07-01',
    winning_numbers: [3, 11, 17, 28, 35],
  },
  {
    draw_id: 'draw-t539-pre',
    draw_date: '2026-07-02',
    winning_numbers: [4, 12, 18, 29, 36],
  },
]

const t539Strategy = {
  run_id: t539Run.run_id,
  strategy_id: 't539_native_strategy',
  strategy_version: 'v1',
  native_ticket_count: 2,
  min_history: 30,
  first_eligible_target_draw_id: 'draw-t539-complete',
  expected_target_draw_count: 1,
  processed_target_draw_count: 1,
  successful_target_draw_count: 1,
  failed_target_draw_count: 0,
  status: 'COMPLETE',
  ticket_count: 2,
  winning_ticket_count: 1,
  hit_distribution: [{ value: 3, count: 1 }],
  first_target_draw_date: '2026-07-01',
  last_target_draw_date: '2026-07-01',
}

const t539CompleteTarget = {
  target_id: 'target-t539-complete',
  run_id: t539Run.run_id,
  strategy_id: t539Strategy.strategy_id,
  strategy_version: t539Strategy.strategy_version,
  target_draw_id: 'draw-t539-complete',
  target_draw_date: '2026-07-01',
  cutoff_draw_id: 'draw-t539-pre',
  cutoff_draw_date: '2026-06-30',
  status: 'COMPLETE_CAUSAL_REPLAY',
  native_ticket_count: 2,
  history_length: 30,
  reason_type: null,
  reason: null,
  target_success: true,
  tickets: [
    {
      ticket_position: 1,
      predicted_numbers: [3, 11, 17, 28, 35],
      actual_numbers: [3, 11, 17, 28, 35],
      hit_numbers: [3, 11, 17, 28, 35],
      hits: 5,
      is_winner: true,
      prize_tier: 'TOP',
      prize_tier_order: 1,
      prize_amount: 1000000,
    },
    {
      ticket_position: 2,
      predicted_numbers: [1, 8, 14, 22, 31],
      actual_numbers: [3, 11, 17, 28, 35],
      hit_numbers: [],
      hits: 0,
      is_winner: false,
      prize_tier: null,
      prize_tier_order: null,
      prize_amount: null,
    },
  ],
}

const t539PreTarget = {
  ...t539CompleteTarget,
  target_id: 'target-t539-pre',
  target_draw_id: 'draw-t539-pre',
  target_draw_date: '2026-07-02',
  status: 'PRE_ELIGIBILITY',
  native_ticket_count: 2,
  history_length: 12,
  reason_type: 'INSUFFICIENT_HISTORY',
  reason: 'Historical target precedes the minimum history boundary.',
  target_success: null,
  tickets: [],
}

const p638Run = {
  run_id: 'run-p638-base',
  import_identity_sha256: 'd'.repeat(64),
  manifest_sha256: 'e'.repeat(64),
  contract_version: 'p638-base-v1',
  source_run_id: 'source-p638',
  source_replay_sha256: 'f'.repeat(64),
  source_draw_db_sha256: '1'.repeat(64),
  source_commit_oid: '2'.repeat(40),
  source_content_sha256: '3'.repeat(64),
  second_zone_ssot_version: 'p638-powerlotto-second-zone-v1',
  status: 'COMPLETE',
  started_at: '2026-08-01T00:00:00Z',
  completed_at: '2026-08-01T00:01:00Z',
  strategy_count: 1,
  draw_count: 2,
  complete_target_count: 1,
  excluded_target_count: 1,
  failed_target_count: 0,
  ticket_count: 2,
  first_draw_number: 'p638-complete',
  first_draw_date: '2026-07-03',
  last_draw_number: 'p638-closure',
  last_draw_date: '2026-07-04',
  is_idempotent_replay: true,
}

const p638Draws = [
  {
    draw_number: 'p638-complete',
    draw_date: '2026-07-03',
    winning_zone1_numbers: [1, 9, 18, 27, 36, 45],
    winning_zone2_number: 7,
  },
  {
    draw_number: 'p638-closure',
    draw_date: '2026-07-04',
    winning_zone1_numbers: [2, 10, 19, 28, 37, 46],
    winning_zone2_number: 8,
  },
]

const p638Strategy = {
  strategy_snapshot_id: 'snapshot-p638',
  run_id: p638Run.run_id,
  strategy_id: 'p638_native_strategy',
  display_label: 'P638 native strategy',
  strategy_version: 'v2',
  executable: false,
  adapter_path: null,
  native_ticket_count: 2,
  min_history: 30,
  zone1_contract: '6 numbers',
  zone2_contract: '1 number',
  lifecycle_status: 'HISTORICAL',
  replay_status: 'COMPLETE',
  source_run_id: 'source-p638',
  source_replay_sha256: 'f'.repeat(64),
  source_paths: ['fixture:p638'],
  provenance: 'fixture:p638',
  exclusion_reason: null,
  complete_target_count: 1,
  excluded_target_count: 1,
  failed_target_count: 0,
  ticket_count: 2,
  zone1_hit_distribution: [{ value: 6, count: 1 }],
  zone2_hit_distribution: [{ value: 1, count: 1 }],
  first_draw_number: 'p638-complete',
  first_draw_date: '2026-07-03',
  last_draw_number: 'p638-closure',
  last_draw_date: '2026-07-04',
}

const p638CompleteTarget = {
  target_id: 'target-p638-complete',
  run_id: p638Run.run_id,
  strategy_snapshot_id: p638Strategy.strategy_snapshot_id,
  strategy_id: p638Strategy.strategy_id,
  strategy_version: p638Strategy.strategy_version,
  target_draw_number: 'p638-complete',
  target_draw_date: '2026-07-03',
  history_boundary_draw_number: 'p638-history',
  history_boundary_date: '2026-07-02',
  history_length: 30,
  expected_ticket_count: 2,
  status: 'COMPLETE_CAUSAL_REPLAY',
  exclusion_reason: null,
  failure_reason: null,
  actual_zone1_numbers: [1, 9, 18, 27, 36, 45],
  actual_zone2_number: 7,
  source_target_locator: 'fixture:p638:complete',
  source_run_id: 'source-p638',
  source_replay_sha256: 'f'.repeat(64),
  provenance: 'fixture:p638',
  reason_type: null,
  reason: null,
  target_success: true,
  tickets: [
    {
      ticket_id: 'ticket-p638-1',
      ticket_position: 1,
      predicted_zone1_numbers: [1, 9, 18, 27, 36, 45],
      predicted_zone2_number: 7,
      actual_zone1_numbers: [1, 9, 18, 27, 36, 45],
      actual_zone2_number: 7,
      zone1_hit_count: 6,
      zone2_hit: true,
      status: 'WINNER',
      source_run_id: 'source-p638',
      source_replay_sha256: 'f'.repeat(64),
      source_record_locator: 'fixture:p638:ticket:1',
      second_zone_ssot_version: 'p638-powerlotto-second-zone-v1',
      provenance: 'fixture:p638',
      is_winner: true,
      prize_tier: 'TOP',
      prize_tier_order: 1,
      prize_amount: 2000000,
    },
    {
      ticket_id: 'ticket-p638-2',
      ticket_position: 2,
      predicted_zone1_numbers: [2, 10, 19, 28, 37, 46],
      predicted_zone2_number: 8,
      actual_zone1_numbers: [1, 9, 18, 27, 36, 45],
      actual_zone2_number: 7,
      zone1_hit_count: 0,
      zone2_hit: false,
      status: 'MISS',
      source_run_id: 'source-p638',
      source_replay_sha256: 'f'.repeat(64),
      source_record_locator: 'fixture:p638:ticket:2',
      second_zone_ssot_version: 'p638-powerlotto-second-zone-v1',
      provenance: 'fixture:p638',
      is_winner: false,
      prize_tier: null,
      prize_tier_order: null,
      prize_amount: null,
    },
  ],
}

const p638TypedClosureTarget = {
  ...p638CompleteTarget,
  target_id: 'target-p638-closure',
  target_draw_number: 'p638-closure',
  target_draw_date: '2026-07-04',
  status: 'SOURCE_NATIVE_TYPED_CLOSURE',
  exclusion_reason: 'Accepted source-native typed closure.',
  reason_type: 'SOURCE_NATIVE_TYPED_CLOSURE',
  reason: 'The accepted source record is a typed closure with no generated ticket.',
  target_success: null,
  tickets: [],
}

let fetchMock: ReturnType<typeof vi.fn<typeof fetch>>

function t539PageResponse(): void {
  fetchMock.mockImplementation((input) => {
    const url = String(input)
    if (url.includes('/api/v1/t539-historical/runs?')) {
      return Promise.resolve(apiResponse({ items: [t539Run], total_count: 1, limit: 25, offset: 0 }))
    }
    if (url.includes('/api/v1/t539-historical/runs/run-t539-base/draws?')) {
      return Promise.resolve(apiResponse({ run_id: t539Run.run_id, items: t539Draws, total_count: 2, limit: 25, offset: 0 }))
    }
    if (url.includes('/api/v1/t539-historical/runs/run-t539-base/strategies?')) {
      return Promise.resolve(apiResponse({ run_id: t539Run.run_id, items: [t539Strategy], total_count: 1, limit: 25, offset: 0 }))
    }
    if (url.includes('/targets/draw-t539-pre')) return Promise.resolve(apiResponse(t539PreTarget))
    if (url.includes('/targets/draw-t539-complete')) return Promise.resolve(apiResponse(t539CompleteTarget))
    if (url.includes('/api/v1/p638-historical/runs?')) {
      return Promise.resolve(apiResponse({ items: [p638Run], total_count: 1, limit: 25, offset: 0 }))
    }
    if (url.includes('/api/v1/p638-historical/runs/run-p638-base/draws?')) {
      return Promise.resolve(apiResponse({ run_id: p638Run.run_id, items: p638Draws, total_count: 2, limit: 25, offset: 0 }))
    }
    if (url.includes('/api/v1/p638-historical/runs/run-p638-base/strategies?')) {
      return Promise.resolve(apiResponse({ run_id: p638Run.run_id, items: [p638Strategy], total_count: 1, limit: 25, offset: 0 }))
    }
    if (url.includes('/targets/p638-closure')) return Promise.resolve(apiResponse(p638TypedClosureTarget))
    if (url.includes('/targets/p638-complete')) return Promise.resolve(apiResponse(p638CompleteTarget))
    return Promise.resolve(apiResponse({ error_code: 'FIXTURE_NOT_FOUND', message: 'Fixture route not found.' }, 404))
  })
}

async function settle(): Promise<void> {
  await flushPromises()
  await flushPromises()
}

beforeEach(() => {
  fetchMock = vi.fn<typeof fetch>()
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('historical base-data API additions', () => {
  it('uses bounded draw pagination and the exact T539 strategy-target route', async () => {
    fetchMock.mockResolvedValueOnce(
      apiResponse({ run_id: 'run-t539-base', items: t539Draws, total_count: 2, limit: 25, offset: 0 }),
    )
    await listT539Draws('run t539/base', { limit: 25, offset: 0 })
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/t539-historical/runs/run%20t539%2Fbase/draws?limit=25&offset=0',
      expect.objectContaining({}),
    )

    fetchMock.mockResolvedValueOnce(apiResponse(t539CompleteTarget))
    await getT539StrategyTarget('run t539/base', 'strategy/a', 'v 1', 'draw/1')
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/t539-historical/runs/run%20t539%2Fbase/strategies/strategy%2Fa/v%201/targets/draw%2F1',
      expect.objectContaining({}),
    )
  })

  it('uses bounded draw pagination and the exact P638 strategy-target route', async () => {
    fetchMock.mockResolvedValueOnce(
      apiResponse({ run_id: 'run-p638-base', items: p638Draws, total_count: 2, limit: 25, offset: 0 }),
    )
    await listP638Draws('run p638/base', { limit: 25, offset: 0 })
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/p638-historical/runs/run%20p638%2Fbase/draws?limit=25&offset=0',
      expect.objectContaining({}),
    )

    fetchMock.mockResolvedValueOnce(apiResponse(p638CompleteTarget))
    await getP638StrategyTarget('run p638/base', 'strategy/a', 'v 2', 'draw/1')
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/p638-historical/runs/run%20p638%2Fbase/strategies/strategy%2Fa/v%202/targets/draw%2F1',
      expect.objectContaining({}),
    )
  })
})

describe('HistoricalBaseDataPage', () => {
  it('browses T539 official draws, strategy identity, pre-eligibility, and every native ticket', async () => {
    t539PageResponse()
    const wrapper = mount(HistoricalBaseDataPage)
    await settle()

    expect(wrapper.text()).toContain('draw-t539-complete')
    expect(wrapper.text()).toContain('3, 11, 17, 28, 35')
    expect(wrapper.text()).toContain('2')

    await wrapper.get('[data-testid="historical-select-draw-draw-t539-complete"]').trigger('click')
    await wrapper.get('[data-testid="historical-select-strategy-t539_native_strategy-v1"]').trigger('click')
    await settle()

    expect(wrapper.get('[data-testid="historical-target-status"]').text()).toContain('COMPLETE_CAUSAL_REPLAY')
    expect(wrapper.findAll('caption').some((caption) => caption.text().includes('All native tickets'))).toBe(true)
    const t539TicketTable = wrapper.findAll('table').find((table) => table.text().includes('All native tickets'))
    expect(t539TicketTable?.findAll('tbody tr')).toHaveLength(2)
    expect(wrapper.text()).toContain('#1')
    expect(wrapper.text()).toContain('#2')
    expect(wrapper.text()).toContain('TOP · 1,000,000')

    await wrapper.get('[data-testid="historical-select-draw-draw-t539-pre"]').trigger('click')
    await settle()
    expect(wrapper.get('[data-testid="historical-target-status"]').text()).toContain('PRE_ELIGIBILITY')
    expect(wrapper.get('[data-testid="historical-non-ticket-state"]').text()).toContain('No ticket rows are fabricated')
    expect(wrapper.findAll('caption').some((caption) => caption.text().includes('All native tickets'))).toBe(false)
    wrapper.unmount()
  })

  it('switches to P638, shows both zones, and treats a typed closure as a valid no-ticket state', async () => {
    t539PageResponse()
    const wrapper = mount(HistoricalBaseDataPage)
    await settle()

    await wrapper.get('input[value="POWER_LOTTO"]').trigger('change')
    await settle()
    expect(wrapper.text()).toContain('p638-complete')
    expect(wrapper.text()).toContain('Second zone: 7')

    await wrapper.get('[data-testid="historical-select-draw-p638-complete"]').trigger('click')
    await wrapper.get('[data-testid="historical-select-strategy-p638_native_strategy-v2"]').trigger('click')
    await settle()
    expect(wrapper.get('[data-testid="historical-target-status"]').text()).toContain('COMPLETE_CAUSAL_REPLAY')
    expect(wrapper.text()).toContain('Second-zone generated')
    expect(wrapper.text()).toContain('2,000,000')
    const p638TicketTable = wrapper.findAll('table').find((table) => table.text().includes('All native tickets'))
    expect(p638TicketTable?.findAll('tbody tr')).toHaveLength(2)

    await wrapper.get('[data-testid="historical-select-draw-p638-closure"]').trigger('click')
    await settle()
    expect(wrapper.get('[data-testid="historical-target-status"]').text()).toContain('SOURCE_NATIVE_TYPED_CLOSURE')
    expect(wrapper.text()).toContain('accepted source-native historical closure')
    expect(wrapper.get('[data-testid="historical-non-ticket-state"]').exists()).toBe(true)
    wrapper.unmount()
  })

  it('shows bounded pagination controls and requests the next run range', async () => {
    const secondRun = { ...t539Run, run_id: 'run-t539-page-2' }
    fetchMock.mockImplementation((input) => {
      const url = String(input)
      if (url.includes('offset=25')) {
        return Promise.resolve(apiResponse({ items: [secondRun], total_count: 26, limit: 25, offset: 25 }))
      }
      if (url.includes('/api/v1/t539-historical/runs?')) {
        return Promise.resolve(apiResponse({ items: [t539Run], total_count: 26, limit: 25, offset: 0 }))
      }
      if (url.includes('/draws?')) {
        return Promise.resolve(apiResponse({ run_id: t539Run.run_id, items: t539Draws, total_count: 2, limit: 25, offset: 0 }))
      }
      if (url.includes('/strategies?')) {
        return Promise.resolve(apiResponse({ run_id: t539Run.run_id, items: [t539Strategy], total_count: 1, limit: 25, offset: 0 }))
      }
      return Promise.resolve(apiResponse({ error_code: 'FIXTURE_NOT_FOUND', message: 'Fixture route not found.' }, 404))
    })
    const wrapper = mount(HistoricalBaseDataPage)
    await settle()

    expect(wrapper.get('[data-testid="historical-runs-pagination"]').text()).toContain('Showing 1–25 of 26')
    const nextButton = wrapper.get('[data-testid="historical-runs-pagination"] button:last-child')
    expect((nextButton.element as HTMLButtonElement).disabled).toBe(false)
    await nextButton.trigger('click')
    await settle()
    expect(fetchMock.mock.calls.some(([input]) => String(input).includes('offset=25'))).toBe(true)
    expect(wrapper.text()).toContain('run-t539-page-2')
    wrapper.unmount()
  })

  it('keeps a stale target response from rendering after the lottery changes', async () => {
    let resolveTarget: ((response: Response) => void) | undefined
    fetchMock.mockImplementation((input) => {
      const url = String(input)
      if (url.includes('/api/v1/t539-historical/runs?')) {
        return Promise.resolve(apiResponse({ items: [t539Run], total_count: 1, limit: 25, offset: 0 }))
      }
      if (url.includes('/api/v1/t539-historical/runs/run-t539-base/draws?')) {
        return Promise.resolve(apiResponse({ run_id: t539Run.run_id, items: [t539Draws[0]], total_count: 1, limit: 25, offset: 0 }))
      }
      if (url.includes('/api/v1/t539-historical/runs/run-t539-base/strategies?')) {
        return Promise.resolve(apiResponse({ run_id: t539Run.run_id, items: [t539Strategy], total_count: 1, limit: 25, offset: 0 }))
      }
      if (url.includes('/targets/draw-t539-complete')) {
        return new Promise<Response>((resolve) => {
          resolveTarget = resolve
        })
      }
      if (url.includes('/api/v1/p638-historical/runs?')) {
        return Promise.resolve(apiResponse({ items: [p638Run], total_count: 1, limit: 25, offset: 0 }))
      }
      if (url.includes('/api/v1/p638-historical/runs/run-p638-base/draws?')) {
        return Promise.resolve(apiResponse({ run_id: p638Run.run_id, items: [p638Draws[0]], total_count: 1, limit: 25, offset: 0 }))
      }
      if (url.includes('/api/v1/p638-historical/runs/run-p638-base/strategies?')) {
        return Promise.resolve(apiResponse({ run_id: p638Run.run_id, items: [p638Strategy], total_count: 1, limit: 25, offset: 0 }))
      }
      return Promise.resolve(apiResponse({ error_code: 'FIXTURE_NOT_FOUND', message: 'Fixture route not found.' }, 404))
    })
    const wrapper = mount(HistoricalBaseDataPage)
    await settle()
    await wrapper.get('[data-testid="historical-select-draw-draw-t539-complete"]').trigger('click')
    await wrapper.get('[data-testid="historical-select-strategy-t539_native_strategy-v1"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="historical-target-loading"]').exists()).toBe(true)

    await wrapper.get('input[value="POWER_LOTTO"]').trigger('change')
    await settle()
    resolveTarget?.(apiResponse(t539CompleteTarget))
    await settle()
    expect(wrapper.text()).not.toContain('target-t539-complete')
    expect(wrapper.text()).toContain('p638-complete')
    wrapper.unmount()
  })
})
