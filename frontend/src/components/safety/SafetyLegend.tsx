import type { SafetyMeta } from '../../api/safetySchemas'
import { CRIME_BANDS, HELP_POINT_KINDS } from '../../api/safetySchemas'
import {
  CRIME_BAND_INFO,
  CRIME_LAYER_NAME,
  HELP_POINT_INFO,
  dayPartFor,
  hoursLabel,
  rgbCss,
  type SafetyLayers,
} from '../../lib/safety'
import { hourLabel } from '../../lib/time'
import { FairnessNote } from './FairnessNote'
import { SafetySources } from './SafetySources'

export interface SafetyLegendProps {
  meta: SafetyMeta | null
  /** Risk Tides hour: the legend names its day part. */
  hour: number
  layers: SafetyLayers
  tooWide: boolean
  /** Map-side versions (phone chip, desktop dock) leave the sources to the sheet and About. */
  compact?: boolean
}

const ALPHA_SCALE = 255

function whenLabel(meta: SafetyMeta | null, hour: number): string {
  const part = meta ? dayPartFor(hour, meta.day_parts) : null
  if (!part) return hourLabel(hour)
  const hours = hoursLabel(part)
  return hours ? `${part.label} · ${hours}` : part.label
}

/** Legend for the personal-safety map mode: crime bands in words, overlays, the fairness note. */
export function SafetyLegend({ meta, hour, layers, tooWide, compact = false }: SafetyLegendProps) {
  const overlays = layers.lit || layers.busy || layers.help
  return (
    <section className="legend safety-legend panel" aria-label="Personal safety legend">
      <div className="legend-title safety-legend-title">
        <span>Personal safety</span>
        <span className="safety-when num">{whenLabel(meta, hour)}</span>
      </div>
      {tooWide && (
        <p className="safety-zoom" role="status">
          Zoom in to see the personal safety layer.
        </p>
      )}
      {layers.crimes && (
        <div className="safety-crime-key">
          <div className="safety-sub">{CRIME_LAYER_NAME}, last 12 months</div>
          <ul className="safety-bands">
            {CRIME_BANDS.map((band) => {
              const info = CRIME_BAND_INFO[band]
              return (
                <li key={band}>
                  <span className="safety-swatch" style={{ background: rgbCss(info.rgb, info.alpha / ALPHA_SCALE + 0.25) }} aria-hidden="true" />
                  {info.label}
                </li>
              )
            })}
          </ul>
          <FairnessNote />
        </div>
      )}
      {overlays && (
        <ul className="safety-keys">
          {layers.lit && (
            <li>
              <span className="key-glow" aria-hidden="true" /> Well-lit streets
            </li>
          )}
          {layers.busy && (
            <li>
              <span className="key-ring" aria-hidden="true" /> Busier streets
            </li>
          )}
          {layers.help &&
            HELP_POINT_KINDS.map((kind) => (
              <li key={kind} className={kind === 'blue_light' ? 'key-help key-help-lead' : 'key-help'}>
                <span className="key-badge" style={{ background: rgbCss(HELP_POINT_INFO[kind].rgb) }} aria-hidden="true" />
                {HELP_POINT_INFO[kind].label}
              </li>
            ))}
        </ul>
      )}
      {!compact && meta && <SafetySources meta={meta} />}
    </section>
  )
}
