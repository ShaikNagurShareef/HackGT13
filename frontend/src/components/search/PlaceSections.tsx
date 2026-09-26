import { useRef, type MouseEvent, type PointerEvent, type ReactNode } from 'react'
import { QUICK_PICKS } from '../../lib/places'
import type { RoutineSuggestion, SavedKind } from '../../lib/routines'
import type { Place } from '../../state/urlState'
import { Icon, type IconName } from '../ui/Icon'

const LONG_PRESS_MS = 550
const SAVED_KINDS: ReadonlyArray<{ kind: SavedKind; title: string; icon: IconName }> = [
  { kind: 'home', title: 'Home', icon: 'home' },
  { kind: 'work', title: 'Work', icon: 'work' },
]

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="search-section">
      <h2 className="search-section-title">{title}</h2>
      <ul className="place-list" aria-label={title}>
        {children}
      </ul>
    </section>
  )
}

function PlaceRow({ icon, title, sub, onPick }: { icon: IconName; title: string; sub?: string; onPick: () => void }) {
  return (
    <li>
      <button type="button" className="place-row" onClick={onPick}>
        <span className="place-icon" aria-hidden="true">
          <Icon name={icon} size={18} />
        </span>
        <span className="place-text">
          <span className="place-title">{title}</span>
          {sub && <span className="place-sub">{sub}</span>}
        </span>
      </button>
    </li>
  )
}

function useLongPress(onLongPress: () => void) {
  const timer = useRef<number | null>(null)
  const cancel = () => {
    if (timer.current != null) window.clearTimeout(timer.current)
    timer.current = null
  }
  return {
    onPointerDown: (e: PointerEvent) => {
      if (e.pointerType === 'mouse') return
      cancel()
      timer.current = window.setTimeout(onLongPress, LONG_PRESS_MS)
    },
    onPointerUp: cancel,
    onPointerLeave: cancel,
    onContextMenu: (e: MouseEvent) => {
      e.preventDefault()
      cancel()
      onLongPress()
    },
  }
}

function SavedRow({ kind, title, icon, place, onPick, onEdit }: {
  kind: SavedKind
  title: string
  icon: IconName
  place: Place | undefined
  onPick: (p: Place) => void
  onEdit: (kind: SavedKind) => void
}) {
  const press = useLongPress(() => onEdit(kind))
  if (!place) {
    return (
      <li>
        <button type="button" className="place-row place-row-empty" aria-label={`Set ${title}`} onClick={() => onEdit(kind)}>
          <span className="place-icon" aria-hidden="true">
            <Icon name={icon} size={18} />
          </span>
          <span className="place-text">
            <span className="place-title">Set {title}</span>
            <span className="place-sub">One tap to walk there later</span>
          </span>
        </button>
      </li>
    )
  }
  return (
    <li className="place-row-split">
      <button type="button" className="place-row" aria-label={`${title}: ${place.label}`} onClick={() => onPick(place)} {...press}>
        <span className="place-icon" aria-hidden="true">
          <Icon name={icon} size={18} />
        </span>
        <span className="place-text">
          <span className="place-title">{title}</span>
          <span className="place-sub">{place.label}</span>
        </span>
      </button>
      <button type="button" className="icon-btn ghost" aria-label={`Change ${title}`} onClick={() => onEdit(kind)}>
        <Icon name="pencil" size={18} />
      </button>
    </li>
  )
}

export interface PlaceSectionsProps {
  showPersonal: boolean
  suggestions: ReadonlyArray<RoutineSuggestion>
  saved: Partial<Record<SavedKind, Place>>
  recents: ReadonlyArray<Place>
  onPick: (place: Place) => void
  onPickSuggestion: (s: RoutineSuggestion) => void
  onEditSaved: (kind: SavedKind) => void
}

/** Empty-query search: learned routines, saved places, recents, and the curated quick picks. */
export function PlaceSections({ showPersonal, suggestions, saved, recents, onPick, onPickSuggestion, onEditSaved }: PlaceSectionsProps) {
  return (
    <>
      {showPersonal && suggestions.length > 0 && (
        <Section title="Suggested for now">
          {suggestions.map((s) => (
            <PlaceRow key={`${s.kind}-${s.to.label}`} icon="spark" title={s.to.label} sub={s.reason} onPick={() => onPickSuggestion(s)} />
          ))}
        </Section>
      )}
      {showPersonal && (
        <Section title="Saved">
          {SAVED_KINDS.map((k) => (
            <SavedRow key={k.kind} {...k} place={saved[k.kind]} onPick={onPick} onEdit={onEditSaved} />
          ))}
        </Section>
      )}
      {recents.length > 0 && (
        <Section title="Recent">
          {recents.map((p) => (
            <PlaceRow key={`${p.label}-${p.lat}-${p.lon}`} icon="clock" title={p.label} onPick={() => onPick(p)} />
          ))}
        </Section>
      )}
      <Section title="Popular near Georgia Tech">
        {QUICK_PICKS.map((p) => (
          <PlaceRow key={p.label} icon="pin" title={p.label} onPick={() => onPick({ lat: p.lat, lon: p.lon, label: p.label })} />
        ))}
      </Section>
    </>
  )
}
