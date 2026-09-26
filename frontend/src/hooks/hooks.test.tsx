import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { useExplanation } from './useExplanation'
import { useTypewriter } from './useTypewriter'
import { useViewState } from './useViewState'

describe('useTypewriter (GEN-05)', () => {
  afterEach(() => vi.useRealTimers())

  it('reveals text progressively and completes', () => {
    vi.useFakeTimers()
    const { result } = renderHook(({ text }) => useTypewriter(text), { initialProps: { text: 'abcdefghij' } })

    act(() => void vi.advanceTimersByTime(16))
    expect(result.current).toBe('abc')
    act(() => void vi.advanceTimersByTime(200))
    expect(result.current).toBe('abcdefghij')
  })

  it('is instant under reduced motion and null for null', () => {
    vi.stubGlobal('matchMedia', () => ({ matches: true }))
    const { result, rerender } = renderHook(({ text }) => useTypewriter(text), {
      initialProps: { text: 'hello' as string | null },
    })
    expect(result.current).toBe('hello')
    rerender({ text: null })
    expect(result.current).toBeNull()
    vi.unstubAllGlobals()
  })
})

describe('useExplanation', () => {
  it('loads per key and ignores failures', async () => {
    const load = vi.fn().mockResolvedValue({ text: 'why', source: 'groq' })
    const { result, rerender } = renderHook(({ k }) => useExplanation(k, load), { initialProps: { k: 'a' as string | null } })

    await waitFor(() => expect(result.current?.text).toBe('why'))
    rerender({ k: null })
    expect(result.current).toBeNull()

    const failing = vi.fn().mockRejectedValue(new Error('down'))
    const second = renderHook(() => useExplanation('b', failing))
    await waitFor(() => expect(failing).toHaveBeenCalled())
    expect(second.result.current).toBeNull()
  })
})

describe('useViewState', () => {
  it('reads the URL and writes updates back', () => {
    window.history.replaceState(null, '', '/?cond=wet&h=22')
    const { result } = renderHook(() => useViewState())

    expect(result.current[0].cond).toBe('wet')
    act(() => result.current[1]({ hour: 5, seg: 9 }))

    expect(window.location.search).toBe('?cond=wet&h=5&seg=9')
  })
})
