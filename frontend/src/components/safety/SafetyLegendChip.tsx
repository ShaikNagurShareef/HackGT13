import { useId, useState } from 'react'
import { CRIME_BANDS } from '../../api/safetySchemas'
import { CRIME_BAND_INFO, rgbCss } from '../../lib/safety'
import { SafetyLegend, type SafetyLegendProps } from './SafetyLegend'

const CHIP_GRADIENT = `linear-gradient(90deg, ${CRIME_BANDS.map((b) => rgbCss(CRIME_BAND_INFO[b].rgb)).join(', ')})`

/** Phone home, personal safety mode: the legend starts open so the fairness note is read first. */
export function SafetyLegendChip(props: Omit<SafetyLegendProps, 'compact'>) {
  const [open, setOpen] = useState(true)
  const legendId = useId()
  return (
    <div className="legend-chip-wrap safety-chip-wrap">
      {open && <SafetyLegend {...props} compact id={legendId} />}
      <button
        type="button"
        className="legend-chip"
        aria-expanded={open}
        aria-controls={legendId}
        onClick={() => setOpen((o) => !o)}
      >
        <span className="legend-chip-ramp" style={{ background: CHIP_GRADIENT }} aria-hidden="true" />
        <span>Personal safety legend</span>
      </button>
    </div>
  )
}
