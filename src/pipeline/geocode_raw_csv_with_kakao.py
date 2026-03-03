import argparse
import os
import time
from pathlib import Path

import polars as pl
import requests


RAW_DIR = Path("src/data/raw_csv")
CACHE_CSV = RAW_DIR / "geocode_cache_kakao_raw.csv"
FAIL_CSV = RAW_DIR / "geocode_failures_kakao_raw.csv"
ENV_PATH = Path(".env")

NULL_VALUES = ["", " ", "-", "NULL", "null", "NaN", "nan"]
ADDR_ROAD = "소재지도로명주소"
ADDR_JIBUN = "소재지지번주소"
LAT_COL = "위도"
LON_COL = "경도"
SKIP_FILES = {
    "download_log_playwright.csv",
    "pv_facility_profile_state.csv",
    ".gitkeep",
    CACHE_CSV.name,
    FAIL_CSV.name,
}


def read_env_key_from_dotenv(env_path: Path) -> str:
    if not env_path.exists():
        return ""
    for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        if k.strip() == "KAKAO_REST_API_KEY":
            return v.strip().strip("'").strip('"')
    return ""


def resolve_kakao_key(explicit_key: str | None) -> str:
    if explicit_key:
        return explicit_key.strip()
    env_key = os.getenv("KAKAO_REST_API_KEY", "").strip()
    if env_key:
        return env_key
    file_key = read_env_key_from_dotenv(ENV_PATH)
    if file_key:
        return file_key
    raise RuntimeError("KAKAO_REST_API_KEY not found in env or .env")


def load_cache(cache_path: Path) -> pl.DataFrame:
    if cache_path.exists():
        return pl.read_csv(cache_path, encoding="utf8-lossy", ignore_errors=True)
    return pl.DataFrame(
        {"geo_addr": [], "lon": [], "lat": [], "status": [], "updated_at": []}
    )


def load_failures(fail_path: Path) -> pl.DataFrame:
    if fail_path.exists():
        return pl.read_csv(fail_path, encoding="utf8-lossy", ignore_errors=True)
    return pl.DataFrame({"geo_addr": [], "reason": [], "updated_at": []})


def write_cache(cache_path: Path, cache_df: pl.DataFrame) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_df.write_csv(cache_path, include_bom=True)


def write_failures(fail_path: Path, fail_df: pl.DataFrame) -> None:
    fail_path.parent.mkdir(parents=True, exist_ok=True)
    fail_df.write_csv(fail_path, include_bom=True)


def geocode_address(
    session: requests.Session, kakao_key: str, address: str
) -> tuple[str, str] | None:
    url = "https://dapi.kakao.com/v2/local/search/address.json"
    headers = {"Authorization": f"KakaoAK {kakao_key}"}
    resp = session.get(url, headers=headers, params={"query": address}, timeout=20)
    if resp.status_code != 200:
        raise RuntimeError(f"http_{resp.status_code}")
    data = resp.json()
    docs = data.get("documents", [])
    if not docs:
        return None
    first = docs[0]
    return str(first.get("x", "")).strip(), str(first.get("y", "")).strip()


def list_raw_csv_files(raw_dir: Path) -> list[Path]:
    files = []
    for p in sorted(raw_dir.glob("*.csv")):
        if p.name in SKIP_FILES:
            continue
        files.append(p)
    return files


def load_with_geo_addr(path: Path) -> pl.DataFrame:
    df = pl.read_csv(
        path,
        encoding="utf8-lossy",
        null_values=NULL_VALUES,
        infer_schema_length=1000,
        ignore_errors=True,
    )
    required = {ADDR_ROAD, ADDR_JIBUN, LAT_COL, LON_COL}
    if not required.issubset(set(df.columns)):
        missing = sorted(required.difference(set(df.columns)))
        raise RuntimeError(f"missing_columns={missing}")

    return df.with_columns(
        pl.when(pl.col(ADDR_ROAD).is_not_null() & (pl.col(ADDR_ROAD).str.len_chars() > 0))
        .then(pl.col(ADDR_ROAD))
        .otherwise(pl.col(ADDR_JIBUN))
        .alias("geo_addr")
    )


def fill_latlon_from_cache(df: pl.DataFrame, cache_df: pl.DataFrame) -> pl.DataFrame:
    cache_ok = (
        cache_df.filter(pl.col("status") == "ok")
        .select(["geo_addr", "lon", "lat"])
        .unique(subset=["geo_addr"], keep="last")
    )
    joined = df.join(cache_ok, on="geo_addr", how="left", suffix="_geo")
    return joined.with_columns(
        [
            pl.when(pl.col(LON_COL).is_null() & pl.col("lon").is_not_null())
            .then(pl.col("lon"))
            .otherwise(pl.col(LON_COL))
            .alias(LON_COL),
            pl.when(pl.col(LAT_COL).is_null() & pl.col("lat").is_not_null())
            .then(pl.col("lat"))
            .otherwise(pl.col(LAT_COL))
            .alias(LAT_COL),
        ]
    ).drop(["lon", "lat"])


