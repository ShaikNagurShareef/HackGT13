import { Icon } from '../ui/Icon'
import { LogoMark } from '../ui/LogoMark'

/** The one thing on the home screen: a floating "Where to?" pill with the PathPro mark. */
export function SearchPill({ onOpen }: { onOpen: () => void }) {
  return (
    <button type="button" className="search-pill" onClick={onOpen}>
      <LogoMark size={28} />
      <span className="search-pill-text">Where to?</span>
      <span className="search-pill-icon" aria-hidden="true">
        <Icon name="search" />
      </span>
    </button>
  )
}
