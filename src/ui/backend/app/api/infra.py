"""
인프라 엔드포인트.
- GET /api/substations/bbox  bbox 내 변전소
- GET /api/power-lines/bbox  bbox 내 송배전선 (bbox 필수 — 없으면 400)
- GET /api/boundaries        시군구 경계 GeoJSON (정적 파일 서빙)
"""
import logging
import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import get_db
from app.schemas import PowerLineBboxResponse, PowerLineItem, SubstationBboxResponse, SubstationItem

logger = logging.getLogger(__name__)

router = APIRouter(tags=["infra"])

# 시군구 경계 GeoJSON 파일 경로
# Docker: BOUNDARIES_PATH 환경변수, 로컬: parents[5] 기반 경로
_boundaries_env = os.getenv("BOUNDARIES_PATH")
if _boundaries_env:
    _BOUNDARIES_PATH = Path(_boundaries_env)
else:
    _BOUNDARIES_PATH = Path(__file__).parents[5] / "src" / "data" / "boundaries" / "sigungu_2018_simple.geojson"

# DB 장애 공통 응답
_DB_ERROR_RESPONSE = {"error": "서비스 일시 중단", "retry_after": 30}


@router.get("/substations/bbox", response_model=SubstationBboxResponse)
async def get_substations_bbox(
    xmin: float = Query(..., description="bbox 서쪽 경도"),
    ymin: float = Query(..., description="bbox 남쪽 위도"),
    xmax: float = Query(..., description="bbox 동쪽 경도"),
    ymax: float = Query(..., description="bbox 북쪽 위도"),
    db: AsyncSession = Depends(get_db),
):
    """
    바운딩박스 내 변전소 목록.
    PostGIS bbox 연산자(&&)로 공간 인덱스 활용.
    """
    try:
        stmt = text("""
            SELECT
                id, name, name_en, voltage, sub_type, frequency,
                operator, osm_id, sido,
                ST_X(geom) AS lng,
                ST_Y(geom) AS lat
            FROM substation
            WHERE geom && ST_MakeEnvelope(:xmin, :ymin, :xmax, :ymax, 4326)
            ORDER BY id
        """)
        result = await db.execute(
            stmt,
            {"xmin": xmin, "ymin": ymin, "xmax": xmax, "ymax": ymax},
        )
        rows = result.fetchall()

        items = [
            SubstationItem(
                id=row.id,
                name=row.name,
                name_en=row.name_en,
                voltage=row.voltage,
                sub_type=row.sub_type,
                frequency=row.frequency,
                operator=row.operator,
                osm_id=row.osm_id,
                sido=row.sido,
                lng=row.lng,
                lat=row.lat,
            )
            for row in rows
        ]
        return SubstationBboxResponse(items=items)

    except SQLAlchemyError as e:
        logger.error(f"/api/substations/bbox DB 오류: {e}")
        raise HTTPException(status_code=503, detail=_DB_ERROR_RESPONSE)


@router.get("/power-lines/bbox", response_model=PowerLineBboxResponse)
async def get_power_lines_bbox(
    xmin: Optional[float] = Query(None, description="bbox 서쪽 경도 (필수)"),
    ymin: Optional[float] = Query(None, description="bbox 남쪽 위도 (필수)"),
    xmax: Optional[float] = Query(None, description="bbox 동쪽 경도 (필수)"),
    ymax: Optional[float] = Query(None, description="bbox 북쪽 위도 (필수)"),
    db: AsyncSession = Depends(get_db),
):
    """
    바운딩박스 내 송배전선 목록.
    bbox 파라미터가 하나라도 없으면 400 반환.
    LineString 좌표를 [[lng, lat], ...] 형태로 변환.
    """
    # bbox 필수 검증
    if any(v is None for v in [xmin, ymin, xmax, ymax]):
        raise HTTPException(
            status_code=400,
            detail="xmin, ymin, xmax, ymax 파라미터가 모두 필요합니다.",
        )

    try:
        # ST_AsGeoJSON으로 좌표 추출
        stmt = text("""
            SELECT
                id, name, power_type, voltage, sido,
                ST_AsGeoJSON(geom)::json -> 'coordinates' AS coordinates
            FROM power_line
            WHERE geom && ST_MakeEnvelope(:xmin, :ymin, :xmax, :ymax, 4326)
            ORDER BY id
        """)
        result = await db.execute(
            stmt,
            {"xmin": xmin, "ymin": ymin, "xmax": xmax, "ymax": ymax},
        )
        rows = result.fetchall()

        items = [
            PowerLineItem(
                id=row.id,
                name=row.name,
                power_type=row.power_type,
                voltage=row.voltage,
                sido=row.sido,
                # PostgreSQL JSON 반환값은 이미 파이썬 리스트
                coordinates=row.coordinates if row.coordinates is not None else [],
            )
            for row in rows
        ]
        return PowerLineBboxResponse(items=items)

    except SQLAlchemyError as e:
        logger.error(f"/api/power-lines/bbox DB 오류: {e}")
        raise HTTPException(status_code=503, detail=_DB_ERROR_RESPONSE)


@router.get("/boundaries")
async def get_boundaries():
    """
    시군구 경계 GeoJSON 정적 파일 서빙.
    파일이 없으면 404 반환.
    """
    if not _BOUNDARIES_PATH.exists():
        raise HTTPException(
            status_code=404,
            detail=f"경계 파일을 찾을 수 없습니다: {_BOUNDARIES_PATH}",
        )

    return FileResponse(
        path=str(_BOUNDARIES_PATH),
        media_type="application/geo+json",
        headers={
            # 브라우저 캐시 1시간 (경계 데이터는 자주 변경 안 됨)
            "Cache-Control": "public, max-age=3600",
        },
    )
