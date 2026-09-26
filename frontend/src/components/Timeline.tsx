import type { DayGroup } from '../lib/time'
import { DAY_GROUP_LABEL, hourLabel } from '../lib/time'

export const START_HOUR = 6 // slider runs 6 AM -> 5 AM (PRD TIDE-01)

export function hourAt(position: number): number {
  return (START_HOUR + position) % 24
}

export function positionOf(hour: number): number {
  return (hour - START_HOUR + 24) % 24
}

export interface TimelineProps {
  hour: number
  onHour: (hour: number) => void
  playing: boolean
  onTogglePlay: () => void
  medians: ReadonlyArray<number>
  lights: ReadonlyArray<string>
  condLabel: string
  day: DayGroup
  onDay: (day: DayGroup) => void
}

const DAYS: ReadonlyArray<DayGroup> = ['weekday', 'friday', 'saturday', 'sunday']

function Sparkline({ medians, hour }: { medians: ReadonlyArray<number>; hour: number }) {
  if (medians.length !== 24) return null
  const pts = Array.from({ length: 24 }, (_, p) => {
    const m = medians[hourAt(p)]
    return `${(p / 23) * 100},${30 - (m / 100) * 28}`
  }).join(' ')
  const x = (positionOf(hour) / 23) * 100
  return (
    <svg className="sparkline" viewBox="0 0 100 32" preserveAspectRatio="none" aria-hidden="true">
      <polyline points={pts} fill="none" stroke="currentColor" strokeWidth="1.2" vectorEffect="non-scaling-stroke" />
      <line x1={x} x2={x} y1="0" y2="32" stroke="var(--focus)" strokeWidth="1" vectorEffect="non-scaling-stroke" />
    </svg>
  )
}

export function Timeline(props: TimelineProps) {
  const { hour, medians, lights } = props
  const median = medians[hour] ?? 0
  const light = lights[hour] ?? 'day'
  const icon = light === 'day' ? '☀' : light === 'twilight' ? '◐' : '☾'
  const valueText = `${hourLabel(hour)}, ${props.condLabel.toLowerCase()}, citywide median risk ${median}`
  return (
    <section className="timeline panel" aria-label="Risk Tides timeline">
      <div className="timeline-head">
        <button
          type="button"
          className="icon-btn"
          onClick={props.onTogglePlay}
          aria-label={props.playing ? 'Pause Risk Tides' : 'Play Risk Tides'}
        >
          {props.playing ? '❚❚' : '▶'}
        </button>
        <div className="timeline-now">
          <span className="timeline-hour num" aria-hidden="true">
            <span className="light-icon">{icon}</span> {hourLabel(hour)}
          </span>
          <span className="faint">
            Citywide median <span className="num">{median}</span> · {props.condLabel}
          </span>
        </div>
        <div className="day-chips" role="group" aria-label="Day of week">
          {DAYS.map((d) => (
            <button key={d} type="button" className="chip" aria-pressed={props.day === d} onClick={() => props.onDay(d)}>
              {DAY_GROUP_LABEL[d]}
            </button>
          ))}
        </div>
      </div>
      <Sparkline medians={medians} hour={hour} />
      <input
        className="timeline-slider"
        type="range"
        min={0}
        max={23}
        step={1}
        value={positionOf(hour)}
        onChange={(e) => props.onHour(hourAt(Number(e.target.value)))}
        aria-label="Hour of day"
        aria-valuetext={valueText}
      />
      <div className="timeline-ticks faint" aria-hidden="true">
        {[0, 6, 12, 18, 23].map((p) => (
          <span key={p}>{hourLabel(hourAt(p))}</span>
        ))}
      </div>
    </section>
  )
}
