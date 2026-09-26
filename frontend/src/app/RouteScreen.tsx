import type { RoutePreference } from '../api/safetySchemas'
import { LocationNotice } from '../components/home/LocationNotice'
import { SafetyRouteNote } from '../components/safety/SafetyRouteNote'
import { RouteSheet, type RouteSheetProps } from '../components/route/RouteSheet'
import { TripHeader, type TripHeaderProps } from '../components/route/TripHeader'

export interface RouteScreenProps {
  header: TripHeaderProps
  notice: string | null
  onPickStart: () => void
  loading: boolean
  sheet: RouteSheetProps | null
  prefer?: RoutePreference
  /** Phone, personal safety mode: note the map shading and open its legend. */
  safetyNote?: (() => void) | null
}

/** Trip view: compact From/To header on top, the route sheet at the bottom. */
export function RouteScreen({ header, notice, onPickStart, loading, sheet, prefer, safetyNote = null }: RouteScreenProps) {
  const finding = prefer === 'lit_and_busy' ? 'Finding a well-lit, busier route…' : 'Finding the lower-risk route…'
  return (
    <>
      <div className="route-top">
        <TripHeader {...header} />
        {notice && <LocationNotice message={notice} onPickStart={onPickStart} />}
        {safetyNote && <SafetyRouteNote onOpenLegend={safetyNote} />}
      </div>
      {loading && (
        <section className="bsheet panel route-loading" aria-label="Finding routes" aria-busy="true">
          <span className="route-loading-bar" aria-hidden="true" />
          <p>{finding}</p>
        </section>
      )}
      {sheet && <RouteSheet key={sheet.routes.route_key} {...sheet} />}
    </>
  )
}
