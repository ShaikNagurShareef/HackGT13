import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { axe } from 'vitest-axe'
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
    await userEvent.click(screen.getByRole('button', { name: 'Send' }))
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
    expect(screen.getByRole('button', { name: 'Send' })).toBeDisabled()
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

// ---------- Ask PathPro v2: on-screen context, sources, and opt-in memory ----------

const MEMORY_TOKEN = '33333333-3333-4333-8333-333333333333.bWVtb3J5LXRva2VuLXNpZ25hdHVyZQ'
const MEMORY_KEY = 'pathpro:ask-memory:v1'
const PRIVACY_NOTE =
  'When on, what you type here is kept by Backboard for this browser until you tap Forget me. Your location, routes and routines are never sent.'
const SEGMENT_CONTEXT = { kind: 'segment', seg_id: 11, t: '2026-09-25T22:30:00-04:00', cond: 'wet', mode: 'walk' } as const
const ROUTE_CONTEXT = { kind: 'route', route_key: 'rk-123' } as const
const AREA_CONTEXT = { kind: 'area', cell: '8844c0a305fffff', t: '2026-09-25T22:30:00-04:00', cond: 'dry' } as const
const STREET_LABEL = 'Fifth Street Northwest · 10 PM'

function answerV2(text: string, extra: Record<string, unknown> = {}) {
  return {
    success: true,
    data: {
      answer: text,
      thread_id: THREAD,
      source: 'backboard',
      note: NOTE,
      sources: [],
      memory: 'off',
      context_used: 'conditions',
      context_dropped: false,
      ...extra,
    },
    error: null,
    model_version: 'v',
  }
}

/** Answers by path so memory calls and questions can interleave. */
function routeFetch(routes: Record<string, unknown[]>) {
  const queues = Object.fromEntries(Object.entries(routes).map(([k, v]) => [k, [...v]]))
  const fetcher = vi.fn(async (url: string) => {
    const body = queues[url]?.shift()
    if (body === undefined) throw new Error(`unexpected request to ${url}`)
    return new Response(JSON.stringify(body), JSON_HEADERS)
  })
  vi.stubGlobal('fetch', fetcher)
  return fetcher
}

function bodiesTo(fetcher: ReturnType<typeof vi.fn>, path: string): Record<string, unknown>[] {
  return (fetcher.mock.calls as unknown as [string, RequestInit][])
    .filter(([url]) => url === path)
    .map(([, init]) => JSON.parse(String(init.body)) as Record<string, unknown>)
}

