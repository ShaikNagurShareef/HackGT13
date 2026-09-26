import { useEffect, useRef } from 'react'

/** A ref that always holds the latest value, so effects can call fresh callbacks without re-running. */
export function useLatest<T>(value: T): { readonly current: T } {
  const ref = useRef(value)
  useEffect(() => {
    ref.current = value
  }, [value])
  return ref
}
