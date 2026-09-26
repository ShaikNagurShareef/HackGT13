import { useEffect, useId, useState } from 'react'
import { ApiError, api } from '../api/client'
import { CATEGORY_LABELS, REPORT_CATEGORIES, type Report, type ReportCategory } from '../api/schemas'
import { walkersLabel } from '../lib/reports'

const THANKS = 'Thanks — other walkers will see this for 14 days.'
const UNAVAILABLE = 'REPORTS_UNAVAILABLE'

type Load = { segId: number; reports: Report[] } | 'hidden' | null

function upsert(reports: ReadonlyArray<Report>, saved: Report): Report[] {
  const others = reports.filter((r) => r.category !== saved.category)
  return [saved, ...others].sort((a, b) => b.confirmations - a.confirmations)
}

/** Community street reports (MongoDB Atlas). Context only: they never change a score. */
export function StreetReports({ segId, onReported }: { segId: number; onReported?: () => void }) {
  const [load, setLoad] = useState<Load>(null)
  const [sent, setSent] = useState<ReportCategory | null>(null)
  const [busy, setBusy] = useState(false)
  const [status, setStatus] = useState('')
  const headingId = useId()

  // Parents key this component by segment, so per-segment state starts fresh on remount.
  useEffect(() => {
    let cancelled = false
    api
      .segmentReports(segId)
      .then((reports) => !cancelled && setLoad({ segId, reports }))
      .catch(() => !cancelled && setLoad('hidden')) // unavailable, offline, or demo: hide quietly
    return () => {
      cancelled = true
    }
  }, [segId])

  if (load === null || load === 'hidden' || load.segId !== segId) return null
  const reports = load.reports

  const submit = (category: ReportCategory) => {
    setBusy(true)
    setStatus('')
    api
      .postReport(segId, category)
      .then((saved) => {
        setLoad({ segId, reports: upsert(reports, saved) })
        setSent(category)
        setStatus(THANKS)
        onReported?.()
      })
      .catch((e: unknown) => {
        if (e instanceof ApiError && e.code === UNAVAILABLE) setLoad('hidden')
        else setStatus(e instanceof ApiError ? e.message : 'Could not send the report.')
      })
      .finally(() => setBusy(false))
  }

  return (
    <section className="street-reports" aria-labelledby={headingId}>
      <h3 id={headingId} className="street-reports-title">
        Report a street issue
      </h3>
      {reports.length > 0 && (
        <ul className="street-reports-list" aria-label="Community reports on this street">
          {reports.map((r) => (
            <li key={r.category}>
              <span>{r.label}</span> <span className="faint num">· {walkersLabel(r.confirmations)}</span>
            </li>
          ))}
        </ul>
      )}
      <div className="street-reports-chips">
        {REPORT_CATEGORIES.map((c) => (
          <button
            key={c}
            type="button"
            className="chip"
            aria-pressed={sent === c}
            disabled={busy}
            onClick={() => submit(c)}
          >
            {CATEGORY_LABELS[c]}
          </button>
        ))}
      </div>
      <p className="faint street-reports-status" role="status" aria-live="polite">
        {status}
      </p>
      <p className="faint">Community reports are shown for context and never change traffic-risk scores.</p>
    </section>
  )
}
