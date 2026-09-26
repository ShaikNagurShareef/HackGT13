/** First-run welcome flag (per device). Storage can be blocked: then the welcome simply shows again. */

export const WELCOME_KEY = 'pathpro:first-run-seen'

export function hasSeenWelcome(storage: Storage | undefined = globalThis.localStorage): boolean {
  try {
    return storage?.getItem(WELCOME_KEY) === '1'
  } catch {
    return false
  }
}

export function markWelcomeSeen(storage: Storage | undefined = globalThis.localStorage): void {
  try {
    storage?.setItem(WELCOME_KEY, '1')
  } catch {
    // Private mode or blocked storage: nothing to persist.
  }
}
