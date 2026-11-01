import { describe, expect, it } from 'vitest'

import { REPLAY_OVERVIEW_WINDOWS } from '../src/features/replay-overview/types'

describe('Replay Overview horizon evidence labels', () => {
  it('preserves the existing window keys, labels, draw counts, and other descriptions', () => {
    expect(
      REPLAY_OVERVIEW_WINDOWS.map(({ key, label, shortLabel, draws, description }) => ({
        key,
        label,
        shortLabel,
        draws,
        description,
      })),
    ).toEqual([
      {
        key: 'FULL',
        label: 'Full Horizon · 全部歷史',
        shortLabel: 'FULL',
        draws: null,
        description: 'Full available historical observation window',
      },
      {
        key: 'RECENT_750',
        label: 'Long · 750 期',
        shortLabel: '750',
        draws: 750,
        description:
          'Most recent 750 historical observation draws. This window alone does not establish out-of-sample isolation; OOS claims require a verifiable training cutoff, walk-forward evaluation, or other auditable training/test isolation evidence.',
      },
      {
        key: 'RECENT_300',
        label: 'Medium · 300 期',
        shortLabel: '300',
        draws: 300,
        description: 'Recent 300 historical evaluation draws (intermediate stability window)',
      },
      {
        key: 'RECENT_50',
        label: 'Short · 50 期',
        shortLabel: '50',
        draws: 50,
        description: 'Recent 50 historical evaluation draws (exploratory / low statistical power)',
      },
    ])
  })

  it('describes RECENT_750 as an observed window without claiming completed OOS validation', () => {
    const recent750 = REPLAY_OVERVIEW_WINDOWS.find(({ key }) => key === 'RECENT_750')

    expect(recent750?.description).toContain('Most recent 750 historical observation draws')
    expect(recent750?.description).toContain('This window alone does not establish out-of-sample isolation')
    expect(recent750?.description).toContain('verifiable training cutoff')
    expect(recent750?.description).toContain('walk-forward evaluation')
    expect(recent750?.description).toContain('auditable training/test isolation evidence')
    expect(recent750?.description).not.toMatch(/primary out-of-sample window/i)
  })
})
