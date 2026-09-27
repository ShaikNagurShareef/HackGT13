import type { RoutineSuggestion } from '../../lib/routines'
import { scopeLine } from '../../lib/safety'
import { SuggestionCard } from '../home/SuggestionCard'
import { OptionsContent, type OptionsContentProps } from '../options/OptionsContent'
import { SearchPanel, type SearchPanelProps } from '../search/SearchPanel'
import { SidebarBrand } from './SidebarBrand'
import { AskButton } from '../ask/AskButton'

export interface DesktopHomeProps {
  suggestion: RoutineSuggestion | null
  etaMin: number | null
  onGo: (s: RoutineSuggestion) => void
  onDismissSuggestion: () => void
  search: Omit<SearchPanelProps, 'autoFocus'>
  options: Omit<OptionsContentProps, 'timeline'>
  onAbout: () => void
  /** Ask PathPro (Backboard); absent in demo mode. */
  onAsk?: () => void
  safetyAvailable?: boolean
}

/** Desktop (≥1024 px) home sidebar: brand, inline search, and the map options in plain view. */
export function DesktopHome({ suggestion, etaMin, onGo, onDismissSuggestion, search, options, onAbout, onAsk, safetyAvailable = false }: DesktopHomeProps) {
  return (
    <aside className="desk-sidebar" aria-label="PathPro">
      <SidebarBrand />
      {suggestion && <SuggestionCard suggestion={suggestion} etaMin={etaMin} onGo={onGo} onDismiss={onDismissSuggestion} />}
      <section className="desk-search" aria-label="Where to?">
        <SearchPanel {...search} />
      </section>
      <div className="desk-options">
        <OptionsContent {...options} />
      </div>
      <footer className="desk-footer">
        <div className="sheet-links sheet-footer">
          {onAsk && <AskButton label="Ask PathPro" onClick={onAsk} variant="entry" />}
          <button type="button" className="link-btn" onClick={onAbout}>
            About PathPro
          </button>
        </div>
        <span className="faint">{scopeLine(safetyAvailable)}</span>
      </footer>
    </aside>
  )
}
