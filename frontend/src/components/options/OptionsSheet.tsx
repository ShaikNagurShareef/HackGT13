import { useId } from 'react'
import { useDialog } from '../../hooks/useDialog'
import type { TimelineProps } from '../Timeline'
import { Icon } from '../ui/Icon'
import { OptionsContent, type OptionsContentProps } from './OptionsContent'

export interface OptionsSheetProps extends OptionsContentProps {
  timeline: TimelineProps
  onAbout: () => void
  /** Ask PathPro (Backboard); absent in demo mode or when unavailable. */
  onAsk?: () => void
  onClose: () => void
}

/** Everything that is not "where to": conditions, time, map mode, Risk Tides, legend, privacy. */
export function OptionsSheet({ onAbout, onAsk, onClose, ...content }: OptionsSheetProps) {
  const titleId = useId()
  useDialog(onClose)

  return (
    <div className="scrim scrim-sheet" onClick={onClose}>
      <div
        className="options-sheet panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        onClick={(e) => e.stopPropagation()}
      >
        <header className="options-head">
          <h1 id={titleId}>Map options</h1>
          <button type="button" className="icon-btn ghost" aria-label="Close options" onClick={onClose} autoFocus>
            <Icon name="close" />
          </button>
        </header>
        <OptionsContent {...content} />
        <button type="button" className="link-btn" onClick={onAbout}>
          About PathPro
        </button>
        {onAsk && (
          <button type="button" className="link-btn" onClick={onAsk}>
            Ask PathPro
          </button>
        )}
      </div>
    </div>
  )
}
