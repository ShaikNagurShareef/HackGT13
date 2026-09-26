/** First-run welcome: two lines, dismissible, never blocks the map (TRUST-02). */
export function WelcomeToast({ dataThrough, onDismiss }: { dataThrough: string; onDismiss: () => void }) {
  return (
    <section className="welcome-toast panel" aria-label="Welcome to PathPro">
      <p className="welcome-lede">See traffic risk before you walk into it.</p>
      <p className="welcome-scope">
        Traffic risk only — not crime or personal safety. Crash data through {dataThrough}.
      </p>
      <button type="button" className="btn primary small" onClick={onDismiss}>
        Got it
      </button>
    </section>
  )
}
