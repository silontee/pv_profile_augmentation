"""
SQLAlchemy ORM 모델.
PostGIS 공간 타입은 GeoAlchemy2로 매핑.
"""
from datetime import date, datetime
from typing import Optional

from geoalchemy2 import Geometry
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    Integer,
    Numeric,
    SmallInteger,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class PvFacility(Base):
    """
    태양광 발전소 메인 테이블.
    좌표 결측(4,718건) 허용 — geom IS NULL.
    """
    __tablename__ = "pv_facility"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # 기본 정보
    name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    addr_road: Mapped[Optional[str]] = mapped_column(Text, nullable=True)   # 도로명주소
    addr_jibun: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 지번주소

    # 공간 데이터 — NULL 허용 (좌표 결측)
    geom = Column(Geometry("POINT", srid=4326), nullable=True)

    # GENERATED ALWAYS AS (geom IS NOT NULL) STORED는 DB에서 자동 계산
    # ORM에서는 읽기 전용 컬럼으로 선언
    has_coord: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)

    # 설치 정보
    install_type: Mapped[Optional[str]] = mapped_column(Text, nullable=True)    # 설치상세위치구분명
    status: Mapped[str] = mapped_column(Text, nullable=False)                   # 가동상태구분명
    capacity_kw: Mapped[Optional[float]] = mapped_column(Numeric(15, 2), nullable=True)
    voltage: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    frequency: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    install_year: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)
    usage_detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)    # 세부용도
    install_area_m2: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)

    # 허가 정보
    permit_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    permit_org: Mapped[Optional[str]] = mapped_column(Text, nullable=True)      # 허가기관 (시군구 식별용)
    data_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)      # 데이터기준일자

    # 메타데이터
    source_file: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )


class Substation(Base):
    """
    변전소 테이블.
    OSM openinframap 데이터 기반.
    """
    __tablename__ = "substation"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    name_en: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 좌표 필수 (변전소는 좌표 결측 없음)
    geom = Column(Geometry("POINT", srid=4326), nullable=False)

    voltage: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sub_type: Mapped[Optional[str]] = mapped_column(Text, nullable=True)   # substation_type
    frequency: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    operator: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    osm_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    sido: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class PowerLine(Base):
    """
    송배전선 테이블.
    OSM openinframap 데이터 기반.
    """
    __tablename__ = "power_line"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # LineString 좌표 필수
    geom = Column(Geometry("LINESTRING", srid=4326), nullable=False)

    power_type: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    voltage: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sido: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
