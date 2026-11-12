// @vitest-environment jsdom

import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, expect, it, vi } from 'vitest'
import ReplayHistoryPage from '../src/features/replay-history/ReplayHistoryPage.vue'

afterEach(() => vi.unstubAllGlobals())

it('shows unavailable versions and no run without rejecting valid empty API results', async () => {
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    const path = new URL(String(input), 'http://localhost').pathname
    const payload = path.endsWith('/replay-strategy-inventory')
      ? { strategy_count: 0, strategies: [] }
      : path.endsWith('/strategies')
      ? { items: [{
        strategy_id: 'historical-only', strategy_version: null, display_name: 'Historical only',
        lottery_type: 'BIG_LOTTO', lifecycle_status: 'OFFLINE', data_status: 'ARTIFACT_ONLY',
        source_kind: 'artifact', executable: false, available_target_count: 0,
        training_status: 'HISTORICAL_ARTIFACT',
      }], total_count: 1, next_cursor: null }
      : path.endsWith('/coverage')
        ? { expected_strategy_count: 0, expected_target_count: 0, expected_cell_count: 0,
          completed_cell_count: 0, failed_cell_count: 0, closed_cell_count: 0,
          complete_coverage_percent: 0, missing_strategy_ids: [], run_id: null }
        : path.endsWith('/predictions')
          ? { run_id: null, total_count: 0, items: [], next_cursor: null }
          : { items: [], total_count: 0, limit: 50, offset: 0 }
    return { ok: true, status: 200, json: async () => payload } as Response
  }))
  const wrapper = mount(ReplayHistoryPage)
  await flushPromises()
  await wrapper.findAll('nav[aria-label="Replay history sections"] button')[2]?.trigger('click')
  await flushPromises()
  expect(wrapper.text()).toContain('版本未提供')
  expect(wrapper.text()).toContain('尚無回放')
  await wrapper.get('form').trigger('submit')
  await flushPromises()
  expect(wrapper.text()).toContain('尚無可查詢的正式Replay資料')
  expect(wrapper.text()).not.toContain('invalid response')
  wrapper.unmount()
})

it('uses the display name belonging to the recorded strategy version', async () => {
  const baseStrategy = {
    strategy_id: 'shared-id', lottery_type: 'BIG_LOTTO', lifecycle_status: 'ONLINE',
    data_status: 'REBUILDABLE', source_kind: 'native', executable: true,
    available_target_count: 1, training_status: 'NOT_TRAINABLE',
  }
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    const path = new URL(String(input), 'http://localhost').pathname
    const payload = path.endsWith('/replay-strategy-inventory')
      ? { strategy_count: 0, strategies: [] }
      : path.endsWith('/strategies')
      ? { items: [
        { ...baseStrategy, strategy_version: 'legacy', display_name: 'Legacy display' },
        { ...baseStrategy, strategy_version: 'v1', display_name: 'Current display' },
      ], total_count: 2, next_cursor: null }
      : path.endsWith('/coverage')
        ? { expected_strategy_count: 1, expected_target_count: 1, expected_cell_count: 1,
          completed_cell_count: 1, failed_cell_count: 0, closed_cell_count: 0,
          complete_coverage_percent: 100, missing_strategy_ids: [], run_id: 'test-run' }
        : path.endsWith('/predictions')
          ? { run_id: 'test-run', total_count: 1, next_cursor: null, items: [{
            lottery_type: 'BIG_LOTTO', strategy_id: 'shared-id', strategy_version: 'v1',
            target_draw_number: '115000001', target_draw_date: '2026-01-01',
            prediction_status: 'COMPLETE', predicted_tickets: [], actual_main_numbers: [1, 2, 3, 4, 5, 6],
            actual_special_numbers: [7], portfolio_any_prize: null, best_main_hits: null,
            source_kind: 'native', data_status: 'REBUILDABLE', training: {
              training_status: 'NOT_TRAINABLE', model_version: null, training_cutoff: null,
              training_artifact_id: null,
            },
          }] }
          : { items: [], total_count: 0, limit: 50, offset: 0 }
    return { ok: true, status: 200, json: async () => payload } as Response
  }))
  const wrapper = mount(ReplayHistoryPage)
  await flushPromises()
  await wrapper.findAll('nav[aria-label="Replay history sections"] button')[2]?.trigger('click')
  await flushPromises()
  await wrapper.get('form').trigger('submit')
  await flushPromises()
  const row = wrapper.get('[data-testid="backfill-row-115000001-shared-id"]')
  expect(row.text()).toContain('Current display')
  expect(row.text()).not.toContain('Legacy display')
  wrapper.unmount()
})

