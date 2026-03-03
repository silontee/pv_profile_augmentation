// ============================================================
// 레이어 토글 패널 (지도 위 좌하단 오버레이)
// 체크박스로 마커/인프라 레이어 on/off
// ============================================================

import React, { useState } from 'react'
import { useUiStore } from '../../stores/uiStore'
import type { UiState } from '../../stores/uiStore'

// UiState에서 layers 타입 추출
type LayerKey = keyof UiState['layers']

interface LayerConfig {
  key: LayerKey
  label: string
  color: string
}

const LAYERS: LayerConfig[] = [
  { key: 'active',     label: '정상가동',  color: 'var(--status-active)'    },
  { key: 'stopped',    label: '가동중단',  color: 'var(--status-stopped)'   },
  { key: 'retired',    label: '폐기',      color: 'var(--status-retired)'   },
  { key: 'substation', label: '변전소',    color: 'var(--infra-substation)' },
  { key: 'powerline',  label: '송배전선',  color: 'var(--infra-powerline)'  },
  { key: 'boundary',   label: '시군구 경계', color: 'var(--text-muted)'    },
]

export const LayerToggle: React.FC = () => {
  const { layers, toggleLayer } = useUiStore()
  const [open, setOpen] = useState(true)

  return (
    <div
      className="absolute bottom-24 left-3 z-10
                 bg-[var(--bg-elevated)]/90 backdrop-blur-sm
                 border border-[var(--border-default)] rounded-lg
                 shadow-lg text-xs"
    >
      {/* 헤더 (토글) */}
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center justify-between w-full px-3 py-2
                   text-[var(--text-secondary)] hover:text-[var(--text-primary)]
                   transition-colors"
      >
        <span className="font-medium">레이어</span>
        <svg
          className={`w-3 h-3 transition-transform ${open ? '' : '-rotate-90'}`}
          fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {/* 레이어 목록 */}
      {open && (
        <div className="pb-2 px-3 space-y-1.5 min-w-[140px]">
          {LAYERS.map(({ key, label, color }) => (
            <label
              key={key}
              className="flex items-center gap-2 cursor-pointer
                         text-[var(--text-secondary)] hover:text-[var(--text-primary)]
                         transition-colors"
            >
              <input
                type="checkbox"
                checked={layers[key]}
                onChange={() => toggleLayer(key)}
                className="sr-only"
              />
              {/* 커스텀 체크박스 */}
              <span
                className={`flex items-center justify-center w-3.5 h-3.5 rounded-sm border
                            transition-colors flex-shrink-0
                            ${layers[key]
                              ? 'border-transparent'
                              : 'border-[var(--border-hover)] bg-transparent'
                            }`}
                style={layers[key] ? { backgroundColor: color } : {}}
              >
                {layers[key] && (
                  <svg className="w-2.5 h-2.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                  </svg>
                )}
              </span>
              <span>{label}</span>
            </label>
          ))}
        </div>
      )}
    </div>
  )
}
