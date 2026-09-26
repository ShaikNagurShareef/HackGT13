import { useCallback, useEffect, useMemo, useState } from 'react'
import { ApiError, api } from '../api/client'
import { isDemoMode } from '../api/demo'
import type { Area } from '../api/schemas'
import { MapControls } from '../components/home/MapControls'
import { NavigationView } from '../components/nav/NavigationView'
import type { BundleData } from '../hooks/useBundle'
import { useDemoMode } from '../hooks/useDemoMode'
import { useExplanation } from '../hooks/useExplanation'
import { useGeolocation } from '../hooks/useGeolocation'
import { useLiveCondition } from '../hooks/useLiveCondition'
import { useNavigation } from '../hooks/useNavigation'
import { useRiskFrames } from '../hooks/useRiskFrames'
import { useRoutes } from '../hooks/useRoutes'
import { useRoutines } from '../hooks/useRoutines'
import { useSegmentDetail } from '../hooks/useSegmentDetail'
import { useTripPlanner } from '../hooks/useTripPlanner'
import { useTypewriter } from '../hooks/useTypewriter'
import { useViewState } from '../hooks/useViewState'
import { useViewportReports } from '../hooks/useViewportReports'
import { hotspotsFor } from '../lib/hotspots'
import { startMode } from '../lib/navigation'
import { originMessage } from '../lib/origin'
import { statusLabel } from '../lib/options'
import { estimateWalkMin, isStrongSuggestion } from '../lib/suggestion'
import { atlantaParts, dayGroupOf, formatTime } from '../lib/time'
import { speak } from '../lib/voice'
import { hasSeenWelcome, markWelcomeSeen } from '../lib/welcome'
import type { MeMarker } from '../map/layers'
import { DetailLayer } from './DetailLayer'
import { HomeScreen } from './HomeScreen'
import { MapStage } from './MapStage'
import { Panels } from './Panels'
import { RouteScreen } from './RouteScreen'
import { useTripActions } from './useTripActions'

const PLAY_MS = 1000

