import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const root = resolve(__dirname, '../..')
const html = readFileSync(resolve(root, 'index.html'), 'utf8')
const SITE = 'https://pathpro.tech'
const BANNED = /\b(safe|safest|unsafe|dangerous|bad area|guaranteed|crime)\b/i

const meta = (attr: 'name' | 'property', key: string) =>
  html.match(new RegExp(`<meta ${attr}="${key}" content="([^"]+)"`))?.[1]

/** Width and height from a PNG's IHDR chunk. */
const pngSize = (path: string) => {
  const buf = readFileSync(path)
  return { width: buf.readUInt32BE(16), height: buf.readUInt32BE(20) }
}

describe('link previews and search metadata', () => {
  it('describes the app for search engines and sets a canonical URL', () => {
    const description = meta('name', 'description')
    expect(description).toMatch(/Atlanta/)
    expect(description!.length).toBeLessThanOrEqual(160)
    expect(html).toContain(`<link rel="canonical" href="${SITE}/" />`)
  })

  it('ships Open Graph tags with an absolute 1200x630 image', () => {
    expect(meta('property', 'og:type')).toBe('website')
    expect(meta('property', 'og:site_name')).toBe('PathPro')
    expect(meta('property', 'og:url')).toBe(`${SITE}/`)
    expect(meta('property', 'og:title')).toMatch(/PathPro/)
    expect(meta('property', 'og:description')).toMatch(/2024/)
    expect(meta('property', 'og:image')).toBe(`${SITE}/og-image.png`)
    expect(meta('property', 'og:image:width')).toBe('1200')
    expect(meta('property', 'og:image:height')).toBe('630')
    expect(meta('property', 'og:image:alt')).toBeTruthy()

    const image = resolve(root, 'public/og-image.png')
    expect(existsSync(image)).toBe(true)
    expect(pngSize(image)).toEqual({ width: 1200, height: 630 })
  })

  it('ships a large Twitter card that reuses the Open Graph image', () => {
    expect(meta('name', 'twitter:card')).toBe('summary_large_image')
    expect(meta('name', 'twitter:title')).toBe(meta('property', 'og:title'))
    expect(meta('name', 'twitter:description')).toBe(meta('property', 'og:description'))
    expect(meta('name', 'twitter:image')).toBe(meta('property', 'og:image'))
  })

  it('keeps preview copy to traffic-risk language', () => {
    const copy = [...html.matchAll(/<meta (?:name|property)="[^"]+" content="([^"]+)"/g)].map((m) => m[1])
    for (const text of copy) expect(text).not.toMatch(BANNED)
  })

  it('shows the tagline in the page shell before the app mounts', () => {
    const shell = html.match(/<div id="root">([\s\S]*?)<\/main>\s*<\/div>/)?.[1] ?? ''
    expect(shell).toContain('PathPro')
    expect(shell).toMatch(/See the risks on your way, before you go/)
    expect(shell).not.toMatch(BANNED)
    expect(html).toMatch(/<noscript>[\s\S]*JavaScript[\s\S]*<\/noscript>/)
  })
})
