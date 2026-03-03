// ============================================================
// UI 상태 Zustand 스토어
// - 패널 모드 (검색 / 상세)
// - DB 장애 여부
// ============================================================

import { create } from 'zustand'

/** 우측 패널 표시 모드 */
export type PanelMode = 'search' | 'detail'

export interface UiState {
  /** 우측 패널 모드 */
  panelMode: PanelMode
  /** DB 장애 여부 (503 수신 시 true) */
  dbError: boolean
  /** 레이어 가시성 */
  layers: {
    active: boolean        // 정상가동 마커
    stopped: boolean       // 가동중단 마커
    retired: boolean       // 폐기 마커
    substation: boolean    // 변전소
    powerline: boolean     // 송배전선
    boundary: boolean      // 시군구 경계
    terrain: boolean       // 3D 지형 (MapTiler DEM)
    landcover: boolean     // 토지피복 (환경부 EGIS WFS)
  }

  // 액션
  setPanelMode: (mode: PanelMode) => void
  setDbError: (v: boolean) => void
  toggleLayer: (key: keyof UiState['layers']) => void
}

export const useUiStore = create<UiState>((set) => ({
  panelMode: 'search',
  dbError:   false,
  layers: {
    active:     true,
    stopped:    true,
    retired:    true,
    substation: true,
    powerline:  true,
    boundary:   false,
    terrain:    false,
    landcover:  false,
  },

  setPanelMode: (mode) => set({ panelMode: mode }),

  setDbError: (v) => set({ dbError: v }),

  toggleLayer: (key) =>
    set((s) => ({
      layers: { ...s.layers, [key]: !s.layers[key] },
    })),
}))
