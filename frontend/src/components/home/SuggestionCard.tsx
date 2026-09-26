import type { RoutineSuggestion } from '../../lib/routines'
import { suggestionHeadline } from '../../lib/suggestion'
import { Icon } from '../ui/Icon'

export interface SuggestionCardProps {
  suggestion: RoutineSuggestion
  etaMin: number | null
  onGo: (s: RoutineSuggestion) => void
  onDismiss: () => void
}

/** One learned-routine card above the search pill: one tap plans the lower-risk route. */
export function SuggestionCard({ suggestion, etaMin, onGo, onDismiss }: SuggestionCardProps) {
  const eta = etaMin != null ? `~${etaMin} min · ` : ''
  return (
    <section className="suggestion-card panel" aria-label="Suggested trip">
      <span className="suggestion-icon" aria-hidden="true">
        <Icon name="spark" size={18} />
      </span>
      <div className="suggestion-text">
        <p className="suggestion-title">{suggestionHeadline(suggestion)}</p>
        <p className="suggestion-sub">{eta}lower-risk route one tap away</p>
      </div>
      <button type="button" className="btn primary small" onClick={() => onGo(suggestion)}>
        Go
      </button>
      <button type="button" className="icon-btn ghost small" aria-label="Dismiss suggestion" onClick={onDismiss}>
        <Icon name="close" size={16} />
      </button>
    </section>
  )
}
