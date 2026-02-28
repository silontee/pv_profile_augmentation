"""
parquet + GeoJSON → PostGIS ETL 스크립트.
최초 1회 실행으로 DB를 초기화.

실행 방법:
    uv run python app/db/load_data.py

데이터 소스:
    - parquet: generator_next/source/processed/pv_facility_processed.parquet
    - 변전소:  generator_next/source/openinframap/by_sido/substations_*.geojson
    - 송배전선: generator_next/source/openinframap/by_sido/power_lines_*.geojson
"""
import glob
import json
import logging
import os
import re
import sys
from datetime import date
from pathlib import Path
from typing import Optional

import polars as pl
import psycopg2
from psycopg2.extras import execute_values

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# 경로 계산:
#   DATA_ROOT 환경변수가 있으면 Docker 모드 (/data/ 마운트)
#   없으면 로컬 모드 (parents[5] = 프로젝트 루트)
_DATA_ROOT = os.getenv("DATA_ROOT", "")

if _DATA_ROOT:
    _data = Path(_DATA_ROOT)
    _PARQUET_PATH = _data / "processed" / "pv_facility_processed.parquet"
    _SUBSTATIONS_GLOB = str(_data / "openinframap" / "by_sido" / "substations_*.geojson")
    _POWER_LINES_GLOB = str(_data / "openinframap" / "by_sido" / "power_lines_*.geojson")
else:
    _PROJECT_ROOT = Path(__file__).resolve().parents[5]
    _PARQUET_PATH = _PROJECT_ROOT / "generator_next" / "source" / "processed" / "pv_facility_processed.parquet"
    _SUBSTATIONS_GLOB = str(_PROJECT_ROOT / "generator_next" / "source" / "openinframap" / "by_sido" / "substations_*.geojson")
    _POWER_LINES_GLOB = str(_PROJECT_ROOT / "generator_next" / "source" / "openinframap" / "by_sido" / "power_lines_*.geojson")

# DB 연결 정보 (환경변수 오버라이드 가능)
_DB_HOST = os.getenv("DB_HOST", "localhost")
_DB_PORT = int(os.getenv("DB_PORT", "5432"))
_DB_NAME = os.getenv("DB_NAME", "pv_profile")
_DB_USER = os.getenv("DB_USER", "pv_user")
_DB_PASSWORD = os.getenv("DB_PASSWORD", "pv_password")

# 배치 크기 (메모리·성능 균형)
_BATCH_SIZE = 5000


def get_connection() -> psycopg2.extensions.connection:
    """psycopg2 동기 연결 반환 (ETL 전용)."""
    return psycopg2.connect(
        host=_DB_HOST,
        port=_DB_PORT,
        dbname=_DB_NAME,
        user=_DB_USER,
        password=_DB_PASSWORD,
    )


