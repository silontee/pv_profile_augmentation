"""
태양광 발전소 지도 시각화

parquet + openinframap GeoJSON을 레이어별로 지도에 표시.
출력: generator_next/map/output/pv_map.html

사용법:
    uv run python generator_next/map/generate_map.py
    uv run python generator_next/map/generate_map.py --no-infra   # 인프라 레이어 제외
    uv run python generator_next/map/generate_map.py --status 정상가동  # 특정 상태만
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import folium
from folium.plugins import FastMarkerCluster, GroupedLayerControl
import polars as pl

ROOT = Path(__file__).resolve().parents[2]
PARQUET_PATH = ROOT / "generator_next/source/processed/pv_facility_processed.parquet"
INFRA_DIR = ROOT / "generator_next/source/openinframap/by_sido"
OUTPUT_PATH = ROOT / "generator_next/map/output/pv_map.html"

# 가동상태별 색상
STATUS_COLOR = {
    "정상가동": "#2ecc71",   # 초록
    "가동중단": "#95a5a6",   # 회색
    "폐기":     "#2c3e50",   # 검정
}

STATUS_RADIUS = {
    "정상가동": 4,
    "가동중단": 4,
    "폐기":     3,
}


def load_plants(status_filter: str | None) -> pl.DataFrame:
    df = pl.read_parquet(PARQUET_PATH)
    df = df.filter(pl.col("위도").is_not_null() & pl.col("경도").is_not_null())
    if status_filter:
        df = df.filter(pl.col("가동상태구분명") == status_filter)
    print(f"[INFO] 발전소 로드: {len(df):,}건 (좌표 있음)")
    return df


def add_plant_layer(m: folium.Map, df: pl.DataFrame, status: str) -> folium.FeatureGroup:
    color = STATUS_COLOR.get(status, "#888888")
    radius = STATUS_RADIUS.get(status, 4)
    fg = folium.FeatureGroup(name=f"태양광 {status} ({len(df.filter(pl.col('가동상태구분명')==status)):,}개)", show=(status == "정상가동"))

    sub = df.filter(pl.col("가동상태구분명") == status)
    cols = [
        "위도", "경도",
        "태양광발전시설명",       # 0→2
        "설비용량",               # 1→3
        "허가일자",               # 2→4
        "허가기관",               # 3→5
        "소재지도로명주소",        # 4→6
        "소재지지번주소",          # 5→7
        "설치연도",               # 6→8
        "설치면적",               # 7→9
        "공급전압",               # 8→10
        "주파수",                 # 9→11
        "설치상세위치구분명",       # 10→12
        "세부용도",               # 11→13
        "가동상태구분명",          # 12→14
        "데이터기준일자",          # 13→15
    ]
    coords = sub.select(cols).to_dicts()

    # FastMarkerCluster — 대량 포인트에 최적
    callback = f"""
    function(row) {{
        var marker = L.circleMarker(
            new L.LatLng(row[0], row[1]),
            {{
                radius: {radius},
                color: '{color}',
                fillColor: '{color}',
                fillOpacity: 0.7,
                weight: 1
            }}
        );
        var d = function(v) {{ return v || '-'; }};
        var addr = d(row[6]) !== '-' ? d(row[6]) : d(row[7]);
        marker.bindPopup(
            '<b>' + d(row[2]) + '</b><br>' +
            '<hr style=\"margin:3px 0\">' +
            '가동상태: ' + d(row[14]) + '<br>' +
            '설비용량: ' + d(row[3]) + ' kW<br>' +
            '주소: ' + addr + '<br>' +
            '허가일자: ' + d(row[4]) + '<br>' +
            '허가기관: ' + d(row[5]) + '<br>' +
            '설치연도: ' + d(row[8]) + '<br>' +
            '설치면적: ' + d(row[9]) + ' m²<br>' +
            '공급전압: ' + d(row[10]) + ' V<br>' +
            '주파수: ' + d(row[11]) + ' Hz<br>' +
            '설치위치: ' + d(row[12]) + '<br>' +
            '세부용도: ' + d(row[13]) + '<br>' +
            '데이터기준일: ' + d(row[15]),
            {{maxWidth: 280}}
        );
        return marker;
    }}
    """
    data = [[
        r["위도"], r["경도"],
        r["태양광발전시설명"] or "", r["설비용량"] or "", r["허가일자"] or "",
        r["허가기관"] or "", r["소재지도로명주소"] or "", r["소재지지번주소"] or "",
        r["설치연도"] or "", r["설치면적"] or "", r["공급전압"] or "",
        r["주파수"] or "", r["설치상세위치구분명"] or "", r["세부용도"] or "",
        r["가동상태구분명"] or "", r["데이터기준일자"] or "",
    ] for r in coords]
    FastMarkerCluster(data, callback=callback).add_to(fg)
    fg.add_to(m)
    return fg


def _substation_radius(voltage_str: str) -> tuple[int, str]:
    """전압(V 단위 문자열) → (반지름, MW 등급 레이블)
    다중 전압(예: '345000;154000')은 최대값 기준.
    765kV → 1000MW급(r=16), 345kV → 500MW급(r=10), 154kV → 100MW급(r=6), 그 외 → r=3
    """
    try:
        max_v = max(int(v) for v in voltage_str.split(";") if v.strip().isdigit())
    except (ValueError, AttributeError):
        return 3, "-"
    if max_v >= 700_000:
        return 16, "1000MW급 (765kV)"
    if max_v >= 300_000:
        return 10, "500MW급 (345kV)"
    if max_v >= 130_000:
        return 6, "100MW급 (154kV)"
    return 3, f"{max_v // 1000}kV"


def add_substations(m: folium.Map) -> None:
    fg = folium.FeatureGroup(name="변전소 (OSM)", show=True)
    files = sorted(INFRA_DIR.glob("substations_*.geojson"))
    count = 0
    for f in files:
        data = json.loads(f.read_text(encoding="utf-8"))
        for feat in data["features"]:
            coord = feat["geometry"]["coordinates"]
            p = feat["properties"]
            name = p.get("name") or "변전소"
            voltage_str = p.get("voltage") or ""
            radius, mw_label = _substation_radius(voltage_str)
            def _val(key: str) -> str:
                return p.get(key) or "-"

            voltage_display = voltage_str or "-"
            # V → kV 변환 표기 (예: 154000;25000 → 154kV / 25kV)
            if voltage_str:
                parts = [v.strip() for v in voltage_str.split(";") if v.strip().isdigit()]
                voltage_display = " / ".join(f"{int(v)//1000}kV" for v in parts)

            popup_html = (
                f"<b>{name}</b><br>"
                f"영문명: {_val('name_en')}<br>"
                f"전압: {voltage_display}<br>"
                f"용량 등급: {mw_label}<br>"
                f"타입: {_val('substation_type')}<br>"
                f"주파수: {_val('frequency')} Hz<br>"
                f"운영사: {_val('operator')}<br>"
                f"위치형태: {_val('location')}<br>"
                f"OSM ID: {_val('osm_type')}/{_val('osm_id')}"
            )
            folium.CircleMarker(
                location=[coord[1], coord[0]],
                radius=radius,
                color="#3498db",
                fill=True,
                fill_color="#3498db",
                fill_opacity=0.8,
                popup=folium.Popup(popup_html, max_width=260),
                tooltip=f"{name} ({voltage_display}, {mw_label})",
            ).add_to(fg)
            count += 1
    fg.add_to(m)
    print(f"[INFO] 변전소 추가: {count:,}건")


def add_power_lines(m: folium.Map) -> None:
    fg = folium.FeatureGroup(name="송배전선 (OSM)", show=True)
    files = sorted(INFRA_DIR.glob("power_lines_*.geojson"))
    count = 0
    for f in files:
        data = json.loads(f.read_text(encoding="utf-8"))
        for feat in data["features"]:
            coords = feat["geometry"]["coordinates"]
            p = feat["properties"]
            latlngs = [[c[1], c[0]] for c in coords]
            if not latlngs:
                continue
            ptype = p.get("power_type", "line")
            color = "#e67e22" if ptype == "line" else "#95a5a6"
            weight = 2 if ptype == "line" else 1
            voltage = p.get("voltage", "")
            name = p.get("name") or p.get("description") or "송배전선"
            folium.PolyLine(
                latlngs,
                color=color,
                weight=weight,
                opacity=0.6,
                tooltip=f"{name} {voltage+'V' if voltage else ''}",
            ).add_to(fg)
            count += 1
    fg.add_to(m)
    print(f"[INFO] 송배전선 추가: {count:,}건")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-infra", action="store_true", help="인프라 레이어(변전소/송전선) 제외")
    parser.add_argument("--status", default=None, help="특정 가동상태만 표시 (예: 정상가동)")
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    args = parser.parse_args()

    print("[1/4] 지도 초기화...")
    m = folium.Map(
        location=[36.5, 127.5],
        zoom_start=7,
        tiles="CartoDB positron",
    )

    print("[2/4] 발전소 레이어 추가...")
    df = load_plants(args.status)
    statuses = [args.status] if args.status else ["정상가동", "가동중단", "폐기"]
    for status in statuses:
        add_plant_layer(m, df, status)

    if not args.no_infra:
        print("[3/4] 인프라 레이어 추가...")
        add_substations(m)
        add_power_lines(m)
    else:
        print("[3/4] 인프라 레이어 스킵.")

    print("[4/4] 레이어 컨트롤 추가 및 저장...")
    folium.LayerControl(collapsed=False).add_to(m)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    m.save(str(args.output))
    print(f"[DONE] 저장 완료: {args.output}")


if __name__ == "__main__":
    main()
