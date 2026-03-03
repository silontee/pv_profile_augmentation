"""
환경부 EGIS WFS 토지피복지도 프록시 엔드포인트.
브라우저에서 api.mcee.go.kr 직접 호출 시 CORS 차단 → 서버사이드 프록시.
"""
import logging
from typing import Any

import httpx
from fastapi import APIRouter, Query, HTTPException

logger = logging.getLogger(__name__)
router = APIRouter()

WFS_URL      = "https://api.mcee.go.kr/geoserver/wfs"
LAYER        = "EGIS:lv2_2025y"
MAX_FEATURES = 8_000

# 대분류 코드 1자리 → 색상
_CODE_COLOR: dict[str, str] = {
    "1": "#6b7280",  # 시가화건조지역
    "2": "#ca8a04",  # 농업지역
    "3": "#15803d",  # 산림지역
    "4": "#86efac",  # 초지
    "5": "#0e7490",  # 습지
    "6": "#92400e",  # 나지
    "7": "#1d4ed8",  # 수역
}


@router.get("/landcover")
async def get_landcover(
    xmin: float = Query(...),
    ymin: float = Query(...),
    xmax: float = Query(...),
    ymax: float = Query(...),
) -> Any:
    """
    bbox 내 토지피복 중분류 폴리곤 반환.
    각 Feature의 properties에 'color' 필드 추가.
    """
    bbox_str = f"{xmin},{ymin},{xmax},{ymax},EPSG:4326"
    params = {
        "service":      "WFS",
        "version":      "2.0.0",
        "request":      "GetFeature",
        "typeName":     LAYER,
        "outputFormat": "application/json",
        "srsName":      "EPSG:4326",
        "bbox":         bbox_str,
        "count":        MAX_FEATURES,
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(WFS_URL, params=params)
            resp.raise_for_status()
            geojson: dict[str, Any] = resp.json()
    except httpx.HTTPStatusError as e:
        logger.error(f"EGIS WFS HTTP 오류: {e.response.status_code}")
        raise HTTPException(status_code=502, detail="EGIS WFS 오류")
    except Exception as e:
        logger.error(f"EGIS WFS 요청 실패: {e}")
        raise HTTPException(status_code=502, detail="EGIS WFS 연결 실패")

    # 각 feature에 color 속성 추가
    for feat in geojson.get("features", []):
        props = feat.get("properties") or {}
        code = str(props.get("lcm_cd", ""))[:1]
        props["color"] = _CODE_COLOR.get(code, "#9ca3af")
        feat["properties"] = props

    return geojson
