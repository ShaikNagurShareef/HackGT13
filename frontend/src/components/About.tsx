import type { Meta } from '../api/schemas'
import { useDialog } from '../hooks/useDialog'

function pct(v: unknown): string {
  return typeof v === 'number' ? `${Math.round(v * 100)}%` : '—'
}

export function About({ meta, onClose }: { meta: Meta; onClose: () => void }) {
  const h = meta.headline
  const ci = Array.isArray(h.capture_top10_ci95) ? (h.capture_top10_ci95 as number[]) : []
  useDialog(onClose)
  return (
    <div className="scrim" role="dialog" aria-modal="true" aria-labelledby="about-title" onClick={onClose}>
      <section className="about panel" onClick={(e) => e.stopPropagation()}>
        <header className="sheet-head">
          <h1 id="about-title">How PathPro works</h1>
          <button type="button" className="icon-btn" aria-label="Close" onClick={onClose} autoFocus>
            ×
          </button>
        </header>
        <h2>What the score means</h2>
        <p>
          Each street gets a 0–100 score: its place on a citywide scale of how concentrated pedestrian traffic
          crashes are there, at that hour, in that weather. 75+ means the top quarter of the city. It describes where
          and when crashes have concentrated — not a guarantee about any single walk.
        </p>
        <h2>How it's built</h2>
        <p>
          A statistical model learns from street design (traffic volume, speed limits, lanes, crossings, transit
          stops), pedestrian activity, and five years of public crash records, then blends each street's own history
          in (Empirical Bayes). A second model learns how crashes shift by hour, day, light, and rain. Every score is
          split into the factors that drive it. An AI writes the plain-English summary from those numbers only — it
          never produces a score.
        </p>
        <h2>How well it works</h2>
        <p>
          Trained on 2020–2023 and tested on held-out {String(h.test_year ?? 2024)} crashes: the 10% of street length
          ranked highest held <strong>{pct(h.capture_top10)}</strong> of pedestrian crashes (95% CI {pct(ci[0])}–
          {pct(ci[1])}), versus 10% by chance and {pct(h.count_only_capture_top10)} by ranking on past crashes alone.
          On the City High Injury Network's own share of street length, PathPro held {pct(h.capture_at_hin_share)}{' '}
          vs {pct(h.hin_capture_at_own_share)}.
        </p>
        <h2>Limitations</h2>
        <ul>
          <li>Busy streets look riskier partly because more people walk there (exposure bias).</li>
          <li>Crash reports are incomplete, and streets change after crashes (new signals, road diets).</li>
          <li>Darkness and rain effects are small in Atlanta's data and not separately significant on holdout.</li>
          <li>No demographic, income, or crime data is used anywhere.</li>
        </ul>
        <h2>Sources</h2>
        <p className="faint">
          Atlanta Regional Commission, City of Atlanta, Central Atlanta Progress, and Georgia Tech crash layers;
          StreetLight pedestrian activity and 2023 traffic volumes (City of Atlanta); OpenStreetMap; Open-Meteo. Model{' '}
          <span className="num">{meta.model_version}</span> · crash data through {meta.data_through}.
        </p>
        <h2>Emergency</h2>
        <p>
          <a href="tel:911">Call 911</a> · <a href="tel:4048942500">Georgia Tech Police 404-894-2500</a>. PathPro is
          not an emergency service.
        </p>
      </section>
    </div>
  )
}
