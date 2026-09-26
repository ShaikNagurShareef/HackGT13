/** Shown only when map options differ from the defaults, e.g. "☂ Wet · 10 PM". Tap to change. */
export function StatusChip({ label, onClick }: { label: string | null; onClick: () => void }) {
  if (!label) return null
  return (
    <button type="button" className="status-chip" onClick={onClick}>
      <span className="sr-only">Changed options: </span>
      {label}
    </button>
  )
}
