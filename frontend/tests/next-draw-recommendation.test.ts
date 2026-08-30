// @vitest-environment jsdom

import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type {
  NextDrawRecommendationLifecycleResponse,
  NextDrawRecommendationResponse,
} from '../src/api/nextDrawRecommendation'
import NextDrawRecommendationPage from '../src/features/next-draw-recommendation/NextDrawRecommendationPage.vue'

let fetchMock: ReturnType<typeof vi.fn<typeof fetch>>

function apiResponse(payload: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: vi.fn().mockResolvedValue(payload),
  } as unknown as Response
}

function previewResponse(
  overrides: Partial<NextDrawRecommendationResponse> = {},
): NextDrawRecommendationResponse {
  return {
    ranking_policy_id: 'NEXT_DRAW_ROBUSTNESS_V1',
    recommendation_status: 'PREVIEW',
    target_binding: 'UNBOUND_AS_OF_NOW',
    lottery_type: 'BIG_LOTTO',
    native_ticket_count: 2,
    availability: 'AVAILABLE',
    total_candidate_count: 1,
    ranked: [
      {
        rank: 1,
        strategy_id: 's1',
        strategy_name: 'Strategy One',
        native_ticket_count: 2,
        windows: [],
        cross_window_rank_sum: 3,
        ticket_generation_status: 'OK',
        tickets: [
          [1, 2, 3, 4, 5, 6],
          [7, 8, 9, 10, 11, 12],
        ],
        ticket_generation_detail: '',
      },
    ],
    excluded: [],
    hit_tier_id: 'M3',
    evidence_computation_status: 'FRESH_UNREVIEWED',
    evidence_artifact_sha256: 'e'.repeat(64),
    evidence_last_causal_draw_id: '115000089',
    ...overrides,
  }
}

function lifecycleResponse(
  overrides: Partial<NextDrawRecommendationLifecycleResponse> = {},
): NextDrawRecommendationLifecycleResponse {
  return {
    lifecycle_state: 'WAITING_FOR_ELIGIBLE_TARGET',
    lottery_type: 'BIG_LOTTO',
    ranking_policy_id: 'NEXT_DRAW_ROBUSTNESS_V1',
    target_draw_number: null,
    target_draw_date: null,
    target_scheduled_at: null,
    sealed_at: null,
    source_head: null,
    source_tree: null,
    target_registration_digest: null,
    evidence_artifact_sha256: null,
    sealed_buckets: [],
    ...overrides,
  }
}

function sealedLifecycleResponse(): NextDrawRecommendationLifecycleResponse {
  return lifecycleResponse({
    lifecycle_state: 'PREDICTIONS_SEALED',
    target_draw_number: '115000090',
    target_draw_date: '2099-09-01',
    target_scheduled_at: '2099-09-01T08:30:00Z',
    sealed_at: '2099-08-30T10:00:00Z',
    source_head: '1'.repeat(40),
    source_tree: '2'.repeat(40),
    target_registration_digest: 'd'.repeat(64),
    evidence_artifact_sha256: 'e'.repeat(64),
    sealed_buckets: [
      {
        native_ticket_count: 2,
        availability: 'AVAILABLE',
        total_candidate_count: 1,
        ranked_strategy_ids: ['s1'],
        sealed_tickets: [
          {
            rank: 1,
            strategy_id: 's1',
            strategy_name: 'Strategy One',
            status: 'OK',
            tickets: [[9, 8, 7, 6, 5, 4]],
            detail: '',
          },
        ],
      },
    ],
  })
}

function fetchRouter(byUrl: Record<string, Response>): ReturnType<typeof vi.fn<typeof fetch>> {
  return vi.fn((input: RequestInfo | URL) => {
    const url = String(input)
    for (const [prefix, response] of Object.entries(byUrl)) {
      if (url.startsWith(prefix)) return Promise.resolve(response)
    }
    throw new Error(`unexpected fetch: ${url}`)
  }) as unknown as ReturnType<typeof vi.fn<typeof fetch>>
}

