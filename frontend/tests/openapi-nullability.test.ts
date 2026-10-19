import { readFileSync } from 'node:fs'

import { describe, expect, it } from 'vitest'

import { schemaType } from '../scripts/generate-openapi-types.mjs'

describe('OpenAPI nullable TypeScript generation', () => {
  it('renders direct, union, reference, and array-item null schemas precisely', () => {
    expect(schemaType({ type: 'null' })).toBe('null')
    expect(schemaType({ anyOf: [{ type: 'string' }, { type: 'null' }] })).toBe(
      'string | null',
    )
    expect(
      schemaType({
        oneOf: [{ $ref: '#/components/schemas/LotteryType' }, { type: 'null' }],
      }),
    ).toBe("components['schemas'][\"LotteryType\"] | null")
    expect(
      schemaType({
        type: 'array',
        items: { anyOf: [{ type: 'number' }, { type: 'null' }] },
      }),
    ).toBe('Array<number | null>')
  })

  it('keeps representative committed declarations nullable without unknown', () => {
    const declarations = readFileSync(
      new URL('../src/api/generated/openapi.d.ts', import.meta.url),
      'utf8',
    )

    expect(declarations).toContain(
      '"result": components[\'schemas\']["ImportCommitResultView"] | null',
    )
    expect(declarations).toContain('"row_number": number | null')
    expect(declarations).toContain(
      '"lottery_type": components[\'schemas\']["LotteryType"] | null',
    )
    expect(declarations).toContain('"source_reference": string | null')
    expect(declarations).not.toContain('| unknown')
  })
})


it('keeps K5 separate with nullable enrichment, integer position and shared source scopes', () => {
  const contract = JSON.parse(readFileSync('../contracts/openapi.json', 'utf8'))
  const schemas = contract.components.schemas
  expect(schemas.B649ExactNativeTicketCount.enum).toEqual([2, 3, 5, 10])
  const k5 = schemaType(schemas.B649K5Record)
  for (const field of ['catalog_strategy_version', 'legacy_method_id', 'source_path', 'method_family', 'metric_unavailable_reason']) {
    expect(k5).toContain(`"${field}": string | null`)
  }
  expect(k5).toContain('"position": number | null')
  expect(k5).toContain('"official_rank": number | null')
  expect(schemaType(schemas.B649K5RecordPageResponse)).toContain('"ties": Array<')
  expect(schemaType(schemas.B649K10Record)).toContain('"position": null')
  expect(schemaType(schemas.B649ExactNativeRecordView)).toContain('"official_rank"?: null')
})
