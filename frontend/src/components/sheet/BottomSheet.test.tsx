import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it } from 'vitest'
import { BottomSheet } from './BottomSheet'

function Harness({ initial = false }: { initial?: boolean }) {
  const [expanded, setExpanded] = useState(initial)
  return (
    <BottomSheet label="Route comparison" expanded={expanded} onExpandedChange={setExpanded} peek={<p>Peek</p>}>
      <p>More detail</p>
    </BottomSheet>
  )
}

describe('BottomSheet', () => {
  it('starts in peek and toggles from the drag handle', async () => {
    const user = userEvent.setup()
    render(<Harness />)
    const sheet = screen.getByRole('region', { name: 'Route comparison' })
    const handle = screen.getByRole('button', { name: 'Expand Route comparison' })

    expect(sheet).toHaveAttribute('data-state', 'peek')
    expect(handle).toHaveAttribute('aria-expanded', 'false')
    await user.click(handle)
    expect(sheet).toHaveAttribute('data-state', 'expanded')
    expect(screen.getByRole('button', { name: 'Collapse Route comparison' })).toHaveAttribute('aria-expanded', 'true')
  })

  it('supports arrow keys and Escape on the handle', () => {
    render(<Harness />)
    const handle = screen.getByRole('button', { name: /Route comparison/ })
    const sheet = screen.getByRole('region', { name: 'Route comparison' })

    fireEvent.keyDown(handle, { key: 'ArrowUp' })
    expect(sheet).toHaveAttribute('data-state', 'expanded')
    fireEvent.keyDown(handle, { key: 'Escape' })
    expect(sheet).toHaveAttribute('data-state', 'peek')
    fireEvent.keyDown(handle, { key: 'ArrowUp' })
    fireEvent.keyDown(handle, { key: 'ArrowDown' })
    expect(sheet).toHaveAttribute('data-state', 'peek')
  })

  it('follows a drag up or down and ignores small jitters', () => {
    render(<Harness />)
    const handle = screen.getByRole('button', { name: /Route comparison/ })
    const sheet = screen.getByRole('region', { name: 'Route comparison' })

    fireEvent.pointerDown(handle, { clientY: 500 })
    fireEvent.pointerUp(handle, { clientY: 420 })
    fireEvent.click(handle) // the click that ends a drag must not undo it
    expect(sheet).toHaveAttribute('data-state', 'expanded')

    fireEvent.pointerDown(handle, { clientY: 420 })
    fireEvent.pointerUp(handle, { clientY: 425 })
    expect(sheet).toHaveAttribute('data-state', 'expanded')

    fireEvent.pointerDown(handle, { clientY: 420 })
    fireEvent.pointerUp(handle, { clientY: 520 })
    expect(sheet).toHaveAttribute('data-state', 'peek')
    expect(screen.getByText('More detail')).toBeInTheDocument()
  })
})
