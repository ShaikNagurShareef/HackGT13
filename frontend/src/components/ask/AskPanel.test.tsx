import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { resetRuntimeForTests } from '../../api/runtime'
import { ASK_ERROR, ASK_SUGGESTIONS, ASK_THREAD_KEY, AskPanel } from './AskPanel'

const JSON_HEADERS = { headers: { 'content-type': 'application/json' } }
const BANNED = /\b(safe|safer|safest|unsafe|dangerous|bad area|guaranteed)\b/i
const BARE_UUID = '22222222-2222-4222-8222-222222222222'
// The server hands out a signed token '<uuid>.<sig>'; a bare Backboard thread id is never sent.
const THREAD = `${BARE_UUID}.Zm9vYmFyYmF6cXV4MTIzNDU2Nzg5MGFi`
const NOTE = "Answered from PathPro's model card and docs · powered by Backboard"

function answer(text: string, thread: string | null = THREAD, source = 'backboard') {
  return {
    success: true,
    data: { answer: text, thread_id: thread, source, note: NOTE },
    error: null,
    model_version: 'v',
  }
}

function respondWith(...bodies: unknown[]) {
  const queue = [...bodies]
  const fetcher = vi.fn(async () => new Response(JSON.stringify(queue.shift()), JSON_HEADERS))
  vi.stubGlobal('fetch', fetcher)
  return fetcher
}

function sentBody(fetcher: ReturnType<typeof vi.fn>, i: number): Record<string, unknown> {
  const [url, init] = fetcher.mock.calls[i] as unknown as [string, RequestInit]
  expect(url).toBe('/api/ask')
  expect(init.method).toBe('POST')
  return JSON.parse(String(init.body)) as Record<string, unknown>
}

