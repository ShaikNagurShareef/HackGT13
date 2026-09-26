import type { Condition } from '../api/client'
import { BANDS, cssColor } from '../lib/bands'

export function ConditionsChip({
  cond,
  label,
  onChange,
}: {
  cond: Condition
  label: string
  onChange: (c: Condition) => void
}) {
  const options: ReadonlyArray<[Condition, string]> = [
    ['live', 'Live'],
    ['dry', 'Dry'],
    ['wet', 'Wet'],
  ]
  return (
    <div className="conditions" role="group" aria-label="Weather conditions">
      {options.map(([value, text]) => (
        <button key={value} type="button" className="chip" aria-pressed={cond === value} onClick={() => onChange(value)}>
          {value === 'wet' ? '☂ ' : ''}
          {text}
        </button>
      ))}
      <span className="faint conditions-label" aria-live="polite">
        {label}
      </span>
    </div>
  )
}

const DEPARTURES: ReadonlyArray<[string, string]> = [
  ['now', 'Now'],
  ['+15m', '+15 min'],
  ['+1h', '+1 h'],
]

export function DepartPicker({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const custom = !DEPARTURES.some(([v]) => v === value)
  return (
    <div className="depart" role="group" aria-label="Departure time">
      {DEPARTURES.map(([v, text]) => (
        <button key={v} type="button" className="chip" aria-pressed={value === v} onClick={() => onChange(v)}>
          {text}
        </button>
      ))}
      <label className={`chip ${custom ? 'active' : ''}`}>
        <span className="sr-only">Custom departure (Atlanta time)</span>
        <input
          type="datetime-local"
          className="depart-input"
          value={custom ? value.slice(0, 16) : ''}
          onChange={(e) => e.target.value && onChange(e.target.value)}
        />
      </label>
    </div>
  )
}

export function Legend() {
  return (
    <section className="legend panel" aria-label="Risk legend">
      <div className="legend-title">Traffic risk to pedestrians</div>
      <div className="legend-bar" aria-hidden="true">
        {Array.from({ length: 20 }, (_, i) => (
          <span key={i} style={{ background: cssColor(i * 5 + 2.5), height: 4 + i * 0.35 }} />
        ))}
      </div>
      <div className="legend-bands">
        {BANDS.map((b) => (
          <span key={b.band}>
            <span className="num">{b.min}</span> {b.band}
          </span>
        ))}
      </div>
      <div className="faint">Citywide 0–100 scale · thicker = higher</div>
    </section>
  )
}

export function TrustNote() {
  return (
    <p className="trust-note faint" role="note">
      Traffic risk estimate from historical crashes. Always stay alert.
    </p>
  )
}
