import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { ErrorBoundary } from './ErrorBoundary'

function Boom(): never {
  throw new Error('chunk failed')
}

describe('ErrorBoundary', () => {
  it('renders the fallback instead of unmounting the app', () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => undefined)
    render(
      <ErrorBoundary fallback={<p>Map unavailable</p>}>
        <Boom />
      </ErrorBoundary>,
    )
    expect(screen.getByText('Map unavailable')).toBeInTheDocument()
    spy.mockRestore()
  })

  it('renders children when nothing fails', () => {
    render(
      <ErrorBoundary fallback={<p>fallback</p>}>
        <p>map</p>
      </ErrorBoundary>,
    )
    expect(screen.getByText('map')).toBeInTheDocument()
  })
})
