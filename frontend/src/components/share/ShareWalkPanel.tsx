import type { NavMode } from '../../hooks/useNavigation'
import { useCheckIn } from '../../hooks/useCheckIn'
import { useShareWalk, type ShareWalkInput } from '../../hooks/useShareWalk'
import { CheckInDialog } from './CheckInDialog'
import { ShareWalkControl } from './ShareWalkControl'

/** Navigation always knows the time left, so the check-in has an ETA to work from. */
export type ShareWalkPanelProps = ShareWalkInput & { mode: NavMode; remainingS: number }

/**
 * Navigation add-on: "Share my walk" plus the local check-in. Mounted for the length of one
 * navigation, so ending navigation ends the shared walk and cancels the check-in. With `resume`,
 * it picks up the walk this tab was sharing before a reload.
 */
export function ShareWalkPanel({ mode, ...input }: ShareWalkPanelProps) {
  const share = useShareWalk(input)
  const checkIn = useCheckIn({ enabled: mode === 'gps', etaS: input.remainingS, finished: input.arrived })

  return (
    <>
      <ShareWalkControl
        phase={share.phase}
        notice={share.notice}
        onStart={() => void share.start()}
        onResend={() => void share.resend()}
        onStop={share.stop}
        onDismissNotice={share.clearNotice}
      />
      {checkIn.due && <CheckInDialog onFine={checkIn.snooze} onShareLocation={() => void share.resend()} />}
    </>
  )
}
