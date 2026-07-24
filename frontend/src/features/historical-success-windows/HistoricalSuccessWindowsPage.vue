<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import {
  getHistoricalSuccessFeatureCohortDiagnostics,
  getHistoricalSuccessFeatureCohorts,
  getHistoricalSuccessCrossImportConcordance,
  getHistoricalSuccessMultiImportConcordanceCensus,
  getHistoricalSuccessRecent50StabilityAudit,
  getHistoricalSuccessStabilityMatrix,
  getHistoricalSuccessTemporalHoldout,
  getHistoricalSuccessWindows,
  HISTORICAL_SUCCESS_CRITERIA,
  HISTORICAL_SUCCESS_PREFIX_COUNTS,
  HistoricalSuccessWindowsRequestError,
  listHistoricalRuns,
  listHistoricalSuccessWindows,
  type HistoricalRun,
  type HistoricalRunPage,
  type HistoricalSuccessCriterion,
  type HistoricalSuccessFeatureCohortDiagnostics,
  type HistoricalSuccessFeatureCohorts,
  type HistoricalSuccessCrossImportConcordance,
  type HistoricalSuccessMultiImportConcordanceCensus,
  type HistoricalSuccessPrefixCount,
  type HistoricalSuccessRecent50StabilityAudit,
  type HistoricalSuccessStabilityMatrix,
  type HistoricalSuccessTemporalHoldout,
  type HistoricalSuccessWindowPage,
  type HistoricalSuccessWindowResult,
} from '../../api/historicalSuccessWindows'

type RunsState = 'loading' | 'ready' | 'empty' | 'not-configured' | 'unavailable' | 'error'
type AnalysisState =
  | 'idle'
  | 'selected'
  | 'loading'
  | 'ready'
  | 'empty'
  | 'not-found'
  | 'invalid'
  | 'unavailable'
  | 'malformed'
  | 'error'
type DetailState = 'closed' | 'loading' | 'ready' | 'not-found' | 'invalid' | 'unavailable' | 'malformed' | 'error'
type MatrixState = 'idle' | 'selected' | 'loading' | 'ready' | 'partial' | 'error'
type MatrixSelection = HistoricalSuccessWindowResult
type MatrixOutcome = {
  selection: MatrixSelection
  matrix: HistoricalSuccessStabilityMatrix | null
  error: string
}
type MatrixCell = HistoricalSuccessStabilityMatrix['cells'][number]
type FeatureCohortOutcome = {
  selection: MatrixSelection
  result: HistoricalSuccessFeatureCohorts | null
  error: string
}
type FeatureCohort = HistoricalSuccessFeatureCohorts['cohorts'][number]
type FeatureCohortDiagnosticOutcome = {
  selection: MatrixSelection
  result: HistoricalSuccessFeatureCohortDiagnostics | null
  error: string
}
type FeatureCohortDiagnostic =
  HistoricalSuccessFeatureCohortDiagnostics['diagnostics'][number]
type TemporalHoldoutOutcome = {
  selection: MatrixSelection
  result: HistoricalSuccessTemporalHoldout | null
  error: string
}
type TemporalHoldoutComparison =
  HistoricalSuccessTemporalHoldout['comparisons'][number]
type Recent50StabilityAuditOutcome = {
  selection: MatrixSelection
  result: HistoricalSuccessRecent50StabilityAudit | null
  error: string
}
type Recent50StabilityAuditComparison =
  HistoricalSuccessRecent50StabilityAudit['comparisons'][number]
type CrossImportConcordanceOutcome = {
  selection: MatrixSelection
  result: HistoricalSuccessCrossImportConcordance | null
  error: string
}
type CrossImportConcordanceComparison =
  HistoricalSuccessCrossImportConcordance['comparisons'][number]
type MultiImportConcordanceCensusOutcome = {
  selection: MatrixSelection
  result: HistoricalSuccessMultiImportConcordanceCensus | null
  error: string
}

const RUN_LIMIT = 10
const RESULT_LIMIT = 20

const runsState = ref<RunsState>('loading')
const runsPage = ref<HistoricalRunPage | null>(null)
const runsError = ref('')
const selectedImportIdentity = ref('')
const selectedRun = ref<HistoricalRun | null>(null)
const comparisonImportIdentity = ref('')
const comparisonRun = ref<HistoricalRun | null>(null)
const prefixCount = ref<HistoricalSuccessPrefixCount>(1)
const criterion = ref<HistoricalSuccessCriterion>('M3_PLUS')
const analysisState = ref<AnalysisState>('idle')
const resultPage = ref<HistoricalSuccessWindowPage | null>(null)
const analysisError = ref('')
const detailState = ref<DetailState>('closed')
const detail = ref<HistoricalSuccessWindowResult | null>(null)
const detailError = ref('')
const copiedIdentity = ref(false)
const matrixSelections = ref<MatrixSelection[]>([])
const matrixState = ref<MatrixState>('idle')
const matrixResults = ref<MatrixOutcome[]>([])
const featureCohortState = ref<MatrixState>('idle')
const featureCohortResults = ref<FeatureCohortOutcome[]>([])
const featureCohortDiagnosticsState = ref<MatrixState>('idle')
const featureCohortDiagnosticsResults = ref<FeatureCohortDiagnosticOutcome[]>([])
const temporalHoldoutState = ref<MatrixState>('idle')
const temporalHoldoutResults = ref<TemporalHoldoutOutcome[]>([])
const recent50StabilityAuditState = ref<MatrixState>('idle')
const recent50StabilityAuditResults = ref<Recent50StabilityAuditOutcome[]>([])
const crossImportConcordanceState = ref<MatrixState>('idle')
const crossImportConcordanceResults = ref<CrossImportConcordanceOutcome[]>([])
const censusImportSelections = ref<HistoricalRun[]>([])
const multiImportCensusState = ref<MatrixState>('idle')
const multiImportCensusResults = ref<MultiImportConcordanceCensusOutcome[]>([])

let mounted = false
let runsGeneration = 0
let analysisGeneration = 0
let detailGeneration = 0
let matrixGeneration = 0
let featureCohortGeneration = 0
let featureCohortDiagnosticsGeneration = 0
let temporalHoldoutGeneration = 0
let recent50StabilityAuditGeneration = 0
let crossImportConcordanceGeneration = 0
let multiImportCensusGeneration = 0
let runsController: AbortController | undefined
let analysisController: AbortController | undefined
let detailController: AbortController | undefined
let matrixController: AbortController | undefined
let featureCohortController: AbortController | undefined
let featureCohortDiagnosticsController: AbortController | undefined
let temporalHoldoutController: AbortController | undefined
let recent50StabilityAuditController: AbortController | undefined
let crossImportConcordanceController: AbortController | undefined
let multiImportCensusController: AbortController | undefined

const selectedRunMissingFromPage = computed(
  () =>
    selectedRun.value !== null &&
    !runsPage.value?.items.some(
      (run) => run.import_identity_sha256 === selectedRun.value?.import_identity_sha256,
    ),
)
const comparisonRunMissingFromPage = computed(
  () =>
    comparisonRun.value !== null &&
    !runsPage.value?.items.some(
      (run) => run.import_identity_sha256 === comparisonRun.value?.import_identity_sha256,
    ),
)
const distinctComparisonRuns = computed(
  () =>
    selectedRun.value !== null &&
    comparisonRun.value !== null &&
    selectedRun.value.import_identity_sha256 !==
      comparisonRun.value.import_identity_sha256,
)
const canRunPrevious = computed(() => (runsPage.value?.offset ?? 0) > 0)
const canRunNext = computed(() => {
  const page = runsPage.value
  return page !== null && page.offset + page.items.length < page.total_count
})
const canResultPrevious = computed(() => (resultPage.value?.offset ?? 0) > 0)
const canResultNext = computed(() => {
  const page = resultPage.value
  return page !== null && page.offset + page.items.length < page.total_count
})
const matrixSelectionLimitReached = computed(() => matrixSelections.value.length >= 4)
const censusImportSelectionLimitReached = computed(
  () => censusImportSelections.value.length >= 4,
)

function errorMessage(error: unknown): string {
  return error instanceof HistoricalSuccessWindowsRequestError
    ? error.message
    : 'The historical research request failed.'
}

function analysisErrorState(error: unknown): AnalysisState {
  if (!(error instanceof HistoricalSuccessWindowsRequestError)) return 'error'
  if (error.kind === 'NOT_FOUND') return 'not-found'
  if (error.kind === 'INVALID_REQUEST') return 'invalid'
  if (error.kind === 'MALFORMED_RESPONSE') return 'malformed'
  return 'unavailable'
}

function detailErrorState(error: unknown): DetailState {
  const mapped = analysisErrorState(error)
  if (mapped === 'not-found' || mapped === 'invalid' || mapped === 'unavailable' || mapped === 'malformed') {
    return mapped
  }
  return 'error'
}

async function loadRuns(offset = 0): Promise<void> {
  clearRecent50StabilityAudit()
  const generation = ++runsGeneration
  runsController?.abort()
  const controller = new AbortController()
  runsController = controller
  runsState.value = 'loading'
  runsError.value = ''
  try {
    const page = await listHistoricalRuns({ limit: RUN_LIMIT, offset }, controller.signal)
    if (!mounted || generation !== runsGeneration || controller.signal.aborted) return
    runsPage.value = page
    runsState.value = page.total_count === 0 ? 'empty' : 'ready'
  } catch (error: unknown) {
    if (!mounted || generation !== runsGeneration || controller.signal.aborted) return
    runsPage.value = null
    runsError.value = errorMessage(error)
    if (
      error instanceof HistoricalSuccessWindowsRequestError &&
      error.kind === 'NOT_CONFIGURED'
    ) {
      runsState.value = 'not-configured'
    } else if (
      error instanceof HistoricalSuccessWindowsRequestError &&
      (error.kind === 'UNAVAILABLE' || error.kind === 'MALFORMED_RESPONSE')
    ) {
      runsState.value = 'unavailable'
    } else {
      runsState.value = 'error'
    }
  }
}

function clearAnalysis(): void {
  analysisGeneration += 1
  analysisController?.abort()
  detailGeneration += 1
  detailController?.abort()
  resultPage.value = null
  detail.value = null
  detailState.value = 'closed'
  analysisError.value = ''
  detailError.value = ''
  analysisState.value = selectedRun.value === null ? 'idle' : 'selected'
}

function matrixIdentity(item: MatrixSelection): string {
  return [
    item.strategy.strategy_id,
    item.strategy.strategy_version,
    String(item.strategy.replicate),
  ].join('\u0000')
}

function isMatrixSelected(item: MatrixSelection): boolean {
  const identity = matrixIdentity(item)
  return matrixSelections.value.some((selected) => matrixIdentity(selected) === identity)
}

function clearMatrix(clearSelections: boolean): void {
  matrixGeneration += 1
  matrixController?.abort()
  matrixResults.value = []
  if (clearSelections) matrixSelections.value = []
  matrixState.value =
    !clearSelections && matrixSelections.value.length > 0 ? 'selected' : 'idle'
}

function clearFeatureCohorts(): void {
  featureCohortGeneration += 1
  featureCohortController?.abort()
  featureCohortResults.value = []
  featureCohortState.value =
    matrixSelections.value.length > 0 ? 'selected' : 'idle'
}

function clearFeatureCohortDiagnostics(): void {
  featureCohortDiagnosticsGeneration += 1
  featureCohortDiagnosticsController?.abort()
  featureCohortDiagnosticsResults.value = []
  featureCohortDiagnosticsState.value =
    matrixSelections.value.length > 0 ? 'selected' : 'idle'
}

function clearTemporalHoldout(): void {
  temporalHoldoutGeneration += 1
  temporalHoldoutController?.abort()
  temporalHoldoutResults.value = []
  temporalHoldoutState.value =
    matrixSelections.value.length > 0 ? 'selected' : 'idle'
}

function clearRecent50StabilityAudit(): void {
  recent50StabilityAuditGeneration += 1
  recent50StabilityAuditController?.abort()
  recent50StabilityAuditResults.value = []
  recent50StabilityAuditState.value =
    matrixSelections.value.length > 0 ? 'selected' : 'idle'
}

function clearCrossImportConcordance(): void {
  crossImportConcordanceGeneration += 1
  crossImportConcordanceController?.abort()
  crossImportConcordanceResults.value = []
  crossImportConcordanceState.value =
    matrixSelections.value.length > 0 ? 'selected' : 'idle'
}

function clearMultiImportCensus(): void {
  multiImportCensusGeneration += 1
  multiImportCensusController?.abort()
  multiImportCensusResults.value = []
  multiImportCensusState.value =
    censusImportSelections.value.length >= 2 &&
    matrixSelections.value.length > 0
      ? 'selected'
      : 'idle'
}

function isCensusImportSelected(run: HistoricalRun): boolean {
  return censusImportSelections.value.some(
    (selected) =>
      selected.import_identity_sha256 === run.import_identity_sha256,
  )
}

function toggleCensusImportSelection(run: HistoricalRun, event: Event): void {
  const checked = (event.target as HTMLInputElement).checked
  if (checked) {
    if (
      censusImportSelections.value.length >= 4 ||
      isCensusImportSelected(run)
    ) {
      ;(event.target as HTMLInputElement).checked =
        isCensusImportSelected(run)
      return
    }
    censusImportSelections.value = [...censusImportSelections.value, run]
  } else {
    censusImportSelections.value = censusImportSelections.value.filter(
      (selected) =>
        selected.import_identity_sha256 !== run.import_identity_sha256,
    )
  }
  clearMultiImportCensus()
}

function removeCensusImport(run: HistoricalRun): void {
  censusImportSelections.value = censusImportSelections.value.filter(
    (selected) =>
      selected.import_identity_sha256 !== run.import_identity_sha256,
  )
  clearMultiImportCensus()
}

function toggleMatrixSelection(item: MatrixSelection, event: Event): void {
  const checked = (event.target as HTMLInputElement).checked
  const identity = matrixIdentity(item)
  if (checked) {
    if (
      matrixSelections.value.length >= 4 ||
      matrixSelections.value.some((selected) => matrixIdentity(selected) === identity)
    ) {
      ;(event.target as HTMLInputElement).checked = isMatrixSelected(item)
      return
    }
    matrixSelections.value = [...matrixSelections.value, item]
  } else {
    matrixSelections.value = matrixSelections.value.filter(
      (selected) => matrixIdentity(selected) !== identity,
    )
  }
  clearMatrix(false)
  clearFeatureCohorts()
  clearFeatureCohortDiagnostics()
  clearTemporalHoldout()
  clearRecent50StabilityAudit()
  clearCrossImportConcordance()
  clearMultiImportCensus()
}

