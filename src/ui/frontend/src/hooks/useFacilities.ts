// ============================================================
// bbox 기반 발전소 조회 훅
// - 지도 뷰포트(bbox) 변경 시 자동 호출
// - zoom < 10: 클러스터, zoom ≥ 10: 개별 마커
// ============================================================

import { useState, useEffect, useRef } from 'react'
import { useMapStore } from '../stores/mapStore'
import { useUiStore } from '../stores/uiStore'
import { useSearchStore } from '../stores/searchStore'
import { fetchBbox, fetchClusters } from '../api/facilities'
import type { Facility, ClusterItem } from '../types'

/** bbox가 의미있는 크기인지 검사 */
function isValidBbox(bbox: { xmin: number; ymin: number; xmax: number; ymax: number } | null): boolean {
  if (!bbox) return false
  return (
    bbox.xmax > bbox.xmin &&
    bbox.ymax > bbox.ymin &&
    // 지구 좌표 범위 초과 방지
    bbox.xmin >= -180 && bbox.xmax <= 180 &&
    bbox.ymin >= -90  && bbox.ymax <= 90
  )
}

interface UseFacilitiesReturn {
  /** 개별 마커 목록 (zoom ≥ 10) */
  markers: Facility[]
  /** 클러스터 목록 (zoom < 10) */
  clusters: ClusterItem[]
  loading: boolean
  error: string | null
}

const CLUSTER_ZOOM_THRESHOLD = 10

export function useFacilities(): UseFacilitiesReturn {
  const bbox       = useMapStore((s) => s.viewport.bbox)
  const zoom       = useMapStore((s) => s.viewport.zoom)
  const setDbError = useUiStore((s) => s.setDbError)

  const capRange  = useSearchStore((s) => s.capRange)
  const yearRange = useSearchStore((s) => s.yearRange)
  const status    = useSearchStore((s) => s.status)

  const [markers,  setMarkers]  = useState<Facility[]>([])
  const [clusters, setClusters] = useState<ClusterItem[]>([])
  const [loading,  setLoading]  = useState(false)
  const [error,    setError]    = useState<string | null>(null)

  // 이전 요청 취소용
  const abortRef = useRef<AbortController | null>(null)

  useEffect(() => {
    const isCluster = zoom < CLUSTER_ZOOM_THRESHOLD

    // 개별 마커 모드: bbox 필요
    if (!isCluster && !isValidBbox(bbox)) return

    // 이전 요청 취소
    abortRef.current?.abort()
    abortRef.current = new AbortController()

    setLoading(true)
    setError(null)

    const load = async () => {
      try {
        const filterOpts = {
          status:   status   || undefined,
          cap_min:  capRange[0],
          cap_max:  capRange[1],
          year_min: yearRange[0],
          year_max: yearRange[1],
        }

        if (isCluster) {
          // zoom < 10: 시군구 집계 클러스터
          const data = await fetchClusters(filterOpts)
          setClusters(data)
          setMarkers([])
        } else if (bbox) {
          // zoom ≥ 10: 개별 마커
          const data = await fetchBbox(bbox, filterOpts)
          setMarkers(data)
          setClusters([])
        }
        setDbError(false)
      } catch (err) {
        if (err instanceof Error && err.name === 'AbortError') return
        const e = err as Error & { status?: number }
        if (e.status === 503) {
          setDbError(true)
        }
        setError(e.message ?? '데이터 로드 실패')
      } finally {
        setLoading(false)
      }
    }

    void load()

    return () => {
      abortRef.current?.abort()
    }
  }, [bbox, zoom, setDbError, status, capRange, yearRange])

  return { markers, clusters, loading, error }
}
