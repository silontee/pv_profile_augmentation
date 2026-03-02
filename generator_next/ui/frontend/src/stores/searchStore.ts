// ============================================================
// 검색 상태 Zustand 스토어
// - 검색 쿼리, 필터, 결과, 페이지네이션
// ============================================================

import { create } from 'zustand'
import type { Facility, FacilityStatus } from '../types'

interface SearchState {
  /** 텍스트 검색어 */
  query: string
  /** 상태 필터 (빈 문자열 = 전체) */
  status: FacilityStatus | ''
  /** 설비용량 범위 [min, max] kW */
  capRange: [number, number]
  /** 설치연도 범위 [min, max] */
  yearRange: [number, number]
  /** 현재 페이지 (1-based) */
  page: number
  /** 검색 결과 목록 */
  results: Facility[]
  /** 전체 결과 수 */
  total: number
  /** 로딩 중 여부 */
  loading: boolean

  // 액션
  setQuery: (q: string) => void
  setStatus: (s: FacilityStatus | '') => void
  setCapRange: (r: [number, number]) => void
  setYearRange: (r: [number, number]) => void
  setPage: (p: number) => void
  setResults: (items: Facility[], total: number) => void
  setLoading: (v: boolean) => void
  /** 필터 초기화 */
  resetFilters: () => void
}

const DEFAULT_CAP_RANGE: [number, number]  = [0, 1000]
const DEFAULT_YEAR_RANGE: [number, number] = [2008, 2025]

export const useSearchStore = create<SearchState>((set) => ({
  query:     '',
  status:    '',
  capRange:  DEFAULT_CAP_RANGE,
  yearRange: DEFAULT_YEAR_RANGE,
  page:      1,
  results:   [],
  total:     0,
  loading:   false,

  setQuery:    (q) => set({ query: q, page: 1 }),
  setStatus:   (s) => set({ status: s, page: 1 }),
  setCapRange: (r) => set({ capRange: r, page: 1 }),
  setYearRange:(r) => set({ yearRange: r, page: 1 }),
  setPage:     (p) => set({ page: p }),
  setResults:  (items, total) => set({ results: items, total }),
  setLoading:  (v) => set({ loading: v }),

  resetFilters: () =>
    set({
      query:     '',
      status:    '',
      capRange:  DEFAULT_CAP_RANGE,
      yearRange: DEFAULT_YEAR_RANGE,
      page:      1,
    }),
}))
