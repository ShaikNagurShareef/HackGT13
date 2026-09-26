import type { RoutePreference } from '../../api/safetySchemas'

export interface RoutePreferencePickerProps {
  value: RoutePreference
  onChange: (value: RoutePreference) => void
}

/** Lower traffic risk (default) or well-lit & busier streets. Crime is never a routing input. */
export function RoutePreferencePicker({ value, onChange }: RoutePreferencePickerProps) {
  return (
    <>
      <div className="conditions" role="group" aria-label="Route preference">
        <button type="button" className="chip" aria-pressed={value === 'lower_traffic_risk'} onClick={() => onChange('lower_traffic_risk')}>
          Lower traffic risk
        </button>
        <button type="button" className="chip" aria-pressed={value === 'lit_and_busy'} onClick={() => onChange('lit_and_busy')}>
          Well-lit &amp; busier <span className="chip-note">after dark</span>
        </button>
      </div>
      <p className="faint preference-note">
        Well-lit &amp; busier favors street lighting and foot traffic. Reported crimes are never used to choose routes.
      </p>
    </>
  )
}
