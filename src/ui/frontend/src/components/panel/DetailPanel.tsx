// ============================================================
// 발전소 상세 패널
// - 기본 정보 / 위치 정보 / 허가 정보 / 주변 정보 (PostGIS)
// - 좌표 결측 시 NoCoordNotice 표시
// ============================================================

import React, { useEffect, useState } from 'react'
import { useMapStore } from '../../stores/mapStore'
import { useUiStore } from '../../stores/uiStore'
import { fetchFacility, fetchNearby } from '../../api/facilities'
import { StatusBadge } from '../common/StatusBadge'
import type { Facility, NearbyFacility } from '../../types'

const fmt = (n: number | null | undefined, unit = '') =>
  n !== null && n !== undefined ? `${n.toLocaleString('ko-KR')}${unit}` : '-'

// ─── 정보 행 컴포넌트 ─────────────────────────────────────────

const InfoRow: React.FC<{ label: string; value: React.ReactNode }> = ({ label, value }) => (
  <div className="flex gap-3 py-1.5">
    <span className="text-xs text-[var(--text-muted)] w-20 flex-shrink-0">{label}</span>
    <span className="text-xs text-[var(--text-primary)] flex-1">{value ?? '-'}</span>
  </div>
)

// ─── 좌표 결측 안내 ───────────────────────────────────────────

const NoCoordNotice: React.FC<{ addrRoad?: string | null }> = ({ addrRoad }) => (
  <div
    className="mx-4 mb-3 p-3 rounded-lg
               bg-[var(--status-no-coord)]/10 border border-[var(--status-no-coord)]/30"
  >
    <div className="flex items-center gap-2 mb-1">
      <svg className="w-4 h-4 text-[var(--status-no-coord)] flex-shrink-0"
        fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round"
          d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
      </svg>
      <p className="text-xs font-medium text-[var(--status-no-coord)]">
        지도 위치 미확인
      </p>
    </div>
    <p className="text-[10px] text-[var(--text-secondary)] leading-relaxed">
      이 발전소는 좌표 정보가 없어 지도에 표시되지 않습니다.
    </p>
    {addrRoad && (
      <a
        href={`https://map.kakao.com/link/search/${encodeURIComponent(addrRoad)}`}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center gap-1 mt-2 text-[10px]
                   text-[var(--accent-primary)] hover:text-[var(--accent-hover)]"
      >
        카카오맵에서 주소 검색
        <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round"
            d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
        </svg>
      </a>
    )}
  </div>
)

// ─── 주변 정보 섹션 ───────────────────────────────────────────

