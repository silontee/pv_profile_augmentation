// ============================================================
// 발전소 API 클라이언트
// Vite 프록시: /api/* → http://localhost:8000
// ============================================================

import type {
  Facility,
  FacilityListResponse,
  BboxParams,
  NearbyFacility,
  ClusterItem,
  FacilityStatus,
} from '../types'

/** 공통 fetch 래퍼: 503 시 ApiError throw */
async function apiFetch<T>(url: string): Promise<T> {
  const res = await fetch(url)
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: `HTTP ${res.status}` }))
    throw Object.assign(new Error(err.error ?? '서버 오류'), { status: res.status })
  }
  return res.json() as Promise<T>
}

/** URL 쿼리 파라미터 빌더 (null/undefined 제외) */
function buildQuery(params: Record<string, string | number | null | undefined>): string {
  const qs = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v !== null && v !== undefined && v !== '') {
      qs.set(k, String(v))
    }
  }
  const s = qs.toString()
  return s ? `?${s}` : ''
}

// ─── 목록 + 검색 ─────────────────────────────────────────────

export interface FetchFacilitiesOptions {
  q?: string
  status?: FacilityStatus | ''
  cap_min?: number
  cap_max?: number
  year_min?: number
  year_max?: number
  page?: number
  per_page?: number
}

/**
 * 발전소 목록 검색 (텍스트 + 필터 + 페이지네이션)
 * GET /api/facilities
 */
export async function fetchFacilities(opts: FetchFacilitiesOptions = {}): Promise<FacilityListResponse> {
  const qs = buildQuery({
    q:         opts.q,
    status:    opts.status || undefined,
    cap_min:   opts.cap_min,
    cap_max:   opts.cap_max,
    year_min:  opts.year_min,
    year_max:  opts.year_max,
    page:      opts.page ?? 1,
    per_page: opts.per_page ?? 50,
  })
  return apiFetch<FacilityListResponse>(`/api/facilities${qs}`)
}

/**
 * 단건 상세 조회
 * GET /api/facilities/{id}
 */
export async function fetchFacility(id: number): Promise<Facility> {
  return apiFetch<Facility>(`/api/facilities/${id}`)
}

export interface BboxFetchOptions {
  status?:   FacilityStatus | ''
  cap_min?:  number
  cap_max?:  number
  year_min?: number
  year_max?: number
}

/**
 * 뷰포트 bbox 내 마커 목록 (좌표 있는 것만, zoom ≥ 10 전용)
 * GET /api/facilities/bbox?xmin=&ymin=&xmax=&ymax=&...
 */
export async function fetchBbox(
  bbox: BboxParams,
  opts: BboxFetchOptions = {},
): Promise<Facility[]> {
  const qs = buildQuery({
    xmin:     bbox.xmin,
    ymin:     bbox.ymin,
    xmax:     bbox.xmax,
    ymax:     bbox.ymax,
    status:   opts.status   || undefined,
    cap_min:  opts.cap_min,
    cap_max:  opts.cap_max,
    year_min: opts.year_min,
    year_max: opts.year_max,
  })
  const res = await apiFetch<{ items: Facility[] }>(`/api/facilities/bbox${qs}`)
  return res.items
}

/**
 * 반경 검색 (클릭 지점 주변)
 * GET /api/facilities/nearby?lng=&lat=&radius_m=
 */
export async function fetchNearby(
  lng: number,
  lat: number,
  radius_m = 5000,
): Promise<NearbyFacility[]> {
  const qs = buildQuery({ lng, lat, radius_m })
  const res = await apiFetch<{ items: NearbyFacility[] }>(`/api/facilities/nearby${qs}`)
  return res.items
}

export interface ClusterFetchOptions {
  cap_min?:  number
  cap_max?:  number
  year_min?: number
  year_max?: number
}

/**
 * zoom < 10 시군구 집계 클러스터
 * GET /api/facilities/clusters?cap_min=&cap_max=&year_min=&year_max=
 */
export async function fetchClusters(opts: ClusterFetchOptions = {}): Promise<ClusterItem[]> {
  const qs = buildQuery({
    cap_min:  opts.cap_min,
    cap_max:  opts.cap_max,
    year_min: opts.year_min,
    year_max: opts.year_max,
  })
  const res = await apiFetch<{ items: ClusterItem[] }>(`/api/facilities/clusters${qs}`)
  return res.items
}
