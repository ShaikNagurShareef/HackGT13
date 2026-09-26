import { H3HexagonLayer } from '@deck.gl/geo-layers'
import type { PickingInfo } from '@deck.gl/core'
import { RAMP } from '../lib/bands'

interface HexDatum {
  i: number
  cell: string
}

export function buildHexLayer(
  cells: ReadonlyArray<string>,
  frame: Uint8Array | null,
  frameKey: string,
  reducedMotion: boolean,
  onPick: (cell: string) => void,
) {
  const data: HexDatum[] = cells.map((cell, i) => ({ i, cell }))
  const score = (i: number) => (frame ? frame[i] : 0)
  return new H3HexagonLayer<HexDatum>({
    id: 'city-pulse',
    data,
    getHexagon: (d) => d.cell,
    getFillColor: (d) => [...RAMP[score(d.i)], 150 + Math.round(score(d.i))] as [number, number, number, number],
    extruded: false,
    stroked: false,
    pickable: true,
    autoHighlight: true,
    highlightColor: [255, 212, 121, 160],
    onClick: (info: PickingInfo<HexDatum>) => {
      if (info.object) onPick(info.object.cell)
    },
    updateTriggers: { getFillColor: frameKey },
    transitions: { getFillColor: reducedMotion ? 0 : 400 },
  })
}
