import { useState } from 'react'
import type { Route, Routes } from '../api/schemas'
import type { SearchField } from '../components/search/SearchSheet'
import type { Geolocation } from '../hooks/useGeolocation'
import type { Navigation } from '../hooks/useNavigation'
import type { TripPlanner } from '../hooks/useTripPlanner'
import { tripNoun } from '../lib/modes'
import { startMode } from '../lib/navigation'
import { describeStart, originMessage } from '../lib/origin'
import type { RoutineSuggestion, SavedKind } from '../lib/routines'
import { shareLink, shareableUrl } from '../lib/share'
import type { Routines } from '../hooks/useRoutines'
import type { Place, ViewState } from '../state/urlState'

export type Panel = { kind: 'search'; field: SearchField } | { kind: 'options' } | { kind: 'about' } | null

const LOCATING_NOTE = 'Finding you so routes start where you are. Your location stays on this phone.'
const SHARE_FAILED = "Couldn't share. Copy the link from the address bar instead."

const LOCATION_OFF = 'Location is off. Allow it in your browser settings to start walks from where you are.'

interface Deps {
  onNotice: (message: string | null) => void
  view: ViewState
  update: (patch: Partial<ViewState>) => void
  geo: Geolocation
  planner: TripPlanner
  routines: Routines
  nav: Navigation
  routes: Routes | null
  selectedRoute: Route | null
}

/** What taps do: open sheets, pick places, start/share a trip. Kept out of the container's render. */
export function useTripActions({ onNotice, view, update, geo, planner, routines, nav, routes, selectedRoute }: Deps) {
  const [panel, setPanel] = useState<Panel>(null)
  const [shareStatus, setShareStatus] = useState<string | null>(null)
  const [recenterKey, setRecenterKey] = useState(0)

  const openSearch = (field: SearchField) => {
    if (field === 'to' && geo.status === 'prompt') geo.request()
    setPanel({ kind: 'search', field })
  }
  const closePanel = () => setPanel(null)

  const pickPlace = (field: SearchField, place: Place) => {
    if (field === 'home' || field === 'work') {
      routines.setSaved(field, place)
      setPanel({ kind: 'search', field: 'to' })
      return
    }
    if (field === 'from') planner.pickOrigin(place)
    else planner.pickDestination(place)
    closePanel()
  }

  const planSuggestion = (s: RoutineSuggestion) => {
    if (s.from) update({ from: s.from, to: s.to, seg: null })
    else planner.pickDestination(s.to)
    closePanel()
  }

  const startFromMyLocation = () => {
    if (planner.origin.place) planner.pickOrigin(planner.origin.place)
    else {
      update({ from: null })
      geo.request()
    }
    closePanel()
  }

  const locate = () => {
    if (geo.status === 'denied' || geo.status === 'unavailable') {
      onNotice(geo.status === 'denied' ? LOCATION_OFF : (geo.error ?? "This device isn't sharing a location right now."))
      return
    }
    geo.request()
    setRecenterKey((k) => k + 1)
  }

  const start = () => {
    if (!selectedRoute || !view.to) return
    onNotice(null) // earlier messages would cover the navigation banner
    if (view.from) routines.record({ from: describeStart(view.from), to: view.to, at: new Date().toISOString() })
    nav.start(startMode(selectedRoute.coords, geo.position).mode)
  }

  const share = async () => {
    const url = shareableUrl(view, window.location.origin, window.location.pathname)
    const text = view.to ? `Lower-risk ${tripNoun(view.mode)} to ${view.to.label} on PathPro` : 'PathPro route'
    const outcome = await shareLink(url, 'PathPro route', text)
    setShareStatus(outcome === 'copied' ? 'Link copied' : outcome === 'failed' ? SHARE_FAILED : null)
  }

  const searchNote = (field: SearchField): string | null => {
    if (field === 'from') return originMessage(planner.origin.status)
    return field === 'to' && geo.status === 'locating' ? LOCATING_NOTE : null
  }

  const editSaved = (kind: SavedKind) => setPanel({ kind: 'search', field: kind })
  const finishTrip = () => {
    nav.end()
    planner.clear()
  }

  return {
    panel,
    setPanel,
    openSearch,
    closePanel,
    pickPlace,
    planSuggestion,
    startFromMyLocation,
    locate,
    recenterKey,
    start,
    share,
    shareStatus: routes ? shareStatus : null,
    searchNote,
    editSaved,
    finishTrip,
  }
}
