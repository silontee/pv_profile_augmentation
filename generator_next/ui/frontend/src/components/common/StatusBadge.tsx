// ============================================================
// 발전소 상태 뱃지 컴포넌트
// 정상가동 / 가동중단 / 폐기 / 좌표없음
// ============================================================

import React from 'react'
import type { FacilityStatus } from '../../types'

interface StatusBadgeProps {
  status: FacilityStatus | 'no-coord'
  /** 뱃지 크기 (기본: md) */
  size?: 'sm' | 'md'
}

/** 상태별 스타일 매핑 */
const STATUS_CONFIG: Record<
  FacilityStatus | 'no-coord',
  { label: string; dot: string; bg: string; text: string }
> = {
  '정상가동': {
    label: '정상가동',
    dot:   'bg-[var(--status-active)]',
    bg:    'bg-[var(--status-active)]/10',
    text:  'text-[var(--status-active)]',
  },
  '가동중단': {
    label: '가동중단',
    dot:   'bg-[var(--status-stopped)]',
    bg:    'bg-[var(--status-stopped)]/10',
    text:  'text-[var(--status-stopped)]',
  },
  '폐기': {
    label: '폐기',
    dot:   'bg-[var(--status-retired)] border border-[var(--border-hover)]',
    bg:    'bg-[var(--status-retired)]/20',
    text:  'text-[var(--text-secondary)]',
  },
  'no-coord': {
    label: '좌표없음',
    dot:   'bg-[var(--status-no-coord)]',
    bg:    'bg-[var(--status-no-coord)]/10',
    text:  'text-[var(--status-no-coord)]',
  },
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, size = 'md' }) => {
  const cfg = STATUS_CONFIG[status]
  const padding = size === 'sm' ? 'px-1.5 py-0.5 text-[10px]' : 'px-2 py-0.5 text-xs'
  const dotSize = size === 'sm' ? 'w-1.5 h-1.5' : 'w-2 h-2'

  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full font-medium ${padding} ${cfg.bg} ${cfg.text}`}
    >
      <span className={`rounded-full flex-shrink-0 ${dotSize} ${cfg.dot}`} />
      {cfg.label}
    </span>
  )
}
