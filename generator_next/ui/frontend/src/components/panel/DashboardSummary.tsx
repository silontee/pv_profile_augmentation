// ============================================================
// 대시보드 요약 통계 카드
// 총 발전소 수 / 총 설비용량 / 좌표 보유율 / 시군구 수
// ============================================================

import React, { useEffect, useState } from 'react'
import { fetchStats } from '../../api/stats'
import { useUiStore } from '../../stores/uiStore'
import type { Stats } from '../../types'

const fmt = (n: number) => n.toLocaleString('ko-KR')

interface StatCardProps {
  label: string
  value: string
  sub?: string
  color?: string
}

const StatCard: React.FC<StatCardProps> = ({ label, value, sub, color }) => (
  <div
    className="flex-1 min-w-0 p-3 rounded-lg bg-[var(--bg-tertiary)]
               border border-[var(--border-default)]"
  >
    <p className="text-[10px] text-[var(--text-muted)] uppercase tracking-wide mb-1">
      {label}
    </p>
    <p
      className="text-lg font-bold leading-tight truncate"
      style={{ color: color ?? 'var(--text-primary)' }}
    >
      {value}
    </p>
    {sub && (
      <p className="text-[10px] text-[var(--text-secondary)] mt-0.5">{sub}</p>
    )}
  </div>
)

export const DashboardSummary: React.FC = () => {
  const [stats,   setStats]   = useState<Stats | null>(null)
  const [loading, setLoading] = useState(true)
  const setDbError = useUiStore((s) => s.setDbError)

  useEffect(() => {
    fetchStats()
      .then((s) => {
        setStats(s)
        setDbError(false)
      })
      .catch((err: Error & { status?: number }) => {
        if (err.status === 503) setDbError(true)
      })
      .finally(() => setLoading(false))
  }, [setDbError])

  if (loading) {
    return (
      <div className="p-4 space-y-2">
        <div className="h-4 w-24 rounded bg-[var(--bg-elevated)] animate-pulse" />
        <div className="flex gap-2">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="flex-1 h-16 rounded-lg bg-[var(--bg-elevated)] animate-pulse" />
          ))}
        </div>
      </div>
    )
  }

  if (!stats) {
    return (
      <div className="p-4 text-sm text-[var(--text-muted)]">
        통계를 불러올 수 없습니다.
      </div>
    )
  }

  // 좌표 보유율 계산
  const coordRate = stats.total > 0
    ? ((stats.total - stats.no_coord) / stats.total * 100).toFixed(1)
    : '0.0'

  // 총 설비용량 (MW 단위)
  const totalMw = (stats.total_capacity_mw).toLocaleString('ko-KR', {
    maximumFractionDigits: 0,
  })

  return (
    <section className="p-4 border-b border-[var(--border-default)]">
      <h2 className="text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wide mb-3">
        대시보드 요약
      </h2>

      {/* 상단 2개 카드 */}
      <div className="flex gap-2 mb-2">
        <StatCard
          label="총 발전소"
          value={`${fmt(stats.total)}개`}
        />
        <StatCard
          label="총 설비용량"
          value={`${totalMw} MW`}
        />
      </div>

      {/* 하단 2개 카드 */}
      <div className="flex gap-2 mb-3">
        <StatCard
          label="좌표 보유"
          value={`${fmt(stats.total - stats.no_coord)}건`}
          sub={`전체의 ${coordRate}%`}
          color="var(--status-active)"
        />
        <StatCard
          label="시군구 수"
          value={`${fmt(stats.sigungu_count)}개`}
        />
      </div>

      {/* 좌표 결측 뱃지 */}
      {stats.no_coord > 0 && (
        <div
          className="flex items-center gap-2 px-3 py-2 rounded-lg
                     bg-[var(--status-no-coord)]/10 border border-[var(--status-no-coord)]/20"
        >
          <span
            className="w-2 h-2 rounded-full flex-shrink-0"
            style={{ backgroundColor: 'var(--status-no-coord)' }}
          />
          <span className="text-xs text-[var(--status-no-coord)]">
            좌표 결측 <strong>{fmt(stats.no_coord)}건</strong>
            {' '}— 리스트에만 표시, 지도 제외
          </span>
        </div>
      )}
    </section>
  )
}
