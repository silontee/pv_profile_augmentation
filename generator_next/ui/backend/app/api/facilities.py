"""
발전소 엔드포인트.
- GET /api/facilities        목록+검색+필터 (페이지네이션)
- GET /api/facilities/bbox   뷰포트 내 마커
- GET /api/facilities/nearby 반경 검색
- GET /api/facilities/clusters 시군구 집계
- GET /api/facilities/{id}   단건 상세
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import get_db
from app.models import PvFacility, Substation
from app.schemas import (
    BboxFacilityItem,
    BboxFacilityResponse,
    ClusterItem,
    ClusterResponse,
    FacilityDetail,
    FacilityListResponse,
    NearbyFacilityItem,
    NearbyFacilityResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["facilities"])

# DB 장애 공통 응답
_DB_ERROR_RESPONSE = {"error": "서비스 일시 중단", "retry_after": 30}


@router.get("/facilities", response_model=FacilityListResponse)
async def list_facilities(
    q: Optional[str] = Query(None, description="텍스트 검색 (시설명, 도로명주소)"),
    status: Optional[str] = Query(None, description="가동상태 (정상가동|가동중단|폐기)"),
    cap_min: Optional[float] = Query(None, ge=0, description="설비용량 최솟값 (kW)"),
    cap_max: Optional[float] = Query(None, ge=0, description="설비용량 최댓값 (kW)"),
    year_min: Optional[int] = Query(None, ge=1990, description="설치연도 최솟값"),
    year_max: Optional[int] = Query(None, le=2030, description="설치연도 최댓값"),
    page: int = Query(1, ge=1, description="페이지 (1부터 시작)"),
    per_page: int = Query(50, ge=1, le=200, description="페이지 크기 (최대 200)"),
    db: AsyncSession = Depends(get_db),
):
    """
    발전소 목록 통합 검색.
    텍스트·상태·용량·연도 필터 복합 적용.
    좌표 결측 항목도 포함 (has_coord=False).
    """
    try:
        offset = (page - 1) * per_page

        # 기본 쿼리 — 좌표 유무 계산 포함
        stmt = select(
            PvFacility,
            func.ST_X(PvFacility.geom).label("lng"),
            func.ST_Y(PvFacility.geom).label("lat"),
        )

        # 텍스트 검색 (ILIKE — pg_trgm 인덱스 활용)
        if q:
            like_q = f"%{q}%"
            stmt = stmt.where(
                (PvFacility.name.ilike(like_q))
                | (PvFacility.addr_road.ilike(like_q))
            )

        # 가동상태 필터
        if status:
            stmt = stmt.where(PvFacility.status == status)

        # 설비용량 범위
        if cap_min is not None:
            stmt = stmt.where(PvFacility.capacity_kw >= cap_min)
        if cap_max is not None:
            stmt = stmt.where(PvFacility.capacity_kw <= cap_max)

        # 설치연도 범위
        if year_min is not None:
            stmt = stmt.where(PvFacility.install_year >= year_min)
        if year_max is not None:
            stmt = stmt.where(PvFacility.install_year <= year_max)

        # 전체 건수 카운트 (서브쿼리 활용)
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_result = await db.execute(count_stmt)
        total = total_result.scalar_one()

        # 페이지네이션 적용
        stmt = stmt.order_by(PvFacility.capacity_kw.desc().nulls_last()).limit(per_page).offset(offset)
        result = await db.execute(stmt)
        rows = result.all()

        items = []
        for row in rows:
            facility = row[0]
            lng = row[1]
            lat = row[2]
            detail = FacilityDetail(
                id=facility.id,
                name=facility.name,
                addr_road=facility.addr_road,
                addr_jibun=facility.addr_jibun,
                install_type=facility.install_type,
                status=facility.status,
                capacity_kw=float(facility.capacity_kw) if facility.capacity_kw is not None else None,
                voltage=facility.voltage,
                frequency=facility.frequency,
                install_year=facility.install_year,
                usage_detail=facility.usage_detail,
                install_area_m2=float(facility.install_area_m2) if facility.install_area_m2 is not None else None,
                permit_date=facility.permit_date,
                permit_org=facility.permit_org,
                data_date=facility.data_date,
                source_file=facility.source_file,
                has_coord=facility.has_coord,
                lng=float(lng) if lng is not None else None,
                lat=float(lat) if lat is not None else None,
            )
            items.append(detail)

        return FacilityListResponse(
            total=total,
            page=page,
            per_page=per_page,
            items=items,
        )

    except SQLAlchemyError as e:
        logger.error(f"/api/facilities DB 오류: {e}")
        raise HTTPException(status_code=503, detail=_DB_ERROR_RESPONSE)


@router.get("/facilities/clusters", response_model=ClusterResponse)
async def get_clusters(
    db: AsyncSession = Depends(get_db),
):
    """
    zoom < 10 용 시군구 집계.
    permit_org 기준으로 그룹핑, 좌표 있는 항목만.
    """
    try:
        stmt = text("""
            SELECT
                permit_org AS sigungu,
                COUNT(*) AS cnt,
                AVG(ST_Y(geom)) AS center_lat,
                AVG(ST_X(geom)) AS center_lng
            FROM pv_facility
            WHERE geom IS NOT NULL
            GROUP BY permit_org
            ORDER BY cnt DESC
        """)
        result = await db.execute(stmt)
        rows = result.fetchall()

        items = [
            ClusterItem(
                sigungu=row.sigungu,
                cnt=row.cnt,
                center_lat=float(row.center_lat) if row.center_lat is not None else None,
                center_lng=float(row.center_lng) if row.center_lng is not None else None,
            )
            for row in rows
        ]
        return ClusterResponse(items=items)

    except SQLAlchemyError as e:
        logger.error(f"/api/facilities/clusters DB 오류: {e}")
        raise HTTPException(status_code=503, detail=_DB_ERROR_RESPONSE)


@router.get("/facilities/bbox", response_model=BboxFacilityResponse)
async def get_facilities_bbox(
    xmin: float = Query(..., description="bbox 서쪽 경도 (EPSG:4326)"),
    ymin: float = Query(..., description="bbox 남쪽 위도 (EPSG:4326)"),
    xmax: float = Query(..., description="bbox 동쪽 경도 (EPSG:4326)"),
    ymax: float = Query(..., description="bbox 북쪽 위도 (EPSG:4326)"),
    status: Optional[str] = Query(None, description="가동상태 필터"),
    db: AsyncSession = Depends(get_db),
):
    """
    뷰포트 바운딩박스 내 발전소 마커.
    geom IS NOT NULL 조건 필수 적용.
    """
    try:
        # asyncpg는 `$N IS NULL` 패턴 비호환 → 동적 SQL 분기
        where_status = "AND status = :status" if status else ""
        sql = f"""
            SELECT
                id,
                name,
                status,
                CAST(capacity_kw AS FLOAT) AS capacity_kw,
                ST_X(geom) AS lng,
                ST_Y(geom) AS lat
            FROM pv_facility
            WHERE
                geom IS NOT NULL
                AND geom && ST_MakeEnvelope(:xmin, :ymin, :xmax, :ymax, 4326)
                {where_status}
            ORDER BY capacity_kw DESC NULLS LAST
        """
        params = {"xmin": xmin, "ymin": ymin, "xmax": xmax, "ymax": ymax}
        if status:
            params["status"] = status

        result = await db.execute(text(sql), params)
        rows = result.fetchall()

        items = [
            BboxFacilityItem(
                id=row.id,
                name=row.name,
                status=row.status,
                capacity_kw=row.capacity_kw,
                lng=row.lng,
                lat=row.lat,
            )
            for row in rows
        ]
        return BboxFacilityResponse(items=items)

    except SQLAlchemyError as e:
        logger.error(f"/api/facilities/bbox DB 오류: {e}")
        raise HTTPException(status_code=503, detail=_DB_ERROR_RESPONSE)


@router.get("/facilities/nearby", response_model=NearbyFacilityResponse)
async def get_facilities_nearby(
    lng: float = Query(..., description="중심 경도"),
    lat: float = Query(..., description="중심 위도"),
    radius_m: float = Query(5000, ge=100, le=50000, description="반경 (m), 기본 5000"),
    db: AsyncSession = Depends(get_db),
):
    """
    반경 검색 — geom::geography 기반 정확한 거리 계산.
    geom IS NOT NULL 조건 적용, 거리 오름차순 정렬.
    """
    try:
        stmt = text("""
            SELECT
                id,
                name,
                status,
                CAST(capacity_kw AS FLOAT) AS capacity_kw,
                has_coord,
                ST_X(geom) AS lng,
                ST_Y(geom) AS lat,
                ST_Distance(
                    geom::geography,
                    ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography
                ) AS dist_m
            FROM pv_facility
            WHERE
                geom IS NOT NULL
                AND ST_DWithin(
                    geom::geography,
                    ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography,
                    :radius_m
                )
            ORDER BY dist_m
            LIMIT 50
        """)

        result = await db.execute(stmt, {"lng": lng, "lat": lat, "radius_m": radius_m})
        rows = result.fetchall()

        items = [
            NearbyFacilityItem(
                id=row.id,
                name=row.name,
                status=row.status,
                capacity_kw=row.capacity_kw,
                has_coord=row.has_coord,
                lng=row.lng,
                lat=row.lat,
                dist_m=row.dist_m,
            )
            for row in rows
        ]
        return NearbyFacilityResponse(items=items)

    except SQLAlchemyError as e:
        logger.error(f"/api/facilities/nearby DB 오류: {e}")
        raise HTTPException(status_code=503, detail=_DB_ERROR_RESPONSE)


@router.get("/facilities/{facility_id}", response_model=FacilityDetail)
async def get_facility(
    facility_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    발전소 단건 상세 조회.
    nearby_count (반경 5km 내 발전소 수) 및 최근접 변전소 포함.
    """
    try:
        # 발전소 기본 정보 조회
        stmt = text("""
            SELECT
                id, name, addr_road, addr_jibun, install_type, status,
                CAST(capacity_kw AS FLOAT) AS capacity_kw,
                voltage,
                frequency,
                install_year, usage_detail,
                CAST(install_area_m2 AS FLOAT) AS install_area_m2,
                permit_date, permit_org, data_date, source_file,
                has_coord,
                ST_X(geom) AS lng,
                ST_Y(geom) AS lat
            FROM pv_facility
            WHERE id = :id
        """)
        result = await db.execute(stmt, {"id": facility_id})
        row = result.fetchone()

        if row is None:
            raise HTTPException(status_code=404, detail="발전소를 찾을 수 없습니다.")

        nearby_count = None
        nearest_name = None
        nearest_dist_m = None

        # 좌표가 있는 경우에만 공간 쿼리 실행
        if row.lng is not None and row.lat is not None:
            # 반경 5km 내 발전소 수 (자기 자신 제외)
            nearby_stmt = text("""
                SELECT COUNT(*) AS cnt
                FROM pv_facility
                WHERE
                    id != :id
                    AND geom IS NOT NULL
                    AND ST_DWithin(
                        geom::geography,
                        ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography,
                        5000
                    )
            """)
            nearby_result = await db.execute(nearby_stmt, {"id": facility_id, "lng": row.lng, "lat": row.lat})
            nearby_count = nearby_result.scalar_one()

            # 최근접 변전소
            substation_stmt = text("""
                SELECT
                    name,
                    ST_Distance(
                        geom::geography,
                        ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography
                    ) AS dist_m
                FROM substation
                ORDER BY geom <-> ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)
                LIMIT 1
            """)
            sub_result = await db.execute(substation_stmt, {"lng": row.lng, "lat": row.lat})
            sub_row = sub_result.fetchone()
            if sub_row:
                nearest_name = sub_row.name
                nearest_dist_m = float(sub_row.dist_m)

        return FacilityDetail(
            id=row.id,
            name=row.name,
            addr_road=row.addr_road,
            addr_jibun=row.addr_jibun,
            install_type=row.install_type,
            status=row.status,
            capacity_kw=row.capacity_kw,
            voltage=row.voltage,
            frequency=row.frequency,
            install_year=row.install_year,
            usage_detail=row.usage_detail,
            install_area_m2=row.install_area_m2,
            permit_date=row.permit_date,
            permit_org=row.permit_org,
            data_date=row.data_date,
            source_file=row.source_file,
            has_coord=row.has_coord,
            lng=row.lng,
            lat=row.lat,
            nearby_count=nearby_count,
            nearest_substation_name=nearest_name,
            nearest_substation_dist_m=nearest_dist_m,
        )

    except HTTPException:
        raise
    except SQLAlchemyError as e:
        logger.error(f"/api/facilities/{facility_id} DB 오류: {e}")
        raise HTTPException(status_code=503, detail=_DB_ERROR_RESPONSE)
