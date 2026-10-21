// @vitest-environment jsdom

import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { DrawHistoryResponse } from '../src/api/drawData'
import DrawHistoryPage from '../src/features/draw-history/DrawHistoryPage.vue'

type DrawRecord = DrawHistoryResponse['records'][number]

function drawRecord(
  lotteryType: DrawRecord['lottery_type'],
  drawNumber: string,
  mainNumbers: number[],
  specialNumbers: number[],
): DrawRecord {
  return {
    lottery_type: lotteryType,
    draw_number: drawNumber,
    draw_date: '2026-07-16',
    main_numbers: mainNumbers,
    special_numbers: specialNumbers,
    source_name: 'draws.csv',
    source_reference: 'synthetic-reference',
    ingestion_run_id: '7de87eeb-ecc7-4c03-830a-c0fdb71254e8',
    created_at: '2026-07-16T07:00:00Z',
    updated_at: '2026-07-16T07:00:00Z',
  }
}

const b649Draw = drawRecord('BIG_LOTTO', '0002', [1, 3, 9, 17, 24, 49], [7])
const p638Draw = drawRecord('POWER_LOTTO', '0003', [2, 5, 9, 15, 27, 38], [11])
const t539Draw = drawRecord('DAILY_539', '0004', [3, 8, 13, 28, 35], [])

const emptyPage = {
  records: [],
  page: 1,
  page_size: 25,
  total_count: 0,
  total_pages: 0,
  sort: ['draw_date:desc', 'draw_number:string_desc', 'id:desc'],
} satisfies DrawHistoryResponse

function populatedPage(record: DrawRecord, page = 1): DrawHistoryResponse {
  return {
    ...emptyPage,
    records: [record],
    page,
    total_count: 2,
    total_pages: 2,
  }
}

function recordForType(type: string | null): DrawRecord {
  if (type === 'POWER_LOTTO') return p638Draw
  if (type === 'DAILY_539') return t539Draw
  return b649Draw
}

let fetchMock: ReturnType<typeof vi.fn<typeof fetch>>

function apiResponse(payload: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: vi.fn().mockResolvedValue(payload),
  } as unknown as Response
}

function requestUrl(index: number): URL {
  return new URL(String(fetchMock.mock.calls[index]?.[0]), 'http://localhost')
}

