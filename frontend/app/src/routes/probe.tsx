import { useState, type CSSProperties, type ReactNode } from 'react'
import { createRoute } from '@tanstack/react-router'
import { rootRoute } from './__root'

// B1 theme-lock probe: a wireframe of the decided builder layout rendered at
// the dense end (16 chains), with switchable palette candidates and a density
// toggle. Round 2: two-column Gear Browser (results + gear detail with image,
// contributor, and the gear's MODELS — selection is model-level), richer chain
// blocks with thumbnails, right-hand action column, back-to-site affordance.
// Session tooling, not product code; deleted when B1 decisions are locked.

type PaletteKey = 'a' | 'b' | 'c'
type DensityKey = 'compact' | 'cozy'

const PALETTES: Record<PaletteKey, { label: string; vars: Record<string, string> }> = {
  a: {
    label: 'A neutral/blue (current vendored)',
    vars: {
      '--p-bg-base': '#0a0a0a',
      '--p-bg-surface': '#141414',
      '--p-bg-elevated': '#1f1f1f',
      '--p-border': '#2a2a2a',
      '--p-border-strong': '#3a3a3a',
      '--p-text': '#f5f5f5',
      '--p-text-2': '#a1a1a1',
      '--p-text-3': '#666666',
      '--p-accent': '#3b82f6',
      '--p-accent-text': '#93b8f8',
      '--p-font': "'Inter', system-ui, sans-serif",
      '--p-block-di': '#3b82f6',
      '--p-block-fx': '#a855f7',
      '--p-block-amp': '#f59e0b',
      '--p-block-cab': '#22c55e',
    },
  },
  b: {
    label: 'B navy/orange (design-system gts)',
    vars: {
      '--p-bg-base': '#070714',
      '--p-bg-surface': '#0f0f23',
      '--p-bg-elevated': '#1a1a2e',
      '--p-border': '#2a2a40',
      '--p-border-strong': '#3a3450',
      '--p-text': '#f0ece7',
      '--p-text-2': '#a8a2b0',
      '--p-text-3': '#6a6478',
      '--p-accent': '#ff6b35',
      '--p-accent-text': '#ff9a70',
      '--p-font': "'Space Grotesk', system-ui, sans-serif",
      '--p-block-di': '#118ab2',
      '--p-block-fx': '#e94560',
      '--p-block-amp': '#ff6b35',
      '--p-block-cab': '#06d6a0',
    },
  },
  c: {
    label: 'C amp/amber (NAM XT register)',
    vars: {
      '--p-bg-base': '#0c0c0c',
      '--p-bg-surface': '#151514',
      '--p-bg-elevated': '#20201e',
      '--p-border': '#2c2c28',
      '--p-border-strong': '#403f38',
      '--p-text': '#f2f0ea',
      '--p-text-2': '#a6a294',
      '--p-text-3': '#6b6858',
      '--p-accent': '#e0a83c',
      '--p-accent-text': '#eec06a',
      '--p-font': "'Inter', system-ui, sans-serif",
      '--p-block-di': '#7aa2c9',
      '--p-block-fx': '#b085c9',
      '--p-block-amp': '#e0a83c',
      '--p-block-cab': '#8fb573',
    },
  },
}

const DENSITIES: Record<DensityKey, Record<string, string>> = {
  compact: {
    '--d-ctl': '24px',
    '--d-row': '24px',
    '--d-bar': '28px',
    '--d-text': '12px',
    '--d-text-sm': '11px',
    '--d-gap': '4px',
    '--d-pad': '8px',
  },
  cozy: {
    '--d-ctl': '28px',
    '--d-row': '28px',
    '--d-bar': '32px',
    '--d-text': '13px',
    '--d-text-sm': '12px',
    '--d-gap': '6px',
    '--d-pad': '10px',
  },
}

