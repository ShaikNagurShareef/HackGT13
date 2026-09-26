import type { SafetyMeta } from '../../api/safetySchemas'
import { safeHref } from '../../lib/safety'

/** "Sources: Atlanta Police Department Open Data (Public records) · … · data through 2026-09-19". */
export function SafetySources({ meta }: { meta: SafetyMeta }) {
  return (
    <p className="faint safety-sources">
      Sources:{' '}
      {meta.sources.map((source, i) => {
        const href = safeHref(source.url)
        return (
          <span key={source.name}>
            {i > 0 && ' · '}
            {href ? (
              <a href={href} target="_blank" rel="noopener noreferrer">
                {source.name}
              </a>
            ) : (
              source.name
            )}
            {source.license && ` (${source.license})`}
          </span>
        )
      })}{' '}
      · data through {meta.data_through}
    </p>
  )
}