def setup_extensions_and_tables(conn: psycopg2.extensions.connection) -> None:
    """
    PostGIS 익스텐션 및 테이블·인덱스 생성.
    idempotent — 이미 존재하면 무시.
    """
    logger.info("PostGIS 익스텐션 및 테이블 초기화 중...")
    with conn.cursor() as cur:
        # PostGIS 및 트리그램 익스텐션
        cur.execute("CREATE EXTENSION IF NOT EXISTS postgis;")
        cur.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")

        # ── pv_facility 테이블 ──────────────────────────────────────────
        cur.execute("""
            CREATE TABLE IF NOT EXISTS pv_facility (
                id              SERIAL PRIMARY KEY,
                name            TEXT,
                addr_road       TEXT,
                addr_jibun      TEXT,
                geom            GEOMETRY(POINT, 4326),
                has_coord       BOOLEAN GENERATED ALWAYS AS (geom IS NOT NULL) STORED,
                install_type    TEXT,
                status          TEXT NOT NULL,
                capacity_kw     NUMERIC(15, 2),
                voltage         TEXT,
                frequency       TEXT,
                install_year    SMALLINT,
                usage_detail    TEXT,
                permit_date     DATE,
                permit_org      TEXT,
                install_area_m2 NUMERIC(15, 2),
                data_date       DATE,
                source_file     TEXT,
                created_at      TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        # 공간 인덱스 (좌표 있는 행만)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_pv_facility_geom
            ON pv_facility USING GIST (geom)
            WHERE geom IS NOT NULL
        """)
        # 상태 인덱스
        cur.execute("CREATE INDEX IF NOT EXISTS idx_pv_facility_status ON pv_facility (status)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_pv_facility_has_coord ON pv_facility (has_coord)")
        # 트리그램 인덱스 (ILIKE 검색 가속)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_pv_facility_name_trgm
            ON pv_facility USING GIN (name gin_trgm_ops)
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_pv_facility_addr_trgm
            ON pv_facility USING GIN (addr_road gin_trgm_ops)
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_pv_facility_capacity ON pv_facility (capacity_kw)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_pv_facility_year ON pv_facility (install_year)")

        # ── substation 테이블 ───────────────────────────────────────────
        cur.execute("""
            CREATE TABLE IF NOT EXISTS substation (
                id       SERIAL PRIMARY KEY,
                name     TEXT,
                name_en  TEXT,
                geom     GEOMETRY(POINT, 4326) NOT NULL,
                voltage  TEXT,
                sub_type TEXT,
                frequency TEXT,
                operator TEXT,
                osm_id   BIGINT,
                sido     TEXT
            )
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_substation_geom
            ON substation USING GIST (geom)
        """)

        # ── power_line 테이블 ───────────────────────────────────────────
        cur.execute("""
            CREATE TABLE IF NOT EXISTS power_line (
                id         SERIAL PRIMARY KEY,
                name       TEXT,
                geom       GEOMETRY(LINESTRING, 4326) NOT NULL,
                power_type TEXT,
                voltage    TEXT,
                sido       TEXT
            )
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_power_line_geom
            ON power_line USING GIST (geom)
        """)

    conn.commit()
    logger.info("테이블 초기화 완료")


def _safe_float(val) -> Optional[float]:
    """문자열 또는 None → float 변환. 실패 시 None."""
    if val is None:
        return None
    try:
        return float(str(val).replace(",", "").strip())
    except (ValueError, TypeError):
        return None


def _safe_int(val) -> Optional[int]:
    """문자열 또는 None → int 변환. 실패 시 None."""
    if val is None:
        return None
    try:
        v = str(val).strip()
        # 연도 형식 정규화 (예: "2016년" → "2016")
        v = re.sub(r"[^0-9]", "", v)
        return int(v) if v else None
    except (ValueError, TypeError):
        return None


def _safe_date(val) -> Optional[str]:
    """날짜 문자열 → ISO 형식. None 허용."""
    if val is None:
        return None
    s = str(val).strip()
    # "YYYY-MM-DD" 형태면 그대로
    if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
        return s
    # "YYYYMMDD" → "YYYY-MM-DD"
    if re.match(r"^\d{8}$", s):
        return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
    # "YYYY.MM.DD"
    m = re.match(r"^(\d{4})\.(\d{2})\.(\d{2})$", s)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return None


