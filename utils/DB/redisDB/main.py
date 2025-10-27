from datetime import datetime, timedelta
import numpy as np
import pandas as pd
import redis, json, time
from tzlocal import get_localzone  # 시스템 로컬 타임존 자동 감지
import json
# aioredis 호환 임포트 (없으면 redis.asyncio 사용)
try:
    import aioredis  # type: ignore
    from aioredis import RedisError as RedisError  # type: ignore
except Exception:  # pragma: no cover
    from redis import asyncio as aioredis  # type: ignore
    from redis.exceptions import RedisError  # type: ignore
# 시스템의 로컬 타임존 가져오기
local_tz = get_localzone()

class RedisManager:
    """
    Redis 기본 데이터, 해시 데이터, 시계열 데이터 및 백업을 통합 관리하는 컨텍스트
    """
    def __init__(self, host='localhost', port=6379, db=0, max_connections=20, password=None):
        """
        Redis 연결 초기화 (비밀번호 인증 포함)
        
        :param host: Redis 서버 호스트
        :param port: Redis 서버 포트
        :param db: Redis 데이터베이스 번호
        :param max_connections: 최대 연결 수
        :param password: Redis 비밀번호 (없으면 None)
        """
        self.host = host
        self.port = port
        self.db = db
        self.max_connections = max_connections
        self.password = password        
        self.lua_script = None

    def connect(self):
        """
        Redis 서버에 연결 (재연결 포함)
        """
        try:
            pool = redis.ConnectionPool(
                host=self.host, port=self.port, db=self.db,
                decode_responses=True, max_connections=self.max_connections,
                socket_timeout=10,  # 10초 후 타임아웃
                socket_connect_timeout=10,  # 연결 타임아웃 10초
                retry_on_timeout=True,  # 타임아웃 시 재시도
            )
            self.client = redis.Redis(connection_pool=pool)
            if self.password:
                self.client.config_set("requirepass", self.password)

        except redis.AuthenticationError:
            pool = redis.ConnectionPool(
                host=self.host, port=self.port, db=self.db,
                password=self.password, decode_responses=True,
                max_connections=self.max_connections,
                socket_timeout=10,  # 10초 후 타임아웃
                socket_connect_timeout=10,  # 연결 타임아웃 10초
                retry_on_timeout=True,  # 타임아웃 시 재시도
            )
            self.client = redis.Redis(connection_pool=pool)

    def is_connected(self):
        """연결 상태 확인 (ping 테스트)"""
        try:
            return self.client.ping() if self.client else False
        except redis.ConnectionError:
            return False
        
    # ------------------------------
    # 📌 일반 데이터 저장 및 조회
    # ------------------------------

    def set_value(self, key, value, expire=None):
        """일반 데이터 저장"""
        value = json.dumps(value)
        self.client.set(key, value, ex=expire)

    def get_value(self, key):
        """일반 데이터 조회"""
        value = self.client.get(key)
        return json.loads(value) if value else None

    def delete_value(self, key):
        """특정 키 삭제"""
        self.client.delete(key)

    def exists(self, key):
        """키 존재 여부 확인"""
        return self.client.exists(key) > 0

    def flush(self):
        """모든 데이터 삭제"""
        self.client.flushdb()

    def get_all_keys(self):
        """모든 키 목록 조회"""
        return self.client.keys('*')

    def mget(self, keys, as_dict=True):
        """여러 키를 한 번에 조회(MGET)하여 JSON 디코딩해 반환
        :param keys: 조회할 키 리스트 또는 단일 키
        :param as_dict: True면 {key: value} dict, False면 값 리스트 반환
        """
        if isinstance(keys, (str, bytes)):
            keys = [keys]
        values = self.client.mget(keys)
        decoded = []
        for v in values:
            try:
                decoded.append(json.loads(v) if v else None)
            except Exception:
                decoded.append(v)
        return {k: v for k, v in zip(keys, decoded)} if as_dict else decoded

    # ------------------------------
    # 📌 Bulk 데이터 처리 (bulk_create, bulk_update)
    # ------------------------------

    def bulk_set(self, data, expire=None):
        """
        여러 개의 키-값 데이터를 한 번에 저장 (bulk_create 역할)
        :param data: {key1: value1, key2: value2, ...} 형태의 딕셔너리
        :param expire: 만료 시간 (초) (선택 사항)
        
        📌 사용 예시:
        redis_manager.bulk_set({
            "user:1001": {"name": "Alice", "age": 30},
            "user:1002": {"name": "Bob", "age": 25}
        })
        """
        pipeline = self.client.pipeline()
        for key, value in data.items():
            pipeline.set(key, json.dumps(value), ex=expire)
        pipeline.execute()

    def bulk_update(self, data, expire=None):
        """
        여러 개의 키-값 데이터를 한 번에 업데이트 (bulk_update 역할)
        :param data: {key1: value1, key2: value2, ...} 형태의 딕셔너리
        :param expire: 만료 시간 (초) (선택 사항)

        📌 사용 예시:
        redis_manager.bulk_update({
            "user:1001": {"age": 31},  # 기존 키 업데이트
            "user:1002": {"city": "Seoul"}  # 새로운 필드 추가
        })
        """
        pipeline = self.client.pipeline()
        for key, new_value in data.items():
            existing_value = self.client.get(key)
            if existing_value:
                updated_value = json.loads(existing_value)
                if isinstance(updated_value, dict) and isinstance(new_value, dict):
                    updated_value.update(new_value)
                else:
                    updated_value = new_value
            else:
                updated_value = new_value
            pipeline.set(key, json.dumps(updated_value), ex=expire)
        pipeline.execute()

    # ------------------------------
    # 📌 해시 데이터 Bulk 저장 및 업데이트 (동기)
    # ------------------------------

    def hbulk_set(self, name, data):
        """
        여러 개의 해시 데이터를 한 번에 저장 (bulk_create 역할)
        :param name: Redis 해시 키 이름
        :param data: {field1: value1, field2: value2, ...} 형태의 딕셔너리
        
        📌 사용 예시:
        redis_manager.hbulk_set("user:1001", {
            "email": "alice@example.com",
            "phone": "123-456-7890"
        })
        """
        pipeline = self.client.pipeline()
        for field, value in data.items():
            pipeline.hset(name, field, json.dumps(value))
        pipeline.execute()

    def hbulk_update(self, name, data):
        """
        여러 개의 해시 데이터를 한 번에 업데이트 (bulk_update 역할)
        :param name: Redis 해시 키 이름
        :param data: {field1: value1, field2: value2, ...} 형태의 딕셔너리
        
        📌 사용 예시:
        redis_manager.hbulk_update("user:1001", {
            "phone": "987-654-3210",  # 기존 필드 업데이트
            "address": "New York"  # 새로운 필드 추가
        })
        """
        pipeline = self.client.pipeline()
        for field, new_value in data.items():
            existing_value = self.client.hget(name, field)
            if existing_value:
                updated_value = json.loads(existing_value)
                if isinstance(updated_value, dict) and isinstance(new_value, dict):
                    updated_value.update(new_value)
                else:
                    updated_value = new_value
            else:
                updated_value = new_value
            pipeline.hset(name, field, json.dumps(updated_value))
        pipeline.execute()
    # ------------------------------
    # 📌 해시 데이터 저장 및 조회
    # ------------------------------

    def hset(self, name, key, value):
        """해시 데이터 저장"""
        value = json.dumps(value)
        self.client.hset(name, key, value)

    def hget(self, name, key):
        """해시 데이터 조회"""
        value = self.client.hget(name, key)
        return json.loads(value) if value else None

    def hmset(self, name, mapping):
        """해시 데이터 여러 개 저장"""
        # 모든 값을 JSON 형식으로 변환
        mapping = {key: json.dumps(value) for key, value in mapping.items()}
        self.client.hmset(name, mapping)
        
    def hmget(self, name, keys):
        """해시 데이터 여러 개 조회"""
        values = self.client.hmget(name, keys)
        
        # JSON 디코딩 (값이 존재할 경우)
        return {key: json.loads(value) if value else None for key, value in zip(keys, values)}
    
    def hexists(self, name, key):
        """키 존재 여부 확인"""
        return self.client.hexists(name, key) > 0

    def hcreate_or_update(self, name, data):
        """해시 데이터 업데이트 또는 생성"""
        for key, value in data.items():
            existing_value = self.client.hget(name, key)

            if existing_value:
                updated_value = json.loads(existing_value)
                if isinstance(updated_value, dict) and isinstance(value, dict):
                    updated_value.update(value)
                else:
                    updated_value = value
            else:
                updated_value = value

            self.client.hset(name, key, json.dumps(updated_value))

    # ------------------------------
    # 📌 일반 키 업데이트 (없으면 생성)
    # ------------------------------

    def create_or_update(self, key, value, expire=None):
        """일반 키 데이터 업데이트 또는 생성"""
        existing_value = self.client.get(key)

        if existing_value:
            updated_value = json.loads(existing_value)
            updated_value.update(value)
        else:
            updated_value = value

        updated_value = json.dumps(updated_value)
        self.client.set(key, updated_value, ex=expire)

    # ------------------------------
    # 📌 시계열 데이터 관리 기능 (TimeSeries)
    # ------------------------------

    def create_timeseries(self, key, retention=0, labels=None):
        """
        시계열 데이터베이스 생성 (한 번에 라벨 추가)
        
        사용 예시:
        tsdb.create_timeseries("sensor:1", retention=60000, labels={"location": "kitchen", "type": "temperature"})
        """
        if labels is None:
            labels = {}

        
        # 1️⃣ 키가 이미 존재하는지 확인
        exists = self.client.exists(key)

        if exists:
            # 2️⃣ 이미 존재하면 TS.ALTER 사용하여 설정 업데이트
            label_args = []
            for label, value in labels.items():
                label_args.extend([label, value])

            self.client.execute_command('TS.ALTER', key, 'DUPLICATE_POLICY', 'LAST', 'RETENTION', retention, 'LABELS', *label_args)
        else:
            # 3️⃣ 존재하지 않으면 새롭게 생성
            label_args = []
            for label, value in labels.items():
                label_args.extend([label, value])
            self.client.execute_command('TS.CREATE', key, 'DUPLICATE_POLICY', 'FIRST', 'RETENTION', retention, 'LABELS', *label_args)

    def add_timeseries_data(self, key, value, timestamp=None):
        """
        시계열 데이터 추가
        :param callback ['get_labels_callback']
        
        사용 예시:
        tsdb.add_timeseries_data("sensor:1", 22.5)
        """
        if timestamp is None:
            timestamp = int(time.time() * 1000)
        self.client.execute_command('TS.ADD', key, timestamp, value)

    def get_timeseries_range(self, key_pattern, start='-', end='+', count=None, callback=None):
        """
        특정 기간의 시계열 데이터 조회 (와일드카드 지원) + COUNT 옵션 추가 
        :param key_pattern: 검색할 키 패턴 (예: "alert:*")
        :param start: 조회 시작 시간 ('-'는 가장 오래된 데이터)
        :param end: 조회 종료 시간 ('+'는 최신 데이터)
        :param count: 조회할 데이터 개수 제한 (Optional)
        :param callback: 후처리 콜백 함수 (Optional)['get_labels_callback']
        사용 예시:
        tsdb.get_timeseries_range("alert:*", start=1672531200000, end=1672617600000, count=100)
        """
        try:
            keys = []
            
            # 와일드카드 포함 여부 확인
            if '*' in key_pattern:
                # SCAN 명령어를 사용하여 일치하는 키 찾기
                cursor = 0
                while True:
                    cursor, found_keys = self.client.scan(cursor, match=key_pattern, count=100)
                    keys.extend(found_keys)
                    if cursor == 0:
                        break
            else:
                keys.append(key_pattern)  # 단일 키 조회

            if not keys:
                return {"error": "No matching TimeSeries keys found."}

            # Redis Pipeline 사용
            pipeline = self.client.pipeline()
            for key in keys:
                if count:
                    pipeline.execute_command("TS.RANGE", key, start, end, "COUNT", count)
                else:
                    pipeline.execute_command("TS.RANGE", key, start, end)
            
            # 결과 실행
            results = pipeline.execute()
            # 데이터 정리
            data = {
                key: [{"timestamp": ts, "value": value} for ts, value in result]
                for key, result in zip(keys, results)
            }
            # 콜백이 제공된 경우 실행
            if callback:
                return callback(data, [key])
            else:
                return data

        except redis.exceptions.RedisError as e:
            return {"error": f"Redis error: {str(e)}"}
        
    def get_labels_callback(self, result, keys):
        """
        클래스 내부의 콜백 함수 (데이터를 추가적으로 처리할 수 있음)
        """
        try:
            if not keys:
                return result

            # Redis Pipeline 사용
            pipeline = self.client.pipeline()
            for key in keys:
                pipeline.execute_command("TS.INFO", key)
            
            info_results = pipeline.execute()

            # 라벨 데이터 정리
            labels_dict = {}
            for key, info in zip(keys, info_results):
                try:
                    # info 리스트에서 'labels' 키 찾기
                    label_index = info.index("labels") if "labels" in info else -1
                    if label_index != -1 and label_index + 1 < len(info):
                        raw_labels = info[label_index + 1]  # 라벨 리스트
                        if isinstance(raw_labels, list):
                            # 리스트 내 리스트 구조를 {key: value} 형태로 변환
                            labels_dict[key] = {str(entry[0]): str(entry[1]) for entry in raw_labels if isinstance(entry, list) and len(entry) == 2}
                        else:
                            labels_dict[key] = {}
                    else:
                        labels_dict[key] = {}

                except ValueError:
                    labels_dict[key] = {}  # 예외 발생 시 빈 라벨 저장

            return result, labels_dict  # 라벨 정보 포함하여 반환

        except redis.exceptions.RedisError as e:
            return result

    def timeseries_exists(self, key):
        """
        Redis Time Series 데이터가 존재하는지 확인하는 함수

        사용 예시:
        exists = tsdb.timeseries_exists("sensor:1")
        print(exists)  # True 또는 False 반환
        """
        try:
            # TS.INFO를 사용하여 키의 존재 여부 확인
            totalSamples = self.client.execute_command('TS.INFO', key)
            if totalSamples[1] > 0:
                return True  # 데이터가 존재하면 True 반환
            else:
                return False  # 존재하지 않으면 False 반환
        except Exception as e:
            if "TSDB: the key does not exist" in str(e):
                return False  # 존재하지 않으면 False 반환
            else:
                raise  # 기타 오류는 그대로 발생


    def get_latest_timeseries(self, key, callback=None):
        """
        최신 시계열 데이터 조회 + 라벨 정보 포함 (옵션)
        :param callback ['get_labels_callback']
        
        사용 예시:
        latest = tsdb.get_latest_timeseries("sensor:1")
        print(latest)
        """
        try:
            # 최신 데이터 조회
            result = self.client.execute_command('TS.GET', key)
            if not result:
                return ModuleNotFoundError
            # 콜백이 제공된 경우 실행
            if callback:
                return callback(result, [key])
            else:
                return result

        except redis.exceptions.RedisError as e:
            return {"error": f"Redis error: {str(e)}"}

    def get_pattern_latest_timeseries(self, key_pattern, callback=None):
        """
        와일드카드 패턴을 사용하여 여러 시계열 키의 최신 데이터 조회
        :param callback ['get_labels_callback']

        사용 예시:
        latest = tsdb.get_pattern_latest_timeseries("sensor:*")
        print(latest)
        """
        try:
            # 패턴에 '*'가 없으면 예외 처리
            if '*' not in key_pattern:
                return {"error": "This function only supports wildcard patterns. Use get_latest_timeseries for single keys."}

            keys = []
            cursor = 0

            # SCAN을 사용하여 패턴에 맞는 키 검색
            while True:
                cursor, found_keys = self.client.scan(cursor, match=key_pattern, count=100)
                keys.extend(found_keys)
                if cursor == 0:
                    break

            if not keys:
                return {"error": "No matching TimeSeries keys found."}

            # Redis Pipeline 사용
            pipeline = self.client.pipeline()
            for key in keys:
                pipeline.execute_command("TS.GET", key)
            
            # 결과 실행
            results = pipeline.execute()

            # 데이터 정리
            data = {
                key: {"timestamp": result[0], "value": result[1]} if result else None
                for key, result in zip(keys, results)
            }

            # 콜백이 제공된 경우 실행
            if callback:
                return callback(data, keys)
            else:
                return data

        except redis.exceptions.RedisError as e:
            return {"error": f"Redis error: {str(e)}"}

    def delete_timeseries(self, key):
        """
        시계열 키 삭제
        
        사용 예시:
        tsdb.delete_timeseries("sensor:1")
        """
        self.client.delete(key)

    def query_scan(self, pattern):
        """
        Redis의 모든 키를 조회 (SCAN 사용)
        :param client: Redis 클라이언트
        :return: 모든 키 리스트
        """
        cursor = 0
        matched_keys = []

        # 1️⃣ SCAN을 이용해 반복 검색
        while True:
            cursor, keys = self.client.execute_command("SCAN", cursor, "MATCH", pattern, "COUNT", 100)
            
            # 2️⃣ keys가 존재할 때만 추가
            if keys and len(keys) > 0:
                matched_keys.extend(keys)

            # 3️⃣ 커서가 0이면 종료
            if cursor == 0:
                break

        return matched_keys
    
    def query_keys(self, pattern):
        """
        패턴을 기반으로 특정 키만 조회
        :param pattern: ["*", "9", "Sensor", "*", "*"] 같은 리스트 형식
        """
        # 1️⃣ 모든 키 가져오기
        keys = self.client.keys('*')

        # 2️⃣ "*"을 제외한 필터링할 값만 추출
        filters = [p for p in pattern if p != "*"]

        # 3️⃣ 필터링 적용 (모든 키에서 필터링할 값이 있는지 확인)
        result_keys = []
        for key in keys:
            if all(f in key for f in filters):
                result_keys.append(key)

        return result_keys
    
    def query_by_label(self, label_filter):
        """
        라벨을 기반으로 해당하는 모든 시계열 키 조회
        
        사용 예시:
        keys = tsdb.query_by_label("location=kitchen")
        print(keys)  # ['sensor:1', 'sensor:3']
        """
        return self.client.execute_command('TS.QUERYINDEX', label_filter)

    def get_data_by_label(self, label_filter, start='-', end='+'):
        """
        라벨을 기반으로 여러 시계열 데이터 조회
        
        사용 예시:
        data = tsdb.get_data_by_label("location=kitchen")
        print(data)
        """
        return self.client.execute_command('TS.MRANGE', start, end, 'FILTER', label_filter)
    

    def custom_aggregate(self, source_keys, query_key='*', aggregate_type=['MIN', 'MAX', 'AVG'], batch_size=10, minute=5, delay=0):
        """
        source_keys: 집계할 데이터 키 리스트
        aggregate_type: 적용할 집계 연산 리스트
        batch_size: Pipeline을 통해 한 번에 처리할 키 개수
        delay: 스케줄러 동작 지연시간 
        ["MIN", "MAX", "AVG", "SUM", "COUNT", "FIRST", "LAST", "STDDEV",
        "VARIANCE", "RANGE", "DIFFERENCE", "DERIVATIVE", "NONNEGATIVE_DERIVATIVE",
        "HISTOGRAM", "SPREAD", "MEDIAN", "SKEW", "CHANGE_TIME", "RUN_TIME", "DOWN_TIME", "UP_PULSE_TIME", "DOWN_PULSE_TIME"]
        - MIN: 최소값 계산
        - MAX: 최대값 계산
        - AVG: 평균값 계산
        - SUM: 합계 계산
        - COUNT: 데이터 개수 계산
        - FIRST: 첫 번째 값
        - LAST: 마지막 값
        - STDDEV: 표준편차 계산
        - VARIANCE: 분산 계산
        - RANGE: 값의 범위 (최대 - 최소)
        - DIFFERENCE: 각 값 간 차이 계산
        - DIFFERENCE_SUM: 총 변화량 계산
        - DERIVATIVE: 변화율 계산
        - NONNEGATIVE_DERIVATIVE: 음수가 없는 변화율 계산
        - HISTOGRAM: 히스토그램 (빈도수 분포)
        - SPREAD: 데이터의 최대값과 최소값 차이
        - MEDIAN: 중앙값 계산
        - SKEW: 데이터의 왜도 계산
        - CHANGE_TIME: 마지막으로 값이 변한 시점
        - RUN_TIME: 값이 0이 아닌 시간의 총합 (단위: 초)
        - DOWN_TIME: 값이 0인 시간의 총합 (단위: 초)
        - UP_PULSE_TIME: 값이 0에서 1 이상으로 변한 시점
        - DOWN_PULSE_TIME: 값이 1 이상에서 0으로 변한 시점
        """
        results = {}
        ndigit = 4
        end_time = int(datetime.now().timestamp() * 1000) - delay * 1000 
        start_time = end_time - (minute * 60 * 1000)  # 최근 5분 데이터  
        total_time = (end_time - start_time) / 1000  # 총 시간(초)
        
        for i in range(0, len(source_keys), batch_size):
            batch_keys = [key for key in source_keys[i:i + batch_size] if query_key in key or query_key == '*']
            
            with self.client.pipeline() as pipe:
                for source_key in batch_keys:
                    pipe.execute_command('TS.RANGE', source_key, start_time, end_time)
                responses = pipe.execute()
                
            for source_key, data in zip(batch_keys, responses):
                if not data:
                    results[source_key] = {agg: None for agg in aggregate_type}
                    continue

                df = pd.DataFrame(data, columns=['timestamp', 'value'])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                df.set_index('timestamp', inplace=True)
                
                # 값이 문자열로 반환될 경우 숫자로 변환
                df['value'] = pd.to_numeric(df['value'], errors='coerce')
                df.dropna(subset=['value'], inplace=True)  # 변환되지 않은 값 제거
                
                if df.empty:
                    results[source_key] = {agg: None for agg in aggregate_type}
                    continue
                
                # 데이터 타입 확인
                dtype = df['value'].dtype

                # int, float, bool 이외의 경우 (예: 문자열) 예외 처리
                if not np.issubdtype(dtype, np.number):
                    raise ValueError("value 컬럼이 숫자형이 아닙니다.")
                
                agg_results = {}
                for agg in aggregate_type:
                    if agg == 'AVG':  # 평균값 계산
                        agg_results['AVG'] = round(float(df['value'].mean()), ndigit) if np.issubdtype(dtype, np.floating) else int(df['value'].mean())
                    elif agg == 'SUM':  # 합계 계산
                        agg_results['SUM'] = round(float(df['value'].sum()), ndigit) if np.issubdtype(dtype, np.floating) else int(df['value'].sum())
                    elif agg == 'MIN':  # 최소값 계산
                        agg_results['MIN'] = round(float(df['value'].min()), ndigit) if np.issubdtype(dtype, np.floating) else int(df['value'].min())
                    elif agg == 'MAX':  # 최대값 계산
                        agg_results['MAX'] = round(float(df['value'].max()), ndigit) if np.issubdtype(dtype, np.floating) else int(df['value'].max())
                    elif agg == 'COUNT':  # 데이터 개수 계산
                        agg_results['COUNT'] = df['value'].count()
                    elif agg == 'FIRST':  # 첫 번째 값
                        agg_results['FIRST'] = round(float(df['value'].iloc[0]), ndigit) if np.issubdtype(dtype, np.floating) else int(df['value'].iloc[0])
                    elif agg == 'LAST':  # 마지막 값
                        agg_results['LAST'] = round(float(df['value'].iloc[-1]), ndigit) if np.issubdtype(dtype, np.floating) else int(df['value'].iloc[-1])
                    elif agg == 'STDDEV':
                        agg_results['STDDEV'] = round(float(df['value'].std()), ndigit)  # 🔹 float 변환
                    elif agg == 'VARIANCE':
                        agg_results['VARIANCE'] = round(float(df['value'].var()), ndigit)  # 🔹 float 변환
                    elif agg == 'RANGE':
                        agg_results['RANGE'] = round(float(df['value'].max() - df['value'].min()), ndigit) if np.issubdtype(dtype, np.floating) else int(df['value'].max() - df['value'].min())
                    elif agg == 'DIFFERENCE':
                        agg_results['DIFFERENCE'] = [round(float(x), ndigit) for x in df['value'].diff().dropna().tolist()]  # 🔹 리스트 내 값 float 변환
                    elif agg == 'DIFFERENCE_SUM':
                        diff_sum = df['value'].diff().dropna().sum()
                        agg_results['DIFFERENCE_SUM'] = round(diff_sum, ndigit) if diff_sum is not None else 0  # 🔹 float 변환
                    elif agg == 'DERIVATIVE':
                        diff_mean = df['value'].diff().dropna().mean()
                        # NaN이 나오지 않도록 체크 후 변환
                        agg_results['DERIVATIVE'] = round(float(diff_mean), ndigit) if not np.isnan(diff_mean) else 0
                    elif agg == 'NONNEGATIVE_DERIVATIVE':
                        agg_results['NONNEGATIVE_DERIVATIVE'] = round(float(df['value'].diff().clip(lower=0).dropna().mean()), ndigit)  # 🔹 float 변환
                    elif agg == 'HISTOGRAM':
                        agg_results['HISTOGRAM'] = {k: int(v) for k, v in df['value'].value_counts().to_dict().items()}  # 🔹 int 변환
                    elif agg == 'SPREAD':
                        agg_results['SPREAD'] = round(float(df['value'].max() - df['value'].min()), ndigit)  # 🔹 float 변환
                    elif agg == 'MEDIAN':
                        agg_results['MEDIAN'] = round(float(df['value'].median()), ndigit)  # 🔹 float 변환
                    elif agg == 'SKEW':
                        agg_results['SKEW'] = round(float(df['value'].skew()), ndigit)  # 🔹 float 변환
                    elif agg == 'CHANGE_TIME':  # 마지막으로 값이 변한 시점
                        last_change = df[df['value'] != df['value'].shift()].index[-1]
                        # UTC 타임존 지정 후, 로컬 타임존 변환
                        last_change = last_change.tz_localize('UTC').tz_convert(local_tz)
                        agg_results['CHANGE_TIME'] = last_change
                    elif agg == 'RUN_TIME':  # 값이 0이 아닌 시간의 총합
                        run_time_series = df[df['value'] > 0].index.to_series().diff().dropna().dt.total_seconds()
                        run_time = run_time_series.sum() if not run_time_series.empty else 0
                        agg_results['RUN_TIME'] = run_time
                    elif agg == 'DOWN_TIME':  # 값이 0인 시간의 총합
                        down_time = total_time - agg_results.get('RUN_TIME', 0)
                        agg_results['DOWN_TIME'] = down_time
                    elif agg == 'UP_PULSE_TIME':
                        up_time = df[df['value'].diff() > 0].index.max()
                        agg_results['UP_PULSE_TIME'] = up_time if not pd.isnull(up_time) else None
                    elif agg == 'DOWN_PULSE_TIME':
                        down_time = df[df['value'].diff() < 0].index.max()
                        agg_results['DOWN_PULSE_TIME'] = down_time if not pd.isnull(down_time) else None
                    else:
                        raise ValueError(f"Unsupported aggregation type: {agg}")
                results[source_key] = agg_results
        
        return results, (datetime.now() - timedelta(seconds=delay)).strftime('%Y-%m-%dT%H:%M:%S')


    # ------------------------------
    # 📌 백업 및 복원 기능
    # ------------------------------

    def backup_data(self, file_path='redis_backup.json'):
        """Redis 데이터를 JSON 파일로 백업"""
        data = {key: self.get_value(key) for key in self.get_all_keys()}
        with open(file_path, 'w', encoding='utf-8') as file:
            json.dump(data, file, ensure_ascii=False, indent=4)

    def restore_data(self, file_path='redis_backup.json'):
        """JSON 백업 파일을 Redis로 복원"""
        with open(file_path, 'r', encoding='utf-8') as file:
            data = json.load(file)
            for key, value in data.items():
                self.set_value(key, value)

    # ------------------------------
    # 📌 시계열 데이터 Bulk 저장 및 업데이트
    # ------------------------------

    def bulk_add_timeseries(self, data):
        """
        여러 개의 시계열 데이터를 한 번에 추가 (bulk_create 역할)
        :param data: {
            "key1": [(timestamp1, value1), (timestamp2, value2), ...],
            "key2": [(timestamp1, value1), (timestamp2, value2), ...],
        }
        
        📌 사용 예시:
        redis_manager.bulk_add_timeseries({
            "sensor:1": [(1672531200000, 25.5), (1672531300000, 26.1)],
            "sensor:2": [(1672531200000, 30.2), (1672531300000, 29.8)]
        })
        """
        pipeline = self.client.pipeline()
        for key, values in data.items():
            for timestamp, value in values:
                pipeline.execute_command("TS.ADD", key, timestamp, value)
        pipeline.execute()

    def bulk_update_timeseries(self, data):
        """
        여러 개의 시계열 데이터를 한 번에 업데이트 (bulk_update 역할)
        기존 값이 있으면 업데이트, 없으면 추가
        :param data: {
            "key1": [(timestamp1, new_value1), (timestamp2, new_value2), ...],
            "key2": [(timestamp1, new_value1), (timestamp2, new_value2), ...],
        }

        📌 사용 예시:
        redis_manager.bulk_update_timeseries({
            "sensor:1": [(1672531200000, 26.0), (1672531300000, 27.0)],
            "sensor:2": [(1672531200000, 31.0), (1672531300000, 30.5)]
        })
        """
        pipeline = self.client.pipeline()
        for key, values in data.items():
            for timestamp, new_value in values:
                existing_data = self.client.execute_command("TS.RANGE", key, timestamp, timestamp)
                
                if existing_data:
                    # 값이 이미 존재하면 업데이트 (삭제 후 재추가)
                    self.client.execute_command("TS.DEL", key, timestamp, timestamp)
                
                # 새로운 값 추가
                pipeline.execute_command("TS.ADD", key, timestamp, new_value)
        pipeline.execute()


