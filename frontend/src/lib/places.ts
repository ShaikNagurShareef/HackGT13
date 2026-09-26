/** Curated gazetteer: quick picks (SRCH-02) and MARTA stations searched first (SRCH-01). */

import type { Place } from '../state/urlState'

export interface NamedPlace extends Place {
  keywords: string
  quick: boolean
}

export const PLACES: ReadonlyArray<NamedPlace> = [
  { label: 'Klaus Building', lat: 33.7771, lon: -84.3962, quick: true, keywords: 'klaus gt georgia tech computing' },
  { label: 'Tech Square', lat: 33.7765, lon: -84.3893, quick: true, keywords: 'tech square technology sq spring' },
  { label: 'Midtown MARTA', lat: 33.781, lon: -84.3863, quick: true, keywords: 'midtown marta station train' },
  { label: 'North Ave MARTA', lat: 33.7716, lon: -84.3872, quick: true, keywords: 'north avenue marta station train' },
  { label: 'Home Park', lat: 33.785, lon: -84.402, quick: true, keywords: 'home park neighborhood' },
  { label: 'Georgia Tech Hotel', lat: 33.7757, lon: -84.3889, quick: true, keywords: 'georgia tech hotel conference' },
  { label: 'Arts Center MARTA', lat: 33.7893, lon: -84.3876, quick: false, keywords: 'arts center marta station train' },
  { label: 'Civic Center MARTA', lat: 33.7665, lon: -84.3873, quick: false, keywords: 'civic center marta station train' },
  { label: 'Peachtree Center MARTA', lat: 33.759, lon: -84.3876, quick: false, keywords: 'peachtree center marta station train' },
  { label: 'Student Center (CULC)', lat: 33.7747, lon: -84.3983, quick: false, keywords: 'culc clough student center library' },
  { label: 'Bobby Dodd Stadium', lat: 33.7724, lon: -84.3928, quick: false, keywords: 'bobby dodd stadium football' },
  { label: 'Piedmont Park', lat: 33.7851, lon: -84.3738, quick: false, keywords: 'piedmont park' },
  { label: 'Fox Theatre', lat: 33.7725, lon: -84.3858, quick: false, keywords: 'fox theatre theater' },
  { label: 'Centennial Olympic Park', lat: 33.7603, lon: -84.3933, quick: false, keywords: 'centennial olympic park downtown' },
  { label: 'Five Points MARTA', lat: 33.7539, lon: -84.3916, quick: false, keywords: 'five points marta station train downtown' },
  { label: 'West End MARTA', lat: 33.7359, lon: -84.4132, quick: false, keywords: 'west end marta station train' },
  { label: 'Atlanta University Center', lat: 33.7496, lon: -84.4136, quick: false, keywords: 'auc atlanta university center spelman morehouse clark' },
  { label: 'Mercedes-Benz Stadium', lat: 33.7554, lon: -84.4008, quick: false, keywords: 'mercedes benz stadium falcons' },
  { label: 'State Farm Arena', lat: 33.7573, lon: -84.3963, quick: false, keywords: 'state farm arena hawks' },
  { label: 'Ponce City Market', lat: 33.7726, lon: -84.3655, quick: false, keywords: 'ponce city market beltline' },
  { label: 'Little Five Points', lat: 33.7645, lon: -84.3495, quick: false, keywords: 'little five points l5p' },
  { label: 'Grant Park', lat: 33.7373, lon: -84.3706, quick: false, keywords: 'grant park zoo' },
  { label: 'Inman Park MARTA', lat: 33.7575, lon: -84.3526, quick: false, keywords: 'inman park reynoldstown marta station train' },
  { label: 'Buckhead MARTA', lat: 33.8479, lon: -84.3673, quick: false, keywords: 'buckhead marta station train' },
  { label: 'Lindbergh Center MARTA', lat: 33.8231, lon: -84.3695, quick: false, keywords: 'lindbergh center marta station train' },
  { label: 'Atlantic Station', lat: 33.7918, lon: -84.3969, quick: false, keywords: 'atlantic station' },
]

export const QUICK_PICKS = PLACES.filter((p) => p.quick)

export function searchPlaces(query: string, limit = 5): NamedPlace[] {
  const q = query.trim().toLowerCase()
  if (q.length < 2) return []
  const terms = q.split(/\s+/)
  return PLACES.map((p) => {
    const hay = `${p.label.toLowerCase()} ${p.keywords}`
    const hits = terms.filter((t) => hay.includes(t)).length
    const prefix = p.label.toLowerCase().startsWith(q) ? 2 : 0
    return { p, rank: hits * 2 + prefix }
  })
    .filter((r) => r.rank >= terms.length * 2)
    .sort((a, b) => b.rank - a.rank)
    .slice(0, limit)
    .map((r) => r.p)
}

export function inBbox(bbox: ReadonlyArray<number>, p: { lat: number; lon: number }): boolean {
  const [west, south, east, north] = bbox
  return p.lon >= west && p.lon <= east && p.lat >= south && p.lat <= north
}
