"""OpenInfraMap 수집 데이터 지도 시각화.

수집한 변전소(Point) + 송전선(LineString) + 발전소(Point) GeoJSON을
지도 위에 표시한다.
출력: HTML 인터랙티브 맵 (folium) 또는 정적 이미지 (matplotlib).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

# --------------- folium 방식 (인터랙티브) ---------------


def render_folium(
    substations_path: Path | None,
    lines_path: Path | None,
    plants_path: Path | None,
    output: Path,
) -> None:
    import folium

    # 어두운 배경 (OpenInfraMap 스타일)
    m = folium.Map(
        location=[37.5665, 126.9780],
        zoom_start=11,
        tiles="CartoDB dark_matter",
    )

    # 송·배전선 / 케이블
    if lines_path and lines_path.exists():
        with lines_path.open(encoding="utf-8") as f:
            lines_fc = json.load(f)

        for feat in lines_fc["features"]:
            coords = feat["geometry"]["coordinates"]
            if not coords:
                continue
            props = feat["properties"]
            latlngs = [[c[1], c[0]] for c in coords]

            style = _line_style(props)
            voltage = props.get("voltage", "")
            power_type = props.get("power_type", "")
            name = props.get("name", "")

            kv_str = _format_voltage(voltage)
            type_label = {"line": "송전선", "minor_line": "배전선", "cable": "케이블"}.get(
                power_type, "전력선"
            )
            tooltip = f"{type_label}: {name}" if name else type_label
            if kv_str:
                tooltip += f" ({kv_str})"

            folium.PolyLine(
                latlngs,
                color=style["color"],
                weight=style["weight"],
                opacity=style["opacity"],
                dash_array=style.get("dash_array"),
                tooltip=tooltip,
            ).add_to(m)

    # 변전소
    if substations_path and substations_path.exists():
        with substations_path.open(encoding="utf-8") as f:
            subs_fc = json.load(f)

        for feat in subs_fc["features"]:
            lon, lat = feat["geometry"]["coordinates"]
            if lat is None or lon is None:
                continue
            props = feat["properties"]
            name = props.get("name", "") or props.get("name_en", "") or "변전소"
            voltage = props.get("voltage", "")
            sub_type = props.get("substation_type", "")
            kv_str = _format_voltage(voltage)

            popup = (
                f"<b>{name}</b><br>"
                f"유형: {sub_type}<br>"
                f"전압: {kv_str or '미상'}<br>"
                f"운영: {props.get('operator', '') or '미상'}"
            )

            # 변전소 전압별 크기/색상
            radius, color = _substation_style(voltage)
            folium.CircleMarker(
                location=[lat, lon],
                radius=radius,
                color="white",
                weight=1,
                fill=True,
                fill_color=color,
                fill_opacity=0.9,
                popup=popup,
                tooltip=name,
            ).add_to(m)

    # 발전소 / 발전기
    if plants_path and plants_path.exists():
        with plants_path.open(encoding="utf-8") as f:
            plants_fc = json.load(f)

        for feat in plants_fc["features"]:
            lon, lat = feat["geometry"]["coordinates"]
            if lat is None or lon is None:
                continue
            props = feat["properties"]
            power_type = props.get("power_type", "")
            name = props.get("name", "") or props.get("name_en", "") or (
                "발전소" if power_type == "plant" else "발전기"
            )
            source = props.get("plant_source", "")
            output_elec = props.get("plant_output", "")

            popup = (
                f"<b>{name}</b><br>"
                f"유형: {power_type}<br>"
                f"에너지원: {source or '미상'}<br>"
                f"출력: {output_elec or '미상'}<br>"
                f"운영: {props.get('operator', '') or '미상'}"
            )

            radius, color, icon = _plant_style(source, power_type)
            folium.CircleMarker(
                location=[lat, lon],
                radius=radius,
                color="white",
                weight=1,
                fill=True,
                fill_color=color,
                fill_opacity=0.9,
                popup=popup,
                tooltip=f"{icon} {name}",
            ).add_to(m)

    # 범례
    legend_html = """
    <div style="position:fixed; bottom:30px; left:30px; z-index:1000;
         background:rgba(0,0,0,0.85); padding:14px 18px; border-radius:8px;
         border:1px solid #555; font-size:13px; color:#eee;
         font-family:'Noto Sans KR',sans-serif; line-height:1.8;">
      <b style="font-size:14px;">전력 인프라</b><br>
      <svg width="30" height="4" style="vertical-align:middle;">
        <line x1="0" y1="2" x2="30" y2="2" stroke="#c41a1a" stroke-width="4"/></svg> 765kV<br>
      <svg width="30" height="4" style="vertical-align:middle;">
        <line x1="0" y1="2" x2="30" y2="2" stroke="#e85d15" stroke-width="3.5"/></svg> 345kV<br>
      <svg width="30" height="4" style="vertical-align:middle;">
        <line x1="0" y1="2" x2="30" y2="2" stroke="#c78d0a" stroke-width="3"/></svg> 154kV<br>
      <svg width="30" height="4" style="vertical-align:middle;">
        <line x1="0" y1="2" x2="30" y2="2" stroke="#4aa82e" stroke-width="2"/></svg> 66kV 이하<br>
      <svg width="30" height="4" style="vertical-align:middle;">
        <line x1="0" y1="2" x2="30" y2="2" stroke="#7c4dff" stroke-width="1.5"/></svg> 배전선<br>
      <svg width="30" height="4" style="vertical-align:middle;">
        <line x1="0" y1="2" x2="30" y2="2" stroke="#29b6f6" stroke-width="2"
              stroke-dasharray="6,4"/></svg> 케이블<br>
      <svg width="30" height="10" style="vertical-align:middle;">
        <circle cx="6" cy="5" r="5" fill="#e85d15" stroke="white" stroke-width="1"/></svg> 변전소<br>
      <b style="font-size:12px; margin-top:4px; display:inline-block;">발전소</b><br>
      <svg width="30" height="10" style="vertical-align:middle;">
        <circle cx="6" cy="5" r="5" fill="#ffeb3b" stroke="white" stroke-width="1"/></svg> 태양광<br>
      <svg width="30" height="10" style="vertical-align:middle;">
        <circle cx="6" cy="5" r="5" fill="#26c6da" stroke="white" stroke-width="1"/></svg> 풍력<br>
      <svg width="30" height="10" style="vertical-align:middle;">
        <circle cx="6" cy="5" r="5" fill="#42a5f5" stroke="white" stroke-width="1"/></svg> 수력<br>
      <svg width="30" height="10" style="vertical-align:middle;">
        <circle cx="6" cy="5" r="5" fill="#ef5350" stroke="white" stroke-width="1"/></svg> 화력<br>
      <svg width="30" height="10" style="vertical-align:middle;">
        <circle cx="6" cy="5" r="5" fill="#ab47bc" stroke="white" stroke-width="1"/></svg> 원자력<br>
      <svg width="30" height="10" style="vertical-align:middle;">
        <circle cx="6" cy="5" r="5" fill="#78909c" stroke="white" stroke-width="1"/></svg> 기타
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))

    output.parent.mkdir(parents=True, exist_ok=True)
    m.save(str(output))
    print(f"지도 저장: {output}")


