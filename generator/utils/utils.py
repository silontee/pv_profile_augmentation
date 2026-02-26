import geopandas as gpd
import pandas as pd
import dash
from dash import dcc, html, dash_table
import requests, json
import pandas as pd
import os
import netCDF4 as nc
import utils
import numpy as np
import pickle

KAKAO_PRIVATE_KEY = "c8e449b6ac54644a0268fd6dd017eb8d"  # 카카오
DATA_PRIVATE_KEY = "H22OmOJexqCM+zsw7uefTycvxU0xHGpf1hpBO2WF2TEPma8bcdd8GP8xVkBzGnmMXE9s4aXjUgHbVUcZGkR8vQ=="  # 공공데이터
KMA_PRIVATE_KEY = "Nc26__Y4SRONuv_2OJkTPw"  # 기상청

package_directory = (
    "/Users/mousebook/Documents/university/연구실/2024 추계/workspace/generator/"
)

source_directory = os.path.join(package_directory, "source")
location_pickle_directory = os.path.join(source_directory, "location-pickle")
location_directory = os.path.join(source_directory, "location")
population_directory = os.path.join(source_directory, "population")
shp_시도_file_path = os.path.join(source_directory, "shp", "시도", "ctprvn.shp")
shp_시군구_file_path = os.path.join(source_directory, "shp", "시군구", "sig.shp")

도 = "경상남도"
시군구 = "거제시"


class Location:
    @staticmethod
    def find_have_not_latitudes_and_longitude(self, df):
        return df[df["위도"].isnull() | df["경도"].isnull()]

    @staticmethod
    def get_location_by_address(address):
        """
            {
          "documents": [
            {
              "address": {
                "address_name": "전남 화순군 춘양면 우봉리 50-3",
                "b_code": "4679032033",
                "h_code": "4679032000",
                "main_address_no": "50",
                "mountain_yn": "N",
                "region_1depth_name": "전남",
                "region_2depth_name": "화순군",
                "region_3depth_h_name": "춘양면",
                "region_3depth_name": "춘양면 우봉리",
                "sub_address_no": "3",
                "x": "126.987165216146",
                "y": "34.9567567148959"
              },
              "address_name": "전남 화순군 춘양면 우봉리 50-3",
              "address_type": "REGION_ADDR",
              "road_address": {},
              "x": "126.987165216146",
              "y": "34.9567567148959"
            }
          ],
          "meta": {
            "is_end": True,
            "pageable_count": 1,
            "total_count": 1
          }
        }

        """

        url = f"https://dapi.kakao.com/v2/local/search/address.json?query={address}"
        headers = {"Authorization": f"KakaoAK {KAKAO_PRIVATE_KEY}"}
        api_json = json.loads(str(requests.get(url, headers=headers).text))
        print(api_json)  # test
        return api_json["documents"][0]["address"]

    @staticmethod
    async def get_location_by_address_async(session, address):
        url = f"https://dapi.kakao.com/v2/local/search/address.json?query={address}"
        headers = {"Authorization": f"KakaoAK {KAKAO_PRIVATE_KEY}"}
        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                data = await response.json()  # API 응답을 JSON으로 변환
                return data  # 그대로 반환
            else:
                return response.status  # 상태 코드 반환


from datetime import datetime, timedelta


class TimeRangeSplitter:
    def __init__(self, starttime: str, endtime: str, minutes: int = 60):
        # 문자열을 datetime 객체로 변환 (포맷: YYYYMMDDHHMM)
        self.starttime = datetime.strptime(starttime, "%Y%m%d%H%M")
        self.endtime = datetime.strptime(endtime, "%Y%m%d%H%M")

        # 현재 시간 초기화
        self.current_time = self.starttime

        # 구간을 1시간 단위로 설정
        self.delta = timedelta(minutes=minutes)

    def __iter__(self):
        # 객체 자체를 반환하므로 이터레이터로 사용 가능
        return self

    def __next__(self):
        # 현재 시간이 끝 시간보다 크면 StopIteration 예외 발생
        if self.current_time >= self.endtime:
            raise StopIteration

        # 현재 시간 범위를 저장
        start_time = self.current_time
        end_time = min(self.current_time + self.delta, self.endtime)

        # 다음 시간 범위를 계산
        self.current_time += self.delta

        # 현재 시간 범위를 반환
        return (start_time.strftime("%Y%m%d%H%M"), end_time.strftime("%Y%m%d%H%M"))


