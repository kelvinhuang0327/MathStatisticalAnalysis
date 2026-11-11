// @vitest-environment jsdom
import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { formatRatePercentage } from '../../../api/rankingMatrix'
import Sealed084ResearchPanel from '../Sealed084ResearchPanel.vue'
import {
  serializeSealed084ManualReviewCsv,
  SEALED_084_STRATEGIES,
  SEALED_084_WINDOWS,
} from '../sealed084Research'
import {
  sealed084ReplayFixture,
  sealed084StatusFixture,
} from './sealed084ApiFixture'

function jsonResponse(payload: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: vi.fn().mockResolvedValue(payload),
  } as unknown as Response
}

function installFetch(
  statusPayload: unknown = sealed084StatusFixture,
  replayPayload: unknown = sealed084ReplayFixture,
  statusCode = 200,
  replayCode = 200,
) {
  const fetchMock = vi.fn<typeof fetch>((input) => {
    const url = String(input)
    if (url.endsWith('/api/v1/b649/sealed-084-replays/status')) {
      return Promise.resolve(jsonResponse(statusPayload, statusCode))
    }
    if (url.endsWith('/api/v1/b649/sealed-084-replays')) {
      return Promise.resolve(jsonResponse(replayPayload, replayCode))
    }
    return Promise.resolve(jsonResponse({ error_code: 'UNEXPECTED_TEST_ROUTE' }, 404))
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function parseCsvLine(line: string): string[] {
  const values: string[] = []
  let value = ''
  let quoted = false
  for (let index = 0; index < line.length; index += 1) {
    const char = line[index]!
    if (char === '"') {
      if (quoted && line[index + 1] === '"') {
        value += '"'
        index += 1
      } else {
        quoted = !quoted
      }
    } else if (char === ',' && !quoted) {
      values.push(value)
      value = ''
    } else {
      value += char
    }
  }
  values.push(value)
  return values
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('084 independent research panel', () => {
  it('maps all 7 strategies and 28 native API rows without changing counts or rates', async () => {
    const fetchMock = installFetch()
    const wrapper = mount(Sealed084ResearchPanel, { props: { enabled: true } })
    await flushPromises()

    expect(fetchMock.mock.calls.map(([url]) => String(url)).sort()).toEqual([
      '/api/v1/b649/sealed-084-replays',
      '/api/v1/b649/sealed-084-replays/status',
    ])
    expect(wrapper.findAll('tbody tr')).toHaveLength(7)
    expect(wrapper.findAll('[data-testid^="sealed-084-cell-"]')).toHaveLength(28)
    expect(wrapper.text()).toContain('7 個策略／28 個窗口結果')
    expect(wrapper.text()).toContain('NOT_DIRECTLY_VERIFIED')

    for (const row of sealed084ReplayFixture.results) {
      const cell = wrapper.get(`[data-testid="sealed-084-cell-${row.strategy_id}-${row.window}"]`)
      expect(cell.text()).toContain(`${row.successful_issues} / ${row.evaluated_issues}`)
      expect(cell.text()).toContain(formatRatePercentage(row.success_rate))
    }
    expect(wrapper.findAll('.sealed-084-peers li')).toHaveLength(40)

    const horizonFull = wrapper.get('[data-testid="sealed-084-cell-b649_new_horizon_minimax_disagreement_r1-FULL"]')
    expect(horizonFull.text()).toContain('原生分母 1966 期；共同 issue 集合 1416 期')
    expect(horizonFull.text()).toContain('NOT_DIRECTLY_COMPARABLE_ELIGIBLE_ISSUE_SET')

    const teK2Full = wrapper.get('[data-testid="sealed-084-cell-research_conditional_transfer_entropy_k2-FULL"]')
    expect(teK2Full.text()).toContain('率差 -1.55 個百分點')
    expect(wrapper.findAll('input')).toHaveLength(0)
    expect(wrapper.findAll('button')).toHaveLength(2)
    wrapper.unmount()
  })

  it('shows SOURCE_UNAVAILABLE and no native percentages when the API source is unavailable', async () => {
    installFetch(
      { error_code: 'SOURCE_UNAVAILABLE', message: 'source root is not configured' },
      { error_code: 'SOURCE_UNAVAILABLE', message: 'source root is not configured' },
      503,
      503,
    )
    const wrapper = mount(Sealed084ResearchPanel, { props: { enabled: true } })
    await flushPromises()

    expect(wrapper.get('[data-testid="sealed-084-source-status"]').text()).toContain('SOURCE_UNAVAILABLE')
    const cell = wrapper.get('[data-testid="sealed-084-cell-research_causal_renewal_hazard_k2-FULL"]')
    expect(cell.text()).toContain('來源不可用／未核實')
    expect(cell.text()).not.toContain('原生')
    expect(wrapper.findAll('.sealed-084-native-metric')).toHaveLength(0)
    wrapper.unmount()
  })

  it('leaves a missing window blank with an explicit status', async () => {
    const payload = {
      ...sealed084ReplayFixture,
      returned_window_rows: 27,
      results: sealed084ReplayFixture.results.filter((row) =>
        !(row.strategy_id === 'b649_new_horizon_minimax_disagreement_r1' && row.window === 'FULL'),
      ),
    }
    installFetch(sealed084StatusFixture, payload)
    const wrapper = mount(Sealed084ResearchPanel, { props: { enabled: true } })
    await flushPromises()

    const cell = wrapper.get('[data-testid="sealed-084-cell-b649_new_horizon_minimax_disagreement_r1-FULL"]')
    expect(cell.text()).toContain('此窗口無資料')
    expect(cell.text()).not.toContain('147 / 1966')
    wrapper.unmount()
  })

  it('does not show a metric when the strategy version differs from the API contract', async () => {
    const payload = {
      ...sealed084ReplayFixture,
      results: sealed084ReplayFixture.results.map((row) =>
        row.strategy_id === 'b649_new_horizon_minimax_disagreement_r1' && row.window === 'FULL'
          ? { ...row, strategy_version: 'v9.9' }
          : row,
      ),
    }
    installFetch(sealed084StatusFixture, payload)
    const wrapper = mount(Sealed084ResearchPanel, { props: { enabled: true } })
    await flushPromises()

    const cell = wrapper.get('[data-testid="sealed-084-cell-b649_new_horizon_minimax_disagreement_r1-FULL"]')
    expect(cell.text()).toContain('版本不符；指標不顯示')
    expect(cell.text()).not.toContain('147 / 1966')
    wrapper.unmount()
  })

  it('does not map a result to a different source artifact identity', async () => {
    const payload = {
      ...sealed084ReplayFixture,
      results: sealed084ReplayFixture.results.map((row) =>
        row.strategy_id === 'b649_new_horizon_minimax_disagreement_r1' && row.window === 'FULL'
          ? { ...row, source_artifact_identity: 'sha256:unmatched-source' }
          : row,
      ),
    }
    installFetch(sealed084StatusFixture, payload)
    const wrapper = mount(Sealed084ResearchPanel, { props: { enabled: true } })
    await flushPromises()

    const cell = wrapper.get('[data-testid="sealed-084-cell-b649_new_horizon_minimax_disagreement_r1-FULL"]')
    expect(cell.text()).toContain('指標資料無效；指標不顯示')
    expect(cell.text()).not.toContain('147 / 1966')
    wrapper.unmount()
  })

  it('exports seven strategy rows and leaves every Owner decision field empty', () => {
    const csv = serializeSealed084ManualReviewCsv(
      sealed084ReplayFixture.results,
      sealed084StatusFixture,
      true,
    )
    const rows = csv.split('\r\n').map(parseCsvLine)
    const header = rows[0]!
    const ownerColumns = ['owner_long_rank', 'owner_mid_rank', 'owner_short_rank', 'owner_reason', 'owner_adoption']

    expect(rows).toHaveLength(8)
    expect(header.slice(-5)).toEqual(ownerColumns)
    for (const row of rows.slice(1)) expect(row.slice(-5)).toEqual(['', '', '', '', ''])
    expect(rows.slice(1).map((row) => row[header.indexOf('strategy_id')])).toEqual(
      SEALED_084_STRATEGIES.map((strategy) => strategy.strategyId),
    )
    expect(header).toContain('native_full_successful_issues')
    expect(header).toContain('common_full_comparable_issue_count')
    expect(SEALED_084_WINDOWS).toHaveLength(4)
  })
})
