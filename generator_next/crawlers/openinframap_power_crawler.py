"""
OpenInfraMap(OSM) 한국 송·변전 인프라 크롤러 (비동기)

Overpass API를 통해 한국의 변전소·송전선 데이터를 시도별로 수집한다.
OpenInfraMap이 보여주는 데이터와 동일한 OSM 원본이다.

수집 대상:
  - power=substation  (변전소: 송전·배전·전환 등)
  - power=line         (송전선: 고압 송전)
  - power=minor_line   (배전선: 저압 배전)
  - power=cable        (지중·해저 케이블)
"""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime
from pathlib import Path

import aiohttp

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

SIDOS: dict[str, str] = {
    "서울특별시": "Seoul",
     "부산광역시": "Busan",
     "대구광역시": "Daegu",
     "인천광역시": "Incheon",
     "광주광역시": "Gwangju",
     "대전광역시": "Daejeon",
     "울산광역시": "Ulsan",
     "세종특별자치시": "Sejong",
     "경기도": "Gyeonggi",
     "충청북도": "Chungbuk",
     "충청남도": "Chungnam",
     "전라남도": "Jeonnam",
     "경상북도": "Gyeongbuk",
     "경상남도": "Gyeongnam",
     "제주특별자치도": "Jeju",
     "강원특별자치도": "Gangwon",
     "전북특별자치도": "Jeonbuk",
}

# Overpass rate limit 대응
MAX_CONCURRENCY = 2
REQUEST_DELAY = 6  # 초


def _substation_query(sido: str) -> str:
    return f"""
[out:json][timeout:120];
area["name"="{sido}"]["admin_level"="4"]->.sido;
(
  node["power"="substation"](area.sido);
  way["power"="substation"](area.sido);
  relation["power"="substation"](area.sido);
);
out tags center;
"""


def _line_query(sido: str) -> str:
    return f"""
[out:json][timeout:180];
area["name"="{sido}"]["admin_level"="4"]->.sido;
(
  way["power"="line"](area.sido);
  relation["power"="line"](area.sido);
  way["power"="minor_line"](area.sido);
  way["power"="cable"](area.sido);
  relation["power"="cable"](area.sido);
);
out geom;
"""


def _parse_substation(el: dict, sido: str) -> dict:
    """변전소 element → GeoJSON Feature (Point)."""
    tags = el.get("tags", {})
    center = el.get("center", {})
    lat = center.get("lat") or el.get("lat")
    lon = center.get("lon") or el.get("lon")
    return {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [lon, lat],
        },
        "properties": {
            "osm_type": el["type"],
            "osm_id": el["id"],
            "sido": sido,
            "name": tags.get("name", ""),
            "name_en": tags.get("name:en", ""),
            "substation_type": tags.get("substation", ""),
            "voltage": tags.get("voltage", ""),
            "frequency": tags.get("frequency", ""),
            "operator": tags.get("operator", ""),
            "location": tags.get("location", ""),
        },
    }


def _parse_line(el: dict, sido: str) -> list[dict]:
    """송전선/배전선/케이블 element → GeoJSON Feature 리스트.

    way  → geometry 필드에 [{lat,lon}, ...] → LineString 1개
    relation → members 안 way별 geometry → LineString 여러 개
    """
    tags = el.get("tags", {})
    props = {
        "osm_type": el["type"],
        "osm_id": el["id"],
        "sido": sido,
        "power_type": tags.get("power", ""),
        "name": tags.get("name", ""),
        "description": tags.get("description", ""),
        "voltage": tags.get("voltage", ""),
        "cables": tags.get("cables", ""),
        "circuits": tags.get("circuits", ""),
        "frequency": tags.get("frequency", ""),
        "operator": tags.get("operator", ""),
        "wires": tags.get("wires", ""),
    }

    if el["type"] == "way":
        geom = el.get("geometry", [])
        coordinates = [[pt["lon"], pt["lat"]] for pt in geom] if geom else []
        if not coordinates:
            return []
        return [{
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": coordinates},
            "properties": props,
        }]

    # relation: members 안 way들의 geometry를 각각 LineString으로
    features: list[dict] = []
    for member in el.get("members", []):
        member_geom = member.get("geometry", [])
        if not member_geom:
            continue
        coordinates = [[pt["lon"], pt["lat"]] for pt in member_geom]
        features.append({
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": coordinates},
            "properties": props,
        })
    return features


