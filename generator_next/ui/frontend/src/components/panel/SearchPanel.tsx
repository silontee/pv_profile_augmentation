// ============================================================
// 검색 패널
// 텍스트 입력 (debounce 300ms) + 상태 필터 + 범위 슬라이더
// 결과 리스트 + 페이지네이션
// ============================================================

import React, { useRef } from 'react'
import { useSearchStore } from '../../stores/searchStore'
import { useMapStore } from '../../stores/mapStore'
import { useUiStore } from '../../stores/uiStore'
import { useSearch } from '../../hooks/useSearch'
import { StatusBadge } from '../common/StatusBadge'
import { RangeSlider } from '../common/RangeSlider'
import type { Facility, FacilityStatus } from '../../types'

const fmt = (n: number) => n.toLocaleString('ko-KR')

// ─── 상태 필터 버튼 ─────────────────────────────────────────

const STATUS_OPTIONS: Array<{ value: FacilityStatus | ''; label: string }> = [
  { value: '',       label: '전체'    },
  { value: '정상가동', label: '정상가동' },
  { value: '가동중단', label: '가동중단' },
  { value: '폐기',     label: '폐기'    },
]

// ─── 발전소 행 아이템 ────────────────────────────────────────

interface FacilityRowProps {
  facility: Facility
  isSelected: boolean
  onClick: () => void
}

