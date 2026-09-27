/**
 * Ask PathPro's agent mark: a friendly rounded bot face with a sparkle on its antenna.
 * Original artwork on the 24 px icon grid; draws in currentColor.
 */
export function AgentGlyph({ size = 20 }: { size?: number }) {
  return (
    <svg
      className="agent-glyph"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      <rect x="4" y="8.5" width="16" height="12" rx="5" />
      <path d="M12 8.5V6.2M2.2 13v3.2M21.8 13v3.2M9.6 17.3c1.4.8 3.4.8 4.8 0" />
      <path d="M12 .9c.3 1.5 1 2.2 2.5 2.5-1.5.3-2.2 1-2.5 2.5-.3-1.5-1-2.2-2.5-2.5 1.5-.3 2.2-1 2.5-2.5Z" fill="currentColor" strokeWidth={1} />
      <circle cx="9.3" cy="13.6" r="1.35" fill="currentColor" stroke="none" />
      <circle cx="14.7" cy="13.6" r="1.35" fill="currentColor" stroke="none" />
    </svg>
  )
}
