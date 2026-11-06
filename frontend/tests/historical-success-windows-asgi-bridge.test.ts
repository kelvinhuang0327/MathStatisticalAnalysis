// @vitest-environment jsdom

import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { cwd } from 'node:process'
import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  type HistoricalRunPage,
  listHistoricalSuccessWindows,
  type HistoricalSuccessWindowPage,
} from '../src/api/historicalSuccessWindows'
import HistoricalSuccessWindowsPage from '../src/features/historical-success-windows/HistoricalSuccessWindowsPage.vue'

const RIGHT_IMPORT_SHA = 'b'.repeat(64)

function apiResponse(payload: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: vi.fn().mockResolvedValue(payload),
  } as unknown as Response
}

function deferred<T>(): {
  promise: Promise<T>
  resolve: (value: T | PromiseLike<T>) => void
} {
  let resolve!: (value: T | PromiseLike<T>) => void
  const promise = new Promise<T>((resolver) => {
    resolve = resolver
  })
  return { promise, resolve }
}

const capture = JSON.parse(
  readFileSync(
    resolve(
      cwd(),
      'tests/fixtures/historical-success-windows-asgi-bridge.capture.json',
    ),
    'utf8',
  ),
) as HistoricalSuccessWindowPage
const incompleteCapture = JSON.parse(
  readFileSync(
    resolve(
      cwd(),
      'tests/fixtures/historical-success-windows-asgi-bridge-incomplete.capture.json',
    ),
    'utf8',
  ),
) as HistoricalSuccessWindowPage
const missingSourceError = JSON.parse(
  readFileSync(
    resolve(
      cwd(),
      'tests/fixtures/historical-success-windows-missing-source.capture.json',
    ),
    'utf8',
  ),
) as { error_code: string; message: string }
const importIdentity = capture.metadata.import_identity_sha256

let fetchMock: ReturnType<typeof vi.fn<typeof fetch>>

function runPage(selectedImportIdentity = importIdentity): HistoricalRunPage {
  const run = {
    run_id: capture.metadata.run_id,
    import_identity_sha256: selectedImportIdentity,
    manifest_sha256: 'f'.repeat(64),
    contract_version: capture.metadata.contract_version,
    source_kind: capture.metadata.source_kind,
    source_repository: capture.metadata.source_repository,
    source_commit_oid: capture.metadata.source_commit_oid,
    source_artifact_sha256: capture.metadata.source_artifact_sha256,
    dataset_identity: capture.metadata.dataset_identity,
    dataset_sha256: capture.metadata.dataset_sha256,
    legacy_run_id: null,
    lottery_type: capture.metadata.lottery_type,
    started_at: '2026-11-04T00:00:00Z',
    completed_at: '2026-11-04T00:01:00Z',
    status: 'COMPLETED',
    strategy_count: 2,
    draw_count: 751,
    portfolio_count: 750,
    is_idempotent_replay: false,
  }
  return {
    items: [
      run,
      { ...run, run_id: 'missing-import-run', import_identity_sha256: RIGHT_IMPORT_SHA },
    ],
    total_count: 2,
    limit: 10,
    offset: 0,
  }
}

function captureItem(strategyId: string) {
  const item = capture.items.find(
    (candidate) => candidate.strategy.strategy_id === strategyId,
  )
  if (item === undefined) throw new Error(`Missing capture identity ${strategyId}`)
  return item
}

function renderedCard(wrapper: ReturnType<typeof mount>, strategyId: string) {
  const card = wrapper
    .findAll('.strategy-window-card')
    .find((candidate) => candidate.get('h3').text() === strategyId)
  if (card === undefined) throw new Error(`Missing rendered identity ${strategyId}`)
  return card
}

beforeEach(() => {
  fetchMock = vi.fn<typeof fetch>()
  vi.stubGlobal('fetch', fetchMock)
  Object.defineProperty(navigator, 'clipboard', {
    configurable: true,
    value: { writeText: vi.fn().mockResolvedValue(undefined) },
  })
})

afterEach(() => vi.unstubAllGlobals())

