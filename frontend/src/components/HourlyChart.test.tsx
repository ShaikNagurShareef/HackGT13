import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { HourlyChart } from './HourlyChart'

const hourly = (crashes: number[]) => ({
  success: true,
  data: { seg_id: 3, crashes, ped_crashes: crashes.map(() => 0), source: 'tiger_data' },
})

describe('HourlyChart', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('renders 24 bars from Tiger Data and names the peak hour', async () => {
    const crashes = Array.from({ length: 24 }, (_, h) => (h === 17 ? 10 : 1))
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify(hourly(crashes)))))

    render(<HourlyChart segId={3} highlightHour={22} />)

    const fig = await screen.findByRole('figure')
    expect(fig).toHaveAccessibleName(/peak at 5 PM/)
    expect(fig.querySelectorAll('.hourly-bar')).toHaveLength(24)
    expect(fig.querySelector('.hourly-bar.now')).not.toBeNull()
  })

  it('hides when the database is unavailable', async () => {
    const body = { success: false, error: { code: 'HISTORY_UNAVAILABLE', message: 'x' } }
    const fetcher = vi.fn(async () => new Response(JSON.stringify(body)))
    vi.stubGlobal('fetch', fetcher)

    const { container } = render(<HourlyChart segId={3} highlightHour={1} />)

    await vi.waitFor(() => expect(fetcher).toHaveBeenCalled())
    expect(container).toBeEmptyDOMElement()
  })
})
