from fastapi import exceptions, requests
from utils.config import settings
from influxdb_client import InfluxDBClient, Point
from datetime import datetime, timedelta
from influxdb_client.client.write_api import SYNCHRONOUS
from typing import Dict, List
from utils.protocol.HTTP import phttp
from influxdb_client.rest import ApiException

class Influx_Database:
    def __init__(self):
        """
        데이터베이스 연결 초기화.
        .env 파일에서 설정 정보를 가져와 사용합니다.
        """
        self.client = None
        self.write_api = None
        self.query_api = None

    def connect(self):
        """
        InfluxDB 연결 생성 및 초기화.
        """
        if not self.client:
            try:
                self.client = InfluxDBClient(
                    url=settings.INFLUXDB_URL,
                    token=settings.INFLUXDB_TOKEN,
                    org=settings.INFLUXDB_ORG
                )
                self.write_api = self.client.write_api(write_options=SYNCHRONOUS)
                self.query_api = self.client.query_api()
            except Exception as e:
                raise ConnectionError(f"Failed to connect to InfluxDB: {e}")

    def is_connected(self):
        """연결 상태 확인"""
        try:
            return self.client.ping() if self.client else False
        except ApiException:
            return False
        
    def execute_query(self, query: str) -> List[dict]:
        """
        Flux 쿼리 실행.
        :param query: Flux 쿼리 문자열
        :return: 쿼리 결과 리스트
        """
        self.connect()
        try:
            result = self.query_api.query(query=query, org=settings.INFLUXDB_ORG)
            # 결과 파싱
            data = [
                {
                    "time": record.get_time(),
                    "value": record.get_value(),
                    "field": record.get_field(),
                    "measurement": record.get_measurement()
                }
                for table in result for record in table.records
            ]
            return data
        except Exception as e:
            raise RuntimeError(f"Failed to execute query: {e}")

    def execute_queries(
        self, 
        bucket:str, 
        measurements: List[str], 
        tags: Dict[str, str] = None,
        fields: List[str] = None,
        start_time: str = "-1h",
        stop_time: str = "now()",
        latest: bool = False
    ) -> List[dict]:
        """
        여러 개의 measurement 데이터를 가져오되, 태그, 필드 및 시간 범위를 필터링할 수 있음.
        최신 데이터만 가져오는 기능도 포함.

        :param measurements: measurement 리스트
        :param tags: 필터링할 태그 딕셔너리 (예: {"device": "sensor_1"})
        :param fields: 특정 필드 값만 가져오도록 설정 (예: ["temperature", "humidity"])
        :param start_time: 조회 시작 시간 (예: "-1h", "-30m", "2024-01-01T00:00:00Z")
        :param stop_time: 조회 종료 시간 (기본값: "now()")
        :param latest: True이면 최신 값 한 개만 가져옴.
        :return: 쿼리 결과 리스트
        """
        self.connect()
        
        # measurement 리스트를 Flux 쿼리용 문자열로 변환
        measurement_filter = ', '.join(f'"{m}"' for m in measurements)

        # 태그 필터링 추가
        tag_filters = ""
        if tags:
            tag_filters = " ".join(f'|> filter(fn: (r) => r["{k}"] == "{v}")' for k, v in tags.items())

        # 필드 필터링 추가
        field_filters = ""
        if fields:
            field_filters = ' |> filter(fn: (r) => contains(value: r["_field"], set: [' + ", ".join(f'"{f}"' for f in fields) + ']))'

        # 최신 데이터만 가져오기 (sort 후 limit 적용)
        latest_filter = ""
        if latest:
            latest_filter = "|> sort(columns: [\"_time\"], desc: true) |> limit(n: 1)"

        # Flux 쿼리 생성
        query = f'''
        from(bucket: "{bucket}")
        |> range(start: {start_time}, stop: {stop_time})
        |> filter(fn: (r) => contains(value: r._measurement, set: [{measurement_filter}]))
        {tag_filters}
        {field_filters}
        {latest_filter}
        '''

        try:
            result = self.query_api.query(query=query, org=settings.INFLUXDB_ORG)
            data = [
                {
                    "time": record.get_time(),
                    "value": record.get_value(),
                    "field": record.get_field(),
                    "measurement": record.get_measurement(),
                    "tags": record.values  # 모든 태그 포함
                }
                for table in result for record in table.records
            ]
            return data
        except Exception as e:
            raise RuntimeError(f"Failed to execute query: {e}")
        
    def execute_write(self, bucket: str, measurement: str, tags: dict, fields: dict, time: str = None):
        """
        데이터 쓰기.
        :param measurement: 측정 이름
        :param tags: 태그 데이터 (dict)
        :param fields: 필드 데이터 (dict)
        :param time(str): 입력 시간: 한국 시간 ISO 8601 format => '%Y-%m-%d %H:%M:%S'
        """
        self.connect()
        point = Point(measurement)

        # 태그 추가
        for tag_key, tag_value in tags.items():
            point = point.tag(tag_key, tag_value)

        # 필드 추가
        for field_key, field_value in fields.items():
            point = point.field(field_key, field_value)

        # 시간 변환: 한국 시간(UTC+09:00)을 UTC로 변환
        if time:
            local_time = datetime.fromisoformat(time)  # 입력 시간: 한국 시간 ISO 8601
            utc_time = local_time - timedelta(hours=9)  # UTC로 변환
            time = utc_time.isoformat() + "Z"  # UTC 시간 ISO 8601 포맷
        else:
            # 시간 미지정 시 현재 UTC 시간을 기본값으로 사용
            utc_time = datetime.now() - timedelta(hours=9)  # UTC로 변환
            time = utc_time.isoformat() + "Z"  # UTC 시간 ISO 8601 포맷

        # 데이터 쓰기
        self.write_api.write(
            bucket=bucket,
            org=settings.INFLUXDB_ORG,
            record=point.time(time)
        )
    def delete_data(self, bucket: str, start_time: str, stop_time: str, predicate: str):
        """
        InfluxDB에서 데이터 삭제.
        :param start_time: 삭제 범위 시작 시간 (ISO 8601 형식)
        :param stop_time: 삭제 범위 종료 시간 (ISO 8601 형식)
        :param predicate: 데이터 삭제 조건 (Flux 표현식)
        """
        self.connect()
        try:
            self.client.delete_api().delete(
                start=start_time,
                stop=stop_time,
                predicate=predicate,
                bucket=bucket,
                org=settings.INFLUXDB_ORG,
            )
            print(f"Data deleted successfully from {start_time} to {stop_time} with predicate: {predicate}")
        except Exception as e:
            raise RuntimeError(f"Failed to delete data: {e}")

    def find_and_store_missing_data(self, bucket:str, start_time: str, end_time: str, measurement: str, interval_minutes: int, url: str, tags_list: List[str]):
        """
        누락된 데이터를 확인하고, API에서 데이터를 가져와 InfluxDB에 저장.
        :param start_time: 시작 시간 (ISO 8601 형식)
        :param end_time: 종료 시간 (ISO 8601 형식)
        :param measurement: 확인할 Measurement 이름
        :param url: 데이터 호출 API URL
        :param tags_list: 저장할 태그 키 리스트
        :param interval_minutes: 간격 (분)
        """
        self.connect()

        
        # 복구 조건(Predicate) 구성
        predicate = f'r._measurement=="{measurement}"'
        # Flux 쿼리
        query = f'''
        from(bucket: "{bucket}")
          |> range(start: {start_time}, stop: {end_time})
          |> filter(fn: (r) => {predicate})
          |> keep(columns: ["_time"])
        '''
        self.connect()
        try:
            result = self.query_api.query(query=query, org=settings.INFLUXDB_ORG)
            # InfluxDB 데이터 결과 파싱
            data_times = []
            for table in result:
                for record in table.records:
                    time_str = record.get_time()
                    try:
                        # 문자열을 datetime 객체로 변환
                        if type(time_str) != datetime:
                            data_times.append(datetime.fromisoformat(time_str))
                        else:
                            data_times.append(time_str)
                    except ValueError:
                        print(f"Invalid time format: {time_str}")
        except Exception as e:
            raise RuntimeError(f"Failed to execute query: {e}")

        # 5분 간격의 전체 시간 목록 생성
        start_dt = datetime.fromisoformat(start_time)
        end_dt = datetime.fromisoformat(end_time)

        expected_times = [
            (start_dt + timedelta(minutes=i)).replace(microsecond=0)
            for i in range(0, int((end_dt - start_dt).total_seconds() / 60), interval_minutes)
        ]

        # data_times를 초 이하 단위를 제거해 정리
        data_times_set = {time.replace(microsecond=0) for time in data_times}

        # 누락된 시간대 찾기
        missing_intervals = [time for time in expected_times if time not in data_times_set]
        
        if not missing_intervals:
            print("No missing intervals detected.")
            return {"message": "No missing data to recover."}
        
        # 누락된 데이터 복구
        try:
            for i, missing_start in enumerate(missing_intervals):
                # 범위를 개별 요청으로 처리
                missing_end = missing_start + timedelta(minutes=interval_minutes)
                params = {
                    'created_at__gte': missing_start.isoformat()[:-6],
                    'created_at__lte': missing_end.isoformat()[:-6],
                }
                response = phttp.GET(url=url, params=params)

                # 배치 데이터 쓰기
                points = []
                for row in response:
                    # 유효한 태그만 선택
                    tags = {tag: row[tag] for tag in tags_list if tag in row and row[tag] is not None}

                    # 유효한 필드 데이터 추출
                    fields = row.get('getData', {}).get('data', {})
                    if not fields:  # 필드가 비어있으면 건너뜀
                        continue

                    # 시간 데이터 처리
                    time = row.get('created_at')
                    try:
                        # 시간 형식 검증 (필요 시 맞는 형식으로 수정)
                        parsed_time = time+"+09:00" if time else None
                    except ValueError:
                        print(f"Invalid time format: {time}")
                        continue
                    # 포인트 객체 생성
                    point = Point(measurement)
                    for tag_key, tag_value in tags.items():
                        point = point.tag(tag_key, tag_value)
                    for field_key, field_value in fields.items():
                        point = point.field(field_key, field_value)
                    if parsed_time:
                        point = point.time(parsed_time)
                    points.append(point)
                if points:
                    self.write_api.write(bucket=settings.INFLUXDB_BUCKET, org=settings.INFLUXDB_ORG, record=points)
                    print(f"Batch {i + 1}: {len(points)} points written.")
            print("All missing data successfully stored in InfluxDB.")
        except exceptions.WebSocketException as e:
            raise RuntimeError(f"Failed to fetch data from API: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"Error storing data to InfluxDB: {str(e)}")

    def list_buckets(self) -> List[dict]:
        """
        버킷 목록 조회.
        :return: 버킷 정보 리스트
        """
        self.connect()
        try:
            buckets_api = self.client.buckets_api()
            org_api = self.client.organizations_api()
            buckets = buckets_api.find_buckets().buckets
            # 모든 조직을 조회하여 ID로 매핑
            orgs = org_api.find_organizations()
            return [
                {
                    "id": b.id,
                    "name": b.name,
                    "org_id": b.org_id,
                    "org_name": next((o.name for o in orgs if o.id == b.org_id), None),
                    "labels": [
                        {"id": lbl.id, "name": lbl.name}
                        for lbl in getattr(b, 'labels', [])
                    ]
                }
                for b in buckets
            ]
        except ApiException as e:
            # 인증 실패 시 HTTP 401 응답으로 전달
            raise exceptions.HTTPException(status_code=401, detail="InfluxDB unauthorized access")
        except Exception as e:
            raise RuntimeError(f"Failed to list buckets: {e}")

    def close(self):
        """
        InfluxDB 연결 종료.
        """
        if self.client:
            try:
                self.client.close()
                self.client = None
                self.write_api = None
                self.query_api = None
                print("InfluxDB connection closed successfully.")
            except Exception as e:
                raise RuntimeError(f"Failed to close InfluxDB connection: {e}")

