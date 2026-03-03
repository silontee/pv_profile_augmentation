// ============================================================
// 최상단 네비게이션 바
// 로고 | 상태 요약 뱃지 | 전역 검색 | 메뉴 버튼
// ============================================================

import React, { useEffect, useState, useRef } from 'react'
import { fetchStats } from '../../api/stats'
import { useSearchStore } from '../../stores/searchStore'
import { useUiStore } from '../../stores/uiStore'
import type { Stats } from '../../types'

/** 숫자를 한국식 천 단위로 포맷 */
const fmt = (n: number) => n.toLocaleString('ko-KR')

// ─── 상태 요약 뱃지 ────────────────────────────────────────

const StatusBadges: React.FC<{ stats: Stats | null }> = ({ stats }) => {
  if (!stats) {
    return (
      <div className="hidden md:flex items-center gap-2">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-6 w-28 rounded-full bg-[var(--bg-elevated)] animate-pulse" />
        ))}
      </div>
    )
  }

  const items = [
    { label: '정상가동', count: stats.active,  color: 'var(--status-active)'  },
    { label: '가동중단', count: stats.stopped, color: 'var(--status-stopped)' },
    { label: '폐기',     count: stats.retired, color: 'var(--status-retired)' },
  ]

  return (
    <div className="hidden md:flex items-center gap-2">
      {items.map(({ label, count, color }) => (
        <span
          key={label}
          className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium
                     bg-[var(--bg-elevated)] border border-[var(--border-default)]"
          style={{ color }}
        >
          <span
            className="w-1.5 h-1.5 rounded-full"
            style={{ backgroundColor: color }}
          />
          {label} {fmt(count)}
        </span>
      ))}
    </div>
  )
}

// ─── 전역 검색 입력 ────────────────────────────────────────

const GlobalSearch: React.FC = () => {
  const setQuery    = useSearchStore((s) => s.setQuery)
  const setPanelMode = useUiStore((s) => s.setPanelMode)
  const inputRef    = useRef<HTMLInputElement>(null)

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setQuery(e.target.value)
    setPanelMode('search')
  }

  // Ctrl+K 단축키
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault()
        inputRef.current?.focus()
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])

  return (
    <div className="relative flex-1 max-w-xs">
      <svg
        className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--text-muted)]"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        strokeWidth={2}
      >
        <path strokeLinecap="round" strokeLinejoin="round"
          d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z"
        />
      </svg>
      <input
        ref={inputRef}
        type="search"
        placeholder="시설명, 주소 검색... (Ctrl+K)"
        onChange={handleChange}
        className="w-full pl-9 pr-3 py-1.5 rounded-lg text-sm
                   bg-[var(--bg-elevated)] border border-[var(--border-default)]
                   text-[var(--text-primary)] placeholder:text-[var(--text-muted)]
                   focus:outline-none focus:border-[var(--accent-primary)]
                   focus:ring-2 focus:ring-[var(--accent-ring)]
                   transition-colors"
      />
    </div>
  )
}

// ─── TopBar 메인 ────────────────────────────────────────────

export const TopBar: React.FC = () => {
  const [stats, setStats] = useState<Stats | null>(null)

  useEffect(() => {
    fetchStats()
      .then(setStats)
      .catch(() => {/* 통계 로드 실패는 배너로 처리 */})
  }, [])

  return (
    <header
      className="flex items-center gap-4 px-4 h-12 flex-shrink-0
                 bg-[var(--bg-secondary)] border-b border-[var(--border-default)]
                 z-40"
    >
      {/* 로고 */}
      <div className="flex items-center gap-2 flex-shrink-0">
        <svg
          className="w-5 h-5 text-[var(--accent-primary)]"
          fill="currentColor"
          viewBox="0 0 24 24"
        >
          <circle cx="12" cy="12" r="5" />
          <path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"
                stroke="currentColor" strokeWidth="2" strokeLinecap="round" fill="none" />
        </svg>
        <span className="font-semibold text-sm text-[var(--text-primary)] tracking-tight">
          PV Profile
        </span>
      </div>

      {/* 상태 뱃지 */}
      <StatusBadges stats={stats} />

      {/* 스페이서 */}
      <div className="flex-1" />

      {/* 전역 검색 */}
      <GlobalSearch />
    </header>
  )
}
