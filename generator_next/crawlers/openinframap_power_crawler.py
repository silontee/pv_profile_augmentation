"""
OpenInfraMap(OSM) 한국 송·변전 인프라 크롤러 (비동기)

Overpass API를 통해 한국의 변전소·송전선 데이터를 시도별로 수집한다.
OpenInfraMap이 보여주는 데이터와 동일한 OSM 원본이다.

수집 대상:
  - power=substation  (변전소: 송전·배전·전환 등)
  - power=line         (송전선: 고압 송전)
  - power=minor_line   (배전선: 저압 배전)
  - power=cable        (지중·해저 케이블)
  - power=plant        (발전소)
  - power=generator    (발전기)
"""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime
from pathlib import Path

import aiohttp

# 공개 Overpass API 미러 목록 — 각 미러는 독립적인 rate limit을 가진다.
# 시도를 미러별로 분배하면 병렬 수집이 가능하다.
OVERPASS_MIRRORS: list[str] = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]

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

# 미러당 동시 요청 제한 (각 미러에 semaphore 1개씩)
REQUEST_DELAY = 3  # 같은 미러 내 연속 요청 간격(초)


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


def _plant_query(sido: str) -> str:
    return f"""
[out:json][timeout:180];
area["name"="{sido}"]["admin_level"="4"]->.sido;
(
  node["power"="plant"](area.sido);
  way["power"="plant"](area.sido);
  relation["power"="plant"](area.sido);
  node["power"="generator"](area.sido);
  way["power"="generator"](area.sido);
);
out tags center;
"""


def _parse_plant(el: dict, sido: str) -> dict:
    """발전소/발전기 element → GeoJSON Feature (Point)."""
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
            "power_type": tags.get("power", ""),
            "name": tags.get("name", ""),
            "name_en": tags.get("name:en", ""),
            "plant_source": tags.get("plant:source", tags.get("generator:source", "")),
            "plant_output": tags.get("plant:output:electricity", tags.get("generator:output:electricity", "")),
            "plant_method": tags.get("plant:method", tags.get("generator:method", "")),
            "operator": tags.get("operator", ""),
        },
    }


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
    mirror_url: str,
    query: str,
    max_retries: int = 3,
) -> list[dict]:
    """Overpass API에 쿼리를 보내고 elements를 반환한다. rate limit 시 재시도."""
    mirror_name = mirror_url.split("/")[2]
    async with sem:
        for attempt in range(max_retries):
            try:
                async with session.post(
                    mirror_url, data={"data": query}
                ) as resp:
                    if resp.status == 429 or resp.status == 504:
                        wait = 15 * (attempt + 1)
                        print(f"    [{mirror_name}] rate limited({resp.status}), {wait}s 대기...")
                        await asyncio.sleep(wait)
                        continue
                    resp.raise_for_status()
                    text = await resp.text()
                    if not text.strip():
                        wait = 10 * (attempt + 1)
                        print(f"    [{mirror_name}] 빈 응답, {wait}s 대기 후 재시도...")
                        await asyncio.sleep(wait)
                        continue
                    data = json.loads(text)
                    return data.get("elements", [])
            except (aiohttp.ClientError, json.JSONDecodeError) as e:
                wait = 10 * (attempt + 1)
                print(f"    [{mirror_name}] 오류({e}), {wait}s 대기 후 재시도...")
                await asyncio.sleep(wait)

        print(f"    [{mirror_name}] 최대 재시도 초과, 빈 결과 반환")
        return []


