import { useId, useState } from 'react'
import type { ModeInfo, TravelMode } from '../../api/schemas'
import { MODE_LABELS, UNAVAILABLE_NOTE, type TabDuration } from '../../lib/modes'
import { Icon } from '../ui/Icon'

export interface ModeTabsProps {
  options: ReadonlyArray<ModeInfo>
  selected: TravelMode
  onSelect: (mode: TravelMode) => void
  /** Routed (or estimated, "~") minutes per mode; missing = not shown yet. */
  durations?: Partial<Record<TravelMode, TabDuration | null>>
  /** Icon-only chips (search sheet); still labelled for screen readers. */
  compact?: boolean
}

function durationText(d: TabDuration | null | undefined): string | null {
  if (!d) return null
  return `${d.estimated ? '~' : ''}${d.minutes} min`
}

/**
 * Walk · Bike · E-bike · Scooter tabs. Unavailable modes stay visible but disabled, with
 * "Coming soon in this area" as their description and (on tap) a short status line.
 */
export function ModeTabs({ options, selected, onSelect, durations = {}, compact = false }: ModeTabsProps) {
  const [notice, setNotice] = useState<string | null>(null)
  const noteId = useId()
  const handleClick = (option: ModeInfo) => {
    if (!option.available) {
      setNotice(`${MODE_LABELS[option.key]}: ${UNAVAILABLE_NOTE}`)
      return
    }
    setNotice(null)
    if (option.key !== selected) onSelect(option.key)
  }

  return (
    <div className={compact ? 'mode-tabs mode-tabs-compact' : 'mode-tabs'}>
      <div className="mode-tabs-row" role="group" aria-label="Travel mode">
        {options.map((option) => {
          const label = MODE_LABELS[option.key]
          const time = option.available ? durationText(durations[option.key]) : null
          return (
            <button
              key={option.key}
              type="button"
              className="mode-tab"
              aria-pressed={option.key === selected}
              aria-disabled={option.available ? undefined : true}
              aria-describedby={option.available ? undefined : noteId}
              aria-label={time ? `${label}, ${time}` : label}
              title={option.available ? undefined : UNAVAILABLE_NOTE}
              data-mode={option.key}
              onClick={() => handleClick(option)}
            >
              <Icon name={option.key} size={compact ? 18 : 20} />
              {!compact && <span className="mode-tab-label">{label}</span>}
              {!compact && time && <span className="mode-tab-time num">{time}</span>}
            </button>
          )
        })}
      </div>
      <span id={noteId} className="sr-only">
        {UNAVAILABLE_NOTE}
      </span>
      <p className="mode-tabs-note faint" role="status">
        {notice ?? ''}
      </p>
    </div>
  )
}
