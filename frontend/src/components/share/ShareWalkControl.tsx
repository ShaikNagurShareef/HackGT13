import { useEffect } from 'react'
import type { SharePhase } from '../../hooks/useShareWalk'
import { Icon } from '../ui/Icon'

const NOTICE_MS = 6000

type Props = {
  phase: SharePhase
  notice: string | null
  onStart: () => void
  onResend: () => void
  onStop: () => void
  onDismissNotice: () => void
}

/** "Share my walk" in navigation; "Sharing live · Send link · Stop" once a friend can follow. */
export function ShareWalkControl({ phase, notice, onStart, onResend, onStop, onDismissNotice }: Props) {
  useEffect(() => {
    if (!notice) return
    const id = window.setTimeout(onDismissNotice, NOTICE_MS)
    return () => window.clearTimeout(id)
  }, [notice, onDismissNotice])

  const starting = phase === 'starting'
  return (
    <div className="share-walk">
      {phase === 'live' ? (
        <div className="share-live panel" role="group" aria-label="Sharing your walk">
          <span className="share-live-dot" aria-hidden="true" />
          <span className="share-live-text">Sharing live</span>
          <button type="button" className="share-chip" onClick={onResend}>
            Send link
          </button>
          <span className="share-sep" aria-hidden="true">
            ·
          </span>
          <button type="button" className="share-chip share-stop" onClick={onStop}>
            Stop
          </button>
        </div>
      ) : (
        <button type="button" className="btn share-btn panel" onClick={onStart} disabled={starting}>
          <Icon name="share" size={18} />
          {starting ? 'Starting…' : 'Share my walk'}
        </button>
      )}
      <div className="share-notice-slot" role="status" aria-live="polite">
        {notice && (
          <p className="share-notice panel">
            <span>{notice}</span>
            <button type="button" className="link-btn" onClick={onDismissNotice}>
              Dismiss
            </button>
          </p>
        )}
      </div>
    </div>
  )
}