const NearbySection: React.FC<{ facility: Facility }> = ({ facility }) => {
  const [nearby,  setNearby]  = useState<NearbyFacility[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!facility.has_coord || !facility.lng || !facility.lat) return
    setLoading(true)
    fetchNearby(facility.lng, facility.lat, 5000)
      .then((data) => {
        // 자기 자신 제외
        setNearby(data.filter((f) => f.id !== facility.id).slice(0, 5))
      })
      .catch(() => setNearby([]))
      .finally(() => setLoading(false))
  }, [facility.id, facility.has_coord, facility.lng, facility.lat])

  if (!facility.has_coord) return null

  return (
    <div className="px-4 pb-4">
      <h3 className="text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-wide mb-2">
        주변 정보 (반경 5km)
      </h3>
      {loading ? (
        <div className="h-8 rounded bg-[var(--bg-elevated)] animate-pulse" />
      ) : (
        <div className="space-y-1">
          <InfoRow
            label="주변 발전소"
            value={`${nearby.length}개`}
          />
          {nearby.slice(0, 3).map((f) => (
            <div key={f.id} className="ml-20 text-[10px] text-[var(--text-secondary)] truncate">
              {f.name} ({(f.dist_m / 1000).toFixed(1)}km)
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ─── DetailPanel 메인 ─────────────────────────────────────────

export const DetailPanel: React.FC = () => {
  const selectedId       = useMapStore((s) => s.selectedId)
  const setSelectedId    = useMapStore((s) => s.setSelectedId)
  const setHighlightedId = useMapStore((s) => s.setHighlightedId)
  const setPanelMode     = useUiStore((s) => s.setPanelMode)
  const setDbError       = useUiStore((s) => s.setDbError)

  const [facility, setFacility] = useState<Facility | null>(null)
  const [loading,  setLoading]  = useState(false)
  const [error,    setError]    = useState<string | null>(null)

  useEffect(() => {
    if (!selectedId) return
    setLoading(true)
    setError(null)

    fetchFacility(selectedId)
      .then((f) => {
        setFacility(f)
        setDbError(false)
      })
      .catch((err: Error & { status?: number }) => {
        if (err.status === 503) setDbError(true)
        setError('발전소 정보를 불러올 수 없습니다.')
      })
      .finally(() => setLoading(false))
  }, [selectedId, setDbError])

  /** 뒤로 (검색 패널으로 복귀) */
  const handleBack = () => {
    setPanelMode('search')
    setSelectedId(null)
    setHighlightedId(null)
  }

  /** 지도에서 보기 */
  const handleViewOnMap = () => {
    if (!facility?.has_coord || !facility.lng || !facility.lat) return
    const flyTo = (window as Window & { __mapFlyTo?: (lng: number, lat: number, zoom?: number) => void }).__mapFlyTo
    flyTo?.(facility.lng, facility.lat, 15)
  }

  if (loading) {
    return (
      <div className="flex flex-col h-full">
        <div className="flex items-center px-4 py-3 border-b border-[var(--border-default)] gap-2">
          <button onClick={handleBack} className="text-[var(--text-secondary)] hover:text-[var(--text-primary)] p-1">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
            </svg>
          </button>
          <span className="text-sm text-[var(--text-secondary)]">로드 중...</span>
        </div>
        <div className="p-4 space-y-3">
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="h-5 rounded bg-[var(--bg-elevated)] animate-pulse" />
          ))}
        </div>
      </div>
    )
  }

  if (error || !facility) {
    return (
      <div className="flex flex-col h-full">
        <div className="flex items-center px-4 py-3 border-b border-[var(--border-default)] gap-2">
          <button onClick={handleBack} className="text-[var(--text-secondary)] hover:text-[var(--text-primary)] p-1">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
            </svg>
          </button>
        </div>
        <div className="flex-1 flex items-center justify-center text-sm text-[var(--text-muted)] p-4 text-center">
          {error ?? '발전소를 선택해주세요.'}
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full overflow-y-auto">
      {/* ── 헤더 ────────────────────────────────────────── */}
      <div
        className="flex items-center justify-between px-4 py-3
                   border-b border-[var(--border-default)] flex-shrink-0"
      >
        <button
          onClick={handleBack}
          className="flex items-center gap-1.5 text-xs text-[var(--text-secondary)]
                     hover:text-[var(--text-primary)] transition-colors"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
          </svg>
          뒤로
        </button>
        <button
          onClick={() => {
            setSelectedId(null)
            setHighlightedId(null)
            setPanelMode('search')
          }}
          className="p-1 text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors"
          aria-label="패널 닫기"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      {/* ── 시설명 + 상태 ───────────────────────────────── */}
      <div className="px-4 py-4 border-b border-[var(--border-default)]">
        <div className="flex items-start justify-between gap-2 mb-1">
          <h2 className="text-sm font-bold text-[var(--text-primary)] leading-tight">
            {facility.name ?? '(이름 없음)'}
          </h2>
          <StatusBadge status={facility.status} />
        </div>
        {facility.permit_org && (
          <p className="text-xs text-[var(--text-muted)]">{facility.permit_org}</p>
        )}
      </div>

      {/* ── 좌표 결측 안내 ──────────────────────────────── */}
      {!facility.has_coord && (
        <div className="pt-3">
          <NoCoordNotice addrRoad={facility.addr_road} />
        </div>
      )}

      {/* ── 기본 정보 ───────────────────────────────────── */}
      <div className="px-4 py-3 border-b border-[var(--border-default)]">
        <h3 className="text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-wide mb-2">
          기본 정보
        </h3>
        <InfoRow label="설비용량"   value={fmt(facility.capacity_kw, ' kW')} />
        <InfoRow label="공급전압"   value={facility.voltage ? `${facility.voltage} V` : '-'} />
        <InfoRow label="주파수"     value={facility.frequency ? `${facility.frequency} Hz` : '-'} />
        <InfoRow label="세부용도"   value={facility.usage_detail} />
      </div>

      {/* ── 위치 정보 ───────────────────────────────────── */}
      <div className="px-4 py-3 border-b border-[var(--border-default)]">
        <h3 className="text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-wide mb-2">
          위치 정보
        </h3>
        <InfoRow label="도로명주소" value={facility.addr_road} />
        <InfoRow label="지번주소"   value={facility.addr_jibun} />
        <InfoRow
          label="좌표"
          value={
            facility.has_coord && facility.lat !== null && facility.lng !== null
              ? `${facility.lat.toFixed(4)}, ${facility.lng.toFixed(4)}`
              : null
          }
        />
        <InfoRow label="설치위치"   value={facility.install_type} />
      </div>

      {/* ── 허가 정보 ───────────────────────────────────── */}
      <div className="px-4 py-3 border-b border-[var(--border-default)]">
        <h3 className="text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-wide mb-2">
          허가 정보
        </h3>
        <InfoRow label="허가일자"   value={facility.permit_date} />
        <InfoRow label="허가기관"   value={facility.permit_org} />
        <InfoRow label="설치연도"   value={facility.install_year ? `${facility.install_year}년` : null} />
        <InfoRow label="설치면적"   value={fmt(facility.install_area_m2, ' m²')} />
        <InfoRow label="데이터 기준" value={facility.data_date} />
      </div>

      {/* ── 주변 정보 ───────────────────────────────────── */}
      <div className="pt-3">
        <NearbySection facility={facility} />
      </div>

      {/* ── 액션 버튼 ───────────────────────────────────── */}
      <div className="px-4 pb-4 flex gap-2 mt-auto">
        {facility.has_coord && (
          <button
            onClick={handleViewOnMap}
            className="flex-1 py-2 rounded-lg text-xs font-medium
                       bg-[var(--accent-primary)] text-white
                       hover:bg-[var(--accent-hover)] transition-colors"
          >
            지도에서 보기
          </button>
        )}
        <button
          onClick={() => {
            // 주변 검색: 검색 패널로 이동 후 반경 검색 트리거
            setPanelMode('search')
          }}
          className="flex-1 py-2 rounded-lg text-xs font-medium
                     bg-[var(--bg-elevated)] text-[var(--text-secondary)]
                     border border-[var(--border-default)]
                     hover:border-[var(--border-hover)] transition-colors"
        >
          주변 검색 확장
        </button>
      </div>
    </div>
  )
}