/** The app container: owns view state, data hooks, and which screen (home / route / nav) is showing. */
export function PathPro({ data }: { data: BundleData }) {
  const [view, update] = useViewState()
  const demo = isDemoMode()
  const [error, setError] = useState<string | null>(null)
  const [area, setArea] = useState<Area | null>(null)
  const [cityMode, setCityMode] = useState(false)
  const [playing, setPlaying] = useState(false)
  const [welcome, setWelcome] = useState(() => !demo && !hasSeenWelcome())
  const [hiddenSuggestion, setHiddenSuggestion] = useState<string | null>(null)
  const [selection, setSelection] = useState<{ key: string; kind: 'pp' | 'fast' } | null>(null)
  const [focus, setFocus] = useState<{ path: [number, number][]; key: number } | null>(null)

  const geo = useGeolocation()
  const planner = useTripPlanner({ view, update, geo, bbox: data.meta.coverage_bbox })
  const routines = useRoutines(geo.position)
  useDemoMode(demo, view, update, setError)
  const live = useLiveCondition(view.cond)
  const showArea = useCallback(
    (load: Promise<Area>, silent = false) =>
      load.then(setArea).catch((e: unknown) => !silent && setError(e instanceof ApiError ? e.message : 'Area unavailable.')),
    [],
  )
  const { routes, loading } = useRoutes(view, {
    onError: setError,
    onOutside: (to) => void showArea(api.areaAt(to.lat, to.lon, view.depart, view.cond), true),
    onLoaded: () => update({ hour: null, day: null }),
  })

  const now = useMemo(() => new Date(), [])
  const departDate = routes ? new Date(routes.depart_at) : now
  const hour = view.hour ?? atlantaParts(departDate).hour
  const day = view.day ?? dayGroupOf(departDate)
  const liveCond = routes?.condition_used.cond ?? (live.wet ? 'wet' : 'dry')
  const mapCond = view.cond === 'live' ? liveCond : view.cond
  const condLabel = view.cond === 'live' ? (live.label ?? `Live · ${mapCond}`) : view.cond === 'wet' ? 'Wet' : 'Dry'
  const frames = useRiskFrames(data.frames, day, mapCond, true, setError, 'Risk Tides frames could not load.')
  const hexFrames = useRiskFrames(data.hexFrames, day, mapCond, cityMode, setError, 'City Pulse frames could not load.')
  const detail = useSegmentDetail(view.seg, routes?.depart_at ?? view.depart, view.cond, setError)

  const routeKey = routes?.route_key ?? null
  const routeExplain = useExplanation(routeKey, () => api.explainRoute(routeKey ?? ''))
  const routeText = useTypewriter(routeExplain.result?.text ?? null)
  const kind = selection && selection.key === routeKey ? selection.kind : 'pp'
  const selectedRoute = routes ? (kind === 'pp' && routes.pathpro ? routes.pathpro : routes.fastest) : null
  const routeStreets = useMemo(() => {
    const ids = new Set(selectedRoute?.segment_ids ?? [])
    return data.segments.filter((s) => ids.has(s.id))
  }, [data.segments, selectedRoute])
  const nav = useNavigation({ route: selectedRoute, gps: geo.position, streets: routeStreets, destination: view.to })
  const reports = useViewportReports(!demo && !cityMode)
  const actions = useTripActions({ onNotice: setError, view, update, geo, planner, routines, nav, routes, selectedRoute })

  useEffect(() => {
    if (!playing) return
    const id = window.setInterval(() => update({ hour: (hour + 1) % 24 }), PLAY_MS)
    return () => window.clearInterval(id)
  }, [playing, hour, update])

  const frame = frames?.hour(hour) ?? null
  const medians = useMemo(() => frames?.medians() ?? [], [frames])
  const hotspots = useMemo(() => (frame ? hotspotsFor(data.hotspotNodes, frame) : []), [data, frame])
  const onSegment = useCallback((id: number) => update({ seg: id }), [update])
  const { pickDestination } = planner
  const onMapPick = useCallback((lat: number, lon: number) => pickDestination({ lat, lon, label: 'Dropped pin' }), [pickDestination])
  const focusSegment = (id: number) => {
    const seg = data.segments.find((s) => s.id === id)
    if (seg) setFocus({ path: seg.path, key: Date.now() })
    update({ seg: id })
  }

  const screen = nav.active ? 'nav' : view.to || view.from ? 'route' : 'home'
  const fix = geo.position
  const me: MeMarker | null =
    nav.active && nav.position
      ? { position: nav.position, accuracy: nav.mode === 'gps' ? (fix?.accuracy ?? null) : null, heading: nav.heading }
      : fix
        ? { position: [fix.lon, fix.lat], accuracy: fix.accuracy, heading: fix.heading }
        : null
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
    lights: data.meta.frame_light[day] ?? [],
    condLabel,
    day,
    onDay: (d: typeof day) => update({ day: d }),
  }

  return (
    <main className="app" data-screen={screen}>
      <MapStage
        bbox={data.meta.coverage_bbox}
        outlineUrl={`${data.meta.static_base}/coverage.geojson`}
        segments={data.segments}
        frame={frame}
        frameKey={`${day}-${mapCond}-${hour}-${frames ? 'ready' : 'empty'}`}
        hotspots={hotspots}
        fastest={routes?.fastest ?? null}
        pathpro={routes?.pathpro ?? null}
        selectedRoute={kind}
        selectedSeg={view.seg}
        onSegment={onSegment}
        onMapPick={onMapPick}
        me={me}
        follow={nav.active}
        recenterKey={actions.recenterKey}
        focus={focus}
        reports={reports.reports}
        onViewport={reports.onViewport}
        hex={
          cityMode && data.hexCells
            ? {
                cells: data.hexCells,
                frame: hexFrames?.hour(hour) ?? null,
                frameKey: `hex-${day}-${mapCond}-${hour}-${hexFrames ? 'ready' : 'empty'}`,
                onPick: (cell: string) => void showArea(api.area(cell, routes?.depart_at ?? view.depart, view.cond)),
              }
            : null
        }
      />
      {screen !== 'nav' && (
        <MapControls onLayers={() => actions.setPanel({ kind: 'options' })} onLocate={actions.locate} geoStatus={geo.status} />
      )}
      {screen === 'home' && (
        <HomeScreen
          suggestion={suggestion}
          etaMin={suggestion && suggestionFrom ? estimateWalkMin(suggestionFrom, suggestion.to) : null}
          onGo={actions.planSuggestion}
          onDismissSuggestion={() => setHiddenSuggestion(top?.to.label ?? null)}
          onOpenSearch={() => actions.openSearch('to')}
          statusLabel={statusLabel({ cond: view.cond, depart: view.depart, hour: view.hour, cityMode })}
          onOpenOptions={() => actions.setPanel({ kind: 'options' })}
          welcomeDataThrough={welcome ? data.meta.data_through : null}
          onDismissWelcome={dismissWelcome}
          reportsLegend={reports.available}
        />
      )}
      {screen === 'route' && (
        <RouteScreen
          header={{
            from: view.from,
            to: view.to,
            onEditFrom: () => actions.openSearch('from'),
            onEditTo: () => actions.openSearch('to'),
            onSwap: planner.swap,
            onBack: planner.clear,
          }}
          notice={view.to && !view.from ? originMessage(planner.origin.status) : null}
          onPickStart={() => actions.openSearch('from')}
          loading={loading}
          sheet={
            routes && !detail && !area
              ? {
                  routes,
                  selected: kind,
                  onSelect: (k) => setSelection({ key: routes.route_key, kind: k }),
                  explanation: routeText,
                  onStart: actions.start,
                  onPreview: () => nav.start('preview'),
                  startNote: selectedRoute ? startMode(selectedRoute.coords, fix).note : null,
                  onListen: () => void speak({ kind: 'route', route_key: routes.route_key }, routeText ?? ''),
                  onShare: () => void actions.share(),
                  shareStatus: actions.shareStatus,
                  onFocusSegment: focusSegment,
                  onSelectSegment: onSegment,
                }
              : null
          }
        />
      )}
      {screen === 'nav' && (
        <NavigationView
          instruction={nav.instruction}
          mode={nav.mode}
          remainingS={nav.remainingS}
          remainingM={nav.remainingM}
          arrival={formatTime(nav.arrivalAt)}
          arrived={nav.arrived}
          destination={view.to?.label ?? 'your destination'}
          onEnd={nav.end}
          onDone={actions.finishTrip}
        />
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
        />
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
        canUseLocation={geo.status !== 'denied' && geo.status !== 'unavailable' && planner.origin.status !== 'outside'}
        welcome={welcome}
        onDismissWelcome={dismissWelcome}
        options={{
          cond: view.cond,
          condLabel: routes?.condition_used.label ?? condLabel,
          onCond: (c) => update({ cond: c }),
          depart: view.depart,
          onDepart: (d) => update({ depart: d }),
          cityAvailable: Boolean(data.hexCells),
          cityMode,
          onCityMode: setCityMode,
          timeline,
          showReportsLegend: reports.available,
        }}
      />
    </main>
  )
}
