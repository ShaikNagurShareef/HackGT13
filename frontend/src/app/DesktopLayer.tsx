import { DesktopHome, type DesktopHomeProps } from '../components/desktop/DesktopHome'
import { SidebarBrand } from '../components/desktop/SidebarBrand'
import { WelcomeToast } from '../components/home/WelcomeToast'
import { Timeline, type TimelineProps } from '../components/Timeline'
import { RouteScreen, type RouteScreenProps } from './RouteScreen'

export interface DesktopLayerProps {
  screen: 'home' | 'route' | 'nav'
  home: DesktopHomeProps
  route: RouteScreenProps
  destination: string
  timeline: TimelineProps
  welcomeDataThrough: string | null
  onDismissWelcome: () => void
}

/** Desktop (≥1024 px): a persistent sidebar beside the map, with Risk Tides docked on the map. */
export function DesktopLayer({ screen, home, route, destination, timeline, welcomeDataThrough, onDismissWelcome }: DesktopLayerProps) {
  return (
    <>
      {screen === 'home' && <DesktopHome {...home} />}
      {screen === 'route' && (
        <aside className="desk-sidebar desk-route" aria-label="PathPro">
          <SidebarBrand />
          <RouteScreen {...route} />
        </aside>
      )}
      {screen === 'nav' && (
        <aside className="desk-sidebar" aria-label="PathPro">
          <SidebarBrand />
          <p className="desk-nav-note">Walking to {destination}. The banner on the map shows what's next.</p>
        </aside>
      )}
      {screen !== 'nav' && (
        <div className="tides-dock">
          <Timeline {...timeline} />
        </div>
      )}
      {screen === 'home' && welcomeDataThrough && (
        <div className="desk-toast">
          <WelcomeToast dataThrough={welcomeDataThrough} onDismiss={onDismissWelcome} />
        </div>
      )}
    </>
  )
}
