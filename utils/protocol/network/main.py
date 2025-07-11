
from typing import List, Dict, Any
from datetime import datetime
import pandas as pd
from utils.DB.mariaDB import SQLBuilder
from utils.connection import *

# 네트워크 디바이스 유형별 시계열 데이터 SQL
def get_network_device_data(start: datetime, end: datetime) -> List[Dict[str, Any]]:
    measurement_time = 'READ_DATETIME'
    
    query = SQLBuilder("t_device_type_log", db1_instance).SELECT(columns=[measurement_time, 'COUNT', 'DEVICE_TYPE', 'POWER_TAG'],)
    query.filter(LOG_DATE__range=[start, end])
    query.order_by(measurement_time)
    read_data = query.execute()
    # Convert read_data to a DataFrame
    df = pd.DataFrame(read_data)
    # 1. 조합 컬럼 생성
    df["DEVICE_POWER"] = df["DEVICE_TYPE"] + "_" + df["POWER_TAG"]
    # 4. READ_DATETIME datetime 변환 + 인덱스 지정
    df["READ_DATETIME"] = pd.to_datetime(df["READ_DATETIME"])
    df.set_index("READ_DATETIME", inplace=True)
    df.sort_index(inplace=True)
    # 10. 최종 컬럼 정리 (READ_DATETIME, DEVICE_POWER, COUNT만)
    df = df[['DEVICE_POWER', 'COUNT']]
    # 3. 5분 단위로 floor (내림)
    df.index = df.index.floor('5min')
    # 5. 5분 간격 전체 인덱스 생성
    full_index = pd.date_range(
        start=df.index.min(),
        end=df.index.max(),
        freq='5min'
    )
            
    # 3. 피벗 (DEVICE_POWER를 컬럼으로)
    pivot_df = df.pivot_table(
        index='READ_DATETIME',
        columns='DEVICE_POWER',
        values='COUNT',
        aggfunc='sum',   # 같은 시간 중복되면 합산
        fill_value=0     # 결측치는 0
    )


    # 4. 5분 간격으로 reindex
    pivot_df = pivot_df.reindex(full_index)

    # 5. 각 컬럼별로 선형 보간
    pivot_df = pivot_df.interpolate(method='linear').round()

    # 6. 정리
    pivot_df.index.name = 'READ_DATETIME'
    pivot_df.reset_index(inplace=True)

    read_data = pivot_df.to_dict(orient="records")

    return read_data