function chooseRun(): void {
  const selected = runsPage.value?.items.find(
    (run) => run.import_identity_sha256 === selectedImportIdentity.value,
  )
  if (selected !== undefined) selectedRun.value = selected
  if (selectedImportIdentity.value === '') selectedRun.value = null
  copiedIdentity.value = false
  clearAnalysis()
  clearMatrix(true)
  clearFeatureCohorts()
  clearFeatureCohortDiagnostics()
  clearTemporalHoldout()
  clearRecent50StabilityAudit()
  clearCrossImportConcordance()
  clearMultiImportCensus()
}

function chooseComparisonRun(): void {
  const selected = runsPage.value?.items.find(
    (run) => run.import_identity_sha256 === comparisonImportIdentity.value,
  )
  if (selected !== undefined) comparisonRun.value = selected
  if (comparisonImportIdentity.value === '') comparisonRun.value = null
  clearCrossImportConcordance()
}

function controlsChanged(): void {
  clearAnalysis()
  clearFeatureCohorts()
  clearFeatureCohortDiagnostics()
  clearTemporalHoldout()
  clearRecent50StabilityAudit()
  clearCrossImportConcordance()
  clearMultiImportCensus()
}

async function compareSelectedMatrices(): Promise<void> {
  clearRecent50StabilityAudit()
  const run = selectedRun.value
  const selections = [...matrixSelections.value]
  if (run === null || selections.length < 1 || selections.length > 4) return
  const generation = ++matrixGeneration
  matrixController?.abort()
  const controller = new AbortController()
  matrixController = controller
  matrixResults.value = []
  matrixState.value = 'loading'
  const outcomes = await Promise.all(
    selections.map(async (selection): Promise<MatrixOutcome> => {
      try {
        const matrix = await getHistoricalSuccessStabilityMatrix(
          {
            import_identity_sha256: run.import_identity_sha256,
            strategy_id: selection.strategy.strategy_id,
            strategy_version: selection.strategy.strategy_version,
            replicate: selection.strategy.replicate,
          },
          controller.signal,
        )
        return { selection, matrix, error: '' }
      } catch (error: unknown) {
        return { selection, matrix: null, error: errorMessage(error) }
      }
    }),
  )
  if (!mounted || generation !== matrixGeneration || controller.signal.aborted) return
  matrixResults.value = outcomes
  const successes = outcomes.filter((outcome) => outcome.matrix !== null).length
  matrixState.value =
    successes === outcomes.length ? 'ready' : successes > 0 ? 'partial' : 'error'
}

async function evaluateSelectedFeatureCohorts(): Promise<void> {
  clearRecent50StabilityAudit()
  const run = selectedRun.value
  const selections = [...matrixSelections.value]
  if (run === null || selections.length < 1 || selections.length > 4) return
  const selectedPrefix = prefixCount.value
  const selectedCriterion = criterion.value
  const generation = ++featureCohortGeneration
  featureCohortController?.abort()
  const controller = new AbortController()
  featureCohortController = controller
  featureCohortResults.value = []
  featureCohortState.value = 'loading'
  const outcomes = await Promise.all(
    selections.map(async (selection): Promise<FeatureCohortOutcome> => {
      try {
        const result = await getHistoricalSuccessFeatureCohorts(
          {
            import_identity_sha256: run.import_identity_sha256,
            strategy_id: selection.strategy.strategy_id,
            strategy_version: selection.strategy.strategy_version,
            replicate: selection.strategy.replicate,
            prefix_count: selectedPrefix,
            criterion: selectedCriterion,
          },
          controller.signal,
        )
        return { selection, result, error: '' }
      } catch (error: unknown) {
        return { selection, result: null, error: errorMessage(error) }
      }
    }),
  )
  if (
    !mounted ||
    generation !== featureCohortGeneration ||
    controller.signal.aborted
  ) {
    return
  }
  featureCohortResults.value = outcomes
  const successes = outcomes.filter((outcome) => outcome.result !== null).length
  featureCohortState.value =
    successes === outcomes.length ? 'ready' : successes > 0 ? 'partial' : 'error'
}

async function evaluateSelectedFeatureCohortDiagnostics(): Promise<void> {
  clearRecent50StabilityAudit()
  const run = selectedRun.value
  const selections = [...matrixSelections.value]
  if (run === null || selections.length < 1 || selections.length > 4) return
  const selectedPrefix = prefixCount.value
  const selectedCriterion = criterion.value
  const generation = ++featureCohortDiagnosticsGeneration
  featureCohortDiagnosticsController?.abort()
  const controller = new AbortController()
  featureCohortDiagnosticsController = controller
  featureCohortDiagnosticsResults.value = []
  featureCohortDiagnosticsState.value = 'loading'
  const outcomes = await Promise.all(
    selections.map(async (selection): Promise<FeatureCohortDiagnosticOutcome> => {
      try {
        const result = await getHistoricalSuccessFeatureCohortDiagnostics(
          {
            import_identity_sha256: run.import_identity_sha256,
            strategy_id: selection.strategy.strategy_id,
            strategy_version: selection.strategy.strategy_version,
            replicate: selection.strategy.replicate,
            prefix_count: selectedPrefix,
            criterion: selectedCriterion,
          },
          controller.signal,
        )
        return { selection, result, error: '' }
      } catch (error: unknown) {
        return { selection, result: null, error: errorMessage(error) }
      }
    }),
  )
  if (
    !mounted ||
    generation !== featureCohortDiagnosticsGeneration ||
    controller.signal.aborted
  ) {
    return
  }
  featureCohortDiagnosticsResults.value = outcomes
  const successes = outcomes.filter((outcome) => outcome.result !== null).length
  featureCohortDiagnosticsState.value =
    successes === outcomes.length ? 'ready' : successes > 0 ? 'partial' : 'error'
}

async function evaluateSelectedTemporalHoldout(): Promise<void> {
  clearRecent50StabilityAudit()
  const run = selectedRun.value
  const selections = [...matrixSelections.value]
  if (run === null || selections.length < 1 || selections.length > 4) return
  const selectedPrefix = prefixCount.value
  const selectedCriterion = criterion.value
  const generation = ++temporalHoldoutGeneration
  temporalHoldoutController?.abort()
  const controller = new AbortController()
  temporalHoldoutController = controller
  temporalHoldoutResults.value = []
  temporalHoldoutState.value = 'loading'
  const outcomes = await Promise.all(
    selections.map(async (selection): Promise<TemporalHoldoutOutcome> => {
      try {
        const result = await getHistoricalSuccessTemporalHoldout(
          {
            import_identity_sha256: run.import_identity_sha256,
            strategy_id: selection.strategy.strategy_id,
            strategy_version: selection.strategy.strategy_version,
            replicate: selection.strategy.replicate,
            prefix_count: selectedPrefix,
            criterion: selectedCriterion,
          },
          controller.signal,
        )
        return { selection, result, error: '' }
      } catch (error: unknown) {
        return { selection, result: null, error: errorMessage(error) }
      }
    }),
  )
  if (
    !mounted ||
    generation !== temporalHoldoutGeneration ||
    controller.signal.aborted
  ) {
    return
  }
  temporalHoldoutResults.value = outcomes
  const successes = outcomes.filter((outcome) => outcome.result !== null).length
  temporalHoldoutState.value =
    successes === outcomes.length ? 'ready' : successes > 0 ? 'partial' : 'error'
}

async function evaluateRecent50StabilityAudit(): Promise<void> {
  const run = selectedRun.value
  const selections = [...matrixSelections.value]
  if (run === null || selections.length < 1 || selections.length > 4) return
  const selectedPrefix = prefixCount.value
  const selectedCriterion = criterion.value
  const generation = ++recent50StabilityAuditGeneration
  recent50StabilityAuditController?.abort()
  const controller = new AbortController()
  recent50StabilityAuditController = controller
  recent50StabilityAuditResults.value = []
  recent50StabilityAuditState.value = 'loading'
  const outcomes = await Promise.all(
    selections.map(async (selection): Promise<Recent50StabilityAuditOutcome> => {
      try {
        const result = await getHistoricalSuccessRecent50StabilityAudit(
          {
            import_identity_sha256: run.import_identity_sha256,
            strategy_id: selection.strategy.strategy_id,
            strategy_version: selection.strategy.strategy_version,
            replicate: selection.strategy.replicate,
            prefix_count: selectedPrefix,
            criterion: selectedCriterion,
          },
          controller.signal,
        )
        return { selection, result, error: '' }
      } catch (error: unknown) {
        return { selection, result: null, error: errorMessage(error) }
      }
    }),
  )
  if (
    !mounted ||
    generation !== recent50StabilityAuditGeneration ||
    controller.signal.aborted
  ) {
    return
  }
  recent50StabilityAuditResults.value = outcomes
  const successes = outcomes.filter((outcome) => outcome.result !== null).length
  recent50StabilityAuditState.value =
    successes === outcomes.length ? 'ready' : successes > 0 ? 'partial' : 'error'
}

async function evaluateCrossImportConcordance(): Promise<void> {
  clearRecent50StabilityAudit()
  const leftRun = selectedRun.value
  const rightRun = comparisonRun.value
  const selections = [...matrixSelections.value]
  if (
    leftRun === null ||
    rightRun === null ||
    leftRun.import_identity_sha256 === rightRun.import_identity_sha256 ||
    selections.length < 1 ||
    selections.length > 4
  ) {
    return
  }
  const selectedPrefix = prefixCount.value
  const selectedCriterion = criterion.value
  const generation = ++crossImportConcordanceGeneration
  crossImportConcordanceController?.abort()
  const controller = new AbortController()
  crossImportConcordanceController = controller
  crossImportConcordanceResults.value = []
  crossImportConcordanceState.value = 'loading'
  const outcomes = await Promise.all(
    selections.map(async (selection): Promise<CrossImportConcordanceOutcome> => {
      try {
        const result = await getHistoricalSuccessCrossImportConcordance(
          {
            left_import_identity_sha256: leftRun.import_identity_sha256,
            right_import_identity_sha256: rightRun.import_identity_sha256,
            strategy_id: selection.strategy.strategy_id,
            strategy_version: selection.strategy.strategy_version,
            replicate: selection.strategy.replicate,
            prefix_count: selectedPrefix,
            criterion: selectedCriterion,
          },
          controller.signal,
        )
        return { selection, result, error: '' }
      } catch (error: unknown) {
        return { selection, result: null, error: errorMessage(error) }
      }
    }),
  )
  if (
    !mounted ||
    generation !== crossImportConcordanceGeneration ||
    controller.signal.aborted
  ) {
    return
  }
  crossImportConcordanceResults.value = outcomes
  const successes = outcomes.filter((outcome) => outcome.result !== null).length
  crossImportConcordanceState.value =
    successes === outcomes.length ? 'ready' : successes > 0 ? 'partial' : 'error'
}

async function evaluateMultiImportCensus(): Promise<void> {
  clearRecent50StabilityAudit()
  const imports = [...censusImportSelections.value]
  const selections = [...matrixSelections.value]
  if (
    imports.length < 2 ||
    imports.length > 4 ||
    selections.length < 1 ||
    selections.length > 4
  ) {
    return
  }
  const importIdentities = imports.map(
    (run) => run.import_identity_sha256,
  )
  const selectedPrefix = prefixCount.value
  const selectedCriterion = criterion.value
  const generation = ++multiImportCensusGeneration
  multiImportCensusController?.abort()
  const controller = new AbortController()
  multiImportCensusController = controller
  multiImportCensusResults.value = []
  multiImportCensusState.value = 'loading'
  const outcomes = await Promise.all(
    selections.map(
      async (
        selection,
      ): Promise<MultiImportConcordanceCensusOutcome> => {
        try {
          const result =
            await getHistoricalSuccessMultiImportConcordanceCensus(
              {
                import_identity_sha256: importIdentities,
                strategy_id: selection.strategy.strategy_id,
                strategy_version: selection.strategy.strategy_version,
                replicate: selection.strategy.replicate,
                prefix_count: selectedPrefix,
                criterion: selectedCriterion,
              },
              controller.signal,
            )
          return { selection, result, error: '' }
        } catch (error: unknown) {
          return {
            selection,
            result: null,
            error: errorMessage(error),
          }
        }
      },
    ),
  )
  if (
    !mounted ||
    generation !== multiImportCensusGeneration ||
    controller.signal.aborted
  ) {
    return
  }
  multiImportCensusResults.value = outcomes
  const successes = outcomes.filter(
    (outcome) => outcome.result !== null,
  ).length
  multiImportCensusState.value =
    successes === outcomes.length
      ? 'ready'
      : successes > 0
        ? 'partial'
        : 'error'
}

async function loadResults(offset: number): Promise<void> {
  clearRecent50StabilityAudit()
  const run = selectedRun.value
  if (run === null) return
  const selectedPrefix = prefixCount.value
  const selectedCriterion = criterion.value
  const generation = ++analysisGeneration
  analysisController?.abort()
  detailGeneration += 1
  detailController?.abort()
  detail.value = null
  detailState.value = 'closed'
  const controller = new AbortController()
  analysisController = controller
  resultPage.value = null
  analysisState.value = 'loading'
  analysisError.value = ''
  try {
    const page = await listHistoricalSuccessWindows(
      {
        import_identity_sha256: run.import_identity_sha256,
        prefix_count: selectedPrefix,
        criterion: selectedCriterion,
        limit: RESULT_LIMIT,
        offset,
      },
      controller.signal,
    )
    if (!mounted || generation !== analysisGeneration || controller.signal.aborted) return
    resultPage.value = page
    analysisState.value = page.total_count === 0 ? 'empty' : 'ready'
  } catch (error: unknown) {
    if (!mounted || generation !== analysisGeneration || controller.signal.aborted) return
    analysisError.value = errorMessage(error)
    analysisState.value = analysisErrorState(error)
  }
}

async function inspectStrategy(item: HistoricalSuccessWindowResult): Promise<void> {
  clearRecent50StabilityAudit()
  const run = selectedRun.value
  if (run === null) return
  const generation = ++detailGeneration
  detailController?.abort()
  const controller = new AbortController()
  detailController = controller
  detail.value = null
  detailState.value = 'loading'
  detailError.value = ''
  try {
    const response = await getHistoricalSuccessWindows(
      {
        import_identity_sha256: run.import_identity_sha256,
        strategy_id: item.strategy.strategy_id,
        strategy_version: item.strategy.strategy_version,
        replicate: item.strategy.replicate,
        prefix_count: prefixCount.value,
        criterion: criterion.value,
      },
      controller.signal,
    )
    if (!mounted || generation !== detailGeneration || controller.signal.aborted) return
    detail.value = response
    detailState.value = 'ready'
  } catch (error: unknown) {
    if (!mounted || generation !== detailGeneration || controller.signal.aborted) return
    detailError.value = errorMessage(error)
    detailState.value = detailErrorState(error)
  }
}