class AsyncRedisManager:
    """
    Redis 기본 데이터, 해시 데이터, 시계열 데이터 및 백업을 통합 관리하는 비동기 컨텍스트

    async def main():
    redis_manager = AsyncRedisManager()
    await redis_manager.connect()

    # 데이터 저장
    await redis_manager.set_value("test_key", {"name": "Alice", "age": 30})
    result = await redis_manager.get_value("test_key")
    print("조회 결과:", result)  # {"name": "Alice", "age": 30}

    # 시계열 데이터 저장
    await redis_manager.create_timeseries("sensor:1", retention=60000, labels={"location": "kitchen"})
    await redis_manager.add_timeseries_data("sensor:1", 22.5)

    # 실행
    asyncio.run(main())
    """

    def __init__(self, host='localhost', port=6379, db=0, max_connections=20, password=None):
        """
        Redis 연결 초기화 (비밀번호 인증 포함)
        """
        self.host = host
        self.port = port
        self.db = db
        self.max_connections = max_connections
        self.password = password
        self.client = None  # 비동기 Redis 클라이언트

    async def connect(self):
        """ Redis 서버에 비동기 연결 """
        try:
            self.client = await aioredis.from_url(
                f"redis://{self.host}:{self.port}/{self.db}",
                password=self.password,
                decode_responses=True,
                max_connections=self.max_connections,
                socket_timeout=10,  # 10초 후 타임아웃
                socket_connect_timeout=10,  # 연결 타임아웃 10초
            )
        except Exception as e:
            print(f"Redis 연결 오류: {e}")

    async def is_connected(self):
        """연결 상태 확인 (ping 테스트)"""
        try:
            return await self.client.ping() if self.client else False
        except Exception:
            return False

    # ------------------------------
    # 📌 일반 데이터 저장 및 조회 (비동기)
    # ------------------------------

    async def set_value(self, key, value, expire=None):
        """일반 데이터 저장"""
        if self.client is None:
            await self.connect()
        value = json.dumps(value)
        await self.client.set(key, value, ex=expire)

    async def get_value(self, key):
        """일반 데이터 조회"""
        if self.client is None:
            await self.connect()
        value = await self.client.get(key)
        return json.loads(value) if value else None

    async def delete_value(self, key):
        """특정 키 삭제"""
        if self.client is None:
            await self.connect()
        await self.client.delete(key)

    async def exists(self, key):
        """키 존재 여부 확인"""
        if self.client is None:
            await self.connect()
        return await self.client.exists(key) > 0

    async def flush(self):
        """모든 데이터 삭제"""
        if self.client is None:
            await self.connect()
        await self.client.flushdb()

    async def get_all_keys(self):
        """모든 키 목록 조회"""
        if self.client is None:
            await self.connect()
        return await self.client.keys('*')

    async def mget(self, keys, as_dict=True):
        """여러 키를 한 번에 조회(MGET)하여 JSON 디코딩해 반환 (비동기)
        :param keys: 조회할 키 리스트 또는 단일 키
        :param as_dict: True면 {key: value} dict, False면 값 리스트 반환
        """
        if self.client is None:
            await self.connect()
        if isinstance(keys, (str, bytes)):
            keys = [keys]
        values = await self.client.mget(keys)
        decoded = []
        for v in values:
            try:
                decoded.append(json.loads(v) if v else None)
            except Exception:
                decoded.append(v)
        return {k: v for k, v in zip(keys, decoded)} if as_dict else decoded

    # ------------------------------
    # 📌 Bulk 데이터 처리 (비동기)
    # ------------------------------

    async def bulk_set(self, data, expire=None):
        """ 여러 개의 키-값 데이터를 한 번에 저장 """
        if self.client is None:
            await self.connect()
        async with self.client.pipeline() as pipe:
            for key, value in data.items():
                await pipe.set(key, json.dumps(value), ex=expire)
            await pipe.execute()

    async def bulk_update(self, data, expire=None):
        """ 여러 개의 키-값 데이터를 한 번에 업데이트 """
        if self.client is None:
            await self.connect()
        async with self.client.pipeline() as pipe:
            for key, new_value in data.items():
                existing_value = await self.client.get(key)
                if existing_value:
                    updated_value = json.loads(existing_value)
                    if isinstance(updated_value, dict) and isinstance(new_value, dict):
                        updated_value.update(new_value)
                    else:
                        updated_value = new_value
                else:
                    updated_value = new_value
                await pipe.set(key, json.dumps(updated_value), ex=expire)
            await pipe.execute()

    # ------------------------------
    # 📌 해시 데이터 Bulk 저장 및 업데이트 (비동기)
    # ------------------------------

    async def hbulk_set(self, name, data):
        """ 여러 개의 해시 데이터를 한 번에 저장 """
        if self.client is None:
            await self.connect()
        async with self.client.pipeline() as pipe:
            for field, value in data.items():
                await pipe.hset(name, field, json.dumps(value))
            await pipe.execute()

    async def hbulk_update(self, name, data):
        """ 여러 개의 해시 데이터를 한 번에 업데이트 """
        if self.client is None:
            await self.connect()
        async with self.client.pipeline() as pipe:
            for field, new_value in data.items():
                existing_value = await self.client.hget(name, field)
                if existing_value:
                    updated_value = json.loads(existing_value)
                    if isinstance(updated_value, dict) and isinstance(new_value, dict):
                        updated_value.update(new_value)
                    else:
                        updated_value = new_value
                else:
                    updated_value = new_value
                await pipe.hset(name, field, json.dumps(updated_value))
            await pipe.execute()

    # ------------------------------
    # 📌 해시 데이터 저장 및 조회 (비동기)
    # ------------------------------

    async def hset(self, name, key, value):
        """해시 데이터 저장"""
        if self.client is None:
            await self.connect()
        value = json.dumps(value)
        await self.client.hset(name, key, value)

    async def hget(self, name, key):
        """해시 데이터 조회"""
        if self.client is None:
            await self.connect()
        value = await self.client.hget(name, key)
        return json.loads(value) if value else None

    async def hmset(self, name, mapping):
        """해시 데이터 여러 개 저장"""
        if self.client is None:
            await self.connect()
        mapping = {key: json.dumps(value) for key, value in mapping.items()}
        await self.client.hset(name, mapping=mapping)

    async def hmget(self, name, keys):
        """해시 데이터 여러 개 조회"""
        if self.client is None:
            await self.connect()
        values = await self.client.hmget(name, keys)
        return {key: json.loads(value) if value else None for key, value in zip(keys, values)}

    async def hexists(self, name, key):
        """키 존재 여부 확인"""
        if self.client is None:
            await self.connect()
        return await self.client.hexists(name, key)

    async def hcreate_or_update(self, name, data):
        """해시 데이터 업데이트 또는 생성"""
        if self.client is None:
            await self.connect()
        async with self.client.pipeline() as pipe:
            for key, value in data.items():
                existing_value = await self.client.hget(name, key)
                if existing_value:
                    updated_value = json.loads(existing_value)
                    if isinstance(updated_value, dict) and isinstance(value, dict):
                        updated_value.update(value)
                    else:
                        updated_value = value
                else:
                    updated_value = value
                await pipe.hset(name, key, json.dumps(updated_value))
            await pipe.execute()


    # ------------------------------
    # 📌 일반 키 업데이트 (없으면 생성)
    # ------------------------------
    async def create_or_update(self, key, value, expire=None):
        """
        일반 키 데이터 업데이트 또는 생성 (비동기)
        
        :param key: Redis 키
        :param value: 저장할 값 (dict)
        :param expire: 만료 시간 (초) (옵션)
        
        사용 예시:
        await redis_manager.create_or_update("user:123", {"name": "Alice"}, expire=3600)
        """
        try:
            # 기존 값 가져오기 (비동기)
            existing_value = await self.client.get(key)

            if existing_value:
                updated_value = json.loads(existing_value)  # 기존 JSON 데이터를 dict로 변환
                updated_value.update(value)  # 기존 데이터 업데이트
            else:
                updated_value = value  # 기존 값이 없으면 새로운 값 사용

            # JSON 형식으로 Redis에 저장 (비동기)
            updated_value = json.dumps(updated_value)
            await self.client.set(key, updated_value, ex=expire)

        except RedisError as e:
            return {"error": f"Redis error: {str(e)}"}
        
    # ------------------------------
    # 📌 시계열 데이터 관리 (TimeSeries)
    # ------------------------------

    async def create_timeseries(self, key, retention=0, labels=None):
        """ 시계열 데이터베이스 생성 """
        if labels is None:
            labels = {}

        if self.client is None:
            await self.connect()

        exists = await self.client.exists(key)
        label_args = []
        for label, value in labels.items():
            label_args.extend([label, value])

        if exists:
            await self.client.execute_command(
                'TS.ALTER', key, 'DUPLICATE_POLICY', 'LAST', 'RETENTION', retention, 'LABELS', *label_args
            )
        else:
            await self.client.execute_command(
                'TS.CREATE', key, 'DUPLICATE_POLICY', 'FIRST', 'RETENTION', retention, 'LABELS', *label_args
            )

    async def add_timeseries_data(self, key, value, timestamp=None):
        """ 시계열 데이터 추가 """
        if timestamp is None:
            timestamp = int(datetime.utcnow().timestamp() * 1000)

        if self.client is None:
            await self.connect()

        await self.client.execute_command('TS.ADD', key, timestamp, value)

    
    async def get_timeseries_range(self, key_pattern, start='-', end='+', count=None, callback=None):
        """
        특정 기간의 시계열 데이터 조회 (와일드카드 지원) + COUNT 옵션 추가
        :param key_pattern: 검색할 키 패턴 (예: "alert:*")
        :param start: 조회 시작 시간 ('-'는 가장 오래된 데이터)
        :param end: 조회 종료 시간 ('+'는 최신 데이터)
        :param count: 조회할 데이터 개수 제한 (Optional)
        :param callback: 후처리 콜백 함수 (Optional)['get_labels_callback']

        사용 예시:
        data = await tsdb.get_timeseries_range("alert:*", start=1672531200000, end=1672617600000, count=100)
        print(data)
        """
        try:
            keys = []

            # 와일드카드 포함 여부 확인
            if '*' in key_pattern:
                # SCAN 명령어를 비동기적으로 실행하여 일치하는 키 찾기
                cursor = 0
                while True:
                    cursor, found_keys = await self.client.scan(cursor, match=key_pattern, count=100)
                    keys.extend(found_keys)
                    if cursor == 0:
                        break
            else:
                keys.append(key_pattern)  # 단일 키 조회

            if not keys:
                return {"error": "No matching TimeSeries keys found."}

            # Redis Pipeline 사용 (비동기 처리)
            pipeline = self.client.pipeline()
            for key in keys:
                if count:
                    pipeline.execute_command("TS.RANGE", key, start, end, "COUNT", count)
                else:
                    pipeline.execute_command("TS.RANGE", key, start, end)

            # 결과 실행 (비동기)
            results = await pipeline.execute()

            # 데이터 정리
            data = {
                key: [{"timestamp": ts, "value": value} for ts, value in result]
                for key, result in zip(keys, results)
            }

            # 콜백이 제공된 경우 실행 (비동기 처리)
            if callback:
                return await callback(data, keys)  # 콜백도 비동기로 실행
            else:
                return data

        except RedisError as e:
            return {"error": f"Redis error: {str(e)}"}
        
    async def get_labels_callback(self, result, keys):
        """
        클래스 내부의 콜백 함수 (데이터를 추가적으로 처리할 수 있음)
        """
        try:
            if not keys:
                return result

            # Redis Pipeline 사용 (비동기)
            pipeline = self.client.pipeline()
            for key in keys:
                pipeline.execute_command("TS.INFO", key)
            
            info_results = await pipeline.execute()

            # 라벨 데이터 정리
            labels_dict = {}
            for key, info in zip(keys, info_results):
                try:
                    # info 리스트에서 'labels' 키 찾기
                    label_index = info.index("labels") if "labels" in info else -1
                    if label_index != -1 and label_index + 1 < len(info):
                        raw_labels = info[label_index + 1]  # 라벨 리스트
                        if isinstance(raw_labels, list):
                            # 리스트 내 리스트 구조를 {key: value} 형태로 변환
                            labels_dict[key] = {str(entry[0]): str(entry[1]) for entry in raw_labels if isinstance(entry, list) and len(entry) == 2}
                        else:
                            labels_dict[key] = {}
                    else:
                        labels_dict[key] = {}

                except ValueError:
                    labels_dict[key] = {}  # 예외 발생 시 빈 라벨 저장

            return result, labels_dict  # 라벨 정보 포함하여 반환

        except RedisError as e:
            return result

    async def timeseries_exists(self, key):
        """
        Redis Time Series 데이터가 존재하는지 확인하는 함수
        """
        try:
            # TS.INFO를 사용하여 키의 존재 여부 확인 (비동기)
            totalSamples = await self.client.execute_command('TS.INFO', key)
            if totalSamples[1] > 0:
                return True  # 데이터가 존재하면 True 반환
            else:
                return False  # 존재하지 않으면 False 반환
        except Exception as e:
            if "TSDB: the key does not exist" in str(e):
                return False  # 존재하지 않으면 False 반환
            else:
                raise  # 기타 오류는 그대로 발생

    
    async def get_latest_timeseries(self, key, callback=None):
        """
        최신 시계열 데이터 조회 + 라벨 정보 포함 (옵션)
        :param callback ['get_labels_callback']
        
        사용 예시:
        latest = await tsdb.get_latest_timeseries("sensor:1")
        print(latest)
        """
        try:
            # 최신 데이터 조회 (비동기 실행)
            result = await self.client.execute_command('TS.GET', key)
            if not result:
                return {"error": "TimeSeries key not found."}

            # 콜백이 제공된 경우 실행
            if callback:
                return await callback(result, [key])  # 콜백도 비동기 처리
            else:
                return result

        except RedisError as e:
            return {"error": f"Redis error: {str(e)}"}

    async def get_pattern_latest_timeseries(self, key_pattern, callback=None):
        """
        와일드카드 패턴을 사용하여 여러 시계열 키의 최신 데이터 조회
        :param callback ['get_labels_callback']

        사용 예시:
        latest = await tsdb.get_pattern_latest_timeseries("sensor:*")
        print(latest)
        """
        try:
            # 패턴에 '*'가 없으면 예외 처리
            if '*' not in key_pattern:
                return {"error": "This function only supports wildcard patterns. Use get_latest_timeseries for single keys."}

            keys = []
            cursor = 0

            # SCAN을 비동기로 실행하여 패턴에 맞는 키 검색
            while True:
                cursor, found_keys = await self.client.scan(cursor, match=key_pattern, count=100)
                keys.extend(found_keys)
                if cursor == 0:
                    break

            if not keys:
                return {"error": "No matching TimeSeries keys found."}

            # Redis Pipeline 사용 (비동기 처리)
            pipeline = self.client.pipeline()
            for key in keys:
                pipeline.execute_command("TS.GET", key)

            results = await pipeline.execute()  # 비동기로 실행

            # 데이터 정리
            data = {
                key: {"timestamp": result[0], "value": result[1]} if result else None
                for key, result in zip(keys, results)
            }

            # 콜백이 제공된 경우 실행
            if callback:
                return await callback(data, keys)  # 콜백도 비동기 처리
            else:
                return data

        except RedisError as e:
            return {"error": f"Redis error: {str(e)}"}

    async def delete_timeseries(self, key):
        """
        시계열 키 삭제
        
        사용 예시:
        await tsdb.delete_timeseries("sensor:1")
        """
        try:
            return await self.client.delete(key)
        except RedisError as e:
            return {"error": f"Redis error: {str(e)}"}


    # ------------------------------
    # 📌 키 검색 기능 (비동기)
    # ------------------------------

    async def query_scan(self, pattern):
        """ Redis의 모든 키를 SCAN을 이용해 검색 """
        if self.client is None:
            await self.connect()
        cursor = 0
        matched_keys = []

        while True:
            cursor, keys = await self.client.scan(cursor, match=pattern, count=100)
            if keys:
                matched_keys.extend(keys)
            if cursor == 0:
                break

        return matched_keys

    async def query_keys(self, pattern):
        """
        패턴을 기반으로 특정 키만 조회 (비동기)
        :param pattern: ["*", "9", "Sensor", "*", "*"] 같은 리스트 형식
        사용 예시:
        result_keys = await redis_manager.query_keys(["*", "9", "Sensor", "*", "*"])
        print(result_keys)
        """
        try:
            # 1️⃣ 모든 키 가져오기 (비동기)
            keys = await self.client.keys('*')

            # 2️⃣ "*"을 제외한 필터링할 값만 추출
            filters = [p for p in pattern if p != "*"]

            # 3️⃣ 필터링 적용 (모든 키에서 필터링할 값이 있는지 확인)
            result_keys = [key for key in keys if all(f in key for f in filters)]

            return result_keys

        except RedisError as e:
            return {"error": f"Redis error: {str(e)}"}

    async def query_by_label(self, label_filter):
        """ 라벨을 기반으로 시계열 키 검색 """
        if self.client is None:
            await self.connect()
        return await self.client.execute_command('TS.QUERYINDEX', label_filter)

    async def get_data_by_label(self, label_filter, start='-', end='+'):
        """ 라벨을 기반으로 시계열 데이터 조회 """
        if self.client is None:
            await self.connect()
        return await self.client.execute_command('TS.MRANGE', start, end, 'FILTER', label_filter)

    # ------------------------------
    # 📌 커스텀 집계 기능 (비동기)
    # ------------------------------

    async def custom_aggregate(self, source_keys, query_key='*', aggregate_type=['MIN', 'MAX', 'AVG'], batch_size=10, minute=5, delay=0):
        """
        비동기 방식으로 여러 키의 집계 연산 수행
        """
        if self.client is None:
            await self.connect()
        
        results = {}
        ndigit = 4
        end_time = int(datetime.now().timestamp() * 1000) - delay * 1000
        start_time = end_time - (minute * 60 * 1000)
        total_time = (end_time - start_time) / 1000
        
        for i in range(0, len(source_keys), batch_size):
            batch_keys = [key for key in source_keys[i:i + batch_size] if query_key in key or query_key == '*']
            async with self.client.pipeline() as pipe:
                for source_key in batch_keys:
                    await pipe.execute_command('TS.RANGE', source_key, start_time, end_time)
                responses = await pipe.execute()
            
            for source_key, data in zip(batch_keys, responses):
                if not data:
                    results[source_key] = {agg: None for agg in aggregate_type}
                    continue
                
                df = pd.DataFrame(data, columns=['timestamp', 'value'])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                df.set_index('timestamp', inplace=True)
                
                # 값이 문자열로 반환될 경우 숫자로 변환
                df['value'] = pd.to_numeric(df['value'], errors='coerce')
                df.dropna(subset=['value'], inplace=True)  # 변환되지 않은 값 제거
                
                if df.empty:
                    results[source_key] = {agg: None for agg in aggregate_type}
                    continue
                
                # 데이터 타입 확인
                dtype = df['value'].dtype

                # int, float, bool 이외의 경우 (예: 문자열) 예외 처리
                if not np.issubdtype(dtype, np.number):
                    raise ValueError("value 컬럼이 숫자형이 아닙니다.")
                
                agg_results = {}
                for agg in aggregate_type:
                    if agg == 'AVG':  # 평균값 계산
                        agg_results['AVG'] = round(float(df['value'].mean()), ndigit) if np.issubdtype(dtype, np.floating) else int(df['value'].mean())
                    elif agg == 'SUM':  # 합계 계산
                        agg_results['SUM'] = round(float(df['value'].sum()), ndigit) if np.issubdtype(dtype, np.floating) else int(df['value'].sum())
                    elif agg == 'MIN':  # 최소값 계산
                        agg_results['MIN'] = round(float(df['value'].min()), ndigit) if np.issubdtype(dtype, np.floating) else int(df['value'].min())
                    elif agg == 'MAX':  # 최대값 계산
                        agg_results['MAX'] = round(float(df['value'].max()), ndigit) if np.issubdtype(dtype, np.floating) else int(df['value'].max())
                    elif agg == 'COUNT':  # 데이터 개수 계산
                        agg_results['COUNT'] = df['value'].count()
                    elif agg == 'FIRST':  # 첫 번째 값
                        agg_results['FIRST'] = round(float(df['value'].iloc[0]), ndigit) if np.issubdtype(dtype, np.floating) else int(df['value'].iloc[0])
                    elif agg == 'LAST':  # 마지막 값
                        agg_results['LAST'] = round(float(df['value'].iloc[-1]), ndigit) if np.issubdtype(dtype, np.floating) else int(df['value'].iloc[-1])
                    elif agg == 'STDDEV':
                        agg_results['STDDEV'] = round(float(df['value'].std()), ndigit)  # 🔹 float 변환
                    elif agg == 'VARIANCE':
                        agg_results['VARIANCE'] = round(float(df['value'].var()), ndigit)  # 🔹 float 변환
                    elif agg == 'RANGE':
                        agg_results['RANGE'] = round(float(df['value'].max() - df['value'].min()), ndigit) if np.issubdtype(dtype, np.floating) else int(df['value'].max() - df['value'].min())
                    elif agg == 'DIFFERENCE':
                        agg_results['DIFFERENCE'] = [round(float(x), ndigit) for x in df['value'].diff().dropna().tolist()]  # 🔹 리스트 내 값 float 변환
                    elif agg == 'DIFFERENCE_SUM':
                        diff_sum = df['value'].diff().dropna().sum()
                        agg_results['DIFFERENCE_SUM'] = round(diff_sum, ndigit) if diff_sum is not None else 0  # 🔹 float 변환
                    elif agg == 'DERIVATIVE':
                        diff_mean = df['value'].diff().dropna().mean()
                        # NaN이 나오지 않도록 체크 후 변환
                        agg_results['DERIVATIVE'] = round(float(diff_mean), ndigit) if not np.isnan(diff_mean) else 0
                    elif agg == 'NONNEGATIVE_DERIVATIVE':
                        agg_results['NONNEGATIVE_DERIVATIVE'] = round(float(df['value'].diff().clip(lower=0).dropna().mean()), ndigit)  # 🔹 float 변환
                    elif agg == 'HISTOGRAM':
                        agg_results['HISTOGRAM'] = {k: int(v) for k, v in df['value'].value_counts().to_dict().items()}  # 🔹 int 변환
                    elif agg == 'SPREAD':
                        agg_results['SPREAD'] = round(float(df['value'].max() - df['value'].min()), ndigit)  # 🔹 float 변환
                    elif agg == 'MEDIAN':
                        agg_results['MEDIAN'] = round(float(df['value'].median()), ndigit)  # 🔹 float 변환
                    elif agg == 'SKEW':
                        agg_results['SKEW'] = round(float(df['value'].skew()), ndigit)  # 🔹 float 변환
                    elif agg == 'CHANGE_TIME':  # 마지막으로 값이 변한 시점
                        last_change = df[df['value'] != df['value'].shift()].index[-1]
                        # UTC 타임존 지정 후, 로컬 타임존 변환
                        last_change = last_change.tz_localize('UTC').tz_convert(local_tz)
                        agg_results['CHANGE_TIME'] = last_change
                    elif agg == 'RUN_TIME':  # 값이 0이 아닌 시간의 총합
                        run_time_series = df[df['value'] > 0].index.to_series().diff().dropna().dt.total_seconds()
                        run_time = run_time_series.sum() if not run_time_series.empty else 0
                        agg_results['RUN_TIME'] = run_time
                    elif agg == 'DOWN_TIME':  # 값이 0인 시간의 총합
                        down_time = total_time - agg_results.get('RUN_TIME', 0)
                        agg_results['DOWN_TIME'] = down_time
                    elif agg == 'UP_PULSE_TIME':
                        up_time = df[df['value'].diff() > 0].index.max()
                        agg_results['UP_PULSE_TIME'] = up_time if not pd.isnull(up_time) else None
                    elif agg == 'DOWN_PULSE_TIME':
                        down_time = df[df['value'].diff() < 0].index.max()
                        agg_results['DOWN_PULSE_TIME'] = down_time if not pd.isnull(down_time) else None
                    else:
                        raise ValueError(f"Unsupported aggregation type: {agg}")
                results[source_key] = agg_results
        
        return results, (datetime.now() - timedelta(seconds=delay)).strftime('%Y-%m-%dT%H:%M:%S')
    
    # ------------------------------
    # 📌 백업 및 복원 기능 (비동기)
    # ------------------------------

    async def backup_data(self, file_path='redis_backup.json'):
        """ Redis 데이터를 JSON 파일로 백업 """
        if self.client is None:
            await self.connect()
        data = {key: await self.get_value(key) for key in await self.get_all_keys()}
        with open(file_path, 'w', encoding='utf-8') as file:
            json.dump(data, file, ensure_ascii=False, indent=4)

    async def restore_data(self, file_path='redis_backup.json'):
        """ JSON 백업 파일을 Redis로 복원 """
        with open(file_path, 'r', encoding='utf-8') as file:
            data = json.load(file)
            for key, value in data.items():
                await self.set_value(key, value)
    # ------------------------------
    # 📌 시계열 데이터 Bulk 저장 및 업데이트 (비동기)
    # ------------------------------

    async def bulk_add_timeseries(self, data):
        """ 여러 개의 시계열 데이터를 한 번에 추가 """
        if self.client is None:
            await self.connect()
        async with self.client.pipeline() as pipe:
            for key, values in data.items():
                for timestamp, value in values:
                    await pipe.execute_command("TS.ADD", key, timestamp, value)
            await pipe.execute()

    async def bulk_update_timeseries(self, data):
        """ 여러 개의 시계열 데이터를 한 번에 업데이트 """
        if self.client is None:
            await self.connect()
        async with self.client.pipeline() as pipe:
            for key, values in data.items():
                for timestamp, new_value in values:
                    existing_data = await self.client.execute_command("TS.RANGE", key, timestamp, timestamp)
                    if existing_data:
                        await self.client.execute_command("TS.DEL", key, timestamp, timestamp)
                    await pipe.execute_command("TS.ADD", key, timestamp, new_value)
            await pipe.execute()

    async def close(self):
        """Redis 연결 종료"""
        if self.client:
            await self.client.close()
            print("✅ Redis 연결 종료됨")