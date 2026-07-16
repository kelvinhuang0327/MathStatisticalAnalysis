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
