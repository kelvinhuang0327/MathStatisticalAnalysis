import { describe, expect, it } from 'vitest'

import { lotteryTypeDisplayLabel } from '../src/utils/lotteryDisplayLabel'

describe('lotteryTypeDisplayLabel', () => {
  it('maps every LotteryType to a screen-safe code', () => {
    expect(lotteryTypeDisplayLabel('DAILY_539')).toBe('T539')
    expect(lotteryTypeDisplayLabel('BIG_LOTTO')).toBe('B649')
    expect(lotteryTypeDisplayLabel('POWER_LOTTO')).toBe('P638')
  })
})