def load_pv_facility(conn: psycopg2.extensions.connection) -> int:
    """
    parquet → pv_facility 테이블 적재.
    기존 데이터 전체 삭제 후 재적재 (idempotent).
    반환: 적재된 행 수
    """
    logger.info(f"parquet 읽기: {_PARQUET_PATH}")
    if not _PARQUET_PATH.exists():
        logger.error(f"parquet 파일 없음: {_PARQUET_PATH}")
        sys.exit(1)

    df = pl.read_parquet(_PARQUET_PATH)
    logger.info(f"parquet 로드 완료: {df.shape[0]}행 × {df.shape[1]}열")

    with conn.cursor() as cur:
        # 기존 데이터 삭제 (재실행 시 중복 방지)
        cur.execute("TRUNCATE TABLE pv_facility RESTART IDENTITY CASCADE")
        conn.commit()
        logger.info("기존 pv_facility 데이터 삭제 완료")

    total_inserted = 0
    rows_buffer = []

    for i, row in enumerate(df.iter_rows(named=True)):
        # 좌표 처리 — 위도/경도 모두 유효한 경우에만 geom 생성
        lat = _safe_float(row.get("위도"))
        lng = _safe_float(row.get("경도"))

        # 좌표 유효성 검증
        # 한반도 범위: 위도 33~38.5, 경도 124~132
        geom_wkt = None
        if lat is not None and lng is not None:
            if 33.0 <= lat <= 39.0 and 124.0 <= lng <= 132.0:
                geom_wkt = f"SRID=4326;POINT({lng} {lat})"
            else:
                logger.debug(f"유효 범위 외 좌표 무시: lat={lat}, lng={lng} (id후보={i})")

        rows_buffer.append((
            row.get("태양광발전시설명"),
            row.get("소재지도로명주소"),
            row.get("소재지지번주소"),
            geom_wkt,           # NULL이면 geom=NULL → has_coord=FALSE
            row.get("설치상세위치구분명"),
            row.get("가동상태구분명") or "미상",  # NOT NULL 컬럼
            _safe_float(row.get("설비용량")),
            row.get("공급전압"),   # TEXT — 원본 그대로 보존 (값이 지저분함)
            row.get("주파수"),     # TEXT — 원본 그대로 보존 (값이 지저분함)
            _safe_int(row.get("설치연도")),
            row.get("세부용도"),
            _safe_date(row.get("허가일자")),
            row.get("허가기관"),
            _safe_float(row.get("설치면적")),
            _safe_date(row.get("데이터기준일자")),
            row.get("source_file"),
        ))

        # 배치 처리
        if len(rows_buffer) >= _BATCH_SIZE:
            _insert_facility_batch(conn, rows_buffer)
            total_inserted += len(rows_buffer)
            rows_buffer = []
            logger.info(f"  진행: {total_inserted:,}건 적재 완료...")

    # 잔여 배치 처리
    if rows_buffer:
        _insert_facility_batch(conn, rows_buffer)
        total_inserted += len(rows_buffer)

    conn.commit()
    logger.info(f"pv_facility 적재 완료: 총 {total_inserted:,}건")
    return total_inserted


def _insert_facility_batch(
    conn: psycopg2.extensions.connection,
    rows: list,
) -> None:
    """pv_facility 배치 INSERT."""
    sql = """
        INSERT INTO pv_facility (
            name, addr_road, addr_jibun, geom,
            install_type, status, capacity_kw, voltage, frequency,
            install_year, usage_detail, permit_date, permit_org,
            install_area_m2, data_date, source_file
        ) VALUES %s
    """
    template = """(
        %s, %s, %s,
        ST_GeomFromEWKT(%s),
        %s, %s, %s, %s, %s,
        %s, %s, %s::DATE, %s,
        %s, %s::DATE, %s
    )"""
    # geom이 None이면 ST_GeomFromEWKT(NULL) → NULL
    # psycopg2는 None을 NULL로 처리
    with conn.cursor() as cur:
        execute_values(cur, sql, rows, template=template, page_size=_BATCH_SIZE)


def load_substations(conn: psycopg2.extensions.connection) -> int:
    """
    substations_*.geojson → substation 테이블 적재.
    반환: 적재된 행 수
    """
    files = sorted(glob.glob(_SUBSTATIONS_GLOB))
    logger.info(f"변전소 GeoJSON 파일 수: {len(files)}")

    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE substation RESTART IDENTITY CASCADE")
    conn.commit()

    total = 0
    for fpath in files:
        with open(fpath, encoding="utf-8") as f:
            data = json.load(f)

        features = data.get("features", [])
        rows = []
        for feat in features:
            geom = feat.get("geometry")
            if not geom or geom.get("type") != "Point":
                continue
            coords = geom.get("coordinates", [])
            if len(coords) < 2:
                continue
            lng_val, lat_val = coords[0], coords[1]

            props = feat.get("properties", {})
            rows.append((
                props.get("name") or None,
                props.get("name_en") or None,
                f"SRID=4326;POINT({lng_val} {lat_val})",
                props.get("voltage") or None,
                props.get("substation_type") or None,
                props.get("frequency") or None,
                props.get("operator") or None,
                props.get("osm_id"),
                props.get("sido") or None,
            ))

        if rows:
            sql = """
                INSERT INTO substation (name, name_en, geom, voltage, sub_type, frequency, operator, osm_id, sido)
                VALUES %s
            """
            template = "(%s, %s, ST_GeomFromEWKT(%s), %s, %s, %s, %s, %s, %s)"
            with conn.cursor() as cur:
                execute_values(cur, sql, rows, template=template)
            conn.commit()
            total += len(rows)

        logger.info(f"  {Path(fpath).name}: {len(rows)}건")

    logger.info(f"substation 적재 완료: 총 {total:,}건")
    return total


