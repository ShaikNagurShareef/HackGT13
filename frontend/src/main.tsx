import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './styles/app.css'
import './styles/layout.css'
import './styles/home.css'
import './styles/sheets.css'
import './styles/nav.css'
import './styles/desktop.css'
import './styles/safety.css'
import './styles/share.css'
import './styles/modes.css'
import './styles/ask.css'
import App from './App.tsx'
import { initRuntime } from './api/runtime'

const root = document.getElementById('root')
if (!root) throw new Error('missing #root element')

// Resolve the live API (static hosting only) before first render; falls back to the demo.
void initRuntime(import.meta.env.BASE_URL).finally(() =>
  createRoot(root).render(
    <StrictMode>
      <App />
    </StrictMode>,
  ),
)