it('distinguishes uncomputed, evaluated, and zero-valued replay results', async () => {
  const strategy = {
    strategy_id: 'nullable', strategy_version: 'v1', display_name: 'Nullable strategy',
    lottery_type: 'BIG_LOTTO', lifecycle_status: 'ONLINE', data_status: 'REBUILDABLE',
    source_kind: 'native', executable: true, available_target_count: 3,
    training_status: 'NOT_TRAINABLE',
  }
  const training = {
    training_status: 'NOT_TRAINABLE', model_version: null, training_cutoff: null,
    training_artifact_id: null,
  }
  const makePrediction = (
    draw: string,
    portfolioAnyPrize: boolean | null,
    bestMainHits: number | null,
    predictedTickets: Array<Record<string, unknown>> = [],
  ) => ({
    lottery_type: 'BIG_LOTTO', strategy_id: 'nullable', strategy_version: 'v1',
    target_draw_number: draw, target_draw_date: '2026-01-01',
    prediction_status: 'COMPLETE', predicted_tickets: predictedTickets,
    actual_main_numbers: [1, 2, 3, 4, 5, 6], actual_special_numbers: [7],
    portfolio_any_prize: portfolioAnyPrize, best_main_hits: bestMainHits,
    source_kind: 'native', data_status: 'REBUILDABLE', training,
  })
  const ticket = (mainHitCount: number | null, specialHit: boolean | null, prizeTier: string | null) => ({
    ticket_position: 1, main_numbers: [1, 2, 3, 4, 5, 6], special_numbers: [7],
    main_hit_count: mainHitCount, special_hit: specialHit, prize_tier: prizeTier,
  })
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    const path = new URL(String(input), 'http://localhost').pathname
    const payload = path.endsWith('/replay-strategy-inventory')
      ? { strategy_count: 0, strategies: [] }
      : path.endsWith('/strategies')
      ? { items: [strategy], total_count: 1, next_cursor: null }
      : path.endsWith('/coverage')
        ? { expected_strategy_count: 1, expected_target_count: 3, expected_cell_count: 3,
          completed_cell_count: 3, failed_cell_count: 0, closed_cell_count: 0,
          complete_coverage_percent: 100, missing_strategy_ids: [], run_id: 'test-run' }
        : path.endsWith('/predictions')
          ? { run_id: 'test-run', total_count: 3, next_cursor: null, items: [
            makePrediction('115000101', null, null, [ticket(null, null, null)]),
            makePrediction('115000102', false, 0, [ticket(0, false, null)]),
            makePrediction('115000103', true, 6, [ticket(6, true, 'SIXTH')]),
          ] }
          : { items: [], total_count: 0, limit: 50, offset: 0 }
    return { ok: true, status: 200, json: async () => payload } as Response
  }))
  const wrapper = mount(ReplayHistoryPage)
  await flushPromises()
  await wrapper.findAll('nav[aria-label="Replay history sections"] button')[2]?.trigger('click')
  await flushPromises()
  await wrapper.get('form').trigger('submit')
  await flushPromises()

  const rowFor = (draw: string) => wrapper.get(`[data-testid="backfill-row-${draw}-nullable"]`)
  const nullRow = rowFor('115000101')
  const falseRow = rowFor('115000102')
  const trueRow = rowFor('115000103')
  expect(nullRow.find('td:nth-child(9)').text()).toBe('尚未計算')
  expect(nullRow.find('td:nth-child(8) table tbody tr td:nth-child(4)').text()).toBe('尚未計算')
  expect(nullRow.find('td:nth-child(8) table tbody tr td:nth-child(5)').text()).toBe('尚未計算')
  expect(falseRow.find('.replay-score-trust-status').text()).toBe('資料核對不一致')
  expect(trueRow.find('td:nth-child(9)').text()).toBe('中獎')
  expect(falseRow.find('td:nth-child(8)').text()).toContain('Best main hits: 資料核對不一致')
  expect(falseRow.find('td:nth-child(8) table tbody tr td:nth-child(4)').text())
    .toBe('資料核對不一致（來源 0；集合交集 6）')
  expect(falseRow.find('td:nth-child(8) table tbody tr td:nth-child(5)').text()).toBe('評估狀態未確認')
  expect(falseRow.find('td:nth-child(8) table tbody tr td:nth-child(6)').text()).toBe('評估狀態未確認')
  expect(trueRow.find('td:nth-child(8) table tbody tr td:nth-child(4)').text()).toBe('6')
  expect(trueRow.find('td:nth-child(8) table tbody tr td:nth-child(5)').text()).toBe('命中')
  expect(trueRow.find('td:nth-child(8) table tbody tr td:nth-child(6)').text()).toBe('SIXTH')
  expect(falseRow.find('td:nth-child(9)').text()).not.toContain('尚未計算')
  wrapper.unmount()
})

