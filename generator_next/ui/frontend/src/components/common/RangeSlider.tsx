// ============================================================
// 범위 슬라이더 컴포넌트 (용량·연도 필터용)
// min/max 두 개의 input[type=range] 조합
// ============================================================

import React, { useId } from 'react'

interface RangeSliderProps {
  /** 슬라이더 레이블 */
  label: string
  /** 절댓값 최솟값 */
  min: number
  /** 절댓값 최댓값 */
  max: number
  /** 현재 선택 범위 */
  value: [number, number]
  /** 값 변경 콜백 */
  onChange: (value: [number, number]) => void
  /** 단위 (예: 'kW', '년') */
  unit?: string
  /** 슬라이더 스텝 */
  step?: number
}

export const RangeSlider: React.FC<RangeSliderProps> = ({
  label,
  min,
  max,
  value,
  onChange,
  unit = '',
  step = 1,
}) => {
  const id = useId()
  const [lo, hi] = value

  const handleMin = (e: React.ChangeEvent<HTMLInputElement>) => {
    const v = Number(e.target.value)
    // min이 max를 초과하지 않도록
    onChange([Math.min(v, hi - step), hi])
  }

  const handleMax = (e: React.ChangeEvent<HTMLInputElement>) => {
    const v = Number(e.target.value)
    onChange([lo, Math.max(v, lo + step)])
  }

  return (
    <div className="space-y-1.5">
      <div className="flex justify-between items-center">
        <label
          htmlFor={`${id}-min`}
          className="text-xs text-[var(--text-secondary)]"
        >
          {label}
        </label>
        <span className="text-xs text-[var(--text-primary)] font-medium tabular-nums">
          {lo.toLocaleString()}{unit} — {hi.toLocaleString()}{unit}
        </span>
      </div>

      <div className="relative flex flex-col gap-1">
        {/* 최솟값 슬라이더 */}
        <input
          id={`${id}-min`}
          type="range"
          min={min}
          max={max}
          step={step}
          value={lo}
          onChange={handleMin}
          className="w-full"
          aria-label={`${label} 최솟값`}
        />
        {/* 최댓값 슬라이더 */}
        <input
          id={`${id}-max`}
          type="range"
          min={min}
          max={max}
          step={step}
          value={hi}
          onChange={handleMax}
          className="w-full"
          aria-label={`${label} 최댓값`}
        />
      </div>
    </div>
  )
}
