export function compareNullableNumbers(a: number | null, b: number | null, direction: number): number {
  const aUnknown = a === null || Number.isNaN(a)
  const bUnknown = b === null || Number.isNaN(b)
  if (aUnknown) return bUnknown ? 0 : 1
  if (bUnknown) return -1
  return (a - b) * direction
}