it('does not treat an aggregate false as evaluated when ticket hit evidence is nullable', async () => {
  const strategy = {
    strategy_id: 'ambiguous', strategy_version: 'v1', display_name: 'Ambiguous strategy',
    lottery_type: 'BIG_LOTTO', lifecycle_status: 'ONLINE', data_status: 'REBUILDABLE',
    source_kind: 'native', executable: true, available_target_count: 1,
    training_status: 'NOT_TRAINABLE',
  }
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    const path = new URL(String(input), 'http://localhost').pathname
    const payload = path.endsWith('/replay-strategy-inventory')
      ? { strategy_count: 0, strategies: [] }
      : path.endsWith('/strategies')
      ? { items: [strategy], total_count: 1, next_cursor: null }
      : path.endsWith('/coverage')
        ? { expected_strategy_count: 1, expected_target_count: 1, expected_cell_count: 1,
          completed_cell_count: 1, failed_cell_count: 0, closed_cell_count: 0,
          complete_coverage_percent: 100, missing_strategy_ids: [], run_id: 'test-run' }
        : path.endsWith('/predictions')
          ? { run_id: 'test-run', total_count: 1, next_cursor: null, items: [{
            lottery_type: 'BIG_LOTTO', strategy_id: 'ambiguous', strategy_version: 'v1',
            target_draw_number: '115000105', target_draw_date: '2026-01-01',
            prediction_status: 'COMPLETE', predicted_tickets: [{
              ticket_position: 1, main_numbers: [1, 2, 3, 4, 5, 6], special_numbers: [7],
              main_hit_count: null, special_hit: null, prize_tier: null,
            }], actual_main_numbers: [1, 2, 3, 4, 5, 6], actual_special_numbers: [7],
            portfolio_any_prize: false, best_main_hits: 0, source_kind: 'native',
            data_status: 'REBUILDABLE', training: {
              training_status: 'NOT_TRAINABLE', model_version: null, training_cutoff: null,
              training_artifact_id: null,
            },
          }] }
          : { items: [], total_count: 0, limit: 50, offset: 0 }
    return { ok: true, status: 200, json: async () => payload } as Response
  }))
  const wrapper = mount(ReplayHistoryPage)
  await flushPromises()
  await wrapper.findAll('nav[aria-label="Replay history sections"] button')[2]?.trigger('click')
  await flushPromises()
  await wrapper.get('form').trigger('submit')
  await flushPromises()

  const row = wrapper.get('[data-testid="backfill-row-115000105-ambiguous"]')
  expect(row.find('td:nth-child(9)').text()).toBe('評估狀態未確認')
  expect(row.find('td:nth-child(8)').text()).toContain('Best main hits: 0')
  wrapper.unmount()
})

