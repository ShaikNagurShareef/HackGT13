import { useEffect, useRef, type KeyboardEvent } from 'react'
import { useDialog } from '../../hooks/useDialog'

type Props = {
  onFine: () => void
  onShareLocation: () => void
}

const FOCUSABLE = 'button, a[href]'

/** Keep Tab / Shift+Tab inside the dialog (WCAG 2.4.3); Escape is handled by useDialog. */
function trapTab(e: KeyboardEvent<HTMLElement>): void {
  if (e.key !== 'Tab') return
  const items = Array.from(e.currentTarget.querySelectorAll<HTMLElement>(FOCUSABLE))
  if (items.length === 0) return
  const first = items[0]
  const last = items[items.length - 1]
  if (e.shiftKey && document.activeElement === first) {
    e.preventDefault()
    last.focus()
  } else if (!e.shiftKey && document.activeElement === last) {
    e.preventDefault()
    first.focus()
  }
}

/** Check-in: the walker is past ETA + 10 min. Escape counts as "I'm fine" (snooze). */
export function CheckInDialog({ onFine, onShareLocation }: Props) {
  useDialog(onFine)
  const fine = useRef<HTMLButtonElement>(null)
  // After useDialog has recorded the opener, move focus to the least drastic choice.
  useEffect(() => fine.current?.focus(), [])

  return (
    <div className="checkin-backdrop">
      <section
        className="checkin panel"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="checkin-title"
        aria-describedby="checkin-detail"
        onKeyDown={trapTab}
      >
        <h2 id="checkin-title" className="checkin-title">
          Everything OK?
        </h2>
        <p id="checkin-detail" className="checkin-detail">
          You're past your expected arrival time. Let us know you're fine, or get help.
        </p>
        <div className="checkin-actions">
          <button ref={fine} type="button" className="btn primary" onClick={onFine}>
            I'm fine
          </button>
          <a className="btn checkin-call" href="tel:911">
            Call 911
          </a>
          <button type="button" className="btn" onClick={onShareLocation}>
            Share my location
          </button>
        </div>
      </section>
    </div>
  )
}