beforeEach(() => {
  fetchMock = vi.fn<typeof fetch>()
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('DrawHistoryPage', () => {
  it('shows loading and genuine empty states, and aborts a request on unmount', async () => {
    let pendingSignal: AbortSignal | undefined
    fetchMock.mockImplementation((_input, init) => {
      pendingSignal = init?.signal ?? undefined
      return new Promise<Response>(() => undefined)
    })
    const loading = mount(DrawHistoryPage)
    await flushPromises()

    expect(loading.text()).toContain('Loading draw history…')
    expect(requestUrl(0).searchParams.get('lottery_type')).toBe('BIG_LOTTO')
    loading.unmount()
    expect(pendingSignal?.aborted).toBe(true)

    fetchMock.mockResolvedValue(apiResponse(emptyPage))
    const empty = mount(DrawHistoryPage)
    await flushPromises()
    expect(empty.text()).toContain('No draws match this query')
    expect(empty.get('.scope-card strong').text()).toBe('0')
    empty.unmount()
  })

  it('keeps B649 as the default and renders its string identity and metadata', async () => {
    fetchMock.mockResolvedValue(apiResponse(populatedPage(b649Draw)))
    const wrapper = mount(DrawHistoryPage)
    await flushPromises()

    const lotterySelect = wrapper.get('select[name="lottery-type"]')
    expect((lotterySelect.element as HTMLSelectElement).value).toBe('BIG_LOTTO')
    expect(requestUrl(0).searchParams.get('lottery_type')).toBe('BIG_LOTTO')
    expect(wrapper.get('code.draw-identity').text()).toBe('0002')
    expect(wrapper.get('tbody tr').text()).toContain('2026-07-16')
    expect(wrapper.get('tbody tr').text()).toContain('draws.csv')
    expect(wrapper.get('tbody tr').text()).toContain('synthetic-reference')
    expect(wrapper.text()).toContain(b649Draw.ingestion_run_id)
    expect(wrapper.text()).toContain('B649')
    expect(wrapper.text()).not.toContain('BIG_LOTTO')
    expect(wrapper.findAll('.ball--main')).toHaveLength(6)
    expect(wrapper.findAll('.ball--special')).toHaveLength(1)
    expect(wrapper.get('.ball--special').attributes('aria-label')).toBe('Special number 7')
    expect(wrapper.text()).toContain('draw_date:desc · draw_number:string_desc · id:desc')
    wrapper.unmount()
  })

  it('sends filters and pagination, then resets the query without changing B649', async () => {
    fetchMock.mockResolvedValue(apiResponse(populatedPage(b649Draw)))
    const wrapper = mount(DrawHistoryPage)
    await flushPromises()

    await wrapper.get('input[name="draw-number"]').setValue('000')
    await wrapper.get('input[name="date-from"]').setValue('2026-07-01')
    await wrapper.get('input[name="date-to"]').setValue('2026-07-16')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    const filtered = requestUrl(1)
    expect(filtered.searchParams.get('lottery_type')).toBe('BIG_LOTTO')
    expect(filtered.searchParams.get('draw_number')).toBe('000')
    expect(filtered.searchParams.get('date_from')).toBe('2026-07-01')
    expect(filtered.searchParams.get('date_to')).toBe('2026-07-16')
    expect(filtered.searchParams.get('page')).toBe('1')

    const next = wrapper.findAll('button').find((button) => button.text() === 'Next')
    await next?.trigger('click')
    await flushPromises()
    expect(requestUrl(2).searchParams.get('page')).toBe('2')

    await wrapper.get('select[name="page-size"]').setValue('100')
    await flushPromises()
    expect(requestUrl(3).searchParams.get('page_size')).toBe('100')
    expect(requestUrl(3).searchParams.get('page')).toBe('1')

    const reset = wrapper.findAll('button').find((button) => button.text() === 'Reset query')
    await reset?.trigger('click')
    await flushPromises()
    const resetUrl = requestUrl(4)
    expect(resetUrl.searchParams.get('lottery_type')).toBe('BIG_LOTTO')
    expect(resetUrl.searchParams.has('draw_number')).toBe(false)
    expect(resetUrl.searchParams.has('date_from')).toBe(false)
    expect(resetUrl.searchParams.has('date_to')).toBe(false)
    expect(resetUrl.searchParams.get('page_size')).toBe('25')
    expect(resetUrl.searchParams.get('page')).toBe('1')
    wrapper.unmount()
  })

  it('resets page and draw number on game change while retaining valid dates', async () => {
    fetchMock.mockImplementation((input) => {
      const url = new URL(String(input), 'http://localhost')
      return Promise.resolve(apiResponse(populatedPage(recordForType(url.searchParams.get('lottery_type')))))
    })
    const wrapper = mount(DrawHistoryPage)
    await flushPromises()

    await wrapper.findAll('button').find((button) => button.text() === 'Next')?.trigger('click')
    await flushPromises()
    expect(requestUrl(1).searchParams.get('page')).toBe('2')

    await wrapper.get('input[name="draw-number"]').setValue('000')
    await wrapper.get('input[name="date-from"]').setValue('2026-07-01')
    await wrapper.get('input[name="date-to"]').setValue('2026-07-16')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(requestUrl(2).searchParams.get('page')).toBe('1')

    await wrapper.findAll('button').find((button) => button.text() === 'Next')?.trigger('click')
    await flushPromises()
    expect(requestUrl(3).searchParams.get('page')).toBe('2')

    await wrapper.get('select[name="lottery-type"]').setValue('POWER_LOTTO')
    await flushPromises()
    const switched = requestUrl(4)
    expect(switched.searchParams.get('lottery_type')).toBe('POWER_LOTTO')
    expect(switched.searchParams.get('page')).toBe('1')
    expect(switched.searchParams.has('draw_number')).toBe(false)
    expect(switched.searchParams.get('date_from')).toBe('2026-07-01')
    expect(switched.searchParams.get('date_to')).toBe('2026-07-16')
    expect((wrapper.get('input[name="date-from"]').element as HTMLInputElement).value).toBe('2026-07-01')
    expect((wrapper.get('input[name="date-to"]').element as HTMLInputElement).value).toBe('2026-07-16')

    await wrapper.findAll('button').find((button) => button.text() === 'Reset query')?.trigger('click')
    await flushPromises()
    const reset = requestUrl(5)
    expect(reset.searchParams.get('lottery_type')).toBe('POWER_LOTTO')
    expect(reset.searchParams.has('draw_number')).toBe(false)
    expect(reset.searchParams.has('date_from')).toBe(false)
    expect(reset.searchParams.has('date_to')).toBe(false)
    wrapper.unmount()
  })

  it('maps all three enums and renders P638 and T539 number regions correctly', async () => {
    fetchMock.mockImplementation((input) => {
      const url = new URL(String(input), 'http://localhost')
      return Promise.resolve(apiResponse(populatedPage(recordForType(url.searchParams.get('lottery_type')))))
    })
    const wrapper = mount(DrawHistoryPage)
    await flushPromises()
    expect(requestUrl(0).searchParams.get('lottery_type')).toBe('BIG_LOTTO')

    await wrapper.get('select[name="lottery-type"]').setValue('POWER_LOTTO')
    await flushPromises()
    expect(requestUrl(1).searchParams.get('lottery_type')).toBe('POWER_LOTTO')
    expect(wrapper.findAll('th').map((cell) => cell.text())).toContain('First zone')
    expect(wrapper.findAll('th').map((cell) => cell.text())).toContain('Second zone')
    expect(wrapper.findAll('.ball--main')).toHaveLength(6)
    expect(wrapper.findAll('.ball--special')).toHaveLength(1)
    expect(wrapper.get('.ball--main').attributes('aria-label')).toBe('First zone number 2')
    expect(wrapper.get('.ball--special').attributes('aria-label')).toBe('Second zone number 11')
    expect(wrapper.get('code.draw-identity').text()).toBe('0003')

    await wrapper.get('select[name="lottery-type"]').setValue('DAILY_539')
    await flushPromises()
    expect(requestUrl(2).searchParams.get('lottery_type')).toBe('DAILY_539')
    expect(wrapper.findAll('th').map((cell) => cell.text())).toContain('No secondary number')
    expect(wrapper.findAll('.ball--main')).toHaveLength(5)
    expect(wrapper.findAll('.ball--special')).toHaveLength(0)
    expect(wrapper.get('tbody tr').text()).toContain('0004')
    expect(wrapper.get('tbody tr').text()).toContain('—')
    wrapper.unmount()
  })

  it('does not display a response belonging to another lottery type', async () => {
    fetchMock.mockResolvedValue(apiResponse(populatedPage(b649Draw)))
    const wrapper = mount(DrawHistoryPage)
    await flushPromises()

    await wrapper.get('select[name="lottery-type"]').setValue('POWER_LOTTO')
    await flushPromises()

    expect(wrapper.text()).toContain('Draw History returned records for a different lottery type.')
    expect(wrapper.find('table').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('0002')
    wrapper.unmount()
  })

  it('ignores a late response after switching games even when fetch ignores abort', async () => {
    const pending = new Map<string, { resolve: (response: Response) => void; signal?: AbortSignal }>()
    fetchMock.mockImplementation((input, init) => {
      const type = new URL(String(input), 'http://localhost').searchParams.get('lottery_type') ?? ''
      return new Promise<Response>((resolve) => {
        pending.set(type, { resolve, signal: init?.signal ?? undefined })
      })
    })
    const wrapper = mount(DrawHistoryPage)
    await flushPromises()
    await wrapper.get('select[name="lottery-type"]').setValue('POWER_LOTTO')
    await flushPromises()

    expect(pending.get('BIG_LOTTO')?.signal?.aborted).toBe(true)
    pending.get('POWER_LOTTO')?.resolve(apiResponse(populatedPage(p638Draw)))
    await flushPromises()
    expect(wrapper.get('code.draw-identity').text()).toBe('0003')

    pending.get('BIG_LOTTO')?.resolve(apiResponse(populatedPage(b649Draw)))
    await flushPromises()
    expect(wrapper.get('code.draw-identity').text()).toBe('0003')
    expect(wrapper.text()).toContain('P638')
    expect(wrapper.text()).not.toContain('0002')
    wrapper.unmount()
  })

  it('renders API and network failures as unavailable instead of zero results', async () => {
    fetchMock.mockResolvedValue(
      apiResponse(
        { error_code: 'REPOSITORY_UNAVAILABLE', message: 'Local draw data is unavailable.' },
        503,
      ),
    )
    const unavailable = mount(DrawHistoryPage)
    await flushPromises()
    expect(unavailable.text()).toContain('Local draw data is unavailable.')
    expect(unavailable.get('.scope-card strong').text()).toBe('—')
    expect(unavailable.find('table').exists()).toBe(false)
    unavailable.unmount()

    fetchMock.mockRejectedValue(new Error('Network request failed.'))
    const networkError = mount(DrawHistoryPage)
    await flushPromises()
    expect(networkError.text()).toContain('Network request failed.')
    expect(networkError.get('.scope-card strong').text()).toBe('—')
    expect(networkError.text()).not.toContain('Matching draws0')
    expect(networkError.findAll('button').some((button) => button.text() === 'Retry')).toBe(true)
    networkError.unmount()
  })
})