def _parse_voltage_kv(voltage: str) -> float | None:
    """전압 문자열 → 대표 kV 값. 파싱 실패 시 None."""
    if not voltage:
        return None
    try:
        vals = [
            int(v.strip())
            for v in voltage.replace(";", ",").split(",")
            if v.strip().isdigit()
        ]
        return max(vals) / 1000 if vals else None
    except ValueError:
        return None


def _format_voltage(voltage: str) -> str:
    """전압 문자열을 사람이 읽기 좋은 형태로."""
    kv = _parse_voltage_kv(voltage)
    if kv is None:
        return ""
    if kv >= 1:
        return f"{kv:g}kV"
    return f"{kv * 1000:g}V"


def _line_style(props: dict) -> dict:
    """power_type + voltage → OpenInfraMap 스타일 색상/굵기/점선."""
    power_type = props.get("power_type", "")
    voltage = props.get("voltage", "")
    kv = _parse_voltage_kv(voltage)

    # 케이블: 파란 점선
    if power_type == "cable":
        return {"color": "#29b6f6", "weight": 2, "opacity": 0.85, "dash_array": "6 4"}

    # 배전선: 보라
    if power_type == "minor_line":
        return {"color": "#7c4dff", "weight": 1.5, "opacity": 0.7}

    # 송전선: 전압별 색상 + 굵기
    if kv is None:
        return {"color": "#aaaaaa", "weight": 1.5, "opacity": 0.5}
    if kv >= 765:
        return {"color": "#c41a1a", "weight": 5, "opacity": 0.9}
    if kv >= 345:
        return {"color": "#e85d15", "weight": 4, "opacity": 0.9}
    if kv >= 154:
        return {"color": "#c78d0a", "weight": 3, "opacity": 0.85}
    if kv >= 66:
        return {"color": "#4aa82e", "weight": 2.5, "opacity": 0.8}
    return {"color": "#4aa82e", "weight": 2, "opacity": 0.7}


