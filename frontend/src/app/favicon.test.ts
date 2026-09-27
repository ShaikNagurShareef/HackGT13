import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const root = resolve(__dirname, '../..')
const html = readFileSync(resolve(root, 'index.html'), 'utf8')
const publicFile = (href: string) => resolve(root, 'public', href.replace(/^\//, ''))

describe('favicon and app icons', () => {
  it('links an SVG favicon, PNG and ICO fallbacks, an Apple touch icon, and a manifest', () => {
    expect(html).toMatch(/<link rel="icon" type="image\/svg\+xml" href="\/favicon\.svg"/)
    expect(html).toMatch(/<link rel="icon" type="image\/png" sizes="32x32" href="\/favicon-32\.png"/)
    expect(html).toMatch(/<link rel="icon" href="\/favicon\.ico" sizes="any"/)
    expect(html).toMatch(/<link rel="apple-touch-icon" href="\/apple-touch-icon\.png"/)
    expect(html).toMatch(/<link rel="manifest" href="\/manifest\.webmanifest"/)
  })

  it('ships every linked icon file', () => {
    const hrefs = [...html.matchAll(/<link rel="(?:icon|apple-touch-icon|manifest)"[^>]*href="([^"]+)"/g)].map((m) => m[1])
    expect(hrefs.length).toBeGreaterThanOrEqual(5)
    for (const href of hrefs) expect(existsSync(publicFile(href)), href).toBe(true)
  })

  it('uses the PathPro mark, not the Vite starter logo', () => {
    const svg = readFileSync(publicFile('/favicon.svg'), 'utf8')
    expect(svg).toContain('#3fd1c6')
    expect(svg).not.toContain('#863bff')
  })

  it('names the app and lists home-screen icons in the manifest', () => {
    const manifest = JSON.parse(readFileSync(publicFile('/manifest.webmanifest'), 'utf8'))
    expect(manifest.name).toBe('PathPro')
    const sizes = manifest.icons.map((i: { sizes: string }) => i.sizes)
    expect(sizes).toEqual(expect.arrayContaining(['192x192', '512x512']))
    for (const icon of manifest.icons) expect(existsSync(publicFile(icon.src)), icon.src).toBe(true)
  })
})
