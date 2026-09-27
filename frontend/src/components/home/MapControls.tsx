import type { GeoStatus } from '../../lib/origin'
import { AskFab } from '../ask/AskFab'
import { Icon } from '../ui/Icon'

export interface MapControlsProps {
  onLayers: () => void
  onLocate: () => void
  geoStatus: GeoStatus
  /** Opens Ask PathPro; absent when Ask is unavailable (demo), which hides the agent button. */
  onAsk?: () => void
  /** Ask PathPro is open (the agent button reports it as expanded). */
  askOpen?: boolean
}

/** Right-edge map buttons: options (layers) up top, the GPS locate FAB, and the Ask PathPro agent. */
export function MapControls({ onLayers, onLocate, geoStatus, onAsk, askOpen = false }: MapControlsProps) {
  const off = geoStatus === 'denied' || geoStatus === 'unavailable'
  return (
    <>
      <button type="button" className="fab fab-layers" aria-label="Map options" onClick={onLayers}>
        <Icon name="layers" size={22} />
      </button>
      <button
        type="button"
        className={`fab fab-locate ${geoStatus === 'granted' ? 'is-live' : ''}`}
        aria-label={off ? 'Location is off' : 'Show my location'}
        aria-busy={geoStatus === 'locating'}
        onClick={onLocate}
      >
        <Icon name={off ? 'locateOff' : 'locate'} size={24} />
      </button>
      {onAsk && <AskFab onClick={onAsk} open={askOpen} />}
    </>
  )
}
