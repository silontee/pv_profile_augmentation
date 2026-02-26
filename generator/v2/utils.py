import pandas as pd
import geopandas as gpd
import pickle
from pathlib import Path
from typing import List, Tuple
import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

# —————————————————————————————
# 전역 변수 선언 및 파일 한 번만 로드
BASE_DIR = Path(
    "/Users/mousebook/Documents/university/연구실/solar/generator/v2/source"
)
CSV_DATA = BASE_DIR / "최종3.csv"
CODES_CSV = BASE_DIR / "최종_기반_기초자치단체별_데이터2.csv"  # 구 지역코드.csv
REGION_PAIRS = BASE_DIR / "최종2_지역코드_set.csv"
GDF_DICT_PKL = BASE_DIR / "gdf_v3.pkl"
SUBSTATIONS_GEOJSON = BASE_DIR / "openstreetmap/filtered_substations.geojson"
POWERLINE_GEOJSON = BASE_DIR / "openstreetmap/filtered_power_lines.geojson"
MAPPING_CSV = BASE_DIR / "openstreetmap/subs_region_mapping.csv"
COASTLINE_GEOJSON = BASE_DIR / "해안선/2023년 전국해안선_shp/2023년 전국해안선.shp"

# 1) 최종3.csv 로드
df = pd.read_csv(CSV_DATA, encoding="utf-8-sig")
df["설비용량"] = pd.to_numeric(df["설비용량"], errors="coerce")

# 2) 지역코드 매핑 로드
mapping_df = pd.read_csv(CODES_CSV, encoding="utf-8-sig", header=0)
mapping_df = mapping_df[["region", "region_code"]].copy()
mapping_df.columns = ["region", "region_code"]
mapping_df["region_code"] = mapping_df["region_code"].astype(int)
parts = mapping_df["region"].str.strip().str.split(" ", n=1, expand=True)
mapping_df["region_1depth_name"] = parts[0]
mapping_df["region_2depth_name"] = parts[1]

# 3) gdf_v2.pkl 로드 (시군구 경계)
with open(GDF_DICT_PKL, "rb") as f:
    gdf_dict = pickle.load(f)


# 4) GeoJSON 변전소 데이터 로드 + orig_idx 보존
gdf_subs = gpd.read_file(SUBSTATIONS_GEOJSON)
gdf_subs = gdf_subs.reset_index().rename(columns={"index": "orig_idx"})
if gdf_subs.crs is None:
    gdf_subs.set_crs(epsg=4326, inplace=True)

# 5) subs_region_mapping.csv 로드
subs_mapping = pd.read_csv(
    MAPPING_CSV,
    encoding="utf-8-sig",
    dtype={"orig_idx": "Int64", "SIG_CD": "Int64", "SIG_KOR_NM": str},  # 대문자 I
)
# —————————————————————————————


def filter_region_and_get_code_and_geom(depth1: str, depth2: str):
    """
    추출한 데이터에 한해서 행정구역을 제공하면은 df, region_code, gdf 를 반환합니다.
    """
    # (1) df 필터링
    sub_df = df[
        (df["region_1depth_name"] == depth1) & (df["region_2depth_name"] == depth2)
    ].copy()
    if sub_df.empty:
        raise ValueError(f"No rows for {depth1} {depth2!r} in CSV")

    # (2) 코드 찾기
    region_code = find_region_code(depth1, depth2)

    # (3) 지역코드에 해당하는 GeoDataFrame을 찾기
    gdf_filtered = get_gdf_by_region_code(region_code=region_code)

    return sub_df, region_code, gdf_filtered


def find_region_code(depth1: str, depth2: str) -> int:
    code_row = mapping_df[
        (mapping_df["region_1depth_name"] == depth1)
        & (mapping_df["region_2depth_name"] == depth2)
    ]
    if code_row.empty:
        raise ValueError(f"No mapping for {depth1} {depth2!r}")
    return int(code_row["region_code"].iloc[0])


def get_gdf_by_region_code(
    depth1=None, depth2=None, region_code: int = None
) -> gpd.GeoDataFrame:
    """
    지역코드에 해당하는 GeoDataFrame을 반환합니다.
    """

    if not region_code:
        if depth1 is None or depth2 is None:
            raise ValueError(
                "depth1 and depth2 must be provided if region_code is not given"
            )
        region_code = find_region_code(depth1, depth2)

    prov_key = str(region_code)[:2]
    gdf_prov = gdf_dict.get(prov_key)
    if gdf_prov is None:
        raise KeyError(f"No GeoDataFrame for prov_key '{prov_key}'")

    # (4) SIG_CD 필터
    mask = gdf_prov["SIG_CD"].astype(str) == str(region_code)
    gdf_filtered = gdf_prov.loc[mask].copy()
    if gdf_filtered.empty:
        raise KeyError(f"No rows for SIG_CD == {region_code}")

    return gdf_filtered


