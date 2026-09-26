import type { SafetyMeta } from '../../api/safetySchemas'
import { FairnessNote } from './FairnessNote'
import { SafetySources } from './SafetySources'

/** About section: how the personal-safety layer works and where it stops. */
export function AboutSafety({ meta }: { meta: SafetyMeta }) {
  const categories = meta.crime_categories.join(', ')
  const dayParts = meta.day_parts.map((p) => p.label.toLowerCase()).join(', ')
  return (
    <>
      <h2>Personal safety layer — how it works and its limits</h2>
      <p>
        The Personal safety map adds signals people weigh when walking, especially after dark: street lighting
        (well-lit streets), foot traffic (busier streets), and help points — Georgia Tech blue-light emergency phones,
        police and fire stations, hospitals, and MARTA stations.
      </p>
      <p>
        It can also show reported crimes against persons from Atlanta Police open data ({categories}), counted over
        the last 12 months, grouped into map hexagons and by time of day ({dayParts}). Shading compares each area with
        the city: fewer reports, typical, or more reports.
      </p>
      <FairnessNote />
      <ul>
        <li>Reported crimes are informational only: they are never used to choose or rank routes.</li>
        <li>
          The optional “Well-lit &amp; busier” route preference uses street lighting and foot traffic only.
        </li>
        <li>
          Police reports are incomplete and their locations are approximate; they show where incidents were recorded.
        </li>
        <li>Lighting and foot-traffic data can lag behind changes on the street.</li>
      </ul>
      <SafetySources meta={meta} />
    </>
  )
}
