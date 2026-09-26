import { useId } from 'react'

type Props = {
  destination: string
  onResume: () => void
  onStop: () => void
}

/** After a reload mid-walk: offer to pick the live link back up, or end it for the friend. */
export function ResumeSharePrompt({ destination, onResume, onStop }: Props) {
  const titleId = useId()
  return (
    <section className="share-resume panel" aria-labelledby={titleId}>
      <p id={titleId} className="share-resume-text">
        You were sharing your walk to {destination}. Resume sharing?
      </p>
      <div className="share-resume-actions">
        <button type="button" className="btn primary" onClick={onResume}>
          Resume
        </button>
        <button type="button" className="btn" onClick={onStop}>
          Stop sharing
        </button>
      </div>
    </section>
  )
}
