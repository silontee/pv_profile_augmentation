// ============================================================
// 루트 App 컴포넌트
// TopBar + ErrorBanner + MainLayout(MapView + SidePanel)
// ============================================================

import React from 'react'
import { TopBar } from './components/layout/TopBar'
import { ErrorBanner } from './components/layout/ErrorBanner'
import { MainLayout } from './components/layout/MainLayout'
import { MapView } from './components/map/MapView'
import { SidePanel } from './components/panel/SidePanel'

const App: React.FC = () => {
  return (
    // h-screen: 화면 전체 높이, flex 세로 방향
    <div className="flex flex-col h-screen bg-[var(--bg-primary)] overflow-hidden">
      {/* 최상단 네비게이션 바 */}
      <TopBar />

      {/* DB 장애 배너 (503 수신 시 표시) */}
      <ErrorBanner />

      {/* 메인 레이아웃: 지도 + 사이드 패널 */}
      <MainLayout
        mapSlot={<MapView />}
        panelSlot={<SidePanel />}
      />
    </div>
  )
}

export default App
