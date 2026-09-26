import type { SharedWalk } from '../../api/walks'
import { withBase } from '../../api/demo'
import { formatAgo } from '../../lib/shareWalk'
import { formatTime } from '../../lib/time'
import type { FollowState } from './useFollowWalk'

type Props = {
  state: FollowState
  walk: SharedWalk | null
  nowMs: number
  reconnecting: boolean
}

type Banner = { tone: 'done' | 'muted'; title: string; detail: string }

const NOTICE_BANNERS: Partial<Record<FollowState, Banner>> = {
  expired: {
    tone: 'muted',
    title: 'Link expired',
    detail: 'Shared walks stay live for 6 hours after the last update.',
  },
  demo: {
    tone: 'muted',
    title: 'Live sharing needs a connection',
    detail: 'This link came from the offline demo, so there is no live position to show.',
  },
}

function statusBanner(walk: SharedWalk): Banner | null {
  if (walk.status === 'arrived') return { tone: 'done', title: 'Arrived', detail: `Reached ${walk.destination.label}.` }
  if (walk.status === 'ended') return { tone: 'muted', title: 'Walk ended', detail: 'Live sharing has stopped.' }
  return null
}

function BannerView({ banner }: { banner: Banner }) {
  return (
    <div className={`follow-banner follow-${banner.tone}`} role="status">
      <p className="follow-banner-title">{banner.title}</p>
      <p className="follow-banner-detail">{banner.detail}</p>
    </div>
  )
}

function WalkDetails({ walk, nowMs, reconnecting }: { walk: SharedWalk; nowMs: number; reconnecting: boolean }) {
  const banner = statusBanner(walk)
  const at = walk.position ? Date.parse(walk.position.at) : null
  const freshness = at == null ? 'Waiting for the first position…' : `Updated ${formatAgo(nowMs - at)}`
  return (
    <>
      <h1 className="follow-title">Walking to {walk.destination.label}</h1>
      {banner ? <BannerView banner={banner} /> : <p className="follow-eta num">Arrives ~{formatTime(new Date(walk.eta_at))}</p>}
      <p className="follow-fresh faint">{freshness}</p>
      {reconnecting && <p className="follow-reconnect">Reconnecting…</p>}
    </>
  )
}

/** The follower's card: where the walker is heading, when they should arrive, and how fresh it is. */
export function FollowCard({ state, walk, nowMs, reconnecting }: Props) {
  const notice = NOTICE_BANNERS[state]
  let body
  if (notice) body = <BannerView banner={notice} />
  else if (walk) body = <WalkDetails walk={walk} nowMs={nowMs} reconnecting={reconnecting} />
  else if (state === 'error') body = <p className="follow-reconnect">Can't reach PathPro right now. Retrying…</p>
  else body = <p className="faint">Loading the live walk…</p>

  return (
    <section className="follow-card panel" aria-label="Live walk">
      <p className="follow-kicker">PathPro · Live walk</p>
      {body}
      <a className="follow-open link-btn" href={withBase('/')}>
        Open PathPro
      </a>
    </section>
  )
}
