/** PathPro mark: a route that bends around a hot spot, ending in a teal waypoint. */
export function LogoMark({ size = 26 }: { size?: number }) {
  return (
    <svg className="logo-mark" width={size} height={size} viewBox="0 0 32 32" aria-hidden="true" focusable="false">
      <circle cx="19" cy="15" r="4.2" fill="var(--hot)" opacity="0.9" />
      <path
        d="M6 26c0-6 3-8.5 7-9.5s4.6-6 2.2-9.3"
        fill="none"
        stroke="var(--teal)"
        strokeWidth="3"
        strokeLinecap="round"
      />
      <circle cx="15" cy="6" r="3.2" fill="var(--bg)" stroke="var(--teal)" strokeWidth="2.4" />
      <circle cx="6" cy="26" r="2.2" fill="var(--teal)" />
    </svg>
  )
}
