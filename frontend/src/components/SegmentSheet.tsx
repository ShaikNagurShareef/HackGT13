import type { SegmentDetail } from '../api/schemas'
import { cssColor } from '../lib/bands'
import { atlantaParts, formatClock } from '../lib/time'
import { HourlyChart } from './HourlyChart'
import { ImagineStreet } from './ImagineStreet'
import { StreetReports } from './StreetReports'

/** Local one-line summary used when the explanation service is unreachable. */
export function segmentSummary(detail: SegmentDetail): string {
  const top = detail.factors.find((f) => f.points > 0)
  const driver = top ? ` The biggest contributor is ${top.label.toLowerCase()}.` : ''
  return `${detail.name} scores ${detail.score} (${detail.band}) for traffic risk at this time.${driver}`
}

const CONFIDENCE_LABEL = { high: 'High confidence', medium: 'Medium confidence', limited: 'Limited data' }

export function ScoreDial({ score, band }: { score: number; band: string }) {
  const r = 42
  const circ = 2 * Math.PI * r
  const dash = (Math.max(0, Math.min(100, score)) / 100) * circ * 0.75
  return (
    <div className="dial" role="img" aria-label={`Traffic risk ${score} of 100, ${band}`}>
      <svg viewBox="0 0 100 100" aria-hidden="true">
        <circle cx="50" cy="50" r={r} className="dial-track" strokeDasharray={`${circ * 0.75} ${circ}`} />
        <circle
          cx="50"
          cy="50"
          r={r}
          className="dial-value"
          stroke={cssColor(score)}
          strokeDasharray={`${dash} ${circ}`}
        />
      </svg>
      <div className="dial-text">
        <span className="dial-score num">{score}</span>
        <span className="dial-band">{band}</span>
      </div>
    </div>
  )
}

type Attribution = Pick<SegmentDetail, 'baseline_points' | 'factors' | 'remainder_points' | 'score'>

export function FactorBars({ detail }: { detail: Attribution }) {
  const rows = [
    { key: 'baseline', label: 'Typical street at a typical hour', points: detail.baseline_points },
    ...detail.factors,
    { key: 'remainder', label: 'Other factors', points: detail.remainder_points },
  ]
  const maxAbs = Math.max(1, ...rows.map((r) => Math.abs(r.points)))
  return (
    <ul className="factors" aria-label="What drives this score">
      {rows.map((r) => {
        const width = `${(Math.abs(r.points) / maxAbs) * 50}%`
        const positive = r.points >= 0
        return (
          <li key={r.key} className="factor">
            <span className="factor-label">{r.label}</span>
            <span className="factor-track" aria-hidden="true">
              <span className={`factor-bar ${positive ? 'up' : 'down'}`} style={{ width }} />
            </span>
            <span className="factor-points num">
              {positive ? '+' : '−'}
              {Math.abs(r.points)}
            </span>
          </li>
        )
      })}
      <li className="factor factor-total">
        <span className="factor-label">Score</span>
        <span />
        <span className="factor-points num">{detail.score}</span>
      </li>
    </ul>
  )
}

export interface SegmentSheetProps {
  detail: SegmentDetail
  explanation: string | null
  onClose: () => void
  onAbout: () => void
  onListen?: () => void
  onReported?: () => void
  /** Ask PathPro about this street; absent when Ask is unavailable (demo). */
  onAsk?: () => void
  /** Ride-network street: the pedestrian crash count, hourly chart, and reports are walk-network data. */
  rideNetwork?: boolean
}

export function SegmentSheet({ detail, explanation, onClose, onAbout, onListen, onReported, onAsk, rideNetwork = false }: SegmentSheetProps) {
  const h = detail.history
  const pct = (x: number) => `${Math.round(x * 100)}%`
  return (
    <section className="sheet panel" aria-label={`Traffic risk for ${detail.name}`}>
      <header className="sheet-head">
        <div>
          <h2 className="sheet-title">{detail.name}</h2>
          <div className="faint">
            {formatClock(new Date(detail.at))} · {detail.condition_used.label}
          </div>
        </div>
        <button type="button" className="icon-btn" aria-label="Close details" onClick={onClose}>
          ×
        </button>
      </header>
      <div className="sheet-score">
        <ScoreDial score={detail.score} band={detail.band} />
        <span className={`badge badge-${detail.confidence}`}>{CONFIDENCE_LABEL[detail.confidence]}</span>
      </div>
      <p className="explanation" data-testid="segment-explanation">
        {explanation ?? 'Loading explanation…'}
      </p>
      {onListen && explanation && (
        <button type="button" className="chip" onClick={onListen}>
          🔊 Listen
        </button>
      )}
      <FactorBars detail={detail} />
      <dl className="history">
        <div>
          <dt className="faint">Crashes here ({h.period})</dt>
          <dd className="num">{h.crashes.toFixed(0)}</dd>
        </div>
        {!rideNetwork && (
          <div>
            <dt className="faint">Involving pedestrians</dt>
            <dd className="num">{h.ped_crashes.toFixed(0)}</dd>
          </div>
        )}
        <div>
          <dt className="faint">After dark</dt>
          <dd className="num">{pct(h.dark_share)}</dd>
        </div>
        <div>
          <dt className="faint">Wet pavement</dt>
          <dd className="num">{pct(h.wet_share)}</dd>
        </div>
      </dl>
      {!rideNetwork && <HourlyChart segId={detail.seg_id} highlightHour={atlantaParts(new Date(detail.at)).hour} />}
      {!rideNetwork && <StreetReports key={detail.seg_id} segId={detail.seg_id} onReported={onReported} />}
      {!rideNetwork && <ImagineStreet key={detail.seg_id} segId={detail.seg_id} streetName={detail.name} />}
      {detail.confidence === 'limited' && (
        <p className="faint">Few recorded crashes here — estimate based mostly on street characteristics.</p>
      )}
      <div className="sheet-links">
        <button type="button" className="link-btn" onClick={onAbout}>
          How is this calculated?
        </button>
        {onAsk && (
          <button type="button" className="link-btn" onClick={onAsk}>
            Ask about this street
          </button>
        )}
      </div>
    </section>
  )
}
