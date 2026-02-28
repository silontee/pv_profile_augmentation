"""
FastAPI 앱 진입점.
CORS, 라우터, DB 라이프사이클 관리.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.db.session import engine, Base
from app.api import facilities, stats, infra

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 시작/종료 시 DB 연결 관리."""
    logger.info("FastAPI 서버 시작 — DB 연결 확인 중...")
    # 테이블 생성은 load_data.py에서 수행하므로 여기서는 연결만 확인
    async with engine.begin() as conn:
        logger.info("DB 연결 성공")
    yield
    # 종료 시 커넥션 풀 정리
    await engine.dispose()
    logger.info("FastAPI 서버 종료 — DB 연결 정리 완료")


app = FastAPI(
    title="PV Profile API",
    description="태양광 발전소 전기사업허가 데이터 조회 API",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS 설정 — Vite dev server (5173) 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(facilities.router, prefix="/api")
app.include_router(stats.router, prefix="/api")
app.include_router(infra.router, prefix="/api")


@app.get("/health")
async def health_check():
    """헬스체크 엔드포인트."""
    return {"status": "ok"}


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """
    처리되지 않은 예외에 대한 전역 핸들러.
    DB 장애 등 예상치 못한 오류 시 503 반환.
    """
    logger.error(f"처리되지 않은 예외: {exc}", exc_info=True)
    return JSONResponse(
        status_code=503,
        content={"error": "서비스 일시 중단", "retry_after": 30},
    )
