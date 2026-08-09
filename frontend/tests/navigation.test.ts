// @vitest-environment jsdom

import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import App from '../src/App.vue'
import { makeRunPage } from './historical-success-windows-fixtures'

let fetchMock: ReturnType<typeof vi.fn<typeof fetch>>

function apiResponse(payload: unknown): Response {
  return {
    ok: true,
    status: 200,
    json: vi.fn().mockResolvedValue(payload),
  } as unknown as Response
}

const keyboardRun = {
  run_id: 'keyboard-failed-run',
  operation_type: 'MANUAL_SYNC',
  status: 'FAILED',
  lottery_type: 'BIG_LOTTO',
  source_filename: 'keyboard-fixture',
  source_sha256: 'a'.repeat(64),
  parser_version: 'AUTOMATION_AUDIT_V1',
  trigger: 'MANUAL_SYNC',
  provider: 'keyboard-fixture',
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

function tabbableElements(): HTMLElement[] {
  return Array.from(
    document.querySelectorAll<HTMLElement>(
      'a[href], button:not(:disabled), input:not(:disabled), select:not(:disabled)',
    ),
  ).filter((element) => element.tabIndex >= 0 && !element.hidden)
}

function keyboardTab(shiftKey = false): HTMLElement {
  const current = document.activeElement as HTMLElement
  current.dispatchEvent(new KeyboardEvent('keydown', { key: 'Tab', shiftKey, bubbles: true }))
  const elements = tabbableElements()
  const currentIndex = elements.indexOf(current)
  let target: HTMLElement | undefined

  if (currentIndex >= 0) {
    target = elements.at(shiftKey ? currentIndex - 1 : currentIndex + 1)
  } else {
    const ordered = elements.filter((element) => {
      const position = current.compareDocumentPosition(element)
      return shiftKey
        ? Boolean(position & Node.DOCUMENT_POSITION_PRECEDING)
        : Boolean(position & Node.DOCUMENT_POSITION_FOLLOWING)
    })
    target = shiftKey ? ordered.at(-1) : ordered.at(0)
  }
  target ??= shiftKey ? elements.at(-1) : elements.at(0)
  if (!target) throw new Error('No tabbable target is available')
  target.focus()
  target.dispatchEvent(new KeyboardEvent('keyup', { key: 'Tab', shiftKey, bubbles: true }))
  return target
}

function tabUntil(
  predicate: (element: HTMLElement) => boolean,
  shiftKey = false,
  maximumMoves = 40,
): HTMLElement {
  const visited: string[] = []
  for (let move = 0; move < maximumMoves; move += 1) {
    const target = keyboardTab(shiftKey)
    visited.push(
      `${target.tagName}:${target.textContent?.trim() ?? ''}:${target.getAttribute('type') ?? ''}`,
    )
    if (predicate(target)) return target
  }
  throw new Error(`Keyboard journey did not reach the expected control: ${visited.join(' -> ')}`)
}

async function activateFocused(key: 'Enter' | ' '): Promise<void> {
  const current = document.activeElement as HTMLElement
  const hashChange =
    current instanceof HTMLAnchorElement && current.hash !== window.location.hash
      ? new Promise<void>((resolve) =>
          window.addEventListener('hashchange', () => resolve(), { once: true }),
        )
      : Promise.resolve()
  current.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true }))
  current.dispatchEvent(new KeyboardEvent('keyup', { key, bubbles: true }))
  current.click()
  await hashChange
  await flushPromises()
}

function enterFocusedValue(value: string): void {
  const current = document.activeElement
  if (!(current instanceof HTMLInputElement)) {
    throw new Error('Expected the focused element to be an input')
  }
  current.value = value
  current.dispatchEvent(new InputEvent('input', { bubbles: true, data: value }))
  current.dispatchEvent(new Event('change', { bubbles: true }))
}