it('does not label a missing portfolio_any_prize field as an evaluated result', async () => {
  const strategy = {
    strategy_id: 'missing-field', strategy_version: 'v1', display_name: 'Missing field',
    lottery_type: 'BIG_LOTTO', lifecycle_status: 'ONLINE', data_status: 'REBUILDABLE',
    source_kind: 'native', executable: true, available_target_count: 1,
    training_status: 'NOT_TRAINABLE',
  }
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    const path = new URL(String(input), 'http://localhost').pathname
    const payload = path.endsWith('/replay-strategy-inventory')
      ? { strategy_count: 0, strategies: [] }
      : path.endsWith('/strategies')
      ? { items: [strategy], total_count: 1, next_cursor: null }
      : path.endsWith('/coverage')
        ? { expected_strategy_count: 1, expected_target_count: 1, expected_cell_count: 1,
          completed_cell_count: 1, failed_cell_count: 0, closed_cell_count: 0,
          complete_coverage_percent: 100, missing_strategy_ids: [], run_id: 'test-run' }
        : path.endsWith('/predictions')
          ? { run_id: 'test-run', total_count: 1, next_cursor: null, items: [{
            lottery_type: 'BIG_LOTTO', strategy_id: 'missing-field', strategy_version: 'v1',
            target_draw_number: '115000104', target_draw_date: '2026-01-01',
            prediction_status: 'COMPLETE', predicted_tickets: [],
            actual_main_numbers: [1, 2, 3, 4, 5, 6], actual_special_numbers: [7],
            best_main_hits: 0, source_kind: 'native', data_status: 'REBUILDABLE', training: {
              training_status: 'NOT_TRAINABLE', model_version: null, training_cutoff: null,
              training_artifact_id: null,
            },
          }] }
          : { items: [], total_count: 0, limit: 50, offset: 0 }
    return { ok: true, status: 200, json: async () => payload } as Response
  }))
  const wrapper = mount(ReplayHistoryPage)
  await flushPromises()
  await wrapper.findAll('nav[aria-label="Replay history sections"] button')[2]?.trigger('click')
  await flushPromises()
  await wrapper.get('form').trigger('submit')
  await flushPromises()

  expect(wrapper.get('[data-testid="backfill-predictions-error"]').text()).toBeTruthy()
  expect(wrapper.findAll('[data-testid^="backfill-row-"]')).toHaveLength(0)
  expect(wrapper.text()).not.toContain('未命中')
  expect(wrapper.text()).not.toContain('中獎')
  expect(wrapper.text()).not.toContain('尚未計算')
  wrapper.unmount()
})

it('rejects a ticket that omits a required nullable hit field', async () => {
  const strategy = {
    strategy_id: 'missing-ticket-hit', strategy_version: 'v1', display_name: 'Missing ticket hit',
    lottery_type: 'BIG_LOTTO', lifecycle_status: 'ONLINE', data_status: 'REBUILDABLE',
    source_kind: 'native', executable: true, available_target_count: 1,
    training_status: 'NOT_TRAINABLE',
  }
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    const path = new URL(String(input), 'http://localhost').pathname
    const payload = path.endsWith('/replay-strategy-inventory')
      ? { strategy_count: 0, strategies: [] }
      : path.endsWith('/strategies')
      ? { items: [strategy], total_count: 1, next_cursor: null }
      : path.endsWith('/coverage')
        ? { expected_strategy_count: 1, expected_target_count: 1, expected_cell_count: 1,
          completed_cell_count: 1, failed_cell_count: 0, closed_cell_count: 0,
          complete_coverage_percent: 100, missing_strategy_ids: [], run_id: 'test-run' }
        : path.endsWith('/predictions')
          ? { run_id: 'test-run', total_count: 1, next_cursor: null, items: [{
            lottery_type: 'BIG_LOTTO', strategy_id: 'missing-ticket-hit', strategy_version: 'v1',
            target_draw_number: '115000106', target_draw_date: '2026-01-01',
            prediction_status: 'COMPLETE', predicted_tickets: [{
              ticket_position: 1, main_numbers: [1, 2, 3, 4, 5, 6], special_numbers: [7],
              main_hit_count: null, prize_tier: null,
            }], actual_main_numbers: [1, 2, 3, 4, 5, 6], actual_special_numbers: [7],
            portfolio_any_prize: null, best_main_hits: null, source_kind: 'native',
            data_status: 'REBUILDABLE', training: {
              training_status: 'NOT_TRAINABLE', model_version: null, training_cutoff: null,
              training_artifact_id: null,
            },
          }] }
          : { items: [], total_count: 0, limit: 50, offset: 0 }
    return { ok: true, status: 200, json: async () => payload } as Response
  }))
  const wrapper = mount(ReplayHistoryPage)
  await flushPromises()
  await wrapper.findAll('nav[aria-label="Replay history sections"] button')[2]?.trigger('click')
  await flushPromises()
  await wrapper.get('form').trigger('submit')
  await flushPromises()

  expect(wrapper.get('[data-testid="backfill-predictions-error"]').text()).toContain('invalid response')
  expect(wrapper.findAll('[data-testid^="backfill-row-"]')).toHaveLength(0)
  wrapper.unmount()
})
