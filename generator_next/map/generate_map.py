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
    "가동중단": "#f39c12",   # 주황
    "폐기":     "#e74c3c",   # 빨강
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
    coords = sub.select(["위도", "경도", "태양광발전시설명", "설비용량", "허가일자"]).to_dicts()

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
        marker.bindPopup(
            '<b>' + (row[2] || '이름없음') + '</b><br>' +
            '설비용량: ' + (row[3] || '-') + ' kW<br>' +
            '허가일자: ' + (row[4] || '-')
        );
        return marker;
    }}
    """
    data = [[r["위도"], r["경도"], r["태양광발전시설명"] or "", r["설비용량"] or "", r["허가일자"] or ""] for r in coords]
    FastMarkerCluster(data, callback=callback).add_to(fg)
    fg.add_to(m)
    return fg


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
            folium.CircleMarker(
                location=[coord[1], coord[0]],
                radius=5,
                color="#3498db",
                fill=True,
                fill_color="#3498db",
                fill_opacity=0.8,
                popup=folium.Popup(
                    f"<b>{name}</b><br>전압: {p.get('voltage','-')}<br>타입: {p.get('substation_type','-')}",
                    max_width=200,
                ),
                tooltip=name,
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
