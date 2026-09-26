import { Component, type ErrorInfo, type ReactNode } from 'react'

interface Props {
  fallback: ReactNode
  children: ReactNode
}

interface State {
  failed: boolean
}

/** Contain failures (e.g. the map chunk failing to load offline) so the rest of the app lives. */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { failed: false }

  static getDerivedStateFromError(): State {
    return { failed: true }
  }

  componentDidCatch(_error: Error, _info: ErrorInfo): void {
    // Rendering the fallback is the whole recovery; nothing to report client-side.
  }

  render(): ReactNode {
    return this.state.failed ? this.props.fallback : this.props.children
  }
}
