from sqlalchemy import create_engine, Column, Integer, String, DateTime, func, JSON, BigInteger, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from databases import Database
from app.config import settings

# MariaDB 연결 URL
DATABASE_URL = f"mysql+pymysql://{settings.DATABASE_USER}:{settings.DATABASE_PASSWORD}@{settings.DATABASE_HOST}:{settings.DATABASE_PORT}/{settings.DATABASE_NAME}"

# SQLAlchemy 엔진 생성
engine = create_engine(DATABASE_URL)

# ORM 베이스 클래스
Base = declarative_base()

# 비동기 데이터베이스 객체
db_database = Database(DATABASE_URL)

# 세션 메이커
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 데이터베이스 모델 정의
class Module_Schedulersettings(Base):
    __tablename__ = 'module_schedulersettings'

    id = Column(Integer, primary_key=True, unique=True, autoincrement=True)
    sequence_id = Column(BigInteger, nullable=False)
    channel_id = Column(BigInteger, nullable=True)
    module_name = Column(String(40), nullable=True)
    pre_func_name = Column(String(40), nullable=True)
    func_name = Column(String(40), nullable=True)
    type = Column(String(40), nullable=True)
    params = Column(JSON, nullable=True)  # JSON 타입
    setting = Column(JSON, nullable=True)  # JSON 타입
    listener = Column(String(40), nullable=True)
    is_active = Column(Boolean, nullable=False, default=False)
