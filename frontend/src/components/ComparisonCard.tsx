import type { Route, Routes } from '../api/schemas'
import { cssColor } from '../lib/bands'
import { routeReportsLine } from '../lib/reports'
import { formatClock, formatMinutes } from '../lib/time'
import { TrustNote } from './Controls'

function km(m: number): string {
  return m >= 1000 ? `${(m / 1000).toFixed(1)} km` : `${Math.round(m)} m`
}

function RouteRow({ label, route, kind }: { label: string; route: Route; kind: 'fast' | 'pp' }) {
  return (
    <div className={`route-row route-${kind}`} data-testid={`route-${kind}`}>
      <span className="route-swatch" aria-hidden="true" />
      <div className="route-main">
        <div className="route-label">{label}</div>
        <div className="faint num">
          {formatMinutes(route.duration_s)} · {km(route.distance_m)} · {km(route.high_risk_m)} on high-risk streets
        </div>
      </div>
      <div className="route-score num" style={{ color: cssColor(route.risk_score) }}>
        <span className="route-score-value">{route.risk_score}</span>
        <span className="faint">{route.band}</span>
      </div>
    </div>
  )
}

/** One-sentence evidence summary; replaced by the grounded LLM text when it arrives. */
export function templateSummary(routes: Routes): string {
  const { fastest, pathpro } = routes
  const worst = fastest.top_segments.slice(0, 2).map((s) => s.name)
  if (!pathpro) {
    return worst.length
      ? `The fastest route is already the lower-risk option; its busiest stretch is ${worst[0]}.`
      : 'The fastest route is already the lower-risk option.'
  }
  const avoided = worst.filter((n) => !pathpro.top_segments.some((s) => s.name === n))
  const via = avoided.length ? ` by avoiding ${avoided.join(' and ')}` : ''
  return `PathPro adds ${routes.time_cost_min} min and cuts traffic-risk exposure ${routes.exposure_reduction_pct}%${via}.`
}

export interface ComparisonCardProps {
  routes: Routes
  explanation: string | null
  onClear: () => void
  onSelectSegment: (id: number) => void
  onFocusSegment?: (id: number) => void
  onListen?: () => void
  walk?: { active: boolean; progress: number; banner: string | null; onStart: () => void; onStop: () => void }
}

export function ComparisonCard({
  routes,
  explanation,
  onClear,
  onSelectSegment,
  onFocusSegment,
  onListen,
  walk,
}: ComparisonCardProps) {
  const { fastest, pathpro } = routes
  const depart = new Date(routes.depart_at)
  return (
    <section className="compare panel" aria-label="Route comparison" aria-live="polite">
      <header className="compare-head">
        <div>
          <div className="compare-title">
            {pathpro ? (
              <>
                <span className="num">+{routes.time_cost_min} min</span>,{' '}
                <span className="num">{routes.exposure_reduction_pct}%</span> less traffic-risk exposure
              </>
            ) : (
              'The fastest route is already the lower-risk option.'
            )}
          </div>
          <div className="faint">
            Leaving {formatClock(depart)} · {routes.condition_used.label}
          </div>
        </div>
        <button type="button" className="icon-btn" aria-label="Clear route" onClick={onClear}>
          ×
        </button>
      </header>
      {pathpro && <RouteRow label="PathPro route" route={pathpro} kind="pp" />}
      <RouteRow label={pathpro ? 'Fastest route' : 'Route'} route={fastest} kind="fast" />
      <p className="explanation" data-testid="route-explanation">
        {explanation ?? templateSummary(routes)}
      </p>
      <div className="card-actions">
        {onListen && (
          <button type="button" className="chip" onClick={onListen}>
            🔊 Listen
          </button>
        )}
        {walk && pathpro && (
          <button
            type="button"
            className="chip"
            aria-pressed={walk.active}
            onClick={walk.active ? walk.onStop : walk.onStart}
          >
            {walk.active ? `■ Stop preview (${Math.round(walk.progress * 100)}%)` : '▶ Preview walk'}
          </button>
        )}
      </div>
      {walk?.banner && (
        <p className="walk-banner" role="status" aria-live="assertive">
          {walk.banner}
        </p>
      )}
      {pathpro && routes.avoided.length > 0 && (
        <div className="avoided" aria-label="High-risk stretches the PathPro route avoids">
          <span className="faint">
            Avoids {routes.avoided.length} high-risk stretch{routes.avoided.length === 1 ? '' : 'es'}:
          </span>
          {routes.avoided.slice(0, 4).map((a) => (
            <button key={a.seg_id} type="button" className="chip" onClick={() => onFocusSegment?.(a.seg_id)}>
              {a.name} <span className="num">{a.score}</span>
            </button>
          ))}
        </div>
      )}
      {routes.message && pathpro && <p className="faint">{routes.message}</p>}
      {routes.reports.length > 0 && (
        <p className="route-reports" data-testid="route-reports">
          <span className="report-dot" aria-hidden="true" /> {routeReportsLine(routes.reports)}
        </p>
      )}
      {routes.unavoidable.length > 0 && (
        <p className="faint">Both routes use {routes.unavoidable.join(', ')} — take extra care there.</p>
      )}
      <div className="hot-list" aria-label="Highest-risk stretches on the fastest route">
        {fastest.top_segments.map((s) => (
          <button key={s.seg_id} type="button" className="chip" onClick={() => onSelectSegment(s.seg_id)}>
            <span className="dot" style={{ background: cssColor(s.score) }} aria-hidden="true" />
            {s.name} <span className="num">{s.score}</span>
          </button>
        ))}
      </div>
      <TrustNote />
    </section>
  )
}
