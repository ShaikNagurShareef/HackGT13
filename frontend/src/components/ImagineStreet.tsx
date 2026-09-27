import { useEffect, useId, useRef, useState } from 'react'
import { ApiError, api, apiBase } from '../api/client'
import { isDemoMode } from '../api/demo'
import type { Imagined } from '../api/schemas'

export const IMAGINE_BUTTON = 'Imagine this street redesigned'
export const IMAGINE_LABEL = 'AI illustration of evidence-based street fixes by Grok Imagine — not a real photo'
const BUSY_TEXT = 'Imagining this street…'
const FALLBACK_ERROR = 'Could not draw this street right now. Please try again.'

/** "Grok draws, Gemini checks": how many planned fixes Gemini confirmed in the picture. */
function checkLine(check: NonNullable<Imagined['check']>): string {
  return `Checked by Gemini: shows ${check.fixes_shown.length} of ${check.fixes_total} planned fixes`
}
// Grok Imagine returns 16:9 images; fixed dimensions keep the sheet from jumping when it loads.
const IMAGE_WIDTH = 1024
const IMAGE_HEIGHT = 576

type State = { kind: 'idle' } | { kind: 'busy' } | { kind: 'done'; data: Imagined } | { kind: 'error'; message: string }

type Props = {
  segId: number
  streetName: string
}

/**
 * Grok Imagine: an AI illustration of this street with evidence-based design fixes, for planners.
 * The server writes the prompt from the street's risk factors; the picture never changes a score.
 * Parents key this component by segment, so state starts fresh for each street.
 */
export function ImagineStreet({ segId, streetName }: Props) {
  const [state, setState] = useState<State>({ kind: 'idle' })
  const active = useRef(true)
  const figureRef = useRef<HTMLElement>(null)
  const headingId = useId()

  useEffect(() => {
    active.current = true
    return () => {
      active.current = false
    }
  }, [])

  useEffect(() => {
    // The button is replaced by the picture; move focus so keyboard users land on the result.
    if (state.kind === 'done') figureRef.current?.focus()
  }, [state.kind])

  if (isDemoMode()) return null

  const busy = state.kind === 'busy'
  const imagine = () => {
    if (busy) return
    setState({ kind: 'busy' })
    api
      .imagineSegment(segId)
      .then((data) => active.current && setState({ kind: 'done', data }))
      .catch((e: unknown) => {
        if (!active.current) return
        setState({ kind: 'error', message: e instanceof ApiError ? e.message : FALLBACK_ERROR })
      })
  }

  return (
    <section className="imagine" aria-labelledby={headingId}>
      <h3 id={headingId} className="imagine-title">
        Street redesign ideas
      </h3>
      {state.kind === 'done' ? (
        <figure className="imagine-figure" ref={figureRef} tabIndex={-1}>
          <img
            className="imagine-image"
            src={`${apiBase()}${state.data.image_url}`}
            alt={`AI illustration of ${streetName} redesigned with ${state.data.fixes.join(', ')}`}
            width={IMAGE_WIDTH}
            height={IMAGE_HEIGHT}
          />
          <figcaption className="imagine-caption">
            <strong className="imagine-label">{IMAGINE_LABEL}</strong>
            <span className="faint">{state.data.prompt_summary}</span>
            {state.data.check ? <span className="imagine-check faint">{checkLine(state.data.check)}</span> : null}
          </figcaption>
        </figure>
      ) : (
        <button
          type="button"
          className="btn small imagine-btn"
          onClick={imagine}
          aria-busy={busy || undefined}
          aria-disabled={busy || undefined}
        >
          {busy ? BUSY_TEXT : IMAGINE_BUTTON}
        </button>
      )}
      <p className="imagine-status faint" role="status" aria-live="polite">
        {state.kind === 'error' ? state.message : ''}
      </p>
    </section>
  )
}
