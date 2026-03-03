// ============================================================
// 인프라 레이어 API 클라이언트 (변전소 / 송배전선)
// ============================================================

import type { Substation, PowerLine, BboxParams } from '../types'

/** 공통 fetch 래퍼 */
async function apiFetch<T>(url: string): Promise<T> {
  const res = await fetch(url)
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: `HTTP ${res.status}` }))
    throw Object.assign(new Error(err.error ?? '서버 오류'), { status: res.status })
  }
  return res.json() as Promise<T>
}

/**
 * bbox 내 변전소 목록
 * GET /api/substations/bbox?xmin=&ymin=&xmax=&ymax=
 */
export async function fetchSubstationsBbox(bbox: BboxParams): Promise<Substation[]> {
  const qs = new URLSearchParams({
    xmin: String(bbox.xmin),
    ymin: String(bbox.ymin),
    xmax: String(bbox.xmax),
    ymax: String(bbox.ymax),
  })
  const res = await apiFetch<{ items: Substation[] }>(`/api/substations/bbox?${qs}`)
  return res.items
}

/**
 * bbox 내 송배전선 목록 (bbox 파라미터 필수, 없으면 400)
 * GET /api/power-lines/bbox?xmin=&ymin=&xmax=&ymax=
 */
export async function fetchPowerLinesBbox(bbox: BboxParams): Promise<PowerLine[]> {
  const qs = new URLSearchParams({
    xmin: String(bbox.xmin),
    ymin: String(bbox.ymin),
    xmax: String(bbox.xmax),
    ymax: String(bbox.ymax),
  })
  const res = await apiFetch<{ items: PowerLine[] }>(`/api/power-lines/bbox?${qs}`)
  return res.items
}
