import { LogoMark } from '../ui/LogoMark'

/** PathPro wordmark + tagline at the top of the desktop sidebar. */
export function SidebarBrand() {
  return (
    <header className="desk-brand">
      <LogoMark size={36} />
      <div>
        <h1 className="desk-brand-name">PathPro</h1>
        <p className="desk-brand-tagline">See the risks on your way, before you go.</p>
      </div>
    </header>
  )
}
