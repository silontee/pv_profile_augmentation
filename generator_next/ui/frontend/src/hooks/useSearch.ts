// ============================================================
// 검색 훅
// - debounce 300ms: query/필터 변경 후 300ms 대기 후 API 호출
// - 검색어/필터/페이지 변경 시 자동 API 호출
// ============================================================

import { useEffect, useRef } from 'react'
import { useSearchStore } from '../stores/searchStore'
import { useUiStore } from '../stores/uiStore'
import { fetchFacilities } from '../api/facilities'

export function useSearch() {
  const {
    query, status, capRange, yearRange, page,
    setResults, setLoading,
  } = useSearchStore()
  const setDbError = useUiStore((s) => s.setDbError)

  // debounce 타이머
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // 최신 파라미터를 ref로 보관 (타이머 클로저에서 stale state 방지)
  const paramsRef = useRef({ query, status, capRange, yearRange, page })
  paramsRef.current = { query, status, capRange, yearRange, page }

  useEffect(() => {
    // 이전 타이머 취소
    if (timerRef.current) clearTimeout(timerRef.current)

    // 300ms debounce
    timerRef.current = setTimeout(() => {
      const p = paramsRef.current
      setLoading(true)

      fetchFacilities({
        q:         p.query || undefined,
        status:    p.status || undefined,
        cap_min:   p.capRange[0],
        cap_max:   p.capRange[1],
        year_min:  p.yearRange[0],
        year_max:  p.yearRange[1],
        page:      p.page,
        per_page: 50,
      })
        .then((res) => {
          setResults(res.items, res.total)
          setDbError(false)
        })
        .catch((err: Error & { status?: number }) => {
          if (err.status === 503) setDbError(true)
          setResults([], 0)
        })
        .finally(() => {
          setLoading(false)
        })
    }, 300)

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current)
    }
  }, [query, status, capRange, yearRange, page, setResults, setLoading, setDbError])
}
