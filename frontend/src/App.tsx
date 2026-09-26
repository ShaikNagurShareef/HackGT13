import { PathPro } from './app/PathPro'
import { useBundle } from './hooks/useBundle'

/** Shell: start loading the model bundle and hand everything to the PathPro container. */
export default function App() {
  const { data, error } = useBundle()
  return <PathPro data={data} loadError={error} />
}
