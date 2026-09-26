import { hexSummary, helpPointLabel, type SafetyPick } from '../../lib/safety'
import { Icon } from '../ui/Icon'
import { FairnessNote } from './FairnessNote'

export interface SafetyPickCardProps {
  pick: SafetyPick
  dayLabel: string | null
  onClose: () => void
}

function CloseButton({ onClose }: { onClose: () => void }) {
  return (
    <button type="button" className="icon-btn ghost" aria-label="Close" onClick={onClose}>
      <Icon name="close" size={18} />
    </button>
  )
}

/** What a tapped hex or help point shows (the desktop hover tooltip says the same). */
export function SafetyPickCard({ pick, dayLabel, onClose }: SafetyPickCardProps) {
  if (pick.kind === 'help') {
    return (
      <section className="safety-pick panel" aria-label="Help point">
        <header className="safety-pick-head">
          <h2>Help point</h2>
          <CloseButton onClose={onClose} />
        </header>
        <p className="safety-pick-name">{helpPointLabel(pick.point)}</p>
        {pick.point.kind === 'blue_light' && (
          <p className="faint">Press the button on the pole to talk to campus police.</p>
        )}
        <p className="faint">
          In an emergency, <a href="tel:911">Call 911</a>.
        </p>
      </section>
    )
  }
  const summary = hexSummary(pick.hex, dayLabel)
  return (
    <section className="safety-pick panel" aria-label={summary.title}>
      <header className="safety-pick-head">
        <h2>{summary.title}</h2>
        <CloseButton onClose={onClose} />
      </header>
      <ul className="safety-pick-lines">
        {summary.lines.map((line) => (
          <li key={line}>{line}</li>
        ))}
      </ul>
      <FairnessNote />
    </section>
  )
}