beforeEach(() => {
  window.location.hash = '#/strategies'
  fetchMock = vi.fn<typeof fetch>().mockImplementation((input) => {
    const url = String(input)
    if (url.includes('/api/v1/strategy-overview')) {
      return Promise.resolve(
        apiResponse({
          items: [
            {
              strategy_id: 'biglotto_social_wisdom_anti_popularity',
              display_name: 'Strategy fixture',
              version: 'v0.1',
              supported_lottery_types: ['BIG_LOTTO'],
              minimum_history: 1,
              lifecycle_status: 'OBSERVATION',
              executable: false,
              provenance: ['fixture:navigation'],
            },
          ],
          summary: {
            total: 1,
            executable_count: 0,
            metadata_only_count: 1,
            lifecycle_counts: {
              IDEA: 0,
              OBSERVATION: 1,
              ONLINE: 0,
              REJECTED: 0,
              RETIRED: 0,
            },
            lottery_type_counts: {
              DAILY_539: 0,
              BIG_LOTTO: 1,
              POWER_LOTTO: 0,
            },
          },
          capabilities: {
            evaluation_metrics_available: false,
            d3_status_available: false,
            best_strategy_ranking_available: false,
            unavailable_reason_codes: ['NO_CANONICAL_STRATEGY_EVALUATION_EVIDENCE'],
          },
        }),
      )
    }
    if (url.includes('/api/v1/strategy-evidence')) {
      return Promise.resolve(
        apiResponse({
          items: [
            {
              strategy_id: 'keyboard_evidence_fixture',
              strategy_version: 'v1',
              replicate: 'NOT_APPLICABLE',
              display_name: 'Keyboard evidence fixture',
              lifecycle_status: 'OBSERVATION',
              executable: false,
              supported_lottery_types: ['BIG_LOTTO'],
              minimum_history: 1,
              provenance: ['fixture:keyboard'],
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
          d3: { status: 'RESERVED_UNAVAILABLE', value: 'NOT_AVAILABLE' },
        }),
      )
    }
    if (url.includes('/api/v1/b649-multi-ticket-records/summary')) {
      return Promise.resolve(
        apiResponse({
          progress: {
            total_strategy_count: 221,
            reproduced_count: 135,
            backtested_count: 135,
            closed_count: 74,
            duplicate_alias_count: 12,
            owner_decision_required_count: 0,
            uncompleted_count: 0,
          },
          prefix_counts: [5, 10, 15, 20],
          windows: ['FULL', 'RECENT_750', 'RECENT_300', 'RECENT_50'],
          success_criteria: [
            'M3_PLUS',
            'M4_PLUS',
            'M5_PLUS',
            'M6',
            'M2_PLUS_SPECIAL',
            'M3_PLUS_SPECIAL',
            'M4_PLUS_SPECIAL',
            'M5_PLUS_SPECIAL',
          ],
          method_families: ['fixture'],
          reproduction_statuses: [
            'BACKTESTED',
            'CLOSED_UNEXECUTABLE',
            'DUPLICATE_ALIAS',
          ],
          catalog_sha256: 'c'.repeat(64),
          records_available: false,
          projection_sha256: null,
          source_report_count: null,
          research_disclaimer:
            '歷史成功率、排名與隨機基準差異僅供描述性研究，不構成未來預測、推薦、上線決策或中獎保證。',
        }),
      )
    }
    if (url.includes('/api/v1/historical-results/runs')) {
      return Promise.resolve(apiResponse(makeRunPage()))
    }
    if (url.endsWith('/api/v1/ingestion-runs/keyboard-failed-run')) {
      return Promise.resolve(
        apiResponse({
          run: keyboardRun,
          items: [
            {
              source_row_number: 1,
              lottery_type: 'BIG_LOTTO',
              draw_number: '1001',
              source: 'keyboard-fixture',
              disposition: 'FAILED',
              normalized_record_hash: 'b'.repeat(64),
              message: 'Sanitized keyboard fixture failure.',
            },
          ],
          item_count: 1,
          items_truncated: false,
        }),
      )
    }
    if (url.includes('/api/v1/ingestion-runs')) {
      return Promise.resolve(
        apiResponse({
          records: [keyboardRun],
          page: 1,
          page_size: 25,
          total_count: 1,
          total_pages: 1,
          sort: ['started_at:desc', 'id:desc'],
        }),
      )
    }
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
  })
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  vi.unstubAllGlobals()
  window.location.hash = ''
  document.body.replaceChildren()
})

describe('App navigation', () => {
  it('navigates among every local workspace without a router', async () => {
    const wrapper = mount(App)
    await flushPromises()

    const navigation = wrapper.get('nav[aria-label="Primary navigation"]')
    expect(navigation.findAll('a').map((link) => link.text())).toEqual([
      'Strategy Overview',
      'Success Windows',
      'B649 Records',
      'B649 Ranking',
      'Data Center',
      'History',
      'Strategy Evidence',
      'Live Zone Split Bets',
      'P638 Replay',
      'P638 Analysis',
      'T539 Analysis',
      'Replay History',
    ])
    expect(wrapper.find('#strategy-catalog-title').exists()).toBe(true)

    window.location.hash = '#/historical-success-windows'
    window.dispatchEvent(new HashChangeEvent('hashchange'))
    await flushPromises()
    expect(wrapper.find('#historical-success-title').exists()).toBe(true)
    expect(
      navigation
        .find('a[href="#/historical-success-windows"]')
        .attributes('aria-current'),
    ).toBe('page')

    window.location.hash = '#/b649-multi-ticket-records'
    window.dispatchEvent(new HashChangeEvent('hashchange'))
    await flushPromises()
    expect(wrapper.find('#b649-records-title').exists()).toBe(true)
    expect(
      navigation
        .find('a[href="#/b649-multi-ticket-records"]')
        .attributes('aria-current'),
    ).toBe('page')

    window.location.hash = '#/b649-owner-ranking'
    window.dispatchEvent(new HashChangeEvent('hashchange'))
    await flushPromises()
    expect(wrapper.text()).toContain('B649 R2 ranking projection 無法載入')
    expect(
      navigation.find('a[href="#/b649-owner-ranking"]').attributes('aria-current'),
    ).toBe('page')

    window.location.hash = '#/data-center'
    window.dispatchEvent(new HashChangeEvent('hashchange'))
    await flushPromises()
    expect(wrapper.find('#data-center-title').exists()).toBe(true)
    expect(navigation.find('a[href="#/data-center"]').attributes('aria-current')).toBe('page')

    window.location.hash = '#/history'
    window.dispatchEvent(new HashChangeEvent('hashchange'))
    await flushPromises()
    expect(wrapper.find('#history-title').exists()).toBe(true)
    expect(wrapper.find('#draw-history-title').exists()).toBe(true)
    expect(navigation.find('a[href="#/history"]').attributes('aria-current')).toBe('page')

    window.location.hash = '#/strategy-evidence'
    window.dispatchEvent(new HashChangeEvent('hashchange'))
    await flushPromises()
    expect(wrapper.find('#strategy-evidence-title').exists()).toBe(true)
    expect(
      navigation.find('a[href="#/strategy-evidence"]').attributes('aria-current'),
    ).toBe('page')

    window.location.hash = '#/replay-history'
    window.dispatchEvent(new HashChangeEvent('hashchange'))
    await flushPromises()
    expect(wrapper.find('#replay-history-title').exists()).toBe(true)
    expect(navigation.find('a[href="#/replay-history"]').attributes('aria-current')).toBe('page')

    window.location.hash = '#/strategies'
    window.dispatchEvent(new HashChangeEvent('hashchange'))
    await flushPromises()
    expect(wrapper.find('#strategy-catalog-title').exists()).toBe(true)
    wrapper.unmount()
  })

  it('discards replay target detail when the selected run changes', async () => {
    const run = (runId: string) => ({
      run_id: runId,
      status: 'COMPLETE',
      strategy_count: 10,
      draw_count: 1933,
      complete_target_count: 1,
      excluded_target_count: 0,
      failed_target_count: 0,
      ticket_count: 1,
      source_run_id: `source-${runId}`,
      source_replay_sha256: 'a'.repeat(64),
      source_draw_db_sha256: 'b'.repeat(64),
      second_zone_ssot_version: 'p638-powerlotto-second-zone-v1',
      first_draw_number: '97000001',
      first_draw_date: '2008-01-24',
      last_draw_number: '115000061',
      last_draw_date: '2026-07-30',
    })
    const replay = (targetId: string) => ({
      target_id: targetId,
      target_draw_number: '97000001',
      target_draw_date: '2008-01-24',
      strategy_id: 'zonal_entropy_2bet',
      strategy_version: 'v0.1-p638-wave1',
      status: 'COMPLETE',
      history_boundary_draw_number: '96000001',
      history_boundary_date: '2008-01-21',
      history_length: 30,
      expected_ticket_count: 1,
      exclusion_reason: null,
      failure_reason: null,
      source_target_locator: `source-target-${targetId}`,
      actual_zone1_numbers: [1, 2, 3, 4, 5, 6],
      actual_zone2_number: 7,
      provenance: `provenance-${targetId}`,
      tickets: [
        {
          ticket_id: `ticket-${targetId}`,
          ticket_position: 1,
          predicted_zone1_numbers: [1, 2, 3, 4, 5, 6],
          predicted_zone2_number: 7,
          zone1_hit_count: 6,
          zone2_hit: true,
          source_record_locator: `source-ticket-${targetId}`,
          source_replay_sha256: 'a'.repeat(64),
        },
      ],
    })
    const strategies = (runId: string) => ({
      run_id: runId,
      items: [
        {
          strategy_snapshot_id: `snapshot-${runId}`,
          strategy_id: 'zonal_entropy_2bet',
          display_label: 'Zonal entropy',
          strategy_version: 'v0.1-p638-wave1',
          lifecycle_status: 'ONLINE',
          replay_status: 'R4_RESULT_REUSABLE',
          zone1_contract: '6 numbers',
          zone2_contract: '1 number',
          complete_target_count: 1,
          excluded_target_count: 0,
          ticket_count: 1,
          exclusion_reason: null,
          source_paths: ['fixture'],
          provenance: 'fixture',
          executable: true,
        },
      ],
      total_count: 1,
      limit: 200,
      offset: 0,
    })
    const replayPage = (runId: string, targetId: string) => ({
      run_id: runId,
      items: [replay(targetId)],
      total_count: 1,
      limit: 25,
      offset: 0,
    })
    let resolveStaleDetail: ((response: Response) => void) | undefined
    fetchMock.mockImplementation((input) => {
      const url = String(input)
      if (url.includes('/api/v1/p638-historical/runs?')) {
        return Promise.resolve(
          apiResponse({ items: [run('run-a'), run('run-b')], total_count: 2, limit: 25, offset: 0 }),
        )
      }
      if (url.includes('/run-a/strategies')) return Promise.resolve(apiResponse(strategies('run-a')))
      if (url.includes('/run-b/strategies')) return Promise.resolve(apiResponse(strategies('run-b')))
      if (url.includes('/run-a/replay')) return Promise.resolve(apiResponse(replayPage('run-a', 'target-a')))
      if (url.includes('/run-b/replay')) return Promise.resolve(apiResponse(replayPage('run-b', 'target-b')))
      if (url.includes('/run-a/targets/target-a')) {
        return new Promise<Response>((resolve) => {
          resolveStaleDetail = resolve
        })
      }
      if (url.includes('/run-b/targets/target-b')) return Promise.resolve(apiResponse(replay('target-b')))
      return Promise.resolve(apiResponse({ items: [], total_count: 0, limit: 25, offset: 0 }))
    })

    window.location.hash = '#/p638-historical-replay'
    window.dispatchEvent(new HashChangeEvent('hashchange'))
    const wrapper = mount(App)
    await flushPromises()
    await flushPromises()
    expect(wrapper.find('#p638-replay-title').exists()).toBe(true)

    const openButton = wrapper
      .findAll('button')
      .find((button) => button.text().trim() === 'Open')
    expect(openButton).toBeDefined()
    await openButton?.trigger('click')
    await flushPromises()
    expect(resolveStaleDetail).toBeDefined()

    await wrapper.get('select').setValue('run-b')
    await flushPromises()
    resolveStaleDetail?.(apiResponse(replay('target-a')))
    await flushPromises()

    expect(wrapper.text()).toContain('run-b')
    expect(wrapper.find('.p638-detail-panel').exists()).toBe(false)
    wrapper.unmount()
  })

  it('completes the keyboard-only workspace journey with intentional route focus', async () => {
    const wrapper = mount(App, { attachTo: document.body })
    await flushPromises()

    expect(document.activeElement).toBe(document.body)
    expect(keyboardTab().getAttribute('aria-label')).toBe('LottoLab home')
    expect(keyboardTab().textContent?.trim()).toBe('Strategy Overview')
    expect(keyboardTab().textContent?.trim()).toBe('Success Windows')
    expect(keyboardTab().textContent?.trim()).toBe('B649 Records')
    expect(keyboardTab().textContent?.trim()).toBe('B649 Ranking')
    expect(keyboardTab().textContent?.trim()).toBe('Data Center')
    await activateFocused('Enter')

    expect(window.location.hash).toBe('#/data-center')
    expect(document.activeElement?.textContent?.trim()).toBe('Data Center')
    expect((document.activeElement as HTMLElement).getAttribute('aria-current')).toBe('page')
    expect(tabUntil((element) => element.matches('input[type="file"]'))).toBe(
      wrapper.get('input[type="file"]').element,
    )
    expect(keyboardTab()).toBe(wrapper.get('[data-testid="sync-date-from"]').element)
    enterFocusedValue('2026-07-28')
    expect(keyboardTab()).toBe(wrapper.get('[data-testid="sync-date-to"]').element)
    enterFocusedValue('2026-07-29')
    await wrapper.vm.$nextTick()

    tabUntil((element) => element.textContent?.trim() === 'Run scheduled trigger')
    expect(document.activeElement?.textContent?.trim()).toBe('Run scheduled trigger')
    expect(keyboardTab(true).textContent?.trim()).toBe('Bounded backfill')
    expect(keyboardTab().textContent?.trim()).toBe('Run scheduled trigger')
    tabUntil(
      (element) =>
        element.matches('nav[aria-label="Primary navigation"] a') &&
        element.textContent?.trim() === 'History',
      true,
    )
    await activateFocused('Enter')

    expect(window.location.hash).toBe('#/history')
    expect(document.activeElement?.textContent?.trim()).toBe('History')
    expect((document.activeElement as HTMLElement).getAttribute('aria-current')).toBe('page')
    expect(tabUntil((element) => element.textContent?.trim() === 'Draw History')).toBe(
      wrapper.get('nav[aria-label="History sections"]').findAll('button')[0]?.element,
    )
    expect(keyboardTab().textContent?.trim()).toBe('Ingestion History')
    await activateFocused(' ')
    const openDetail = tabUntil((element) => element.textContent?.trim() === 'Open')
    expect(openDetail.tagName).toBe('BUTTON')
    await activateFocused('Enter')
    expect(wrapper.text()).toContain('Run Detail')
    expect(wrapper.text()).toContain('Sanitized keyboard fixture failure.')

    tabUntil((element) => element.textContent?.trim() === 'Ingestion History', true)
    tabUntil(
      (element) =>
        element.matches('nav[aria-label="Primary navigation"] a') &&
        element.textContent?.trim() === 'Strategy Evidence',
      true,
    )
    await activateFocused('Enter')

    expect(window.location.hash).toBe('#/strategy-evidence')
    expect(document.activeElement?.textContent?.trim()).toBe('Strategy Evidence')
    expect((document.activeElement as HTMLElement).getAttribute('aria-current')).toBe('page')
    expect(tabUntil((element) => element.matches('input[type="search"]'))).toBe(
      wrapper.get('input[type="search"]').element,
    )
    wrapper.unmount()
  })

  it('reaches the T539 Analysis controls via keyboard, including the run selector and a retry control', async () => {
    window.location.hash = '#/t539-strategy-analysis'
    const t539Run = {
      run_id: 'run-t539-kb',
      schema_version: 'v1',
      lottery_type: 'DAILY_539',
      source_endpoint: 'https://example.invalid/t539',
      source_sha256: 'a'.repeat(64),
      as_of_date: '2026-08-01',
      adapter_source_commit: 'b'.repeat(40),
      status: 'COMPLETE',
      strategy_count: 1,
      draw_count: 100,
      eligible_target_count: 90,
      ticket_count: 90,
      failure_count: 0,
      first_draw_id: 'draw-1',
      first_draw_date: '2020-01-01',
      last_draw_id: 'draw-100',
      last_draw_date: '2026-07-30',
    }
    const strategy = {
      run_id: 'run-t539-kb',
      strategy_id: 't539_keyboard_fixture',
      strategy_version: 'v1',
      native_ticket_count: 1,
      min_history: 30,
      first_eligible_target_draw_id: 'draw-31',
      expected_target_draw_count: 90,
      processed_target_draw_count: 90,
      successful_target_draw_count: 90,
      failed_target_draw_count: 0,
      status: 'SUCCESS',
      ticket_count: 90,
      winning_ticket_count: 9,
      hit_distribution: [{ value: 3, count: 9 }],
      first_target_draw_date: '2020-02-01',
      last_target_draw_date: '2026-07-30',
    }
    const ranking = {
      run_id: 'run-t539-kb',
      rank: 1,
      strategy_id: 't539_keyboard_fixture',
      strategy_version: 'v1',
      native_ticket_count: 1,
      eligible_target_count: 90,
      winning_target_count: 9,
      winning_target_rate: 0.1,
      total_ticket_count: 90,
      winning_ticket_count: 9,
      ticket_winning_rate: 0.1,
      prize_tier_counts: [{ prize_tier: 'sixth', count: 9 }],
      highest_prize_tier_achieved: 'sixth',
      first_eligible_draw: 'draw-31',
      last_eligible_draw: 'draw-100',
      prize_rule_version: 'v1',
      prize_rule_provenance: 'fixture',
    }

    fetchMock.mockImplementation((input) => {
      const url = String(input)
      if (url.includes('/t539-historical/runs?')) {
        return Promise.resolve(apiResponse({ items: [t539Run], total_count: 1, limit: 25, offset: 0 }))
      }
      if (url.includes('/strategies?')) {
        return Promise.resolve(
          apiResponse({ run_id: 'run-t539-kb', items: [strategy], total_count: 1, limit: 100, offset: 0 }),
        )
      }
      if (url.includes('/rankings')) {
        return Promise.resolve(
          apiResponse({ run_id: 'run-t539-kb', items: [ranking], disclaimer: 'fixture disclaimer' }),
        )
      }
      if (url.includes('/coverage')) {
        return Promise.resolve(
          apiResponse({
            run_id: 'run-t539-kb',
            executed: [
              {
                strategy_id: 't539_keyboard_fixture',
                strategy_version: 'v1',
                native_ticket_count: 1,
                min_history: 30,
                selection_reason: 'wave1_fixed_scope',
              },
            ],
            blocked: [
              {
                strategy_id: 't539_blocked_keyboard_fixture',
                reason_code: 'INSUFFICIENT_HISTORY',
                reason: 'not enough history for replay.',
              },
            ],
            coverage_complete: false,
          }),
        )
      }
      if (url.includes('/metrics')) {
        return Promise.resolve(
          apiResponse({ error_code: 'T539_HISTORICAL_UNAVAILABLE', message: 'metrics sanitized unavailable' }, 503),
        )
      }
      return Promise.resolve(
        apiResponse({ records: [], page: 1, page_size: 25, total_count: 0, total_pages: 0, sort: [] }),
      )
    })

    const wrapper = mount(App, { attachTo: document.body })
    await flushPromises()
    await flushPromises()

    expect(wrapper.find('#t539-analysis-title').exists()).toBe(true)
    expect(document.activeElement).toBe(document.body)

    tabUntil(
      (element) =>
        element.matches('nav[aria-label="Primary navigation"] a') &&
        element.textContent?.trim() === 'T539 Analysis',
    )
    expect((document.activeElement as HTMLElement).getAttribute('aria-current')).toBe('page')

    expect(keyboardTab().textContent?.trim()).toBe('Replay History')
    expect(keyboardTab().textContent?.trim()).toBe('Refresh')
    expect(keyboardTab()).toBe(wrapper.get('[data-testid="t539-run-select"]').element)

    const retry = tabUntil((element) => element.matches('[data-testid="t539-retry-metrics"]'))
    expect(retry.tagName).toBe('BUTTON')

    const selectStrategyButton = tabUntil((element) =>
      element.matches('[data-testid="t539-select-strategy-t539_keyboard_fixture"]'),
    )
    expect(selectStrategyButton.tagName).toBe('BUTTON')

    wrapper.unmount()
  })
})