describe('AskPanel v2: questions about what is on screen', () => {
  beforeEach(() => {
    window.sessionStorage.clear()
    window.localStorage.clear()
  })
  afterEach(() => {
    vi.unstubAllGlobals()
    resetRuntimeForTests()
    window.sessionStorage.clear()
    window.localStorage.clear()
  })

  it('shows a street context chip with street suggestions instead of the general ones', () => {
    render(<AskPanel onClose={vi.fn()} context={SEGMENT_CONTEXT} contextLabel={STREET_LABEL} />)

    expect(screen.getByText(`About: ${STREET_LABEL}`)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: `Stop asking about ${STREET_LABEL}` })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Why is this street high-risk at this hour?' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'What would lower the risk here?' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'How was the model tested?' })).toBeNull()
  })

  it('offers route suggestions for a route', () => {
    render(<AskPanel onClose={vi.fn()} context={ROUTE_CONTEXT} contextLabel="this route" />)

    expect(screen.getByText('About: this route')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Why is this route longer?' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Which stretches did it avoid?' })).toBeInTheDocument()
  })

  it('offers an area suggestion for a City Pulse area', () => {
    render(<AskPanel onClose={vi.fn()} context={AREA_CONTEXT} contextLabel="this area" />)

    expect(screen.getByText('About: this area')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'What drives traffic risk in this area?' })).toBeInTheDocument()
  })

  it('has no chip and the general suggestions without a context', () => {
    render(<AskPanel onClose={vi.fn()} />)

    expect(screen.queryByText(/^About:/)).toBeNull()
    for (const q of ASK_SUGGESTIONS) expect(screen.getByRole('button', { name: q })).toBeInTheDocument()
  })

  it('sends the context with each question', async () => {
    const fetcher = routeFetch({ '/api/ask': [answerV2('It has many crashes.', { context_used: 'segment' }), answerV2('Fewer lanes.')] })
    render(<AskPanel onClose={vi.fn()} context={SEGMENT_CONTEXT} contextLabel={STREET_LABEL} />)

    await userEvent.click(screen.getByRole('button', { name: 'Why is this street high-risk at this hour?' }))
    await screen.findByText('It has many crashes.')
    await userEvent.type(screen.getByRole('textbox', { name: /your question/i }), 'And at noon?{enter}')
    await screen.findByText('Fewer lanes.')

    expect(bodiesTo(fetcher, '/api/ask')).toEqual([
      { question: 'Why is this street high-risk at this hour?', context: SEGMENT_CONTEXT },
      { question: 'And at noon?', context: SEGMENT_CONTEXT, thread_id: THREAD },
    ])
  })

  it('clears the chip with its × button and then asks in general', async () => {
    const fetcher = routeFetch({ '/api/ask': [answerV2('General answer.')] })
    render(<AskPanel onClose={vi.fn()} context={ROUTE_CONTEXT} contextLabel="this route" />)

    await userEvent.click(screen.getByRole('button', { name: 'Stop asking about this route' }))

    expect(screen.queryByText('About: this route')).toBeNull()
    expect(screen.getByRole('textbox', { name: /your question/i })).toHaveFocus()
    await userEvent.click(screen.getByRole('button', { name: 'How was the model tested?' }))
    await screen.findByText('General answer.')
    expect(bodiesTo(fetcher, '/api/ask')).toEqual([{ question: 'How was the model tested?' }])
  })

  it('says so politely and drops the chip when the route is no longer available', async () => {
    const fetcher = routeFetch({
      '/api/ask': [answerV2('Routes favour lower traffic risk.', { context_dropped: true }), answerV2('Next.')],
    })
    render(<AskPanel onClose={vi.fn()} context={ROUTE_CONTEXT} contextLabel="this route" />)

    await userEvent.click(screen.getByRole('button', { name: 'Why is this route longer?' }))
    await screen.findByText('Routes favour lower traffic risk.')

    expect(screen.getByRole('status')).toHaveTextContent('That route is no longer available, so I answered in general.')
    expect(screen.queryByText('About: this route')).toBeNull()
    await userEvent.type(screen.getByRole('textbox', { name: /your question/i }), 'What data is used?{enter}')
    await screen.findByText('Next.')
    expect(bodiesTo(fetcher, '/api/ask')[1]).toEqual({ question: 'What data is used?', thread_id: THREAD })
  })

  it('names the street when a street context is dropped', async () => {
    routeFetch({ '/api/ask': [answerV2('In general…', { context_dropped: true })] })
    render(<AskPanel onClose={vi.fn()} context={SEGMENT_CONTEXT} contextLabel={STREET_LABEL} />)

    await userEvent.click(screen.getByRole('button', { name: 'What would lower the risk here?' }))
    await screen.findByText('In general…')

    expect(screen.getByRole('status')).toHaveTextContent('That street is no longer available, so I answered in general.')
  })

  it('links the sources behind an answer in a new tab', async () => {
    routeFetch({
      '/api/ask': [
        answerV2('Tested on held-out crashes.', {
          sources: [
            { label: 'Model card', url: 'https://github.com/pathpro/pathpro/blob/main/docs/model_card.md' },
            { label: 'Decision log', url: 'https://github.com/pathpro/pathpro/blob/main/docs/decisions.md' },
          ],
        }),
      ],
    })
    render(<AskPanel onClose={vi.fn()} />)

    await userEvent.click(screen.getByRole('button', { name: 'How was the model tested?' }))
    await screen.findByText('Tested on held-out crashes.')

    expect(screen.getByText(/^Sources:/).closest('p')).toHaveTextContent('Sources: Model card · Decision log')
    const link = screen.getByRole('link', { name: 'Model card' })
    expect(link).toHaveAttribute('href', 'https://github.com/pathpro/pathpro/blob/main/docs/model_card.md')
    expect(link).toHaveAttribute('target', '_blank')
    expect(link).toHaveAttribute('rel', 'noopener noreferrer')
    expect(screen.getByRole('link', { name: 'Decision log' })).toBeInTheDocument()
  })

  it('shows no sources line when an answer has none', async () => {
    routeFetch({ '/api/ask': [answerV2('No sources here.')] })
    render(<AskPanel onClose={vi.fn()} />)

    await userEvent.click(screen.getByRole('button', { name: 'How was the model tested?' }))
    await screen.findByText('No sources here.')

    expect(screen.queryByText(/^Sources:/)).toBeNull()
  })

  it('keeps its v2 copy within the wording rules', () => {
    const { container } = render(<AskPanel onClose={vi.fn()} context={AREA_CONTEXT} contextLabel="this area" />)
    expect(container.textContent ?? '').not.toMatch(BANNED)
  })
})

