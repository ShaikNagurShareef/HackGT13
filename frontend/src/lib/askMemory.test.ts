import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  ASK_MEMORY_KEY,
  ASK_THREAD_KEY,
  clearAskMemory,
  forgetAskMemory,
  readAskMemory,
  readAskThread,
  useAskMemory,
  writeAskMemory,
  writeAskThread,
} from './askMemory'

const TOKEN = '33333333-3333-4333-8333-333333333333.bWVtb3J5LXRva2VuLXNpZ25hdHVyZQ'
const THREAD = '22222222-2222-4222-8222-222222222222.Zm9vYmFyYmF6cXV4MTIzNDU2Nzg5MGFi'
const JSON_HEADERS = { headers: { 'content-type': 'application/json' } }

function blockedStorage(): Storage {
  const fail = () => {
    throw new Error('blocked')
  }
  return { getItem: fail, setItem: fail, removeItem: fail, clear: fail, key: fail, length: 0 } as unknown as Storage
}

describe('Ask PathPro memory token storage', () => {
  beforeEach(() => {
    window.localStorage.clear()
    window.sessionStorage.clear()
  })
  afterEach(() => {
    vi.unstubAllGlobals()
    window.localStorage.clear()
    window.sessionStorage.clear()
  })

  it('has no memory by default', () => {
    expect(readAskMemory()).toBeNull()
  })

  it('round-trips the token and on/off state in localStorage under a versioned key', () => {
    writeAskMemory({ token: TOKEN, on: true })

    expect(ASK_MEMORY_KEY).toBe('pathpro:ask-memory:v1')
    expect(readAskMemory()).toEqual({ token: TOKEN, on: true })
    expect(JSON.parse(window.localStorage.getItem(ASK_MEMORY_KEY) ?? 'null')).toEqual({ token: TOKEN, on: true })

    writeAskMemory({ token: TOKEN, on: false })
    expect(readAskMemory()).toEqual({ token: TOKEN, on: false })
  })

  it('treats corrupt JSON, a wrong shape, or an unsigned token as no memory', () => {
    window.localStorage.setItem(ASK_MEMORY_KEY, '{not json')
    expect(readAskMemory()).toBeNull()

    window.localStorage.setItem(ASK_MEMORY_KEY, JSON.stringify({ token: 42, on: true }))
    expect(readAskMemory()).toBeNull()

    window.localStorage.setItem(ASK_MEMORY_KEY, JSON.stringify({ token: '33333333-3333-4333-8333-333333333333', on: true }))
    expect(readAskMemory()).toBeNull()
  })

  it('refuses to store an invalid token', () => {
    writeAskMemory({ token: '../nope', on: true })
    expect(window.localStorage.getItem(ASK_MEMORY_KEY)).toBeNull()
  })

  it('clears the stored token', () => {
    writeAskMemory({ token: TOKEN, on: true })
    clearAskMemory()
    expect(readAskMemory()).toBeNull()
  })

  it('never throws when storage is blocked', () => {
    const storage = blockedStorage()
    expect(readAskMemory(storage)).toBeNull()
    expect(() => writeAskMemory({ token: TOKEN, on: true }, storage)).not.toThrow()
    expect(() => clearAskMemory(storage)).not.toThrow()
  })

  it('keeps the thread token in sessionStorage only and rejects unsigned ids', () => {
    writeAskThread(THREAD)
    expect(readAskThread()).toBe(THREAD)
    expect(window.sessionStorage.getItem(ASK_THREAD_KEY)).toBe(THREAD)
    expect(window.localStorage.getItem(ASK_THREAD_KEY)).toBeNull()

    window.sessionStorage.setItem(ASK_THREAD_KEY, '22222222-2222-4222-8222-222222222222')
    expect(readAskThread()).toBeNull()

    writeAskThread(null)
    expect(window.sessionStorage.getItem(ASK_THREAD_KEY)).toBeNull()
  })

  it('forgets: deletes the memory on the server, then the token and the thread here', async () => {
    writeAskMemory({ token: TOKEN, on: true })
    writeAskThread(THREAD)
    const fetcher = vi.fn(async () => new Response(JSON.stringify({ success: true, data: { forgotten: true } }), JSON_HEADERS))
    vi.stubGlobal('fetch', fetcher)

    expect(await forgetAskMemory()).toBe('deleted')

    const [url, init] = fetcher.mock.calls[0] as unknown as [string, RequestInit]
    expect(url).toBe('/api/ask/memory/forget')
    expect(JSON.parse(String(init.body))).toEqual({ memory_token: TOKEN })
    expect(readAskMemory()).toBeNull()
    expect(readAskThread()).toBeNull()
  })

  it('keeps the token to retry when the server cannot be reached', async () => {
    writeAskMemory({ token: TOKEN, on: true })
    vi.stubGlobal('fetch', vi.fn(async () => Promise.reject(new TypeError('offline'))))

    expect(await forgetAskMemory()).toBe('failed')
    expect(readAskMemory()).toEqual({ token: TOKEN, on: true })
  })

  it('clears a token the server no longer recognises', async () => {
    writeAskMemory({ token: TOKEN, on: true })
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response(JSON.stringify({ success: false, data: null, error: { code: 'BAD_REQUEST', message: 'x' } }), JSON_HEADERS)),
    )

    expect(await forgetAskMemory()).toBe('deleted')
    expect(readAskMemory()).toBeNull()
  })

  it('has nothing to forget without a token', async () => {
    const fetcher = vi.fn()
    vi.stubGlobal('fetch', fetcher)

    expect(await forgetAskMemory()).toBe('deleted')
    expect(fetcher).not.toHaveBeenCalled()
  })

  it('useAskMemory follows writes and clears made anywhere in this tab', () => {
    const { result } = renderHook(() => useAskMemory())
    expect(result.current).toBeNull()

    act(() => writeAskMemory({ token: TOKEN, on: true }))
    expect(result.current).toEqual({ token: TOKEN, on: true })

    act(() => clearAskMemory())
    expect(result.current).toBeNull()
  })
})
