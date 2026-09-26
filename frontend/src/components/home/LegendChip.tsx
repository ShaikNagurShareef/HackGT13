import { useState } from 'react'
import { Legend } from '../Controls'

/** Compact "Lower → High" gradient chip; tap to open the full numeric legend. */
export function LegendChip({ reports }: { reports: boolean }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="legend-chip-wrap">
      {open && <Legend reports={reports} />}
      <button type="button" className="legend-chip" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
        <span className="legend-chip-ramp" aria-hidden="true" />
        <span>
          Lower <span aria-hidden="true">→</span> High traffic risk
        </span>
      </button>
    </div>
  )
}
