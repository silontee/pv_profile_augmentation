"""
환경부 EGIS WFS 토지피복지도 오프라인 다운로더.
시도별 bbox로 분할 요청 → GeoJSON 저장.

사용:
    uv run python src/crawlers/land_cover_crawler.py
    uv run python src/crawlers/land_cover_crawler.py --sido 서울 경기
    uv run python src/crawlers/land_cover_crawler.py --layer lv3_2025y
    uv run python src/crawlers/land_cover_crawler.py --out-dir src/data/landcover
"""

import argparse
import json
import time
from pathlib import Path

import requests

WFS_URL  = "https://api.mcee.go.kr/geoserver/wfs"
PAGE_SIZE = 5_000

# 시도별 bbox (xmin, ymin, xmax, ymax) — EPSG:4326
SIDO_BBOX: dict[str, tuple[float, float, float, float]] = {
    "서울":  (126.734, 37.413, 127.269, 37.715),
    "부산":  (128.739, 34.876, 129.316, 35.396),
    "대구":  (128.401, 35.658, 128.757, 36.000),
    "인천":  (126.148, 37.155, 126.978, 37.803),
    "광주":  (126.793, 35.060, 127.017, 35.269),
    "대전":  (127.253, 36.196, 127.601, 36.534),
    "울산":  (128.959, 35.440, 129.417, 35.811),
    "세종":  (127.099, 36.432, 127.454, 36.741),
    "경기":  (126.335, 36.886, 127.887, 38.058),
    "강원":  (127.052, 37.002, 129.341, 38.620),
    "충북":  (127.293, 36.234, 128.533, 37.255),
    "충남":  (125.876, 35.943, 127.497, 37.004),
    "전북":  (126.236, 35.383, 127.869, 36.248),
    "전남":  (125.028, 33.910, 127.817, 35.435),
    "경북":  (127.978, 35.544, 129.601, 37.345),
    "경남":  (127.597, 34.606, 129.420, 35.710),
    "제주":  (126.149, 33.106, 126.985, 33.617),
}


def fetch_sido(sido: str, bbox: tuple, layer: str, out_dir: Path) -> None:
    xmin, ymin, xmax, ymax = bbox
    bbox_str = f"{xmin},{ymin},{xmax},{ymax},EPSG:4326"
    features: list = []
    start = 0

    print(f"[{sido}] 다운로드 시작 (layer={layer})")
    while True:
        params = {
            "service":      "WFS",
            "version":      "2.0.0",
            "request":      "GetFeature",
            "typeName":     f"EGIS:{layer}",
            "outputFormat": "application/json",
            "srsName":      "EPSG:4326",
            "bbox":         bbox_str,
            "count":        PAGE_SIZE,
            "startIndex":   start,
        }
        try:
            resp = requests.get(WFS_URL, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"  [오류] {sido} startIndex={start}: {e}")
            break

        batch = data.get("features", [])
        features.extend(batch)
        print(f"  [{sido}] {start} ~ {start + len(batch)} ({len(features)} 누적)")

        if len(batch) < PAGE_SIZE:
            break
        start += PAGE_SIZE
        time.sleep(0.5)

    out_path = out_dir / f"{sido}_{layer}.geojson"
    geojson = {
        "type": "FeatureCollection",
        "features": features,
    }
    out_path.write_text(json.dumps(geojson, ensure_ascii=False), encoding="utf-8")
    print(f"  [{sido}] 저장 완료: {out_path} ({len(features)}건)")


def main() -> None:
    parser = argparse.ArgumentParser(description="EGIS 토지피복 WFS 다운로더")
    parser.add_argument("--sido", nargs="+", default=list(SIDO_BBOX.keys()),
                        help="수집할 시도 목록 (기본: 전국)")
    parser.add_argument("--layer", default="lv2_2025y",
                        choices=["lv2_2025y", "lv3_2025y"],
                        help="레이어 (중분류: lv2, 세분류: lv3)")
    parser.add_argument("--out-dir", default="src/data/landcover",
                        help="출력 디렉토리")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    for sido in args.sido:
        if sido not in SIDO_BBOX:
            print(f"[경고] 알 수 없는 시도: {sido} (스킵)")
            continue
        fetch_sido(sido, SIDO_BBOX[sido], args.layer, out_dir)
        time.sleep(1.0)

    print("전체 완료.")


if __name__ == "__main__":
    main()