async def crawl_sido_infra(
    session: aiohttp.ClientSession,
    sem: asyncio.Semaphore,
    mirror_url: str,
    sido: str,
) -> tuple[list[dict], list[dict], list[dict]]:
    """단일 시도의 변전소 + 송전선 + 발전소 데이터를 수집한다."""
    mirror_name = mirror_url.split("/")[2]
    print(f"  [{mirror_name}] {sido} 변전소 조회 중...")
    sub_els = await _query_overpass(session, sem, mirror_url, _substation_query(sido))
    substations = [_parse_substation(el, sido) for el in sub_els]
    print(f"  [{mirror_name}] {sido} 변전소: {len(substations)}건")

    await asyncio.sleep(REQUEST_DELAY)

    print(f"  [{mirror_name}] {sido} 송·배전선/케이블 조회 중...")
    line_els = await _query_overpass(session, sem, mirror_url, _line_query(sido))
    lines: list[dict] = []
    for el in line_els:
        lines.extend(_parse_line(el, sido))
    print(f"  [{mirror_name}] {sido} 송·배전선/케이블: {len(lines)}건")

    await asyncio.sleep(REQUEST_DELAY)

    print(f"  [{mirror_name}] {sido} 발전소/발전기 조회 중...")
    plant_els = await _query_overpass(session, sem, mirror_url, _plant_query(sido))
    plants = [_parse_plant(el, sido) for el in plant_els]
    print(f"  [{mirror_name}] {sido} 발전소/발전기: {len(plants)}건")

    await asyncio.sleep(REQUEST_DELAY)

    return substations, lines, plants


def _sido_filename(sido: str) -> str:
    """시도 이름 → 파일명에 쓸 수 있는 영문 키."""
    return SIDOS.get(sido, sido).lower()


def _find_collected_sidos(output_dir: Path) -> set[str]:
    """이미 수집 완료된 시도 목록을 반환한다.

    by_sido/ 디렉토리에 substations, power_lines, plants 3종이
    모두 존재하는 시도만 수집 완료로 판정한다.
    """
    sido_dir = output_dir / "by_sido"
    if not sido_dir.is_dir():
        return set()

    sub_files = {p.stem.replace("substations_", "") for p in sido_dir.glob("substations_*.geojson")}
    line_files = {p.stem.replace("power_lines_", "") for p in sido_dir.glob("power_lines_*.geojson")}
    plant_files = {p.stem.replace("plants_", "") for p in sido_dir.glob("plants_*.geojson")}
    collected_keys = sub_files & line_files & plant_files

    # 영문 key → 한글 시도 역매핑
    en_to_kr = {v.lower(): k for k, v in SIDOS.items()}
    return {en_to_kr[k] for k in collected_keys if k in en_to_kr}


