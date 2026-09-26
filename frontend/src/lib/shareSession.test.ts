import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  SHARE_SESSION_KEY,
  clearShareSession,
  loadShareSession,
  refreshShareExpiry,
  sameDestination,
  saveShareSession,
  type StoredShareSession,
} from './shareSession'

const NOW = Date.parse('2026-09-27T02:45:00Z')
const SESSION: StoredShareSession = {
  walk_id: 'AbCdEfGhIjKlMnOpQrStUv',
  owner_token: 'secret-token',
  follow_path: '/follow/AbCdEfGhIjKlMnOpQrStUv',
  expires_at: '2026-09-27T08:44:48Z',
  destination: { label: 'Midtown MARTA', lat: 33.781, lon: -84.3863 },
}

/** A Storage whose every call throws, like Safari private mode or a sandboxed iframe. */
function blockedStorage(): Storage {
  const fail = () => {
    throw new DOMException('blocked', 'SecurityError')
  }
  return { getItem: fail, setItem: fail, removeItem: fail, clear: fail, key: fail, length: 0 }
}

describe('share session storage', () => {
  afterEach(() => {
    window.sessionStorage.clear()
    window.localStorage.clear()
    vi.unstubAllGlobals()
  })

  it('round-trips the active share session through sessionStorage', () => {
    saveShareSession(SESSION)

    expect(loadShareSession(NOW)).toEqual(SESSION)
    expect(window.sessionStorage.getItem(SHARE_SESSION_KEY)).not.toBeNull()
  })

  it('keeps the owner token out of localStorage and the URL', () => {
    saveShareSession(SESSION)

    expect(JSON.stringify({ ...window.localStorage })).not.toContain('secret-token')
    expect(window.location.href).not.toContain('secret-token')
  })

  it('drops and forgets corrupt JSON', () => {
    window.sessionStorage.setItem(SHARE_SESSION_KEY, '{not json')

    expect(loadShareSession(NOW)).toBeNull()
    expect(window.sessionStorage.getItem(SHARE_SESSION_KEY)).toBeNull()
  })

  it.each([
    ['a missing token', { ...SESSION, owner_token: undefined }],
    ['an empty walk id', { ...SESSION, walk_id: '' }],
    ['an unreadable expiry', { ...SESSION, expires_at: 'soon' }],
    ['a destination without coordinates', { ...SESSION, destination: { label: 'x' } }],
  ])('rejects a stored session with %s', (_why, stored) => {
    window.sessionStorage.setItem(SHARE_SESSION_KEY, JSON.stringify(stored))

    expect(loadShareSession(NOW)).toBeNull()
    expect(window.sessionStorage.getItem(SHARE_SESSION_KEY)).toBeNull()
  })

  it('treats an expired session as gone and clears it', () => {
    saveShareSession({ ...SESSION, expires_at: '2026-09-27T02:44:59Z' })

    expect(loadShareSession(NOW)).toBeNull()
    expect(window.sessionStorage.getItem(SHARE_SESSION_KEY)).toBeNull()
  })

  it('survives blocked storage without throwing', () => {
    const storage = blockedStorage()

    expect(() => saveShareSession(SESSION, storage)).not.toThrow()
    expect(loadShareSession(NOW, storage)).toBeNull()
    expect(() => clearShareSession(SESSION.walk_id, storage)).not.toThrow()
    expect(() => refreshShareExpiry(SESSION.walk_id, SESSION.expires_at, storage)).not.toThrow()
  })

  it('survives a sessionStorage accessor that throws', () => {
    const accessor = vi.spyOn(window, 'sessionStorage', 'get').mockImplementation(() => {
      throw new DOMException('blocked', 'SecurityError')
    })
    try {
      expect(() => saveShareSession(SESSION)).not.toThrow()
      expect(loadShareSession(NOW)).toBeNull()
      expect(() => clearShareSession()).not.toThrow()
    } finally {
      accessor.mockRestore()
    }
  })

  it('clears only the named walk', () => {
    saveShareSession(SESSION)

    clearShareSession('another-walk')
    expect(loadShareSession(NOW)).toEqual(SESSION)

    clearShareSession(SESSION.walk_id)
    expect(loadShareSession(NOW)).toBeNull()
  })

  it('clears whatever is stored when no walk is named', () => {
    saveShareSession(SESSION)

    clearShareSession()

    expect(loadShareSession(NOW)).toBeNull()
  })

  it('extends the stored expiry for the same walk only', () => {
    saveShareSession(SESSION)

    refreshShareExpiry('another-walk', '2026-09-28T00:00:00Z')
    expect(loadShareSession(NOW)?.expires_at).toBe(SESSION.expires_at)

    refreshShareExpiry(SESSION.walk_id, '2026-09-27T09:00:00Z')
    expect(loadShareSession(NOW)?.expires_at).toBe('2026-09-27T09:00:00Z')
  })

  it('does not bring back a cleared session when refreshing', () => {
    refreshShareExpiry(SESSION.walk_id, '2026-09-27T09:00:00Z')

    expect(loadShareSession(NOW)).toBeNull()
  })
})

describe('sameDestination', () => {
  const dest = SESSION.destination

  it('matches the same place', () => {
    expect(sameDestination(dest, { ...dest })).toBe(true)
  })

  it('ignores rounding noise from the URL', () => {
    expect(sameDestination(dest, { lat: 33.781004, lon: -84.386296 })).toBe(true)
  })

  it('rejects a different place or no place', () => {
    expect(sameDestination(dest, { lat: 33.79, lon: -84.3863 })).toBe(false)
    expect(sameDestination(dest, null)).toBe(false)
  })
})
