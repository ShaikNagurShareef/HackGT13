import { LegendChip } from '../components/home/LegendChip'
import { SearchPill } from '../components/home/SearchPill'
import { StatusChip } from '../components/home/StatusChip'
import { SuggestionCard } from '../components/home/SuggestionCard'
import { WelcomeToast } from '../components/home/WelcomeToast'
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
        {props.welcomeDataThrough && <WelcomeToast dataThrough={props.welcomeDataThrough} onDismiss={props.onDismissWelcome} />}
        <LegendChip reports={props.reportsLegend} />
      </div>
    </>
  )
}