// Browser results: gear items (a capture pack for one physical amp), each
// holding 1..n MODELS. Many near-duplicates of the same amp is the realistic
// catalogue shape.
const GEAR_RESULTS = [
  { name: 'JCM800 2203 — full pack', by: 'SirCaptures', models: 14 },
  { name: 'JCM800 2203X 1982', by: 'tonehound', models: 6 },
  { name: 'JCM800 2204 modded', by: 'ampfarm', models: 22 },
  { name: 'JCM800 Studio SC20', by: 'beedoo', models: 3 },
  { name: 'JCM800 2203 KT88', by: 'valvestate', models: 9 },
  { name: 'JCM800 2210 channel A', by: 'sgear', models: 5 },
  { name: 'JCM800 2203 vintage 30w', by: 'tone3000', models: 11 },
  { name: 'JCM800 2204 half-stack', by: 'rigsmith', models: 8 },
  { name: 'JCM800 Zakk mod', by: 'ampfarm', models: 17 },
  { name: 'JCM800 2203 studio mic', by: 'micloxx', models: 4 },
  { name: 'JCM800 clone (Ceriatone)', by: 'diyamps', models: 12 },
  { name: 'JCM800 2203 hot-rodded', by: 'SirCaptures', models: 7 },
] as const

// Selected gear's models — what actually loads into a slot.
const GEAR_MODELS = [
  { name: 'Crunch ch · Gain 3 · Master 6', added: false },
  { name: 'Crunch ch · Gain 5 · Master 6', added: false },
  { name: 'Crunch ch · Gain 7 · Master 5', added: true },
  { name: 'Crunch ch · Gain 9 · Master 4', added: false },
  { name: 'Boost ch · Gain 4 · bright cap', added: false },
  { name: 'Boost ch · Gain 6 · bright cap', added: true },
  { name: 'Boost ch · Gain 8 · deep mod', added: false },
  { name: 'Boost ch · Gain 10 · deep mod', added: false },
] as const

const FX_OPTIONS = ['TS9 Tube Screamer · drive 4', 'Klon Centaur · gold', 'SD-1 · stock']
const AMP_OPTIONS = [
  { model: 'Crunch ch · Gain 7 · Master 5', gear: 'JCM800 2203 — full pack', by: 'SirCaptures' },
  { model: 'Boost ch · Gain 6 · bright cap', gear: 'JCM800 2203 — full pack', by: 'SirCaptures' },
]
const CAB_OPTIONS = ['Mesa 4x12 OS · SM57 cap edge', 'Marshall 1960A · R121 room']

function matrixRows(): { idx: number; label: string }[] {
  const fx = [...FX_OPTIONS.map((f) => f.split(' · ')[0]), null]
  const rows: { idx: number; label: string }[] = []
  let i = 0
  for (const f of fx)
    for (const a of AMP_OPTIONS)
      for (const c of CAB_OPTIONS)
        rows.push({
          idx: i++,
          label: [f, `JCM800 ${a.model.split(' · ').slice(0, 2).join(' ')}`, c.split(' · ')[0]]
            .filter(Boolean)
            .join('  +  '),
        })
  return rows
}

// Placeholder gear image: an amp-head suggestion drawn in SVG, tinted by hue.
function GearImage({ h, color }: { h: number; color: string }) {
  return (
    <svg viewBox="0 0 200 100" style={{ width: '100%', height: h, display: 'block' }} preserveAspectRatio="xMidYMid meet">
      <rect x="10" y="8" width="180" height="84" rx="6" fill="color-mix(in srgb, #000 55%, transparent)" stroke={color} strokeOpacity="0.5" />
      <rect x="18" y="16" width="164" height="38" rx="3" fill={color} fillOpacity="0.12" stroke={color} strokeOpacity="0.3" />
      <text x="100" y="40" textAnchor="middle" fill={color} fillOpacity="0.75" fontSize="15" fontFamily="inherit" fontWeight="600">
        GEAR PHOTO
      </text>
      {[40, 65, 90, 115, 140, 160].map((cx) => (
        <circle key={cx} cx={cx} cy="72" r="7" fill="none" stroke={color} strokeOpacity="0.55" strokeWidth="2" />
      ))}
    </svg>
  )
}

function Thumb({ color, size }: { color: string; size: number }) {
  return (
    <svg viewBox="0 0 40 40" width={size} height={size} style={{ flexShrink: 0, display: 'block' }}>
      <rect x="3" y="6" width="34" height="28" rx="3" fill={color} fillOpacity="0.14" stroke={color} strokeOpacity="0.5" />
      <circle cx="13" cy="26" r="3.5" fill="none" stroke={color} strokeOpacity="0.6" strokeWidth="1.5" />
      <circle cx="27" cy="26" r="3.5" fill="none" stroke={color} strokeOpacity="0.6" strokeWidth="1.5" />
      <rect x="9" y="11" width="22" height="7" rx="1.5" fill={color} fillOpacity="0.25" />
    </svg>
  )
}

