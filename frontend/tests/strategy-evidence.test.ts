// @vitest-environment jsdom

import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  queryStrategyEvidence,
  StrategyEvidenceRequestError,
  type StrategyEvidenceResponse,
} from '../src/api/strategyEvidence'
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
    expect(text).toContain('B649')
    expect(text).toContain('P638')
    expect(text).not.toContain('DAILY_539')
    expect(text).not.toContain('BIG_LOTTO')
    expect(text).not.toContain('POWER_LOTTO')
    wrapper.unmount()
  })
})

describe('queryStrategyEvidence canonical D3 definition validation', () => {
  it('accepts a response carrying a well-formed canonical D3 definition', async () => {
    fetchMock.mockResolvedValue(apiResponse(makeEvidence()))

    const result = await queryStrategyEvidence()

    expect(result.d3.definition.metric_id).toBe('D3')
    expect(result.d3.definition.authority_path).toBe(
      'contracts/evidence/metric_definitions/d3.json',
    )
  })

  it('fails closed when the canonical D3 definition block is missing', async () => {
    const evidence = makeEvidence()
    const { definition: _definition, ...d3WithoutDefinition } = evidence.d3
    fetchMock.mockResolvedValue(
      apiResponse({ ...evidence, d3: d3WithoutDefinition }),
    )

    await expect(queryStrategyEvidence()).rejects.toBeInstanceOf(StrategyEvidenceRequestError)
  })

  it('fails closed when a required canonical D3 definition field is malformed', async () => {
    const evidence = makeEvidence()
    fetchMock.mockResolvedValue(
      apiResponse({
        ...evidence,
        d3: {
          ...evidence.d3,
          definition: { ...evidence.d3.definition, decimal_scale: 'not-a-number' },
        },
      }),
    )

    await expect(queryStrategyEvidence()).rejects.toBeInstanceOf(StrategyEvidenceRequestError)
  })
})
