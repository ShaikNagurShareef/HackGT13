import { useEffect, useState } from 'react'
import { AgentGlyph } from './AgentGlyph'

/** Session flag: the launcher's attention pulse plays on its first appearance only. */
export const ASK_FAB_INTRO_KEY = 'pathpro:ask-fab-intro'

function introSeen(): boolean {
  try {
    return window.sessionStorage.getItem(ASK_FAB_INTRO_KEY) === '1'
  } catch {
    return true // storage blocked: skip the pulse rather than replay it on every mount
  }
}

function markIntroSeen(): void {
  try {
    window.sessionStorage.setItem(ASK_FAB_INTRO_KEY, '1')
  } catch {
    // storage blocked: nothing to remember
  }
}

export interface AskFabProps {
  onClick: () => void
  /** The Ask panel is showing (the desktop card docks above this button). */
  open?: boolean
}

/** Ask PathPro launcher: a round agent button on the map, bottom-right. */
export function AskFab({ onClick, open = false }: AskFabProps) {
  const [intro] = useState(() => !introSeen())
  useEffect(() => {
    if (intro) markIntroSeen()
  }, [intro])

  return (
    <button
      type="button"
      className="ask-fab"
      aria-label="Ask PathPro"
      title="Ask PathPro"
      aria-haspopup="dialog"
      aria-expanded={open}
      data-intro={intro ? 'true' : undefined}
      onClick={onClick}
    >
      <AgentGlyph size={28} />
    </button>
  )
}