def get_all_regions_gdf() -> gpd.GeoDataFrame:
    """
    모든 행정구역(load_all_region_pair)별 GeoDataFrame을
    get_gdf_by_region_code로 로드한 뒤 하나로 합쳐 반환합니다.
    """
    regions = load_all_region_pair()  # List[Tuple[depth1, depth2]]
    gdfs = []
    for depth1, depth2 in regions:
        try:
            gdf = get_gdf_by_region_code(depth1, depth2)
            gdfs.append(gdf)
        except Exception as e:
            # 혹시 누락된 지역이 있으면 로그만 남기고 넘어갑니다.
            print(f"⚠️ {depth1} {depth2} 로드 실패: {e}")
    if not gdfs:
        raise ValueError("로드된 GeoDataFrame이 없습니다.")
    # 인덱스 리셋 및 단일 CRS 확인 후 합치기
    full = gpd.GeoDataFrame(pd.concat(gdfs, ignore_index=True), crs=gdfs[0].crs)
    return full


def load_region_pairs() -> List[Tuple[str, str]]:
    """
    추출한 지역의 행정구역을 분할하며 List로 반환한다.
    """
    pairs: List[Tuple[str, str]] = []
    df_pairs = pd.read_csv(
        REGION_PAIRS, encoding="utf-8-sig", header=0, names=["region"]
    )
    for region in df_pairs["region"].dropna().str.strip():
        parts = region.split(" ", 1)
        if len(parts) != 2:
            raise ValueError(f"잘못된 형식의 region: {region!r}")
        pairs.append((parts[0], parts[1]))
    return pairs


def load_all_region_pair():
    """
    지역코드와 지역명을 모두 로드합니다.
    """
    df = pd.read_csv(CODES_CSV, encoding="utf-8-sig", header=0)

    pairs: List[Tuple[str, str]] = []
    for region in df["region"].dropna().str.strip():
        parts = region.split(" ", 1)
        if len(parts) != 2:
            raise ValueError(f"잘못된 형식의 region: {region!r}")
        pairs.append((parts[0], parts[1]))
    return pairs


def get_substations_by_region(region_code: int) -> gpd.GeoDataFrame:
    """
    전역 subs_mapping, gdf_subs 를 참조해서
    특정 SIG_CD(region_code)에 속하는 변전소만 반환합니다.
    """
    idx_list = subs_mapping.loc[
        subs_mapping["SIG_CD"] == region_code, "orig_idx"
    ].tolist()
    if not idx_list:
        # 빈 GeoDataFrame 반환
        return gpd.GeoDataFrame(columns=gdf_subs.columns, crs=gdf_subs.crs)
    return gdf_subs[gdf_subs["orig_idx"].isin(idx_list)].copy()


def plot_mountain_base(
    gdf_region: gpd.GeoDataFrame,
    alpha_mtn: float = 0.6,
    figsize: tuple = (8, 8),
    title: str = None,
    font_family: str = "AppleGothic",
):
    """
    산지 영역만 초록색으로 채운 밑그림을 그리고,
    비산지(Non-Mountain) 영역은 채우지 않습니다.

    Parameters
    ----------
    gdf_region : GeoDataFrame
        filter_region_and_get_code_and_geom() 으로 얻은 GeoDataFrame.
        반드시 'Mountain Area' 컬럼을 포함해야 합니다.
    alpha_mtn : float
        산지 영역 투명도 (0~1)
    figsize : tuple
        그림 크기 (가로, 세로)
    title : str
        그림 제목 (한글 지원)
    font_family: str
        matplotlib 에서 사용할 한글 폰트 이름
    """
    # 한글 폰트 셋팅
    plt.rc("font", family=font_family)
    plt.rc("axes", unicode_minus=False)

    fig, ax = plt.subplots(figsize=figsize)
    # 1) 경계 윤곽선만 그리고
    gdf_region.geometry.boundary.plot(ax=ax, color="black", linewidth=1)

    # 2) 산지 영역만 초록색으로 채우기
    gpd.GeoSeries(gdf_region["Mountain Area"], crs=gdf_region.crs).plot(
        ax=ax, color="green", alpha=alpha_mtn
    )

    # 3) 범례 (산지만)
    legend_patches = [
        Patch(facecolor="green", edgecolor="none", label="산지"),
    ]
    ax.legend(handles=legend_patches, loc="upper right", frameon=False)

    if title:
        ax.set_title(title, fontsize=16)
    ax.axis("off")
    plt.tight_layout()
    return fig, ax
