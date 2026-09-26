import { scopeLine } from '../../lib/safety'

export interface WelcomeToastProps {
  dataThrough: string
  /** The server has the personal-safety layer: the scope line mentions it. */
  safetyAvailable?: boolean
  onDismiss: () => void
}

/** First-run welcome: two lines, dismissible, never blocks the map (TRUST-02). */
export function WelcomeToast({ dataThrough, safetyAvailable = false, onDismiss }: WelcomeToastProps) {
  return (
    <section className="welcome-toast panel" aria-label="Welcome to PathPro">
      <p className="welcome-lede">See traffic risk before you walk into it.</p>
      <p className="welcome-scope">
        {scopeLine(safetyAvailable)} Crash data through {dataThrough}.
      </p>
      <button type="button" className="btn primary small" onClick={onDismiss}>
        Got it
      </button>
    </section>
  )
}
