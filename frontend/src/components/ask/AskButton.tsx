import { AgentGlyph } from './AgentGlyph'

export interface AskButtonProps {
  label: string
  onClick: () => void
  /** "pill": compact, inside street / route / area sheets. "entry": the Options and sidebar entry. */
  variant?: 'pill' | 'entry'
}

/** A labelled Ask PathPro button carrying the agent mark, e.g. "Ask about this street". */
export function AskButton({ label, onClick, variant = 'pill' }: AskButtonProps) {
  return (
    <button type="button" className={`ask-btn ask-btn-${variant}`} onClick={onClick}>
      <span className="ask-btn-glyph" aria-hidden="true">
        <AgentGlyph size={variant === 'entry' ? 18 : 16} />
      </span>
      <span>{label}</span>
    </button>
  )
}
