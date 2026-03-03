"""
recloud.energy.or.kr 태양광 발전소 현황 크롤러 (비동기)

RPS 발전설비 이용률 페이지에서 전국/광역시도/시군구 단위
태양광 발전소 개소·설비용량·이용률 데이터를 수집한다.

데이터 흐름:
  1) 메인 페이지(main01.do) → 17개 광역시도 + 전국 집계 (JSONP)
  2) area_code/gugun.do   → 시군구 5자리 코드 목록
  3) main_cgg_power01.do  → 시군구별 발전소 현황
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote_plus

import aiohttp

BASE_URL = "https://recloud.energy.or.kr"
MAIN_PAGE = f"{BASE_URL}/rps/main/main01.do"
GUGUN_API = f"{BASE_URL}/area_code/gugun.do"
CGG_POWER_API = f"{BASE_URL}/rps/main/main_cgg_power01.do"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "X-Requested-With": "XMLHttpRequest",
    "Referer": MAIN_PAGE,
    "Origin": BASE_URL,
}

SIDO_CODES: dict[str, str] = {
    "11": "서울특별시",
    "26": "부산광역시",
    "27": "대구광역시",
    "28": "인천광역시",
    "29": "광주광역시",
    "30": "대전광역시",
    "31": "울산광역시",
    "36": "세종특별자치시",
    "41": "경기도",
    "43": "충청북도",
    "44": "충청남도",
    "46": "전라남도",
    "47": "경상북도",
    "48": "경상남도",
    "50": "제주특별자치도",
    "51": "강원특별자치도",
    "52": "전북특별자치도",
}

# 동시 요청 제한 (서버 부하 방지)
MAX_CONCURRENCY = 5

# "시+구" 형태 도시: 구 단위 코드로는 데이터가 없고 시 단위 코드(끝 0)로 합산 조회해야 함
# key = 상위 시 코드, value = 해당 시의 구 코드 접두사 (이 접두사로 시작하면 합산 대상)
CITY_WITH_GU: dict[str, str] = {
    "41110": "4111",   # 수원시
    "41130": "4113",   # 성남시
    "41170": "4117",   # 안양시
    "41270": "4127",   # 안산시
    "41280": "4128",   # 고양시
    "41460": "4146",   # 용인시
    "43110": "4311",   # 청주시
    "44130": "4413",   # 천안시
    "47110": "4711",   # 포항시
    "48120": "4812",   # 창원시
    "52110": "5211",   # 전주시
}

# 구 코드 → 상위 시 코드 역매핑 (자동 생성)
_GU_TO_CITY: dict[str, str] = {}
for city_code, prefix in CITY_WITH_GU.items():
    # 구 코드는 접두사 + 1~9 (예: 41111, 41113, ...)
    for suffix in range(1, 10):
        _GU_TO_CITY[prefix + str(suffix)] = city_code

# area_code API와 power API 간 코드 불일치 보정
# key = area_code API가 주는 코드, value = (power API 코드, sido_code)
CODE_REMAP: dict[str, tuple[str, str]] = {
    "47720": ("27720", "27"),  # 군위군: 2023년 대구 편입, power API는 대구(27) 코드 사용
}


async def fetch_sido_summary(session: aiohttp.ClientSession) -> list[dict]:
    """메인 페이지 JSONP에서 전국 + 17개 광역시도 집계 데이터를 파싱한다."""
    async with session.get(MAIN_PAGE) as resp:
        resp.raise_for_status()
        html = await resp.text()

    match = re.search(r"main_power\(\s*(\[.*?\])\s*\)", html, re.DOTALL)
    if not match:
        raise RuntimeError("main_power JSONP 데이터를 찾을 수 없습니다.")

    raw: list[dict] = json.loads(match.group(1))
    return [
        {
            "rgn_code": item.get("RGN_CODE", ""),
            "rgn_name": item.get("RGN_CODE_NM", ""),
            "cnt": item.get("CNT", 0),
            "cnt_ratio": item.get("CNT_RATIO", ""),
            "fac_tot_mw": item.get("FAC_TOT_MW", ""),
            "fac_tot_ratio": item.get("FAC_TOT_RATIO", ""),
            "avg_use_rate": item.get("AVG_USE_RATE", 0),
        }
        for item in raw
    ]


async def fetch_gugun_codes(
    session: aiohttp.ClientSession, sido_code: str
) -> list[dict[str, str]]:
    """sido_code(2자리)에 속하는 시군구 5자리 코드와 이름 목록을 반환한다."""
    async with session.post(GUGUN_API, data={"sido_code": sido_code}) as resp:
        resp.raise_for_status()
        text = await resp.text()

    decoded = unquote_plus(text)
    items = re.findall(r"value='(\d+)'\s*>([^<]+)<", decoded)
    return [{"code": code, "name": name.strip()} for code, name in items]


async def fetch_gugun_power(
    session: aiohttp.ClientSession,
    sem: asyncio.Semaphore,
    sido_code: str,
    sido_name: str,
    gugun_code: str,
    gugun_name: str,
) -> dict | None:
    """시군구 1건의 발전소 현황을 가져와 결과 dict로 반환한다."""
    async with sem:
        async with session.post(
            CGG_POWER_API, data={"code": sido_code, "code2": gugun_code}
        ) as resp:
            resp.raise_for_status()
            text = (await resp.text()).strip()

    if not text:
        print(f"    [skip] {gugun_name}({gugun_code}): 데이터 없음")
        return None

    decoded = unquote_plus(text)
    arr = json.loads(decoded)
    if not arr:
        return None

    power = arr[0]
    print(f"    {gugun_name}: 개소={power.get('cnt')}, 용량={power.get('inst_capa')}kW")
    return {
        "sido_code": sido_code,
        "sido_name": sido_name,
        "gugun_code": gugun_code,
        "gugun_name": gugun_name,
        "cnt": power.get("cnt", ""),
        "inst_capa": power.get("inst_capa", ""),
        "gelec_qty": power.get("gelec_qty", ""),
        "cnt_ratio": power.get("poplnt_cnt_cmp_view", ""),
        "capa_ratio": power.get("poplnt_inst_capa_cmp_view", ""),
        "gelec_diff": power.get("gelec_qty_cmp_view", ""),
    }


async def crawl_sido(
    session: aiohttp.ClientSession,
    sem: asyncio.Semaphore,
    sido_code: str,
    sido_name: str,
) -> list[dict]:
    """단일 광역시도 내 모든 시군구를 비동기로 수집한다.

    "시+구" 형태 도시(수원시, 청주시 등)는 구 단위 코드 대신
    상위 시 코드로 합산 조회하여 중복 없이 1건만 반환한다.
    """
    guguns = await fetch_gugun_codes(session, sido_code)

    # 구 코드를 시 코드로 치환하고, 코드 불일치를 보정하며, 중복 제거
    seen_city_codes: set[str] = set()
    deduped: list[dict[str, str]] = []
    for g in guguns:
        code = g["code"]
        name = g["name"]

        # 1) "시+구" 도시 → 상위 시 코드로 합산
        city_code = _GU_TO_CITY.get(code)
        if city_code:
            if city_code in seen_city_codes:
                continue
            seen_city_codes.add(city_code)
            parts = name.split()
            deduped.append({
                "code": city_code,
                "name": parts[0] if len(parts) > 1 else name,
                "sido_override": sido_code,
            })
            continue

        # 2) 코드 불일치 보정 (예: 군위군 경북→대구)
        if code in CODE_REMAP:
            remapped_code, remapped_sido = CODE_REMAP[code]
            deduped.append({
                "code": remapped_code,
                "name": name,
                "sido_override": remapped_sido,
            })
            continue

        # 3) 일반 시군구
        deduped.append({"code": code, "name": name, "sido_override": sido_code})

    print(f"  {sido_name}({sido_code}): {len(guguns)}개 행정구역 -> {len(deduped)}개 조회 단위")

    tasks = [
        fetch_gugun_power(
            session, sem,
            g["sido_override"], sido_name,
            g["code"], g["name"],
        )
        for g in deduped
    ]
    results = await asyncio.gather(*tasks)
    return [r for r in results if r is not None]


async def crawl_all(
    concurrency: int = MAX_CONCURRENCY,
    sido_filter: str | None = None,
) -> tuple[list[dict], list[dict]]:
    """
    전국 태양광 발전소 데이터를 비동기로 수집한다.

    Args:
        concurrency: 동시 요청 수 제한.
        sido_filter: 특정 광역시도만 수집할 때 2자리 코드 (예: "28").

    Returns:
        (sido_rows, gugun_rows) 두 리스트.
    """
    sem = asyncio.Semaphore(concurrency)
    timeout = aiohttp.ClientTimeout(total=60)

    async with aiohttp.ClientSession(headers=HEADERS, timeout=timeout) as session:
        # 1) 광역시도 집계
        print("[1/2] 광역시도 집계 수집 중...")
        sido_rows = await fetch_sido_summary(session)
        print(f"  -> {len(sido_rows)}개 지역 수집 완료")

        # 2) 시군구별 데이터 (광역시도 단위로 병렬)
        print("[2/2] 시군구별 데이터 수집 중...")
        target = (
            {sido_filter: SIDO_CODES.get(sido_filter, "")}
            if sido_filter
            else SIDO_CODES
        )

        sido_tasks = [
            crawl_sido(session, sem, code, name)
            for code, name in target.items()
        ]
        sido_results = await asyncio.gather(*sido_tasks)
        gugun_rows = [row for batch in sido_results for row in batch]

    print(f"\n수집 완료: 광역 {len(sido_rows)}건, 시군구 {len(gugun_rows)}건")
    return sido_rows, gugun_rows


def save_csv(rows: list[dict], path: Path) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"저장: {path} ({len(rows)}건)")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="recloud.energy.or.kr 태양광 발전소 현황 크롤러 (비동기)"
    )
    parser.add_argument(
        "--sido",
        default=None,
        help="특정 광역시도만 수집 (2자리 코드, 예: 28=인천)",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=MAX_CONCURRENCY,
        help=f"동시 요청 수 제한 (기본: {MAX_CONCURRENCY})",
    )
    parser.add_argument(
        "--output-dir",
        default="src/data/recloud",
        help="출력 디렉토리 (기본: src/data/recloud)",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    _, gugun_rows = asyncio.run(
        crawl_all(concurrency=args.concurrency, sido_filter=args.sido)
    )

    suffix = f"_{args.sido}" if args.sido else ""
    save_csv(gugun_rows, output_dir / f"rps_{timestamp}{suffix}.csv")


if __name__ == "__main__":
    main()
