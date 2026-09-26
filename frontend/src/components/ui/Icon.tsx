/** Small stroke icon set (24 px grid, currentColor) so controls read without emoji. */

const PATHS = {
  search: 'M10.5 17a6.5 6.5 0 1 0 0-13 6.5 6.5 0 0 0 0 13ZM15.5 15.5 20 20',
  layers: 'M12 4 3 8.5l9 4.5 9-4.5L12 4ZM3 12.5l9 4.5 9-4.5M3 16.5l9 4.5 9-4.5',
  locate: 'M12 19a7 7 0 1 0 0-14 7 7 0 0 0 0 14ZM12 2v3M12 19v3M2 12h3M19 12h3M12 14.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5Z',
  locateOff: 'M12 19a7 7 0 1 0 0-14 7 7 0 0 0 0 14ZM12 2v3M12 19v3M2 12h3M19 12h3M4 4l16 16',
  swap: 'M8 4v15M8 4 4.5 7.5M8 4l3.5 3.5M16 20V5M16 20l-3.5-3.5M16 20l3.5-3.5',
  back: 'M15 5 8 12l7 7',
  close: 'M6 6l12 12M18 6 6 18',
  share: 'M12 15V3M12 3 8 7M12 3l4 4M6 11H5a1 1 0 0 0-1 1v8a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-8a1 1 0 0 0-1-1h-1',
  volume: 'M4 10v4h4l5 4V6L8 10H4ZM16.5 8.5a5 5 0 0 1 0 7M19 6a8.5 8.5 0 0 1 0 12',
  info: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18ZM12 11v6M12 7.5v.5',
  play: 'M7 4.5v15L19.5 12 7 4.5Z',
  pencil: 'M4 20h4L19 9l-4-4L4 16v4ZM13.5 6.5l4 4',
  home: 'M4 11 12 4l8 7v9h-5v-6H9v6H4v-9Z',
  work: 'M4 8h16v11H4V8ZM9 8V5h6v3M4 13h16',
  clock: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18ZM12 7v5l3 2',
  pin: 'M12 21s7-6.2 7-11.5A7 7 0 0 0 5 9.5C5 14.8 12 21 12 21ZM12 12a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5Z',
  spark: 'M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M6 18l2.5-2.5M15.5 8.5 18 6',
  alert: 'M12 4 2.5 20h19L12 4ZM12 10v4.5M12 17.5v.5',
  flag: 'M5 21V4M5 4h11l-2 4 2 4H5',
  walk: 'M13.5 5.5a1.75 1.75 0 1 0 0-3.5 1.75 1.75 0 0 0 0 3.5ZM9 21l2.3-5.5L12.6 9M12.6 9 9.5 11v3M12.6 9l2.4 3 3 1M11.9 13l3.1 3v5',
  bike: 'M6 18.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7ZM18 18.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7ZM6 15l3.5-6.5H15L18 15M9.5 8.5 12 15H6M13.5 5.5H16l-1 3',
  ebike: 'M6 18.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7ZM18 18.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7ZM6 15l3.5-6.5H15L18 15M9.5 8.5 12 15H6M13 2.5l-2 3.5h3l-2 3',
  scooter: 'M6 20a2 2 0 1 0 0-4 2 2 0 0 0 0 4ZM18 20a2 2 0 1 0 0-4 2 2 0 0 0 0 4ZM8 18h8M18 18 15 5M12.5 5H17',
  train: 'M7 3h10a2 2 0 0 1 2 2v9a3 3 0 0 1-3 3H8a3 3 0 0 1-3-3V5a2 2 0 0 1 2-2ZM5 10h14M8 21l2-4M16 21l-2-4M8.5 13.5h.01M15.5 13.5h.01',
} as const

export type IconName = keyof typeof PATHS

export function Icon({ name, size = 20 }: { name: IconName; size?: number }) {
  return (
    <svg
      className="icon"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      <path d={PATHS[name]} />
    </svg>
  )
}
