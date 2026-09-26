import { useId, useState } from 'react'
import { useDialog } from '../../hooks/useDialog'
import { useGeocode } from '../../hooks/useGeocode'
import { searchPlaces } from '../../lib/places'
import type { RoutineSuggestion, SavedKind } from '../../lib/routines'
import type { Place } from '../../state/urlState'
import { Icon } from '../ui/Icon'
import { PlaceSections } from './PlaceSections'

export type SearchField = 'to' | 'from' | 'home' | 'work'

const TITLES: Record<SearchField, string> = {
  to: 'Where to?',
  from: 'Choose a start',
  home: 'Set Home',
  work: 'Set Work',
}
const MAX_RESULTS = 6
const MIN_QUERY_CHARS = 2

type Result = Place & { note?: string }

function useResults(text: string): Result[] {
  const remote = useGeocode(text)
  const local = searchPlaces(text)
  return [
    ...local.map((l) => ({ lat: l.lat, lon: l.lon, label: l.label })),
    ...remote
      .filter((r) => !local.some((l) => l.label === r.label))
      .map((r) => ({ lat: r.lat, lon: r.lon, label: r.label, note: r.in_coverage ? r.address : 'Outside routing coverage' })),
  ].slice(0, MAX_RESULTS)
}

export interface SearchSheetProps {
  field: SearchField
  welcome: boolean
  onDismissWelcome: () => void
  /** Context line: why location is being asked for, or why a start must be picked. */
  note: string | null
  suggestions: ReadonlyArray<RoutineSuggestion>
  saved: Partial<Record<SavedKind, Place>>
  recents: ReadonlyArray<Place>
  canUseLocation: boolean
  onUseLocation: () => void
  onPick: (place: Place) => void
  onPickSuggestion: (s: RoutineSuggestion) => void
  onEditSaved: (kind: SavedKind) => void
  onClose: () => void
}

/** Full-screen place search (SRCH-01..04): type to search, or pick a routine, saved, recent, or popular place. */
export function SearchSheet(props: SearchSheetProps) {
  const { field } = props
  const [text, setText] = useState('')
  const titleId = useId()
  const listId = useId()
  const results = useResults(text)
  const searching = text.trim().length >= MIN_QUERY_CHARS
  useDialog(props.onClose)

  return (
    <div className="search-sheet" role="dialog" aria-modal="true" aria-labelledby={titleId}>
      <header className="search-head">
        <button type="button" className="icon-btn ghost" aria-label="Close search" onClick={props.onClose}>
          <Icon name="back" />
        </button>
        <h1 id={titleId} className="search-title">
          {TITLES[field]}
        </h1>
      </header>
      <div className="search-input-wrap">
        <Icon name="search" />
        <input
          className="search-input"
          role="combobox"
          aria-label="Search places"
          aria-expanded={searching && results.length > 0}
          aria-controls={listId}
          aria-autocomplete="list"
          placeholder="Search a place, building, or MARTA stop"
          autoFocus
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && results[0]) props.onPick(results[0])
          }}
        />
      </div>
      {props.welcome && (
        <aside className="welcome-line" aria-label="Welcome">
          <p>
            <strong>See traffic risk before you walk into it.</strong> Traffic risk only — not crime or personal
            safety.
          </p>
          <button type="button" className="icon-btn ghost" aria-label="Dismiss welcome" onClick={props.onDismissWelcome}>
            <Icon name="close" size={18} />
          </button>
        </aside>
      )}
      {props.note && <p className="search-note">{props.note}</p>}
      <div className="search-body">
        {field === 'from' && props.canUseLocation && !searching && (
          <button type="button" className="place-row place-row-location" onClick={props.onUseLocation}>
            <span className="place-icon" aria-hidden="true">
              <Icon name="locate" size={18} />
            </span>
            <span className="place-title">Your location</span>
          </button>
        )}
        {searching ? (
          <>
            <ul id={listId} role="listbox" className="place-list" aria-label="Results">
              {results.map((r) => (
                <li key={`${r.label}-${r.lat}`} role="option" aria-selected={false}>
                  <button type="button" className="place-row" onClick={() => props.onPick({ lat: r.lat, lon: r.lon, label: r.label })}>
                    <span className="place-icon" aria-hidden="true">
                      <Icon name="pin" size={18} />
                    </span>
                    <span className="place-text">
                      <span className="place-title">{r.label}</span>
                      {r.note && <span className="place-sub">{r.note}</span>}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
            {results.length === 0 && <p className="faint search-empty">No match nearby. Try a building or street name.</p>}
          </>
        ) : (
          <PlaceSections
            showPersonal={field === 'to'}
            suggestions={props.suggestions}
            saved={props.saved}
            recents={props.recents}
            onPick={props.onPick}
            onPickSuggestion={props.onPickSuggestion}
            onEditSaved={props.onEditSaved}
          />
        )}
      </div>
    </div>
  )
}