const FacilityRow: React.FC<FacilityRowProps> = ({ facility, isSelected, onClick }) => {
  const noCoord = !facility.has_coord

  return (
    <button
      onClick={onClick}
      className={`w-full text-left px-3 py-2.5 border-b border-[var(--border-default)]
                  hover:bg-[var(--bg-tertiary)] transition-colors
                  ${isSelected ? 'bg-[var(--bg-tertiary)] border-l-2 border-l-[var(--accent-primary)]' : ''}`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          {/* 시설명 */}
          <div className="flex items-center gap-1.5 mb-0.5">
            {noCoord && (
              <span
                className="text-[9px] font-bold px-1 rounded
                           bg-[var(--status-no-coord)]/20 text-[var(--status-no-coord)]
                           flex-shrink-0"
              >
                좌표없음
              </span>
            )}
            <p className="text-xs font-medium text-[var(--text-primary)] truncate">
              {facility.name ?? '(이름 없음)'}
            </p>
          </div>
          {/* 주소 */}
          <p className="text-[10px] text-[var(--text-muted)] truncate">
            {facility.addr_road ?? facility.addr_jibun ?? '-'}
          </p>
        </div>

        {/* 오른쪽: 상태 + 용량 */}
        <div className="flex flex-col items-end gap-1 flex-shrink-0">
          <StatusBadge status={facility.status} size="sm" />
          {facility.capacity_kw !== null && (
            <span className="text-[10px] text-[var(--text-secondary)] tabular-nums">
              {facility.capacity_kw.toLocaleString('ko-KR')} kW
            </span>
          )}
        </div>
      </div>

      {/* 허가일자 */}
      {facility.permit_date && (
        <p className="text-[10px] text-[var(--text-muted)] mt-0.5">
          허가 {facility.permit_date}
        </p>
      )}
    </button>
  )
}

// ─── SearchPanel 메인 ────────────────────────────────────────

export const SearchPanel: React.FC = () => {
  // 검색 훅 등록 (useEffect 내부에서 API 호출)
  useSearch()

  const {
    query, setQuery,
    status, setStatus,
    capRange, setCapRange,
    yearRange, setYearRange,
    page, setPage,
    results, total, loading,
  } = useSearchStore()

  const selectedId       = useMapStore((s) => s.selectedId)
  const setSelectedId    = useMapStore((s) => s.setSelectedId)
  const setHighlightedId = useMapStore((s) => s.setHighlightedId)
  const setPanelMode     = useUiStore((s) => s.setPanelMode)

  // 선택된 행으로 스크롤
  const rowRefs = useRef<Map<number, HTMLDivElement>>(new Map())

  const PAGE_SIZE = 50
  const totalPages = Math.ceil(total / PAGE_SIZE)

  /** 발전소 행 클릭 */
  const handleRowClick = (f: Facility) => {
    setSelectedId(f.id)
    setHighlightedId(f.id)
    setPanelMode('detail')

    // 좌표가 있으면 fly-to
    if (f.has_coord && f.lng !== null && f.lat !== null) {
      const flyTo = (window as Window & { __mapFlyTo?: (lng: number, lat: number, zoom?: number) => void }).__mapFlyTo
      flyTo?.(f.lng, f.lat, 15)

      // URL 딥링크 갱신
      const url = new URL(window.location.href)
      url.searchParams.set('id',  String(f.id))
      url.searchParams.set('lng', String(f.lng))
      url.searchParams.set('lat', String(f.lat))
      url.searchParams.set('z',   '15')
      window.history.pushState({}, '', url.toString())
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* ── 검색 입력 ─────────────────────────────────────── */}
      <div className="px-4 py-3 border-b border-[var(--border-default)]">
        <div className="relative">
          <svg
            className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--text-muted)]"
            fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
          >
            <path strokeLinecap="round" strokeLinejoin="round"
              d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z"
            />
          </svg>
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="주소 / 시설명 입력..."
            className="w-full pl-9 pr-3 py-2 rounded-lg text-sm
                       bg-[var(--bg-elevated)] border border-[var(--border-default)]
                       text-[var(--text-primary)] placeholder:text-[var(--text-muted)]
                       focus:outline-none focus:border-[var(--accent-primary)]
                       focus:ring-2 focus:ring-[var(--accent-ring)]"
          />
        </div>
      </div>

      {/* ── 상태 필터 버튼 ────────────────────────────────── */}
      <div className="px-4 py-2.5 flex gap-1.5 border-b border-[var(--border-default)]">
        {STATUS_OPTIONS.map(({ value, label }) => (
          <button
            key={value}
            onClick={() => setStatus(value)}
            className={`flex-1 py-1 rounded text-xs font-medium transition-colors
                        ${status === value
                          ? 'bg-[var(--accent-primary)] text-white'
                          : 'bg-[var(--bg-elevated)] text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)]'
                        }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* ── 범위 슬라이더 ─────────────────────────────────── */}
      <div className="px-4 py-3 space-y-4 border-b border-[var(--border-default)]">
        <RangeSlider
          label="설비용량"
          min={0}
          max={1000}
          step={10}
          value={capRange}
          onChange={setCapRange}
          unit=" kW"
        />
        <RangeSlider
          label="설치연도"
          min={2000}
          max={2026}
          step={1}
          value={yearRange}
          onChange={setYearRange}
          unit="년"
        />
      </div>

      {/* ── 검색 결과 헤더 ────────────────────────────────── */}
      <div className="px-4 py-2 flex items-center justify-between border-b border-[var(--border-default)]">
        <span className="text-xs text-[var(--text-secondary)]">
          {loading ? '검색 중...' : `총 ${fmt(total)}건`}
        </span>
        {query || status ? (
          <button
            onClick={() => {
              setQuery('')
              setStatus('')
            }}
            className="text-[10px] text-[var(--text-muted)] hover:text-[var(--text-secondary)]"
          >
            초기화
          </button>
        ) : null}
      </div>

      {/* ── 결과 리스트 ───────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto">
        {loading && results.length === 0 ? (
          // 스켈레톤
          <div className="p-3 space-y-2">
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="h-14 rounded bg-[var(--bg-elevated)] animate-pulse" />
            ))}
          </div>
        ) : results.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-40 text-[var(--text-muted)] text-sm">
            <svg className="w-8 h-8 mb-2 opacity-40" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round"
                d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z"
              />
            </svg>
            검색 결과가 없습니다.
          </div>
        ) : (
          results.map((f) => (
            <div
              key={f.id}
              ref={(el) => {
                if (el) rowRefs.current.set(f.id, el)
                else rowRefs.current.delete(f.id)
              }}
            >
              <FacilityRow
                facility={f}
                isSelected={selectedId === f.id}
                onClick={() => handleRowClick(f)}
              />
            </div>
          ))
        )}
      </div>

      {/* ── 페이지네이션 ──────────────────────────────────── */}
      {totalPages > 1 && (
        <div
          className="flex items-center justify-center gap-1 px-4 py-2
                     border-t border-[var(--border-default)] flex-shrink-0"
        >
          <button
            onClick={() => setPage(Math.max(1, page - 1))}
            disabled={page === 1}
            className="p-1.5 rounded text-[var(--text-secondary)] hover:text-[var(--text-primary)]
                       disabled:opacity-30 disabled:cursor-not-allowed"
            aria-label="이전 페이지"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
            </svg>
          </button>

          {/* 페이지 번호 버튼 (최대 5개 표시) */}
          {Array.from({ length: Math.min(totalPages, 5) }, (_, i) => {
            let p: number
            if (totalPages <= 5) {
              p = i + 1
            } else if (page <= 3) {
              p = i + 1
            } else if (page >= totalPages - 2) {
              p = totalPages - 4 + i
            } else {
              p = page - 2 + i
            }
            return (
              <button
                key={p}
                onClick={() => setPage(p)}
                className={`w-7 h-7 rounded text-xs font-medium transition-colors
                            ${page === p
                              ? 'bg-[var(--accent-primary)] text-white'
                              : 'text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)]'
                            }`}
              >
                {p}
              </button>
            )
          })}

          <button
            onClick={() => setPage(Math.min(totalPages, page + 1))}
            disabled={page === totalPages}
            className="p-1.5 rounded text-[var(--text-secondary)] hover:text-[var(--text-primary)]
                       disabled:opacity-30 disabled:cursor-not-allowed"
            aria-label="다음 페이지"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
            </svg>
          </button>
        </div>
      )}
    </div>
  )
}
