import { useState } from 'react'
import { cssColor } from '../../lib/bands'
import { Legend } from '../Controls'

const RAMP_STOPS = [0, 25, 50, 75, 100]
const RAMP_GRADIENT = `linear-gradient(90deg, ${RAMP_STOPS.map(cssColor).join(', ')})`

/** Compact "Lower → High" gradient chip; tap to open the full numeric legend. */
export function LegendChip({ reports, title }: { reports: boolean; title?: string }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="legend-chip-wrap">
      {open && <Legend reports={reports} title={title} />}
      <button type="button" className="legend-chip" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
        <span className="legend-chip-ramp" style={{ background: RAMP_GRADIENT }} aria-hidden="true" />
        <span>
          Lower <span aria-hidden="true">→</span> High traffic risk
        </span>
      </button>
    </div>
  )
}
