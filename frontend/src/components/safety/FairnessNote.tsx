import { FAIRNESS_NOTE } from '../../lib/safety'

/** Shown wherever reported crimes appear: how to read them, and that routing never uses them. */
export function FairnessNote() {
  return <p className="fairness-note">{FAIRNESS_NOTE}</p>
}
