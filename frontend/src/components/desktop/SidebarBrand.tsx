import { LogoMark } from '../ui/LogoMark'

/** PathPro wordmark + tagline at the top of the desktop sidebar. */
export function SidebarBrand() {
  return (
    <header className="desk-brand">
      <LogoMark size={36} />
      <div>
        <h1 className="desk-brand-name">PathPro</h1>
        <p className="desk-brand-tagline">See traffic risk before you walk into it.</p>
      </div>
    </header>
  )
}
