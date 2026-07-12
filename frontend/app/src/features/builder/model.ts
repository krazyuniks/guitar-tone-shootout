import type { components } from '../../api/schema.ts'

export type SlotKind = 'fx' | 'amp' | 'cab'

export const RENDERABLE_PLATFORMS = ['nam', 'ir'] as const

export interface SlotOption {
  optionId: string
  userGearId: string
  gearType: 'pedal' | 'amp' | 'ir'
  displayName: string
  platform: (typeof RENDERABLE_PLATFORMS)[number]
  gearId: string
}

export interface Slot {
  kind: SlotKind
  options: SlotOption[]
  includeNone: boolean
}

export interface DiSelection {
  diTrackId: string
  displayName: string
  durationSeconds: number
  source: 'own' | 'shared'
}

export interface ChainDraft {
  name: string
  description: string | null
  di: DiSelection | null
  slots: { fx: Slot; amp: Slot; cab: Slot }
}

export interface BuilderUiState {
  selection: { slot: SlotKind; optionId: string } | null
  browserScope: SlotKind | 'di' | null
  dirty: boolean
}

export type RunState =
  | { phase: 'idle' }
  | { phase: 'assembling' }
  | { phase: 'observing'; shootoutId: string; parentJobId: string }

export interface MatrixCombination {
  index: number
  label: string
  fx: SlotOption | null
  amp: SlotOption
  cab: SlotOption
}

export type GuidanceRequest = components['schemas']['GuidanceRequest']
export type GuidanceResponse = components['schemas']['GuidanceResponse']
export type GuidanceValidationError = components['schemas']['HTTPValidationError']

export const DEFAULT_GUIDANCE: GuidanceResponse = {
  next_valid_gear_types: ['pedal', 'amp'],
  guidance_message: 'Choose the first piece of gear in your signal chain.',
  is_complete: false,
}

export function createEmptyChainDraft(): ChainDraft {
  return {
    name: '',
    description: null,
    di: null,
    slots: {
      fx: { kind: 'fx', options: [], includeNone: false },
      amp: { kind: 'amp', options: [], includeNone: false },
      cab: { kind: 'cab', options: [], includeNone: false },
    },
  }
}

export function expandMatrix(slots: ChainDraft['slots']): MatrixCombination[] {
  const fxOptions: Array<SlotOption | null> = slots.fx.options.length > 0
    ? [...slots.fx.options, ...(slots.fx.includeNone ? [null] : [])]
    : [null]
  const combinations: MatrixCombination[] = []

  for (const fx of fxOptions) {
    for (const amp of slots.amp.options) {
      for (const cab of slots.cab.options) {
        combinations.push({
          index: combinations.length,
          label: [fx, amp, cab]
            .filter((entry): entry is SlotOption => entry !== null)
            .map((entry) => entry.displayName)
            .join(' + '),
          fx,
          amp,
          cab,
        })
      }
    }
  }

  return combinations
}

export function isRunnableMatrixSize(combinationCount: number): boolean {
  return combinationCount >= 2 && combinationCount <= 16
}

export function runGate(
  draft: ChainDraft,
  guidance: GuidanceResponse,
  runState: RunState,
): boolean {
  return draft.di !== null
    && draft.slots.amp.options.length >= 1
    && draft.slots.cab.options.length >= 1
    && isRunnableMatrixSize(expandMatrix(draft.slots).length)
    && guidance.is_complete
    && runState.phase === 'idle'
}

export function projectGuidanceBlocks(draft: ChainDraft): GuidanceRequest['blocks'] {
  const blocks: GuidanceRequest['blocks'] = []
  if (draft.slots.fx.options.length > 0) blocks.push({ gear_type: 'pedal' })
  if (draft.slots.amp.options.length > 0) blocks.push({ gear_type: 'amp' })
  if (draft.slots.cab.options.length > 0) blocks.push({ gear_type: 'ir' })
  return blocks
}

export function guidanceAffordances(guidance: GuidanceResponse) {
  return {
    canAddFx: guidance.next_valid_gear_types.includes('pedal'),
    canAddAmp: guidance.next_valid_gear_types.includes('amp'),
    canAddCab: guidance.next_valid_gear_types.includes('ir'),
  }
}

