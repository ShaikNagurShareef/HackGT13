import { About } from '../components/About'
import { AskPanel } from '../components/ask/AskPanel'
import { OptionsSheet, type OptionsSheetProps } from '../components/options/OptionsSheet'
import { SearchSheet } from '../components/search/SearchSheet'
import type { ModeTabsProps } from '../components/route/ModeTabs'
import type { Meta } from '../api/schemas'
import type { SafetyMeta } from '../api/safetySchemas'
import type { Routines } from '../hooks/useRoutines'
import type { Panel } from './useTripActions'
import type { useTripActions } from './useTripActions'

type Actions = ReturnType<typeof useTripActions>
type OptionValues = Omit<OptionsSheetProps, 'onAbout' | 'onAsk' | 'onClearHistory' | 'onClose'>

export interface PanelsProps {
  panel: Panel
  meta: Meta
  actions: Actions
  routines: Routines
  canUseLocation: boolean
  welcome: boolean
  onDismissWelcome: () => void
  options: OptionValues
  /** Personal-safety meta when the server has the layer (About section, welcome scope). */
  safetyMeta?: SafetyMeta | null
  /** Travel-mode chip in the search sheet. */
  modes?: ModeTabsProps | null
  /** Ask PathPro entry; omitted in demo mode (it needs the live API). */
  askAvailable?: boolean
}

/** The one modal sheet that can be open at a time: search, options, or About. */
export function Panels(props: PanelsProps) {
  const { panel, meta, actions, routines, canUseLocation, welcome, onDismissWelcome, options, safetyMeta = null, modes = null, askAvailable = false } = props
  if (!panel) return null
  if (panel.kind === 'about') return <About meta={meta} safetyMeta={safetyMeta} onClose={actions.closePanel} />
  if (panel.kind === 'ask') return askAvailable ? <AskPanel onClose={actions.closePanel} /> : null
  if (panel.kind === 'options') {
    return (
      <OptionsSheet
        {...options}
        onAbout={() => actions.setPanel({ kind: 'about' })}
        onAsk={askAvailable ? () => actions.setPanel({ kind: 'ask' }) : undefined}
        onClearHistory={routines.clear}
        onClose={actions.closePanel}
      />
    )
  }
  const { field } = panel
  return (
    <SearchSheet
      key={field}
      field={field}
      welcome={welcome}
      safetyAvailable={safetyMeta != null}
      onDismissWelcome={onDismissWelcome}
      note={actions.searchNote(field)}
      suggestions={routines.suggestions}
      saved={routines.saved}
      recents={routines.recents}
      canUseLocation={canUseLocation}
      onUseLocation={actions.startFromMyLocation}
      onPick={(place) => actions.pickPlace(field, place)}
      onPickSuggestion={actions.planSuggestion}
      onEditSaved={actions.editSaved}
      onClose={actions.closePanel}
      modes={modes}
    />
  )
}