describe('AskPanel v2: opt-in memory', () => {
  beforeEach(() => {
    window.sessionStorage.clear()
    window.localStorage.clear()
  })
  afterEach(() => {
    vi.unstubAllGlobals()
    resetRuntimeForTests()
    window.sessionStorage.clear()
    window.localStorage.clear()
  })

  it('is off by default and explains exactly what is kept', () => {
    render(<AskPanel onClose={vi.fn()} />)

    const toggle = screen.getByRole('switch', { name: 'Remember my preferences' })
    expect(toggle).toHaveAttribute('aria-checked', 'false')
    expect(screen.getByText(PRIVACY_NOTE)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Forget me' })).toBeNull()
  })

  it('turning it on stores the token, starts a new thread, and sends the token with questions', async () => {
    window.sessionStorage.setItem(ASK_THREAD_KEY, THREAD)
    const fetcher = routeFetch({
      '/api/ask/memory': [{ success: true, data: { memory_token: MEMORY_TOKEN } }],
      '/api/ask': [answerV2('Noted: you prefer well-lit streets.', { memory: 'on' })],
    })
    render(<AskPanel onClose={vi.fn()} />)

    const toggle = screen.getByRole('switch', { name: 'Remember my preferences' })
    await userEvent.click(toggle)

    await waitFor(() => expect(toggle).toHaveAttribute('aria-checked', 'true'))
    expect(JSON.parse(window.localStorage.getItem(MEMORY_KEY) ?? 'null')).toEqual({ token: MEMORY_TOKEN, on: true })
    expect(window.sessionStorage.getItem(ASK_THREAD_KEY)).toBeNull()
    expect(bodiesTo(fetcher, '/api/ask/memory')).toEqual([{}])

    await userEvent.type(screen.getByRole('textbox', { name: /your question/i }), 'I prefer well-lit streets{enter}')
    await screen.findByText('Noted: you prefer well-lit streets.')
    expect(bodiesTo(fetcher, '/api/ask')).toEqual([{ question: 'I prefer well-lit streets', memory_token: MEMORY_TOKEN }])
    expect(screen.getByText('Memory on')).toBeInTheDocument()
  })

  it('turning it off stops sending the token but keeps it until Forget me', async () => {
    window.localStorage.setItem(MEMORY_KEY, JSON.stringify({ token: MEMORY_TOKEN, on: true }))
    window.sessionStorage.setItem(ASK_THREAD_KEY, THREAD)
    const fetcher = routeFetch({ '/api/ask': [answerV2('General answer.')] })
    render(<AskPanel onClose={vi.fn()} />)

    const toggle = screen.getByRole('switch', { name: 'Remember my preferences' })
    expect(toggle).toHaveAttribute('aria-checked', 'true')
    await userEvent.click(toggle)

    expect(toggle).toHaveAttribute('aria-checked', 'false')
    expect(window.sessionStorage.getItem(ASK_THREAD_KEY)).toBeNull()
    expect(JSON.parse(window.localStorage.getItem(MEMORY_KEY) ?? 'null')).toEqual({ token: MEMORY_TOKEN, on: false })
    expect(screen.getByRole('button', { name: 'Forget me' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'How was the model tested?' }))
    await screen.findByText('General answer.')
    expect(bodiesTo(fetcher, '/api/ask')).toEqual([{ question: 'How was the model tested?' }])
    expect(screen.queryByText('Memory on')).toBeNull()
  })

  it('turning it back on reuses the stored token without a new clone', async () => {
    window.localStorage.setItem(MEMORY_KEY, JSON.stringify({ token: MEMORY_TOKEN, on: false }))
    const fetcher = routeFetch({})
    render(<AskPanel onClose={vi.fn()} />)

    const toggle = screen.getByRole('switch', { name: 'Remember my preferences' })
    await userEvent.click(toggle)

    expect(toggle).toHaveAttribute('aria-checked', 'true')
    expect(fetcher).not.toHaveBeenCalled()
  })

  it('Forget me deletes the memory, the token, and the thread', async () => {
    window.localStorage.setItem(MEMORY_KEY, JSON.stringify({ token: MEMORY_TOKEN, on: true }))
    window.sessionStorage.setItem(ASK_THREAD_KEY, THREAD)
    const fetcher = routeFetch({ '/api/ask/memory/forget': [{ success: true, data: { forgotten: true } }] })
    render(<AskPanel onClose={vi.fn()} />)

    await userEvent.click(screen.getByRole('button', { name: 'Forget me' }))

    expect(await screen.findByText('Ask PathPro memory deleted.')).toBeInTheDocument()
    expect(bodiesTo(fetcher, '/api/ask/memory/forget')).toEqual([{ memory_token: MEMORY_TOKEN }])
    expect(window.localStorage.getItem(MEMORY_KEY)).toBeNull()
    expect(window.sessionStorage.getItem(ASK_THREAD_KEY)).toBeNull()
    expect(screen.getByRole('switch', { name: 'Remember my preferences' })).toHaveAttribute('aria-checked', 'false')
    expect(screen.queryByRole('button', { name: 'Forget me' })).toBeNull()
  })

  it('handles the daily memory limit politely and stays off', async () => {
    routeFetch({ '/api/ask/memory': [{ success: false, data: null, error: { code: 'ASK_MEMORY_LIMIT', message: 'limit' } }] })
    render(<AskPanel onClose={vi.fn()} />)

    const toggle = screen.getByRole('switch', { name: 'Remember my preferences' })
    await userEvent.click(toggle)

    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent(/memory is full for today/i))
    expect(screen.getByRole('status')).toHaveTextContent(/still answers without it/i)
    expect(toggle).toHaveAttribute('aria-checked', 'false')
    expect(window.localStorage.getItem(MEMORY_KEY)).toBeNull()
  })

  it('says memory is unavailable when it cannot be turned on', async () => {
    routeFetch({ '/api/ask/memory': [{ success: false, data: null, error: { code: 'ASK_UNAVAILABLE', message: 'x' } }] })
    render(<AskPanel onClose={vi.fn()} />)

    await userEvent.click(screen.getByRole('switch', { name: 'Remember my preferences' }))

    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent(/can't turn on memory right now/i))
    expect(screen.getByRole('switch', { name: 'Remember my preferences' })).toHaveAttribute('aria-checked', 'false')
  })

  it('keeps its memory copy within the wording rules', () => {
    window.localStorage.setItem(MEMORY_KEY, JSON.stringify({ token: MEMORY_TOKEN, on: true }))
    const { container } = render(<AskPanel onClose={vi.fn()} />)
    expect(container.textContent ?? '').not.toMatch(BANNED)
  })
})

describe('AskPanel chat layout', () => {
  beforeEach(() => {
    window.sessionStorage.clear()
    window.localStorage.clear()
  })
  afterEach(() => {
    vi.unstubAllGlobals()
    resetRuntimeForTests()
    window.sessionStorage.clear()
    window.localStorage.clear()
  })

  it('names the assistant in the header and says it is powered by Backboard', () => {
    render(<AskPanel onClose={vi.fn()} />)

    const dialog = screen.getByRole('dialog', { name: 'Ask PathPro' })
    expect(within(dialog).getByRole('heading', { name: 'Ask PathPro' })).toBeInTheDocument()
    expect(within(dialog).getByText('Powered by Backboard')).toBeInTheDocument()
  })

  it('shows the question as a message with a typing indicator while waiting', async () => {
    let release: (r: Response) => void = () => undefined
    vi.stubGlobal('fetch', vi.fn(() => new Promise<Response>((resolve) => (release = resolve))))
    render(<AskPanel onClose={vi.fn()} />)

    await userEvent.click(screen.getByRole('button', { name: 'How was the model tested?' }))

    const log = screen.getByRole('log')
    expect(log).toHaveTextContent('How was the model tested?')
    expect(within(log).getByTestId('ask-typing')).toBeInTheDocument()
    release(new Response(JSON.stringify(answer('Done.')), JSON_HEADERS))
    await screen.findByText('Done.')
    expect(within(log).queryByTestId('ask-typing')).toBeNull()
    expect(within(log).getAllByText('How was the model tested?')).toHaveLength(1)
  })

  it('drops the pending question when the answer fails, keeping the error line', async () => {
    respondWith({ success: false, data: null, error: { code: 'ASK_UNAVAILABLE', message: 'x' } })
    render(<AskPanel onClose={vi.fn()} />)

    await userEvent.click(screen.getByRole('button', { name: 'How was the model tested?' }))

    expect(await screen.findByText(ASK_ERROR)).toBeInTheDocument()
    expect(screen.getByRole('log')).not.toHaveTextContent('How was the model tested?')
  })

  it('marks a fallback answer so it reads as a muted message', async () => {
    respondWith(answer('I could not answer that.', null, 'fallback'), answer('Real answer.'))
    render(<AskPanel onClose={vi.fn()} />)

    await userEvent.click(screen.getByRole('button', { name: 'How was the model tested?' }))
    const fallback = await screen.findByText('I could not answer that.')
    await userEvent.type(screen.getByRole('textbox', { name: /your question/i }), 'Try again please{enter}')
    const real = await screen.findByText('Real answer.')

    expect(fallback.closest('[data-variant]')).toHaveAttribute('data-variant', 'fallback')
    expect(real.closest('[data-variant]')).toHaveAttribute('data-variant', 'answer')
  })

  it('tucks the memory privacy note under an info button', async () => {
    render(<AskPanel onClose={vi.fn()} />)

    const info = screen.getByRole('button', { name: 'What memory keeps' })
    const note = screen.getByText(PRIVACY_NOTE)
    expect(info).toHaveAttribute('aria-expanded', 'false')
    expect(note).not.toBeVisible()
    expect(screen.getByRole('switch', { name: 'Remember my preferences' })).toHaveAccessibleDescription(PRIVACY_NOTE)

    await userEvent.click(info)

    expect(info).toHaveAttribute('aria-expanded', 'true')
    expect(note).toBeVisible()
  })

  it('has no axe violations with a context chip', async () => {
    const { container } = render(<AskPanel onClose={vi.fn()} context={SEGMENT_CONTEXT} contextLabel={STREET_LABEL} />)
    expect((await axe(container)).violations).toEqual([])
  })
})

describe('Forget me styling', () => {
  it('uses the shared link button style, not an unstyled box', () => {
    window.localStorage.setItem(MEMORY_KEY, JSON.stringify({ token: MEMORY_TOKEN, on: true }))
    routeFetch({})
    render(<AskPanel onClose={vi.fn()} />)

    expect(screen.getByRole('button', { name: 'Forget me' })).toHaveClass('link-btn', 'ask-forget')
  })
})
