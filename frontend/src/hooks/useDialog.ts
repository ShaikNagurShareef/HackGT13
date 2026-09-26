import { useEffect, useRef } from 'react'

/**
 * Modal sheet behaviour: Escape closes, and focus returns to whatever opened the sheet
 * (WCAG 2.4.3). The latest `onClose` is used without re-binding the listener.
 */
export function useDialog(onClose: () => void): void {
  const closeRef = useRef(onClose)

  useEffect(() => {
    closeRef.current = onClose
  }, [onClose])

  useEffect(() => {
    const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') closeRef.current()
    }
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('keydown', onKey)
      if (opener?.isConnected) opener.focus()
    }
  }, [])
}