class WeatherResponseData:
    def __init__(self, starttime: str, endtime: str, data, index=None):
        self.starttime = starttime
        self.endtime = endtime
        self.data = data
        self._index = index

    def __lt__(self, other):
        return self.starttime < other.starttime

    @property
    def index(self):
        return self._index

    @index.setter
    def index(self, new_value):
        self._index = new_value

    def __str__(self):
        return f"[{self.index}] {self.starttime} ~ {self.endtime}: {self.data[:20]}"

    def __repr__(self):
        return self.__str__()

    def to_dict(self):
        return {
            "starttime": self.starttime,
            "endtime": self.endtime,
            "data": self.data,
            "index": self.index,
        }


class GridRepository:

    def __init__(self):
        path = os.path.join(utils.source_directory, "sfc_grid_latlon.nc")
        fdata = nc.Dataset(path)
        self.fdata = fdata
        self.latitudes = fdata.variables["lat"][:]  # (2049, 2049)
        self.longitudes = fdata.variables["lon"][:]  # (2049, 2049)

    def find_nearest_grid_point(self, target_lat, target_lon):
        # 각 격자점에서의 위도와 경도의 차이 계산
        lat_diff = np.abs(self.latitudes - target_lat)
        lon_diff = np.abs(self.longitudes - target_lon)

        # 차이를 더하여 가장 작은 값을 가진 인덱스를 찾음
        total_diff = lat_diff + lon_diff
        min_index = np.unravel_index(np.argmin(total_diff), total_diff.shape)

        return min_index


def get_center_point(df):
    """
    주어진 데이터프레임의 중심점을 반환합니다.
    :param df: 데이터프레임
    :return: 중심점 (위도, 경도)
    """
    center = (
        df["위도"].mean(),
        df["경도"].mean(),
    )
    return center


def get_gdf(path=shp_시군구_file_path):
    # .shp 파일을 geopandas로 불러오기
    gdf = gpd.read_file(path, encoding="cp949")

    # 현재 CRS 설정 (예: EPSG:5174 또는 해당 shp 파일의 실제 좌표계)
    gdf = gdf.set_crs(epsg=5179)  # 여기서 EPSG 코드를 파일에 맞게 변경해야 함

    # 지역 코드 최신화
    if path == shp_시군구_file_path:
        gdf.loc[gdf["SIG_CD"].str.startswith("45"), "SIG_CD"] = gdf[
            "SIG_CD"
        ].str.replace("^45", "52", regex=True)
    return gdf.to_crs(epsg=4326)


def get_region_by_name(gdf, kor_name):
    return gdf[gdf["SIG_KOR_NM"] == kor_name]


def show_df_detail(file_path, encoding="utf-8"):
    df = pd.read_csv(file_path, encoding=encoding)

    # Dash 앱 생성
    app = dash.Dash(__name__)

    # 레이아웃 설정
    app.layout = html.Div(
        [
            dash_table.DataTable(
                id="table",
                columns=[{"name": i, "id": i} for i in df.columns],
                data=df.to_dict("records"),
                page_size=10,  # 페이지당 10개의 행
                style_table={"overflowX": "auto"},  # 테이블 가로 스크롤 허용
                filter_action="native",  # 필터링 기능
                sort_action="native",  # 정렬 기능
            )
        ]
    )
    app.run_server(debug=True)


