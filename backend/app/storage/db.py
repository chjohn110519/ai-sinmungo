from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from app.config import settings
from app.storage.models import Base

# 데이터베이스 엔진 생성
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {},
)

# 세션 팩토리 생성
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Session:
    """데이터베이스 세션 의존성 주입용 함수"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    """데이터베이스 테이블 생성"""
    Base.metadata.create_all(bind=engine)


def _run_migrations():
    """기존 테이블에 신규 컬럼 추가 (이미 존재하면 무시)."""
    migrations = [
        "ALTER TABLE structured_proposals ADD COLUMN win_theme TEXT",
        "ALTER TABLE structured_proposals ADD COLUMN discriminators TEXT",
        "ALTER TABLE structured_proposals ADD COLUMN executive_summary TEXT",
        "ALTER TABLE structured_proposals ADD COLUMN proof_points TEXT",
    ]
    with engine.connect() as conn:
        for sql in migrations:
            try:
                conn.execute(text(sql))
                conn.commit()
            except Exception:
                pass  # 컬럼이 이미 존재하면 무시


def init_db():
    """데이터베이스 초기화"""
    _run_migrations()
    create_tables()
    from app.storage.seed import seed_if_empty
    db = SessionLocal()
    try:
        seed_if_empty(db)
    finally:
        db.close()