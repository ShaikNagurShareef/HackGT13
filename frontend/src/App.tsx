import { PathPro } from './app/PathPro'
import { useBundle } from './hooks/useBundle'

/** Shell: load the model bundle once, then hand over to the PathPro container. */
export default function App() {
  const { data, error } = useBundle()
  if (error) {
    return (
      <main className="app app-error">
        <p>{error}</p>
      </main>
    )
  }
  if (!data) {
    return (
      <main className="app app-loading" aria-busy="true">
        <p>Loading PathPro…</p>
      </main>
    )
  }
  return <PathPro data={data} />
}
