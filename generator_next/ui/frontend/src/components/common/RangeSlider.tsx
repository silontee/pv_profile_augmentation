// ============================================================
// 듀얼 핸들 범위 슬라이더
// - 포인터 이벤트 기반 드래그 (두 핸들 모두 정상 작동)
// - onChangeCommitted: 손 뗄 때만 호출 → 검색 API 최소화
// ============================================================

import React, { useRef, useState, useEffect, useCallback } from 'react'

interface RangeSliderProps {
  label: string
  min: number
  max: number
  value: [number, number]
  /** 드래그 중 즉시 호출 (표시값 동기화용) — 생략 가능 */
  onChange?: (value: [number, number]) => void
  /** 손 뗄 때만 호출 (API 검색 트리거용) */
  onChangeCommitted: (value: [number, number]) => void
  unit?: string
  step?: number
}

export const RangeSlider: React.FC<RangeSliderProps> = ({
  label,
  min,
  max,
  value,
  onChange,
  onChangeCommitted,
  unit = '',
  step = 1,
}) => {
  // 드래그 중 시각적 피드백용 로컬 상태
  const [local, setLocal] = useState<[number, number]>(value)
  // 부모 value가 외부에서 변경될 때 동기화
  const prevValue = useRef(value)
  if (prevValue.current[0] !== value[0] || prevValue.current[1] !== value[1]) {
    prevValue.current = value
    setLocal(value)
  }

  const trackRef  = useRef<HTMLDivElement>(null)
  const dragging  = useRef<'lo' | 'hi' | null>(null)
  const localRef  = useRef(local)
  localRef.current = local

  const snap = useCallback(
    (raw: number) => Math.round(raw / step) * step,
    [step],
  )

  const valueFromPointer = useCallback(
    (clientX: number): number => {
      const rect = trackRef.current!.getBoundingClientRect()
      const pct  = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width))
      return snap(min + pct * (max - min))
    },
    [min, max, snap],
  )

  const applyDrag = useCallback(
    (clientX: number) => {
      if (!dragging.current) return
      const val  = valueFromPointer(clientX)
      const [lo, hi] = localRef.current

      let next: [number, number]
      if (dragging.current === 'lo') {
        next = [Math.max(min, Math.min(val, hi - step)), hi]
      } else {
        next = [lo, Math.min(max, Math.max(val, lo + step))]
      }
      setLocal(next)
      onChange?.(next)
    },
    [valueFromPointer, min, max, step, onChange],
  )

  const handlePointerDown = useCallback(
    (e: React.PointerEvent<HTMLDivElement>) => {
      e.preventDefault()
      const val  = valueFromPointer(e.clientX)
      const [lo, hi] = localRef.current
      // 클릭 지점이 lo/hi 중 더 가까운 핸들 선택
      dragging.current = Math.abs(val - lo) <= Math.abs(val - hi) ? 'lo' : 'hi'
      ;(e.currentTarget as HTMLDivElement).setPointerCapture(e.pointerId)
      applyDrag(e.clientX)
    },
    [valueFromPointer, applyDrag],
  )

  const handlePointerMove = useCallback(
    (e: React.PointerEvent<HTMLDivElement>) => {
      if (!dragging.current) return
      applyDrag(e.clientX)
    },
    [applyDrag],
  )

  const handlePointerUp = useCallback(() => {
    if (!dragging.current) return
    dragging.current = null
    onChangeCommitted(localRef.current)
  }, [onChangeCommitted])

  const [lo, hi] = local
  const pctLo = ((lo - min) / (max - min)) * 100
  const pctHi = ((hi - min) / (max - min)) * 100

  return (
    <div className="space-y-2">
      {/* 레이블 + 현재값 */}
      <div className="flex justify-between items-center">
        <span className="text-xs text-[var(--text-secondary)]">{label}</span>
        <span className="text-xs text-[var(--text-primary)] font-medium tabular-nums">
          {lo.toLocaleString()}{unit} — {hi.toLocaleString()}{unit}
        </span>
      </div>

      {/* 트랙 + 핸들 */}
      <div
        ref={trackRef}
        className="relative h-5 flex items-center cursor-pointer select-none"
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerCancel={handlePointerUp}
      >
        {/* 배경 트랙 */}
        <div className="absolute inset-x-0 h-1.5 rounded-full bg-[var(--bg-tertiary)]" />
        {/* 선택 범위 채움 */}
        <div
          className="absolute h-1.5 rounded-full bg-[var(--accent-primary)]"
          style={{ left: `${pctLo}%`, right: `${100 - pctHi}%` }}
        />
        {/* Lo 핸들 */}
        <div
          className="absolute w-4 h-4 rounded-full bg-[var(--accent-primary)]
                     border-2 border-white shadow-md pointer-events-none"
          style={{ left: `calc(${pctLo}% - 8px)` }}
        />
        {/* Hi 핸들 */}
        <div
          className="absolute w-4 h-4 rounded-full bg-[var(--accent-primary)]
                     border-2 border-white shadow-md pointer-events-none"
          style={{ left: `calc(${pctHi}% - 8px)` }}
        />
      </div>

      {/* 최솟값 / 최댓값 힌트 */}
      <div className="flex justify-between text-[10px] text-[var(--text-muted)] tabular-nums">
        <span>{min.toLocaleString()}{unit}</span>
        <span>{max.toLocaleString()}{unit}</span>
      </div>
    </div>
  )
}
