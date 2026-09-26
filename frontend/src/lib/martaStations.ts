/**
 * All 38 MARTA heavy-rail stations (same list as backend/app/domain/marta_stations.json), bundled
 * for the offline demo (`?demo=1`) when no recorded `/transit/stations` fixture exists.
 */

import type { TransitStation } from '../api/schemas'

export const MARTA_STATIONS: ReadonlyArray<TransitStation> = [
  { name: 'Airport', lat: 33.640733, lon: -84.446213, lines: ['Red', 'Gold'] },
  { name: 'College Park', lat: 33.651142, lon: -84.448742, lines: ['Red', 'Gold'] },
  { name: 'East Point', lat: 33.677211, lon: -84.440554, lines: ['Red', 'Gold'] },
  { name: 'Lakewood/Fort McPherson', lat: 33.700136, lon: -84.428896, lines: ['Red', 'Gold'] },
  { name: 'Oakland City', lat: 33.716799, lon: -84.425187, lines: ['Red', 'Gold'] },
  { name: 'West End', lat: 33.736054, lon: -84.413664, lines: ['Red', 'Gold'] },
  { name: 'Garnett', lat: 33.748163, lon: -84.396165, lines: ['Red', 'Gold'] },
  { name: 'Five Points', lat: 33.753887, lon: -84.391596, lines: ['Red', 'Gold', 'Blue', 'Green'] },
  { name: 'Peachtree Center', lat: 33.758146, lon: -84.387613, lines: ['Red', 'Gold'] },
  { name: 'Civic Center', lat: 33.766509, lon: -84.387542, lines: ['Red', 'Gold'] },
  { name: 'North Avenue', lat: 33.771605, lon: -84.386769, lines: ['Red', 'Gold'] },
  { name: 'Midtown', lat: 33.781116, lon: -84.386432, lines: ['Red', 'Gold'] },
  { name: 'Arts Center', lat: 33.789121, lon: -84.387325, lines: ['Red', 'Gold'] },
  { name: 'Lindbergh Center', lat: 33.822754, lon: -84.369549, lines: ['Red', 'Gold'] },
  { name: 'Buckhead', lat: 33.848963, lon: -84.368402, lines: ['Red'] },
  { name: 'Medical Center', lat: 33.910757, lon: -84.351819, lines: ['Red'] },
  { name: 'Dunwoody', lat: 33.92113, lon: -84.344268, lines: ['Red'] },
  { name: 'Sandy Springs', lat: 33.932155, lon: -84.351496, lines: ['Red'] },
  { name: 'North Springs', lat: 33.945143, lon: -84.357296, lines: ['Red'] },
  { name: 'Lenox', lat: 33.845587, lon: -84.357748, lines: ['Gold'] },
  { name: 'Brookhaven/Oglethorpe', lat: 33.860329, lon: -84.339245, lines: ['Gold'] },
  { name: 'Chamblee', lat: 33.887607, lon: -84.305556, lines: ['Gold'] },
  { name: 'Doraville', lat: 33.902787, lon: -84.280497, lines: ['Gold'] },
  { name: 'Hamilton E. Holmes', lat: 33.754513, lon: -84.469948, lines: ['Blue'] },
  { name: 'West Lake', lat: 33.753321, lon: -84.445301, lines: ['Blue'] },
  { name: 'Bankhead', lat: 33.772257, lon: -84.428941, lines: ['Green'] },
  { name: 'Ashby', lat: 33.75648, lon: -84.417347, lines: ['Blue', 'Green'] },
  { name: 'Vine City', lat: 33.756564, lon: -84.404012, lines: ['Blue', 'Green'] },
  { name: 'SEC District', lat: 33.75619, lon: -84.397596, lines: ['Blue', 'Green'] },
  { name: 'Georgia State', lat: 33.750165, lon: -84.385957, lines: ['Blue', 'Green'] },
  { name: 'King Memorial', lat: 33.750008, lon: -84.375451, lines: ['Blue', 'Green'] },
  { name: 'Inman Park/Reynoldstown', lat: 33.757822, lon: -84.35236, lines: ['Blue', 'Green'] },
  { name: 'Edgewood/Candler Park', lat: 33.761905, lon: -84.339866, lines: ['Blue', 'Green'] },
  { name: 'East Lake', lat: 33.765194, lon: -84.312881, lines: ['Blue'] },
  { name: 'Decatur', lat: 33.774697, lon: -84.295806, lines: ['Blue'] },
  { name: 'Avondale', lat: 33.775178, lon: -84.282188, lines: ['Blue'] },
  { name: 'Kensington', lat: 33.772601, lon: -84.251896, lines: ['Blue'] },
  { name: 'Indian Creek', lat: 33.769915, lon: -84.229427, lines: ['Blue'] },
]
