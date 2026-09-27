import type { Area } from '../api/schemas'
import { formatClock } from '../lib/time'
import { FactorBars, ScoreDial } from './SegmentSheet'
import { AskButton } from './ask/AskButton'
import { Icon } from './ui/Icon'

const CONFIDENCE_LABEL = { high: 'High confidence', medium: 'Medium confidence', limited: 'Limited data' }

export interface AreaCardProps {
  area: Area
  onClose: () => void
  onAbout: () => void
  /** Ask PathPro about this area; absent when Ask is unavailable (demo). */
  onAsk?: () => void
}

/** City Pulse: citywide area traffic-risk card (CITY-02/03). */
export function AreaCard({ area, onClose, onAbout, onAsk }: AreaCardProps) {
  return (
    <section className="sheet panel" aria-label="Area traffic risk">
      <header className="sheet-head">
        <div>
          <h2 className="sheet-title">City Pulse · this area</h2>
          <div className="faint">
            {formatClock(new Date(area.at))} · {area.condition_used.label}
          </div>
        </div>
        <button type="button" className="icon-btn" aria-label="Close area" onClick={onClose}>
          <Icon name="close" size={18} />
        </button>
      </header>
      <div className="sheet-score">
        <ScoreDial score={area.score} band={area.band} />
        <span className={`badge badge-${area.confidence}`}>{CONFIDENCE_LABEL[area.confidence]}</span>
      </div>
      {!area.in_street_coverage && (
        <p className="faint" data-testid="coverage-note">
          Street-level routing covers Midtown, Georgia Tech, and Downtown. This is an area-level traffic-risk
          estimate.
        </p>
      )}
      <FactorBars detail={area} />
      <dl className="history">
        <div>
          <dt className="faint">Crashes in this area ({area.period})</dt>
          <dd className="num">{area.crashes.toFixed(0)}</dd>
        </div>
        <div>
          <dt className="faint">Involving pedestrians</dt>
          <dd className="num">{area.ped_crashes.toFixed(0)}</dd>
        </div>
      </dl>
      <div className="sheet-links">
        <button type="button" className="link-btn" onClick={onAbout}>
          How is this calculated?
        </button>
        {onAsk && <AskButton label="Ask about this area" onClick={onAsk} />}
      </div>
    </section>
  )
}
