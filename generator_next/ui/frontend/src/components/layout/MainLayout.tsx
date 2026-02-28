// ============================================================
// 메인 레이아웃 컴포넌트
// TopBar 아래: [지도 영역 (flex-1)] + [사이드 패널 (420px)]
// ============================================================

import React from 'react'

interface MainLayoutProps {
  mapSlot:   React.ReactNode
  panelSlot: React.ReactNode
}

export const MainLayout: React.FC<MainLayoutProps> = ({ mapSlot, panelSlot }) => {
  return (
    // h-full: 부모(App)가 h-screen을 가짐
    <main className="flex flex-1 overflow-hidden h-full">
      {/* 지도 영역: 나머지 공간 전체 */}
      <div className="flex-1 relative overflow-hidden">
        {mapSlot}
      </div>

      {/* 사이드 패널: 420px 고정 너비, 세로 스크롤 */}
      <aside
        className="w-[420px] flex-shrink-0 flex flex-col
                   bg-[var(--bg-secondary)] border-l border-[var(--border-default)]
                   overflow-y-auto"
      >
        {panelSlot}
      </aside>
    </main>
  )
}
