import { useCallback, useEffect, useMemo, useState } from 'react'
import { ApiError, api } from '../api/client'
import { isDemoMode } from '../api/demo'
import type { Bbox } from '../api/client'
import type { Area } from '../api/schemas'
import { MapControls } from '../components/home/MapControls'
import { NavigationView } from '../components/nav/NavigationView'
import { ResumedShareBar } from '../components/share/ResumedShareBar'
import { ResumeSharePrompt } from '../components/share/ResumeSharePrompt'
import { ShareWalkPanel } from '../components/share/ShareWalkPanel'
import { StatusScreen } from '../components/StatusScreen'
import { SafetyPickCard } from '../components/safety/SafetyPickCard'
import type { BundleData } from '../hooks/useBundle'
import { useDemoMode } from '../hooks/useDemoMode'
import { useExplanation } from '../hooks/useExplanation'
import { useGeolocation } from '../hooks/useGeolocation'
import { useMediaQuery } from '../hooks/useMediaQuery'
import { useLiveCondition } from '../hooks/useLiveCondition'
import { useNavigation } from '../hooks/useNavigation'
import { useRideNetwork } from '../hooks/useRideNetwork'
import { useRiskFrames } from '../hooks/useRiskFrames'
import { useRoutes } from '../hooks/useRoutes'
import { useRoutines } from '../hooks/useRoutines'
import { useSegmentDetail } from '../hooks/useSegmentDetail'
import { useTripPlanner } from '../hooks/useTripPlanner'
import { useViewState } from '../hooks/useViewState'
import { useViewportReports } from '../hooks/useViewportReports'
import { routeAskTarget, screenAskTarget, type AskTarget } from '../lib/askContext'
import { hotspotsFor } from '../lib/hotspots'
import { isRideMode, networkLegendTitle, tabDurations } from '../lib/modes'
import { startMode } from '../lib/navigation'
import { originMessage } from '../lib/origin'
import { statusLabel, type MapMode } from '../lib/options'
import { estimateWalkMin, isStrongSuggestion } from '../lib/suggestion'
import { haversine } from '../lib/walk'
import { atlantaParts, dayGroupOf, formatTime } from '../lib/time'
import { speak } from '../lib/voice'
import { hasSeenWelcome, markWelcomeSeen } from '../lib/welcome'
import type { MeMarker } from '../map/layers'
import { DetailLayer } from './DetailLayer'
import { HomeScreen } from './HomeScreen'
import { MapStage } from './MapStage'
import { Panels } from './Panels'
import { DesktopLayer } from './DesktopLayer'
import { RouteScreen, type RouteScreenProps } from './RouteScreen'
import { useSafetyMode } from './useSafetyMode'
import { useShareResume } from './useShareResume'
import { useTripActions } from './useTripActions'
import { useHandoff, useTravelModes } from './useTravelModes'

const PLAY_MS = 1000
const DESKTOP_QUERY = '(min-width: 1024px)'
/** Straight-line distance → rough routed distance, for mode-tab estimates before any route loads. */
const DETOUR_FACTOR = 1.3

/** The app container: owns view state, data hooks, and which screen (home / route / nav) is showing. */
export interface PathProProps {
  data: BundleData | null
  loadError: string | null
}

/**
 * Hooks run from the first render (before the model bundle arrives) so the trip, GPS, and
 * routes load in parallel with the map data; only the rendering waits for the bundle.
 */
