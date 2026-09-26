import { LogoMark } from './ui/LogoMark'

export type StatusScreenProps = { kind: 'loading' } | { kind: 'error'; message: string }

/** Full-screen loading / failure state before the map bundle is ready. */
export function StatusScreen(props: StatusScreenProps) {
  const loading = props.kind === 'loading'
  return (
    <main className="app status-screen" aria-busy={loading}>
      <div className="status-card">
        <LogoMark size={44} />
        <p className="status-brand">PathPro</p>
        {loading ? (
          <>
            <p role="status">Loading the traffic-risk map…</p>
            <span className="route-loading-bar" aria-hidden="true" />
          </>
        ) : (
          <>
            <p role="alert">{props.message}</p>
            <div className="status-actions">
              <button type="button" className="btn primary" onClick={() => window.location.reload()}>
                Try again
              </button>
              <a className="btn" href="?demo=1">
                Try the offline demo
              </a>
            </div>
          </>
        )}
      </div>
    </main>
  )
}
