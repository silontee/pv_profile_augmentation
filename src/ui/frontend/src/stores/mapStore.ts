// ============================================================
// 지도 상태 Zustand 스토어
// - 뷰포트 (center, zoom, bbox)
// - 선택/하이라이트 마커
// ============================================================

import { create } from 'zustand'
import type { BboxParams } from '../types'

interface MapViewport {
  center: [number, number]   // [lng, lat]
  zoom: number
  bbox: BboxParams | null    // 현재 뷰포트 bbox (지도 이동 시 갱신)
}

interface MapState {
  viewport: MapViewport
  /** 현재 선택된 발전소 ID (DetailPanel 표시용) */
  selectedId: number | null
  /** 하이라이트된 마커 ID (크기 1.5×, 흰 테두리) */
  highlightedId: number | null

  // 액션
  setViewport: (v: Partial<MapViewport>) => void
  setSelectedId: (id: number | null) => void
  setHighlightedId: (id: number | null) => void
  setBbox: (bbox: BboxParams) => void
}

export const useMapStore = create<MapState>((set) => ({
  viewport: {
    center: [127.5, 36.5],  // 한국 중심
    zoom: 7,
    bbox: null,
  },
  selectedId: null,
  highlightedId: null,

  setViewport: (v) =>
    set((s) => ({ viewport: { ...s.viewport, ...v } })),

  setSelectedId: (id) => set({ selectedId: id }),

  setHighlightedId: (id) => set({ highlightedId: id }),

  setBbox: (bbox) =>
    set((s) => ({ viewport: { ...s.viewport, bbox } })),
}))
