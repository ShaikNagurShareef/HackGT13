import { LegendChip } from '../components/home/LegendChip'
import { SearchPill } from '../components/home/SearchPill'
import { StatusChip } from '../components/home/StatusChip'
import { SuggestionCard } from '../components/home/SuggestionCard'
import { WelcomeToast } from '../components/home/WelcomeToast'
import type { SafetyLegendProps } from '../components/safety/SafetyLegend'
import { SafetyLegendChip } from '../components/safety/SafetyLegendChip'
import type { RoutineSuggestion } from '../lib/routines'

export interface HomeScreenProps {
  suggestion: RoutineSuggestion | null
  etaMin: number | null
  onGo: (s: RoutineSuggestion) => void
  onDismissSuggestion: () => void
  onOpenSearch: () => void
  statusLabel: string | null
  onOpenOptions: () => void
  welcomeDataThrough: string | null
  onDismissWelcome: () => void
  reportsLegend: boolean
  safetyAvailable?: boolean
  /** Personal safety mode: the safety legend replaces the traffic-risk chip. */
  safetyLegend?: SafetyLegendProps | null
  /** Street legend title for the network on the map (walk or ride). */
  legendTitle?: string
}

/** Map-first home: one search pill (plus at most one routine card and a status chip). */
export function HomeScreen(props: HomeScreenProps) {
  return (
    <>
      <div className="home-top">
        {props.suggestion && (
          <SuggestionCard suggestion={props.suggestion} etaMin={props.etaMin} onGo={props.onGo} onDismiss={props.onDismissSuggestion} />
        )}
        <SearchPill onOpen={props.onOpenSearch} />
        <StatusChip label={props.statusLabel} onClick={props.onOpenOptions} />
      </div>
      <div className="home-bottom">
        {props.welcomeDataThrough && (
          <WelcomeToast dataThrough={props.welcomeDataThrough} safetyAvailable={props.safetyAvailable} onDismiss={props.onDismissWelcome} />
        )}
        {props.safetyLegend ? <SafetyLegendChip {...props.safetyLegend} /> : <LegendChip reports={props.reportsLegend} title={props.legendTitle} />}
      </div>
    </>
  )
}
