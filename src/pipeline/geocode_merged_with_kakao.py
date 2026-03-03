import argparse
import os
import re
import time
from pathlib import Path

import polars as pl
import requests


MERGED_CSV = Path("src/data/final/pv_facility_profile_merged.csv")
OUT_CSV = Path("src/data/final/pv_facility_profile_geocoded.csv")
CACHE_CSV = Path("src/data/final/geocode_cache_kakao.csv")
FAIL_CSV = Path("src/data/final/geocode_failures_kakao.csv")
UTILS_PY = Path("src/utils/utils.py")


def resolve_kakao_key(explicit_key: str | None) -> str:
    if explicit_key:
        return explicit_key
    env_key = os.getenv("KAKAO_REST_API_KEY", "").strip()
    if env_key:
        return env_key

    if UTILS_PY.exists():
        text = UTILS_PY.read_text(encoding="utf-8", errors="ignore")
        match = re.search(r'KAKAO_PRIVATE_KEY\s*=\s*"([^"]+)"', text)
        if match:
            return match.group(1).strip()

    raise RuntimeError(
        "Kakao API key not found. Set KAKAO_REST_API_KEY or pass --kakao-key."
    )


def load_cache(cache_path: Path) -> pl.DataFrame:
    if cache_path.exists():
        return pl.read_csv(cache_path, encoding="utf8-lossy", ignore_errors=True)
    return pl.DataFrame(
        {
            "geo_addr": [],
            "lon": [],
            "lat": [],
            "status": [],
            "updated_at": [],
        }
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


def geocode_address(session: requests.Session, kakao_key: str, address: str) -> tuple[str, str] | None:
    url = "https://dapi.kakao.com/v2/local/search/address.json"
    headers = {"Authorization": f"KakaoAK {kakao_key}"}
    resp = session.get(url, headers=headers, params={"query": address}, timeout=15)
    if resp.status_code != 200:
        raise RuntimeError(f"http_{resp.status_code}")
    data = resp.json()
    docs = data.get("documents", [])
    if not docs:
        return None
    first = docs[0]
    return str(first.get("x", "")).strip(), str(first.get("y", "")).strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="Geocode merged PV profile CSV with Kakao API.")
    parser.add_argument("--merged-csv", default=str(MERGED_CSV))
    parser.add_argument("--out-csv", default=str(OUT_CSV))
    parser.add_argument("--cache-csv", default=str(CACHE_CSV))
    parser.add_argument("--fail-csv", default=str(FAIL_CSV))
    parser.add_argument("--kakao-key", default=None)
    parser.add_argument("--sleep-sec", type=float, default=0.03)
    parser.add_argument("--max-requests", type=int, default=None)
    parser.add_argument("--save-every", type=int, default=200)
    args = parser.parse_args()

    merged_path = Path(args.merged_csv)
    out_path = Path(args.out_csv)
    cache_path = Path(args.cache_csv)
    fail_path = Path(args.fail_csv)

    kakao_key = resolve_kakao_key(args.kakao_key)

    df = pl.read_csv(
        merged_path,
        encoding="utf8-lossy",
        null_values=["", " ", "-", "NULL", "null", "NaN", "nan"],
        infer_schema_length=1000,
        ignore_errors=True,
    )

    road_col = "소재지도로명주소"
    jibun_col = "소재지지번주소"
    lat_col = "위도"
    lon_col = "경도"

    if road_col not in df.columns or jibun_col not in df.columns:
        raise RuntimeError("Address columns not found in merged CSV.")

    work = df.with_columns(
        pl.when(pl.col(road_col).is_not_null())
        .then(pl.col(road_col))
        .otherwise(pl.col(jibun_col))
        .alias("geo_addr")
    )

    need = work.filter((pl.col(lat_col).is_null() | pl.col(lon_col).is_null()) & pl.col("geo_addr").is_not_null())
    unique_need = need.select("geo_addr").unique()

    cache_df = load_cache(cache_path)
    fail_df = load_failures(fail_path)

    cached_addrs = set(cache_df.get_column("geo_addr").to_list()) if cache_df.height else set()
    target_addrs = [a for a in unique_need.get_column("geo_addr").to_list() if a not in cached_addrs]

    print(f"rows_total={df.height}")
    print(f"rows_need_geocode={need.height}")
    print(f"unique_need_addr={unique_need.height}")
    print(f"already_cached_addr={len(cached_addrs)}")
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
                new_fail_rows.append({"geo_addr": addr, "reason": "no_result", "updated_at": now_ts})
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
            new_fail_rows.append({"geo_addr": addr, "reason": str(exc), "updated_at": now_ts})

        if idx % args.save_every == 0:
            if new_cache_rows:
                cache_df = pl.concat([cache_df, pl.DataFrame(new_cache_rows)], how="vertical_relaxed")
                cache_df = cache_df.unique(subset=["geo_addr"], keep="last")
                write_cache(cache_path, cache_df)
                new_cache_rows = []
            if new_fail_rows:
                fail_df = pl.concat([fail_df, pl.DataFrame(new_fail_rows)], how="vertical_relaxed")
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

    cache_ok = cache_df.filter(pl.col("status") == "ok").select(["geo_addr", "lon", "lat"])
    joined = work.join(cache_ok, on="geo_addr", how="left", suffix="_geo")

    geocoded = joined.with_columns(
        [
            pl.when(pl.col(lon_col).is_null() & pl.col("lon").is_not_null())
            .then(pl.col("lon"))
            .otherwise(pl.col(lon_col))
            .alias(lon_col),
            pl.when(pl.col(lat_col).is_null() & pl.col("lat").is_not_null())
            .then(pl.col("lat"))
            .otherwise(pl.col(lat_col))
            .alias(lat_col),
        ]
    ).drop(["geo_addr", "lon", "lat"])

    out_path.parent.mkdir(parents=True, exist_ok=True)
    geocoded.write_csv(out_path, include_bom=True)

    filled_now = (
        geocoded.filter(pl.col(lat_col).is_not_null() & pl.col(lon_col).is_not_null()).height
        - df.filter(pl.col(lat_col).is_not_null() & pl.col(lon_col).is_not_null()).height
    )
    print(f"requests_sent={request_count}")
    print(f"cache_size={cache_df.height}")
    print(f"filled_new_latlon={filled_now}")
    print(f"output={out_path}")


if __name__ == "__main__":
    main()
