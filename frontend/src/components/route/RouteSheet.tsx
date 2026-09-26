import { useRef, useState } from 'react'
import type { Routes } from '../../api/schemas'
import type { DayPart } from '../../api/safetySchemas'
import { summarizeRoutes, type RouteLine } from '../../lib/routeSummary'
import { formatRouteSafety } from '../../lib/safety'
import { BottomSheet } from '../sheet/BottomSheet'
import { Icon } from '../ui/Icon'
import { HandoffCard, type HandoffCardProps } from './HandoffCard'
import { RouteDetails } from './RouteDetails'
import { RouteOption } from './RouteOption'

export type RouteKind = RouteLine['kind']
const NO_DAY_PARTS: ReadonlyArray<DayPart> = []

export interface RouteSheetProps {
  routes: Routes
  selected: RouteKind
  onSelect: (kind: RouteKind) => void
  explanation: string | null
  onStart: () => void
  onPreview: () => void
  /** Why Start will preview instead of following GPS, when that is the case. */
  startNote: string | null
  onListen: () => void
  onShare: () => void
  shareStatus: string | null
  onFocusSegment: (id: number) => void
  onSelectSegment: (id: number) => void
  /** Personal-safety day parts, to name the time window of reported crimes. */
  dayParts?: ReadonlyArray<DayPart>
  /** Long walks: MARTA hand-off and "Try Bike" suggestions. */
  handoff?: HandoffCardProps | null
}

/** Route sheet: the PathPro route headline, the fastest alternative, and big Start (RTE-04). */
export function RouteSheet(props: RouteSheetProps) {
  const { routes, selected } = props
  const [expanded, setExpanded] = useState(false)
  const explanationRef = useRef<HTMLParagraphElement>(null)
  const summary = summarizeRoutes(routes)
  const lines = summary.secondary ? [summary.primary, summary.secondary] : [summary.primary]
  const routeFor = (kind: RouteKind) => (kind === 'pp' && routes.pathpro ? routes.pathpro : routes.fastest)

  const handleWhy = () => {
    setExpanded(true)
    window.requestAnimationFrame(() => explanationRef.current?.focus())
  }

  const peek = (
    <>
      <div className="route-options">
        {lines.map((line) => (
          <RouteOption
            key={line.kind}
            line={line}
            route={routeFor(line.kind)}
            selected={selected === line.kind || lines.length === 1}
            onSelect={props.onSelect}
            safetyLine={formatRouteSafety(routeFor(line.kind).safety)}
          />
        ))}
      </div>
      {props.handoff && <HandoffCard {...props.handoff} />}
      <div className="route-actions">
        <button type="button" className="btn primary start-btn" onClick={props.onStart}>
          <Icon name="play" size={18} />
          Start
        </button>
        <button type="button" className="btn round" onClick={props.onListen}>
          <Icon name="volume" size={18} /> Listen
        </button>
        <button type="button" className="btn round" onClick={handleWhy}>
          <Icon name="info" size={18} /> Why?
        </button>
        <button type="button" className="btn round" onClick={props.onShare}>
          <Icon name="share" size={18} /> Share
        </button>
      </div>
      {props.startNote && <p className="start-note faint">{props.startNote}</p>}
      <p className="share-status faint" role="status">
        {props.shareStatus ?? ''}
      </p>
    </>
  )

  return (
    <BottomSheet label="Route comparison" className="route-sheet" expanded={expanded} onExpandedChange={setExpanded} peek={peek}>
      <RouteDetails
        routes={routes}
        explanation={props.explanation}
        explanationRef={explanationRef}
        onPreview={props.onPreview}
        onFocusSegment={props.onFocusSegment}
        onSelectSegment={props.onSelectSegment}
        dayParts={props.dayParts ?? NO_DAY_PARTS}
      />
    </BottomSheet>
  )
}
