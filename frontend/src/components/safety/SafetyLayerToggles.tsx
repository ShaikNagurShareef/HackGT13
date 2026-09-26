import { CRIME_LAYER_NAME, type SafetyLayers } from '../../lib/safety'

export interface SafetyLayerTogglesProps {
  layers: SafetyLayers
  onChange: (layers: SafetyLayers) => void
  /** Lighting / foot-traffic toggles appear only when the data has them. */
  hasLit: boolean
  hasBusy: boolean
}

type LayerKey = keyof SafetyLayers

/** Switch rows (native checkboxes, 44 px targets) for each personal-safety layer. */
export function SafetyLayerToggles({ layers, onChange, hasLit, hasBusy }: SafetyLayerTogglesProps) {
  const rows: ReadonlyArray<[LayerKey, string, boolean]> = [
    ['crimes', CRIME_LAYER_NAME, true],
    ['lit', 'Well-lit streets', hasLit],
    ['busy', 'Busier streets', hasBusy],
    ['help', 'Help points', true],
  ]
  return (
    <fieldset className="safety-toggles">
      <legend className="sr-only">Personal safety layers</legend>
      {rows
        .filter(([, , shown]) => shown)
        .map(([key, label]) => (
          <label key={key} className={`toggle-row toggle-${key}`}>
            <span>{label}</span>
            <input
              type="checkbox"
              className="switch"
              checked={layers[key]}
              onChange={(e) => onChange({ ...layers, [key]: e.target.checked })}
            />
          </label>
        ))}
    </fieldset>
  )
}
