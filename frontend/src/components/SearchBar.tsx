import { useId, useState } from 'react'
import { QUICK_PICKS, searchPlaces, type NamedPlace } from '../lib/places'
import type { Place } from '../state/urlState'

interface FieldProps {
  label: string
  value: Place | null
  placeholder: string
  onPick: (p: Place | null) => void
}

function PlaceField({ label, value, placeholder, onPick }: FieldProps) {
  const [text, setText] = useState('')
  const [open, setOpen] = useState(false)
  const listId = useId()
  const results: NamedPlace[] = searchPlaces(text)
  const showEmpty = open && text.trim().length >= 2 && results.length === 0

  const pick = (p: Place) => {
    onPick({ lat: p.lat, lon: p.lon, label: p.label })
    setText('')
    setOpen(false)
  }

  return (
    <div className="place-field">
      <label className="place-label faint" htmlFor={`${listId}-input`}>
        {label}
      </label>
      <input
        id={`${listId}-input`}
        className="place-input"
        role="combobox"
        aria-expanded={open && results.length > 0}
        aria-controls={listId}
        aria-autocomplete="list"
        placeholder={value?.label ?? placeholder}
        value={text}
        onChange={(e) => {
          setText(e.target.value)
          setOpen(true)
        }}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && results[0]) pick(results[0])
          if (e.key === 'Escape') setOpen(false)
        }}
      />
      {value && !text && (
        <button type="button" className="clear-btn" aria-label={`Clear ${label.toLowerCase()}`} onClick={() => onPick(null)}>
          ×
        </button>
      )}
      {open && results.length > 0 && (
        <ul id={listId} role="listbox" className="suggestions panel">
          {results.map((r) => (
            <li key={r.label} role="option" aria-selected={false}>
              <button type="button" onMouseDown={(e) => e.preventDefault()} onClick={() => pick(r)}>
                {r.label}
              </button>
            </li>
          ))}
        </ul>
      )}
      {showEmpty && <p className="suggestions-empty faint">No match nearby. Try a building or street name.</p>}
    </div>
  )
}

export interface SearchBarProps {
  from: Place | null
  to: Place | null
  onFrom: (p: Place | null) => void
  onTo: (p: Place | null) => void
  onSwap: () => void
}

export function SearchBar({ from, to, onFrom, onTo, onSwap }: SearchBarProps) {
  const target = from ? onTo : onFrom
  return (
    <section className="search panel" aria-label="Plan a walk">
      <div className="search-fields">
        <PlaceField label="From" value={from} placeholder="Choose a starting point" onPick={onFrom} />
        <button type="button" className="icon-btn swap" aria-label="Swap origin and destination" onClick={onSwap}>
          ⇅
        </button>
        <PlaceField label="To" value={to} placeholder="Where to?" onPick={onTo} />
      </div>
      <div className="quick-picks" role="group" aria-label={`Quick picks for ${from ? 'destination' : 'origin'}`}>
        {QUICK_PICKS.map((p) => (
          <button key={p.label} type="button" className="chip" onClick={() => target({ lat: p.lat, lon: p.lon, label: p.label })}>
            {p.label}
          </button>
        ))}
      </div>
    </section>
  )
}
