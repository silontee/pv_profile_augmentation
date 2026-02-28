// ============================================================
// MapLibre GL JS 초기화 훅
// - 지도 인스턴스 생성 및 정리
// - zoom 기반 레이어 전환 (< 10: 클러스터, ≥ 10: 개별 마커)
// - 뷰포트 변경 시 mapStore 갱신
// ============================================================

import { useEffect, useRef, useState, useCallback } from 'react'
import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { useMapStore } from '../stores/mapStore'
import type { BboxParams } from '../types'

/** zoom < 10 임계값 */
const CLUSTER_ZOOM_THRESHOLD = 10

interface UseMapReturn {
  mapRef: React.RefObject<HTMLDivElement>
  map: maplibregl.Map | null
  /** 현재 zoom level */
  zoom: number
  /** 클러스터 모드 여부 */
  isClusterMode: boolean
  /** 특정 위치로 fly-to */
  flyTo: (lng: number, lat: number, targetZoom?: number) => void
}

export function useMap(): UseMapReturn {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapInstance = useRef<maplibregl.Map | null>(null)
  const [zoom, setZoom] = useState(7)
  const setViewport = useMapStore((s) => s.setViewport)
  const setBbox    = useMapStore((s) => s.setBbox)

  /** bbox 계산 헬퍼 */
  const extractBbox = useCallback((m: maplibregl.Map): BboxParams => {
    const b = m.getBounds()
    return {
      xmin: b.getWest(),
      ymin: b.getSouth(),
      xmax: b.getEast(),
      ymax: b.getNorth(),
    }
  }, [])

  useEffect(() => {
    if (!containerRef.current || mapInstance.current) return

    const map = new maplibregl.Map({
      container: containerRef.current,
      // CARTO 다크 매터 무료 벡터 타일 스타일
      style: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
      center: [127.5, 36.5],  // 한국 중심
      zoom: 7,
      attributionControl: false,
    })

    // 기본 컨트롤 (확대/축소)
    map.addControl(new maplibregl.NavigationControl(), 'bottom-right')
    // 간략 저작권 표시
    map.addControl(
      new maplibregl.AttributionControl({ compact: true }),
      'bottom-left',
    )

    // 지도 이동/줌 변경 시 상태 동기화
    const onMove = () => {
      const c = map.getCenter()
      const z = map.getZoom()
      setZoom(z)
      setViewport({ center: [c.lng, c.lat], zoom: z })
      setBbox(extractBbox(map))
    }

    map.on('load', onMove)
    map.on('moveend', onMove)
    map.on('zoomend', onMove)

    mapInstance.current = map

    // 컴포넌트 언마운트 시 지도 정리
    return () => {
      map.remove()
      mapInstance.current = null
    }
  }, [setViewport, setBbox, extractBbox])

  /** 특정 좌표로 fly-to 애니메이션 */
  const flyTo = useCallback(
    (lng: number, lat: number, targetZoom = 15) => {
      mapInstance.current?.flyTo({
        center: [lng, lat],
        zoom: targetZoom,
        duration: 1200,
        essential: true,
      })
    },
    [],
  )

  return {
    mapRef: containerRef,
    map: mapInstance.current,
    zoom,
    isClusterMode: zoom < CLUSTER_ZOOM_THRESHOLD,
    flyTo,
  }
}
