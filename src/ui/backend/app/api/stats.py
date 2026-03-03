"""
통계 엔드포인트.
- GET /api/stats   대시보드 요약 (캐시 TTL 60초)
"""
import logging
import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import get_db
from app.schemas import StatsResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["stats"])

# 인메모리 캐시 (TTL 60초)
_stats_cache: Optional[StatsResponse] = None
_stats_cache_time: float = 0.0
_CACHE_TTL = 60.0  # 초


@router.get("/stats", response_model=StatsResponse)
async def get_stats(
    db: AsyncSession = Depends(get_db),
):
    """
    대시보드 요약 통계.
    - 전체 발전소 수 / 가동상태별 집계
    - 총 설비용량 (MW)
    - 좌표 결측 건수
    - 시군구 수 (permit_org 기준)
    60초 인메모리 캐시 적용.
    """
    global _stats_cache, _stats_cache_time

    now = time.monotonic()

    # 캐시 유효 시 즉시 반환
    if _stats_cache is not None and (now - _stats_cache_time) < _CACHE_TTL:
        return _stats_cache

    try:
        stmt = text("""
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN status = '정상가동' THEN 1 ELSE 0 END) AS active,
                SUM(CASE WHEN status = '가동중단' THEN 1 ELSE 0 END) AS stopped,
                SUM(CASE WHEN status = '폐기'     THEN 1 ELSE 0 END) AS retired,
                SUM(CASE WHEN geom IS NULL        THEN 1 ELSE 0 END) AS no_coord,
                COALESCE(SUM(CAST(capacity_kw AS NUMERIC)) / 1000.0, 0) AS total_capacity_mw,
                COUNT(DISTINCT permit_org) AS sigungu_count
            FROM pv_facility
        """)
        result = await db.execute(stmt)
        row = result.fetchone()

        stats = StatsResponse(
            total=row.total,
            active=row.active,
            stopped=row.stopped,
            retired=row.retired,
            no_coord=row.no_coord,
            total_capacity_mw=float(row.total_capacity_mw),
            sigungu_count=row.sigungu_count,
        )

        # 캐시 갱신
        _stats_cache = stats
        _stats_cache_time = now

        return stats

    except SQLAlchemyError as e:
        logger.error(f"/api/stats DB 오류: {e}")
        raise HTTPException(
            status_code=503,
            detail={"error": "서비스 일시 중단", "retry_after": 30},
        )