async function copyImportIdentity(): Promise<void> {
  clearRecent50StabilityAudit()
  const run = selectedRun.value
  if (run === null || navigator.clipboard === undefined) return
  await navigator.clipboard.writeText(run.import_identity_sha256)
  copiedIdentity.value = true
}

function exactRate(item: HistoricalSuccessWindowResult['windows'][number]): string {
  return item.success_rate.available
    ? `${item.success_rate.numerator} / ${item.success_rate.denominator}`
    : 'Unavailable (0 / 0)'
}

function targetLabel(target: HistoricalSuccessWindowResult['windows'][number]['first_target']): string {
  return `${target.draw_date} · #${target.draw_number}`
}

function matrixCell(
  matrix: HistoricalSuccessStabilityMatrix,
  criterionIdentity: HistoricalSuccessCriterion,
  prefix: HistoricalSuccessPrefixCount,
): MatrixCell {
  const criterionIndex = HISTORICAL_SUCCESS_CRITERIA.indexOf(criterionIdentity)
  const prefixIndex = HISTORICAL_SUCCESS_PREFIX_COUNTS.indexOf(prefix)
  return matrix.cells[criterionIndex * HISTORICAL_SUCCESS_PREFIX_COUNTS.length + prefixIndex]!
}

function matrixRate(
  rate: MatrixCell['windows'][number]['success_rate'],
): string {
  return rate.available
    ? `${rate.numerator} / ${rate.denominator}`
    : 'Unavailable (0 / 0)'
}

function matrixDelta(
  comparison: MatrixCell['comparisons'][number],
): string {
  return comparison.delta.available
    ? `${comparison.delta.numerator} / ${comparison.delta.denominator}`
    : 'Unavailable (0 / 0)'
}

function featureCohortKey(cohort: FeatureCohort): string {
  return [
    cohort.feature_key.long_to_medium,
    cohort.feature_key.medium_to_short,
    cohort.feature_key.long_to_short,
  ].join(':')
}

function featureRate(
  rate: HistoricalSuccessFeatureCohorts['baseline']['success_rate'],
): string {
  return rate.available
    ? `${rate.numerator} / ${rate.denominator}`
    : 'Unavailable (0 / 0)'
}

function featureDelta(cohort: FeatureCohort): string {
  return cohort.delta_vs_baseline.available
    ? `${cohort.delta_vs_baseline.numerator} / ${cohort.delta_vs_baseline.denominator}`
    : 'Unavailable (0 / 0)'
}

function optionalTarget(target: FeatureCohort['first_target']): string {
  return target === null ? 'None' : `${target.draw_date} · #${target.draw_number}`
}

function diagnosticKey(diagnostic: FeatureCohortDiagnostic): string {
  return `${diagnostic.cohort_index}:${[
    diagnostic.feature_key.long_to_medium,
    diagnostic.feature_key.medium_to_short,
    diagnostic.feature_key.long_to_short,
  ].join(':')}`
}

function exactProbability(
  probability: FeatureCohortDiagnostic['raw_p_value'],
): string {
  return `${probability.numerator} / ${probability.denominator}`
}

function diagnosticEffect(diagnostic: FeatureCohortDiagnostic): string {
  return diagnostic.risk_difference.available
    ? `${diagnostic.risk_difference.numerator} / ${diagnostic.risk_difference.denominator}`
    : 'Unavailable (0 / 0)'
}

function temporalEffectChange(comparison: TemporalHoldoutComparison): string {
  return comparison.effect_change.available
    ? `${comparison.effect_change.numerator} / ${comparison.effect_change.denominator}`
    : 'Unavailable (0 / 0)'
}

function recent50EffectChange(
  comparison: Recent50StabilityAuditComparison,
): string {
  return comparison.effect_change.available
    ? `${comparison.effect_change.numerator} / ${comparison.effect_change.denominator}`
    : 'Unavailable (0 / 0)'
}

function crossImportEffectChange(
  comparison: CrossImportConcordanceComparison,
): string {
  return comparison.effect_change.available
    ? `${comparison.effect_change.numerator} / ${comparison.effect_change.denominator}`
    : 'Unavailable (0 / 0)'
}

onMounted(() => {
  mounted = true
  void loadRuns()
})
onBeforeUnmount(() => {
  mounted = false
  runsGeneration += 1
  analysisGeneration += 1
  detailGeneration += 1
  matrixGeneration += 1
  featureCohortGeneration += 1
  featureCohortDiagnosticsGeneration += 1
  temporalHoldoutGeneration += 1
  recent50StabilityAuditGeneration += 1
  crossImportConcordanceGeneration += 1
  multiImportCensusGeneration += 1
  runsController?.abort()
  analysisController?.abort()
  detailController?.abort()
  matrixController?.abort()
  featureCohortController?.abort()
  featureCohortDiagnosticsController?.abort()
  temporalHoldoutController?.abort()
  recent50StabilityAuditController?.abort()
  crossImportConcordanceController?.abort()
  multiImportCensusController?.abort()
})
</script>

