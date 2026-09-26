import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { SearchBar } from './SearchBar'

function setup(from = null as null | { lat: number; lon: number; label: string }) {
  const handlers = { onFrom: vi.fn(), onTo: vi.fn(), onSwap: vi.fn() }
  render(<SearchBar from={from} to={null} {...handlers} />)
  return handlers
}

describe('SearchBar (SRCH-01..04)', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('quick picks fill the origin first, then the destination', async () => {
    const first = setup()
    await userEvent.click(screen.getByRole('button', { name: 'Klaus Building' }))
    expect(first.onFrom).toHaveBeenCalledWith({ lat: 33.7771, lon: -84.3962, label: 'Klaus Building' })
  })

  it('fills the destination once an origin exists, and swaps', async () => {
    const h = setup({ lat: 1, lon: 2, label: 'Here' })
    await userEvent.click(screen.getByRole('button', { name: 'Midtown MARTA' }))
    await userEvent.click(screen.getByRole('button', { name: 'Swap origin and destination' }))
    expect(h.onTo).toHaveBeenCalledWith(expect.objectContaining({ label: 'Midtown MARTA' }))
    expect(h.onSwap).toHaveBeenCalled()
  })

  it('autocompletes MARTA stations from the gazetteer and picks with Enter', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ success: true, data: [] }), { headers: { 'content-type': 'application/json' } })))
    const h = setup({ lat: 1, lon: 2, label: 'Here' })
    const to = screen.getByRole('combobox', { name: 'To' })

    await userEvent.type(to, 'north ave')
    expect(await screen.findByRole('option', { name: /North Ave MARTA/ })).toBeInTheDocument()
    await userEvent.keyboard('{Enter}')

    expect(h.onTo).toHaveBeenCalledWith(expect.objectContaining({ label: 'North Ave MARTA' }))
  })

  it('merges geocoder results and flags places outside coverage', async () => {
    const results = [
      { label: 'Stone Mountain Park', address: 'Stone Mountain, GA', lat: 33.806, lon: -84.145, in_coverage: false },
    ]
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ success: true, data: results }), { headers: { 'content-type': 'application/json' } })))
    setup()

    await userEvent.type(screen.getByRole('combobox', { name: 'From' }), 'Stone Mountain')

    await waitFor(() => expect(screen.getByText('Outside routing coverage')).toBeInTheDocument())
  })

  it('says so when nothing matches (EC-03)', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ success: true, data: [] }), { headers: { 'content-type': 'application/json' } })))
    setup()

    await userEvent.type(screen.getByRole('combobox', { name: 'From' }), 'zzzz')

    expect(await screen.findByText('No match nearby. Try a building or street name.')).toBeInTheDocument()
  })
})