def cp949_to_utf_8(file_path):
    # 여러 인코딩 방식을 시도하여 파일 읽기
    encodings = ["cp949", "utf-8", "latin1", "euc-kr"]

    for enc in encodings:
        try:
            df = pd.read_csv(file_path, encoding=enc)
            df.to_csv(file_path, encoding="utf-8", index=False)
            print(f"{file_path} 파일이 {enc} 인코딩으로 변환되었습니다.")
            break  # 파일을 성공적으로 읽었으므로 종료
        except UnicodeDecodeError:
            print(
                f"{file_path} 파일을 {enc} 인코딩으로 읽을 수 없습니다. 다른 인코딩을 시도합니다."
            )
        except Exception as e:
            print(f"다른 에러 발생: {e}")


def get_region_cd(location):
    url = "http://apis.data.go.kr/1741000/StanReginCd/getStanReginCdList"
    params = {
        "ServiceKey": DATA_PRIVATE_KEY,
        "pageNo": 1,
        "numOfRows": 3,
        "type": "json",
        "locatadd_nm": location,
    }
    response = requests.get(url, params=params).json()
    try:
        response = int(response["StanReginCd"][1]["row"][0]["region_cd"]) // 100000
    except Exception as e:
        response = None
    return response


def validate_location(df):
    """
    데이터프레임의 위도와 경도가 유효한지 확인합니다.
    :param df: 데이터프레임
    :return: 유효한 데이터프레임
    """
    return df[
        (df["위도"] > 30) & (df["위도"] < 45) & (df["경도"] > 120) & (df["경도"] < 135)
    ]


def validate_df(df):
    # 위도, 경도 컬럼이 모두 null이 아닌지
    if df["위도"].isnull().sum() > 0 or df["경도"].isnull().sum() > 0:
        raise ValueError("데이터프레임에 결측치가 있습니다.")


def get_path_by도시군구(도, 시군구):
    return os.path.join(source_directory, 도, f"3.{도}_{시군구}.csv")


def get_df_by도시군구(도, 시군구):
    source = get_path_by도시군구(도, 시군구)
    return pd.read_csv(source)


def 도_구하기(df):
    return list(set(df["도"]))


def 시군구_구하기(df, 도):
    return list(set(df[df["도"] == 도]["시군구"]))


def 시군구별_갯수_구하기(df, 도, 시군구):
    filtered_df = df[df["도"] == 도]
    filtered_df = filtered_df[filtered_df["시군구"] == 시군구]
    return len(filtered_df)


def 시군구별_설비용량_합_구하기(df, 도, 시군구):
    filtered_df = df[df["도"] == 도]
    filtered_df = filtered_df[filtered_df["시군구"] == 시군구]
    return filtered_df["설비용량"].sum()


def get_validated_df(df):
    # 위도, 경도 컬럼이 모두 null이 아닌지
    if df["위도"].isnull().sum() > 0 or df["경도"].isnull().sum() > 0:
        raise ValueError("데이터프레임에 결측치가 있습니다.")
    return df


def 도_시군구의_gdf_가져오기(도, 시군구):
    region_pd = pd.read_csv(
        "/Users/mousebook/Documents/university/연구실/2024 추계/workspace/generator/source/region_cd.csv"
    )
    region_cd = region_pd[region_pd["지역명"] == f"{도} {시군구}"]["지역코드"].values[0]
    prefix = str(region_cd)[:2]
    file_path = "/Users/mousebook/Documents/university/연구실/2024 추계/workspace/generator/source/shp_pickle/"
    with open(file_path + f"{prefix}_separate.pkl", "rb") as f:
        gdf = pickle.load(f)
    return gdf[gdf["SIG_CD"].astype(str) == str(region_cd)]


def get_rps():
    path = "/Users/mousebook/Documents/university/연구실/2024 추계/workspace/generator/source/RPS.pkl"
    with open(path, "rb") as f:
        return pickle.load(f)


def get_RPS_와의_차이():
    return pd.read_csv(os.path.join(utils.source_directory, "2-6.RPS와의 차이.csv"))