<template>
  <section class="historical-workspace" aria-labelledby="historical-success-title">
    <header class="historical-heading">
      <div>
        <p class="eyebrow">Persisted evidence · explicit source selection</p>
        <h1 id="historical-success-title">Historical Success Windows</h1>
        <p class="historical-intro">
          Inspect descriptive results from one completed Historical Results import. This workspace
          does not rank, promote, predict, or choose a strategy.
        </p>
      </div>
      <div class="research-guard" aria-label="Research interpretation">
        <span>Interpretation</span>
        <strong>Reference only</strong>
        <small>Exact persisted evidence</small>
      </div>
    </header>

    <section class="research-panel" aria-labelledby="source-selection-title">
      <div class="panel-heading">
        <div>
          <p class="step-label">1 · Source</p>
          <h2 id="source-selection-title">Choose one completed import</h2>
        </div>
        <div v-if="runsPage" class="panel-heading__actions">
          <div class="page-count">
            {{ runsPage.offset + 1 }}–{{ Math.min(runsPage.offset + runsPage.items.length, runsPage.total_count) }}
            of {{ runsPage.total_count }}
          </div>
          <button class="button button--quiet refresh-runs" type="button" @click="loadRuns(runsPage.offset)">
            Refresh runs
          </button>
        </div>
      </div>

      <p v-if="runsState === 'loading'" class="research-state">Loading persisted run metadata…</p>
      <div v-else-if="runsState === 'not-configured'" class="research-state research-state--notice">
        <strong>Historical database configuration required.</strong>
        <span>Set <code>LOTTOLAB_HISTORICAL_RESULTS_DB</code> to one existing database and restart the local runtime.</span>
        <button class="button button--quiet" type="button" @click="loadRuns()">Retry</button>
      </div>
      <div v-else-if="runsState === 'empty'" class="research-state">
        <strong>No completed Historical Results runs are available.</strong>
        <button class="button button--quiet" type="button" @click="loadRuns()">Reload</button>
      </div>
      <div v-else-if="runsState === 'unavailable' || runsState === 'error'" class="research-state research-state--error">
        <strong>{{ runsError }}</strong>
        <button class="button button--quiet" type="button" @click="loadRuns()">Retry</button>
      </div>

      <template v-if="runsState === 'ready' && runsPage">
        <label class="source-selector">
          <span>Primary run — no run is selected automatically</span>
          <select v-model="selectedImportIdentity" name="historical-run" @change="chooseRun">
            <option value="">Select an exact persisted run</option>
            <option
              v-if="selectedRunMissingFromPage && selectedRun"
              :value="selectedRun.import_identity_sha256"
            >
              {{ selectedRun.dataset_identity }} · {{ selectedRun.completed_at }}
            </option>
            <option
              v-for="run in runsPage.items"
              :key="run.import_identity_sha256"
              :value="run.import_identity_sha256"
            >
              {{ run.dataset_identity }} · {{ run.lottery_type }} · {{ run.completed_at }}
            </option>
          </select>
        </label>
        <label class="source-selector comparison-run-selector">
          <span>Comparison run — selected separately and never chosen automatically</span>
          <select
            v-model="comparisonImportIdentity"
            name="comparison-run"
            @change="chooseComparisonRun"
          >
            <option value="">Select a second exact persisted run</option>
            <option
              v-if="comparisonRunMissingFromPage && comparisonRun"
              :value="comparisonRun.import_identity_sha256"
            >
              {{ comparisonRun.dataset_identity }} · {{ comparisonRun.completed_at }}
            </option>
            <option
              v-for="run in runsPage.items"
              :key="`comparison:${run.import_identity_sha256}`"
              :value="run.import_identity_sha256"
            >
              {{ run.dataset_identity }} · {{ run.lottery_type }} · {{ run.completed_at }}
            </option>
          </select>
        </label>
        <p
          v-if="selectedRun && comparisonRun && !distinctComparisonRuns"
          class="research-state research-state--notice identical-run-notice"
        >
          Choose two distinct imports for cross-import concordance.
        </p>
        <fieldset class="census-import-selector">
          <legend>
            Multi-import census runs — choose 2–4 explicitly; selection order is
            preserved across pages
          </legend>
          <label
            v-for="run in runsPage.items"
            :key="`census:${run.import_identity_sha256}`"
            class="census-import-option"
          >
            <input
              type="checkbox"
              :checked="isCensusImportSelected(run)"
              :disabled="
                censusImportSelectionLimitReached &&
                !isCensusImportSelected(run)
              "
              @change="toggleCensusImportSelection(run, $event)"
            />
            <span>
              {{ run.dataset_identity }} · {{ run.completed_at }} ·
              <code>{{ run.import_identity_sha256 }}</code>
            </span>
          </label>
          <p v-if="censusImportSelections.length === 0" class="explicit-action-note">
            No census import is selected automatically.
          </p>
          <ol
            v-else
            class="census-import-selection-order"
            aria-label="Ordered multi-import census selection"
          >
            <li
              v-for="(run, index) in censusImportSelections"
              :key="`selected-census:${run.import_identity_sha256}`"
            >
              <span>{{ index + 1 }} · {{ run.dataset_identity }}</span>
              <code>{{ run.import_identity_sha256 }}</code>
              <button
                class="button button--quiet census-import-remove"
                type="button"
                @click="removeCensusImport(run)"
              >
                Remove
              </button>
            </li>
          </ol>
        </fieldset>

        <nav class="research-pagination" aria-label="Historical run pages">
          <button
            class="button button--quiet"
            type="button"
            :disabled="!canRunPrevious"
            @click="loadRuns(Math.max(0, (runsPage?.offset ?? 0) - RUN_LIMIT))"
          >
            Previous
          </button>
          <button
            class="button button--quiet"
            type="button"
            :disabled="!canRunNext"
            @click="loadRuns((runsPage?.offset ?? 0) + RUN_LIMIT)"
          >
            Next
          </button>
        </nav>
      </template>

      <dl v-if="selectedRun" class="source-facts">
        <div><dt>Dataset</dt><dd>{{ selectedRun.dataset_identity }}</dd></div>
        <div><dt>Lottery</dt><dd>{{ selectedRun.lottery_type }}</dd></div>
        <div><dt>Completed</dt><dd>{{ selectedRun.completed_at }}</dd></div>
        <div><dt>Source repository</dt><dd>{{ selectedRun.source_repository }}</dd></div>
        <div><dt>Source commit</dt><dd><code>{{ selectedRun.source_commit_oid }}</code></dd></div>
        <div class="source-facts__identity">
          <dt>Exact import SHA-256</dt>
          <dd>
            <code>{{ selectedRun.import_identity_sha256 }}</code>
            <button class="copy-button" type="button" @click="copyImportIdentity">
              {{ copiedIdentity ? 'Copied' : 'Copy' }}
            </button>
          </dd>
        </div>
      </dl>
    </section>

    <section class="research-panel" aria-labelledby="analysis-controls-title">
      <div class="panel-heading">
        <div>
          <p class="step-label">2 · Evaluation identity</p>
          <h2 id="analysis-controls-title">Choose prefix and criterion</h2>
        </div>
        <span class="explicit-action-note">Analyze is always explicit</span>
      </div>
      <form class="analysis-controls" @submit.prevent="loadResults(0)">
        <label>
          <span>Prefix count</span>
          <select v-model.number="prefixCount" name="prefix-count" @change="controlsChanged">
            <option v-for="value in HISTORICAL_SUCCESS_PREFIX_COUNTS" :key="value" :value="value">
              {{ value }}
            </option>
          </select>
        </label>
        <label>
          <span>Success criterion</span>
          <select v-model="criterion" name="criterion" @change="controlsChanged">
            <option v-for="value in HISTORICAL_SUCCESS_CRITERIA" :key="value" :value="value">
              {{ value }}
            </option>
          </select>
        </label>
        <button
          class="button button--primary"
          type="submit"
          :disabled="selectedRun === null || analysisState === 'loading'"
        >
          Analyze selected run
        </button>
      </form>
      <p v-if="selectedRun === null" class="research-state">Select a run before analysis.</p>
      <p v-else-if="analysisState === 'selected'" class="research-state">
        Run selected. No analysis request has been made yet.
      </p>
    </section>

    <section class="research-results" aria-labelledby="historical-results-title">
      <div class="panel-heading">
        <div>
          <p class="step-label">3 · Descriptive windows</p>
          <h2 id="historical-results-title">Exact strategy identities</h2>
        </div>
        <div v-if="resultPage" class="page-count">{{ resultPage.total_count }} identities</div>
      </div>

      <p v-if="analysisState === 'idle' || analysisState === 'selected'" class="research-state">
        Results remain empty until Analyze is activated.
      </p>
      <p v-else-if="analysisState === 'loading'" class="research-state">Loading exact persisted windows…</p>
      <div v-else-if="analysisState === 'empty'" class="research-state">
        <strong>This exact import contains zero strategy identities.</strong>
      </div>
      <div
        v-else-if="['not-found', 'invalid', 'unavailable', 'malformed', 'error'].includes(analysisState)"
        class="research-state research-state--error"
      >
        <strong>{{ analysisError }}</strong>
        <button class="button button--quiet" type="button" @click="loadResults(resultPage?.offset ?? 0)">Retry</button>
      </div>

      <ol v-if="analysisState === 'ready' && resultPage" class="strategy-window-list">
        <li v-for="item in resultPage.items" :key="`${item.strategy.strategy_id}:${item.strategy.strategy_version}:${item.strategy.replicate}`" class="strategy-window-card">
          <header class="strategy-window-card__header">
            <div>
              <span class="identity-kind">{{ item.strategy.identity_kind }}</span>
              <h3>{{ item.strategy.strategy_id }}</h3>
              <code>{{ item.strategy.strategy_version }} · replicate {{ item.strategy.replicate }}</code>
            </div>
            <div class="strategy-window-card__actions">
              <label class="matrix-selector">
                <input
                  class="matrix-select"
                  type="checkbox"
                  :checked="isMatrixSelected(item)"
                  :disabled="!isMatrixSelected(item) && matrixSelectionLimitReached"
                  :aria-label="`Select ${item.strategy.strategy_id} ${item.strategy.strategy_version} replicate ${item.strategy.replicate} for stability matrix comparison`"
                  @change="toggleMatrixSelection(item, $event)"
                >
                Select matrix
              </label>
              <button class="button button--quiet inspect-button" type="button" @click="inspectStrategy(item)">
                Inspect exact identity
              </button>
            </div>
          </header>

          <dl class="identity-facts">
            <div><dt>Effective ID</dt><dd>{{ item.strategy.effective_strategy_id }}</dd></div>
            <div><dt>Governance</dt><dd>{{ item.strategy.governance_status }}</dd></div>
            <div><dt>Alias target</dt><dd>{{ item.strategy.alias_of_strategy_id ?? 'None' }}</dd></div>
            <div><dt>Equivalence group</dt><dd>{{ item.strategy.equivalence_group ?? 'None' }}</dd></div>
            <div><dt>Source observations</dt><dd>{{ item.source_observation_count }}</dd></div>
            <div><dt>Observation status</dt><dd>{{ item.source_observation_count === 0 ? 'ZERO OBSERVATIONS' : item.status }}</dd></div>
          </dl>

          <p v-if="item.windows.length === 0" class="zero-observation">
            This exact identity is retained with zero observations; no window is fabricated.
          </p>
          <div v-else class="window-grid">
            <article v-for="window in item.windows" :key="window.window_kind" class="window-card">
              <header>
                <div><span>{{ window.window_kind }}</span><strong>{{ window.window_role }}</strong></div>
                <code>{{ window.requested_draw_count ?? 'all' }} draws</code>
              </header>
              <p class="exact-rate">{{ exactRate(window) }}</p>
              <dl>
                <div><dt>Evaluation</dt><dd>{{ window.evaluation_status }}</dd></div>
                <div><dt>Evidence</dt><dd>{{ window.evidence_status }}</dd></div>
                <div><dt>Source</dt><dd>{{ window.source_draw_count }}</dd></div>
                <div><dt>Eligible</dt><dd>{{ window.eligible_draw_count }}</dd></div>
                <div><dt>Excluded</dt><dd>{{ window.excluded_draw_count }}</dd></div>
                <div><dt>Success</dt><dd>{{ window.success_count }}</dd></div>
                <div><dt>Failure</dt><dd>{{ window.failure_count }}</dd></div>
                <div><dt>Available</dt><dd>{{ window.success_rate.available ? 'YES' : 'NO' }}</dd></div>
              </dl>
              <footer>
                <span>First target · {{ targetLabel(window.first_target) }}</span>
                <span>Last target · {{ targetLabel(window.last_target) }}</span>
              </footer>
            </article>
          </div>
        </li>
      </ol>

      <nav v-if="resultPage && analysisState === 'ready'" class="research-pagination" aria-label="Historical Success Window pages">
        <button class="button button--quiet" type="button" :disabled="!canResultPrevious" @click="loadResults(Math.max(0, resultPage.offset - RESULT_LIMIT))">Previous</button>
        <span>Offset {{ resultPage.offset }} · limit {{ resultPage.limit }}</span>
        <button class="button button--quiet" type="button" :disabled="!canResultNext" @click="loadResults(resultPage.offset + RESULT_LIMIT)">Next</button>
      </nav>
    </section>

    <section class="research-results matrix-comparison" aria-labelledby="matrix-comparison-title">
      <div class="panel-heading">
        <div>
          <p class="step-label">4 · Manual stability comparison</p>
          <h2 id="matrix-comparison-title">Exact strategy stability matrices</h2>
        </div>
        <button
          class="button button--primary matrix-compare"
          type="button"
          :disabled="selectedRun === null || matrixSelections.length === 0"
          @click="compareSelectedMatrices"
        >
          Compare selected stability matrices
        </button>
      </div>

      <p v-if="selectedRun === null" class="research-state">
        Select a run before choosing stability matrices.
      </p>
      <p v-else-if="matrixSelections.length === 0" class="research-state">
        Select one to four exact strategy identities. No matrix request runs on selection.
      </p>
      <p v-else-if="matrixState === 'selected'" class="research-state">
        {{ matrixSelections.length }} exact {{ matrixSelections.length === 1 ? 'identity' : 'identities' }} selected in manual order.
      </p>
      <p v-if="matrixSelectionLimitReached" class="research-state research-state--notice selection-limit">
        Selection limit reached: four exact identities.
      </p>
      <p v-if="matrixState === 'loading'" class="research-state">
        Loading {{ matrixSelections.length }} exact stability {{ matrixSelections.length === 1 ? 'matrix' : 'matrices' }}…
      </p>
      <div v-if="matrixState === 'partial'" class="research-state research-state--notice">
        <strong>Some exact matrices are unavailable; successful results remain visible.</strong>
        <button class="button button--quiet matrix-retry" type="button" @click="compareSelectedMatrices">Retry all</button>
      </div>
      <div v-if="matrixState === 'error'" class="research-state research-state--error">
        <strong>All selected matrix requests failed with sanitized errors.</strong>
        <button class="button button--quiet matrix-retry" type="button" @click="compareSelectedMatrices">Retry all</button>
      </div>

      <ol v-if="matrixResults.length > 0" class="matrix-result-list">
        <li
          v-for="outcome in matrixResults"
          :key="matrixIdentity(outcome.selection)"
          class="matrix-result-card"
        >
          <header>
            <div>
              <span class="identity-kind">{{ outcome.selection.strategy.identity_kind }}</span>
              <h3>{{ outcome.selection.strategy.strategy_id }}</h3>
              <code>
                {{ outcome.selection.strategy.strategy_version }} · replicate
                {{ outcome.selection.strategy.replicate }}
              </code>
            </div>
          </header>
          <div v-if="outcome.matrix">
            <dl class="identity-facts matrix-identity-facts">
              <div><dt>Effective ID</dt><dd>{{ outcome.matrix.strategy.effective_strategy_id }}</dd></div>
              <div><dt>Identity kind</dt><dd>{{ outcome.matrix.strategy.identity_kind }}</dd></div>
              <div><dt>Governance</dt><dd>{{ outcome.matrix.strategy.governance_status }}</dd></div>
              <div><dt>Alias target</dt><dd>{{ outcome.matrix.strategy.alias_of_strategy_id ?? 'None' }}</dd></div>
              <div><dt>Equivalence group</dt><dd>{{ outcome.matrix.strategy.equivalence_group ?? 'None' }}</dd></div>
              <div><dt>Source observations</dt><dd>{{ outcome.matrix.source_observation_count }}</dd></div>
            </dl>
            <p v-if="outcome.matrix.source_observation_count === 0" class="zero-observation">
              Zero-observation matrix: all 64 canonical cells remain visible without fabricated rates.
            </p>
            <div class="matrix-table-scroll">
              <table class="stability-matrix">
                <caption>
                  Exact descriptive rates and signed arithmetic deltas for
                  {{ outcome.matrix.strategy.strategy_id }}
                </caption>
                <thead>
                  <tr>
                    <th scope="col">Criterion</th>
                    <th v-for="prefix in HISTORICAL_SUCCESS_PREFIX_COUNTS" :key="prefix" scope="col">
                      Prefix {{ prefix }}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="criterionIdentity in HISTORICAL_SUCCESS_CRITERIA" :key="criterionIdentity">
                    <th scope="row">{{ criterionIdentity }}</th>
                    <td v-for="prefix in HISTORICAL_SUCCESS_PREFIX_COUNTS" :key="prefix">
                      <template v-if="matrixCell(outcome.matrix, criterionIdentity, prefix).windows.length === 0">
                        <span class="matrix-unavailable">NO_OBSERVATIONS · rates unavailable</span>
                      </template>
                      <details v-else class="matrix-cell-detail">
                        <summary>Exact values</summary>
                        <dl>
                          <div
                            v-for="window in matrixCell(outcome.matrix, criterionIdentity, prefix).windows"
                            :key="window.window_kind"
                          >
                            <dt>{{ window.window_kind }}</dt>
                            <dd>{{ matrixRate(window.success_rate) }}</dd>
                          </div>
                          <div
                            v-for="comparison in matrixCell(outcome.matrix, criterionIdentity, prefix).comparisons"
                            :key="comparison.comparison_kind"
                          >
                            <dt>{{ comparison.comparison_kind }}</dt>
                            <dd>
                              {{ matrixDelta(comparison) }} · {{ comparison.relation }}
                            </dd>
                          </div>
                        </dl>
                      </details>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
          <div v-else class="research-state research-state--error matrix-item-error">
            <strong>{{ outcome.error }}</strong>
          </div>
        </li>
      </ol>
    </section>

    <section class="research-results feature-cohort-comparison" aria-labelledby="feature-cohort-comparison-title">
      <div class="panel-heading">
        <div>
          <p class="step-label">5 · Walk-forward feature cohorts</p>
          <h2 id="feature-cohort-comparison-title">Exact next-target cohort comparison</h2>
        </div>
        <button
          class="button button--primary feature-cohort-evaluate"
          type="button"
          :disabled="selectedRun === null || matrixSelections.length === 0"
          @click="evaluateSelectedFeatureCohorts"
        >
          Evaluate walk-forward feature cohorts
        </button>
      </div>

      <p v-if="selectedRun === null" class="research-state">
        Select a run before evaluating walk-forward feature cohorts.
      </p>
      <p v-else-if="matrixSelections.length === 0" class="research-state">
        Select one to four exact strategy identities above. No feature-cohort request runs on selection.
      </p>
      <p v-else-if="featureCohortState === 'selected'" class="research-state">
        {{ matrixSelections.length }} exact {{ matrixSelections.length === 1 ? 'identity' : 'identities' }}
        selected in manual order. Prefix {{ prefixCount }} · criterion {{ criterion }}.
      </p>
      <p v-if="featureCohortState === 'loading'" class="research-state">
        Evaluating {{ matrixSelections.length }} exact walk-forward
        {{ matrixSelections.length === 1 ? 'cohort grid' : 'cohort grids' }}…
      </p>
      <div v-if="featureCohortState === 'partial'" class="research-state research-state--notice">
        <strong>Some exact feature-cohort requests are unavailable; successful results remain visible.</strong>
        <button class="button button--quiet feature-cohort-retry" type="button" @click="evaluateSelectedFeatureCohorts">Retry all</button>
      </div>
      <div v-if="featureCohortState === 'error'" class="research-state research-state--error">
        <strong>All selected feature-cohort requests failed with sanitized errors.</strong>
        <button class="button button--quiet feature-cohort-retry" type="button" @click="evaluateSelectedFeatureCohorts">Retry all</button>
      </div>

      <ol v-if="featureCohortResults.length > 0" class="feature-cohort-result-list">
        <li
          v-for="outcome in featureCohortResults"
          :key="matrixIdentity(outcome.selection)"
          class="feature-cohort-result-card"
        >
          <header>
            <div>
              <span class="identity-kind">{{ outcome.selection.strategy.identity_kind }}</span>
              <h3>{{ outcome.selection.strategy.strategy_id }}</h3>
              <code>
                {{ outcome.selection.strategy.strategy_version }} · replicate
                {{ outcome.selection.strategy.replicate }}
              </code>
            </div>
          </header>
          <div v-if="outcome.result">
            <dl class="identity-facts feature-cohort-facts">
              <div><dt>Prefix</dt><dd>{{ outcome.result.prefix_count }}</dd></div>
              <div><dt>Criterion</dt><dd>{{ outcome.result.criterion.criterion }}</dd></div>
              <div><dt>Baseline observations</dt><dd>{{ outcome.result.baseline.observation_count }}</dd></div>
              <div><dt>Baseline successes</dt><dd>{{ outcome.result.baseline.success_count }}</dd></div>
              <div><dt>Baseline failures</dt><dd>{{ outcome.result.baseline.failure_count }}</dd></div>
              <div><dt>Baseline exact rate</dt><dd>{{ featureRate(outcome.result.baseline.success_rate) }}</dd></div>
            </dl>
            <div class="feature-cohort-table-scroll">
              <table class="feature-cohort-table">
                <caption>
                  Canonical 64-cohort walk-forward observations for
                  {{ outcome.result.strategy.strategy_id }}. Feature snapshots use prior targets only.
                </caption>
                <thead>
                  <tr>
                    <th scope="col">Long→Medium</th>
                    <th scope="col">Medium→Short</th>
                    <th scope="col">Long→Short</th>
                    <th scope="col">Observations</th>
                    <th scope="col">Successes</th>
                    <th scope="col">Failures</th>
                    <th scope="col">Exact cohort rate</th>
                    <th scope="col">Delta vs baseline</th>
                    <th scope="col">Relation</th>
                    <th scope="col">First target</th>
                    <th scope="col">Last target</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="cohort in outcome.result.cohorts"
                    :key="featureCohortKey(cohort)"
                    :class="{ 'feature-cohort-row--empty': cohort.observation_count === 0 }"
                  >
                    <td>{{ cohort.feature_key.long_to_medium }}</td>
                    <td>{{ cohort.feature_key.medium_to_short }}</td>
                    <td>{{ cohort.feature_key.long_to_short }}</td>
                    <td>{{ cohort.observation_count }}</td>
                    <td>{{ cohort.success_count }}</td>
                    <td>{{ cohort.failure_count }}</td>
                    <td>{{ featureRate(cohort.success_rate) }}</td>
                    <td>{{ featureDelta(cohort) }}</td>
                    <td>{{ cohort.relation_vs_baseline }}</td>
                    <td>{{ optionalTarget(cohort.first_target) }}</td>
                    <td>{{ optionalTarget(cohort.last_target) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
          <div v-else class="research-state research-state--error feature-cohort-item-error">
            <strong>{{ outcome.error }}</strong>
          </div>
        </li>
      </ol>
    </section>

    <section
      class="research-results recent-50-stability-audit-panel"
      aria-labelledby="recent-50-stability-audit-title"
    >
      <div class="panel-heading">
        <div>
          <p class="step-label">Descriptive confirmation recency check</p>
          <h2 id="recent-50-stability-audit-title">Reference 250 / recent 50 stability audit</h2>
        </div>
        <button
          class="button recent-50-stability-audit-action"
          type="button"
          :disabled="selectedRun === null || matrixSelections.length === 0"
          @click="evaluateRecent50StabilityAudit"
        >
          Evaluate recent-50 stability audit
        </button>
      </div>

      <p class="research-state research-state--notice recent-50-descriptive-notice">
        Descriptive only. The audit compares two fixed, chronological, non-overlapping
        slices and produces no prescriptive interpretation.
      </p>
      <p v-if="selectedRun === null" class="research-state">
        Select a run before evaluating the recent-50 stability audit.
      </p>
      <p v-else-if="matrixSelections.length === 0" class="research-state">
        Select one to four exact strategy identities above. No audit request runs on selection.
      </p>
      <p v-else-if="recent50StabilityAuditState === 'selected'" class="research-state">
        {{ matrixSelections.length }} exact {{ matrixSelections.length === 1 ? 'identity' : 'identities' }}
        selected in manual order. The audit runs only from the explicit action.
      </p>
      <p v-if="recent50StabilityAuditState === 'loading'" class="research-state">
        Evaluating the fixed 250-target reference and 50-target recent slices…
      </p>
      <div
        v-if="recent50StabilityAuditState === 'partial'"
        class="research-state research-state--notice"
      >
        <strong>Some recent-50 audit requests are unavailable; successful results remain visible.</strong>
        <button
          class="button button--quiet recent-50-stability-audit-retry"
          type="button"
          @click="evaluateRecent50StabilityAudit"
        >
          Retry all
        </button>
      </div>
      <div
        v-if="recent50StabilityAuditState === 'error'"
        class="research-state research-state--error"
      >
        <strong>All selected recent-50 audit requests were unavailable; sanitized errors are shown.</strong>
        <button
          class="button button--quiet recent-50-stability-audit-retry"
          type="button"
          @click="evaluateRecent50StabilityAudit"
        >
          Retry all
        </button>
      </div>

      <ol
        v-if="recent50StabilityAuditResults.length > 0"
        class="temporal-holdout-result-list recent-50-stability-audit-result-list"
      >
        <li
          v-for="outcome in recent50StabilityAuditResults"
          :key="matrixIdentity(outcome.selection)"
          class="temporal-holdout-result-card recent-50-stability-audit-result-card"
        >
          <header>
            <div>
              <span class="identity-kind">{{ outcome.selection.strategy.identity_kind }}</span>
              <h3>{{ outcome.selection.strategy.strategy_id }}</h3>
              <code>
                {{ outcome.selection.strategy.strategy_version }} · replicate
                {{ outcome.selection.strategy.replicate }}
              </code>
            </div>
          </header>
          <div v-if="outcome.result">
            <dl class="identity-facts temporal-holdout-facts">
              <div class="source-facts__identity">
                <dt>Import identity</dt>
                <dd><code>{{ outcome.result.metadata.import_identity_sha256 }}</code></dd>
              </div>
              <div><dt>Strategy identity</dt><dd>{{ outcome.result.strategy.strategy_id }}</dd></div>
              <div><dt>Version</dt><dd>{{ outcome.result.strategy.strategy_version }}</dd></div>
              <div><dt>Replicate</dt><dd>{{ outcome.result.strategy.replicate }}</dd></div>
              <div><dt>Prefix</dt><dd>{{ outcome.result.prefix_count }}</dd></div>
              <div><dt>Criterion</dt><dd>{{ outcome.result.criterion.criterion }}</dd></div>
              <div><dt>Status</dt><dd>{{ outcome.result.audit_status }}</dd></div>
              <div><dt>Source split</dt><dd>{{ outcome.result.split.source_temporal_split_method }}</dd></div>
              <div><dt>Audit split</dt><dd>{{ outcome.result.split.audit_split_method }}</dd></div>
              <div><dt>Total assignments</dt><dd>{{ outcome.result.split.total_assignment_count }}</dd></div>
              <div><dt>Warmup</dt><dd>{{ outcome.result.split.warmup_count }}</dd></div>
              <div><dt>Discovery</dt><dd>{{ outcome.result.split.discovery_count }}</dd></div>
              <div><dt>Confirmation</dt><dd>{{ outcome.result.split.confirmation_count }}</dd></div>
              <div><dt>Reference</dt><dd>{{ outcome.result.split.reference_count }}</dd></div>
              <div><dt>Recent</dt><dd>{{ outcome.result.split.recent_count }}</dd></div>
              <div><dt>Discovery first</dt><dd>{{ optionalTarget(outcome.result.split.discovery_first_target) }}</dd></div>
              <div><dt>Discovery last</dt><dd>{{ optionalTarget(outcome.result.split.discovery_last_target) }}</dd></div>
              <div><dt>Confirmation first</dt><dd>{{ optionalTarget(outcome.result.split.confirmation_first_target) }}</dd></div>
              <div><dt>Confirmation last</dt><dd>{{ optionalTarget(outcome.result.split.confirmation_last_target) }}</dd></div>
              <div><dt>Reference first</dt><dd>{{ optionalTarget(outcome.result.split.reference_first_target) }}</dd></div>
              <div><dt>Reference last</dt><dd>{{ optionalTarget(outcome.result.split.reference_last_target) }}</dd></div>
              <div><dt>Recent first</dt><dd>{{ optionalTarget(outcome.result.split.recent_first_target) }}</dd></div>
              <div><dt>Recent last</dt><dd>{{ optionalTarget(outcome.result.split.recent_last_target) }}</dd></div>
              <div><dt>Family size</dt><dd>{{ outcome.result.family_size }}</dd></div>
            </dl>
            <p
              v-if="outcome.result.audit_status === 'NOT_READY_INSUFFICIENT_HISTORY'"
              class="research-state recent-50-stability-audit-not-ready"
            >
              Insufficient labeled history. The fixed slices were not shortened and no
              partial diagnostics were produced.
            </p>
            <div v-else class="feature-cohort-diagnostics-table-scroll temporal-holdout-table-scroll">
              <table class="feature-cohort-diagnostics-table temporal-holdout-table">
                <caption>
                  All 64 canonical cohorts in server order. Reference and recent values
                  are separately adjusted fixed families; exact probabilities remain decimal strings.
                </caption>
                <thead>
                  <tr>
                    <th scope="col">Index</th>
                    <th scope="col">Long→Medium</th>
                    <th scope="col">Medium→Short</th>
                    <th scope="col">Long→Short</th>
                    <th scope="col">Reference S/F/N</th>
                    <th scope="col">Reference cohort rate</th>
                    <th scope="col">Reference outside rate</th>
                    <th scope="col">Reference risk difference</th>
                    <th scope="col">Reference raw exact p</th>
                    <th scope="col">Reference BY exact p</th>
                    <th scope="col">Recent S/F/N</th>
                    <th scope="col">Recent cohort rate</th>
                    <th scope="col">Recent outside rate</th>
                    <th scope="col">Recent risk difference</th>
                    <th scope="col">Recent raw exact p</th>
                    <th scope="col">Recent BY exact p</th>
                    <th scope="col">Recent − reference effect</th>
                    <th scope="col">Relationship</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="comparison in outcome.result.comparisons"
                    :key="comparison.cohort_index"
                    class="recent-50-stability-audit-comparison"
                  >
                    <td>{{ comparison.cohort_index }}</td>
                    <td>{{ comparison.feature_key.long_to_medium }}</td>
                    <td>{{ comparison.feature_key.medium_to_short }}</td>
                    <td>{{ comparison.feature_key.long_to_short }}</td>
                    <td>
                      {{ comparison.reference_diagnostic.cohort_counts.success_count }} /
                      {{ comparison.reference_diagnostic.cohort_counts.failure_count }} /
                      {{ comparison.reference_diagnostic.cohort_counts.observation_count }}
                    </td>
                    <td>{{ featureRate(comparison.reference_diagnostic.cohort_success_rate) }}</td>
                    <td>{{ featureRate(comparison.reference_diagnostic.outside_success_rate) }}</td>
                    <td>{{ diagnosticEffect(comparison.reference_diagnostic) }}</td>
                    <td><code class="exact-probability">{{ exactProbability(comparison.reference_diagnostic.raw_p_value) }}</code></td>
                    <td><code class="exact-probability">{{ exactProbability(comparison.reference_diagnostic.adjusted_p_value) }}</code></td>
                    <td>
                      {{ comparison.recent_diagnostic.cohort_counts.success_count }} /
                      {{ comparison.recent_diagnostic.cohort_counts.failure_count }} /
                      {{ comparison.recent_diagnostic.cohort_counts.observation_count }}
                    </td>
                    <td>{{ featureRate(comparison.recent_diagnostic.cohort_success_rate) }}</td>
                    <td>{{ featureRate(comparison.recent_diagnostic.outside_success_rate) }}</td>
                    <td>{{ diagnosticEffect(comparison.recent_diagnostic) }}</td>
                    <td><code class="exact-probability">{{ exactProbability(comparison.recent_diagnostic.raw_p_value) }}</code></td>
                    <td><code class="exact-probability">{{ exactProbability(comparison.recent_diagnostic.adjusted_p_value) }}</code></td>
                    <td>{{ recent50EffectChange(comparison) }}</td>
                    <td>{{ comparison.relationship }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
          <div
            v-else
            class="research-state research-state--error recent-50-stability-audit-item-error"
          >
            <strong>{{ outcome.error }}</strong>
          </div>
        </li>
      </ol>
    </section>

    <section
      class="research-results feature-cohort-diagnostics"
      aria-labelledby="feature-cohort-diagnostics-title"
    >
      <div class="panel-heading">
        <div>
          <p class="step-label">6 · Cohort inferential diagnostics</p>
          <h2 id="feature-cohort-diagnostics-title">Exact disjoint cohort diagnostics</h2>
        </div>
        <button
          class="button button--primary feature-cohort-diagnostics-evaluate"
          type="button"
          :disabled="selectedRun === null || matrixSelections.length === 0"
          @click="evaluateSelectedFeatureCohortDiagnostics"
        >
          Evaluate cohort inferential diagnostics
        </button>
      </div>

      <p v-if="selectedRun === null" class="research-state">
        Select a run before evaluating cohort inferential diagnostics.
      </p>
      <p v-else-if="matrixSelections.length === 0" class="research-state">
        Select one to four exact strategy identities above. No diagnostics request runs on selection.
      </p>
      <p v-else-if="featureCohortDiagnosticsState === 'selected'" class="research-state">
        {{ matrixSelections.length }} exact {{ matrixSelections.length === 1 ? 'identity' : 'identities' }}
        selected in manual order. Diagnostics run only from the explicit action.
      </p>
      <p v-if="featureCohortDiagnosticsState === 'loading'" class="research-state">
        Evaluating exact disjoint cohort diagnostics…
      </p>
      <div
        v-if="featureCohortDiagnosticsState === 'partial'"
        class="research-state research-state--notice"
      >
        <strong>Some exact diagnostics requests are unavailable; successful results remain visible.</strong>
        <button
          class="button button--quiet feature-cohort-diagnostics-retry"
          type="button"
          @click="evaluateSelectedFeatureCohortDiagnostics"
        >
          Retry all
        </button>
      </div>
      <div
        v-if="featureCohortDiagnosticsState === 'error'"
        class="research-state research-state--error"
      >
        <strong>All selected diagnostics requests failed with sanitized errors.</strong>
        <button
          class="button button--quiet feature-cohort-diagnostics-retry"
          type="button"
          @click="evaluateSelectedFeatureCohortDiagnostics"
        >
          Retry all
        </button>
      </div>

      <ol
        v-if="featureCohortDiagnosticsResults.length > 0"
        class="feature-cohort-diagnostics-result-list"
      >
        <li
          v-for="outcome in featureCohortDiagnosticsResults"
          :key="matrixIdentity(outcome.selection)"
          class="feature-cohort-diagnostics-result-card"
        >
          <header>
            <div>
              <span class="identity-kind">{{ outcome.selection.strategy.identity_kind }}</span>
              <h3>{{ outcome.selection.strategy.strategy_id }}</h3>
              <code>
                {{ outcome.selection.strategy.strategy_version }} · replicate
                {{ outcome.selection.strategy.replicate }}
              </code>
            </div>
          </header>
          <div v-if="outcome.result">
            <dl class="identity-facts feature-cohort-diagnostics-facts">
              <div><dt>Prefix</dt><dd>{{ outcome.result.prefix_count }}</dd></div>
              <div><dt>Criterion</dt><dd>{{ outcome.result.criterion.criterion }}</dd></div>
              <div><dt>Family size</dt><dd>{{ outcome.result.family_size }}</dd></div>
              <div><dt>Raw test</dt><dd>{{ outcome.result.raw_test_method }}</dd></div>
              <div><dt>Adjustment</dt><dd>{{ outcome.result.adjustment_method }}</dd></div>
              <div><dt>Baseline observations</dt><dd>{{ outcome.result.baseline.observation_count }}</dd></div>
              <div><dt>Baseline successes</dt><dd>{{ outcome.result.baseline.success_count }}</dd></div>
              <div><dt>Baseline failures</dt><dd>{{ outcome.result.baseline.failure_count }}</dd></div>
            </dl>
            <div class="feature-cohort-diagnostics-table-scroll">
              <table class="feature-cohort-diagnostics-table">
                <caption>
                  All 64 hypotheses remain in canonical server order. Cohort and outside counts are
                  disjoint; probabilities and effects are neutral diagnostics only.
                </caption>
                <thead>
                  <tr>
                    <th scope="col">Index</th>
                    <th scope="col">Long→Medium</th>
                    <th scope="col">Medium→Short</th>
                    <th scope="col">Long→Short</th>
                    <th scope="col">Test status</th>
                    <th scope="col">Cohort S/F/N</th>
                    <th scope="col">Outside S/F/N</th>
                    <th scope="col">Cohort rate</th>
                    <th scope="col">Outside rate</th>
                    <th scope="col">Risk difference</th>
                    <th scope="col">Relation</th>
                    <th scope="col">Raw exact p</th>
                    <th scope="col">BY-adjusted exact p</th>
                    <th scope="col">First target</th>
                    <th scope="col">Last target</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="diagnostic in outcome.result.diagnostics"
                    :key="diagnosticKey(diagnostic)"
                    :class="{
                      'feature-cohort-row--empty':
                        diagnostic.cohort_counts.observation_count === 0,
                    }"
                  >
                    <td>{{ diagnostic.cohort_index }}</td>
                    <td>{{ diagnostic.feature_key.long_to_medium }}</td>
                    <td>{{ diagnostic.feature_key.medium_to_short }}</td>
                    <td>{{ diagnostic.feature_key.long_to_short }}</td>
                    <td>{{ diagnostic.test_status }}</td>
                    <td>
                      {{ diagnostic.cohort_counts.success_count }} /
                      {{ diagnostic.cohort_counts.failure_count }} /
                      {{ diagnostic.cohort_counts.observation_count }}
                    </td>
                    <td>
                      {{ diagnostic.outside_counts.success_count }} /
                      {{ diagnostic.outside_counts.failure_count }} /
                      {{ diagnostic.outside_counts.observation_count }}
                    </td>
                    <td>{{ featureRate(diagnostic.cohort_success_rate) }}</td>
                    <td>{{ featureRate(diagnostic.outside_success_rate) }}</td>
                    <td>{{ diagnosticEffect(diagnostic) }}</td>
                    <td>{{ diagnostic.relation_vs_outside }}</td>
                    <td><code class="exact-probability">{{ exactProbability(diagnostic.raw_p_value) }}</code></td>
                    <td><code class="exact-probability">{{ exactProbability(diagnostic.adjusted_p_value) }}</code></td>
                    <td>{{ optionalTarget(diagnostic.first_target) }}</td>
                    <td>{{ optionalTarget(diagnostic.last_target) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
          <div
            v-else
            class="research-state research-state--error feature-cohort-diagnostics-item-error"
          >
            <strong>{{ outcome.error }}</strong>
          </div>
        </li>
      </ol>
    </section>

    <section class="research-results temporal-holdout-panel" aria-labelledby="temporal-holdout-title">
      <div class="panel-heading">
        <div>
          <p class="step-label">Fixed chronological diagnostic split</p>
          <h2 id="temporal-holdout-title">750/300 temporal holdout</h2>
        </div>
        <button
          class="button temporal-holdout-action"
          type="button"
          :disabled="selectedRun === null || matrixSelections.length === 0"
          @click="evaluateSelectedTemporalHoldout"
        >
          Evaluate 750/300 temporal holdout
        </button>
      </div>

      <p v-if="selectedRun === null" class="research-state">
        Select a run before evaluating the temporal holdout.
      </p>
      <p v-else-if="matrixSelections.length === 0" class="research-state">
        Select one to four exact strategy identities above. No holdout request runs on selection.
      </p>
      <p v-else-if="temporalHoldoutState === 'selected'" class="research-state">
        {{ matrixSelections.length }} exact {{ matrixSelections.length === 1 ? 'identity' : 'identities' }}
        selected in manual order. The holdout runs only from the explicit action.
      </p>
      <p v-if="temporalHoldoutState === 'loading'" class="research-state">
        Evaluating the fixed 750-target discovery and 300-target confirmation phases…
      </p>
      <div
        v-if="temporalHoldoutState === 'partial'"
        class="research-state research-state--notice"
      >
        <strong>Some temporal holdout requests are unavailable; successful results remain visible.</strong>
        <button class="button button--quiet temporal-holdout-retry" type="button" @click="evaluateSelectedTemporalHoldout">
          Retry all
        </button>
      </div>
      <div
        v-if="temporalHoldoutState === 'error'"
        class="research-state research-state--error"
      >
        <strong>All selected temporal holdout requests failed with sanitized errors.</strong>
        <button class="button button--quiet temporal-holdout-retry" type="button" @click="evaluateSelectedTemporalHoldout">
          Retry all
        </button>
      </div>

      <ol v-if="temporalHoldoutResults.length > 0" class="temporal-holdout-result-list">
        <li
          v-for="outcome in temporalHoldoutResults"
          :key="matrixIdentity(outcome.selection)"
          class="temporal-holdout-result-card"
        >
          <header>
            <div>
              <span class="identity-kind">{{ outcome.selection.strategy.identity_kind }}</span>
              <h3>{{ outcome.selection.strategy.strategy_id }}</h3>
              <code>
                {{ outcome.selection.strategy.strategy_version }} · replicate
                {{ outcome.selection.strategy.replicate }}
              </code>
            </div>
          </header>
          <div v-if="outcome.result">
            <dl class="identity-facts temporal-holdout-facts">
              <div class="source-facts__identity">
                <dt>Import identity</dt>
                <dd><code>{{ outcome.result.metadata.import_identity_sha256 }}</code></dd>
              </div>
              <div><dt>Prefix</dt><dd>{{ outcome.result.prefix_count }}</dd></div>
              <div><dt>Criterion</dt><dd>{{ outcome.result.criterion.criterion }}</dd></div>
              <div><dt>Status</dt><dd>{{ outcome.result.evaluation_status }}</dd></div>
              <div><dt>Split method</dt><dd>{{ outcome.result.split.split_method }}</dd></div>
              <div><dt>Total assignments</dt><dd>{{ outcome.result.split.total_assignment_count }}</dd></div>
              <div><dt>Warmup</dt><dd>{{ outcome.result.split.warmup_count }}</dd></div>
              <div><dt>Discovery</dt><dd>{{ outcome.result.split.discovery_count }}</dd></div>
              <div><dt>Confirmation</dt><dd>{{ outcome.result.split.confirmation_count }}</dd></div>
              <div><dt>Discovery first</dt><dd>{{ optionalTarget(outcome.result.split.discovery_first_target) }}</dd></div>
              <div><dt>Discovery last</dt><dd>{{ optionalTarget(outcome.result.split.discovery_last_target) }}</dd></div>
              <div><dt>Confirmation first</dt><dd>{{ optionalTarget(outcome.result.split.confirmation_first_target) }}</dd></div>
              <div><dt>Confirmation last</dt><dd>{{ optionalTarget(outcome.result.split.confirmation_last_target) }}</dd></div>
              <div><dt>Family size</dt><dd>{{ outcome.result.family_size }}</dd></div>
            </dl>
            <p
              v-if="outcome.result.evaluation_status === 'NOT_READY_INSUFFICIENT_HISTORY'"
              class="research-state temporal-holdout-not-ready"
            >
              Insufficient labeled history. Neither phase was shortened and no partial diagnostics were produced.
            </p>
            <div v-else class="feature-cohort-diagnostics-table-scroll temporal-holdout-table-scroll">
              <table class="feature-cohort-diagnostics-table temporal-holdout-table">
                <caption>
                  All 64 canonical cohorts in server order. Discovery and confirmation are separate
                  fixed families; relationship labels are neutral descriptive comparisons.
                </caption>
                <thead>
                  <tr>
                    <th scope="col">Index</th>
                    <th scope="col">Long→Medium</th>
                    <th scope="col">Medium→Short</th>
                    <th scope="col">Long→Short</th>
                    <th scope="col">Discovery S/F/N</th>
                    <th scope="col">Discovery cohort rate</th>
                    <th scope="col">Discovery outside rate</th>
                    <th scope="col">Discovery risk difference</th>
                    <th scope="col">Discovery raw exact p</th>
                    <th scope="col">Discovery BY exact p</th>
                    <th scope="col">Confirmation S/F/N</th>
                    <th scope="col">Confirmation cohort rate</th>
                    <th scope="col">Confirmation outside rate</th>
                    <th scope="col">Confirmation risk difference</th>
                    <th scope="col">Confirmation raw exact p</th>
                    <th scope="col">Confirmation BY exact p</th>
                    <th scope="col">Effect change</th>
                    <th scope="col">Relationship</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="comparison in outcome.result.comparisons"
                    :key="comparison.cohort_index"
                    class="temporal-holdout-comparison"
                  >
                    <td>{{ comparison.cohort_index }}</td>
                    <td>{{ comparison.feature_key.long_to_medium }}</td>
                    <td>{{ comparison.feature_key.medium_to_short }}</td>
                    <td>{{ comparison.feature_key.long_to_short }}</td>
                    <td>
                      {{ comparison.discovery_diagnostic.cohort_counts.success_count }} /
                      {{ comparison.discovery_diagnostic.cohort_counts.failure_count }} /
                      {{ comparison.discovery_diagnostic.cohort_counts.observation_count }}
                    </td>
                    <td>{{ featureRate(comparison.discovery_diagnostic.cohort_success_rate) }}</td>
                    <td>{{ featureRate(comparison.discovery_diagnostic.outside_success_rate) }}</td>
                    <td>{{ diagnosticEffect(comparison.discovery_diagnostic) }}</td>
                    <td><code class="exact-probability">{{ exactProbability(comparison.discovery_diagnostic.raw_p_value) }}</code></td>
                    <td><code class="exact-probability">{{ exactProbability(comparison.discovery_diagnostic.adjusted_p_value) }}</code></td>
                    <td>
                      {{ comparison.confirmation_diagnostic.cohort_counts.success_count }} /
                      {{ comparison.confirmation_diagnostic.cohort_counts.failure_count }} /
                      {{ comparison.confirmation_diagnostic.cohort_counts.observation_count }}
                    </td>
                    <td>{{ featureRate(comparison.confirmation_diagnostic.cohort_success_rate) }}</td>
                    <td>{{ featureRate(comparison.confirmation_diagnostic.outside_success_rate) }}</td>
                    <td>{{ diagnosticEffect(comparison.confirmation_diagnostic) }}</td>
                    <td><code class="exact-probability">{{ exactProbability(comparison.confirmation_diagnostic.raw_p_value) }}</code></td>
                    <td><code class="exact-probability">{{ exactProbability(comparison.confirmation_diagnostic.adjusted_p_value) }}</code></td>
                    <td>{{ temporalEffectChange(comparison) }}</td>
                    <td>{{ comparison.relationship }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
          <div v-else class="research-state research-state--error temporal-holdout-item-error">
            <strong>{{ outcome.error }}</strong>
          </div>
        </li>
      </ol>
    </section>

    <section
      class="research-results cross-import-concordance-panel"
      aria-labelledby="cross-import-concordance-title"
    >
      <div class="panel-heading">
        <div>
          <p class="step-label">Ordered two-import diagnostic comparison</p>
          <h2 id="cross-import-concordance-title">Cross-import temporal concordance</h2>
        </div>
        <button
          class="button cross-import-concordance-action"
          type="button"
          :disabled="!distinctComparisonRuns || matrixSelections.length === 0"
          @click="evaluateCrossImportConcordance"
        >
          Evaluate cross-import temporal concordance
        </button>
      </div>

      <p v-if="selectedRun === null" class="research-state">
        Select the primary run before evaluating cross-import concordance.
      </p>
      <p v-else-if="comparisonRun === null" class="research-state">
        Select a separate comparison run. No comparison run is chosen automatically.
      </p>
      <p v-else-if="!distinctComparisonRuns" class="research-state research-state--notice">
        The primary and comparison runs must be distinct.
      </p>
      <p v-else-if="matrixSelections.length === 0" class="research-state">
        Select one to four exact strategy identities from the primary run. No concordance
        request runs on selection.
      </p>
      <p v-else-if="crossImportConcordanceState === 'selected'" class="research-state">
        {{ matrixSelections.length }} exact
        {{ matrixSelections.length === 1 ? 'identity' : 'identities' }} selected in manual
        order. Evaluation runs only from the explicit action.
      </p>
      <p v-if="crossImportConcordanceState === 'loading'" class="research-state">
        Comparing the two source-specific confirmation families…
      </p>
      <div
        v-if="crossImportConcordanceState === 'partial'"
        class="research-state research-state--notice"
      >
        <strong>Some concordance requests are unavailable; successful results remain visible.</strong>
        <button
          class="button button--quiet cross-import-concordance-retry"
          type="button"
          @click="evaluateCrossImportConcordance"
        >
          Retry all
        </button>
      </div>
      <div
        v-if="crossImportConcordanceState === 'error'"
        class="research-state research-state--error"
      >
        <strong>All selected concordance requests failed with sanitized errors.</strong>
        <button
          class="button button--quiet cross-import-concordance-retry"
          type="button"
          @click="evaluateCrossImportConcordance"
        >
          Retry all
        </button>
      </div>

      <ol
        v-if="crossImportConcordanceResults.length > 0"
        class="cross-import-concordance-result-list"
      >
        <li
          v-for="outcome in crossImportConcordanceResults"
          :key="matrixIdentity(outcome.selection)"
          class="cross-import-concordance-result-card"
        >
          <header>
            <span class="identity-kind">{{ outcome.selection.strategy.identity_kind }}</span>
            <h3>{{ outcome.selection.strategy.strategy_id }}</h3>
            <code>
              {{ outcome.selection.strategy.strategy_version }} · replicate
              {{ outcome.selection.strategy.replicate }}
            </code>
          </header>
          <div v-if="outcome.result">
            <dl class="identity-facts cross-import-concordance-facts">
              <div><dt>Pair status</dt><dd>{{ outcome.result.pair_status }}</dd></div>
              <div><dt>Primary holdout</dt><dd>{{ outcome.result.left_holdout_status }}</dd></div>
              <div><dt>Comparison holdout</dt><dd>{{ outcome.result.right_holdout_status }}</dd></div>
              <div><dt>Same dataset SHA</dt><dd>{{ outcome.result.metadata.same_dataset_sha256 ? 'YES' : 'NO' }}</dd></div>
              <div><dt>Same source artifact SHA</dt><dd>{{ outcome.result.metadata.same_source_artifact_sha256 ? 'YES' : 'NO' }}</dd></div>
              <div><dt>Prefix</dt><dd>{{ outcome.result.prefix_count }}</dd></div>
              <div><dt>Criterion</dt><dd>{{ outcome.result.criterion.criterion }}</dd></div>
              <div><dt>Primary run ID</dt><dd>{{ outcome.result.metadata.left.run_id }}</dd></div>
              <div class="source-facts__identity"><dt>Primary import SHA</dt><dd><code>{{ outcome.result.metadata.left.import_identity_sha256 }}</code></dd></div>
              <div><dt>Primary source</dt><dd>{{ outcome.result.metadata.left.source_repository }} · {{ outcome.result.metadata.left.source_commit_oid }}</dd></div>
              <div class="source-facts__identity"><dt>Primary source artifact SHA</dt><dd><code>{{ outcome.result.metadata.left.source_artifact_sha256 }}</code></dd></div>
              <div><dt>Primary dataset</dt><dd>{{ outcome.result.metadata.left.dataset_identity }} · {{ outcome.result.metadata.left.lottery_type }}</dd></div>
              <div class="source-facts__identity"><dt>Primary dataset SHA</dt><dd><code>{{ outcome.result.metadata.left.dataset_sha256 }}</code></dd></div>
              <div><dt>Comparison run ID</dt><dd>{{ outcome.result.metadata.right.run_id }}</dd></div>
              <div class="source-facts__identity"><dt>Comparison import SHA</dt><dd><code>{{ outcome.result.metadata.right.import_identity_sha256 }}</code></dd></div>
              <div><dt>Comparison source</dt><dd>{{ outcome.result.metadata.right.source_repository }} · {{ outcome.result.metadata.right.source_commit_oid }}</dd></div>
              <div class="source-facts__identity"><dt>Comparison source artifact SHA</dt><dd><code>{{ outcome.result.metadata.right.source_artifact_sha256 }}</code></dd></div>
              <div><dt>Comparison dataset</dt><dd>{{ outcome.result.metadata.right.dataset_identity }} · {{ outcome.result.metadata.right.lottery_type }}</dd></div>
              <div class="source-facts__identity"><dt>Comparison dataset SHA</dt><dd><code>{{ outcome.result.metadata.right.dataset_sha256 }}</code></dd></div>
            </dl>
            <dl
              v-if="outcome.result.confirmation_target_overlap"
              class="identity-facts confirmation-overlap-facts"
            >
              <div><dt>Primary confirmation targets</dt><dd>{{ outcome.result.confirmation_target_overlap.left_confirmation_target_count }}</dd></div>
              <div><dt>Comparison confirmation targets</dt><dd>{{ outcome.result.confirmation_target_overlap.right_confirmation_target_count }}</dd></div>
              <div><dt>Target overlap</dt><dd>{{ outcome.result.confirmation_target_overlap.overlap_count }}</dd></div>
              <div><dt>Primary only</dt><dd>{{ outcome.result.confirmation_target_overlap.left_only_count }}</dd></div>
              <div><dt>Comparison only</dt><dd>{{ outcome.result.confirmation_target_overlap.right_only_count }}</dd></div>
              <div><dt>Target relation</dt><dd>{{ outcome.result.confirmation_target_overlap.relation }}</dd></div>
            </dl>
            <p
              v-if="outcome.result.pair_status !== 'COMPLETE'"
              class="research-state cross-import-concordance-not-ready"
            >
              At least one temporal holdout is not ready. No partial comparison family was produced.
            </p>
            <div v-else class="feature-cohort-diagnostics-table-scroll cross-import-concordance-table-scroll">
              <table class="feature-cohort-diagnostics-table cross-import-concordance-table">
                <caption>
                  All 64 confirmation-phase cohorts in canonical server order. Each import retains
                  its own raw and BY-adjusted exact probability.
                </caption>
                <thead>
                  <tr>
                    <th scope="col">Index</th>
                    <th scope="col">Long→Medium</th>
                    <th scope="col">Medium→Short</th>
                    <th scope="col">Long→Short</th>
                    <th scope="col">Primary S/F/N</th>
                    <th scope="col">Primary cohort rate</th>
                    <th scope="col">Primary outside rate</th>
                    <th scope="col">Primary risk difference</th>
                    <th scope="col">Primary raw exact p</th>
                    <th scope="col">Primary BY exact p</th>
                    <th scope="col">Comparison S/F/N</th>
                    <th scope="col">Comparison cohort rate</th>
                    <th scope="col">Comparison outside rate</th>
                    <th scope="col">Comparison risk difference</th>
                    <th scope="col">Comparison raw exact p</th>
                    <th scope="col">Comparison BY exact p</th>
                    <th scope="col">Effect change</th>
                    <th scope="col">Relationship</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="comparison in outcome.result.comparisons"
                    :key="comparison.cohort_index"
                    class="cross-import-concordance-comparison"
                  >
                    <td>{{ comparison.cohort_index }}</td>
                    <td>{{ comparison.feature_key.long_to_medium }}</td>
                    <td>{{ comparison.feature_key.medium_to_short }}</td>
                    <td>{{ comparison.feature_key.long_to_short }}</td>
                    <td>{{ comparison.left_confirmation_diagnostic.cohort_counts.success_count }} / {{ comparison.left_confirmation_diagnostic.cohort_counts.failure_count }} / {{ comparison.left_confirmation_diagnostic.cohort_counts.observation_count }}</td>
                    <td>{{ featureRate(comparison.left_confirmation_diagnostic.cohort_success_rate) }}</td>
                    <td>{{ featureRate(comparison.left_confirmation_diagnostic.outside_success_rate) }}</td>
                    <td>{{ diagnosticEffect(comparison.left_confirmation_diagnostic) }}</td>
                    <td><code class="exact-probability">{{ exactProbability(comparison.left_confirmation_diagnostic.raw_p_value) }}</code></td>
                    <td><code class="exact-probability">{{ exactProbability(comparison.left_confirmation_diagnostic.adjusted_p_value) }}</code></td>
                    <td>{{ comparison.right_confirmation_diagnostic.cohort_counts.success_count }} / {{ comparison.right_confirmation_diagnostic.cohort_counts.failure_count }} / {{ comparison.right_confirmation_diagnostic.cohort_counts.observation_count }}</td>
                    <td>{{ featureRate(comparison.right_confirmation_diagnostic.cohort_success_rate) }}</td>
                    <td>{{ featureRate(comparison.right_confirmation_diagnostic.outside_success_rate) }}</td>
                    <td>{{ diagnosticEffect(comparison.right_confirmation_diagnostic) }}</td>
                    <td><code class="exact-probability">{{ exactProbability(comparison.right_confirmation_diagnostic.raw_p_value) }}</code></td>
                    <td><code class="exact-probability">{{ exactProbability(comparison.right_confirmation_diagnostic.adjusted_p_value) }}</code></td>
                    <td>{{ crossImportEffectChange(comparison) }}</td>
                    <td>{{ comparison.relationship }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
          <div v-else class="research-state research-state--error cross-import-concordance-item-error">
            <strong>{{ outcome.error }}</strong>
          </div>
        </li>
      </ol>
    </section>

    <section
      class="research-results multi-import-census-panel"
      aria-labelledby="multi-import-census-title"
    >
      <div class="panel-heading">
        <div>
          <p class="step-label">Ordered 2–4 import confirmation census</p>
          <h2 id="multi-import-census-title">
            Multi-import concordance census
          </h2>
        </div>
        <button
          class="button multi-import-census-action"
          type="button"
          :disabled="
            censusImportSelections.length < 2 ||
            censusImportSelections.length > 4 ||
            matrixSelections.length === 0
          "
          @click="evaluateMultiImportCensus"
        >
          Evaluate multi-import concordance census
        </button>
      </div>

      <p
        v-if="censusImportSelections.length < 2"
        class="research-state"
      >
        Select two to four distinct imports in the source panel. No import is
        selected and no request is issued automatically.
      </p>
      <p
        v-else-if="matrixSelections.length === 0"
        class="research-state"
      >
        Select one to four exact strategy identities from the primary run.
      </p>
      <p
        v-else-if="multiImportCensusState === 'selected'"
        class="research-state"
      >
        {{ censusImportSelections.length }} imports and
        {{ matrixSelections.length }} strategies are selected in manual order.
        Evaluation runs only from the explicit action.
      </p>
      <p
        v-if="multiImportCensusState === 'loading'"
        class="research-state"
      >
        Evaluating {{ matrixSelections.length }} strategy-specific censuses with
        the same ordered imports…
      </p>
      <div
        v-if="multiImportCensusState === 'partial'"
        class="research-state research-state--notice"
      >
        <strong>
          Some census requests are unavailable; successful results remain
          visible in strategy order.
        </strong>
        <button
          class="button button--quiet multi-import-census-retry"
          type="button"
          @click="evaluateMultiImportCensus"
        >
          Retry all
        </button>
      </div>
      <div
        v-if="multiImportCensusState === 'error'"
        class="research-state research-state--error"
      >
        <strong>All selected census requests failed with sanitized errors.</strong>
        <button
          class="button button--quiet multi-import-census-retry"
          type="button"
          @click="evaluateMultiImportCensus"
        >
          Retry all
        </button>
      </div>

      <ol
        v-if="multiImportCensusResults.length > 0"
        class="multi-import-census-result-list"
      >
        <li
          v-for="outcome in multiImportCensusResults"
          :key="matrixIdentity(outcome.selection)"
          class="multi-import-census-result-card"
        >
          <header>
            <span class="identity-kind">
              {{ outcome.selection.strategy.identity_kind }}
            </span>
            <h3>{{ outcome.selection.strategy.strategy_id }}</h3>
            <code>
              {{ outcome.selection.strategy.strategy_version }} · replicate
              {{ outcome.selection.strategy.replicate }}
            </code>
          </header>
          <div v-if="outcome.result">
            <dl class="identity-facts multi-import-census-facts">
              <div>
                <dt>Census status</dt>
                <dd>{{ outcome.result.census_status }}</dd>
              </div>
              <div>
                <dt>Ordered imports</dt>
                <dd>{{ outcome.result.imports.length }}</dd>
              </div>
              <div><dt>Pair count</dt><dd>{{ outcome.result.pair_count }}</dd></div>
              <div>
                <dt>Cohort rows</dt>
                <dd>{{ outcome.result.cohort_census_count }}</dd>
              </div>
              <div>
                <dt>Prefix</dt>
                <dd>{{ outcome.result.prefix_count }}</dd>
              </div>
              <div>
                <dt>Criterion</dt>
                <dd>{{ outcome.result.criterion.criterion }}</dd>
              </div>
            </dl>

            <ol
              class="multi-import-source-order"
              aria-label="Server import order"
            >
              <li
                v-for="item in outcome.result.imports"
                :key="item.metadata.import_identity_sha256"
              >
                <strong>{{ item.import_index + 1 }}</strong>
                <code>{{ item.metadata.import_identity_sha256 }}</code>
                <span>{{ item.holdout_status }}</span>
              </li>
            </ol>

            <div class="multi-import-pair-table-scroll">
              <table class="multi-import-pair-table">
                <caption>
                  Canonical pair matrix in caller-order index sequence.
                </caption>
                <thead>
                  <tr>
                    <th scope="col">Pair</th>
                    <th scope="col">Status</th>
                    <th scope="col">Same dataset</th>
                    <th scope="col">Same artifact</th>
                    <th scope="col">Overlap</th>
                    <th scope="col">Relation</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="pair in outcome.result.pairs"
                    :key="`${pair.left_import_index}:${pair.right_import_index}`"
                    class="multi-import-pair-row"
                  >
                    <td>
                      {{ pair.left_import_index + 1 }} →
                      {{ pair.right_import_index + 1 }}
                    </td>
                    <td>{{ pair.pair_status }}</td>
                    <td>
                      {{ pair.metadata.same_dataset_sha256 ? 'YES' : 'NO' }}
                    </td>
                    <td>
                      {{
                        pair.metadata.same_source_artifact_sha256 ? 'YES' : 'NO'
                      }}
                    </td>
                    <td>
                      {{
                        pair.confirmation_target_overlap?.overlap_count ??
                        'Unavailable'
                      }}
                    </td>
                    <td>
                      {{
                        pair.confirmation_target_overlap?.relation ??
                        'Unavailable'
                      }}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>

            <p
              v-if="outcome.result.census_status !== 'COMPLETE'"
              class="research-state multi-import-census-not-ready"
            >
              At least one temporal holdout is not ready. No partial cohort census
              was produced.
            </p>
            <div v-else class="multi-import-census-table-scroll">
              <table class="multi-import-census-table">
                <caption>
                  All 64 confirmation-only cohort rows in canonical server order.
                  Rows are presented exactly in that order.
                </caption>
                <thead>
                  <tr>
                    <th scope="col">Index</th>
                    <th scope="col">Long→Medium</th>
                    <th scope="col">Medium→Short</th>
                    <th scope="col">Long→Short</th>
                    <th scope="col">Higher</th>
                    <th scope="col">Equal</th>
                    <th scope="col">Lower</th>
                    <th scope="col">Unavailable</th>
                    <th scope="col">Neutral summary</th>
                    <th scope="col">Ordered per-import confirmation diagnostics</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="row in outcome.result.cohort_census"
                    :key="row.cohort_index"
                    class="multi-import-census-row"
                  >
                    <td>{{ row.cohort_index }}</td>
                    <td>{{ row.feature_key.long_to_medium }}</td>
                    <td>{{ row.feature_key.medium_to_short }}</td>
                    <td>{{ row.feature_key.long_to_short }}</td>
                    <td>{{ row.higher_count }}</td>
                    <td>{{ row.equal_count }}</td>
                    <td>{{ row.lower_count }}</td>
                    <td>{{ row.unavailable_count }}</td>
                    <td>{{ row.summary }}</td>
                    <td>
                      <ol class="multi-import-diagnostics">
                        <li
                          v-for="item in row.confirmation_diagnostics"
                          :key="item.import_identity_sha256"
                        >
                          <strong>{{ item.import_index + 1 }}</strong>
                          <span>
                            {{ item.diagnostic.relation_vs_outside }} · effect
                            {{ diagnosticEffect(item.diagnostic) }}
                          </span>
                          <code class="exact-probability">
                            raw
                            {{ exactProbability(item.diagnostic.raw_p_value) }} · BY
                            {{
                              exactProbability(
                                item.diagnostic.adjusted_p_value,
                              )
                            }}
                          </code>
                        </li>
                      </ol>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
          <div
            v-else
            class="research-state research-state--error multi-import-census-item-error"
          >
            <strong>{{ outcome.error }}</strong>
          </div>
        </li>
      </ol>
    </section>

    <aside v-if="detailState !== 'closed'" class="detail-panel" aria-labelledby="exact-detail-title">
      <div class="panel-heading">
        <div>
          <p class="step-label">Exact endpoint response</p>
          <h2 id="exact-detail-title">Strategy inspection</h2>
        </div>
        <button class="button button--quiet" type="button" @click="detailState = 'closed'; detail = null">Close</button>
      </div>
      <p v-if="detailState === 'loading'" class="research-state">Loading exact strategy identity…</p>
      <div v-else-if="detailState === 'ready' && detail" class="detail-content">
        <h3>{{ detail.strategy.strategy_id }}</h3>
        <p><code>{{ detail.strategy.strategy_version }} · replicate {{ detail.strategy.replicate }}</code></p>
        <p>{{ detail.status }} · {{ detail.source_observation_count }} source observations</p>
        <ol>
          <li v-for="window in detail.windows" :key="window.window_kind">
            <strong>{{ window.window_kind }} / {{ window.window_role }}</strong>
            <span>{{ exactRate(window) }}</span>
          </li>
        </ol>
      </div>
      <div v-else class="research-state research-state--error">
        <strong>{{ detailError }}</strong>
      </div>
    </aside>
  </section>
</template>

<style scoped>
.historical-workspace { padding: 64px 0 92px; }
.historical-heading { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 48px; align-items: end; margin-bottom: 36px; }
.historical-intro { max-width: 760px; margin-bottom: 0; color: var(--muted); font-size: 16px; line-height: 1.7; }
.research-guard { display: grid; min-width: 190px; padding: 18px; border: 1px solid rgb(242 197 114 / 34%); border-radius: 18px; background: rgb(42 34 19 / 42%); }
.research-guard span, .research-guard small, .step-label, .page-count, .explicit-action-note { color: var(--muted); font: 500 10px/1.3 'SFMono-Regular', Consolas, monospace; letter-spacing: .08em; text-transform: uppercase; }
.research-guard strong { margin: 13px 0 8px; color: var(--amber); font: 600 16px/1.2 'SFMono-Regular', Consolas, monospace; }
.research-panel, .research-results, .detail-panel { margin-bottom: 20px; padding: 26px; border: 1px solid var(--line); border-radius: 22px; background: linear-gradient(145deg, rgb(18 35 31 / 94%), rgb(10 23 20 / 96%)); box-shadow: 0 22px 60px rgb(0 0 0 / 16%); }
.panel-heading { display: flex; gap: 18px; align-items: center; justify-content: space-between; margin-bottom: 22px; }
.panel-heading__actions { display: flex; gap: 12px; align-items: center; }
.panel-heading h2 { margin-bottom: 0; color: var(--ink); font-size: 22px; letter-spacing: -.025em; }
.step-label { margin-bottom: 9px; color: var(--mint); }
.source-selector, .analysis-controls label { display: grid; gap: 8px; color: var(--muted); font-size: 11px; letter-spacing: .05em; text-transform: uppercase; }
.source-selector select, .analysis-controls select { width: 100%; min-height: 46px; padding: 10px 12px; border: 1px solid var(--line); border-radius: 11px; background: #081512; color: var(--ink); }
.research-pagination { display: flex; gap: 10px; align-items: center; justify-content: flex-end; margin-top: 16px; color: var(--muted); font-size: 11px; }
.source-facts, .identity-facts { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 1px; overflow: hidden; margin: 22px 0 0; border: 1px solid var(--line); border-radius: 14px; background: var(--line); }
.source-facts div, .identity-facts div { min-width: 0; padding: 14px; background: var(--surface); }
.source-facts dt, .source-facts dd, .identity-facts dt, .identity-facts dd { margin: 0; }
.source-facts dt, .identity-facts dt { color: var(--muted); font-size: 9px; letter-spacing: .08em; text-transform: uppercase; }
.source-facts dd, .identity-facts dd { margin-top: 8px; color: var(--ink); font-size: 12px; overflow-wrap: anywhere; }
.source-facts__identity { grid-column: 1 / -1; }
.source-facts__identity dd { display: flex; gap: 12px; align-items: center; justify-content: space-between; }
.copy-button { padding: 6px 9px; border: 1px solid var(--line); border-radius: 8px; background: transparent; color: var(--mint); cursor: pointer; }
.analysis-controls { display: grid; grid-template-columns: minmax(130px, .5fr) minmax(240px, 1fr) auto; gap: 14px; align-items: end; }
.research-state { display: flex; gap: 14px; align-items: center; justify-content: space-between; margin: 0; padding: 20px; border: 1px solid var(--line); border-radius: 14px; background: rgb(6 17 14 / 58%); color: var(--muted); line-height: 1.5; }
.research-state--notice { border-color: rgb(242 197 114 / 36%); color: var(--amber); }
.research-state--error { border-color: rgb(255 154 141 / 42%); color: var(--danger); }
.strategy-window-list { display: grid; gap: 18px; margin: 0; padding: 0; list-style: none; }
.strategy-window-card { padding: 22px; border: 1px solid var(--line); border-radius: 18px; background: rgb(7 18 15 / 62%); }
.strategy-window-card__header, .window-card header, .window-card footer { display: flex; gap: 14px; align-items: center; justify-content: space-between; }
.strategy-window-card__actions { display: flex; gap: 10px; align-items: center; }
.matrix-selector { display: inline-flex; gap: 8px; align-items: center; color: var(--muted); font-size: 11px; }
.matrix-selector input { accent-color: var(--mint); }
.strategy-window-card h3 { margin: 7px 0; color: var(--ink); font-size: 20px; overflow-wrap: anywhere; }
.identity-kind { color: var(--amber); font: 500 9px/1 'SFMono-Regular', Consolas, monospace; letter-spacing: .08em; }
.inspect-button { flex: 0 0 auto; }
.window-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; margin-top: 18px; }
.window-card { padding: 16px; border: 1px solid var(--line); border-radius: 14px; background: var(--surface); }
.window-card header span, .window-card header strong { display: block; }
.window-card header span { color: var(--mint); font: 600 11px/1.2 'SFMono-Regular', Consolas, monospace; }
.window-card header strong { margin-top: 5px; color: var(--muted); font-size: 9px; letter-spacing: .06em; }
.window-card header code { color: var(--muted); font-size: 10px; }
.exact-rate { margin: 18px 0; color: var(--ink); font: 650 28px/1 'SFMono-Regular', Consolas, monospace; }
.window-card dl { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 1px; overflow: hidden; margin: 0; border: 1px solid var(--line); border-radius: 10px; background: var(--line); }
.window-card dl div { padding: 9px; background: #0a1714; }
.window-card dt, .window-card dd { margin: 0; }
.window-card dt { color: var(--muted); font-size: 8px; text-transform: uppercase; }
.window-card dd { margin-top: 5px; color: var(--ink); font: 500 10px/1.3 'SFMono-Regular', Consolas, monospace; overflow-wrap: anywhere; }
.window-card footer { align-items: flex-start; flex-direction: column; margin-top: 14px; color: var(--muted); font-size: 10px; }
.zero-observation { margin: 18px 0 0; padding: 14px; border: 1px dashed var(--line); border-radius: 12px; color: var(--muted); }
.matrix-result-list { display: grid; gap: 20px; margin: 20px 0 0; padding: 0; list-style: none; }
.matrix-result-card { padding: 22px; border: 1px solid var(--line); border-radius: 18px; background: rgb(7 18 15 / 62%); }
.matrix-result-card h3 { margin: 7px 0; color: var(--ink); overflow-wrap: anywhere; }
.matrix-table-scroll { overflow-x: auto; margin-top: 18px; }
.stability-matrix { width: 100%; min-width: 1120px; border-collapse: collapse; color: var(--ink); font-size: 11px; }
.stability-matrix caption { padding: 0 0 12px; color: var(--muted); text-align: left; }
.stability-matrix th, .stability-matrix td { padding: 10px; border: 1px solid var(--line); vertical-align: top; }
.stability-matrix th { background: #0a1714; color: var(--mint); text-align: left; }
.matrix-cell-detail summary { color: var(--muted); cursor: pointer; }
.matrix-cell-detail dl { display: grid; gap: 7px; margin: 10px 0 0; }
.matrix-cell-detail dl div { display: grid; gap: 2px; }
.matrix-cell-detail dt { color: var(--muted); font-size: 8px; overflow-wrap: anywhere; }
.matrix-cell-detail dd { margin: 0; color: var(--ink); font: 500 10px/1.3 'SFMono-Regular', Consolas, monospace; }
.matrix-unavailable { color: var(--muted); font-size: 9px; line-height: 1.4; }
.matrix-item-error { margin-top: 16px; }
.feature-cohort-result-list { display: grid; gap: 20px; margin: 20px 0 0; padding: 0; list-style: none; }
.feature-cohort-result-card { padding: 22px; border: 1px solid var(--line); border-radius: 18px; background: rgb(7 18 15 / 62%); }
.feature-cohort-result-card h3 { margin: 7px 0; color: var(--ink); overflow-wrap: anywhere; }
.feature-cohort-table-scroll { overflow-x: auto; margin-top: 18px; }
.feature-cohort-table { width: 100%; min-width: 1500px; border-collapse: collapse; color: var(--ink); font-size: 10px; }
.feature-cohort-table caption { padding: 0 0 12px; color: var(--muted); text-align: left; }
.feature-cohort-table th, .feature-cohort-table td { padding: 9px; border: 1px solid var(--line); vertical-align: top; }
.feature-cohort-table th { background: #0a1714; color: var(--mint); text-align: left; }
.feature-cohort-table td { font-family: 'SFMono-Regular', Consolas, monospace; }
.feature-cohort-row--empty { color: var(--muted); }
.feature-cohort-item-error { margin-top: 16px; }
.feature-cohort-diagnostics-result-list { display: grid; gap: 20px; margin: 20px 0 0; padding: 0; list-style: none; }
.feature-cohort-diagnostics-result-card { padding: 22px; border: 1px solid var(--line); border-radius: 18px; background: rgb(7 18 15 / 62%); }
.feature-cohort-diagnostics-result-card h3 { margin: 7px 0; color: var(--ink); overflow-wrap: anywhere; }
.feature-cohort-diagnostics-table-scroll { overflow-x: auto; margin-top: 18px; }
.feature-cohort-diagnostics-table { width: 100%; min-width: 2100px; border-collapse: collapse; color: var(--ink); font-size: 10px; }
.feature-cohort-diagnostics-table caption { padding: 0 0 12px; color: var(--muted); text-align: left; }
.feature-cohort-diagnostics-table th, .feature-cohort-diagnostics-table td { padding: 9px; border: 1px solid var(--line); vertical-align: top; }
.feature-cohort-diagnostics-table th { background: #0a1714; color: var(--mint); text-align: left; }
.feature-cohort-diagnostics-table td { font-family: 'SFMono-Regular', Consolas, monospace; }
.exact-probability { display: block; max-width: 36rem; overflow-x: auto; white-space: pre; user-select: all; }
.feature-cohort-diagnostics-item-error { margin-top: 16px; }
.temporal-holdout-result-list { display: grid; gap: 20px; margin: 20px 0 0; padding: 0; list-style: none; }
.temporal-holdout-result-card { padding: 22px; border: 1px solid var(--line); border-radius: 18px; background: rgb(7 18 15 / 62%); }
.temporal-holdout-result-card h3 { margin: 7px 0; color: var(--ink); overflow-wrap: anywhere; }
.temporal-holdout-table { min-width: 2800px; }
.temporal-holdout-not-ready, .temporal-holdout-item-error { margin-top: 18px; }
.comparison-run-selector { margin-top: 14px; }
.census-import-selector { display: grid; gap: 10px; margin-top: 18px; padding: 16px; border: 1px solid var(--line); border-radius: 14px; }
.census-import-selector legend { padding: 0 8px; color: var(--mint); font-size: 11px; }
.census-import-option { display: flex; gap: 10px; align-items: flex-start; color: var(--muted); font-size: 11px; }
.census-import-option input { margin-top: 2px; accent-color: var(--mint); }
.census-import-option code { overflow-wrap: anywhere; }
.census-import-selection-order, .multi-import-source-order, .multi-import-diagnostics { display: grid; gap: 8px; margin: 4px 0 0; padding: 0; list-style: none; }
.census-import-selection-order li, .multi-import-source-order li { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; gap: 10px; align-items: center; padding: 10px; border: 1px solid var(--line); border-radius: 10px; color: var(--muted); font-size: 10px; }
.census-import-selection-order code, .multi-import-source-order code { overflow-wrap: anywhere; }
.cross-import-concordance-result-list { display: grid; gap: 20px; margin: 20px 0 0; padding: 0; list-style: none; }
.cross-import-concordance-result-card { padding: 22px; border: 1px solid var(--line); border-radius: 18px; background: rgb(7 18 15 / 62%); }
.cross-import-concordance-result-card h3 { margin: 7px 0; color: var(--ink); overflow-wrap: anywhere; }
.cross-import-concordance-table { min-width: 2800px; }
.cross-import-concordance-not-ready, .cross-import-concordance-item-error { margin-top: 18px; }
.multi-import-census-result-list { display: grid; gap: 20px; margin: 20px 0 0; padding: 0; list-style: none; }
.multi-import-census-result-card { padding: 22px; border: 1px solid var(--line); border-radius: 18px; background: rgb(7 18 15 / 62%); }
.multi-import-census-result-card h3 { margin: 7px 0; color: var(--ink); overflow-wrap: anywhere; }
.multi-import-source-order { margin-top: 18px; }
.multi-import-pair-table-scroll, .multi-import-census-table-scroll { overflow-x: auto; margin-top: 18px; }
.multi-import-pair-table, .multi-import-census-table { width: 100%; border-collapse: collapse; color: var(--ink); font-size: 10px; }
.multi-import-pair-table { min-width: 900px; }
.multi-import-census-table { min-width: 1900px; }
.multi-import-pair-table caption, .multi-import-census-table caption { padding: 0 0 12px; color: var(--muted); text-align: left; }
.multi-import-pair-table th, .multi-import-pair-table td, .multi-import-census-table th, .multi-import-census-table td { padding: 9px; border: 1px solid var(--line); vertical-align: top; }
.multi-import-pair-table th, .multi-import-census-table th { background: #0a1714; color: var(--mint); text-align: left; }
.multi-import-diagnostics li { display: grid; grid-template-columns: auto minmax(180px, 1fr) minmax(320px, 2fr); gap: 8px; align-items: start; padding: 8px; border: 1px solid var(--line); border-radius: 8px; }
.multi-import-census-not-ready, .multi-import-census-item-error { margin-top: 18px; }
.detail-panel { border-color: rgb(121 227 178 / 38%); }
.detail-content h3 { margin-bottom: 6px; color: var(--ink); }
.detail-content { color: var(--muted); }
.detail-content ol { display: grid; gap: 8px; padding: 0; list-style: none; }
.detail-content li { display: flex; gap: 16px; justify-content: space-between; padding: 12px; border: 1px solid var(--line); border-radius: 10px; }
.detail-content li strong { color: var(--ink); }
@media (max-width: 900px) {
  .historical-heading, .analysis-controls { grid-template-columns: 1fr; }
  .research-guard { min-width: 0; }
  .source-facts, .identity-facts, .window-grid { grid-template-columns: 1fr 1fr; }
}
@media (max-width: 620px) {
  .source-facts, .identity-facts, .window-grid, .window-card dl { grid-template-columns: 1fr; }
  .panel-heading, .strategy-window-card__header, .strategy-window-card__actions, .research-state { align-items: flex-start; flex-direction: column; }
  .source-facts__identity { grid-column: auto; }
  .source-facts__identity dd { align-items: flex-start; flex-direction: column; }
}
</style>
