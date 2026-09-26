import { FollowPage } from './app/FollowPage'
import { PathPro } from './app/PathPro'
import { useBundle } from './hooks/useBundle'
import { followIdFromPath } from './lib/shareWalk'

/** Shell: start loading the model bundle and hand everything to the PathPro container. */
function MapApp() {
  const { data, error } = useBundle()
  return <PathPro data={data} loadError={error} />
}

/** /follow/<id> is a friend's live view of a shared walk; it needs no model bundle. */
export default function App() {
  const followId = followIdFromPath(window.location.pathname)
  return followId ? <FollowPage walkId={followId} /> : <MapApp />
}