def load_power_lines(conn: psycopg2.extensions.connection) -> int:
    """
    power_lines_*.geojson → power_line 테이블 적재.
    MultiLineString은 개별 LineString으로 분해하여 적재.
    반환: 적재된 행 수
    """
    files = sorted(glob.glob(_POWER_LINES_GLOB))
    logger.info(f"송배전선 GeoJSON 파일 수: {len(files)}")

    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE power_line RESTART IDENTITY CASCADE")
    conn.commit()

    total = 0
    for fpath in files:
        with open(fpath, encoding="utf-8") as f:
            data = json.load(f)

        features = data.get("features", [])
        rows = []
        for feat in features:
            geom = feat.get("geometry")
            if not geom:
                continue

            geom_type = geom.get("type")
            coords_list = []

            if geom_type == "LineString":
                coords_list = [geom.get("coordinates", [])]
            elif geom_type == "MultiLineString":
                # MultiLineString → 각 LineString으로 분해
                coords_list = geom.get("coordinates", [])
            else:
                continue

            props = feat.get("properties", {})

            for coords in coords_list:
                if len(coords) < 2:
                    continue
                # WKT LineString 생성
                points_str = ", ".join(f"{c[0]} {c[1]}" for c in coords if len(c) >= 2)
                if not points_str:
                    continue
                geom_wkt = f"SRID=4326;LINESTRING({points_str})"
                rows.append((
                    props.get("name") or None,
                    geom_wkt,
                    props.get("power_type") or None,
                    props.get("voltage") or None,
                    props.get("sido") or None,
                ))

        if rows:
            sql = """
                INSERT INTO power_line (name, geom, power_type, voltage, sido)
                VALUES %s
            """
            template = "(%s, ST_GeomFromEWKT(%s), %s, %s, %s)"
            with conn.cursor() as cur:
                execute_values(cur, sql, rows, template=template)
            conn.commit()
            total += len(rows)

        logger.info(f"  {Path(fpath).name}: {len(rows)}건")

    logger.info(f"power_line 적재 완료: 총 {total:,}건")
    return total


def verify_counts(conn: psycopg2.extensions.connection) -> None:
    """적재 후 행수 검증 및 요약 출력."""
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*), SUM(CASE WHEN geom IS NOT NULL THEN 1 ELSE 0 END) FROM pv_facility")
        pv_total, pv_coord = cur.fetchone()

        cur.execute("SELECT COUNT(*) FROM substation")
        sub_total = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM power_line")
        pl_total = cur.fetchone()[0]

    logger.info("=" * 60)
    logger.info("DB 적재 검증 결과")
    logger.info(f"  pv_facility  : {pv_total:>8,}건 (좌표 보유: {pv_coord:,}, 결측: {pv_total - pv_coord:,})")
    logger.info(f"  substation   : {sub_total:>8,}건")
    logger.info(f"  power_line   : {pl_total:>8,}건")
    logger.info("=" * 60)


def main() -> None:
    logger.info("ETL 시작 — PostGIS 데이터 적재")
    logger.info(f"데이터 경로: {_PARQUET_PATH.parent.parent}")

    conn = None
    try:
        conn = get_connection()
        logger.info(f"DB 연결 성공: {_DB_HOST}:{_DB_PORT}/{_DB_NAME}")

        # 1. 테이블 초기화
        setup_extensions_and_tables(conn)

        # 2. 발전소 parquet 적재
        load_pv_facility(conn)

        # 3. 변전소 GeoJSON 적재
        load_substations(conn)

        # 4. 송배전선 GeoJSON 적재
        load_power_lines(conn)

        # 5. 검증
        verify_counts(conn)

        logger.info("ETL 완료")

    except psycopg2.OperationalError as e:
        logger.error(f"DB 연결 실패: {e}")
        logger.error("Docker PostGIS가 실행 중인지 확인하세요: docker-compose up -d")
        sys.exit(1)
    except Exception as e:
        logger.error(f"ETL 중 오류 발생: {e}", exc_info=True)
        if conn:
            conn.rollback()
        sys.exit(1)
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    main()
