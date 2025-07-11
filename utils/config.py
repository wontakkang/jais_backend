import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings
from typing import ClassVar

# 유틸리티 설정용 .env 파일 로드
load_dotenv(dotenv_path='D:\project\projects\jais\py_backend\.env')
class Settings(BaseSettings):
    APP_NAME: str
    APP_VERSION: str
    APP_DESCRIPTION: str
    DEBUG: bool
    LOG_DIR: str
    BASE_PATH: str
    DATABASE_HOST: str
    DATABASE_USER: str
    DATABASE_PASSWORD: str
    DATABASE_NAME: str
    DATABASE_PORT: int
    DATABASE_DATADUMP_PATH: str
    DATABASE_BACKUP_PATH: str
    
    DATABASE1_HOST: str
    DATABASE1_USER: str
    DATABASE1_PASSWORD: str
    DATABASE1_NAME: str
    DATABASE1_PORT: int
    DATABASE1_DATADUMP_PATH: str
    DATABASE1_BACKUP_PATH: str
    WORKERS: int = 1
    LAT: float
    LNG: float
    STANDARD_DATE: str
    TIMEZONE: str
    AWS_AD: str
    AWS_AS: str
    AWS_RH: str
    AWS_SR: str
    AWS_TEMP: str
    measurement_time: str
    low_variance_threshold: float
    DATA_GO_KR_TOKEN: str
    email: str
    imap: str
    NETWORK_RANGE: str
    removal_methods: str
    IARAW_FILTER: str
    TEMP_FILTER: str
    HUMIDITY_FILTER: str
    CO2_FILTER: str
    OUT_DOOR: str
    IN_DOOR: str
    
    
    # 환경변수 필터링을 위한 리스트 속성 초기화
    # 리스트 속성 초기화
    PWR_WM: dict = {}
    RNE_WM: dict = {}
    FEATURES: dict = {}
    AWS: dict = {}
    IARAW: dict = {}
    NETWORK: dict = {}
    FILTERED_KEYS: dict = {}
    removal_methods_list: list = []
    IARAW_FILTER_LIST: list = []
    TEMP_FILTER_LIST: list = []
    HUMIDITY_FILTER_LIST: list = []
    CO2_FILTER_LIST: list = []
    
    class Config:
        env_file = ".env"
        extra = "allow"  # 정의되지 않은 속성도 허용

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # ✅ 필터 목록을 .env에서 로드
        startswith_filters = [s.strip() for s in os.getenv("STARTSWITH_FILTER", "").split(",")]
        endswith_filters = [s.strip() for s in os.getenv("ENDSWITH_FILTER", "").split(",")]
        # removal_methods 리스트 환경변수 로드
        self.removal_methods_list = [s.strip() for s in self.removal_methods.split(",") if s.strip()]
        # removal_methods 리스트 환경변수 로드
        self.IARAW_FILTER_LIST = [s.strip() for s in self.IARAW_FILTER.split(",") if s.strip()]
        self.TEMP_FILTER_LIST = [s.strip() for s in self.TEMP_FILTER.split(",") if s.strip()]
        self.HUMIDITY_FILTER_LIST = [s.strip() for s in self.HUMIDITY_FILTER.split(",") if s.strip()]
        self.CO2_FILTER_LIST = [s.strip() for s in self.CO2_FILTER.split(",") if s.strip()]
        
        # os.environ에서 IARAW로 시작하는 모든 키를 탐색하여 추가
        for key, value in os.environ.items():
            if key.startswith("NET") and not key == "NETWORK_RANGE":
                setattr(self, key, value)
                self.NETWORK[key] = value
        for key, value in os.environ.items():
            if key.startswith("IARAW")and not key.endswith("FILTER"):
                for key2 in self.IARAW_FILTER_LIST:
                    setattr(self, f"{key}.{key2}", f"{value}.{key2}")
                    self.IARAW[f"{key}.{key2}"] = f"{value}.{key2}"
        # os.environ에서 AWS 시작하는 모든 키를 탐색하여 추가
        self.AWS['AWS_AD'] = os.getenv('AWS_AD')
        self.AWS['AWS_AS'] = os.getenv('AWS_AS')
        self.AWS['AWS_CO2'] = os.getenv('AWS_CO2')
        self.AWS['AWS_RH'] = os.getenv('AWS_RH')
        self.AWS['AWS_SR'] = os.getenv('AWS_SR')
        self.AWS['AWS_TEMP'] = os.getenv('AWS_TEMP')
        
 
        # ✅ 전체 환경변수 중 조건 일치하는 항목만 분류
        for key, value in os.environ.items():
            if any(key.startswith(prefix) for prefix in startswith_filters) and \
               any(key.endswith(suffix) for suffix in endswith_filters):
                setattr(self, key, value)  # 속성 등록
                self.FILTERED_KEYS[key] = value  # 전체 필터 결과

                if key.startswith("PWR"):
                    self.PWR_WM[key] = value
                elif key.startswith("RNE"):
                    self.RNE_WM[key] = value
                    
            # FEATURES 속성 초기화
            self.FEATURES.update(self.RNE_WM)
            self.FEATURES.update(self.AWS)
            self.FEATURES.update(self.IARAW)
            self.FEATURES.update(self.NETWORK)
        

# Settings 객체 생성 및 확인
settings = Settings()
