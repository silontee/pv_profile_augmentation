// ============================================================
// MapLibre GL JS 메인 지도 컴포넌트
// - zoom < 10: 클러스터(시군구 집계 원형) 표시
// - zoom ≥ 10: 개별 CircleMarker 표시
// - 클릭 이벤트 → 하이라이트 + DetailPanel 전환
// ============================================================

import React, { useEffect, useRef, useCallback, useState } from 'react'
import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { useMapStore } from '../../stores/mapStore'
import { useUiStore } from '../../stores/uiStore'
import { useFacilities } from '../../hooks/useFacilities'
import { fetchFacility } from '../../api/facilities'
import { fetchSubstationsBbox, fetchPowerLinesBbox } from '../../api/infra'
import { LayerToggle } from './LayerToggle'
import { LandcoverLegend } from './LandcoverLegend'
import type { Facility, ClusterItem, Substation, PowerLine } from '../../types'

// ─── MapTiler ───────────────────────────────────────────────
const MAPTILER_KEY = import.meta.env.VITE_MAPTILER_KEY

// ─── 색상 상수 ──────────────────────────────────────────────
const COLOR = {
  active:     '#2ecc71',
  stopped:    '#95a5a6',
  retired:    '#4a5568',
  highlight:  '#ffffff',
  cluster:    '#6366f1',
  substation: '#3498db',
  powerline:  '#e67e22',
} as const

const CLUSTER_ZOOM = 10  // zoom < 10: 클러스터 모드

// ─── 소스/레이어 ID 상수 ────────────────────────────────────
const SRC_MARKERS        = 'pv-markers'
const SRC_CLUSTERS       = 'pv-clusters'
const SRC_SUBSTATIONS    = 'infra-substations'
const SRC_POWERLINES     = 'infra-powerlines'
const SRC_TERRAIN        = 'maptiler-terrain'
const SRC_LANDCOVER_VEC  = 'landcover-vec'
const LYR_HILLSHADE      = 'lyr-hillshade'
const LYR_LANDCOVER_VEC  = 'lyr-landcover-vec'
const LYR_MARKERS          = 'pv-marker-layer'
const LYR_CLUSTERS_ACTIVE  = 'pv-cluster-active'
const LYR_CLUSTERS_STOPPED = 'pv-cluster-stopped'
const LYR_CLUSTERS_RETIRED = 'pv-cluster-retired'
const LYR_CLUSTER_COUNT    = 'pv-cluster-count'
const LYR_SUBSTATIONS = 'infra-substation-layer'
const LYR_POWERLINES  = 'infra-powerline-layer'

// 모든 클러스터 레이어 목록 (visibility 일괄 제어용)
const ALL_CLUSTER_LYRS = [LYR_CLUSTERS_ACTIVE, LYR_CLUSTERS_STOPPED, LYR_CLUSTERS_RETIRED, LYR_CLUSTER_COUNT]

// ─── GeoJSON 변환 헬퍼 ──────────────────────────────────────
function markersToGeoJSON(markers: Facility[]): GeoJSON.FeatureCollection {
  return {
    type: 'FeatureCollection',
    features: markers
      .filter((f) => f.lng != null && f.lat != null)
      .map((f) => ({
        type: 'Feature' as const,
        geometry: {
          type: 'Point' as const,
          coordinates: [f.lng!, f.lat!],
        },
        properties: {
          id:       f.id,
          name:     f.name,
          status:   f.status,
          capacity: f.capacity_kw,
        },
      })),
  }
}

function substationsToGeoJSON(subs: Substation[]): GeoJSON.FeatureCollection {
  return {
    type: 'FeatureCollection',
    features: subs.map((s) => ({
      type: 'Feature' as const,
      geometry: { type: 'Point' as const, coordinates: [s.lng, s.lat] },
      properties: { id: s.id, name: s.name, voltage: s.voltage },
    })),
  }
}

function powerlinesToGeoJSON(lines: PowerLine[]): GeoJSON.FeatureCollection {
  return {
    type: 'FeatureCollection',
    features: lines.map((l) => ({
      type: 'Feature' as const,
      geometry: { type: 'LineString' as const, coordinates: l.coordinates },
      properties: { id: l.id, name: l.name, voltage: l.voltage, power_type: l.power_type },
    })),
  }
}

