/** Wording and strength of learned-routine suggestions for the home card. */

import type { RoutineSuggestion } from './routines'

/** A routine needs this score (≈ a regular trip from where you stand) to earn the home card. */
export const STRONG_ROUTINE_SCORE = 1

export function isStrongSuggestion(s: RoutineSuggestion | undefined): s is RoutineSuggestion {
  if (!s) return false
  return s.kind === 'return' || (s.kind === 'routine' && s.score >= STRONG_ROUTINE_SCORE)
}

export function suggestionHeadline(s: RoutineSuggestion): string {
  if (s.kind === 'return') return `Heading back to ${s.to.label}?`
  if (s.kind === 'routine') return `Heading to ${s.to.label}?`
  return `Go to ${s.to.label}?`
}
