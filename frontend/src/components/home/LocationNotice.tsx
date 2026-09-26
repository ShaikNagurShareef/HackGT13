/** Friendly fallback when GPS can't give a start: says why, offers to pick one. */
export function LocationNotice({ message, onPickStart }: { message: string; onPickStart: () => void }) {
  return (
    <div className="location-notice panel" role="status">
      <p>{message}</p>
      <button type="button" className="btn small" onClick={onPickStart}>
        Pick a start
      </button>
    </div>
  )
}