export function PathPro({ data, loadError }: PathProProps) {
  const [view, update] = useViewState()
  const demo = isDemoMode()
  const [error, setError] = useState<string | null>(null)
  const [area, setArea] = useState<Area | null>(null)
  const [mapMode, setMapMode] = useState<MapMode>('streets')
  const cityMode = mapMode === 'city'
  const [playing, setPlaying] = useState(false)
  const [welcome, setWelcome] = useState(() => !demo && !hasSeenWelcome())
  const [hiddenSuggestion, setHiddenSuggestion] = useState<string | null>(null)
  const [selection, setSelection] = useState<{ key: string; kind: 'pp' | 'fast' } | null>(null)
  const [focus, setFocus] = useState<{ path: [number, number][]; key: number } | null>(null)

  const geo = useGeolocation()
  const desktop = useMediaQuery(DESKTOP_QUERY)
  const planner = useTripPlanner({ view, update, geo, bbox: data?.meta.coverage_bbox ?? null })
  const routines = useRoutines(geo.position)
  useDemoMode(demo, view, update, setError)
  const live = useLiveCondition(view.cond)
  const showArea = useCallback(
    (load: Promise<Area>, silent = false) =>
      load.then(setArea).catch((e: unknown) => !silent && setError(e instanceof ApiError ? e.message : 'Area unavailable.')),
    [],
  )
  const travel = useTravelModes({ meta: data?.meta ?? null, view, update, onNotice: setError })
  const { mode } = travel
  const { routes, loading, durations } = useRoutes(
    { ...view, mode },
    {
      onError: setError,
      onOutside: (to) => void showArea(api.areaAt(to.lat, to.lon, view.depart, view.cond), true),
      onLoaded: () => update({ hour: null, day: null }),
      onModeUnavailable: travel.onModeUnavailable,
    },
  )
  // Ride modes draw the ride network once its geometry and frames are in; walks never download it.
  const rideNet = useRideNetwork(data?.meta ?? null, isRideMode(mode) ? travel.info : null, setError)
  const networkMode = rideNet ? mode : 'walk'
  const networkSegments = rideNet?.segments ?? data?.segments ?? []
  const routeMode = routes?.mode ?? 'walk'

  const now = useMemo(() => new Date(), [])
  const departDate = routes ? new Date(routes.depart_at) : now
  const hour = view.hour ?? atlantaParts(departDate).hour
  const day = view.day ?? dayGroupOf(departDate)
  const liveCond = routes?.condition_used.cond ?? (live.wet ? 'wet' : 'dry')
  const mapCond = view.cond === 'live' ? liveCond : view.cond
  const condLabel = view.cond === 'live' ? (live.label ?? `Live · ${mapCond}`) : view.cond === 'wet' ? 'Wet' : 'Dry'
  const frames = useRiskFrames(rideNet?.frames ?? data?.frames ?? null, day, mapCond, true, setError, 'Risk Tides frames could not load.')
  const hexFrames = useRiskFrames(data?.hexFrames ?? null, day, mapCond, cityMode, setError, 'City Pulse frames could not load.')
  const detail = useSegmentDetail(view.seg, routes?.depart_at ?? view.depart, view.cond, setError, networkMode)

  const routeKey = routes?.route_key ?? null
  const routeExplain = useExplanation(routeKey, () => api.explainRoute(routeKey ?? ''))
  const routeText = routeExplain.result?.text ?? null
  const kind = selection && selection.key === routeKey ? selection.kind : 'pp'
  const selectedRoute = routes ? (kind === 'pp' && routes.pathpro ? routes.pathpro : routes.fastest) : null
  // Street names for the banner come from the network the route was planned on.
  const routeNetwork = isRideMode(routeMode) ? rideNet?.segments : data?.segments
  const routeStreets = useMemo(() => {
    const ids = new Set(selectedRoute?.segment_ids ?? [])
    return (routeNetwork ?? []).filter((s) => ids.has(s.id))
  }, [routeNetwork, selectedRoute])
  const nav = useNavigation({
    route: selectedRoute,
    gps: geo.position,
    streets: routeStreets,
    destination: view.to,
    departAt: routes?.depart_at ?? null,
    mode: routeMode,
    speedMps: travel.speedMps,
    routeKey,
    routeKind: routes && selectedRoute === routes.pathpro ? 'pp' : 'fast',
  })
  const reports = useViewportReports(!demo && mapMode === 'streets')
  const safety = useSafetyMode(mapMode, hour)
  const reportsViewport = reports.onViewport
  const safetyViewport = safety.onViewport
  const onViewport = useCallback(
    (bbox: Bbox) => {
      reportsViewport(bbox)
      safetyViewport(bbox)
    },
    [reportsViewport, safetyViewport],
  )
  const actions = useTripActions({ onNotice: setError, view, update, geo, planner, routines, nav, routes, selectedRoute })
  const openAskTarget = (target: AskTarget) => actions.openAsk(target.context, target.label)
  const askOpen = actions.panel?.kind === 'ask'
  // The map's agent button toggles: on desktop the Ask card docks right above it. It opens
  // with whatever is on screen (area card, street sheet, or route) as the question's context.
  const toggleAsk = () => {
    if (askOpen) return actions.closePanel()
    const target = screenAskTarget({ detail, area, routeKey, cond: view.cond, mode: networkMode })
    return target ? openAskTarget(target) : actions.openAsk()
  }
  const shareResume = useShareResume({ demo, destination: view.to, route: selectedRoute, nav, onNotice: setError })
  const resumeSharing = () => {
    if (geo.status === 'prompt') geo.request() // a tap, so the browser may ask for location here
    shareResume.resume()
  }

  useEffect(() => {
    if (!playing) return
    const id = window.setInterval(() => update({ hour: (hour + 1) % 24 }), PLAY_MS)
    return () => window.clearInterval(id)
  }, [playing, hour, update])

  const frame = useMemo(() => frames?.hour(hour) ?? null, [frames, hour])
  const medians = useMemo(() => frames?.medians() ?? [], [frames])
  // Hotspot nodes belong to the walk network.
  const hotspots = useMemo(
    () => (data && frame && networkMode === 'walk' ? hotspotsFor(data.hotspotNodes, frame) : []),
    [data, frame, networkMode],
  )
  const onSegment = useCallback((id: number) => update({ seg: id }), [update])
  const { pickDestination } = planner
  const onMapPick = useCallback((lat: number, lon: number) => pickDestination({ lat, lon, label: 'Dropped pin' }), [pickDestination])
  const focusSegment = (id: number) => {
    const seg = networkSegments.find((s) => s.id === id)
    if (seg) setFocus({ path: seg.path, key: Date.now() })
    update({ seg: id })
  }

  const hexFrame = useMemo(() => hexFrames?.hour(hour) ?? null, [hexFrames, hour])
  const hexKey = `hex-${day}-${mapCond}-${hour}-${hexFrames ? 'ready' : 'empty'}`
  const hexDepart = routes?.depart_at ?? view.depart
  const hexCells = data?.hexCells ?? null
  const hex = useMemo(
    () =>
      cityMode && hexCells
        ? {
            cells: hexCells,
            frame: hexFrame,
            frameKey: hexKey,
            onPick: (cell: string) => void showArea(api.area(cell, hexDepart, view.cond)),
          }
        : null,
    [cityMode, hexCells, hexFrame, hexKey, hexDepart, view.cond, showArea],
  )
  const fastest = routes?.fastest ?? null
  const pathpro = routes?.pathpro ?? null

  const screen = nav.active ? 'nav' : view.to || view.from ? 'route' : 'home'
  const fix = geo.position
  const navLon = nav.position?.[0]
  const navLat = nav.position?.[1]
  const me = useMemo<MeMarker | null>(() => {
    if (nav.active && navLon != null && navLat != null) {
      return { position: [navLon, navLat], accuracy: nav.mode === 'gps' ? (fix?.accuracy ?? null) : null, heading: nav.heading }
    }
    return fix ? { position: [fix.lon, fix.lat], accuracy: fix.accuracy, heading: fix.heading } : null
  }, [nav.active, nav.mode, nav.heading, navLon, navLat, fix])
  const top = routines.suggestions[0]
  const suggestion = isStrongSuggestion(top) && hiddenSuggestion !== top.to.label ? top : null
  const suggestionFrom = suggestion?.from ?? fix
  const dismissWelcome = () => {
    markWelcomeSeen()
    setWelcome(false)
  }
  const timeline = {
    hour,
    onHour: (h: number) => update({ hour: h }),
    playing,
    onTogglePlay: () => setPlaying((p) => !p),
    medians,
    lights: data?.meta.frame_light[day] ?? [],
    condLabel,
    day,
    onDay: (d: typeof day) => update({ day: d }),
  }

  const etaMin = suggestion && suggestionFrom ? estimateWalkMin(suggestionFrom, suggestion.to) : null
  const dismissSuggestion = () => setHiddenSuggestion(top?.to.label ?? null)
  const safetyControls = safety.controls
  const optionValues = {
    travelMode: mode,
    cond: view.cond,
    condLabel: routes?.condition_used.label ?? condLabel,
    onCond: (c: typeof view.cond) => update({ cond: c }),
    depart: view.depart,
    onDepart: (d: string) => update({ depart: d }),
    cityAvailable: Boolean(data?.hexCells),
    mapMode,
    onMapMode: setMapMode,
    safety: safetyControls
      ? {
          ...safetyControls,
          // From the phone's options sheet, close it so the help point's card is visible.
          onPickHelp: (pick: Parameters<typeof safetyControls.onPickHelp>[0]) => {
            safetyControls.onPickHelp(pick)
            actions.closePanel()
          },
          prefer: view.prefer,
          onPrefer: (prefer: typeof view.prefer) => update({ prefer }),
        }
      : null,
    showReportsLegend: reports.available,
  }
  const canUseLocation = geo.status !== 'denied' && geo.status !== 'unavailable' && planner.origin.status !== 'outside'
  const straightM = view.from && view.to ? haversine([view.from.lon, view.from.lat], [view.to.lon, view.to.lat]) * DETOUR_FACTOR : null
  const modeTabs = {
    options: travel.options,
    selected: mode,
    onSelect: travel.onMode,
    durations: tabDurations(travel.options, durations, routes?.fastest.distance_m ?? straightM),
  }
  const handoff = useHandoff({
    routes,
    from: view.from,
    to: view.to,
    options: travel.options,
    onPlanStation: planner.pickDestination,
    onTryMode: travel.onMode,
  })
  const routeScreen: RouteScreenProps = {
    header: {
      from: view.from,
      to: view.to,
      onEditFrom: () => actions.openSearch('from'),
      onEditTo: () => actions.openSearch('to'),
      onSwap: planner.swap,
      onBack: planner.clear,
    },
    notice: view.to && !view.from ? originMessage(planner.origin.status) : null,
    onPickStart: () => actions.openSearch('from'),
    loading,
    sheet:
      routes && !detail && !area
        ? {
            routes,
            selected: kind,
            onSelect: (k) => setSelection({ key: routes.route_key, kind: k }),
            explanation: routeText,
            onStart: actions.start,
            onPreview: () => nav.start('preview'),
            startNote: selectedRoute ? startMode(selectedRoute.coords, fix, routeMode).note : null,
            onListen: () => void speak({ kind: 'route', route_key: routes.route_key }, routeText ?? ''),
            onShare: () => void actions.share(),
            shareStatus: actions.shareStatus,
            onFocusSegment: focusSegment,
            onSelectSegment: onSegment,
            dayParts: safety.meta?.day_parts,
            handoff,
            onAsk: demo ? undefined : () => openAskTarget(routeAskTarget(routes.route_key)),
          }
        : null,
    modes: modeTabs,
    prefer: view.prefer,
    safetyNote: !desktop && safety.legend?.layers.crimes ? () => actions.setPanel({ kind: 'options' }) : null,
  }

  if (loadError) return <StatusScreen kind="error" message={loadError} />
  if (!data) return <StatusScreen kind="loading" />
  return (
    <main className={desktop ? 'app app-desktop' : 'app'} data-screen={screen}>
      <MapStage
        bbox={data.meta.coverage_bbox}
        outlineUrl={`${data.meta.static_base}/coverage.geojson`}
        segments={networkSegments}
        frame={frame}
        frameKey={`${networkMode}-${day}-${mapCond}-${hour}-${frames ? 'ready' : 'empty'}`}
        hotspots={hotspots}
        fastest={fastest}
        pathpro={pathpro}
        selectedRoute={kind}
        selectedSeg={view.seg}
        onSegment={onSegment}
        onMapPick={onMapPick}
        me={me}
        follow={nav.active}
        recenterKey={actions.recenterKey}
        focus={focus}
        reports={reports.reports}
        onViewport={onViewport}
        hex={hex}
        safety={safety.mapInput}
      />
      {screen !== 'nav' && (
        <MapControls
          onLayers={() => actions.setPanel({ kind: 'options' })}
          onLocate={actions.locate}
          geoStatus={geo.status}
          onAsk={demo ? undefined : toggleAsk}
          askOpen={askOpen}
        />
      )}
      {desktop ? (
        <DesktopLayer
          screen={screen}
          home={{
            suggestion,
            etaMin,
            onGo: actions.planSuggestion,
            onDismissSuggestion: dismissSuggestion,
            search: {
              field: 'to',
              suggestions: routines.suggestions,
              saved: routines.saved,
              recents: routines.recents,
              canUseLocation,
              onUseLocation: actions.startFromMyLocation,
              onPick: (place) => actions.pickPlace('to', place),
              onPickSuggestion: actions.planSuggestion,
              onEditSaved: actions.editSaved,
              modes: modeTabs,
            },
            options: { ...optionValues, onClearHistory: routines.clear },
            onAbout: () => actions.setPanel({ kind: 'about' }),
            onAsk: demo ? undefined : () => actions.openAsk(),
            safetyAvailable: safety.available,
          }}
          route={routeScreen}
          destination={view.to?.label ?? 'your destination'}
          timeline={timeline}
          welcomeDataThrough={welcome ? data.meta.data_through : null}
          onDismissWelcome={dismissWelcome}
          safetyAvailable={safety.available}
          safetyDock={safety.legend}
          travelMode={routeMode}
        />
      ) : (
        <>
          {screen === 'home' && (
            <HomeScreen
              suggestion={suggestion}
              etaMin={etaMin}
              onGo={actions.planSuggestion}
              onDismissSuggestion={dismissSuggestion}
              onOpenSearch={() => actions.openSearch('to')}
              statusLabel={statusLabel({
                cond: view.cond,
                depart: view.depart,
                hour: view.hour,
                cityMode,
                safetyMode: mapMode === 'safety',
                prefer: view.prefer,
                mode,
              })}
              onOpenOptions={() => actions.setPanel({ kind: 'options' })}
              welcomeDataThrough={welcome ? data.meta.data_through : null}
              onDismissWelcome={dismissWelcome}
              reportsLegend={reports.available}
              safetyAvailable={safety.available}
              safetyLegend={safety.legend}
              legendTitle={networkLegendTitle(networkMode)}
            />
          )}
          {screen === 'route' && <RouteScreen {...routeScreen} />}
        </>
      )}
      {screen === 'nav' && (
        <NavigationView
          instruction={nav.instruction}
          mode={nav.mode}
          travel={routeMode}
          remainingS={nav.remainingS}
          remainingM={nav.remainingM}
          arrival={formatTime(nav.arrivalAt)}
          arrived={nav.arrived}
          destination={view.to?.label ?? 'your destination'}
          onEnd={nav.end}
          onDone={actions.finishTrip}
          share={
            <ShareWalkPanel
              demo={demo}
              mode={nav.mode}
              destination={view.to}
              route={selectedRoute?.coords ?? null}
              position={nav.position}
              accuracy={nav.mode === 'gps' ? (fix?.accuracy ?? null) : null}
              remainingS={nav.remainingS}
              arrived={nav.arrived}
              resume={shareResume.resumed != null}
            />
          }
        />
      )}
      {screen !== 'nav' && shareResume.pending && (
        <ResumeSharePrompt
          destination={shareResume.pending.destination.label}
          onResume={resumeSharing}
          onStop={shareResume.stopSharing}
        />
      )}
      {screen !== 'nav' && shareResume.resumed && (
        <ResumedShareBar destination={shareResume.resumed.destination} position={fix} />
      )}
      {screen !== 'nav' && (
        <DetailLayer
          area={area}
          detail={detail}
          cond={view.cond}
          onCloseArea={() => setArea(null)}
          onCloseDetail={() => update({ seg: null })}
          onAbout={() => actions.setPanel({ kind: 'about' })}
          onReported={reports.refresh}
          rideNetwork={networkMode !== 'walk'}
          mode={networkMode}
          onAsk={demo ? undefined : actions.openAsk}
        />
      )}
      {screen !== 'nav' && safety.pick && (
        <SafetyPickCard pick={safety.pick} dayLabel={safety.dayLabel} onClose={safety.closePick} />
      )}
      {error && (
        <div className="banner panel" role="alert">
          <span>{error}</span>
          <button type="button" className="link-btn" onClick={() => setError(null)}>
            Dismiss
          </button>
        </div>
      )}
      <Panels
        panel={actions.panel}
        meta={data.meta}
        actions={actions}
        routines={routines}
        canUseLocation={canUseLocation}
        welcome={welcome}
        onDismissWelcome={dismissWelcome}
        options={{ ...optionValues, timeline }}
        safetyMeta={safety.meta}
        modes={{ ...modeTabs, durations: undefined }}
        askAvailable={!demo}
      />
    </main>
  )
}
