import type { Condition } from '../api/client'
import { api } from '../api/client'
import type { Area, AskContext, SegmentDetail, TravelMode } from '../api/schemas'
import { AreaCard } from '../components/AreaCard'
import { SegmentSheet, segmentSummary } from '../components/SegmentSheet'
import { useExplanation } from '../hooks/useExplanation'
import { useTypewriter } from '../hooks/useTypewriter'
import { areaAskTarget, segmentAskTarget } from '../lib/askContext'
import { deviceSpeak, speak } from '../lib/voice'

export interface DetailLayerProps {
  area: Area | null
  detail: SegmentDetail | null
  cond: Condition
  onCloseArea: () => void
  onCloseDetail: () => void
  onAbout: () => void
  onReported: () => void
  /** A ride-network street: explained locally, without the walk-network hourly chart and reports. */
  rideNetwork?: boolean
  /** Network the street belongs to, sent with an Ask PathPro street question. */
  mode?: TravelMode
  /** Opens Ask PathPro about the street or area shown; absent when Ask is unavailable (demo). */
  onAsk?: (context: AskContext, label: string) => void
}

/** Street or City Pulse area sheet, layered over whatever screen is showing (EXP-01..05, CITY-02). */
export function DetailLayer(props: DetailLayerProps) {
  const { area, detail, cond, onCloseArea, onCloseDetail, onAbout, onReported, rideNetwork = false, mode = 'walk', onAsk } = props
  // The explanation service reads walk-network segment ids, so ride streets use the local summary.
  const segKey = detail && !rideNetwork ? `${detail.seg_id}|${detail.at}|${cond}` : null
  const segExplain = useExplanation(segKey, () => api.explainSegment(detail?.seg_id ?? 0, detail?.at ?? 'now', cond))
  const fallback = (segExplain.failed || rideNetwork) && detail ? segmentSummary(detail) : null
  const segText = useTypewriter(segExplain.result?.text ?? fallback)

  if (area) {
    const askArea = onAsk
      ? () => {
          const target = areaAskTarget(area, cond)
          onAsk(target.context, target.label)
        }
      : undefined
    return (
      <div className="detail-layer">
        <AreaCard area={area} onClose={onCloseArea} onAbout={onAbout} onAsk={askArea} />
      </div>
    )
  }
  if (!detail) return null
  const askStreet = onAsk
    ? () => {
        const target = segmentAskTarget(detail, cond, mode)
        onAsk(target.context, target.label)
      }
    : undefined
  return (
    <div className="detail-layer">
      <SegmentSheet
        detail={detail}
        explanation={segText}
        onListen={() => {
          const text = segText ?? segmentSummary(detail)
          // Server voice explains walk-network ids; a ride street is read on the device.
          if (rideNetwork) deviceSpeak(text)
          else void speak({ kind: 'segment', seg_id: detail.seg_id, t: detail.at, cond }, text)
        }}
        onClose={onCloseDetail}
        onAbout={onAbout}
        onReported={onReported}
        onAsk={askStreet}
        rideNetwork={rideNetwork}
      />
    </div>
  )
}
