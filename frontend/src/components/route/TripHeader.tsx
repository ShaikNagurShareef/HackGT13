import type { Place } from '../../state/urlState'
import { Icon } from '../ui/Icon'

export interface TripHeaderProps {
  from: Place | null
  to: Place | null
  onEditFrom: () => void
  onEditTo: () => void
  onSwap: () => void
  onBack: () => void
}

/** Compact From/To header shown once a destination is chosen (tap a line to change it). */
export function TripHeader({ from, to, onEditFrom, onEditTo, onSwap, onBack }: TripHeaderProps) {
  const fromLabel = from?.label ?? 'Choose a start'
  const toLabel = to?.label ?? 'Choose a destination'
  return (
    <section className="trip-header panel" aria-label="Trip">
      <button type="button" className="icon-btn ghost" aria-label="Back to map" onClick={onBack}>
        <Icon name="back" />
      </button>
      <div className="trip-lines">
        <button type="button" className={`trip-line ${from ? '' : 'trip-line-missing'}`} onClick={onEditFrom}>
          <span className="trip-dot trip-dot-from" aria-hidden="true" />
          <span className="trip-key">From</span>
          <span className="trip-value">{fromLabel}</span>
        </button>
        <button type="button" className="trip-line" onClick={onEditTo}>
          <span className="trip-dot trip-dot-to" aria-hidden="true" />
          <span className="trip-key">To</span>
          <span className="trip-value">{toLabel}</span>
        </button>
      </div>
      <button type="button" className="icon-btn ghost" aria-label="Swap start and destination" onClick={onSwap}>
        <Icon name="swap" />
      </button>
    </section>
  )
}
