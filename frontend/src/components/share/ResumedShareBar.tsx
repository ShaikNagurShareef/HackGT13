import { useShareWalk } from '../../hooks/useShareWalk'
import { hasArrived } from '../../lib/navigation'
import type { GeoFix } from '../../lib/origin'
import type { StoredShareSession } from '../../lib/shareSession'
import { ShareWalkControl } from './ShareWalkControl'

type Props = {
  destination: StoredShareSession['destination']
  position: GeoFix | null
}

const noop = () => undefined

/**
 * A resumed walk while navigation isn't running (its route couldn't be restored yet): keeps
 * posting the GPS position, without an ETA, until Stop, arrival, or the link ends. It hands the
 * walk on to navigation instead of ending it when navigation starts.
 */
export function ResumedShareBar({ destination, position }: Props) {
  const share = useShareWalk({
    demo: false,
    destination,
    route: null,
    position: position ? [position.lon, position.lat] : null,
    accuracy: position?.accuracy ?? null,
    remainingS: null,
    arrived: position != null && hasArrived(position, destination),
    resume: true,
    endOnUnmount: false,
  })

  if (share.phase === 'idle' && !share.notice) return null
  return (
    <div className="share-resumed">
      <ShareWalkControl
        phase={share.phase}
        notice={share.notice}
        canStart={false}
        onStart={noop}
        onResend={() => void share.resend()}
        onStop={share.stop}
        onDismissNotice={share.clearNotice}
      />
    </div>
  )
}