def extract_target_addrs(files: list[Path], cache_df: pl.DataFrame) -> tuple[list[str], dict[str, int]]:
    cached_addrs = set(cache_df.get_column("geo_addr").to_list()) if cache_df.height else set()
    addr_set: set[str] = set()
    stats = {"rows_total": 0, "rows_need_geocode": 0}
    for path in files:
        df = load_with_geo_addr(path)
        stats["rows_total"] += df.height
        need = df.filter(
            (pl.col(LAT_COL).is_null() | pl.col(LON_COL).is_null())
            & pl.col("geo_addr").is_not_null()
        )
        stats["rows_need_geocode"] += need.height
        addrs = need.get_column("geo_addr").to_list()
        for a in addrs:
            if a not in cached_addrs:
                addr_set.add(a)
    return sorted(addr_set), stats


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Geocode all raw profile CSV files in-place with Kakao API."
    )
    parser.add_argument("--raw-dir", default=str(RAW_DIR))
    parser.add_argument("--cache-csv", default=str(CACHE_CSV))
    parser.add_argument("--fail-csv", default=str(FAIL_CSV))
    parser.add_argument("--kakao-key", default=None)
    parser.add_argument("--sleep-sec", type=float, default=0.05)
    parser.add_argument("--max-requests", type=int, default=None)
    parser.add_argument("--save-every", type=int, default=200)
    parser.add_argument(
        "--retry-status",
        default="",
        help="Comma-separated cache statuses to retry (e.g. no_result,error)",
    )
    args = parser.parse_args()

    raw_dir = Path(args.raw_dir)
    cache_path = Path(args.cache_csv)
    fail_path = Path(args.fail_csv)
    kakao_key = resolve_kakao_key(args.kakao_key)

    files = list_raw_csv_files(raw_dir)
    if not files:
        raise RuntimeError(f"No raw csv files found in {raw_dir}")

    cache_df = load_cache(cache_path)
    fail_df = load_failures(fail_path)

    target_addrs, stats = extract_target_addrs(files, cache_df)
    retry_statuses = {s.strip() for s in args.retry_status.split(",") if s.strip()}
    if retry_statuses and cache_df.height:
        retry_addrs = (
            cache_df.filter(pl.col("status").is_in(list(retry_statuses)))
            .select("geo_addr")
            .unique()
            .get_column("geo_addr")
            .to_list()
        )
        target_addrs = sorted(set(target_addrs).union(set(retry_addrs)))

    print(f"files={len(files)}")
    print(f"rows_total={stats['rows_total']}")
    print(f"rows_need_geocode={stats['rows_need_geocode']}")
    if retry_statuses:
        print(f"retry_statuses={','.join(sorted(retry_statuses))}")
    print(f"target_addr={len(target_addrs)}")

    session = requests.Session()
    new_cache_rows: list[dict[str, str]] = []
    new_fail_rows: list[dict[str, str]] = []
    request_count = 0

    for idx, addr in enumerate(target_addrs, start=1):
        if args.max_requests is not None and request_count >= args.max_requests:
            break
        now_ts = time.strftime("%Y-%m-%dT%H:%M:%S")
        try:
            res = geocode_address(session, kakao_key, addr)
            request_count += 1
            if res is None:
                new_cache_rows.append(
                    {
                        "geo_addr": addr,
                        "lon": "",
                        "lat": "",
                        "status": "no_result",
                        "updated_at": now_ts,
                    }
                )
                new_fail_rows.append(
                    {"geo_addr": addr, "reason": "no_result", "updated_at": now_ts}
                )
            else:
                lon, lat = res
                new_cache_rows.append(
                    {
                        "geo_addr": addr,
                        "lon": lon,
                        "lat": lat,
                        "status": "ok",
                        "updated_at": now_ts,
                    }
                )
        except Exception as exc:  # noqa: BLE001
            request_count += 1
            new_cache_rows.append(
                {
                    "geo_addr": addr,
                    "lon": "",
                    "lat": "",
                    "status": "error",
                    "updated_at": now_ts,
                }
            )
            new_fail_rows.append(
                {"geo_addr": addr, "reason": str(exc), "updated_at": now_ts}
            )

        if idx % args.save_every == 0:
            if new_cache_rows:
                cache_df = pl.concat(
                    [cache_df, pl.DataFrame(new_cache_rows)], how="vertical_relaxed"
                )
                cache_df = cache_df.unique(subset=["geo_addr"], keep="last")
                write_cache(cache_path, cache_df)
                new_cache_rows = []
            if new_fail_rows:
                fail_df = pl.concat(
                    [fail_df, pl.DataFrame(new_fail_rows)], how="vertical_relaxed"
                )
                write_failures(fail_path, fail_df)
                new_fail_rows = []
            print(f"progress={idx}/{len(target_addrs)} requests={request_count}")

        time.sleep(args.sleep_sec)

    if new_cache_rows:
        cache_df = pl.concat([cache_df, pl.DataFrame(new_cache_rows)], how="vertical_relaxed")
        cache_df = cache_df.unique(subset=["geo_addr"], keep="last")
        write_cache(cache_path, cache_df)
    if new_fail_rows:
        fail_df = pl.concat([fail_df, pl.DataFrame(new_fail_rows)], how="vertical_relaxed")
        write_failures(fail_path, fail_df)

    total_filled = 0
    for path in files:
        df = load_with_geo_addr(path)
        before = df.filter(pl.col(LAT_COL).is_not_null() & pl.col(LON_COL).is_not_null()).height
        filled_df = fill_latlon_from_cache(df, cache_df).drop("geo_addr")
        after = filled_df.filter(
            pl.col(LAT_COL).is_not_null() & pl.col(LON_COL).is_not_null()
        ).height
        total_filled += max(0, after - before)
        filled_df.write_csv(path, include_bom=True)

    print(f"requests_sent={request_count}")
    print(f"cache_size={cache_df.height}")
    print(f"filled_new_latlon={total_filled}")
    print(f"raw_dir_updated={raw_dir}")


if __name__ == "__main__":
    main()
