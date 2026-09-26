import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { StatusScreen } from './StatusScreen'

describe('StatusScreen', () => {
  it('shows a branded, announced loading state', () => {
    render(<StatusScreen kind="loading" />)
    const main = screen.getByRole('main')
    expect(main).toHaveAttribute('aria-busy', 'true')
    expect(screen.getByRole('status')).toHaveTextContent('Loading the traffic-risk map…')
  })

  it('explains a failure and offers the offline demo and a retry', () => {
    render(<StatusScreen kind="error" message="Couldn't load the PathPro map data. Check your connection and refresh." />)
    expect(screen.getByRole('alert')).toHaveTextContent("Couldn't load the PathPro map data")
    expect(screen.getByRole('link', { name: 'Try the offline demo' })).toHaveAttribute('href', '?demo=1')
    expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument()
  })
})