describe('SQLite to ASGI to API client to Vue bridge', () => {
  it('replays the captured HTTP JSON through the client and renders all four windows verbatim', async () => {
    fetchMock.mockResolvedValueOnce(apiResponse(capture))
    const page = await listHistoricalSuccessWindows({
      import_identity_sha256: importIdentity,
      prefix_count: 1,
      criterion: 'M3_PLUS',
      limit: capture.limit,
      offset: capture.offset,
    })
    expect(page).toEqual(capture)
    const clientUrl = new URL(String(fetchMock.mock.calls[0]?.[0]), 'http://localhost')
    expect(Object.fromEntries(clientUrl.searchParams)).toMatchObject({
      import_identity_sha256: importIdentity,
      prefix_count: '1',
      criterion: 'M3_PLUS',
      limit: String(capture.limit),
      offset: String(capture.offset),
    })

    fetchMock.mockClear()
    fetchMock.mockImplementation((input) => {
      const url = String(input)
      if (url.includes('/historical-results/runs')) {
        return Promise.resolve(apiResponse(runPage()))
      }
      if (url.includes('/historical-prefix-success-windows')) {
        return Promise.resolve(apiResponse(capture))
      }
      throw new Error(`Unexpected bridge request: ${url}`)
    })

    const wrapper = mount(HistoricalSuccessWindowsPage)
    await flushPromises()
    await wrapper.get('select[name="historical-run"]').setValue(importIdentity)
    await wrapper.get('form.analysis-controls').trigger('submit')
    await flushPromises()

    const analysisRequest = fetchMock.mock.calls
      .map(([input]) => String(input))
      .find((url) => url.includes('/historical-prefix-success-windows'))
    expect(analysisRequest).toBeDefined()
    const analysisUrl = new URL(analysisRequest!, 'http://localhost')
    expect(Object.fromEntries(analysisUrl.searchParams)).toMatchObject({
      import_identity_sha256: importIdentity,
      prefix_count: '1',
      criterion: 'M3_PLUS',
    })

    const main = captureItem('SYNTHETIC_BRIDGE_MAIN')
    const mainCard = renderedCard(wrapper, main.strategy.strategy_id)
    const windowCards = mainCard.findAll('.window-card')
    expect(windowCards).toHaveLength(4)
    expect(
      windowCards.map((card) => card.get('header span').text()),
    ).toEqual(main.windows.map((window) => window.window_kind))
    expect(
      windowCards.map((card) => card.get('header strong').text()),
    ).toEqual(main.windows.map((window) => window.window_role))

    for (const [index, window] of main.windows.entries()) {
      const card = windowCards[index]!
      expect(card.find('.exact-rate').text()).toBe(
        `${window.success_rate.numerator} / ${window.success_rate.denominator}`,
      )
      expect(card.text()).toContain(
        `${window.requested_draw_count ?? 'all'} draws`,
      )
      expect(card.find('footer').text()).toContain(String(window.first_target.draw_number))
      expect(card.find('footer').text()).toContain(String(window.last_target.draw_number))
      expect(card.text()).toContain(window.evaluation_status)
      expect(card.text()).toContain(window.evidence_status)
      const facts = card.findAll('dl div').map((row) => [
        row.get('dt').text(),
        row.get('dd').text(),
      ])
      expect(facts).toEqual([
        ['Evaluation', window.evaluation_status],
        ['Evidence', window.evidence_status],
        ['Source', String(window.source_draw_count)],
        ['Eligible', String(window.eligible_draw_count)],
        ['Excluded', String(window.excluded_draw_count)],
        ['Success', String(window.success_count)],
        ['Failure', String(window.failure_count)],
        ['Available', window.success_rate.available ? 'YES' : 'NO'],
      ])
    }
    expect(mainCard.text()).toContain(main.strategy.strategy_version)
    expect(mainCard.text()).toContain(`replicate ${main.strategy.replicate}`)
    expect(mainCard.text()).toContain(String(main.selection.ticket_count))

    const zeroWindow = main.windows[3]!
    expect(zeroWindow.success_rate).toEqual({
      numerator: 0,
      denominator: 50,
      available: true,
    })
    expect(windowCards[3]!.find('.exact-rate').text()).toBe('0 / 50')
    for (const window of main.windows) {
      for (const value of [
        window.source_draw_count,
        window.eligible_draw_count,
        window.excluded_draw_count,
        window.success_count,
        window.failure_count,
        window.success_rate.numerator,
        window.success_rate.denominator,
      ]) {
        expect(Number.isSafeInteger(value)).toBe(true)
      }
    }

    const empty = captureItem('SYNTHETIC_BRIDGE_EMPTY')
    const emptyCard = renderedCard(wrapper, empty.strategy.strategy_id)
    expect(empty.status).toBe('NO_OBSERVATIONS')
    expect(empty.windows).toEqual([])
    expect(emptyCard.text()).toContain('ZERO OBSERVATIONS')
    expect(emptyCard.text()).toContain('no window is fabricated')
    expect(wrapper.text()).not.toMatch(/\d+(?:\.\d+)?%/)

    wrapper.unmount()
  })

  it('accepts and renders the captured incomplete-window response with its unavailable 0/0 rate', async () => {
    const incompleteIdentity = incompleteCapture.metadata.import_identity_sha256
    const capturedInsufficient = incompleteCapture.items
      .find((item) => item.strategy.strategy_id === 'SYNTHETIC_BRIDGE_ZERO_NINE')
      ?.windows.find((window) => window.window_kind === 'LONG')
    expect(capturedInsufficient).toMatchObject({
      evaluation_status: 'INSUFFICIENT_DRAWS',
      source_draw_count: 9,
      eligible_draw_count: 9,
      excluded_draw_count: 0,
      success_count: 0,
      failure_count: 9,
      success_rate: { numerator: 0, denominator: 0, available: false },
    })

    fetchMock.mockResolvedValueOnce(apiResponse(incompleteCapture))
    const page = await listHistoricalSuccessWindows({
      import_identity_sha256: incompleteIdentity,
      prefix_count: 1,
      criterion: 'M3_PLUS',
      limit: incompleteCapture.limit,
      offset: incompleteCapture.offset,
    })
    const insufficient = page.items
      .find((item) => item.strategy.strategy_id === 'SYNTHETIC_BRIDGE_ZERO_NINE')
      ?.windows.find((window) => window.window_kind === 'LONG')
    expect(insufficient).toEqual(capturedInsufficient)

    fetchMock.mockClear()
    fetchMock.mockImplementation((input) => {
      const url = String(input)
      if (url.includes('/historical-results/runs')) {
        return Promise.resolve(apiResponse(runPage(incompleteIdentity)))
      }
      if (url.includes('/historical-prefix-success-windows')) {
        return Promise.resolve(apiResponse(incompleteCapture))
      }
      throw new Error(`Unexpected incomplete-window request: ${url}`)
    })

    const wrapper = mount(HistoricalSuccessWindowsPage)
    await flushPromises()
    await wrapper.get('select[name="historical-run"]').setValue(incompleteIdentity)
    await wrapper.get('form.analysis-controls').trigger('submit')
    await flushPromises()

    const card = renderedCard(wrapper, 'SYNTHETIC_BRIDGE_ZERO_NINE')
    const longWindow = card.findAll('.window-card').find(
      (candidate) => candidate.get('header span').text() === 'LONG',
    )
    if (longWindow === undefined) throw new Error('Missing rendered LONG window')
    expect(longWindow.text()).toContain('INSUFFICIENT_DRAWS')
    expect(
      longWindow.findAll('dl div').map((row) => [
        row.get('dt').text(),
        row.get('dd').text(),
      ]),
    ).toContainEqual(['Eligible', '9'])
    expect(longWindow.find('.exact-rate').text()).toBe('Unavailable (0 / 0)')
    expect(longWindow.find('.exact-rate').text()).not.toContain('0%')
    wrapper.unmount()
  })

  it('limits unavailable 0/0 to insufficient windows and keeps validating counts and safe integers', async () => {
    const incompleteIdentity = incompleteCapture.metadata.import_identity_sha256
    const query = {
      import_identity_sha256: incompleteIdentity,
      prefix_count: 1 as const,
      criterion: 'M3_PLUS' as const,
      limit: incompleteCapture.limit,
      offset: incompleteCapture.offset,
    }
    const copyCapture = () =>
      JSON.parse(JSON.stringify(incompleteCapture)) as HistoricalSuccessWindowPage
    const longWindow = (page: HistoricalSuccessWindowPage) => {
      const window = page.items
        .find((item) => item.strategy.strategy_id === 'SYNTHETIC_BRIDGE_ZERO_NINE')
        ?.windows.find((candidate) => candidate.window_kind === 'LONG')
      if (window === undefined) throw new Error('Missing captured LONG window')
      return window
    }
    const expectMalformed = async (page: HistoricalSuccessWindowPage) => {
      fetchMock.mockResolvedValueOnce(apiResponse(page))
      await expect(listHistoricalSuccessWindows(query)).rejects.toMatchObject({
        kind: 'MALFORMED_RESPONSE',
        status: 502,
      })
    }

    const zeroEligible = copyCapture()
    Object.assign(longWindow(zeroEligible), {
      source_draw_count: 9,
      eligible_draw_count: 0,
      excluded_draw_count: 9,
      success_count: 0,
      failure_count: 0,
      success_rate: { numerator: 0, denominator: 0, available: false },
      evaluation_status: 'COMPLETE',
      evidence_status: 'DESCRIPTIVE_ONLY',
    })
    fetchMock.mockResolvedValueOnce(apiResponse(zeroEligible))
    const zeroEligiblePage = await listHistoricalSuccessWindows(query)
    expect(JSON.parse(JSON.stringify(longWindow(zeroEligiblePage)))).toMatchObject({
      evaluation_status: 'COMPLETE',
      source_draw_count: 9,
      eligible_draw_count: 0,
      excluded_draw_count: 9,
      success_count: 0,
      failure_count: 0,
      success_rate: { numerator: 0, denominator: 0, available: false },
    })

    const completeUnavailable = copyCapture()
    longWindow(completeUnavailable).evaluation_status = 'COMPLETE'
    await expectMalformed(completeUnavailable)

    const inconsistentCounts = copyCapture()
    longWindow(inconsistentCounts).failure_count = 8
    await expectMalformed(inconsistentCounts)

    const mismatchedNumerator = copyCapture()
    longWindow(mismatchedNumerator).success_count = 1
    longWindow(mismatchedNumerator).failure_count = 8
    await expectMalformed(mismatchedNumerator)

    const mismatchedDenominator = copyCapture()
    longWindow(mismatchedDenominator).success_rate = {
      numerator: 0,
      denominator: 8,
      available: true,
    }
    await expectMalformed(mismatchedDenominator)

    const availableZeroDenominator = copyCapture()
    longWindow(availableZeroDenominator).success_rate.available = true
    await expectMalformed(availableZeroDenominator)

    const wrongImportIdentity = copyCapture()
    wrongImportIdentity.metadata.import_identity_sha256 = 'c'.repeat(64)
    await expectMalformed(wrongImportIdentity)

    const wrongStrategyIdentity = copyCapture()
    const strategyItem = wrongStrategyIdentity.items.find(
      (item) => item.strategy.strategy_id === 'SYNTHETIC_BRIDGE_ZERO_NINE',
    )
    if (strategyItem === undefined) throw new Error('Missing captured strategy')
    strategyItem.strategy.strategy_id = 'SYNTHETIC_BRIDGE_OTHER'
    await expectMalformed(wrongStrategyIdentity)

    const wrongStrategyVersion = copyCapture()
    const versionItem = wrongStrategyVersion.items.find(
      (item) => item.strategy.strategy_id === 'SYNTHETIC_BRIDGE_ZERO_NINE',
    )
    if (versionItem === undefined) throw new Error('Missing captured strategy')
    versionItem.strategy.strategy_version = 'bridge-v2'
    await expectMalformed(wrongStrategyVersion)

    const wrongWindowIdentity = copyCapture()
    longWindow(wrongWindowIdentity).window_kind = 'SHORT'
    await expectMalformed(wrongWindowIdentity)

    const unsafeCount = copyCapture()
    longWindow(unsafeCount).source_draw_count = Number.MAX_SAFE_INTEGER + 1
    await expectMalformed(unsafeCount)
  })

  it('clears the captured result on import change and ignores its late response after a missing-source error', async () => {
    const olderCapture = deferred<Response>()
    let analysisRequestCount = 0
    fetchMock.mockImplementation((input) => {
      const url = String(input)
      if (url.includes('/historical-results/runs')) {
        return Promise.resolve(apiResponse(runPage()))
      }
      if (url.includes('/historical-prefix-success-windows')) {
        analysisRequestCount += 1
        if (analysisRequestCount === 1) return olderCapture.promise
        return Promise.resolve(apiResponse(missingSourceError, 404))
      }
      throw new Error(`Unexpected bridge request: ${url}`)
    })

    const wrapper = mount(HistoricalSuccessWindowsPage)
    await flushPromises()
    await wrapper.get('select[name="historical-run"]').setValue(importIdentity)
    await wrapper.get('form.analysis-controls').trigger('submit')
    await flushPromises()
    expect(analysisRequestCount).toBe(1)
    const oldSignal = fetchMock.mock.calls.find(([input]) =>
      String(input).includes('/historical-prefix-success-windows'),
    )?.[1]?.signal

    await wrapper.get('select[name="historical-run"]').setValue(RIGHT_IMPORT_SHA)
    expect(wrapper.findAll('.strategy-window-card')).toHaveLength(0)
    await wrapper.get('form.analysis-controls').trigger('submit')
    await flushPromises()
    expect(analysisRequestCount).toBe(2)
    expect(oldSignal?.aborted).toBe(true)
    expect(wrapper.text()).toContain('The exact historical source or strategy no longer exists.')
    expect(wrapper.text()).not.toContain('SYNTHETIC_BRIDGE_MAIN')

    olderCapture.resolve(apiResponse(capture))
    await flushPromises()
    expect(wrapper.findAll('.strategy-window-card')).toHaveLength(0)
    expect(wrapper.text()).not.toContain('SYNTHETIC_BRIDGE_MAIN')
    wrapper.unmount()
  })
})
