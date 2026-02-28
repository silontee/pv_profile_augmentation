// ============================================================
// 우측 사이드 패널 컨테이너
// panelMode에 따라 (검색+요약) 또는 상세 패널 전환
// ============================================================

import React from 'react'
import { useUiStore } from '../../stores/uiStore'
import { DashboardSummary } from './DashboardSummary'
import { SearchPanel } from './SearchPanel'
import { DetailPanel } from './DetailPanel'

export const SidePanel: React.FC = () => {
  const panelMode = useUiStore((s) => s.panelMode)

  return (
    <div className="flex flex-col h-full">
      {panelMode === 'search' ? (
        // 검색 모드: 요약 + 검색 패널
        <>
          <DashboardSummary />
          <div className="flex-1 flex flex-col overflow-hidden">
            <SearchPanel />
          </div>
        </>
      ) : (
        // 상세 모드: 발전소 상세 패널
        <div className="flex-1 overflow-hidden">
          <DetailPanel />
        </div>
      )}
    </div>
  )
}
