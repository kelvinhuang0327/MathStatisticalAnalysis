import type { LotteryType } from '../api/strategies'

const LOTTERY_TYPE_DISPLAY_LABELS: Record<LotteryType, string> = {
  DAILY_539: 'T539',
  BIG_LOTTO: 'L649',
  POWER_LOTTO: 'P638',
}

export function lotteryTypeDisplayLabel(value: LotteryType): string {
  return LOTTERY_TYPE_DISPLAY_LABELS[value]
}
