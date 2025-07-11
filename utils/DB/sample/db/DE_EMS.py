from sqlalchemy import create_engine, Column, Integer, String, DateTime, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from databases import Database
from app.config import settings

# MariaDB 연결 URL
DATABASE_URL = f"mysql+pymysql://{settings.DATABASE1_USER}:{settings.DATABASE1_PASSWORD}@{settings.DATABASE1_HOST}:{settings.DATABASE1_PORT}/{settings.DATABASE1_NAME}"

# SQLAlchemy 엔진 생성
engine = create_engine(DATABASE_URL)

# ORM 베이스 클래스
Base = declarative_base()

# 비동기 데이터베이스 객체
EMS_database = Database(DATABASE_URL)

# 세션 메이커
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 데이터베이스 모델 정의
class T_STAT_PRED_HOUR(Base):
    __tablename__ = "t_stat_pred_hour"
    id = Column(Integer, primary_key=True, index=True, comment="번호")
    READ_DATETIME = Column(String(14), comment="년월일시분초")
    READ_MONTH = Column(String(6), comment="년월")
    READ_DATE = Column(String(8), comment="년월일")
    READ_TIME = Column(String(6), comment="시분초")
    ITEM = Column(String(255), index=True, comment="태그명")
    ITEM_KIND = Column(String(20), default="PRED", comment="측정형태-LOAD,CON,PRED")
    ITEM_GUBUN = Column(String(20), comment="측정구분-전기,가스,시수,기타")
    ITEM_DESC = Column(String(20), comment="태그설명")
    ITEM_VAL = Column(Integer, comment="사용량")
    # 자동으로 현재 시간을 저장하도록 수정
    INS_TIME = Column(DateTime, server_default=func.now(), index=True, comment="등록시간")

# 데이터베이스 초기화 (테이블 생성)
# Base.metadata.create_all(bind=engine)  # 새로 생성