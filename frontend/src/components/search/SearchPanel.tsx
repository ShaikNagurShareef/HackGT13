import { useId, useState } from 'react'
import { useGeocode } from '../../hooks/useGeocode'
import { searchPlaces } from '../../lib/places'
import type { RoutineSuggestion, SavedKind } from '../../lib/routines'
import type { Place } from '../../state/urlState'
import { Icon } from '../ui/Icon'
import { PlaceSections } from './PlaceSections'

export type SearchField = 'to' | 'from' | 'home' | 'work'

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

export interface SearchPanelProps {
  field: SearchField
  suggestions: ReadonlyArray<RoutineSuggestion>
  saved: Partial<Record<SavedKind, Place>>
  recents: ReadonlyArray<Place>
  canUseLocation: boolean
  onUseLocation: () => void
  onPick: (place: Place) => void
  onPickSuggestion: (s: RoutineSuggestion) => void
  onEditSaved: (kind: SavedKind) => void
  autoFocus?: boolean
}

/** Search input plus results (typing) or the place sections (empty): used in the sheet and the desktop sidebar. */
export function SearchPanel(props: SearchPanelProps) {
  const { field } = props
  const [text, setText] = useState('')
  const listId = useId()
  const results = useResults(text)
  const searching = text.trim().length >= MIN_QUERY_CHARS

  return (
    <>
      <div className="search-input-wrap">
        <Icon name="search" />
        <input
          className="search-input"
          role="combobox"
          aria-label="Search places"
          aria-expanded={searching && results.length > 0}
          aria-controls={listId}
          aria-autocomplete="list"
          placeholder="Search places or MARTA stops"
          autoFocus={props.autoFocus}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && results[0]) props.onPick(results[0])
          }}
        />
      </div>
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
    </>
  )
}
