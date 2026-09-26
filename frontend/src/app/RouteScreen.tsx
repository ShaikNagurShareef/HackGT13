import { LocationNotice } from '../components/home/LocationNotice'
import { RouteSheet, type RouteSheetProps } from '../components/route/RouteSheet'
import { TripHeader, type TripHeaderProps } from '../components/route/TripHeader'

export interface RouteScreenProps {
  header: TripHeaderProps
  notice: string | null
  onPickStart: () => void
  loading: boolean
  sheet: RouteSheetProps | null
}

/** Trip view: compact From/To header on top, the route sheet at the bottom. */
export function RouteScreen({ header, notice, onPickStart, loading, sheet }: RouteScreenProps) {
  return (
    <>
      <div className="route-top">
        <TripHeader {...header} />
        {notice && <LocationNotice message={notice} onPickStart={onPickStart} />}
      </div>
      {loading && (
        <section className="bsheet panel route-loading" aria-label="Finding routes" aria-busy="true">
          <span className="route-loading-bar" aria-hidden="true" />
          <p>Finding the lower-risk route…</p>
        </section>
      )}
      {sheet && <RouteSheet key={sheet.routes.route_key} {...sheet} />}
    </>
  )
}
