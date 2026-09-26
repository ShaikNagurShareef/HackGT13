import type { MapMode } from '../../lib/options'

export interface MapModePickerProps {
  mode: MapMode
  onMode: (mode: MapMode) => void
  cityAvailable: boolean
  safetyAvailable: boolean
}

/** Streets (traffic risk) · City Pulse · Personal safety — only the modes this bundle supports. */
export function MapModePicker({ mode, onMode, cityAvailable, safetyAvailable }: MapModePickerProps) {
  const modes: ReadonlyArray<[MapMode, string, boolean]> = [
    ['streets', 'Streets', true],
    ['city', 'City Pulse', cityAvailable],
    ['safety', 'Personal safety', safetyAvailable],
  ]
  return (
    <div className="conditions" role="group" aria-label="Map mode">
      {modes
        .filter(([, , shown]) => shown)
        .map(([value, label]) => (
          <button key={value} type="button" className="chip" aria-pressed={mode === value} onClick={() => onMode(value)}>
            {label}
          </button>
        ))}
    </div>
  )
}
