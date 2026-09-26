import { useId, useState } from 'react'
import type { Condition } from '../../api/client'
import { useDialog } from '../../hooks/useDialog'
import { ConditionsChip, DepartPicker, Legend } from '../Controls'
import { Timeline, type TimelineProps } from '../Timeline'
import { Icon } from '../ui/Icon'

export interface OptionsSheetProps {
  cond: Condition
  condLabel: string
  onCond: (c: Condition) => void
  depart: string
  onDepart: (d: string) => void
  cityAvailable: boolean
  cityMode: boolean
  onCityMode: (on: boolean) => void
  timeline: TimelineProps
  showReportsLegend: boolean
  onAbout: () => void
  onClearHistory: () => void
  onClose: () => void
}

/** Everything that is not "where to": conditions, time, map mode, Risk Tides, legend, privacy. */
export function OptionsSheet(props: OptionsSheetProps) {
  const titleId = useId()
  const [cleared, setCleared] = useState(false)
  useDialog(props.onClose)

  const handleClear = () => {
    props.onClearHistory()
    setCleared(true)
  }

  return (
    <div className="scrim scrim-sheet" onClick={props.onClose}>
      <div
        className="options-sheet panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        onClick={(e) => e.stopPropagation()}
      >
        <header className="options-head">
          <h1 id={titleId}>Map options</h1>
          <button type="button" className="icon-btn ghost" aria-label="Close options" onClick={props.onClose} autoFocus>
            <Icon name="close" />
          </button>
        </header>
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
        <section className="options-group">
          <h2>Risk Tides</h2>
          <Timeline {...props.timeline} />
        </section>
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
        <button type="button" className="link-btn" onClick={props.onAbout}>
          About PathPro
        </button>
      </div>
    </div>
  )
}
