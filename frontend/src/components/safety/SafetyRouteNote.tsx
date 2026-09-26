/** Phone route screen in personal safety mode: the map shading is informational only. */
export function SafetyRouteNote({ onOpenLegend }: { onOpenLegend: () => void }) {
  return (
    <p className="safety-route-note panel">
      <span>Shaded areas show reported crimes against persons, never used to choose routes.</span>
      <button type="button" className="link-btn" onClick={onOpenLegend}>
        Legend
      </button>
    </p>
  )
}
