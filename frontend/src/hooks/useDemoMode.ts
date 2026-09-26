import { useEffect } from 'react'
import { DEMO_DEPART, DEMO_ROUTE, loadFixtures } from '../api/demo'
import type { ViewState } from '../state/urlState'
import { useLatest } from './useLatest'

const DEMO_HOUR = 22

/** Demo mode (DEMO-01/02): preload fixtures, open the scripted route, and enable T / R / D shortcuts. */
export function useDemoMode(
  demo: boolean,
  view: ViewState,
  update: (patch: Partial<ViewState>) => void,
  onError: (message: string) => void,
): void {
  const latest = useLatest({ view, update, onError })

  useEffect(() => {
    if (!demo) return
    const { view: first, update: set } = latest.current
    void loadFixtures().catch(() => latest.current.onError('Demo data is missing. Run the demo recorder.'))
    if (!first.from && !first.to) set({ ...DEMO_ROUTE, depart: DEMO_DEPART, cond: 'wet' })
    const onKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.metaKey || e.ctrlKey) return
      const { view: now, update: apply } = latest.current
      const k = e.key.toLowerCase()
      if (k === 't') apply({ hour: DEMO_HOUR })
      if (k === 'r') apply({ cond: now.cond === 'wet' ? 'dry' : 'wet' })
      if (k === 'd') apply({ ...DEMO_ROUTE, depart: DEMO_DEPART, cond: 'wet', seg: null })
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [demo, latest])
}