def _substation_style(voltage: str) -> tuple[int, str]:
    """변전소 전압 → (반지름, 색상)."""
    kv = _parse_voltage_kv(voltage)
    if kv is None:
        return 5, "#aaaaaa"
    if kv >= 345:
        return 9, "#e85d15"
    if kv >= 154:
        return 7, "#c78d0a"
    return 5, "#4aa82e"


# 에너지원 키워드 → (색상, 아이콘)
_SOURCE_STYLES: dict[str, tuple[str, str]] = {
    "solar":       ("#ffeb3b", "S"),
    "wind":        ("#26c6da", "W"),
    "hydro":       ("#42a5f5", "H"),
    "coal":        ("#ef5350", "C"),
    "gas":         ("#ef5350", "G"),
    "oil":         ("#ef5350", "O"),
    "nuclear":     ("#ab47bc", "N"),
    "biomass":     ("#66bb6a", "B"),
    "geothermal":  ("#ff7043", "T"),
    "waste":       ("#8d6e63", "R"),
}


def _plant_style(source: str, power_type: str) -> tuple[int, str, str]:
    """발전소/발전기 에너지원 → (반지름, 색상, 아이콘 문자)."""
    radius = 8 if power_type == "plant" else 5
    src = source.lower()
    for key, (color, icon) in _SOURCE_STYLES.items():
        if key in src:
            return radius, color, icon
    return radius, "#78909c", "?"


# --------------- matplotlib 방식 (정적) ---------------


def render_matplotlib(
    substations_path: Path | None,
    lines_path: Path | None,
    output: Path,
) -> None:
    import geopandas as gpd
    import matplotlib.pyplot as plt

    plt.rc("font", family="AppleGothic")
    plt.rc("axes", unicode_minus=False)

    fig, ax = plt.subplots(1, 1, figsize=(12, 10))

    if lines_path and lines_path.exists():
        lines_gdf = gpd.read_file(lines_path)
        lines_gdf.plot(ax=ax, color="#f39c12", linewidth=1.5, label="송전선")

    if substations_path and substations_path.exists():
        subs_gdf = gpd.read_file(substations_path)
        subs_gdf.plot(ax=ax, color="#e74c3c", markersize=30, label="변전소", zorder=5)

    ax.set_title("송·변전 인프라 (OpenInfraMap/OSM)", fontsize=16)
    ax.legend(fontsize=12)
    ax.set_xlabel("경도")
    ax.set_ylabel("위도")

    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(output), dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"이미지 저장: {output}")


def main() -> None:
    parser = argparse.ArgumentParser(description="OpenInfraMap 수집 데이터 지도 시각화")
    parser.add_argument("--substations", type=Path, default=None, help="변전소 GeoJSON 경로")
    parser.add_argument("--lines", type=Path, default=None, help="송전선 GeoJSON 경로")
    parser.add_argument("--plants", type=Path, default=None, help="발전소 GeoJSON 경로")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("src/data/openinframap/infra_map.html"),
        help="출력 파일 경로 (.html → folium, .png → matplotlib)",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="GeoJSON 파일이 있는 디렉토리 (자동 탐색)",
    )
    args = parser.parse_args()

    substations = args.substations
    lines = args.lines
    plants = args.plants

    # --data-dir 지정 시 가장 최근 파일 자동 탐색
    if args.data_dir and args.data_dir.is_dir():
        if not substations:
            candidates = sorted(args.data_dir.glob("substations_*.geojson"))
            substations = candidates[-1] if candidates else None
        if not lines:
            candidates = sorted(args.data_dir.glob("power_lines_*.geojson"))
            lines = candidates[-1] if candidates else None
        if not plants:
            candidates = sorted(args.data_dir.glob("plants_*.geojson"))
            plants = candidates[-1] if candidates else None

    if not substations and not lines and not plants:
        print("표시할 GeoJSON 파일이 없습니다. --data-dir를 지정하세요.")
        return

    if args.output.suffix == ".png":
        render_matplotlib(substations, lines, output=args.output)
    else:
        render_folium(substations, lines, plants, args.output)


if __name__ == "__main__":
    main()
