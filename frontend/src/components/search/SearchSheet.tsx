import { useId } from 'react'
import { useDialog } from '../../hooks/useDialog'
import { scopeLine } from '../../lib/safety'
import { Icon } from '../ui/Icon'
import { SearchPanel, type SearchField, type SearchPanelProps } from './SearchPanel'

export type { SearchField } from './SearchPanel'

const TITLES: Record<SearchField, string> = {
  to: 'Where to?',
  from: 'Choose a start',
  home: 'Set Home',
  work: 'Set Work',
}

export interface SearchSheetProps extends Omit<SearchPanelProps, 'autoFocus'> {
  welcome: boolean
  onDismissWelcome: () => void
  /** Context line: why location is being asked for, or why a start must be picked. */
  note: string | null
  onClose: () => void
  /** The server has the personal-safety layer: the welcome line says so. */
  safetyAvailable?: boolean
}

/** Full-screen place search (SRCH-01..04): type to search, or pick a routine, saved, recent, or popular place. */
export function SearchSheet({ welcome, onDismissWelcome, note, onClose, safetyAvailable = false, ...panel }: SearchSheetProps) {
  const titleId = useId()
  useDialog(onClose)

  return (
    <div className="search-sheet" role="dialog" aria-modal="true" aria-labelledby={titleId}>
      <header className="search-head">
        <button type="button" className="icon-btn ghost" aria-label="Close search" onClick={onClose}>
          <Icon name="back" />
        </button>
        <h1 id={titleId} className="search-title">
          {TITLES[panel.field]}
        </h1>
      </header>
      {welcome && (
        <aside className="welcome-line" aria-label="Welcome">
          <p>
            <strong>See traffic risk before you walk into it.</strong> {scopeLine(safetyAvailable)}
          </p>
          <button type="button" className="icon-btn ghost" aria-label="Dismiss welcome" onClick={onDismissWelcome}>
            <Icon name="close" size={18} />
          </button>
        </aside>
      )}
      {note && <p className="search-note">{note}</p>}
      <SearchPanel {...panel} autoFocus />
    </div>
  )
}
