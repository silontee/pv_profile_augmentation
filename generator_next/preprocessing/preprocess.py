"""
전처리 파이프라인: raw_csv → 필터링 → 지오코딩 → parquet 출력

사용법:
    uv run python generator_next/preprocessing/preprocess.py
    uv run python generator_next/preprocessing/preprocess.py --mode incremental
    uv run python generator_next/preprocessing/preprocess.py --no-geocode
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import re

import polars as pl
import requests

# ── 기본 경로 ────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RAW_CSV_DIR = ROOT / "generator_next/source/raw_csv"
DEFAULT_OUTPUT_DIR = ROOT / "generator_next/source/processed"
DEFAULT_CACHE_PATH = ROOT / "generator_next/source/logs/geocode/geocode_cache_kakao_raw.csv"
DEFAULT_FAILURES_PATH = ROOT / "generator_next/source/logs/geocode/geocode_failures_kakao_raw.csv"
DEFAULT_CRAWLER_STATE = ROOT / "generator_next/source/logs/crawler/pv_facility_profile_state.csv"

KAKAO_API_URL = "https://dapi.kakao.com/v2/local/search/address.json"

# 한국 좌표 유효 범위
LAT_MIN, LAT_MAX = 30.0, 45.0
LON_MIN, LON_MAX = 120.0, 135.0


# ── 주소 정제 ─────────────────────────────────────────────────────────────────

def clean_addr_for_geocode(addr: str) -> str:
    """Kakao API 전달 전 주소 노이즈 제거. 원본 데이터는 변경하지 않음."""
    addr = re.sub(r'\s*\([^)]*\)', '', addr)                            # 괄호 내용 제거
    addr = re.sub(r'\s*[-–]?\s*(토지위|토지|건물\s*위|부지\s*위)', '', addr)  # 주석 제거
    addr = re.sub(r'\s*(외|등)\s*\d+\s*필지', '', addr)                 # 외N필지 제거
    addr = re.sub(r'(\d+)번지\s*(\d+)호', r'\1-\2', addr)              # 번지N호 → N-M
    addr = re.sub(r'(\d+)\s*번지(?:\s+\d+(?:[-]\d+)*)?', r'\1', addr)  # 번지+뒤번호 제거
    addr = re.sub(r'\s*번지\b', '', addr)                                # 나머지 번지 제거
    if ',' in addr:
        addr = addr.split(',')[0]                                         # 다필지: 첫 번째만
    addr = re.sub(r'(\d+-\d+)\s+\d+-\d+(?:\s+\d+-\d+)*\s*$', r'\1', addr)  # 공백 다필지
    return addr.strip()


# ── 현재 시각 ─────────────────────────────────────────────────────────────────
def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().replace(microsecond=0).isoformat()


# ── Step 1. raw_csv 통합 + 필터링 ─────────────────────────────────────────────

def load_raw_csvs(raw_csv_dir: Path, target_files: list[Path] | None = None) -> pl.DataFrame:
    """raw_csv/ 내 CSV 파일을 읽어 통합 DataFrame 반환."""
    files = target_files if target_files is not None else sorted(raw_csv_dir.glob("*.csv"))
    if not files:
        print("[WARN] raw_csv 파일 없음.")
        return pl.DataFrame()

    frames = []
    for f in files:
        try:
            df = pl.read_csv(
                f,
                encoding="utf8-lossy",
                infer_schema_length=0,  # 모든 컬럼을 문자열로 읽기
                ignore_errors=True,
            )
            df = df.with_columns(pl.lit(f.name).alias("source_file"))
            frames.append(df)
        except Exception as e:
            print(f"[WARN] {f.name} 읽기 실패: {e}")

    if not frames:
        return pl.DataFrame()

    combined = pl.concat(frames, how="diagonal_relaxed")
    print(f"[INFO] 통합 행 수: {len(combined):,} ({len(frames)}개 파일)")
    return combined


def filter_and_cast(df: pl.DataFrame) -> pl.DataFrame:
    """위도/경도 float 변환. 가동상태 무관 전체 보존."""
    if df.is_empty():
        return df

    # 위도/경도: 빈 문자열 → null → float
    for col in ("위도", "경도"):
        if col in df.columns:
            df = df.with_columns(
                pl.when(pl.col(col).str.strip_chars() == "")
                .then(None)
                .otherwise(pl.col(col))
                .alias(col)
            ).with_columns(pl.col(col).cast(pl.Float64, strict=False))

    return df


# ── Step 2. 지오코딩 ──────────────────────────────────────────────────────────

def load_cache(cache_path: Path) -> dict[str, dict]:
    """기존 캐시 CSV를 dict 로 로드."""
    cache: dict[str, dict] = {}
    if not cache_path.exists():
        return cache
    try:
        with open(cache_path, encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                cache[row["geo_addr"]] = row
    except Exception as e:
        print(f"[WARN] 캐시 로드 실패: {e}")
    print(f"[INFO] 기존 캐시: {len(cache):,}건")
    return cache


def kakao_geocode(address: str, api_key: str) -> dict | None:
    """
    Kakao 주소 검색 API 호출.
    반환값: {"lon": float, "lat": float} 또는 None
    """
    try:
        resp = requests.get(
            KAKAO_API_URL,
            headers={"Authorization": f"KakaoAK {api_key}"},
            params={"query": address},
            timeout=10,
        )
        if resp.status_code == 400:
            return {"error": "http_400"}
        resp.raise_for_status()
        docs = resp.json().get("documents", [])
        if not docs:
            return None
        addr_info = docs[0].get("address") or docs[0].get("road_address")
        if not addr_info:
            return None
        lon = float(addr_info.get("x", 0))
        lat = float(addr_info.get("y", 0))
        # 좌표 유효성 검증
        if not (LAT_MIN <= lat <= LAT_MAX and LON_MIN <= lon <= LON_MAX):
            return None
        return {"lon": lon, "lat": lat}
    except requests.RequestException as e:
        return {"error": f"error:{type(e).__name__}"}


def geocode_dataframe(
    df: pl.DataFrame,
    cache: dict[str, dict],
    api_key: str,
) -> tuple[pl.DataFrame, list[dict], list[dict]]:
    """
    위도/경도 결측 행에 지오코딩 적용.
    반환: (갱신된 df, 신규 캐시 항목 리스트, 실패 항목 리스트)
    """
    new_cache_rows: list[dict] = []
    failure_rows: list[dict] = []

    # 결측 인덱스 추출
    need_geo = df.with_row_index("__idx__").filter(
        pl.col("위도").is_null() | pl.col("경도").is_null()
    )
    total = len(need_geo)
    if total == 0:
        print("[INFO] 지오코딩 대상 없음.")
        return df, new_cache_rows, failure_rows

    print(f"[INFO] 지오코딩 대상: {total:,}행")

    # 갱신할 좌표를 인덱스 기반으로 추적
    updates: dict[int, tuple[float | None, float | None]] = {}

    for i, row in enumerate(need_geo.iter_rows(named=True), 1):
        idx = row["__idx__"]
        road_addr = (row.get("소재지도로명주소") or "").strip()
        jibun_addr = (row.get("소재지지번주소") or "").strip()

        coords = None
        used_addr = None

        for orig_addr in filter(None, [road_addr, jibun_addr]):
            # 원본 + 정제 주소 순서로 시도 (중복 제거)
            cleaned = clean_addr_for_geocode(orig_addr)
            candidates = [orig_addr] if orig_addr == cleaned else [orig_addr, cleaned]

            for addr in candidates:
                # 캐시 확인
                if addr in cache:
                    cached = cache[addr]
                    if cached["status"] == "ok":
                        lon = float(cached["lon"])
                        lat = float(cached["lat"])
                        coords = (lon, lat)
                        used_addr = addr
                        break
                    else:
                        # no_result / error → 다음 후보로
                        continue

                # API 호출
                result = kakao_geocode(addr, api_key)
                ts = now_iso()

                if result and "lon" in result:
                    lon, lat = result["lon"], result["lat"]
                    entry = {"geo_addr": addr, "lon": str(lon), "lat": str(lat), "status": "ok", "updated_at": ts}
                    cache[addr] = entry
                    new_cache_rows.append(entry)
                    coords = (lon, lat)
                    used_addr = addr
                    break
                elif result and "error" in result:
                    reason = result["error"]
                    entry = {"geo_addr": addr, "lon": "", "lat": "", "status": reason, "updated_at": ts}
                    cache[addr] = entry
                    new_cache_rows.append(entry)
                    failure_rows.append({"geo_addr": addr, "reason": reason, "updated_at": ts})
                else:
                    # no_result
                    entry = {"geo_addr": addr, "lon": "", "lat": "", "status": "no_result", "updated_at": ts}
                    cache[addr] = entry
                    new_cache_rows.append(entry)

                time.sleep(0.05)  # API 부하 방지

            if coords:
                break  # 원본 주소에서 성공했으면 지번 시도 불필요

        if coords:
            updates[idx] = coords
        else:
            if not used_addr:
                addr_tried = road_addr or jibun_addr or "(없음)"
                ts = now_iso()
                failure_rows.append({"geo_addr": addr_tried, "reason": "no_result", "updated_at": ts})

        if i % 500 == 0:
            print(f"  [{i:,}/{total:,}] 처리 중...")

    print(f"[INFO] 지오코딩 완료: 성공 {len(updates):,} / 실패 {total - len(updates):,}")

    if not updates:
        return df, new_cache_rows, failure_rows

    # DataFrame에 좌표 반영
    idx_col = need_geo.get_column("__idx__").to_list()
    lon_map = {idx: updates[idx][0] if idx in updates else None for idx in idx_col}
    lat_map = {idx: updates[idx][1] if idx in updates else None for idx in idx_col}

    df_indexed = df.with_row_index("__idx__")
    df_indexed = df_indexed.with_columns([
        pl.struct(["__idx__", "경도"]).map_elements(
            lambda s: lon_map.get(s["__idx__"], s["경도"]),
            return_dtype=pl.Float64,
        ).alias("경도"),
        pl.struct(["__idx__", "위도"]).map_elements(
            lambda s: lat_map.get(s["__idx__"], s["위도"]),
            return_dtype=pl.Float64,
        ).alias("위도"),
    ])
    df_out = df_indexed.drop("__idx__")
    return df_out, new_cache_rows, failure_rows


# ── Step 3. 로그 파일 갱신 ────────────────────────────────────────────────────

def append_cache(cache_path: Path, new_rows: list[dict]) -> None:
    """신규 캐시 항목만 append."""
    if not new_rows:
        return
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not cache_path.exists()
    with open(cache_path, "a", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["geo_addr", "lon", "lat", "status", "updated_at"])
        if write_header:
            writer.writeheader()
        writer.writerows(new_rows)
    print(f"[INFO] 캐시 추가: {len(new_rows):,}건 → {cache_path.name}")


def append_failures(failures_path: Path, failure_rows: list[dict]) -> None:
    """실패 항목 append."""
    if not failure_rows:
        return
    failures_path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not failures_path.exists()
    with open(failures_path, "a", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["geo_addr", "reason", "updated_at"])
        if write_header:
            writer.writeheader()
        writer.writerows(failure_rows)
    print(f"[INFO] 실패 로그 추가: {len(failure_rows):,}건 → {failures_path.name}")


# ── Step 4. 출력 ──────────────────────────────────────────────────────────────

def save_parquet(df: pl.DataFrame, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "pv_facility_processed.parquet"
    df.write_parquet(out_path)
    print(f"[INFO] parquet 저장: {out_path} ({len(df):,}행)")
    return out_path


def save_preprocess_state(
    state_rows: list[dict],
    output_dir: Path,
    mode: str,
    existing_state: pl.DataFrame | None = None,
) -> None:
    """처리 이력 저장 (full: 전체 교체, incremental: upsert)."""
    output_dir.mkdir(parents=True, exist_ok=True)
    state_path = output_dir / "preprocess_state.csv"

    new_df = pl.DataFrame(state_rows, schema={
        "source_file": pl.Utf8,
        "row_count_raw": pl.Int64,
        "row_count_filtered": pl.Int64,
        "processed_at": pl.Utf8,
    })

    if mode == "incremental" and existing_state is not None and not existing_state.is_empty():
        updated_files = {r["source_file"] for r in state_rows}
        kept = existing_state.filter(~pl.col("source_file").is_in(list(updated_files)))
        combined = pl.concat([kept, new_df])
    else:
        combined = new_df

    combined.write_csv(state_path, separator=",")
    print(f"[INFO] preprocess_state 저장: {state_path} ({len(combined):,}건)")


# ── 증분 처리 헬퍼 ────────────────────────────────────────────────────────────

def load_preprocess_state(output_dir: Path) -> pl.DataFrame:
    state_path = output_dir / "preprocess_state.csv"
    if not state_path.exists():
        return pl.DataFrame()
    return pl.read_csv(state_path, encoding="utf8-lossy")


def load_crawler_state(crawler_state_path: Path) -> dict[str, str]:
    """크롤러 상태 파일에서 saved_file → modified_date 매핑 반환."""
    mapping: dict[str, str] = {}
    if not crawler_state_path.exists():
        return mapping
    try:
        df = pl.read_csv(crawler_state_path, encoding="utf8-lossy", infer_schema_length=0)
        for row in df.iter_rows(named=True):
            saved = row.get("saved_file", "")
            modified = row.get("modified_date", "")
            if saved:
                mapping[Path(saved).name] = modified
    except Exception as e:
        print(f"[WARN] 크롤러 상태 로드 실패: {e}")
    return mapping


def find_incremental_files(
    raw_csv_dir: Path,
    existing_state: pl.DataFrame,
    crawler_state: dict[str, str],
) -> list[Path]:
    """신규 또는 변경된 파일 목록 반환."""
    all_files = {f.name: f for f in sorted(raw_csv_dir.glob("*.csv"))}

    processed: dict[str, str] = {}
    if not existing_state.is_empty() and "source_file" in existing_state.columns:
        for row in existing_state.iter_rows(named=True):
            processed[row["source_file"]] = row.get("processed_at", "")

    targets = []
    for fname, fpath in all_files.items():
        if fname not in processed:
            targets.append(fpath)
        elif fname in crawler_state:
            # 크롤러가 새로 받은 파일인지 확인 (modified_date 비교)
            # preprocess_state의 processed_at이 크롤러 수정일보다 이전이면 재처리
            # 단순히: 크롤러 상태에 있고 이미 처리됐다면 날짜 비교 대신 파일 존재 여부로 판단
            # 여기서는 크롤러 상태 ok 파일 중 미처리 파일만 추가 처리
            pass

    print(f"[INFO] 증분 처리 대상: {len(targets):,}개 파일")
    return targets


# ── 메인 ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="PV 시설 데이터 전처리 파이프라인")
    parser.add_argument("--raw-csv-dir", type=Path, default=DEFAULT_RAW_CSV_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--cache-path", type=Path, default=DEFAULT_CACHE_PATH)
    parser.add_argument("--failures-path", type=Path, default=DEFAULT_FAILURES_PATH)
    parser.add_argument("--crawler-state", type=Path, default=DEFAULT_CRAWLER_STATE)
    parser.add_argument("--mode", choices=["full", "incremental"], default="full")
    parser.add_argument("--no-geocode", action="store_true", help="지오코딩 건너뜀")
    args = parser.parse_args()

    api_key = os.environ.get("KAKAO_API_KEY", "")
    if not args.no_geocode and not api_key:
        print("[ERROR] KAKAO_API_KEY 환경변수가 설정되지 않았습니다. --no-geocode 옵션을 사용하거나 키를 설정하세요.")
        sys.exit(1)

    # ── 증분 모드 파일 선택 ──────────────────────────────────────────────────
    existing_state = load_preprocess_state(args.output_dir)
    existing_parquet: pl.DataFrame | None = None

    if args.mode == "incremental":
        crawler_state = load_crawler_state(args.crawler_state)
        target_files = find_incremental_files(args.raw_csv_dir, existing_state, crawler_state)
        if not target_files:
            print("[INFO] 처리할 신규/변경 파일 없음. 종료.")
            return
        parquet_path = args.output_dir / "pv_facility_processed.parquet"
        if parquet_path.exists():
            existing_parquet = pl.read_parquet(parquet_path)
            print(f"[INFO] 기존 parquet 로드: {len(existing_parquet):,}행")
    else:
        target_files = None  # 전체

    # ── Step 1. 통합 + 필터링 ────────────────────────────────────────────────
    raw_df = load_raw_csvs(args.raw_csv_dir, target_files)
    if raw_df.is_empty():
        print("[ERROR] 처리할 데이터 없음. 종료.")
        sys.exit(1)

    raw_counts: dict[str, int] = {}
    for fname, group in raw_df.group_by("source_file"):
        raw_counts[fname[0]] = len(group)

    filtered_df = filter_and_cast(raw_df)

    filtered_counts: dict[str, int] = {}
    for fname, group in filtered_df.group_by("source_file"):
        filtered_counts[fname[0]] = len(group)

    # ── Step 2. 지오코딩 ─────────────────────────────────────────────────────
    new_cache_rows: list[dict] = []
    failure_rows: list[dict] = []

    if not args.no_geocode and "위도" in filtered_df.columns:
        cache = load_cache(args.cache_path)
        filtered_df, new_cache_rows, failure_rows = geocode_dataframe(filtered_df, cache, api_key)
    else:
        if args.no_geocode:
            print("[INFO] --no-geocode: 지오코딩 건너뜀.")

    # ── Step 3. 로그 갱신 ────────────────────────────────────────────────────
    append_cache(args.cache_path, new_cache_rows)
    append_failures(args.failures_path, failure_rows)

    # ── Step 4. 출력 ─────────────────────────────────────────────────────────
    final_df = filtered_df

    # 증분: 기존 parquet에서 해당 source_file 행 제거 후 concat
    if args.mode == "incremental" and existing_parquet is not None:
        processed_files = list(raw_counts.keys())
        kept = existing_parquet.filter(~pl.col("source_file").is_in(processed_files))
        final_df = pl.concat([kept, filtered_df], how="diagonal_relaxed")
        print(f"[INFO] 증분 병합: 기존 {len(kept):,}행 + 신규 {len(filtered_df):,}행 = {len(final_df):,}행")

    save_parquet(final_df, args.output_dir)

    # 처리 이력 저장
    ts = now_iso()
    all_files_in_raw = sorted({*raw_counts.keys()})
    state_rows = [
        {
            "source_file": fname,
            "row_count_raw": raw_counts.get(fname, 0),
            "row_count_filtered": filtered_counts.get(fname, 0),
            "processed_at": ts,
        }
        for fname in all_files_in_raw
    ]
    save_preprocess_state(state_rows, args.output_dir, args.mode, existing_state)

    print("[DONE] 전처리 완료.")


if __name__ == "__main__":
    main()
