import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import {
  DEFAULT_GUIDANCE,
  createBuilderStore,
  expandMatrix,
  guidanceAffordances,
  mapOptionValidationErrors,
  projectGuidanceBlocks,
  runGate,
  type ChainDraft,
  type SlotOption,
} from './model.ts'

function option(
  optionId: string,
  gearType: SlotOption['gearType'],
  displayName: string,
): SlotOption {
  return {
    optionId,
    userGearId: `user-${optionId}`,
    gearType,
    displayName,
    platform: gearType === 'ir' ? 'ir' : 'nam',
    gearId: `gear-${optionId}`,
  }
}

function draft(): ChainDraft {
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

describe('expandMatrix', () => {
  it('orders FX outermost, cab fastest, and the no-FX combination last', () => {
    const value = draft()
    value.slots.fx.options = [option('boost', 'pedal', 'Boost'), option('fuzz', 'pedal', 'Fuzz')]
    value.slots.fx.includeNone = true
    value.slots.amp.options = [option('clean', 'amp', 'Clean'), option('lead', 'amp', 'Lead')]
    value.slots.cab.options = [option('one12', 'ir', '1x12'), option('four12', 'ir', '4x12')]

    const combinations = expandMatrix(value.slots)

    assert.deepEqual(
      combinations.map(({ index, label, fx, amp, cab }) => [
        index,
        label,
        fx?.optionId ?? null,
        amp.optionId,
        cab.optionId,
      ]),
      [
        [0, 'Boost + Clean + 1x12', 'boost', 'clean', 'one12'],
        [1, 'Boost + Clean + 4x12', 'boost', 'clean', 'four12'],
        [2, 'Boost + Lead + 1x12', 'boost', 'lead', 'one12'],
        [3, 'Boost + Lead + 4x12', 'boost', 'lead', 'four12'],
        [4, 'Fuzz + Clean + 1x12', 'fuzz', 'clean', 'one12'],
        [5, 'Fuzz + Clean + 4x12', 'fuzz', 'clean', 'four12'],
        [6, 'Fuzz + Lead + 1x12', 'fuzz', 'lead', 'one12'],
        [7, 'Fuzz + Lead + 4x12', 'fuzz', 'lead', 'four12'],
        [8, 'Clean + 1x12', null, 'clean', 'one12'],
        [9, 'Clean + 4x12', null, 'clean', 'four12'],
        [10, 'Lead + 1x12', null, 'lead', 'one12'],
        [11, 'Lead + 4x12', null, 'lead', 'four12'],
      ],
    )
  })

  it('treats an empty FX slot as a factor of one', () => {
    const value = draft()
    value.slots.amp.options = [option('amp', 'amp', 'Amp')]
    value.slots.cab.options = [option('cab-a', 'ir', 'Cab A'), option('cab-b', 'ir', 'Cab B')]

    assert.deepEqual(
      expandMatrix(value.slots).map(({ label, fx }) => [label, fx]),
      [['Amp + Cab A', null], ['Amp + Cab B', null]],
    )
  })

  it('reports the 2..16 cap through the Run gate', () => {
    const value = draft()
    value.di = { diTrackId: 'di', displayName: 'DI', durationSeconds: 3, source: 'own' }
    value.slots.amp.options = Array.from({ length: 4 }, (_, index) => option(`amp-${index}`, 'amp', `Amp ${index}`))
    value.slots.cab.options = Array.from({ length: 4 }, (_, index) => option(`cab-${index}`, 'ir', `Cab ${index}`))
    const complete = { ...DEFAULT_GUIDANCE, is_complete: true }

    assert.equal(runGate(value, complete, { phase: 'idle' }), true)
    value.slots.fx.options.push(option('fx', 'pedal', 'FX'))
    value.slots.fx.includeNone = true
    assert.equal(runGate(value, complete, { phase: 'idle' }), false)
  })

  it('requires the DI, both fixed slots, complete guidance, and an idle run state', () => {
    const value = draft()
    value.di = { diTrackId: 'di', displayName: 'DI', durationSeconds: 3, source: 'own' }
    value.slots.amp.options = [option('amp-a', 'amp', 'Amp A'), option('amp-b', 'amp', 'Amp B')]
    value.slots.cab.options = [option('cab', 'ir', 'Cab')]
    const complete = { ...DEFAULT_GUIDANCE, is_complete: true }

    assert.equal(runGate(value, complete, { phase: 'idle' }), true)
    assert.equal(runGate({ ...value, di: null }, complete, { phase: 'idle' }), false)
    assert.equal(runGate(value, DEFAULT_GUIDANCE, { phase: 'idle' }), false)
    assert.equal(runGate(value, complete, { phase: 'assembling' }), false)
    assert.equal(runGate({
      ...value,
      slots: { ...value.slots, amp: { ...value.slots.amp, options: [] } },
    }, complete, { phase: 'idle' }), false)
    assert.equal(runGate({
      ...value,
      slots: { ...value.slots, cab: { ...value.slots.cab, options: [] } },
    }, complete, { phase: 'idle' }), false)
  })
})

describe('guidance', () => {
  it('projects one representative block per non-empty slot in template order', () => {
    const value = draft()
    value.slots.fx.options = [option('fx-a', 'pedal', 'FX A'), option('fx-b', 'pedal', 'FX B')]
    value.slots.amp.options = [option('amp', 'amp', 'Amp')]
    value.slots.cab.options = [option('cab', 'ir', 'Cab')]

    assert.deepEqual(projectGuidanceBlocks(value), [
      { gear_type: 'pedal' },
      { gear_type: 'amp' },
      { gear_type: 'ir' },
    ])
    assert.deepEqual(guidanceAffordances(DEFAULT_GUIDANCE), {
      canAddFx: true,
      canAddAmp: true,
      canAddCab: false,
    })
  })
})

describe('builder store', () => {
  it('enforces includeNone as an FX-only invariant', () => {
    const store = createBuilderStore()

    store.setIncludeNone('fx', true)
    store.setIncludeNone('amp', true)

    assert.equal(store.getState().draft.slots.fx.includeNone, true)
    assert.equal(store.getState().draft.slots.amp.includeNone, false)
  })

  it('maps assembly validation locations to stable option ids', () => {
    const value = draft()
    value.slots.amp.options = [
      option('amp-a', 'amp', 'Amp A'),
      option('amp-b', 'amp', 'Amp B'),
    ]

    assert.deepEqual(mapOptionValidationErrors(value, {
      detail: [{
        loc: ['slots', 'amp', 'options', 1, 'user_gear_id'],
        msg: 'Capture is not renderable',
        type: 'value_error',
      }],
    }), { 'amp-b': 'Capture is not renderable' })
  })
})
