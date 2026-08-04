// @vitest-environment jsdom

import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { StrategyEvidenceResponse } from '../src/api/strategyEvidence'
import StrategyEvidencePage from '../src/features/strategy-evidence/StrategyEvidencePage.vue'

type StrategyEvidenceItem = StrategyEvidenceResponse['items'][number]

const evidenceItem = {
  strategy_id: 'sample_strategy_evidence_check',
  strategy_version: 'v0.1',
  replicate: 'NOT_APPLICABLE',
  display_name: 'Sample Strategy Evidence Check',
  lifecycle_status: 'OBSERVATION',
  executable: false,
  supported_lottery_types: ['DAILY_539', 'BIG_LOTTO', 'POWER_LOTTO'],
  minimum_history: 1,
  provenance: [],
  adapter_available: false,
  registration_status: 'CANONICAL_EVIDENCE_MISSING',
  definition_status: 'DEFINITION_AVAILABLE',
  verification_status: 'EVIDENCE_MISSING',
  unavailable_reason_code: null,
} satisfies StrategyEvidenceItem

function makeEvidence(
  items: StrategyEvidenceItem[] = [evidenceItem],
): StrategyEvidenceResponse {
  return {
    items,
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
      status: 'UNAVAILABLE',
      value: 'NOT_AVAILABLE',
    },
  }
}

function apiResponse(payload: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: vi.fn().mockResolvedValue(payload),
  } as unknown as Response
}

let fetchMock: ReturnType<typeof vi.fn<typeof fetch>>

beforeEach(() => {
  fetchMock = vi.fn<typeof fetch>()
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('StrategyEvidencePage', () => {
  it('masks raw lottery type enums behind screen-safe display labels', async () => {
    fetchMock.mockResolvedValue(apiResponse(makeEvidence()))
    const wrapper = mount(StrategyEvidencePage)
    await flushPromises()

    const text = wrapper.text()
    expect(text).toContain('T539')
    expect(text).toContain('L649')
    expect(text).toContain('P638')
    expect(text).not.toContain('DAILY_539')
    expect(text).not.toContain('BIG_LOTTO')
    expect(text).not.toContain('POWER_LOTTO')
    wrapper.unmount()
  })
})
