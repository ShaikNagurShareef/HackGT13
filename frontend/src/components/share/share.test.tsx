import { act, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { axe } from 'vitest-axe'
import { FOLLOW_NOW, sharedWalk } from '../../test/walkFixtures'
import { CheckInDialog } from './CheckInDialog'
import { FollowCard } from './FollowCard'
import { ShareWalkControl } from './ShareWalkControl'
import { ShareWalkPanel, type ShareWalkPanelProps } from './ShareWalkPanel'

describe('ShareWalkControl', () => {
  it('offers "Share my walk" when idle', async () => {
    const onStart = vi.fn()
    render(<ShareWalkControl phase="idle" notice={null} onStart={onStart} onResend={vi.fn()} onStop={vi.fn()} onDismissNotice={vi.fn()} />)

    await userEvent.click(screen.getByRole('button', { name: 'Share my walk' }))

    expect(onStart).toHaveBeenCalled()
  })

  it('shows progress while the link is being made', () => {
    render(<ShareWalkControl phase="starting" notice={null} onStart={vi.fn()} onResend={vi.fn()} onStop={vi.fn()} onDismissNotice={vi.fn()} />)

    expect(screen.getByRole('button', { name: 'Starting…' })).toBeDisabled()
  })

  it('shows "Sharing live · Stop" with a way to send the link again', async () => {
    const onStop = vi.fn()
    const onResend = vi.fn()
    render(<ShareWalkControl phase="live" notice={null} onStart={vi.fn()} onResend={onResend} onStop={onStop} onDismissNotice={vi.fn()} />)

    expect(screen.getByText('Sharing live')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Send link' }))
    await userEvent.click(screen.getByRole('button', { name: 'Stop' }))

    expect(onResend).toHaveBeenCalled()
    expect(onStop).toHaveBeenCalled()
  })

  it('announces notices politely and lets them be dismissed', async () => {
    const onDismiss = vi.fn()
    render(
      <ShareWalkControl phase="live" notice="Link copied. Paste it to a friend." onStart={vi.fn()} onResend={vi.fn()} onStop={vi.fn()} onDismissNotice={onDismiss} />,
    )

    expect(screen.getByRole('status')).toHaveTextContent('Link copied. Paste it to a friend.')
    await userEvent.click(screen.getByRole('button', { name: 'Dismiss' }))
    expect(onDismiss).toHaveBeenCalled()
  })
})

describe('CheckInDialog', () => {
  it('renders above the navigation chrome, as a direct child of <body>', () => {
    // A nav container with its own stacking context must not trap the dialog below the bottom bar.
    render(
      <div data-testid="nav-host" style={{ position: 'fixed', zIndex: 5 }}>
        <CheckInDialog onFine={() => {}} onShareLocation={() => {}} />
      </div>,
    )

    const dialog = screen.getByRole('alertdialog', { name: 'Everything OK?' })
    expect(screen.getByTestId('nav-host')).not.toContainElement(dialog)
    expect(dialog.closest('.checkin-backdrop')?.parentElement).toBe(document.body)
    expect(screen.getByRole('button', { name: 'Share my location' })).toBeVisible()
  })

  it('asks "Everything OK?" with three clear choices, focusing "I\'m fine"', async () => {
    const onFine = vi.fn()
    const onShare = vi.fn()
    const { container } = render(<CheckInDialog onFine={onFine} onShareLocation={onShare} />)

    const dialog = screen.getByRole('alertdialog', { name: 'Everything OK?' })
    expect(dialog).toHaveAttribute('aria-modal', 'true')
    expect(screen.getByRole('button', { name: "I'm fine" })).toHaveFocus()
    expect(screen.getByRole('link', { name: 'Call 911' })).toHaveAttribute('href', 'tel:911')
    await userEvent.click(screen.getByRole('button', { name: 'Share my location' }))
    expect(onShare).toHaveBeenCalled()
    await userEvent.click(screen.getByRole('button', { name: "I'm fine" }))
    expect(onFine).toHaveBeenCalled()
    expect((await axe(container)).violations).toEqual([])
  })

  it('treats Escape as "I\'m fine"', async () => {
    const onFine = vi.fn()
    render(<CheckInDialog onFine={onFine} onShareLocation={vi.fn()} />)

    await userEvent.keyboard('{Escape}')

    expect(onFine).toHaveBeenCalled()
  })

  it('keeps Tab focus inside the dialog', async () => {
    render(<CheckInDialog onFine={vi.fn()} onShareLocation={vi.fn()} />)

    await userEvent.tab()
    await userEvent.tab()
    await userEvent.tab()

    expect(screen.getByRole('button', { name: "I'm fine" })).toHaveFocus()
    await userEvent.tab({ shift: true })
    expect(screen.getByRole('button', { name: 'Share my location' })).toHaveFocus()
  })
})

describe('FollowCard', () => {
  it('shows who is walking where, the arrival time, and how fresh the position is', () => {
    render(<FollowCard state="live" walk={sharedWalk()} nowMs={FOLLOW_NOW} reconnecting={false} />)

    expect(screen.getByRole('heading', { name: 'Walking to Midtown MARTA' })).toBeInTheDocument()
    expect(screen.getByText('Arrives ~10:54 PM')).toBeInTheDocument()
    expect(screen.getByText('Updated 12 s ago')).toBeInTheDocument()
  })

  it('waits for the first position', () => {
    render(<FollowCard state="live" walk={sharedWalk({ position: null })} nowMs={FOLLOW_NOW} reconnecting={false} />)

    expect(screen.getByText('Waiting for the first position…')).toBeInTheDocument()
  })

  it.each([
    ['arrived', 'Arrived', 'Reached Midtown MARTA.'],
    ['ended', 'Walk ended', 'Live sharing has stopped.'],
  ] as const)('shows a %s banner', (status, title, detail) => {
    render(<FollowCard state="live" walk={sharedWalk({ status })} nowMs={FOLLOW_NOW} reconnecting={false} />)

    const banner = screen.getByRole('status')
    expect(banner).toHaveTextContent(title)
    expect(banner).toHaveTextContent(detail)
    expect(screen.queryByText(/Arrives ~/)).toBeNull()
  })

  it('explains an expired link', () => {
    render(<FollowCard state="expired" walk={null} nowMs={FOLLOW_NOW} reconnecting={false} />)

    expect(screen.getByRole('status')).toHaveTextContent('Link expired')
  })

  it('says live sharing needs a connection in demo mode', () => {
    render(<FollowCard state="demo" walk={null} nowMs={FOLLOW_NOW} reconnecting={false} />)

    expect(screen.getByRole('status')).toHaveTextContent('Live sharing needs a connection')
  })

  it('shows loading, retrying, and reconnecting states', () => {
    const { rerender } = render(<FollowCard state="loading" walk={null} nowMs={FOLLOW_NOW} reconnecting={false} />)
    expect(screen.getByText('Loading the live walk…')).toBeInTheDocument()

    rerender(<FollowCard state="error" walk={null} nowMs={FOLLOW_NOW} reconnecting />)
    expect(screen.getByText("Can't reach PathPro right now. Retrying…")).toBeInTheDocument()

    rerender(<FollowCard state="live" walk={sharedWalk()} nowMs={FOLLOW_NOW} reconnecting />)
    expect(screen.getByText('Reconnecting…')).toBeInTheDocument()
  })

  it('never uses absolute-safety wording', () => {
    const { container } = render(<FollowCard state="live" walk={sharedWalk()} nowMs={FOLLOW_NOW} reconnecting={false} />)

    expect(container.textContent?.toLowerCase()).not.toMatch(/\bsafe|safest|unsafe|dangerous|guaranteed/)
  })
})

describe('ShareWalkPanel', () => {
  const MIN = 60_000
  let share: ReturnType<typeof vi.fn>

  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    share = vi.fn().mockResolvedValue(undefined)
    vi.stubGlobal('navigator', { share })
  })
  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  function props(over: Partial<ShareWalkPanelProps> = {}): ShareWalkPanelProps {
    return {
      demo: true,
      mode: 'gps',
      destination: { label: 'Midtown MARTA', lat: 33.781, lon: -84.3863 },
      route: null,
      position: [-84.395, 33.7775],
      accuracy: 9,
      remainingS: 600,
      arrived: false,
      ...over,
    }
  }

  it('shares a simulated walk in demo mode and shows it is live', async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    render(<ShareWalkPanel {...props()} />)

    await user.click(screen.getByRole('button', { name: 'Share my walk' }))

    expect(await screen.findByText('Sharing live')).toBeInTheDocument()
    expect(share).toHaveBeenCalledWith(expect.objectContaining({ url: expect.stringContaining('?demo=1') }))
  })

  it('checks in ten minutes after the expected arrival and re-shares on request', async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    render(<ShareWalkPanel {...props()} />)

    await act(async () => {
      await vi.advanceTimersByTimeAsync(20 * MIN)
    })
    const dialog = screen.getByRole('alertdialog', { name: 'Everything OK?' })
    expect(dialog).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Share my location' }))
    expect(share).toHaveBeenCalledTimes(1)
    await user.click(screen.getByRole('button', { name: "I'm fine" }))
    expect(screen.queryByRole('alertdialog')).toBeNull()
  })

  it('does not check in during a preview walk', async () => {
    render(<ShareWalkPanel {...props({ mode: 'preview' })} />)

    await act(async () => {
      await vi.advanceTimersByTimeAsync(60 * MIN)
    })

    expect(screen.queryByRole('alertdialog')).toBeNull()
  })
})