async def crawl_all(
    sido_filter: str | None = None,
    output_dir: Path | None = None,
    force: bool = False,
) -> tuple[list[dict], list[dict], list[dict]]:
    """전국 송·변전·발전 인프라 데이터를 미러별 병렬로 수집한다.

    시도 목록을 미러 수만큼 그룹으로 나누고,
    각 그룹은 전담 미러에 순차 요청 / 그룹 간에는 동시 실행.
    이미 수집된 시도는 스킵한다 (--force 로 재수집 가능).
    """
    timeout = aiohttp.ClientTimeout(total=600)

    all_target = list({sido_filter: SIDOS.get(sido_filter, "")} if sido_filter else SIDOS)

    # 이미 수집된 시도 스킵
    skipped: list[str] = []
    if not force and output_dir:
        collected = _find_collected_sidos(output_dir)
        target = [s for s in all_target if s not in collected]
        skipped = [s for s in all_target if s in collected]
    else:
        target = all_target

    if skipped:
        print(f"이미 수집된 시도 스킵({len(skipped)}개): {', '.join(skipped)}")

    if not target:
        print("모든 시도가 이미 수집되었습니다. (재수집: --force)")
        return _load_existing(output_dir) if output_dir else ([], [], [])

    mirrors = OVERPASS_MIRRORS
    n_mirrors = len(mirrors)

    # 시도를 미러 수만큼 라운드로빈 분배
    groups: list[list[str]] = [[] for _ in range(n_mirrors)]
    for i, sido in enumerate(target):
        groups[i % n_mirrors].append(sido)

    # 미러별 semaphore (미러당 동시 1개 요청)
    sems = [asyncio.Semaphore(1) for _ in range(n_mirrors)]

    print(f"\n미러 {n_mirrors}개로 시도 {len(target)}개 병렬 수집 시작")
    for idx, (mirror, group) in enumerate(zip(mirrors, groups)):
        if not group:
            continue
        mirror_name = mirror.split("/")[2]
        print(f"  미러{idx + 1} [{mirror_name}]: {', '.join(group)}")

    sido_dir = output_dir / "by_sido" if output_dir else None

    async def _worker(
        session: aiohttp.ClientSession,
        mirror_url: str,
        sem: asyncio.Semaphore,
        sidos: list[str],
    ) -> tuple[list[dict], list[dict], list[dict]]:
        subs_all: list[dict] = []
        lines_all: list[dict] = []
        plants_all: list[dict] = []
        for sido in sidos:
            subs, lines, plants = await crawl_sido_infra(session, sem, mirror_url, sido)
            subs_all.extend(subs)
            lines_all.extend(lines)
            plants_all.extend(plants)
            # 시도별 즉시 저장 (중간 중단 대비)
            if sido_dir:
                key = _sido_filename(sido)
                save_geojson(subs, sido_dir / f"substations_{key}.geojson")
                save_geojson(lines, sido_dir / f"power_lines_{key}.geojson")
                save_geojson(plants, sido_dir / f"plants_{key}.geojson")
        return subs_all, lines_all, plants_all

    all_substations: list[dict] = []
    all_lines: list[dict] = []
    all_plants: list[dict] = []

    async with aiohttp.ClientSession(timeout=timeout) as session:
        tasks = [
            _worker(session, mirror, sem, group)
            for mirror, sem, group in zip(mirrors, sems, groups)
            if group
        ]
        results = await asyncio.gather(*tasks)

        for subs, lines, plants in results:
            all_substations.extend(subs)
            all_lines.extend(lines)
            all_plants.extend(plants)

    # 스킵된 시도의 기존 데이터도 합산
    if skipped and output_dir:
        exist_subs, exist_lines, exist_plants = _load_existing_sidos(output_dir, skipped)
        all_substations.extend(exist_subs)
        all_lines.extend(exist_lines)
        all_plants.extend(exist_plants)

    print(
        f"\n수집 완료: 변전소 {len(all_substations)}건, "
        f"송·배전선/케이블 {len(all_lines)}건, "
        f"발전소/발전기 {len(all_plants)}건"
    )
    return all_substations, all_lines, all_plants


def _load_existing(output_dir: Path) -> tuple[list[dict], list[dict], list[dict]]:
    """by_sido/ 디렉토리의 모든 기존 데이터를 로드한다."""
    return _load_existing_sidos(output_dir, list(SIDOS.keys()))


def _load_existing_sidos(
    output_dir: Path, sidos: list[str]
) -> tuple[list[dict], list[dict], list[dict]]:
    """지정된 시도들의 기존 per-sido 파일을 로드한다."""
    sido_dir = output_dir / "by_sido"
    all_subs: list[dict] = []
    all_lines: list[dict] = []
    all_plants: list[dict] = []
    for sido in sidos:
        key = _sido_filename(sido)
        for prefix, target in [
            ("substations_", all_subs),
            ("power_lines_", all_lines),
            ("plants_", all_plants),
        ]:
            path = sido_dir / f"{prefix}{key}.geojson"
            if path.exists():
                with path.open(encoding="utf-8") as f:
                    target.extend(json.load(f).get("features", []))
    if all_subs or all_lines or all_plants:
        print(
            f"기존 데이터 로드: 변전소 {len(all_subs)}건, "
            f"송·배전선/케이블 {len(all_lines)}건, "
            f"발전소/발전기 {len(all_plants)}건"
        )
    return all_subs, all_lines, all_plants


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
        "--output-dir",
        default="generator_next/source/openinframap",
        help="출력 디렉토리",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="이미 수집된 시도도 재수집",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    substations, lines, plants = asyncio.run(
        crawl_all(sido_filter=args.sido, output_dir=output_dir, force=args.force)
    )

    # 전체 합본 저장
    suffix = f"_{args.sido}" if args.sido else ""
    save_geojson(substations, output_dir / f"substations_{timestamp}{suffix}.geojson")
    save_geojson(lines, output_dir / f"power_lines_{timestamp}{suffix}.geojson")
    save_geojson(plants, output_dir / f"plants_{timestamp}{suffix}.geojson")


if __name__ == "__main__":
    main()
