import { useState } from 'react'
import type { Condition } from '../../api/client'
import { ConditionsChip, DepartPicker, Legend } from '../Controls'
import { Timeline, type TimelineProps } from '../Timeline'

export interface OptionsContentProps {
  cond: Condition
  condLabel: string
  onCond: (c: Condition) => void
  depart: string
  onDepart: (d: string) => void
  cityAvailable: boolean
  cityMode: boolean
  onCityMode: (on: boolean) => void
  /** Risk Tides lives here on phones; desktop docks it on the map instead. */
  timeline?: TimelineProps
  showReportsLegend: boolean
  onClearHistory: () => void
}

/** Conditions, departure, map mode, (Risk Tides), legend, and privacy: shared by the sheet and the sidebar. */
export function OptionsContent(props: OptionsContentProps) {
  const [cleared, setCleared] = useState(false)
  const handleClear = () => {
    props.onClearHistory()
    setCleared(true)
  }
  return (
    <>
      <section className="options-group">
        <h2>Conditions</h2>
        <ConditionsChip cond={props.cond} label={props.condLabel} onChange={props.onCond} />
      </section>
      <section className="options-group">
        <h2>Leaving</h2>
        <DepartPicker value={props.depart} onChange={props.onDepart} />
      </section>
      {props.cityAvailable && (
        <section className="options-group">
          <h2>Map</h2>
          <div className="conditions" role="group" aria-label="Map scale">
            <button type="button" className="chip" aria-pressed={!props.cityMode} onClick={() => props.onCityMode(false)}>
              Streets
            </button>
            <button type="button" className="chip" aria-pressed={props.cityMode} onClick={() => props.onCityMode(true)}>
              City Pulse
            </button>
          </div>
        </section>
      )}
      {props.timeline && (
        <section className="options-group">
          <h2>Risk Tides</h2>
          <Timeline {...props.timeline} />
        </section>
      )}
      <Legend reports={props.showReportsLegend} />
      <section className="options-group options-privacy">
        <h2>Privacy</h2>
        <p>Your walking patterns stay on this phone.</p>
        <p className="faint">PathPro learns your usual walks on this device only, to suggest them later.</p>
        <div className="options-row">
          <button type="button" className="btn small" onClick={handleClear}>
            Clear history
          </button>
          <span className="faint" role="status">
            {cleared ? 'History cleared' : ''}
          </span>
        </div>
      </section>
    </>
  )
}
