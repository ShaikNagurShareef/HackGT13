import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactElement } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { DEFAULT_SAFETY_LAYERS } from '../../lib/safety'
import { helpPoint, meta, route, routes, safetyHex, safetyMeta } from '../../test/fixtures'
import { About } from '../About'
import { WelcomeToast } from '../home/WelcomeToast'
import { OptionsContent } from '../options/OptionsContent'
import { RouteSheet } from '../route/RouteSheet'
import { AboutSafety } from './AboutSafety'
import { RoutePreferencePicker } from './RoutePreferencePicker'
import { SafetyLayerToggles } from './SafetyLayerToggles'
import { SafetyLegend } from './SafetyLegend'
import { SafetyPickCard } from './SafetyPickCard'
import { SafetyRouteNote } from './SafetyRouteNote'

/** Words PathPro never uses about places or routes (product copy rules). */
const BANNED = /\b(safe|safest|unsafe|dangerous|bad area|sketchy|guaranteed)\b/i

const ALL_ON = { crimes: true, lit: true, busy: true, help: true }
const SAFETY = { lit_share: 0.82, busy_share: 0.6, help_points_within_100m: 3, crimes_persons_nearby: 4, day_part: 'evening' }

function textOf(ui: ReactElement): string {
  const { container, unmount } = render(ui)
  const text = container.textContent ?? ''
  unmount()
  return text
}

describe('personal-safety copy', () => {
  const cases: Array<[string, () => ReactElement]> = [
    ['legend', () => <SafetyLegend meta={safetyMeta()} hour={21} layers={ALL_ON} tooWide={false} />],
    ['legend (zoomed out)', () => <SafetyLegend meta={null} hour={3} layers={ALL_ON} tooWide />],
    ['toggles', () => <SafetyLayerToggles layers={ALL_ON} onChange={vi.fn()} hasLit hasBusy />],
    ['preference', () => <RoutePreferencePicker value="lit_and_busy" onChange={vi.fn()} />],
    ['hex card', () => <SafetyPickCard pick={{ kind: 'hex', hex: safetyHex({ crime_band: 'higher', activity_band: 'quiet' }) }} dayLabel="Late night" onClose={vi.fn()} />],
    ['help card', () => <SafetyPickCard pick={{ kind: 'help', point: helpPoint({ kind: 'police', name: 'Zone 5' }) }} dayLabel={null} onClose={vi.fn()} />],
    ['route note', () => <SafetyRouteNote onOpenLegend={vi.fn()} />],
    ['about section', () => <AboutSafety meta={safetyMeta()} />],
    ['about (whole)', () => <About meta={meta()} safetyMeta={safetyMeta()} onClose={vi.fn()} />],
    ['welcome (with safety)', () => <WelcomeToast dataThrough="2026-09-19" safetyAvailable onDismiss={vi.fn()} />],
    ['welcome (without)', () => <WelcomeToast dataThrough="2026-09-19" safetyAvailable={false} onDismiss={vi.fn()} />],
  ]

  it.each(cases)('%s avoids banned words', (_name, ui) => {
    const text = textOf(ui())
    expect(text.length).toBeGreaterThan(0)
    expect(text).not.toMatch(BANNED)
  })

  it('options in safety mode avoid banned words', () => {
    const text = textOf(
      <OptionsContent
        cond="live"
        condLabel="Live · dry"
        onCond={vi.fn()}
        depart="now"
        onDepart={vi.fn()}
        cityAvailable
        mapMode="safety"
        onMapMode={vi.fn()}
        safety={{
          legend: { meta: safetyMeta(), hour: 21, layers: ALL_ON, tooWide: false },
          onLayers: vi.fn(),
          hasLit: true,
          hasBusy: true,
          prefer: 'lower_traffic_risk',
          onPrefer: vi.fn(),
        }}
        showReportsLegend={false}
        onClearHistory={vi.fn()}
      />,
    )
    expect(text).toContain('Personal safety')
    expect(text).not.toMatch(BANNED)
  })

  it('the expanded route sheet with safety avoids banned words', async () => {
    const withSafety = routes({ fastest: route({ safety: SAFETY }), pathpro: route({ safety: { ...SAFETY, crimes_persons_nearby: 0 } }) })
    const { container } = render(
      <RouteSheet
        routes={withSafety}
        selected="pp"
        onSelect={vi.fn()}
        explanation={null}
        onStart={vi.fn()}
        onPreview={vi.fn()}
        startNote={null}
        onListen={vi.fn()}
        onShare={vi.fn()}
        shareStatus={null}
        onFocusSegment={vi.fn()}
        onSelectSegment={vi.fn()}
        dayParts={safetyMeta().day_parts}
      />,
    )
    await userEvent.click(screen.getByRole('button', { name: 'Why?' }))
    expect(container.textContent).toContain('reported crimes against persons')
    expect(container.textContent).not.toMatch(BANNED)
  })

  it('default layers start with the crime layer and help points on', () => {
    expect(DEFAULT_SAFETY_LAYERS).toEqual({ crimes: true, lit: false, busy: false, help: true })
  })
})