export function mapOptionValidationErrors(
  draft: ChainDraft,
  response: GuidanceValidationError,
): Record<string, string> {
  const errors: Record<string, string> = {}

  for (const error of response.detail ?? []) {
    const [slots, slotKind, options, optionIndex, field] = error.loc
    if (
      slots !== 'slots'
      || (slotKind !== 'fx' && slotKind !== 'amp' && slotKind !== 'cab')
      || options !== 'options'
      || typeof optionIndex !== 'number'
      || field !== 'user_gear_id'
    ) continue

    const optionId = draft.slots[slotKind].options[optionIndex]?.optionId
    if (optionId) errors[optionId] = error.msg
  }

  return errors
}

export interface BuilderState {
  draft: ChainDraft
  ui: BuilderUiState
  run: RunState
  optionErrors: Record<string, string>
}

type Listener = () => void

export interface BuilderStore {
  getState(): BuilderState
  subscribe(listener: Listener): () => void
  setDraftDetails(name: string, description: string | null): void
  setDi(di: DiSelection | null): void
  addOption(slot: SlotKind, option: SlotOption): void
  removeOption(slot: SlotKind, optionId: string): void
  moveOption(slot: SlotKind, optionId: string, destinationIndex: number): void
  setIncludeNone(slot: SlotKind, includeNone: boolean): void
  setSelection(selection: BuilderUiState['selection']): void
  setBrowserScope(scope: BuilderUiState['browserScope']): void
  setRunState(run: RunState): void
  setOptionErrors(errors: Record<string, string>): void
  clearDraft(): void
}

const SLOT_GEAR_TYPES: Record<SlotKind, SlotOption['gearType']> = {
  fx: 'pedal',
  amp: 'amp',
  cab: 'ir',
}

export function createBuilderStore(initialDraft = createEmptyChainDraft()): BuilderStore {
  let state: BuilderState = {
    draft: initialDraft,
    ui: { selection: null, browserScope: null, dirty: false },
    run: { phase: 'idle' },
    optionErrors: {},
  }
  const listeners = new Set<Listener>()

  const update = (next: BuilderState) => {
    state = next
    listeners.forEach((listener) => listener())
  }
  const updateDraft = (draft: ChainDraft) => update({
    ...state,
    draft,
    ui: { ...state.ui, dirty: true },
  })
  const updateSlot = (slot: SlotKind, value: Slot) => updateDraft({
    ...state.draft,
    slots: { ...state.draft.slots, [slot]: value },
  })

  return {
    getState: () => state,
    subscribe(listener) {
      listeners.add(listener)
      return () => listeners.delete(listener)
    },
    setDraftDetails(name, description) {
      updateDraft({ ...state.draft, name, description })
    },
    setDi(di) {
      updateDraft({ ...state.draft, di })
    },
    addOption(slot, option) {
      if (option.gearType !== SLOT_GEAR_TYPES[slot]) {
        throw new Error(`${option.gearType} cannot be added to the ${slot} slot`)
      }
      updateSlot(slot, {
        ...state.draft.slots[slot],
        options: [...state.draft.slots[slot].options, option],
      })
    },
    removeOption(slot, optionId) {
      updateSlot(slot, {
        ...state.draft.slots[slot],
        options: state.draft.slots[slot].options.filter((option) => option.optionId !== optionId),
      })
    },
    moveOption(slot, optionId, destinationIndex) {
      const options = [...state.draft.slots[slot].options]
      const sourceIndex = options.findIndex((option) => option.optionId === optionId)
      if (sourceIndex < 0) throw new Error(`Unknown optionId: ${optionId}`)
      const [option] = options.splice(sourceIndex, 1)
      if (!option) throw new Error(`Unknown optionId: ${optionId}`)
      options.splice(destinationIndex, 0, option)
      updateSlot(slot, { ...state.draft.slots[slot], options })
    },
    setIncludeNone(slot, includeNone) {
      updateSlot(slot, {
        ...state.draft.slots[slot],
        includeNone: slot === 'fx' && includeNone,
      })
    },
    setSelection(selection) {
      update({ ...state, ui: { ...state.ui, selection } })
    },
    setBrowserScope(browserScope) {
      update({ ...state, ui: { ...state.ui, browserScope } })
    },
    setRunState(run) {
      update({ ...state, run })
    },
    setOptionErrors(optionErrors) {
      update({ ...state, optionErrors })
    },
    clearDraft() {
      update({
        draft: createEmptyChainDraft(),
        ui: { selection: null, browserScope: null, dirty: false },
        run: { phase: 'idle' },
        optionErrors: {},
      })
    },
  }
}
