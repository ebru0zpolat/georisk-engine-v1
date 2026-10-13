import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import './index.css'
import './portfolio-demo.css'
import SpaShellSync from './SpaShellSync.tsx'
import { syncSpaShell } from './spaShell.ts'
import { initHeroScorecard } from './heroScorecard.ts'
import RiskSnapshot from './pages/RiskSnapshot.tsx'
import RiskTilesPage from './pages/RiskTilesPage.tsx'
import PortfolioDemoPage from './pages/PortfolioDemoPage.tsx'

syncSpaShell(window.location.pathname)

// Landing-only: binds the hero coordinate box to POST /v1/risk/preview.
initHeroScorecard()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <SpaShellSync />
      <Routes>
        <Route path="/snapshot/:assetId" element={<RiskSnapshot />} />
        <Route path="/tiles" element={<RiskTilesPage />} />
        <Route path="/demo" element={<PortfolioDemoPage />} />
      </Routes>
    </BrowserRouter>
  </StrictMode>,
)
