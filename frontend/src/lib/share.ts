/** Share a trip: the Web Share sheet on phones, a copied link elsewhere. */

import { serializeState, type ViewState } from '../state/urlState'
import { YOUR_LOCATION } from './origin'

export type ShareOutcome = 'shared' | 'copied' | 'cancelled' | 'failed'

const SHARED_START = 'Start point'

/** Trip link without transient view state; a GPS start is never shared as "Your location". */
export function shareableUrl(view: ViewState, origin: string, pathname: string): string {
  const from = view.from?.label === YOUR_LOCATION ? { ...view.from, label: SHARED_START } : view.from
  return `${origin}${pathname}${serializeState({ ...view, from, seg: null, hour: null, day: null })}`
}

export async function shareLink(url: string, title: string, text: string): Promise<ShareOutcome> {
  if (typeof navigator.share === 'function') {
    try {
      await navigator.share({ title, text, url })
      return 'shared'
    } catch (err) {
      if (err instanceof Error && err.name === 'AbortError') return 'cancelled'
    }
  }
  try {
    if (!navigator.clipboard) return 'failed'
    await navigator.clipboard.writeText(url)
    return 'copied'
  } catch {
    return 'failed'
  }
}