beforeEach(() => {
  fetchMock = vi.fn<typeof fetch>()
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('NextDrawRecommendationPage', () => {
  it('requests both the preview ranking and the lifecycle status on mount', async () => {
    const router = fetchRouter({
      '/api/v1/next-draw-recommendation?': apiResponse(previewResponse()),
      '/api/v1/next-draw-recommendation/lifecycle': apiResponse(lifecycleResponse()),
    })
    vi.stubGlobal('fetch', router)

    const wrapper = mount(NextDrawRecommendationPage)
    await flushPromises()

    const calledUrls = router.mock.calls.map((call) => String(call[0]))
    expect(calledUrls.some((url) => url.startsWith('/api/v1/next-draw-recommendation?'))).toBe(
      true,
    )
    expect(
      calledUrls.some((url) => url === '/api/v1/next-draw-recommendation/lifecycle'),
    ).toBe(true)
    wrapper.unmount()
  })

  it('shows the waiting banner and live preview tickets when no target is sealed', async () => {
    vi.stubGlobal(
      'fetch',
      fetchRouter({
        '/api/v1/next-draw-recommendation?': apiResponse(previewResponse()),
        '/api/v1/next-draw-recommendation/lifecycle': apiResponse(lifecycleResponse()),
      }),
    )

    const wrapper = mount(NextDrawRecommendationPage)
    await flushPromises()

    expect(wrapper.text()).toContain('Waiting for next draw')
    expect(wrapper.text()).toContain('Preview tickets')
    expect(wrapper.text()).not.toContain('Sealed tickets')
    wrapper.unmount()
  })

  it('shows the sealed banner and frozen sealed tickets once predictions are sealed', async () => {
    vi.stubGlobal(
      'fetch',
      fetchRouter({
        '/api/v1/next-draw-recommendation?': apiResponse(previewResponse()),
        '/api/v1/next-draw-recommendation/lifecycle': apiResponse(sealedLifecycleResponse()),
      }),
    )

    const wrapper = mount(NextDrawRecommendationPage)
    await flushPromises()

    const text = wrapper.text()
    expect(text).toContain('Predictions sealed')
    expect(text).toContain('115000090')
    expect(text).toContain('Sealed tickets')
    // The frozen sealed ticket numbers, not the live preview's ticket numbers.
    expect(text).toContain('09')
    expect(text).toContain('08')
    expect(text).not.toContain('Preview tickets')
    wrapper.unmount()
  })

  it('flags a candidate absent from the sealed bucket instead of silently reusing live tickets', async () => {
    const sealed = sealedLifecycleResponse()
    sealed.sealed_buckets[0]!.sealed_tickets = []
    sealed.sealed_buckets[0]!.ranked_strategy_ids = []

    vi.stubGlobal(
      'fetch',
      fetchRouter({
        '/api/v1/next-draw-recommendation?': apiResponse(previewResponse()),
        '/api/v1/next-draw-recommendation/lifecycle': apiResponse(sealed),
      }),
    )

    const wrapper = mount(NextDrawRecommendationPage)
    await flushPromises()

    expect(wrapper.text()).toContain('not among the sealed top candidates')
    wrapper.unmount()
  })

  it('reports outcome-available while still showing the sealed tickets', async () => {
    const sealed = sealedLifecycleResponse()
    sealed.lifecycle_state = 'OUTCOME_AVAILABLE'

    vi.stubGlobal(
      'fetch',
      fetchRouter({
        '/api/v1/next-draw-recommendation?': apiResponse(previewResponse()),
        '/api/v1/next-draw-recommendation/lifecycle': apiResponse(sealed),
      }),
    )

    const wrapper = mount(NextDrawRecommendationPage)
    await flushPromises()

    const text = wrapper.text()
    expect(text).toContain('Outcome available')
    expect(text).toContain('Sealed tickets')
    wrapper.unmount()
  })

  it('does not fail the page when the lifecycle request itself fails', async () => {
    vi.stubGlobal(
      'fetch',
      fetchRouter({
        '/api/v1/next-draw-recommendation?': apiResponse(previewResponse()),
        '/api/v1/next-draw-recommendation/lifecycle': apiResponse(
          { error_code: 'NEXT_DRAW_RECOMMENDATION_LIFECYCLE_UNAVAILABLE', message: 'nope' },
          503,
        ),
      }),
    )

    const wrapper = mount(NextDrawRecommendationPage)
    await flushPromises()

    // The ranking preview must still render even if lifecycle lookup failed.
    expect(wrapper.text()).toContain('Strategy One')
    expect(wrapper.text()).toContain('Preview tickets')
    wrapper.unmount()
  })
})
