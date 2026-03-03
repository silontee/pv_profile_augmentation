// ============================================================
// 토지피복 범례 — 토지피복 레이어 ON 시 지도 우상단에 표시
// ============================================================

import React from 'react'
import { useUiStore } from '../../stores/uiStore'

const LEGEND_ITEMS = [
  { color: '#ea580c', label: '시가화건조지역', sub: '도시·도로·공업' },
  { color: '#eab308', label: '농업지역',       sub: '논·밭·과수원'  },
  { color: '#22c55e', label: '산림지역',       sub: '활엽·침엽·혼효림' },
  { color: '#84cc16', label: '초지',           sub: '자연·인공초지' },
  { color: '#06b6d4', label: '습지',           sub: '내륙·연안습지' },
  { color: '#d97706', label: '나지',           sub: '채광지·모래·황무지' },
  { color: '#3b82f6', label: '수역',           sub: '하천·호수·해양' },
]

export const LandcoverLegend: React.FC = () => {
  const landcover = useUiStore((s) => s.layers.landcover)

  if (!landcover) return null

  return (
    <div
      className="absolute top-3 right-3 z-10
                 bg-[var(--bg-elevated)]
                 border border-[var(--border-default)] rounded-lg
                 shadow-lg px-3 py-2.5 min-w-[160px]"
    >
      <p className="text-[11px] font-semibold text-[var(--text-secondary)] mb-2 tracking-wide">
        토지피복 (중분류)
      </p>
      <div className="space-y-1.5">
        {LEGEND_ITEMS.map(({ color, label, sub }) => (
          <div key={label} className="flex items-center gap-2">
            <span
              className="w-3 h-3 rounded-sm flex-shrink-0 border border-black/10"
              style={{ backgroundColor: color }}
            />
            <div>
              <span className="text-[11px] text-[var(--text-primary)]">{label}</span>
              <span className="text-[10px] text-[var(--text-muted)] ml-1">{sub}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
