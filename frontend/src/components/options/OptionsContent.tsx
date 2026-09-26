import { useState } from 'react'
import type { Condition } from '../../api/client'
import type { HelpPoint, RoutePreference } from '../../api/safetySchemas'
import type { MapMode } from '../../lib/options'
import type { SafetyLayers, SafetyPick } from '../../lib/safety'
import { ConditionsChip, DepartPicker, Legend } from '../Controls'
import { RoutePreferencePicker } from '../safety/RoutePreferencePicker'
import { SafetyHelpList } from '../safety/SafetyHelpList'
import { SafetyLayerToggles } from '../safety/SafetyLayerToggles'
import { SafetyLegend, type SafetyLegendProps } from '../safety/SafetyLegend'
import { Timeline, type TimelineProps } from '../Timeline'
import { MapModePicker } from './MapModePicker'

/** Personal-safety controls; null when the server has no safety layer (older bundles, offline demo). */
export interface SafetyOptions {
  legend: SafetyLegendProps
  onLayers: (layers: SafetyLayers) => void
  hasLit: boolean
  hasBusy: boolean
  /** Help points in view: listed as buttons so each is reachable without the map. */
  helpPoints: ReadonlyArray<HelpPoint>
  onPickHelp: (pick: SafetyPick) => void
  prefer: RoutePreference
  onPrefer: (prefer: RoutePreference) => void
}

export interface OptionsContentProps {
  cond: Condition
  condLabel: string
  onCond: (c: Condition) => void
  depart: string
  onDepart: (d: string) => void
  cityAvailable: boolean
  mapMode: MapMode
  onMapMode: (mode: MapMode) => void
  safety: SafetyOptions | null
  /** Risk Tides lives here on phones; desktop docks it on the map instead. */
  timeline?: TimelineProps
  showReportsLegend: boolean
  onClearHistory: () => void
}

/** Conditions, departure, route preference, map mode, (Risk Tides), legend, and privacy: sheet and sidebar. */
export function OptionsContent(props: OptionsContentProps) {
  const [cleared, setCleared] = useState(false)
  const handleClear = () => {
    props.onClearHistory()
    setCleared(true)
  }
  const { safety } = props
  const safetyMode = props.mapMode === 'safety' && safety != null
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
      {safety && (
        <section className="options-group">
          <h2>Route preference</h2>
          <RoutePreferencePicker value={safety.prefer} onChange={safety.onPrefer} />
        </section>
      )}
      {(props.cityAvailable || safety) && (
        <section className="options-group">
          <h2>Map</h2>
          <MapModePicker mode={props.mapMode} onMode={props.onMapMode} cityAvailable={props.cityAvailable} safetyAvailable={safety != null} />
          {safetyMode && (
            <SafetyLayerToggles layers={safety.legend.layers} onChange={safety.onLayers} hasLit={safety.hasLit} hasBusy={safety.hasBusy} />
          )}
          {safetyMode && safety.legend.layers.help && <SafetyHelpList points={safety.helpPoints} onPick={safety.onPickHelp} />}
        </section>
      )}
      {props.timeline && (
        <section className="options-group">
          <h2>Risk Tides</h2>
          <Timeline {...props.timeline} />
        </section>
      )}
      {safetyMode ? <SafetyLegend {...safety.legend} /> : <Legend reports={props.showReportsLegend} />}
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
