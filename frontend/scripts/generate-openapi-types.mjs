import { readFileSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const contractUrl = new URL('../../contracts/openapi.json', import.meta.url)
const outputUrl = new URL('../src/api/generated/openapi.d.ts', import.meta.url)
const contract = JSON.parse(readFileSync(contractUrl, 'utf8'))

const quote = (value) => JSON.stringify(value)

function indent(text, spaces) {
  const prefix = ' '.repeat(spaces)
  return text
    .split('\n')
    .map((line) => `${prefix}${line}`)
    .join('\n')
}

function referenceType(reference) {
  const prefix = '#/components/schemas/'
  if (!reference.startsWith(prefix)) {
    throw new Error(`Unsupported OpenAPI reference: ${reference}`)
  }
  return `components['schemas'][${quote(reference.slice(prefix.length))}]`
}

export function schemaType(schema, level = 0) {
  if (!schema || typeof schema !== 'object') return 'unknown'
  if (schema.$ref) return referenceType(schema.$ref)
  if (Array.isArray(schema.enum)) return schema.enum.map(quote).join(' | ')
  if (schema.anyOf) return schema.anyOf.map((item) => schemaType(item, level)).join(' | ')
  if (schema.oneOf) return schema.oneOf.map((item) => schemaType(item, level)).join(' | ')

  switch (schema.type) {
    case 'string':
      return 'string'
    case 'integer':
    case 'number':
      return 'number'
    case 'boolean':
      return 'boolean'
    case 'null':
      return 'null'
    case 'array':
      return `Array<${schemaType(schema.items, level)}>`
    case 'object': {
      if (schema.properties) {
        const required = new Set(schema.required ?? [])
        const entries = Object.entries(schema.properties).map(([name, property]) => {
          const optional = required.has(name) ? '' : '?'
          return `${quote(name)}${optional}: ${schemaType(property, level + 1)}`
        })
        if (entries.length === 0) return 'Record<string, never>'
        return `{\n${indent(entries.join('\n'), (level + 1) * 2)}\n${' '.repeat(level * 2)}}`
      }
      if (schema.additionalProperties) {
        return `Record<string, ${schemaType(schema.additionalProperties, level)}>`
      }
      return 'Record<string, unknown>'
    }
    default:
      return 'unknown'
  }
}

function renderResponses(responses, level) {
  return Object.entries(responses)
    .map(([status, response]) => {
      const content = response.content ?? {}
      const contentEntries = Object.entries(content).map(
        ([mediaType, media]) => `${quote(mediaType)}: ${schemaType(media.schema, level + 3)}`,
      )
      const contentType = contentEntries.length
        ? `{\n${indent(contentEntries.join('\n'), (level + 2) * 2)}\n${' '.repeat((level + 1) * 2)}}`
        : 'Record<string, never>'
      return `${status}: {\n${indent(`content: ${contentType}`, (level + 1) * 2)}\n${' '.repeat(level * 2)}}`
    })
    .join('\n')
}

function renderPaths(paths) {
  const pathEntries = Object.entries(paths).map(([path, pathItem]) => {
    const methods = Object.entries(pathItem)
      .filter(([method]) => ['get', 'post', 'put', 'patch', 'delete'].includes(method))
      .map(([method, operation]) => {
        const responses = renderResponses(operation.responses ?? {}, 3)
        return `${method}: {\n${indent(`responses: {\n${indent(responses, 8)}\n      }`, 4)}\n  }`
      })
      .join('\n')
    return `${quote(path)}: {\n${indent(methods, 4)}\n  }`
  })
  return `export interface paths {\n${indent(pathEntries.join('\n'), 2)}\n}`
}

function renderComponents(schemas) {
  const entries = Object.entries(schemas).map(
    ([name, schema]) => `${quote(name)}: ${schemaType(schema, 2)}`,
  )
  return `export interface components {\n  schemas: {\n${indent(entries.join('\n'), 4)}\n  }\n}`
}

const generated = [
  '// Generated from contracts/openapi.json. Do not edit by hand.',
  `// OpenAPI ${contract.openapi}; ${contract.info.title} ${contract.info.version}`,
  '',
  renderPaths(contract.paths ?? {}),
  '',
  renderComponents(contract.components?.schemas ?? {}),
  '',
].join('\n')

const invokedAsScript =
  process.argv[1] !== undefined && resolve(process.argv[1]) === fileURLToPath(import.meta.url)

if (invokedAsScript) {
  if (process.argv.includes('--check')) {
    const current = readFileSync(outputUrl, 'utf8')
    if (current !== generated) {
      console.error('Generated OpenAPI declarations are stale. Run npm run api:generate.')
      process.exitCode = 1
    } else {
      console.log('Generated OpenAPI declarations are current.')
    }
  } else {
    writeFileSync(outputUrl, generated, 'utf8')
    console.log(`Generated ${fileURLToPath(outputUrl)}`)
  }
}
