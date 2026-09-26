import type { NavMode } from '../../hooks/useNavigation'
import { formatDistance, type NavInstruction } from '../../lib/navigation'
import { Icon } from '../ui/Icon'

export interface NavigationViewProps {
  instruction: NavInstruction | null
  mode: NavMode
  remainingS: number
  remainingM: number
  arrival: string
  arrived: boolean
  destination: string
  onEnd: () => void
  onDone: () => void
}

const SECONDS_PER_MIN = 60

/** Navigation mode chrome: the next thing in a big top banner, time left and End at the bottom. */
export function NavigationView(props: NavigationViewProps) {
  const { instruction } = props
  const tone = instruction?.tone ?? 'info'
  const minutes = Math.max(1, Math.round(props.remainingS / SECONDS_PER_MIN))
  return (
    <>
      <div className={`nav-banner nav-${tone}`} role="status" aria-live="polite">
        <span className="nav-banner-icon" aria-hidden="true">
          <Icon name={tone === 'alert' ? 'alert' : tone === 'arrive' ? 'flag' : 'play'} size={26} />
        </span>
        <div className="nav-banner-text">
          {instruction ? (
            <>
              <p className="nav-headline">{instruction.headline}</p>
              <p className="nav-detail">{instruction.detail}</p>
            </>
          ) : (
            <p className="nav-headline">Finding your position on the route…</p>
          )}
        </div>
        {props.mode === 'preview' && <span className="nav-badge">Preview walk</span>}
      </div>
      {props.arrived ? (
        <section className="nav-arrived panel" aria-label="You've arrived">
          <p className="nav-arrived-title">You've arrived</p>
          <p className="faint">{props.destination}</p>
          <button type="button" className="btn primary" onClick={props.onDone} autoFocus>
            Done
          </button>
        </section>
      ) : (
        <section className="nav-bar panel" aria-label="Trip progress">
          <div>
            <p className="nav-eta num">{minutes} min</p>
            <p className="faint num">
              {formatDistance(props.remainingM)} · arrive {props.arrival}
            </p>
          </div>
          <button type="button" className="btn end-btn" onClick={props.onEnd}>
            End
          </button>
        </section>
      )}
    </>
  )
}
