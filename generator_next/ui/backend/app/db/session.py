"""
SQLAlchemy 비동기 세션 설정.
asyncpg 드라이버 사용, 환경변수 DATABASE_URL로 오버라이드 가능.
"""
import os
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

# 환경변수로 오버라이드 가능
# asyncpg 드라이버: postgresql+asyncpg://
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://pv_user:pv_password@localhost:5432/pv_profile",
)

# asyncpg 비동기 엔진
# pool_pre_ping: DB 장애 감지 후 재연결
engine = create_async_engine(
    DATABASE_URL,
    echo=False,           # SQL 쿼리 로깅 (개발 시 True로 변경)
    pool_size=10,          # 커넥션 풀 크기
    max_overflow=20,       # 풀 초과 허용 커넥션 수
    pool_pre_ping=True,    # 연결 유효성 사전 확인
    pool_recycle=3600,     # 1시간마다 커넥션 재생성
)

# 세션 팩토리
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # commit 후에도 객체 접근 가능
    autoflush=False,
    autocommit=False,
)


class Base(DeclarativeBase):
    """SQLAlchemy ORM 기반 클래스."""
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI 의존성 주입용 DB 세션 제너레이터.
    요청당 세션 생성 후 응답 완료 시 자동 닫기.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
