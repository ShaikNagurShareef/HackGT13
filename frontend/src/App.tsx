import { useCallback, useEffect, useMemo, useState } from 'react'
import { ApiError, api } from './api/client'
import type { Routes, SegmentDetail } from './api/schemas'
import { About, FirstRun } from './components/About'
import { ComparisonCard } from './components/ComparisonCard'
import { ConditionsChip, DepartPicker, Legend } from './components/Controls'
import { SearchBar } from './components/SearchBar'
import { SegmentSheet } from './components/SegmentSheet'
import { Timeline } from './components/Timeline'
import type { FrameSet } from './frames/frameStore'
import { useBundle } from './hooks/useBundle'
import { useViewState } from './hooks/useViewState'
import { hotspotsFor } from './lib/hotspots'
import { atlantaParts, dayGroupOf } from './lib/time'
import { MapView } from './map/MapView'
import type { Place } from './state/urlState'

const SEEN_KEY = 'pathpulse:first-run-seen'
const PLAY_MS = 1000

function readSeen(): boolean {
  try {
    return window.localStorage.getItem(SEEN_KEY) === '1'
  } catch {
    return false
  }
}

export default function App() {
  const { data, error: loadError } = useBundle()
  const [view, update] = useViewState()
  const [frames, setFrames] = useState<FrameSet | null>(null)
  const [routes, setRoutes] = useState<Routes | null>(null)
  const [detail, setDetail] = useState<SegmentDetail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [playing, setPlaying] = useState(false)
  const [aboutOpen, setAboutOpen] = useState(false)
  const [firstRun, setFirstRun] = useState(() => !readSeen() && !view.demo)
  const [liveWet, setLiveWet] = useState(false)

  const now = useMemo(() => new Date(), [])
  const departDate = routes ? new Date(routes.depart_at) : now
  const hour = view.hour ?? atlantaParts(departDate).hour
  const day = view.day ?? dayGroupOf(departDate)
  const mapCond = view.cond === 'live' ? (liveWet ? 'wet' : 'dry') : view.cond
  const condLabel = view.cond === 'live' ? `Live · ${mapCond}` : view.cond === 'wet' ? 'Wet' : 'Dry'

  useEffect(() => {
    if (!data) return
    let cancelled = false
    data.frames.prefetch(day)
    data.frames
      .get(day, mapCond)
      .then((f) => !cancelled && setFrames(f))
      .catch(() => !cancelled && setError('Risk Tides frames could not load.'))
    return () => {
      cancelled = true
    }
  }, [data, day, mapCond])

  useEffect(() => {
    if (!view.from || !view.to) {
      setRoutes(null)
      return
    }
    let cancelled = false
    setError(null)
    api
      .routes(view.from, view.to, view.depart, view.cond)
      .then((r) => {
        if (cancelled) return
        setRoutes(r)
        if (view.cond === 'live') setLiveWet(r.condition_used.cond === 'wet')
        update({ hour: null, day: null })
      })
      .catch((e: unknown) => !cancelled && setError(e instanceof ApiError ? e.message : 'Could not compute routes.'))
    return () => {
      cancelled = true
    }
  }, [view.from, view.to, view.depart, view.cond, update])

  useEffect(() => {
    if (view.seg == null) {
      setDetail(null)
      return
    }
    let cancelled = false
    api
      .segment(view.seg, routes?.depart_at ?? view.depart, view.cond)
      .then((d) => !cancelled && setDetail(d))
      .catch((e: unknown) => !cancelled && setError(e instanceof ApiError ? e.message : 'Could not load details.'))
    return () => {
      cancelled = true
    }
  }, [view.seg, view.depart, view.cond, routes?.depart_at])

  useEffect(() => {
    if (!playing) return
    const id = window.setInterval(() => update({ hour: (hour + 1) % 24 }), PLAY_MS)
    return () => window.clearInterval(id)
  }, [playing, hour, update])

  const frame = frames?.hour(hour) ?? null
  const medians = useMemo(() => frames?.medians() ?? [], [frames])
  const hotspots = useMemo(
    () => (data && frame ? hotspotsFor(data.hotspotNodes, frame) : []),
    [data, frame],
  )
  const onSegment = useCallback((id: number) => update({ seg: id }), [update])
  const onMapPick = useCallback(
    (lat: number, lon: number) => {
      const pin: Place = { lat, lon, label: 'Dropped pin' }
      update(view.from ? { to: pin } : { from: pin })
    },
    [update, view.from],
  )

  if (loadError) return <main className="app app-error"><p>{loadError}</p></main>
  if (!data) return <main className="app app-loading" aria-busy="true"><p>Loading PathPulse…</p></main>

  const lights = data.meta.frame_light[day] ?? []
  return (
    <main className="app">
      <MapView
        bbox={data.meta.coverage_bbox}
        segments={data.segments}
        frame={frame}
        frameKey={`${day}-${mapCond}-${hour}-${frames ? "ready" : "empty"}`}
        hotspots={hotspots}
        fastest={routes?.fastest ?? null}
        pathpulse={routes?.pathpulse ?? null}
        selectedSeg={view.seg}
        onSegment={onSegment}
        onMapPick={onMapPick}
      />
      <div className="top-bar">
        <SearchBar
          from={view.from}
          to={view.to}
          onFrom={(p) => update({ from: p })}
          onTo={(p) => update({ to: p })}
          onSwap={() => update({ from: view.to, to: view.from })}
        />
        <div className="top-controls panel">
          <ConditionsChip cond={view.cond} label={routes?.condition_used.label ?? condLabel} onChange={(c) => update({ cond: c })} />
          <DepartPicker value={view.depart} onChange={(d) => update({ depart: d })} />
        </div>
        <button type="button" className="icon-btn about-btn" aria-label="About PathPulse" onClick={() => setAboutOpen(true)}>
          i
        </button>
      </div>
      {error && (
        <div className="banner panel" role="alert">
          {error}
          <button type="button" className="link-btn" onClick={() => setError(null)}>
            Dismiss
          </button>
        </div>
      )}
      <aside className="side">
        {detail ? (
          <SegmentSheet
            detail={detail}
            explanation={null}
            onClose={() => update({ seg: null })}
            onAbout={() => setAboutOpen(true)}
          />
        ) : routes ? (
          <ComparisonCard
            routes={routes}
            explanation={null}
            onClear={() => update({ from: null, to: null })}
            onSelectSegment={onSegment}
          />
        ) : (
          <Legend />
        )}
      </aside>
      <Timeline
        hour={hour}
        onHour={(h) => update({ hour: h })}
        playing={playing}
        onTogglePlay={() => setPlaying((p) => !p)}
        medians={medians}
        lights={lights}
        condLabel={condLabel}
        day={day}
        onDay={(d) => update({ day: d })}
      />
      {firstRun && (
        <FirstRun
          dataThrough={data.meta.data_through}
          onDone={() => {
            try {
              window.localStorage.setItem(SEEN_KEY, '1')
            } catch {
              /* private mode: the card simply shows again next visit */
            }
            setFirstRun(false)
          }}
        />
      )}
      {aboutOpen && <About meta={data.meta} onClose={() => setAboutOpen(false)} />}
    </main>
  )
}