async def _query_overpass(
    session: aiohttp.ClientSession,
    sem: asyncio.Semaphore,
    query: str,
    max_retries: int = 3,
) -> list[dict]:
    """Overpass API에 쿼리를 보내고 elements를 반환한다. rate limit 시 재시도."""
    async with sem:
        for attempt in range(max_retries):
            try:
                async with session.post(
                    OVERPASS_URL, data={"data": query}
                ) as resp:
                    if resp.status == 429 or resp.status == 504:
                        wait = 15 * (attempt + 1)
                        print(f"    rate limited({resp.status}), {wait}s 대기...")
                        await asyncio.sleep(wait)
                        continue
                    resp.raise_for_status()
                    text = await resp.text()
                    if not text.strip():
                        wait = 10 * (attempt + 1)
                        print(f"    빈 응답, {wait}s 대기 후 재시도...")
                        await asyncio.sleep(wait)
                        continue
                    data = json.loads(text)
                    return data.get("elements", [])
            except (aiohttp.ClientError, json.JSONDecodeError) as e:
                wait = 10 * (attempt + 1)
                print(f"    오류({e}), {wait}s 대기 후 재시도...")
                await asyncio.sleep(wait)

        print("    최대 재시도 초과, 빈 결과 반환")
        return []


async def crawl_sido_infra(
    session: aiohttp.ClientSession,
    sem: asyncio.Semaphore,
    sido: str,
) -> tuple[list[dict], list[dict]]:
    """단일 시도의 변전소 + 송전선 데이터를 수집한다."""
    print(f"  {sido} 변전소 조회 중...")
    sub_els = await _query_overpass(session, sem, _substation_query(sido))
    substations = [_parse_substation(el, sido) for el in sub_els]
    print(f"  {sido} 변전소: {len(substations)}건")

    await asyncio.sleep(REQUEST_DELAY)

    print(f"  {sido} 송·배전선/케이블 조회 중...")
    line_els = await _query_overpass(session, sem, _line_query(sido))
    lines: list[dict] = []
    for el in line_els:
        lines.extend(_parse_line(el, sido))
    print(f"  {sido} 송·배전선/케이블: {len(lines)}건")

    await asyncio.sleep(REQUEST_DELAY)

    return substations, lines


async def crawl_all(
    concurrency: int = MAX_CONCURRENCY,
    sido_filter: str | None = None,
) -> tuple[list[dict], list[dict]]:
    """전국 송·변전 인프라 데이터를 수집한다."""
    sem = asyncio.Semaphore(concurrency)
    timeout = aiohttp.ClientTimeout(total=300)

    target = {sido_filter: SIDOS.get(sido_filter, "")} if sido_filter else SIDOS

    all_substations: list[dict] = []
    all_lines: list[dict] = []

    async with aiohttp.ClientSession(timeout=timeout) as session:
        # Overpass rate limit 때문에 시도를 순차 처리
        for sido in target:
            subs, lines = await crawl_sido_infra(session, sem, sido)
            all_substations.extend(subs)
            all_lines.extend(lines)

    print(f"\n수집 완료: 변전소 {len(all_substations)}건, 송·배전선/케이블 {len(all_lines)}건")
    return all_substations, all_lines


def save_geojson(features: list[dict], path: Path) -> None:
    """GeoJSON FeatureCollection으로 저장한다."""
    if not features:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    collection = {
        "type": "FeatureCollection",
        "features": features,
    }
    with path.open("w", encoding="utf-8") as f:
        json.dump(collection, f, ensure_ascii=False, indent=2)
    print(f"저장: {path} ({len(features)}건)")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="OpenInfraMap(OSM) 한국 송·변전 인프라 크롤러"
    )
    parser.add_argument(
        "--sido",
        default=None,
        help="특정 시도만 수집 (예: 인천광역시)",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=MAX_CONCURRENCY,
        help=f"동시 요청 수 (기본: {MAX_CONCURRENCY})",
    )
    parser.add_argument(
        "--output-dir",
        default="generator_next/data/openinframap",
        help="출력 디렉토리",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    substations, lines = asyncio.run(
        crawl_all(concurrency=args.concurrency, sido_filter=args.sido)
    )

    suffix = f"_{args.sido}" if args.sido else ""
    save_geojson(substations, output_dir / f"substations_{timestamp}{suffix}.geojson")
    save_geojson(lines, output_dir / f"power_lines_{timestamp}{suffix}.geojson")


if __name__ == "__main__":
    main()
