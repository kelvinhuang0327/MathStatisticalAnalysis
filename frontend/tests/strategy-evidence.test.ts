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
        definition_prose:
          'D3 is reserved for a future Owner-approved primary ranking metric. No formula, threshold, or ranking direction is committed by this task. Any result declaring VALUE_PRESENT against this definition is a METRIC_DEFINITION_FAILURE.',
        authority_path: 'contracts/evidence/metric_definitions/d3.json',
      },
    },
  }
}

function evidenceWithItem(patch: Record<string, unknown>): unknown {
  const evidence = makeEvidence()
  return { ...evidence, items: [{ ...evidenceItem, ...patch }] }
}

function evidenceWithD3Definition(patch: Record<string, unknown>): unknown {
  const evidence = makeEvidence()
  return {
    ...evidence,
    d3: {
      ...evidence.d3,
      definition: { ...evidence.d3.definition, ...patch },
    },
  }
}

async function expectBadGateway(payload: unknown): Promise<void> {
  fetchMock.mockResolvedValue(apiResponse(payload))
  const error = await queryStrategyEvidence().catch((cause: unknown) => cause)
  expect(error).toBeInstanceOf(StrategyEvidenceRequestError)
  expect(error).toMatchObject({ status: 502 })
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

    const error = await queryStrategyEvidence().catch((cause: unknown) => cause)
    expect(error).toBeInstanceOf(StrategyEvidenceRequestError)
    expect(error).toMatchObject({ status: 502 })
  })

  it.each([
    ['negative replicate', { replicate: -1 }],
    ['fractional replicate', { replicate: 1.5 }],
    ['NaN replicate', { replicate: Number.NaN }],
    ['infinite replicate', { replicate: Number.POSITIVE_INFINITY }],
    ['unsafe replicate', { replicate: Number.MAX_SAFE_INTEGER + 1 }],
    ['zero minimum_history', { minimum_history: 0 }],
    ['negative minimum_history', { minimum_history: -1 }],
    ['fractional minimum_history', { minimum_history: 1.5 }],
    ['NaN minimum_history', { minimum_history: Number.NaN }],
    ['infinite minimum_history', { minimum_history: Number.POSITIVE_INFINITY }],
    ['unsafe minimum_history', { minimum_history: Number.MAX_SAFE_INTEGER + 1 }],
  ])('rejects %s as malformed evidence', async (_label, itemPatch) => {
    await expectBadGateway(evidenceWithItem(itemPatch))
  })

  it.each([
    ['unknown lifecycle status', { lifecycle_status: 'UNRECOGNIZED' }],
    ['unsupported lottery type', { supported_lottery_types: ['LOTTO_X'] }],
    ['null registration status', { registration_status: null }],
    ['unknown registration status', { registration_status: 'REGISTERED' }],
    ['null definition status', { definition_status: null }],
    ['unknown definition status', { definition_status: 'AVAILABLE' }],
    ['null verification status', { verification_status: null }],
    ['unknown verification status', { verification_status: 'VERIFIED' }],
    ['blank strategy identity', { strategy_id: '   ' }],
    ['placeholder display name', { display_name: 'TBD' }],
    ['null strategy version', { strategy_version: null }],
    [
      'placeholder identity marked verified',
      {
        strategy_id: 'unknown',
        registration_status: 'CANONICAL_EVIDENCE_REGISTERED',
        verification_status: 'EVIDENCE_VERIFIED',
      },
    ],
  ])('rejects %s as malformed evidence', async (_label, itemPatch) => {
    await expectBadGateway(evidenceWithItem(itemPatch))
  })

  it.each([
    ['available formula status', { formula_status: 'AVAILABLE' }],
    ['wrong metric identity', { metric_id: 'D4' }],
    ['wrong metric version', { metric_version: 'v2' }],
    ['wrong schema identity', { schema_id: 'other.schema' }],
    ['wrong schema version', { schema_version: '2.0.0' }],
    ['wrong direction', { direction: 'HIGHER_IS_BETTER' }],
    ['wrong aggregation', { aggregation: 'SUM' }],
    ['wrong sample unit', { sample_unit: 'ROWS' }],
    ['negative decimal scale', { decimal_scale: -1 }],
    ['fractional decimal scale', { decimal_scale: 1.5 }],
    ['infinite decimal scale', { decimal_scale: Number.POSITIVE_INFINITY }],
    ['wrong rounding mode', { rounding_mode: 'ROUND_HALF_UP' }],
    ['wrong unit', { unit: 'PERCENT' }],
    ['wrong authority path', { authority_path: 'contracts/evidence/d4.json' }],
  ])('rejects %s as malformed D3 evidence', async (_label, definitionPatch) => {
    await expectBadGateway(evidenceWithD3Definition(definitionPatch))
  })

  it('rejects D3 availability that claims a calculated value', async () => {
    const evidence = makeEvidence()
    await expectBadGateway({
      ...evidence,
      d3: { ...evidence.d3, status: 'VALUE_PRESENT', value: '0.5000' },
    })
  })

  it('accepts a valid empty evidence catalog', async () => {
    fetchMock.mockResolvedValue(apiResponse(makeEvidence([])))

    await expect(queryStrategyEvidence()).resolves.toMatchObject({ items: [] })
  })

  it.each([0, Number.MAX_SAFE_INTEGER])(
    'accepts a nonnegative safe-integer replicate (%s)',
    async (replicate) => {
      fetchMock.mockResolvedValue(
        apiResponse(evidenceWithItem({ replicate })),
      )

      await expect(queryStrategyEvidence()).resolves.toMatchObject({
        items: [{ replicate }],
      })
    },
  )

  it('preserves non-200 HTTP errors and their status', async () => {
    fetchMock.mockResolvedValue(apiResponse({ message: 'service unavailable' }, 503))

    const error = await queryStrategyEvidence().catch((cause: unknown) => cause)
    expect(error).toBeInstanceOf(StrategyEvidenceRequestError)
    expect(error).toMatchObject({ status: 503, message: 'service unavailable' })
  })

  it('does not render malformed verified evidence as a successful result', async () => {
    fetchMock.mockResolvedValue(
      apiResponse(
        evidenceWithItem({
          lifecycle_status: 'UNRECOGNIZED',
          registration_status: 'CANONICAL_EVIDENCE_REGISTERED',
          verification_status: 'EVIDENCE_VERIFIED',
        }),
      ),
    )
    const wrapper = mount(StrategyEvidencePage)
    await flushPromises()

    expect(wrapper.text()).toContain('invalid response contract')
    expect(wrapper.text()).not.toContain('sample_strategy_evidence_check')
    expect(wrapper.text()).not.toContain('EVIDENCE_VERIFIED')
    wrapper.unmount()
  })
})
