"""
Pydantic v2 응답 스키마.
API 응답 직렬화에 사용.
"""
from datetime import date
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, field_validator


class FacilityListItem(BaseModel):
    """발전소 목록 아이템 (경량화 — 지도 마커용)."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: Optional[str] = None
    status: str
    capacity_kw: Optional[float] = None
    lng: Optional[float] = None   # ST_X(geom)
    lat: Optional[float] = None   # ST_Y(geom)
    has_coord: Optional[bool] = None


class FacilityDetail(BaseModel):
    """발전소 상세 응답 (단건 조회)."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: Optional[str] = None
    addr_road: Optional[str] = None
    addr_jibun: Optional[str] = None
    install_type: Optional[str] = None
    status: str
    capacity_kw: Optional[float] = None
    voltage: Optional[str] = None
    frequency: Optional[str] = None
    install_year: Optional[int] = None
    usage_detail: Optional[str] = None
    install_area_m2: Optional[float] = None
    permit_date: Optional[date] = None
    permit_org: Optional[str] = None
    data_date: Optional[date] = None
    source_file: Optional[str] = None
    has_coord: Optional[bool] = None
    lng: Optional[float] = None
    lat: Optional[float] = None
    # PostGIS 계산 필드
    nearby_count: Optional[int] = None            # 반경 5km 내 발전소 수
    nearest_substation_name: Optional[str] = None  # 가장 가까운 변전소명
    nearest_substation_dist_m: Optional[float] = None  # 거리 (m)


class FacilityListResponse(BaseModel):
    """발전소 목록 응답 (페이지네이션)."""
    total: int
    page: int
    per_page: int
    items: List[FacilityDetail]


class BboxFacilityItem(BaseModel):
    """bbox 쿼리용 경량 아이템."""
    id: int
    name: Optional[str] = None
    status: str
    capacity_kw: Optional[float] = None
    lng: float
    lat: float


class BboxFacilityResponse(BaseModel):
    """bbox 발전소 응답."""
    items: List[BboxFacilityItem]


class NearbyFacilityItem(BaseModel):
    """반경 검색 아이템 — dist_m 추가."""
    id: int
    name: Optional[str] = None
    status: str
    capacity_kw: Optional[float] = None
    lng: Optional[float] = None
    lat: Optional[float] = None
    has_coord: Optional[bool] = None
    dist_m: float


class NearbyFacilityResponse(BaseModel):
    """반경 검색 응답."""
    items: List[NearbyFacilityItem]


class ClusterItem(BaseModel):
    """시군구 집계 아이템 (zoom < 10 클러스터용)."""
    sigungu: Optional[str] = None
    cnt: int
    center_lat: Optional[float] = None
    center_lng: Optional[float] = None


class ClusterResponse(BaseModel):
    """시군구 집계 응답."""
    items: List[ClusterItem]


class StatsResponse(BaseModel):
    """대시보드 요약 통계."""
    total: int
    active: int           # 정상가동
    stopped: int          # 가동중단
    retired: int          # 폐기
    no_coord: int         # 좌표 결측
    total_capacity_mw: float
    sigungu_count: int


class SubstationItem(BaseModel):
    """변전소 아이템."""
    id: int
    name: Optional[str] = None
    name_en: Optional[str] = None
    voltage: Optional[str] = None
    sub_type: Optional[str] = None
    frequency: Optional[str] = None
    operator: Optional[str] = None
    osm_id: Optional[int] = None
    sido: Optional[str] = None
    lng: float
    lat: float


class SubstationBboxResponse(BaseModel):
    """bbox 변전소 응답."""
    items: List[SubstationItem]


class PowerLineItem(BaseModel):
    """송배전선 아이템."""
    id: int
    name: Optional[str] = None
    power_type: Optional[str] = None
    voltage: Optional[str] = None
    sido: Optional[str] = None
    # LineString 좌표 리스트 [[lng, lat], ...]
    coordinates: List[List[float]]


class PowerLineBboxResponse(BaseModel):
    """bbox 송배전선 응답."""
    items: List[PowerLineItem]
