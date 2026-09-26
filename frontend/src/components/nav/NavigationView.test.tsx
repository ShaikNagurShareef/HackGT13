import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { NavigationView, type NavigationViewProps } from './NavigationView'

function setup(over: Partial<NavigationViewProps> = {}) {
  const props: NavigationViewProps = {
    instruction: { tone: 'alert', headline: 'High traffic risk ahead', detail: '10th St NW in 120 m' },
    mode: 'gps',
    remainingS: 720,
    remainingM: 850,
    arrival: '10:54 PM',
    arrived: false,
    destination: 'Midtown MARTA',
    onEnd: vi.fn(),
    onDone: vi.fn(),
    ...over,
  }
  render(<NavigationView {...props} />)
  return props
}

describe('NavigationView', () => {
  it('shows the next thing in a big banner and the trip status with End', async () => {
    const p = setup()

    expect(screen.getByRole('status')).toHaveTextContent('High traffic risk ahead')
    expect(screen.getByRole('status')).toHaveTextContent('10th St NW in 120 m')
    const bar = screen.getByRole('region', { name: 'Trip progress' })
    expect(bar).toHaveTextContent('12 min')
    expect(bar).toHaveTextContent('850 m · arrive 10:54 PM')
    expect(screen.queryByText('Preview walk')).toBeNull()
    await userEvent.click(screen.getByRole('button', { name: 'End' }))
    expect(p.onEnd).toHaveBeenCalled()
  })

  it('renders the share-my-walk slot while navigating and after arrival', () => {
    const { unmount } = render(
      <NavigationView
        instruction={null}
        mode="gps"
        remainingS={600}
        remainingM={700}
        arrival="10:54 PM"
        arrived={false}
        destination="Midtown MARTA"
        onEnd={vi.fn()}
        onDone={vi.fn()}
        share={<button type="button">Share my walk</button>}
      />,
    )
    expect(screen.getByRole('button', { name: 'Share my walk' })).toBeInTheDocument()
    unmount()

    setup({ arrived: true, share: <span>Sharing live</span> })
    expect(screen.getByText('Sharing live')).toBeInTheDocument()
  })

  it('labels a preview walk', () => {
    setup({ mode: 'preview' })
    expect(screen.getByText('Preview walk')).toBeInTheDocument()
  })

  it('celebrates arrival and finishes', async () => {
    const p = setup({ arrived: true })

    const done = screen.getByRole('region', { name: "You've arrived" })
    expect(done).toHaveTextContent('Midtown MARTA')
    await userEvent.click(screen.getByRole('button', { name: 'Done' }))
    expect(p.onDone).toHaveBeenCalled()
  })

  it('waits for a position before showing a banner', () => {
    setup({ instruction: null })
    expect(screen.getByRole('status')).toHaveTextContent('Finding your position on the route…')
  })
})