function clustersToGeoJSON(clusters: ClusterItem[]): GeoJSON.FeatureCollection {
  return {
    type: 'FeatureCollection',
    features: clusters.map((c) => ({
      type: 'Feature' as const,
      geometry: {
        type: 'Point' as const,
        coordinates: [c.center_lng, c.center_lat],
      },
      properties: {
        sigungu:     c.sigungu,
        cnt:         c.cnt,
        cnt_active:  c.cnt_active,
        cnt_stopped: c.cnt_stopped,
        cnt_retired: c.cnt_retired,
      },
    })),
  }
}

// ─── MapView 컴포넌트 ────────────────────────────────────────

export const MapView: React.FC = () => {
  const containerRef  = useRef<HTMLDivElement>(null)
  const mapRef        = useRef<maplibregl.Map | null>(null)
  const popupRef      = useRef<maplibregl.Popup | null>(null)
  const [mapLoaded, setMapLoaded] = useState(false)

  const setSelectedId    = useMapStore((s) => s.setSelectedId)
  const setHighlightedId = useMapStore((s) => s.setHighlightedId)
  const highlightedId    = useMapStore((s) => s.highlightedId)
  const viewport         = useMapStore((s) => s.viewport)
  const setBbox          = useMapStore((s) => s.setBbox)
  const setViewport      = useMapStore((s) => s.setViewport)

  const setPanelMode = useUiStore((s) => s.setPanelMode)
  const layers       = useUiStore((s) => s.layers)
  const setDbError   = useUiStore((s) => s.setDbError)

  // 토지피복 fetch AbortController + 최신 콜백 ref (stale closure 방지)
  const landcoverAbortRef       = useRef<AbortController | null>(null)
  const fetchLandcoverOnMoveRef = useRef<() => void>(() => {})

  const { markers, clusters } = useFacilities()

  // layers를 ref로 추적 — onMove 클로저에서 최신 값 접근용
  const layersRef = useRef(layers)
  useEffect(() => { layersRef.current = layers }, [layers])

  // ─── 지도 초기화 ──────────────────────────────────────────
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
      center: [127.5, 36.5],
      zoom: 7,
      attributionControl: false,
    })

    map.addControl(new maplibregl.NavigationControl(), 'bottom-right')
    map.addControl(new maplibregl.AttributionControl({ compact: true }), 'bottom-left')

    // 팝업 인스턴스 (마커 hover용)
    popupRef.current = new maplibregl.Popup({
      closeButton: false,
      closeOnClick: false,
      offset: 10,
    })

    map.on('load', () => {
      // ── MapTiler DEM 소스 (3D 지형·hillshade용) ──────────
      map.addSource(SRC_TERRAIN, {
        type: 'raster-dem',
        url: `https://api.maptiler.com/tiles/terrain-rgb-v2/tiles.json?key=${MAPTILER_KEY}`,
        tileSize: 256,
      })

      // ── hillshade 레이어 (3D 지형 음영 효과) ─────────────
      map.addLayer({
        id: LYR_HILLSHADE,
        type: 'hillshade',
        source: SRC_TERRAIN,
        layout: { visibility: 'none' },
        paint: {
          'hillshade-shadow-color': '#000000',
          'hillshade-highlight-color': '#ffffff',
          'hillshade-exaggeration': 0.5,
        },
      })

      // ── sky 대기층 ────────────────────────────────────────
      map.addLayer({
        id: 'sky',
        type: 'sky',
        paint: {
          'sky-type': 'atmosphere',
          'sky-atmosphere-sun': [0.0, 90.0],
          'sky-atmosphere-sun-intensity': 15,
        },
      } as maplibregl.LayerSpecification)

      // ── 토지피복 벡터 소스/레이어 ────────────────────────
      map.addSource(SRC_LANDCOVER_VEC, {
        type: 'geojson',
        data: { type: 'FeatureCollection', features: [] },
      })
      map.addLayer({
        id: LYR_LANDCOVER_VEC,
        type: 'fill',
        source: SRC_LANDCOVER_VEC,
        layout: { visibility: 'none' },
        paint: {
          'fill-color': ['get', 'color'],
          'fill-opacity': 0.45,
          'fill-outline-color': 'rgba(0,0,0,0.1)',
        },
      })

      // ── 개별 마커 소스/레이어 ─────────────────────────────
      map.addSource(SRC_MARKERS, {
        type: 'geojson',
        data: markersToGeoJSON([]),
      })

      map.addLayer({
        id: LYR_MARKERS,
        type: 'circle',
        source: SRC_MARKERS,
        layout: { visibility: 'none' },
        paint: {
          'circle-radius': [
            'case',
            ['boolean', ['feature-state', 'highlighted'], false], 9,
            6,
          ],
          'circle-color': [
            'match',
            ['get', 'status'],
            '정상가동', COLOR.active,
            '가동중단', COLOR.stopped,
            '폐기',     COLOR.retired,
            COLOR.stopped,
          ],
          'circle-stroke-width': [
            'case',
            ['boolean', ['feature-state', 'highlighted'], false], 2,
            0,
          ],
          'circle-stroke-color': COLOR.highlight,
          'circle-opacity': 0.9,
        },
      })

      // ── 클러스터 소스/레이어 (상태별 3개) ─────────────────
      map.addSource(SRC_CLUSTERS, {
        type: 'geojson',
        data: clustersToGeoJSON([]),
      })

      // 공통 반경 표현식 생성 헬퍼
      const clusterRadius = (field: string) => [
        'interpolate', ['linear'], ['get', field],
        1, 6, 50, 14, 500, 24, 5000, 38,
      ] as maplibregl.ExpressionSpecification

      // 정상가동 (초록) — 가장 먼저 그려 바닥에 위치
      map.addLayer({
        id: LYR_CLUSTERS_ACTIVE,
        type: 'circle',
        source: SRC_CLUSTERS,
        filter: ['>', ['get', 'cnt_active'], 0],
        layout: { visibility: 'visible' },
        paint: {
          'circle-radius': clusterRadius('cnt_active'),
          'circle-color': COLOR.active,
          'circle-opacity': 0.80,
          'circle-stroke-width': 1.5,
          'circle-stroke-color': '#27ae60',
        },
      })

      // 가동중단 (회색) — 중간 레이어
      map.addLayer({
        id: LYR_CLUSTERS_STOPPED,
        type: 'circle',
        source: SRC_CLUSTERS,
        filter: ['>', ['get', 'cnt_stopped'], 0],
        layout: { visibility: 'visible' },
        paint: {
          'circle-radius': clusterRadius('cnt_stopped'),
          'circle-color': COLOR.stopped,
          'circle-opacity': 0.85,
          'circle-stroke-width': 1.5,
          'circle-stroke-color': '#7f8c8d',
        },
      })

      // 폐기 (빨강) — 최상단
      map.addLayer({
        id: LYR_CLUSTERS_RETIRED,
        type: 'circle',
        source: SRC_CLUSTERS,
        filter: ['>', ['get', 'cnt_retired'], 0],
        layout: { visibility: 'visible' },
        paint: {
          'circle-radius': clusterRadius('cnt_retired'),
          'circle-color': '#e74c3c',
          'circle-opacity': 0.85,
          'circle-stroke-width': 1.5,
          'circle-stroke-color': '#c0392b',
        },
      })

      // 합계 숫자 텍스트
      map.addLayer({
        id: LYR_CLUSTER_COUNT,
        type: 'symbol',
        source: SRC_CLUSTERS,
        layout: {
          visibility: 'visible',
          'text-field': ['get', 'cnt'],
          'text-size': 11,
          'text-font': ['Noto Sans Regular'],
        },
        paint: {
          'text-color': '#ffffff',
          'text-halo-color': 'rgba(0,0,0,0.5)',
          'text-halo-width': 1,
        },
      })

      // ── 변전소 소스/레이어 ──────────────────────────────
      map.addSource(SRC_SUBSTATIONS, {
        type: 'geojson',
        data: substationsToGeoJSON([]),
      })
      map.addLayer({
        id: LYR_SUBSTATIONS,
        type: 'circle',
        source: SRC_SUBSTATIONS,
        layout: { visibility: 'visible' },
        paint: {
          'circle-radius': 5,
          'circle-color': COLOR.substation,
          'circle-opacity': 0.85,
          'circle-stroke-width': 1,
          'circle-stroke-color': '#2980b9',
        },
      })

      // ── 송배전선 소스/레이어 ──────────────────────────────
      map.addSource(SRC_POWERLINES, {
        type: 'geojson',
        data: powerlinesToGeoJSON([]),
      })
      map.addLayer({
        id: LYR_POWERLINES,
        type: 'line',
        source: SRC_POWERLINES,
        layout: { visibility: 'visible', 'line-cap': 'round', 'line-join': 'round' },
        paint: {
          'line-color': COLOR.powerline,
          'line-width': 2,
          'line-opacity': 0.6,
        },
      })

      // ── 변전소 hover 팝업 ──────────────────────────────
      map.on('mouseenter', LYR_SUBSTATIONS, (e) => {
        map.getCanvas().style.cursor = 'pointer'
        const feat = e.features?.[0]
        if (!feat || !popupRef.current) return
        popupRef.current
          .setLngLat(e.lngLat)
          .setHTML(
            `<div style="font-size:12px;line-height:1.5">
               <strong style="color:${COLOR.substation}">${feat.properties?.name ?? '변전소'}</strong><br/>
               ${feat.properties?.voltage ? `전압: ${feat.properties.voltage}` : ''}
             </div>`,
          )
          .addTo(map)
      })
      map.on('mouseleave', LYR_SUBSTATIONS, () => {
        map.getCanvas().style.cursor = ''
        popupRef.current?.remove()
      })

      // ── 송배전선 hover 팝업 ──────────────────────────────
      map.on('mouseenter', LYR_POWERLINES, (e) => {
        map.getCanvas().style.cursor = 'pointer'
        const feat = e.features?.[0]
        if (!feat || !popupRef.current) return
        popupRef.current
          .setLngLat(e.lngLat)
          .setHTML(
            `<div style="font-size:12px">
               <strong style="color:${COLOR.powerline}">${feat.properties?.name ?? '송배전선'}</strong>
               ${feat.properties?.voltage ? ` · ${feat.properties.voltage}V` : ''}
             </div>`,
          )
          .addTo(map)
      })
      map.on('mouseleave', LYR_POWERLINES, () => {
        map.getCanvas().style.cursor = ''
        popupRef.current?.remove()
      })

      // ── 뷰포트 변경 이벤트 ────────────────────────────────
      const onMove = () => {
        const c = map.getCenter()
        const z = map.getZoom()
        const b = map.getBounds()
        setViewport({ center: [c.lng, c.lat], zoom: z })
        setBbox({
          xmin: b.getWest(),
          ymin: b.getSouth(),
          xmax: b.getEast(),
          ymax: b.getNorth(),
        })

        // zoom 임계 전환 — 레이어 토글 상태도 함께 반영
        const isCluster = z < CLUSTER_ZOOM
        const lyr = layersRef.current
        const setClusterVis = (id: string, on: boolean) => {
          if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', on ? 'visible' : 'none')
        }
        setClusterVis(LYR_CLUSTERS_ACTIVE,  isCluster && lyr.active)
        setClusterVis(LYR_CLUSTERS_STOPPED, isCluster && lyr.stopped)
        setClusterVis(LYR_CLUSTERS_RETIRED, isCluster && lyr.retired)
        setClusterVis(LYR_CLUSTER_COUNT,    isCluster && (lyr.active || lyr.stopped || lyr.retired))
        setClusterVis(LYR_MARKERS,          !isCluster && (lyr.active || lyr.stopped || lyr.retired))

        // 토지피복 ON 상태면 이동 후 재fetch
        fetchLandcoverOnMoveRef.current()
      }

      map.on('moveend', onMove)
      map.on('zoomend', onMove)
      // 초기 호출
      onMove()
      // style 로드 완료 알림 → clusters/markers effect 재실행 트리거
      setMapLoaded(true)

      // ── 개별 마커 클릭 ────────────────────────────────────
      map.on('click', LYR_MARKERS, (e) => {
        const feat = e.features?.[0]
        if (!feat) return
        const id = feat.properties?.id as number
        if (!id) return

        setHighlightedId(id)
        setSelectedId(id)
        setPanelMode('detail')

        // 상세 정보 비동기 로드
        fetchFacility(id).catch((err: Error & { status?: number }) => {
          if (err.status === 503) setDbError(true)
        })
      })

      // ── 클러스터 클릭 → fly-to zoom 12 ───────────────────
      const onClusterClick = (e: maplibregl.MapMouseEvent & { features?: maplibregl.MapGeoJSONFeature[] }) => {
        const feat = e.features?.[0]
        if (!feat) return
        const coords = (feat.geometry as GeoJSON.Point).coordinates as [number, number]
        map.flyTo({ center: coords, zoom: 12, duration: 1000 })
      }
      map.on('click', LYR_CLUSTERS_ACTIVE,  onClusterClick)
      map.on('click', LYR_CLUSTERS_STOPPED, onClusterClick)
      map.on('click', LYR_CLUSTERS_RETIRED, onClusterClick)

      // ── 마커 hover → 팝업 ─────────────────────────────────
      map.on('mouseenter', LYR_MARKERS, (e) => {
        map.getCanvas().style.cursor = 'pointer'
        const feat = e.features?.[0]
        if (!feat || !popupRef.current) return
        const name     = feat.properties?.name as string
        const capacity = feat.properties?.capacity as number | null
        popupRef.current
          .setLngLat(e.lngLat)
          .setHTML(
            `<div style="font-size:12px;line-height:1.5">
               <strong style="color:var(--text-primary)">${name ?? '(이름 없음)'}</strong><br/>
               ${capacity != null ? `${capacity.toLocaleString('ko-KR')} kW` : '용량 미상'}
             </div>`,
          )
          .addTo(map)
      })
      map.on('mouseleave', LYR_MARKERS, () => {
        map.getCanvas().style.cursor = ''
        popupRef.current?.remove()
      })

      // ── 클러스터 hover ────────────────────────────────────
      const onClusterEnter = (e: maplibregl.MapMouseEvent & { features?: maplibregl.MapGeoJSONFeature[] }) => {
        map.getCanvas().style.cursor = 'pointer'
        const feat = e.features?.[0]
        if (!feat || !popupRef.current) return
        const p = feat.properties ?? {}
        popupRef.current
          .setLngLat(e.lngLat)
          .setHTML(
            `<div style="font-size:12px;line-height:1.8">
               <strong style="font-size:13px">${p.sigungu ?? '(미분류)'}</strong>
               &nbsp;<span style="color:#aaa">총 ${Number(p.cnt).toLocaleString('ko-KR')}개소</span><br/>
               <span style="color:${COLOR.active}">● 정상가동</span> ${Number(p.cnt_active).toLocaleString('ko-KR')}개<br/>
               <span style="color:${COLOR.stopped}">● 가동중단</span> ${Number(p.cnt_stopped).toLocaleString('ko-KR')}개<br/>
               <span style="color:#e74c3c">● 폐기</span> ${Number(p.cnt_retired).toLocaleString('ko-KR')}개
             </div>`,
          )
          .addTo(map)
      }
      const onClusterLeave = () => {
        map.getCanvas().style.cursor = ''
        popupRef.current?.remove()
      }
      map.on('mouseenter', LYR_CLUSTERS_ACTIVE,  onClusterEnter)
      map.on('mouseenter', LYR_CLUSTERS_STOPPED, onClusterEnter)
      map.on('mouseenter', LYR_CLUSTERS_RETIRED, onClusterEnter)
      map.on('mouseleave', LYR_CLUSTERS_ACTIVE,  onClusterLeave)
      map.on('mouseleave', LYR_CLUSTERS_STOPPED, onClusterLeave)
      map.on('mouseleave', LYR_CLUSTERS_RETIRED, onClusterLeave)
    })

    mapRef.current = map

    return () => {
      popupRef.current?.remove()
      map.remove()
      mapRef.current = null
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // ─── 마커 데이터 갱신 ─────────────────────────────────────
  useEffect(() => {
    if (!mapLoaded) return
    const map = mapRef.current
    if (!map) return
    const src = map.getSource(SRC_MARKERS) as maplibregl.GeoJSONSource | undefined
    src?.setData(markersToGeoJSON(markers))
  }, [markers, mapLoaded])

  // ─── 클러스터 데이터 갱신 ─────────────────────────────────
  useEffect(() => {
    if (!mapLoaded) return
    const map = mapRef.current
    if (!map) return
    const src = map.getSource(SRC_CLUSTERS) as maplibregl.GeoJSONSource | undefined
    src?.setData(clustersToGeoJSON(clusters))
  }, [clusters, mapLoaded])

  // ─── 인프라 데이터 갱신 (bbox 변경 시) ───────────────────
  const infraAbortRef = useRef<AbortController | null>(null)
  useEffect(() => {
    if (!mapLoaded) return
    const map = mapRef.current
    if (!map) return
    const bbox = map.getBounds()
    if (!bbox) return

    // 이전 요청 취소
    infraAbortRef.current?.abort()
    infraAbortRef.current = new AbortController()

    const bboxParams = {
      xmin: bbox.getWest(),
      ymin: bbox.getSouth(),
      xmax: bbox.getEast(),
      ymax: bbox.getNorth(),
    }

    // 변전소 로드
    if (layers.substation) {
      fetchSubstationsBbox(bboxParams)
        .then((subs) => {
          const src = map.getSource(SRC_SUBSTATIONS) as maplibregl.GeoJSONSource | undefined
          src?.setData(substationsToGeoJSON(subs))
        })
        .catch(() => {})
    }

    // 송배전선 로드
    if (layers.powerline) {
      fetchPowerLinesBbox(bboxParams)
        .then((lines) => {
          const src = map.getSource(SRC_POWERLINES) as maplibregl.GeoJSONSource | undefined
          src?.setData(powerlinesToGeoJSON(lines))
        })
        .catch(() => {})
    }

    return () => { infraAbortRef.current?.abort() }
  }, [markers, clusters, layers.substation, layers.powerline, mapLoaded])

  // ─── 레이어 가시성 토글 반영 ────────────────────────────
  useEffect(() => {
    if (!mapLoaded) return
    const map = mapRef.current
    if (!map) return
    if (map.getLayer(LYR_SUBSTATIONS)) {
      map.setLayoutProperty(LYR_SUBSTATIONS, 'visibility', layers.substation ? 'visible' : 'none')
    }
    if (map.getLayer(LYR_POWERLINES)) {
      map.setLayoutProperty(LYR_POWERLINES, 'visibility', layers.powerline ? 'visible' : 'none')
    }
  }, [layers.substation, layers.powerline, mapLoaded])

  // ─── 3D 지형 토글 ────────────────────────────────────────
  useEffect(() => {
    if (!mapLoaded) return
    const map = mapRef.current
    if (!map) return
    if (layers.terrain) {
      map.setTerrain({ source: SRC_TERRAIN, exaggeration: 1.5 })
      if (map.getLayer(LYR_HILLSHADE)) map.setLayoutProperty(LYR_HILLSHADE, 'visibility', 'visible')
      map.easeTo({ pitch: 50, duration: 800 })
    } else {
      map.setTerrain(null)
      if (map.getLayer(LYR_HILLSHADE)) map.setLayoutProperty(LYR_HILLSHADE, 'visibility', 'none')
      map.easeTo({ pitch: 0, duration: 800 })
    }
  }, [layers.terrain, mapLoaded])

  // ─── 토지피복 레이어 토글 + bbox 변경 시 fetch ──────────
  useEffect(() => {
    if (!mapLoaded) return
    const map = mapRef.current
    if (!map || !map.getLayer(LYR_LANDCOVER_VEC)) return

    if (!layers.landcover) {
      map.setLayoutProperty(LYR_LANDCOVER_VEC, 'visibility', 'none')
      fetchLandcoverOnMoveRef.current = () => {}
      return
    }

    map.setLayoutProperty(LYR_LANDCOVER_VEC, 'visibility', 'visible')

    const fetchLandcover = async () => {
      landcoverAbortRef.current?.abort()
      landcoverAbortRef.current = new AbortController()
      const b = map.getBounds()
      const params = new URLSearchParams({
        xmin: b.getWest().toFixed(5),
        ymin: b.getSouth().toFixed(5),
        xmax: b.getEast().toFixed(5),
        ymax: b.getNorth().toFixed(5),
      })
      try {
        const res = await fetch(`/api/landcover?${params}`, { signal: landcoverAbortRef.current.signal })
        if (!res.ok) return
        const geojson = await res.json()
        const src = map.getSource(SRC_LANDCOVER_VEC) as maplibregl.GeoJSONSource | undefined
        src?.setData(geojson)
      } catch { /* AbortError or network */ }
    }

    fetchLandcoverOnMoveRef.current = fetchLandcover
    fetchLandcover()

    return () => { landcoverAbortRef.current?.abort() }
  }, [layers.landcover, mapLoaded])

  // ─── 하이라이트 feature-state 갱신 ───────────────────────
  const prevHighlightRef = useRef<number | null>(null)
  useEffect(() => {
    if (!mapLoaded) return
    const map = mapRef.current
    if (!map) return

    // 이전 하이라이트 해제
    if (prevHighlightRef.current !== null) {
      map.setFeatureState(
        { source: SRC_MARKERS, id: prevHighlightRef.current },
        { highlighted: false },
      )
    }
    // 새 하이라이트 적용
    if (highlightedId !== null) {
      map.setFeatureState(
        { source: SRC_MARKERS, id: highlightedId },
        { highlighted: true },
      )
    }
    prevHighlightRef.current = highlightedId
  }, [highlightedId, mapLoaded])

  // ─── URL 딥링크: 초기 로드 시 복원 ───────────────────────
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const id  = params.get('id')
    const lng = params.get('lng')
    const lat = params.get('lat')
    const z   = params.get('z')

    if (lng && lat) {
      const map = mapRef.current
      if (map) {
        map.jumpTo({
          center: [parseFloat(lng), parseFloat(lat)],
          zoom:   z ? parseFloat(z) : 12,
        })
      }
    }
    if (id) {
      const numId = parseInt(id, 10)
      setSelectedId(numId)
      setHighlightedId(numId)
      setPanelMode('detail')
    }
  // 마운트 시 1회만 실행
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // ─── 마커 상태 필터 반영 (active/stopped/retired 토글) ──
  useEffect(() => {
    if (!mapLoaded) return
    const map = mapRef.current
    if (!map) return

    const anyPvOn = layers.active || layers.stopped || layers.retired
    const isCluster = map.getZoom() < CLUSTER_ZOOM

    // 클러스터/마커 visibility — zoom 레벨과 레이어 상태 둘 다 반영
    const setV = (id: string, on: boolean) => {
      if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', on ? 'visible' : 'none')
    }
    setV(LYR_CLUSTERS_ACTIVE,  isCluster && layers.active)
    setV(LYR_CLUSTERS_STOPPED, isCluster && layers.stopped)
    setV(LYR_CLUSTERS_RETIRED, isCluster && layers.retired)
    setV(LYR_CLUSTER_COUNT,    isCluster && anyPvOn)
    setV(LYR_MARKERS,          !isCluster && anyPvOn)

    // 개별 마커 상태 필터
    if (map.getLayer(LYR_MARKERS)) {
      const allowed: string[] = []
      if (layers.active)  allowed.push('정상가동')
      if (layers.stopped) allowed.push('가동중단')
      if (layers.retired) allowed.push('폐기')

      map.setFilter(
        LYR_MARKERS,
        allowed.length === 0
          ? ['==', 1, 0]
          : ['in', ['get', 'status'], ['literal', allowed]],
      )
    }
  }, [layers.active, layers.stopped, layers.retired, mapLoaded])

  // ─── 외부 flyTo 요청 반영 (mapStore.viewport 변경) ───────
  const flyTo = useCallback((lng: number, lat: number, zoom = 15) => {
    mapRef.current?.flyTo({ center: [lng, lat], zoom, duration: 1200 })
  }, [])

  // viewport.center 변경 감지는 App.tsx에서 처리
  // flyTo 함수를 window에 임시 노출 (다른 컴포넌트에서 호출)
  useEffect(() => {
    (window as Window & { __mapFlyTo?: typeof flyTo }).__mapFlyTo = flyTo
    return () => {
      delete (window as Window & { __mapFlyTo?: typeof flyTo }).__mapFlyTo
    }
  }, [flyTo])

  return (
    <div className="relative w-full h-full">
      {/* 지도 컨테이너 */}
      <div ref={containerRef} className="w-full h-full" />

      {/* 레이어 토글 오버레이 */}
      <LayerToggle />

      {/* 토지피복 범례 (우상단) */}
      <LandcoverLegend />

      {/* 현재 줌 레벨 표시 (디버그) */}
      <div
        className="absolute top-2 left-3 px-2 py-0.5 rounded text-[10px]
                   bg-[var(--bg-elevated)]/80 text-[var(--text-muted)]
                   pointer-events-none select-none"
      >
        zoom {viewport.zoom.toFixed(1)}
        {viewport.zoom < CLUSTER_ZOOM ? ' · 클러스터' : ' · 마커'}
      </div>
    </div>
  )
}