export const probeRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/probe',
  component: ProbePage,
})

function ProbePage() {
  const [palette, setPalette] = useState<PaletteKey>('a')
  const [density, setDensity] = useState<DensityKey>('compact')
  const [matrixOpen, setMatrixOpen] = useState(true)
  const vars = { ...PALETTES[palette].vars, ...DENSITIES[density] } as CSSProperties

  return (
    <div
      style={{
        ...vars,
        fontFamily: 'var(--p-font)',
        fontSize: 'var(--d-text)',
        background: 'var(--p-bg-base)',
        color: 'var(--p-text)',
        position: 'fixed',
        inset: 0,
        display: 'flex',
        flexDirection: 'column',
        lineHeight: 1.35,
      }}
    >
      {/* top bar — carries the way back to the public site */}
      <div
        style={{
          height: 'var(--d-bar)',
          display: 'flex',
          alignItems: 'center',
          gap: 16,
          padding: '0 var(--d-pad)',
          borderBottom: '1px solid var(--p-border)',
          background: 'var(--p-bg-surface)',
          flexShrink: 0,
        }}
      >
        <span style={{ fontWeight: 600, letterSpacing: '0.02em' }}>GTS</span>
        <span style={{ color: 'var(--p-accent-text)' }}>Build</span>
        <span style={{ color: 'var(--p-text-2)' }}>Shootouts</span>
        <span style={{ color: 'var(--p-text-2)' }}>Library</span>
        <span style={{ color: 'var(--p-text-3)', fontSize: 'var(--d-text-sm)' }}>← back to site</span>
        <span style={{ marginLeft: 'auto', color: 'var(--p-text-3)', fontSize: 'var(--d-text-sm)' }}>⌘K</span>
        <span style={{ color: 'var(--p-text-2)' }}>ryan</span>
      </div>

      {/* middle: browser results | gear detail | canvas | actions */}
      <div style={{ flex: 1, display: 'flex', minHeight: 0 }}>
        {/* browser column 1: search + facets + results */}
        <div
          style={{
            width: 252,
            borderRight: '1px solid var(--p-border)',
            background: 'var(--p-bg-surface)',
            display: 'flex',
            flexDirection: 'column',
            flexShrink: 0,
          }}
        >
          <div
            style={{
              padding: 'var(--d-pad)',
              borderBottom: '1px solid var(--p-border)',
              display: 'flex',
              alignItems: 'baseline',
              gap: 6,
            }}
          >
            <span style={{ fontWeight: 600 }}>Gear Browser</span>
            <span style={{ color: 'var(--p-block-amp)', fontSize: 'var(--d-text-sm)', fontWeight: 600 }}>
              AMP slot
            </span>
          </div>
          <div style={{ padding: 'var(--d-pad)', display: 'flex', flexDirection: 'column', gap: 'var(--d-gap)' }}>
            <input
              placeholder="jcm800"
              style={{
                height: 'var(--d-ctl)',
                background: 'var(--p-bg-base)',
                border: '1px solid var(--p-border)',
                borderRadius: 4,
                color: 'var(--p-text)',
                padding: '0 8px',
                fontSize: 'var(--d-text)',
                fontFamily: 'inherit',
                outline: 'none',
              }}
            />
            <div style={{ display: 'flex', gap: 4 }}>
              {['NAM', 'IR', 'My Gear'].map((f, i) => (
                <span
                  key={f}
                  style={{
                    height: 20,
                    display: 'inline-flex',
                    alignItems: 'center',
                    padding: '0 8px',
                    borderRadius: 4,
                    fontSize: 'var(--d-text-sm)',
                    border: '1px solid',
                    borderColor: i === 0 ? 'var(--p-accent)' : 'var(--p-border)',
                    color: i === 0 ? 'var(--p-accent-text)' : 'var(--p-text-2)',
                    background: i === 0 ? 'color-mix(in srgb, var(--p-accent) 12%, transparent)' : 'transparent',
                  }}
                >
                  {f}
                </span>
              ))}
            </div>
          </div>
          <div style={{ flex: 1, overflowY: 'auto' }}>
            {GEAR_RESULTS.map((g, i) => (
              <div
                key={g.name}
                style={{
                  minHeight: 'calc(var(--d-row) + 10px)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  padding: '3px var(--d-pad)',
                  background: i === 0 ? 'color-mix(in srgb, var(--p-accent) 10%, transparent)' : 'transparent',
                  borderLeft: i === 0 ? '2px solid var(--p-accent)' : '2px solid transparent',
                }}
              >
                <Thumb color="var(--p-block-amp)" size={26} />
                <div style={{ minWidth: 0 }}>
                  <div style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{g.name}</div>
                  <div style={{ color: 'var(--p-text-3)', fontSize: 'var(--d-text-sm)' }}>
                    {g.by} · {g.models} models
                  </div>
                </div>
              </div>
            ))}
          </div>
          <div
            style={{
              padding: 'var(--d-pad)',
              borderTop: '1px solid var(--p-border)',
              color: 'var(--p-text-3)',
              fontSize: 'var(--d-text-sm)',
            }}
          >
            214 gear · 1,830 models
          </div>
        </div>

        {/* browser column 2: selected gear detail — image, summary, MODELS */}
        <div
          style={{
            width: 300,
            borderRight: '1px solid var(--p-border)',
            background: 'var(--p-bg-surface)',
            display: 'flex',
            flexDirection: 'column',
            flexShrink: 0,
          }}
        >
          <div style={{ padding: 'var(--d-pad)', borderBottom: '1px solid var(--p-border)' }}>
            <GearImage h={110} color="var(--p-block-amp)" />
            <div style={{ fontWeight: 600, marginTop: 6 }}>JCM800 2203 — full pack</div>
            <div style={{ color: 'var(--p-text-3)', fontSize: 'var(--d-text-sm)' }}>
              by SirCaptures · NAM · 48 kHz · added 2026-06-12
            </div>
            <div style={{ color: 'var(--p-text-2)', fontSize: 'var(--d-text-sm)', marginTop: 4 }}>
              1982 2203 head through the effects loop mod. Captures at stepped gain on
              both channels, SM57 + R121 blend reamped at unity.
            </div>
          </div>
          <div
            style={{
              padding: '4px var(--d-pad)',
              color: 'var(--p-text-3)',
              fontSize: 'var(--d-text-sm)',
              borderBottom: '1px solid var(--p-border)',
            }}
          >
            14 models — pick one or more for the slot
          </div>
          <div style={{ flex: 1, overflowY: 'auto' }}>
            {GEAR_MODELS.map((m) => (
              <div
                key={m.name}
                style={{
                  height: 'var(--d-row)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  padding: '0 var(--d-pad)',
                }}
              >
                <span
                  style={{
                    color: m.added ? 'var(--p-accent-text)' : 'var(--p-text-2)',
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                  }}
                >
                  {m.name}
                </span>
                <button
                  style={{
                    marginLeft: 'auto',
                    height: 'calc(var(--d-ctl) - 8px)',
                    padding: '0 8px',
                    flexShrink: 0,
                    background: m.added ? 'color-mix(in srgb, var(--p-accent) 15%, transparent)' : 'transparent',
                    border: '1px solid',
                    borderColor: m.added ? 'var(--p-accent)' : 'var(--p-border-strong)',
                    borderRadius: 3,
                    color: m.added ? 'var(--p-accent-text)' : 'var(--p-text-2)',
                    fontSize: 'var(--d-text-sm)',
                    fontFamily: 'inherit',
                    cursor: 'pointer',
                  }}
                >
                  {m.added ? 'added ✓' : '+ add'}
                </button>
              </div>
            ))}
          </div>
        </div>

        {/* canvas — the hero */}
        <div style={{ flex: 1, padding: 16, overflow: 'auto', minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginBottom: 12 }}>
            <span style={{ fontWeight: 600, fontSize: 'calc(var(--d-text) + 1px)' }}>Signal chain</span>
            <span style={{ color: 'var(--p-text-3)', fontSize: 'var(--d-text-sm)' }}>unsaved draft</span>
          </div>
          <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
            <StageCol label="DI" color="var(--p-block-di)">
              <BlockCard color="var(--p-block-di)" model="Strat DI — riff take 3" gear="own track · 0:42" />
            </StageCol>
            <Arrow />
            <StageCol label="FX" color="var(--p-block-fx)" note="+ none">
              {FX_OPTIONS.map((o) => {
                const [model, setting] = [o.split(' · ')[0]!, o.split(' · ')[1]!]
                return <BlockCard key={o} color="var(--p-block-fx)" model={model} gear={setting} />
              })}
            </StageCol>
            <Arrow />
            <StageCol label="AMP" color="var(--p-block-amp)">
              <BlockCard
                color="var(--p-block-amp)"
                model={AMP_OPTIONS[0]!.model}
                gear={`${AMP_OPTIONS[0]!.gear} · ${AMP_OPTIONS[0]!.by}`}
                selected
              />
              <BlockCard
                color="var(--p-block-amp)"
                model={AMP_OPTIONS[1]!.model}
                gear={`${AMP_OPTIONS[1]!.gear} · ${AMP_OPTIONS[1]!.by}`}
              />
              <AddBtn />
            </StageCol>
            <Arrow />
            <StageCol label="CAB" color="var(--p-block-cab)">
              {CAB_OPTIONS.map((o) => {
                const [model, setting] = [o.split(' · ')[0]!, o.split(' · ')[1]!]
                return <BlockCard key={o} color="var(--p-block-cab)" model={model} gear={setting} />
              })}
            </StageCol>
          </div>
        </div>

        {/* right action column */}
        <div
          style={{
            width: 216,
            borderLeft: '1px solid var(--p-border)',
            background: 'var(--p-bg-surface)',
            padding: 'var(--d-pad)',
            flexShrink: 0,
            display: 'flex',
            flexDirection: 'column',
            gap: 'var(--d-gap)',
          }}
        >
          <button
            style={{
              height: 'calc(var(--d-ctl) + 8px)',
              background: 'var(--p-accent)',
              color: '#0a0a0a',
              fontWeight: 600,
              border: 'none',
              borderRadius: 4,
              fontSize: 'calc(var(--d-text) + 1px)',
              fontFamily: 'inherit',
              cursor: 'pointer',
            }}
          >
            Run shootout
          </button>
          <div style={{ color: 'var(--p-text-3)', fontSize: 'var(--d-text-sm)', textAlign: 'center' }}>
            16 chains · ~4 min render
          </div>
          <button style={secondaryBtn}>Save for later</button>
          <button style={secondaryBtn}>Clear draft</button>
        </div>
      </div>

      {/* bottom matrix bar */}
      <div
        style={{
          borderTop: '1px solid var(--p-border)',
          background: 'var(--p-bg-surface)',
          flexShrink: 0,
          maxHeight: '42vh',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        <div
          style={{
            height: 'var(--d-bar)',
            display: 'flex',
            alignItems: 'center',
            gap: 12,
            padding: '0 var(--d-pad)',
            flexShrink: 0,
          }}
        >
          <button
            onClick={() => setMatrixOpen((v) => !v)}
            style={{
              background: 'none',
              border: 'none',
              color: 'var(--p-text-2)',
              fontSize: 'var(--d-text)',
              fontFamily: 'inherit',
              cursor: 'pointer',
              padding: 0,
            }}
          >
            {matrixOpen ? '▾' : '▸'} Matrix
          </button>
          <span style={{ color: 'var(--p-text-2)' }}>
            FX 3+none × AMP 2 × CAB 2 = <span style={{ color: 'var(--p-text)', fontWeight: 600 }}>16 chains</span>
          </span>
          <span style={{ color: 'var(--p-text-3)', fontSize: 'var(--d-text-sm)' }}>cap 16/16</span>
        </div>
        {matrixOpen && (
          <div style={{ overflowY: 'auto', borderTop: '1px solid var(--p-border)' }}>
            {matrixRows().map((r) => (
              <div
                key={r.idx}
                style={{
                  height: 'var(--d-row)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  padding: '0 var(--d-pad)',
                  borderBottom: '1px solid color-mix(in srgb, var(--p-border) 50%, transparent)',
                  fontSize: 'var(--d-text-sm)',
                }}
              >
                <span style={{ color: 'var(--p-text-3)', width: 20, textAlign: 'right' }}>{r.idx + 1}</span>
                <span style={{ color: 'var(--p-text-2)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {r.label}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* probe controls */}
      <div
        style={{
          position: 'fixed',
          left: 570,
          bottom: matrixOpen ? 'calc(42vh + 8px)' : 'calc(var(--d-bar) + 8px)',
          background: 'var(--p-bg-elevated)',
          border: '1px solid var(--p-border-strong)',
          borderRadius: 4,
          padding: '4px 6px',
          display: 'flex',
          gap: 4,
          fontSize: 'var(--d-text-sm)',
          zIndex: 10,
          opacity: 0.95,
          alignItems: 'center',
        }}
      >
        {(Object.keys(PALETTES) as PaletteKey[]).map((k) => (
          <button
            key={k}
            onClick={() => setPalette(k)}
            title={PALETTES[k].label}
            style={{
              background: k === palette ? 'color-mix(in srgb, var(--p-accent) 15%, transparent)' : 'none',
              border: '1px solid var(--p-border)',
              borderRadius: 3,
              color: k === palette ? 'var(--p-accent-text)' : 'var(--p-text-2)',
              fontFamily: 'inherit',
              fontSize: 'inherit',
              cursor: 'pointer',
              padding: '2px 8px',
            }}
          >
            {k.toUpperCase()}
          </button>
        ))}
        <span style={{ color: 'var(--p-text-3)' }}>|</span>
        {(Object.keys(DENSITIES) as DensityKey[]).map((k) => (
          <button
            key={k}
            onClick={() => setDensity(k)}
            style={{
              background: k === density ? 'color-mix(in srgb, var(--p-accent) 15%, transparent)' : 'none',
              border: '1px solid var(--p-border)',
              borderRadius: 3,
              color: k === density ? 'var(--p-accent-text)' : 'var(--p-text-2)',
              fontFamily: 'inherit',
              fontSize: 'inherit',
              cursor: 'pointer',
              padding: '2px 6px',
            }}
          >
            {k}
          </button>
        ))}
        <span style={{ color: 'var(--p-text-3)', marginLeft: 4 }}>{PALETTES[palette].label}</span>
      </div>
    </div>
  )
}

const secondaryBtn: CSSProperties = {
  height: 'var(--d-ctl)',
  background: 'transparent',
  border: '1px solid var(--p-border-strong)',
  borderRadius: 4,
  color: 'var(--p-text-2)',
  fontSize: 'var(--d-text)',
  fontFamily: 'inherit',
  cursor: 'pointer',
}

function StageCol({
  label,
  color,
  note,
  children,
}: {
  label: string
  color: string
  note?: string
  children: ReactNode
}) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--d-gap)', minWidth: 200 }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
        <span style={{ color, fontWeight: 700, fontSize: 'var(--d-text-sm)', letterSpacing: '0.08em' }}>
          {label}
        </span>
        {note && <span style={{ color: 'var(--p-text-3)', fontSize: 'var(--d-text-sm)' }}>{note}</span>}
      </div>
      {children}
    </div>
  )
}

// A chain block: model-level entry with thumbnail + gear/context line.
function BlockCard({
  model,
  gear,
  color,
  selected,
}: {
  model: string
  gear: string
  color: string
  selected?: boolean
}) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        padding: '5px 8px',
        background: 'var(--p-bg-elevated)',
        border: '1px solid',
        borderColor: selected ? 'var(--p-accent)' : 'var(--p-border)',
        borderRadius: 4,
        boxShadow: selected ? '0 0 0 1px var(--p-accent)' : 'none',
        overflow: 'hidden',
        width: 248,
      }}
    >
      <Thumb color={color} size={30} />
      <div style={{ minWidth: 0 }}>
        <div style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{model}</div>
        <div
          style={{
            color: 'var(--p-text-3)',
            fontSize: 'var(--d-text-sm)',
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
          }}
        >
          {gear}
        </div>
      </div>
    </div>
  )
}

function AddBtn() {
  return (
    <button
      style={{
        height: 'var(--d-ctl)',
        width: 248,
        background: 'transparent',
        border: '1px dashed var(--p-border-strong)',
        borderRadius: 4,
        color: 'var(--p-text-3)',
        fontSize: 'var(--d-text)',
        fontFamily: 'inherit',
        cursor: 'pointer',
      }}
    >
      + add option
    </button>
  )
}

function Arrow() {
  return (
    <span style={{ color: 'var(--p-text-3)', alignSelf: 'center', padding: '0 2px', marginTop: 18 }}>
      →
    </span>
  )
}
