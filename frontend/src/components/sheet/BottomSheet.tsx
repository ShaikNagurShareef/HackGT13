import { useRef, type KeyboardEvent, type PointerEvent, type ReactNode } from 'react'

const DRAG_THRESHOLD_PX = 24

export interface BottomSheetProps {
  label: string
  expanded: boolean
  onExpandedChange: (expanded: boolean) => void
  /** Always visible (the peek state). */
  peek: ReactNode
  /** Revealed when expanded on phones; always shown in the desktop side panel. */
  children?: ReactNode
  className?: string
}

/**
 * Phone bottom sheet with peek + expanded states. The drag handle is a real button: tap or
 * Enter/Space toggles, ArrowUp/ArrowDown/Escape set the state, and a vertical drag follows
 * the finger. On wide screens CSS turns it into a left side panel.
 */
export function BottomSheet({ label, expanded, onExpandedChange, peek, children, className = '' }: BottomSheetProps) {
  const dragStart = useRef<number | null>(null)
  const justDragged = useRef(false)

  const handlePointerDown = (e: PointerEvent<HTMLButtonElement>) => {
    dragStart.current = e.clientY
    justDragged.current = false
  }
  const handlePointerUp = (e: PointerEvent<HTMLButtonElement>) => {
    if (dragStart.current == null) return
    const dy = e.clientY - dragStart.current
    dragStart.current = null
    if (Math.abs(dy) < DRAG_THRESHOLD_PX) return
    justDragged.current = true
    onExpandedChange(dy < 0)
  }
  const handleClick = () => {
    if (justDragged.current) {
      justDragged.current = false
      return
    }
    onExpandedChange(!expanded)
  }
  const handleKeyDown = (e: KeyboardEvent<HTMLButtonElement>) => {
    if (e.key === 'ArrowUp') onExpandedChange(true)
    else if (e.key === 'ArrowDown' || e.key === 'Escape') onExpandedChange(false)
    else return
    e.preventDefault()
    e.stopPropagation()
  }

  return (
    <section
      className={`bsheet panel ${className}`.trim()}
      aria-label={label}
      data-state={expanded ? 'expanded' : 'peek'}
    >
      <button
        type="button"
        className="bsheet-handle"
        aria-expanded={expanded}
        aria-label={`${expanded ? 'Collapse' : 'Expand'} ${label}`}
        onPointerDown={handlePointerDown}
        onPointerUp={handlePointerUp}
        onClick={handleClick}
        onKeyDown={handleKeyDown}
      >
        <span className="bsheet-grip" aria-hidden="true" />
      </button>
      <div className="bsheet-body">
        <div className="bsheet-peek">{peek}</div>
        {children && <div className="bsheet-more">{children}</div>}
      </div>
    </section>
  )
}
