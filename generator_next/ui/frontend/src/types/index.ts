// ============================================================
// 공통 타입 정의
// 백엔드 Pydantic 스키마와 1:1 대응
// ============================================================

/** 발전소 가동 상태 */
export type FacilityStatus = '정상가동' | '가동중단' | '폐기'

/** 발전소 목록 아이템 (검색 결과 / bbox 마커) */
export interface Facility {
  id: number
  name: string
  addr_road: string | null
  addr_jibun: string | null
  /** 경도 (좌표 결측 시 null) */
  lng: number | null
  /** 위도 (좌표 결측 시 null) */
  lat: number | null
  /** 좌표 보유 여부 (DB 계산 컬럼) */
  has_coord: boolean
  install_type: string | null
  status: FacilityStatus
  capacity_kw: number | null
  voltage: string | null
  frequency: string | null
  install_year: number | null
  usage_detail: string | null
  permit_date: string | null   // ISO 8601 date string
  permit_org: string | null
  install_area_m2: number | null
  data_date: string | null
}

/** 대시보드 통계 (캐시 TTL 60s) */
export interface Stats {
  total: number
  active: number
  stopped: number
  retired: number
  no_coord: number
  total_capacity_mw: number
  sigungu_count: number
}

/** 변전소 */
export interface Substation {
  id: number
  name: string | null
  name_en: string | null
  lng: number
  lat: number
  voltage: string | null
  sub_type: string | null
  frequency: string | null
  operator: string | null
  osm_id: number | null
  sido: string | null
}

/** 송배전선 (GeoJSON LineString) */
export interface PowerLine {
  id: number
  name: string | null
  /** GeoJSON LineString 좌표 배열 [[lng, lat], ...] */
  coordinates: [number, number][]
  power_type: string | null
  voltage: string | null
  sido: string | null
}

/** zoom < 10 클러스터 집계 아이템 */
export interface ClusterItem {
  sigungu: string
  cnt: number
  center_lat: number
  center_lng: number
}

/** 검색 API 응답 */
export interface FacilityListResponse {
  items: Facility[]
  total: number
  page: number
  per_page: number
}

/** bbox 파라미터 */
export interface BboxParams {
  xmin: number
  ymin: number
  xmax: number
  ymax: number
}

/** 반경 검색 응답 (거리 포함) */
export interface NearbyFacility extends Facility {
  dist_m: number
}

/** 최근접 변전소 (DetailPanel 주변 정보용) */
export interface NearestSubstation {
  name: string | null
  dist_m: number
}

/** 주변 발전소 요약 */
export interface NearbyInfo {
  nearby_count: number
  nearest_substation: NearestSubstation | null
}

/** API 에러 응답 */
export interface ApiError {
  error: string
  retry_after?: number
}

/** URL 딥링크 파라미터 */
export interface DeepLinkParams {
  id?: number
  lng?: number
  lat?: number
  z?: number
}
