import type { RoutePreference } from '../api/safetySchemas'
import { LocationNotice } from '../components/home/LocationNotice'
import { SafetyRouteNote } from '../components/safety/SafetyRouteNote'
import { ModeTabs, type ModeTabsProps } from '../components/route/ModeTabs'
import { RouteSheet, type RouteSheetProps } from '../components/route/RouteSheet'
import { isRideMode } from '../lib/modes'
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
  /** Walk · Bike · E-bike · Scooter tabs under the trip header. */
  modes?: ModeTabsProps | null
}

/** Trip view: compact From/To header on top, the route sheet at the bottom. */
function findingText(prefer: RoutePreference | undefined, ride: boolean): string {
  if (ride) return 'Finding the lower-risk ride…'
  return prefer === 'lit_and_busy' ? 'Finding a well-lit, busier route…' : 'Finding the lower-risk route…'
}

export function RouteScreen({ header, notice, onPickStart, loading, sheet, prefer, safetyNote = null, modes = null }: RouteScreenProps) {
  const finding = findingText(prefer, modes != null && isRideMode(modes.selected))
  return (
    <>
      <div className="route-top">
        <TripHeader {...header} />
        {modes && <ModeTabs {...modes} />}
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
