import type { TravelMode } from '../../api/schemas'
import {
  handoffFollowUp,
  handoffTitle,
  rideChipLabel,
  stationPlace,
  type MartaHandoff,
  type RideSuggestion,
} from '../../lib/handoff'
import type { Place } from '../../state/urlState'
import { Icon } from '../ui/Icon'

export interface HandoffCardProps {
  marta: MartaHandoff | null
  ride: RideSuggestion | null
  /** Plans the walk route to the boarding station. */
  onPlanStation: (place: Place) => void
  onTryMode: (mode: TravelMode) => void
}

/** Long walks: "Faster with MARTA" (walk to the nearest station) and a "Try Bike" chip. */
export function HandoffCard({ marta, ride, onPlanStation, onTryMode }: HandoffCardProps) {
  if (!marta && !ride) return null
  const followUp = marta ? handoffFollowUp(marta) : null
  return (
    <section className="handoff" aria-label="Faster options">
      {marta && (
        <button type="button" className="handoff-marta" onClick={() => onPlanStation(stationPlace(marta.board.station))}>
          <span className="handoff-icon" aria-hidden="true">
            <Icon name="train" size={20} />
          </span>
          <span className="handoff-text">
            <span className="handoff-title">{handoffTitle(marta)}</span>
            {followUp && <span className="handoff-sub faint">{followUp}</span>}
          </span>
        </button>
      )}
      {ride && (
        <button type="button" className="chip handoff-ride" onClick={() => onTryMode(ride.mode)}>
          <Icon name={ride.mode} size={16} />
          {rideChipLabel(ride)}
        </button>
      )}
    </section>
  )
}