describe('AskPanel (Ask PathPro on Backboard)', () => {
  beforeEach(() => window.sessionStorage.clear())
  afterEach(() => {
    vi.unstubAllGlobals()
    resetRuntimeForTests()
    window.sessionStorage.clear()
  })

  it('offers three suggested questions and a labelled, bounded input', () => {
    render(<AskPanel onClose={vi.fn()} />)

    expect(screen.getByRole('dialog', { name: 'Ask PathPro' })).toBeInTheDocument()
    expect(ASK_SUGGESTIONS).toEqual([
      "Why isn't crime used for routing?",
      'How was the model tested?',
      "What does '54% less traffic risk' mean?",
    ])
    for (const q of ASK_SUGGESTIONS) expect(screen.getByRole('button', { name: q })).toBeInTheDocument()
    const input = screen.getByRole('textbox', { name: /your question/i })
    expect(input).toHaveAttribute('maxLength', '300')
    expect(input).toHaveFocus()
  })

  it('asks a suggested question and shows the answer in a live region with the note', async () => {
    const fetcher = respondWith(answer('It was tested on held-out 2024 crashes.'))
    render(<AskPanel onClose={vi.fn()} />)

    await userEvent.click(screen.getByRole('button', { name: 'How was the model tested?' }))

    expect(await screen.findByText('It was tested on held-out 2024 crashes.')).toBeInTheDocument()
    expect(sentBody(fetcher, 0)).toEqual({ question: 'How was the model tested?' })
    const log = screen.getByRole('log')
    expect(log).toHaveAttribute('aria-live', 'polite')
    expect(log).toHaveTextContent('How was the model tested?')
    expect(screen.getByText(NOTE)).toBeInTheDocument()
    expect(window.sessionStorage.getItem(ASK_THREAD_KEY)).toBe(THREAD)
    expect(window.localStorage.getItem(ASK_THREAD_KEY)).toBeNull()
  })

  it('continues the same thread for follow-up questions typed in the box', async () => {
    const fetcher = respondWith(answer('First answer.'), answer('Second answer.'))
    render(<AskPanel onClose={vi.fn()} />)
    const input = screen.getByRole('textbox', { name: /your question/i })

    await userEvent.type(input, 'What data does PathPro use?{enter}')
    await screen.findByText('First answer.')
    await userEvent.type(input, 'And how often is it updated?')
    await userEvent.click(screen.getByRole('button', { name: 'Ask' }))
    await screen.findByText('Second answer.')

    expect(sentBody(fetcher, 0)).toEqual({ question: 'What data does PathPro use?' })
    expect(sentBody(fetcher, 1)).toEqual({ question: 'And how often is it updated?', thread_id: THREAD })
    expect(input).toHaveValue('')
  })

  it('resumes a thread kept in this tab and forgets it when the server drops it', async () => {
    window.sessionStorage.setItem(ASK_THREAD_KEY, THREAD)
    const fetcher = respondWith(answer('I could not answer that.', null, 'fallback'))
    render(<AskPanel onClose={vi.fn()} />)

    await userEvent.click(screen.getByRole('button', { name: 'How was the model tested?' }))
    await screen.findByText('I could not answer that.')

    expect(sentBody(fetcher, 0)).toEqual({ question: 'How was the model tested?', thread_id: THREAD })
    expect(window.sessionStorage.getItem(ASK_THREAD_KEY)).toBeNull()
  })

  it('ignores a bare thread id stored before threads were signed', async () => {
    window.sessionStorage.setItem(ASK_THREAD_KEY, BARE_UUID)
    const fetcher = respondWith(answer('Answer.'))
    render(<AskPanel onClose={vi.fn()} />)

    await userEvent.click(screen.getByRole('button', { name: 'How was the model tested?' }))
    await screen.findByText('Answer.')

    expect(sentBody(fetcher, 0)).toEqual({ question: 'How was the model tested?' })
    expect(window.sessionStorage.getItem(ASK_THREAD_KEY)).toBe(THREAD)
  })

  it('ignores a token with a too-short signature', async () => {
    window.sessionStorage.setItem(ASK_THREAD_KEY, `${BARE_UUID}.short`)
    const fetcher = respondWith(answer('Answer.'))
    render(<AskPanel onClose={vi.fn()} />)

    await userEvent.click(screen.getByRole('button', { name: 'How was the model tested?' }))
    await screen.findByText('Answer.')

    expect(sentBody(fetcher, 0)).toEqual({ question: 'How was the model tested?' })
  })

  it('ignores a corrupt stored thread id', async () => {
    window.sessionStorage.setItem(ASK_THREAD_KEY, '../not-a-thread')
    const fetcher = respondWith(answer('Answer.'))
    render(<AskPanel onClose={vi.fn()} />)

    await userEvent.click(screen.getByRole('button', { name: 'How was the model tested?' }))
    await screen.findByText('Answer.')

    expect(sentBody(fetcher, 0)).toEqual({ question: 'How was the model tested?' })
  })

  it('shows a loading state while waiting', async () => {
    let release: (r: Response) => void = () => undefined
    vi.stubGlobal('fetch', vi.fn(() => new Promise<Response>((resolve) => (release = resolve))))
    render(<AskPanel onClose={vi.fn()} />)

    await userEvent.click(screen.getByRole('button', { name: 'How was the model tested?' }))

    expect(screen.getByRole('status')).toHaveTextContent(/looking through pathpro's docs/i)
    expect(screen.getByRole('button', { name: 'Ask' })).toBeDisabled()
    release(new Response(JSON.stringify(answer('Done.')), JSON_HEADERS))
    await screen.findByText('Done.')
  })

  it('shows a polite error line when Ask PathPro is unavailable', async () => {
    respondWith({ success: false, data: null, error: { code: 'ASK_UNAVAILABLE', message: 'x' } })
    render(<AskPanel onClose={vi.fn()} />)

    await userEvent.click(screen.getByRole('button', { name: 'How was the model tested?' }))

    expect(await screen.findByText(ASK_ERROR)).toBeInTheDocument()
  })

  it('does not send blank or too-short questions', async () => {
    const fetcher = respondWith(answer('unused'))
    render(<AskPanel onClose={vi.fn()} />)

    await userEvent.type(screen.getByRole('textbox', { name: /your question/i }), '  a {enter}')

    expect(fetcher).not.toHaveBeenCalled()
  })

  it('closes from the close button', async () => {
    const onClose = vi.fn()
    render(<AskPanel onClose={onClose} />)

    await userEvent.click(screen.getByRole('button', { name: 'Close Ask PathPro' }))

    expect(onClose).toHaveBeenCalled()
  })

  it('keeps its copy within the wording rules', async () => {
    const { container } = render(<AskPanel onClose={vi.fn()} />)

    expect(container.textContent ?? '').not.toMatch(BANNED)
    expect(ASK_ERROR).not.toMatch(BANNED)
    await waitFor(() => expect(screen.getByRole('dialog')).toBeInTheDocument())
  })
})
