import { describe, expect, it } from 'vitest'
import { WELCOME_KEY, hasSeenWelcome, markWelcomeSeen } from './welcome'

describe('welcome flag', () => {
  it('remembers dismissal', () => {
    localStorage.removeItem(WELCOME_KEY)
    expect(hasSeenWelcome()).toBe(false)
    markWelcomeSeen()
    expect(hasSeenWelcome()).toBe(true)
  })

  it('survives blocked storage', () => {
    const blocked = {
      getItem: () => {
        throw new Error('blocked')
      },
      setItem: () => {
        throw new Error('blocked')
      },
    } as unknown as Storage
    expect(hasSeenWelcome(blocked)).toBe(false)
    expect(() => markWelcomeSeen(blocked)).not.toThrow()
  })
})
