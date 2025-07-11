from functools import reduce
import json, sys, time
from datetime import datetime, timedelta
from app.utils.protocol.LSIS import LSIS_TcpClient
from app.utils import setup_logger
from app.utils.DB import SQLBuilder
from app.db import *
from app.utils import dict_to_object, log_exceptions
from app.utils.protocol.LSIS.utilities import LSIS_MappingTool
from app.utils.DB.context import RegistersSlaveContext
from app.utils.protocol.HTTP import phttp

client_logger = setup_logger(name="client_logger", log_file="./log/client_queries.log")

# 글로벌 변수 선언
LS_XGT_TCP_CLIENT = []
VAR_ITEMS = None
sample_count = 0
raw_count = 0

def initialize():
    """
    애플리케이션 초기화 함수.
    글로벌 변수와 클라이언트를 초기화합니다.
    """
    global LS_XGT_TCP_CLIENT, VAR_ITEMS
    global sample_count, raw_count

    # 글로벌 변수 초기화
    LS_XGT_TCP_CLIENT = {}
    VAR_ITEMS = {}
    VAR_KEYS = ['status', 'log', 'write', 'alert']
    sample_count = 0
    raw_count = 0
    client_logger.info("client 글로벌 변수 초기화")
    
    # REDIS에 변수정보 불러오기 없으면 글로벌 변수 사용
    if redis_instance.exists("VAR_ITEMS"):
        VAR_ITEMS = redis_instance.get_value("VAR_ITEMS").copy()

    sensors_query = SQLBuilder(table_name="jais_Sensor", instance=db_instance).all()
    sensors = sensors_query.execute()
    for sensor in sensors:
        sensor = dict_to_object(sensor)
        for (key, value) in json.loads(sensor.mapping).items():
            labels= {
                "cid":sensor.Channel_id,
                "fid":sensor.Basic_Facility_id,
                "bid":sensor.Basic_Sensor_id,
                "rid":sensor.id,
            }
            for i, category in enumerate(VAR_KEYS, start=5):  # 5번째 인덱스부터 시작
                if value.split(',')[i] == 'true':
                    if value.split(',')[0] in ['bit']:
                        VAR_ITEMS.setdefault(str(sensor.Channel_id), {}).setdefault(category, {})[f"{category}:Sensor:{key}:bool:{sensor.id}"] = value.split(',') + [key]
                        redis_instance.create_timeseries(
                            f"{category}:Sensor:{key}:bool:{sensor.id}", retention=7*24*60*60*1000, labels=labels
                        )
                    else:
                        VAR_ITEMS.setdefault(str(sensor.Channel_id), {}).setdefault(category, {})[f"{category}:Sensor:{key}:number:{sensor.id}"] = value.split(',') + [key]
                        redis_instance.create_timeseries(
                            f"{category}:Sensor:{key}:number:{sensor.id}", retention=7*24*60*60*1000, labels=labels
                        )

    equipments_query = SQLBuilder(table_name="jais_Equipment", instance=db_instance).all()
    equipments = equipments_query.execute()
    for equipment in equipments:
        equipment = dict_to_object(equipment)
        for (key, value) in json.loads(equipment.mapping).items():
            labels= {
                "cid":equipment.Channel_id,
                "fid":equipment.Basic_Facility_id,
                "bid":equipment.Basic_Equipment_id,
                "rid":equipment.id,
            }
            for i, category in enumerate(VAR_KEYS, start=5):  # 5번째 인덱스부터 시작
                if value.split(',')[i] == 'true':
                    facility_id = str(equipment.Basic_Facility_id)
                    equipment_id = str(equipment.Basic_Equipment_id)
                    if value.split(',')[0] in ['bit']:
                        VAR_ITEMS.setdefault(str(equipment.Channel_id), {}).setdefault(category, {})[f"{category}:Equipment:{key}:bool:{equipment.id}"] = value.split(',') + [key]
                        redis_instance.create_timeseries(
                            f"{category}:Equipment:{key}:bool:{equipment.id}", retention=7*24*60*60*1000, labels=labels
                        )
                    else:
                        VAR_ITEMS.setdefault(str(equipment.Channel_id), {}).setdefault(category, {})[f"{category}:Equipment:{key}:number:{equipment.id}"] = value.split(',') + [key]
                        redis_instance.create_timeseries(
                            f"{category}:Equipment:{key}:number:{equipment.id}", retention=7*24*60*60*1000, labels=labels
                        )

    # REDIS에 변수정보 저장
    redis_instance.set_value("VAR_ITEMS", VAR_ITEMS)   
    

def LS_XGT_TCP_CONNECT(*args, **kwargs):
    global LS_XGT_TCP_CLIENT, VAR_ITEMS
    LS_XGT_TCP_CLIENT[str(kwargs['channel_id'])] = []
    channel_key = F"Channel:{kwargs['channel_id']}"
    default_setting = {
        "reconnect_delay": 1000,
        "reconnect_delay_max": 60000,
        "retry_on_empty": True,
    }
    for client in args:
        if 'port' in client:
            sock = LSIS_TcpClient(host=client['host'], port=client['port'], **default_setting)
        else:
            sock = LSIS_TcpClient(host=client['host'], **default_setting)
        sock.connect(retry_forever=False)
        LS_XGT_TCP_CLIENT[str(kwargs['channel_id'])].append(sock)
        start_address = int(client['address'])
        end_address = int(client['address'])+client['count']
        if start_address < end_address and type(start_address) == int and type(end_address) == int:
            if 'port' in client:
                if not redis_instance.hexists(channel_key, f"{client['host']}:{client['port']}"):
                    redis_instance.hset(channel_key, f"client:{client['host']}:{client['port']}", f"{start_address}, {end_address}")
            else:
                if not redis_instance.hexists(channel_key, f"{client['host']}:2004"):
                    redis_instance.hset(channel_key, f"client:{client['host']}:2004", f"{start_address}, {end_address}")
        else:
            client_logger.error(f'client.py :: LS_XGT_TCP_CONNECT redis_instance.hset : err')


@log_exceptions(client_logger)
def LS_XGT_TCP_TO_CHANNEL(*args, **kwargs):
    global LS_XGT_TCP_CLIENT, VAR_ITEMS
    result = []

    for client in args:
        # 각 클라이언트에 대해 함수 호출 및 결과 저장
        client_index = args.index(client)
        func_name = client['func_name']
        memory_address = client['memory'] + client['address']
        count = client['count']
        # 해당 클라이언트의 함수 실행
        client_result = getattr(LS_XGT_TCP_CLIENT[str(kwargs['channel_id'])][client_index], func_name)(memory_address, count)
        result.append(client_result)

    if kwargs['listener'] != 'None':
        getattr(sys.modules[__name__], kwargs['listener'])(result, *args, **kwargs)
        
def HTTP_TO_CHANNEL(*args, **kwargs):
    result = [getattr(phttp, client['func_name'])(url=client['url']) for client in args]
    if kwargs['listener'] != 'None':
        getattr(sys.modules[__name__], kwargs['listener'])(result, *args, **kwargs)


@log_exceptions(client_logger)
def REDIS_MAPPING_LOGGER_2m(*args, **kwargs):
    start_time = datetime.now()
    log_keys = redis_instance.query_scan('log:*')
    result, log_dt = redis_instance.custom_aggregate(log_keys, minute=2, delay=5, aggregate_type=['MIN', 'MAX', 'LAST', 'AVG', 'CHANGE_TIME'])
    for tag, values in result.items():
        if values['CHANGE_TIME'] != None:
            values['CHANGE_TIME'] = values['CHANGE_TIME'].isoformat()
        fields = {
            k: (float("{:.1f}".format(round(v, 1))) if isinstance(v, (int, float)) else v) 
            for k, v in values.items()
        }
        inFlux_instance.execute_write(measurement=tag, tags={'cron':'2min'}, fields=fields, time=log_dt)
    end_time = datetime.now()  # 실행 완료 시간 기록
    duration = (end_time - start_time).total_seconds()
    client_logger.info(f"[{log_dt}] FUNC=REDIS_MAPPING_LOGGER_2min 작업 완료 (실행 시간: {duration}초)")

@log_exceptions(client_logger)
def REDIS_MAPPING_LOGGER_10m(*args, **kwargs):
    start_time = datetime.now()
    log_keys = redis_instance.query_scan('log:*')
    result, log_dt = redis_instance.custom_aggregate(log_keys, minute=10, delay=15, aggregate_type=['MIN', 'MAX', 'LAST', 'AVG', 'CHANGE_TIME'])
    for tag, values in result.items():
        if values['CHANGE_TIME'] != None:
            values['CHANGE_TIME'] = values['CHANGE_TIME'].isoformat()
        fields = {
            k: (float("{:.1f}".format(round(v, 1))) if isinstance(v, (int, float)) else v) 
            for k, v in values.items()
        }
        inFlux_instance.execute_write(measurement=tag, tags={'cron':'10min'}, fields=fields, time=log_dt)
    end_time = datetime.now()  # 실행 완료 시간 기록
    duration = (end_time - start_time).total_seconds()
    client_logger.info(f"[{log_dt}] FUNC=REDIS_MAPPING_LOGGER_10min 작업 완료 (실행 시간: {duration}초)")



@log_exceptions(client_logger)
def REDIS_MAPPING_LOGGER_5m(*args, **kwargs):
    """
    기본 통계값

    MIN / MAX: 최소/최대값
    AVG: 평균
    SUM: 합계
    COUNT: 데이터 개수
    FIRST / LAST: 해당 기간의 첫 번째/마지막 값
    변동성 분석

    STDDEV / VARIANCE: 표준편차, 분산
    RANGE / SPREAD: 데이터의 변동폭
    추세 분석

    DIFFERENCE / DERIVATIVE / NONNEGATIVE_DERIVATIVE: 변화량, 변화율
    SKEW: 왜도(데이터의 비대칭성)
    이벤트 감지

    CHANGE_TIME: 마지막으로 값이 변한 시간
    HISTOGRAM: 값의 분포

    (1) 5분 간격
    Number: 센서값의 실시간 변화 감지 (MAX, MIN, AVG, DERIVATIVE)
    Boolean: 장비가 동작했는지 확인 (COUNT, RUN_TIME)
    """
    minute = 5
    delay = 20
    start_time = datetime.now()
    log_format = {
        'rtype': None, 
        'rid': None, 
        'name': None, 
        'measured_at': None, 
        'type': None, 
        'value': None, 
        'info': None, 
    }
    bulk_create_queries = []
    aggregate = {}
    aggregate['number'] = ['MIN', 'MAX', 'AVG', 'SUM', 'FIRST', 'LAST', 'DIFFERENCE_SUM', 'DERIVATIVE', 'SPREAD', 'CHANGE_TIME']
    aggregate['bool'] = ['FIRST', 'LAST', 'RUN_TIME', 'DOWN_TIME', 'CHANGE_TIME']
    log_keys = redis_instance.query_scan('log:*')
    for query_key in ['number', 'bool']:
        result, log_dt = redis_instance.custom_aggregate(log_keys, query_key=query_key, minute=minute, delay=delay, aggregate_type=aggregate[query_key])
        for tag, values in result.items():
            tags = tag.split(':')
            log_value = log_format.copy()
            log_value['rtype'] = tags[1]
            log_value['name'] = tags[2]
            log_value['rid'] = str(tags[4])
            log_value['measured_at'] = log_dt.replace('T', ' ')
            if query_key == 'bool':
                log_value['type'] = query_key
                log_value['value'] = str(bool(values['LAST'])) if values['LAST'] is not None else None
            else:
                log_value['type'] = type(values['LAST']).__name__
                if log_value['type'] == "int":
                    log_value['value'] = str(int(values['LAST'])) if values['LAST'] is not None else values['LAST']
                elif log_value['type'] == "float":
                    log_value['value'] = str(round(float(values['LAST']), 4)) if values['LAST'] is not None else values['LAST']
            log_value['info'] = { **values}
            if log_value['info']['CHANGE_TIME'] != None:
                log_value['info']['CHANGE_TIME'] = values['CHANGE_TIME'].isoformat().replace('T', ' ').replace('+09:00', '')
            
            log_value['info'] = json.dumps({ **log_value['info']})
            if log_value['value'] is not None:
                bulk_create_queries.append(
                    log_value
                )
            else:
                client_logger.error(f"[{log_dt}] FUNC=REDIS_MAPPING_LOGGER_5min 에러발생 ({log_value})")
    log_read_query = SQLBuilder(table_name='jais_log_read_raw', instance=db_instance).bulk_create(
        bulk_create_queries
    ).execute_many()
    end_time = datetime.now()  # 실행 완료 시간 기록
    duration = (end_time - start_time).total_seconds()
    client_logger.info(f"[{log_dt}] FUNC=REDIS_MAPPING_LOGGER_5min 작업 완료 (실행 시간: {duration}초)")

@log_exceptions(client_logger)
def REDIS_MAPPING_LOGGER_15m(*args, **kwargs):
    """
    기본 통계값

    MIN / MAX: 최소/최대값
    AVG: 평균
    SUM: 합계
    COUNT: 데이터 개수
    FIRST / LAST: 해당 기간의 첫 번째/마지막 값
    변동성 분석

    STDDEV / VARIANCE: 표준편차, 분산
    RANGE / SPREAD: 데이터의 변동폭
    추세 분석

    DIFFERENCE / DERIVATIVE / NONNEGATIVE_DERIVATIVE: 변화량, 변화율
    SKEW: 왜도(데이터의 비대칭성)
    이벤트 감지

    CHANGE_TIME: 마지막으로 값이 변한 시간
    HISTOGRAM: 값의 분포
    
    (2) 15분 간격
    Number: 주기적 트렌드 분석 (MEDIAN, HISTOGRAM)
    Boolean: 특정 이벤트(예: 기계 작동) 빈도 분석 (COUNT, CHANGE_TIME)
    """
    minute = 15
    delay = 12
    start_time = datetime.now()
    log_format = {
        'rtype': None, 
        'rid': None, 
        'name': None, 
        'measured_at': None, 
        'type': None, 
        'value': None, 
        'info': None, 
    }
    bulk_create_queries = []
    aggregate = {}
    aggregate['number'] = ['MIN', 'MAX', 'AVG', 'SUM', 'FIRST', 'MEDIAN', 'LAST', 'DIFFERENCE_SUM', 'VARIANCE', 'RANGE', 'DERIVATIVE', 'SPREAD', 'CHANGE_TIME']
    aggregate['bool'] = ['FIRST', 'LAST', 'RUN_TIME', 'DOWN_TIME', 'CHANGE_TIME']
    log_keys = redis_instance.query_scan('log:*')
    for query_key in ['number', 'bool']:
        result, log_dt = redis_instance.custom_aggregate(log_keys, query_key=query_key, minute=minute, delay=delay, aggregate_type=aggregate[query_key])
        for tag, values in result.items():
            tags = tag.split(':')
            log_value = log_format.copy()
            log_value['rtype'] = tags[1]
            log_value['name'] = tags[2]
            log_value['rid'] = str(tags[4])
            log_value['measured_at'] = log_dt.replace('T', ' ')
            if query_key == 'bool':
                log_value['type'] = query_key
                log_value['value'] = str(bool(values['LAST'])) if values['LAST'] is not None else None
            else:
                log_value['type'] = type(values['LAST']).__name__
                if log_value['type'] == "int":
                    log_value['value'] = str(int(values['LAST'])) if values['LAST'] is not None else values['LAST']
                elif log_value['type'] == "float":
                    log_value['value'] = str(round(float(values['LAST']), 4)) if values['LAST'] is not None else values['LAST']
            log_value['info'] = { **values}
            if log_value['info']['CHANGE_TIME'] != None:
                log_value['info']['CHANGE_TIME'] = values['CHANGE_TIME'].isoformat().replace('T', ' ').replace('+09:00', '')
            
            log_value['info'] = json.dumps({ **log_value['info']})
            if log_value['value'] is not None:
                bulk_create_queries.append(
                    log_value
                )
            else:
                client_logger.error(f"[{log_dt}] FUNC=REDIS_MAPPING_LOGGER_15min 에러발생 ({log_value})")
    log_read_query = SQLBuilder(table_name='jais_log_read_time', instance=db_instance).bulk_create(
        bulk_create_queries
    ).execute_many()
    end_time = datetime.now()  # 실행 완료 시간 기록
    duration = (end_time - start_time).total_seconds()
    client_logger.info(f"[{log_dt}] FUNC=REDIS_MAPPING_LOGGER_15min 작업 완료 (실행 시간: {duration}초)")


@log_exceptions(client_logger)
def REDIS_MAPPING_LOGGER_1h(*args, **kwargs):
    """
    기본 통계값

    MIN / MAX: 최소/최대값
    AVG: 평균
    SUM: 합계
    COUNT: 데이터 개수
    FIRST / LAST: 해당 기간의 첫 번째/마지막 값
    변동성 분석

    STDDEV / VARIANCE: 표준편차, 분산
    RANGE / SPREAD: 데이터의 변동폭
    추세 분석

    DIFFERENCE / DERIVATIVE / NONNEGATIVE_DERIVATIVE: 변화량, 변화율
    SKEW: 왜도(데이터의 비대칭성)
    이벤트 감지

    CHANGE_TIME: 마지막으로 값이 변한 시간
    HISTOGRAM: 값의 분포
    
    (3) 1시간 간격
    Number: 패턴 변화 확인 (SKEW, VARIANCE)
    Boolean: 일정 기간 동안의 ON/OFF 비율 분석 (RUN_TIME, DOWN_TIME)
    """
    minute = 60
    delay = 65
    start_time = datetime.now()
    log_format = {
        'rtype': None, 
        'rid': None, 
        'name': None, 
        'measured_at': None, 
        'type': None, 
        'value': None, 
        'info': None, 
    }
    bulk_create_queries = []
    aggregate = {}

    end = datetime.now() - timedelta(seconds=delay) 
    start = end - timedelta(minutes=minute)  # 최근 5분 데이터
    aggregate['number'] = ['MIN', 'MAX', 'AVG', 'SUM', 'FIRST', 'MEDIAN', 'LAST', 'DIFFERENCE_SUM', 'SKEW', 'HISTOGRAM', 'VARIANCE', 'RANGE', 'DERIVATIVE', 'SPREAD', 'CHANGE_TIME']
    aggregate['bool'] = ['FIRST', 'LAST', 'RUN_TIME', 'DOWN_TIME', 'CHANGE_TIME']
    
    log_keys = redis_instance.query_scan('log:*')
    for query_key in ['number', 'bool']:
        result, log_dt = redis_instance.custom_aggregate(log_keys, query_key=query_key, minute=minute, delay=delay, aggregate_type=aggregate[query_key])
        for tag, values in result.items():
            tags = tag.split(':')
            log_value = log_format.copy()
            log_value['rtype'] = tags[1]
            log_value['name'] = tags[2]
            log_value['rid'] = str(tags[4])
            log_value['measured_at'] = log_dt.replace('T', ' ')
            if query_key == 'bool':
                log_value['type'] = query_key
                log_value['value'] = str(bool(values['LAST'])) if values['LAST'] is not None else None
            else:
                log_value['type'] = type(values['LAST']).__name__
                if log_value['type'] == "int":
                    log_value['value'] = str(int(values['LAST'])) if values['LAST'] is not None else values['LAST']
                elif log_value['type'] == "float":
                    log_value['value'] = str(round(float(values['LAST']), 4)) if values['LAST'] is not None else values['LAST']
            log_value['info'] = { **values}
            if log_value['info']['CHANGE_TIME'] != None:
                log_value['info']['CHANGE_TIME'] = values['CHANGE_TIME'].isoformat().replace('T', ' ').replace('+09:00', '')
            
            log_value['info'] = json.dumps({ **log_value['info']})
            if log_value['value'] is not None:
                bulk_create_queries.append(
                    log_value
                )
            else:
                client_logger.error(f"[{log_dt}] FUNC=REDIS_MAPPING_LOGGER_1hour 에러발생 ({log_value})")
    log_read_query = SQLBuilder(table_name='jais_log_read_hour', instance=db_instance).bulk_create(
        bulk_create_queries
    ).execute_many()
    end_time = datetime.now()  # 실행 완료 시간 기록
    duration = (end_time - start_time).total_seconds()
    client_logger.info(f"[{end_time}] FUNC=REDIS_MAPPING_LOGGER_1hour 작업 완료 (실행 시간: {duration}초)")


@log_exceptions(client_logger)
def REDIS_MAPPING_LOGGER_1d(*args, **kwargs):
    """
    기본 통계값

    MIN / MAX: 최소/최대값
    AVG: 평균
    SUM: 합계
    COUNT: 데이터 개수
    FIRST / LAST: 해당 기간의 첫 번째/마지막 값
    변동성 분석

    STDDEV / VARIANCE: 표준편차, 분산
    RANGE / SPREAD: 데이터의 변동폭
    추세 분석

    DIFFERENCE / DERIVATIVE / NONNEGATIVE_DERIVATIVE: 변화량, 변화율
    SKEW: 왜도(데이터의 비대칭성)
    이벤트 감지

    CHANGE_TIME: 마지막으로 값이 변한 시간
    HISTOGRAM: 값의 분포
    
    (4) 1일 간격
    Number: 하루 동안의 평균 사용량 및 변동성 확인 (AVG, STDDEV)
    Boolean: 하루 동안 기기가 얼마나 가동되었는지 분석 (RUN_TIME, DOWN_TIME)
    """
    minute = 60*24
    delay = 75
    start_time = datetime.now()
    log_format = {
        'rtype': None, 
        'rid': None, 
        'name': None, 
        'measured_at': None, 
        'type': None, 
        'value': None, 
        'info': None, 
    }
    bulk_create_queries = []
    aggregate = {}

    end = datetime.now() - timedelta(seconds=delay) 
    start = end - timedelta(minutes=minute)
    aggregate['number'] = ['MIN', 'MAX', 'AVG', 'SUM', 'COUNT', 'MEDIAN', 'STDDEV', 'VARIANCE', 'HISTOGRAM', 'SKEW', 'RUN_TIME', 'DOWN_TIME']
    aggregate['bool'] = ['FIRST', 'LAST', 'RUN_TIME', 'DOWN_TIME', 'CHANGE_TIME']
    log_keys = redis_instance.query_scan('log:*')
    for query_key in ['number', 'bool']:
        result, log_dt = redis_instance.custom_aggregate(log_keys, query_key=query_key, minute=minute, delay=delay, aggregate_type=aggregate[query_key])
        for tag, values in result.items():
            tags = tag.split(':')
            log_value = log_format.copy()
            log_value['rtype'] = tags[1]
            log_value['name'] = tags[2]
            log_value['rid'] = str(tags[4])
            log_value['measured_at'] = log_dt.replace('T', ' ')
            if query_key == 'bool':
                log_value['type'] = query_key
                log_value['value'] = str(bool(values['LAST'])) if values['LAST'] is not None else None
            else:
                log_value['type'] = type(values['LAST']).__name__
                if log_value['type'] == "int":
                    log_value['value'] = str(int(values['LAST'])) if values['LAST'] is not None else values['LAST']
                elif log_value['type'] == "float":
                    log_value['value'] = str(round(float(values['LAST']), 4)) if values['LAST'] is not None else values['LAST']
            log_value['info'] = { **values}
            if log_value['info']['CHANGE_TIME'] != None:
                log_value['info']['CHANGE_TIME'] = values['CHANGE_TIME'].isoformat().replace('T', ' ').replace('+09:00', '')
            
            log_value['info'] = json.dumps({ **log_value['info']})
            if log_value['value'] is not None:
                bulk_create_queries.append(
                    log_value
                )
            else:
                client_logger.error(f"[{log_dt}] FUNC=REDIS_MAPPING_LOGGER_day 에러발생 ({log_value})")
    log_read_query = SQLBuilder(table_name='jais_log_read_day', instance=db_instance).bulk_create(
        bulk_create_queries
    ).execute_many()
    end_time = datetime.now()  # 실행 완료 시간 기록
    duration = (end_time - start_time).total_seconds()
    client_logger.info(f"[{end_time}] FUNC=REDIS_MAPPING_LOGGER_1hour 작업 완료 (실행 시간: {duration}초)")


# #===============================================================================================================
# #============================     LISTENER     =================================================================
# #===============================================================================================================

@log_exceptions(client_logger)
def LS_XGT_TCP_TO_REDIS(result, *args, **kwargs):
    global LS_XGT_TCP_CLIENT, VAR_ITEMS
    alert_data = {}
    start_time = datetime.now()
    # 채널 파라미터와 JSON 데이터 로드
    ch_params = kwargs
    channel_id = ch_params['channel_id']
    channel_json_data_key = f"Channel:{channel_id}"
    channel_json_data = RegistersSlaveContext(createMemory='LS_XGT_TCP').store
    # 응답 데이터를 사용해 채널 JSON 데이터 업데이트
    responses = result
    response_params_list = args
    channel_datetime = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
    timestamp_ms = int(datetime.now().timestamp() * 1000)
    for response, res_params in zip(responses, response_params_list):
        identifier = res_params[ch_params['identifier']]
        address = int(res_params['address'])
        count = int(res_params['count'])
        data_access_key = ch_params['data_Access'][0]
        channel_json_data[identifier][address:address + count] = getattr(response, data_access_key)
    # 🔥 밀리초(ms) 단위 타임스탬프 변환
    pipeline = redis_instance.client.pipeline()
    for category, tags in VAR_ITEMS[str(kwargs['channel_id'])].items():
        for key, value in tags.items():
            identifier, address, scale, _min, _max, status_able, log_able, write_able, alert_able, cat_name, name = value
            # 채널의 식별자와 매핑된 식별자 비교
            if ch_params['identifier'] == 'memory':
                lmt = LSIS_MappingTool(*value)
                json_data = channel_json_data[lmt.address]
                log_value = lmt.repack(json_data)
                #REDIS TIMESERIES에서는 부울값을 저장 못함
                if type(log_value).__name__ == 'float':
                    log_value= float("{:.3f}".format(round(log_value, 3)))
                if key.split(':')[0] == 'alert' or key.split(':')[0] == 'write' or key.split(':')[0] == 'status':
                    #과거 값 조회시 변경된 것을 확인하면 DB 업로드
                    if redis_instance.timeseries_exists(key):
                        if len(redis_instance.get_latest_timeseries(key)):
                            get_timestamp, get_data = redis_instance.get_latest_timeseries(key)
                            if key.split(':')[3] == 'number':
                                if float(log_value) != float(get_data):
                                    pipeline.execute_command("TS.ADD", key, timestamp_ms, 1 if log_value == True else 0 if log_value == False else log_value)
                            if key.split(':')[3] == 'bool':
                                if int(log_value) != int(get_data):
                                    pipeline.execute_command("TS.ADD", key, timestamp_ms, 1 if log_value == True else 0 if log_value == False else log_value)
                    else: 
                        pipeline.execute_command("TS.ADD", key, timestamp_ms, 1 if log_value == True else 0 if log_value == False else log_value)
                else:
                    pipeline.execute_command("TS.ADD", key, timestamp_ms, 1 if log_value == True else 0 if log_value == False else log_value)
                    
    pipeline.execute()

    # LSIS-XGT WRITE
    now = datetime.now()
    now_str = now.strftime('%Y-%m-%d %H:%M:%S.%f')  # 문자열 변환
    # 5분 전
    five_minute_ago = now - timedelta(minutes=5)
    five_minute_ago_str = five_minute_ago.strftime('%Y-%m-%d %H:%M:%S.%f')  # 문자열 변환

    write_bit = {
        'off_delay_timer': {'id': [], 'arrays': []},
        'set': {'id': [], 'arrays': []},
        'reset': {'arrays': []}
    }

    write_byte = {
        'set': {'id': [], 'arrays': []}
    }

    write_word = {
        'set': {'id': [], 'arrays': []}
    }

    write_dword = {
        'set': {'id': [], 'arrays': []}
    }
    # # 데이터베이스 조회
    
    controlList_query = SQLBuilder(table_name="module_control", instance=db_instance)
    controlList_query.filter(Channel_id=kwargs['channel_id'], control_st__range=[five_minute_ago_str, now_str],
                                         status="standby")
    controlList = controlList_query.execute()
    query = SQLBuilder(table_name="module_Control", instance=db_instance).EXISTS(
        {"Channel_id": kwargs['channel_id'], "control_st__lt": five_minute_ago_str, "status":"standby" }).execute()
    for _, exist_val in query[0].items():
        if exist_val:
            # 5분 후 제어 안된것은 놓친것으로 처리
            missed_query = SQLBuilder(table_name="module_control", instance=db_instance).UPDATE(
                    data={"status": "Missed"},
                    where={"Channel_id": kwargs['channel_id'], "control_st__lt": five_minute_ago_str, "status":"standby" }
                )
            missed_query.execute()

    bulk_update_list = []
    if len(controlList) > 0:
        for client in args:
            # 각 클라이언트에 대해 함수 호출 및 결과 저장
            client_index = args.index(client)
            func_name = client['func_name']
            memory_address = client['memory'] + client['address']
            count = client['count']
            if controlList != []:
                for row in controlList:
                    row = dict_to_object(row)
                    ctrl_data = json.loads(row.control_data)
                    ctrl_data.update({'controlitem': VAR_ITEMS[str(row.Channel_id)]['write'][f"write:{row.rtype}:{row.name}:{row.type}:{row.rid}"]})
                    ctrl_method = ctrl_data['control_method']
                    lmt = LSIS_MappingTool(*ctrl_data['controlitem'])
                    is_between = int(client['address'][0]) <= lmt.position[0] <= int(client['address'][0]) + int(count)
                    if is_between:
                        write_data = lmt.repack_write(row.value)
                        if ctrl_data['controlitem'][0] == 'bit' and len(write_bit[ctrl_method]['id']) < 9:
                            if ctrl_method == "off_delay_timer":
                                write_bit[ctrl_method]['arrays'].append(lmt.repack_write(1))
                                write_bit['reset']['arrays'].append(lmt.repack_write(0))
                            elif ctrl_method == "set":
                                write_bit[ctrl_method]['arrays'].append(write_data)
                            write_bit[ctrl_method]['id'].append(row.id)
                        elif write_data['format'] == 'B' and  len(write_byte[ctrl_method]['id']) < 9:
                            write_byte[ctrl_method]['arrays'].append(write_data)
                            write_byte[ctrl_method]['id'].append(row.id)
                        elif write_data['format'] == 'H' and len(write_word[ctrl_method]['id']) < 9:
                            write_word[ctrl_method]['arrays'].append(write_data)
                            write_word[ctrl_method]['id'].append(row.id)
                        elif write_data['format'] == 'I' and len(write_dword[ctrl_method]['id']) < 9:
                            write_dword[ctrl_method]['arrays'].append(write_data)
                            write_dword[ctrl_method]['id'].append(row.id)
            if write_dword['set']['id'] != []:
                response = getattr(LS_XGT_TCP_CLIENT[str(kwargs['channel_id'])][client_index], "single_write_datas")("dword", str(len(write_dword['set']['arrays'])), write_dword['set']['arrays'])
                try:
                    if hasattr(response, 'detailedStatus'):
                        for id in write_dword['set']['id']:
                            bulk_update_list.append({
                                "id": id,
                                "status": "executed",
                                "response": json.dumps(response.detailedStatus, ensure_ascii=False),
                            })
                    else:
                        for id in write_dword['set']['id']:
                            bulk_update_list.append({
                                "id": id,
                                "status": "failed",
                                "response": json.dumps(response.message, ensure_ascii=False),
                            })
                except Exception as err:
                    client_logger.error("control_query, error", err)
            if write_word['set']['id'] != []:
                response = getattr(LS_XGT_TCP_CLIENT[str(kwargs['channel_id'])][client_index], "single_write_datas")("word", str(len(write_word['set']['arrays'])), write_word['set']['arrays'])
                try:
                    if hasattr(response, 'detailedStatus'):
                        for id in write_word['set']['id']:
                            bulk_update_list.append({
                                "id": id,
                                "status": "executed",
                                "response": json.dumps(response.detailedStatus, ensure_ascii=False),
                            })
                    else:
                        for id in write_word['set']['id']:
                            bulk_update_list.append({
                                "id": id,
                                "status": "failed",
                                "response": json.dumps(response.message, ensure_ascii=False),
                            })
                except Exception as err:
                    client_logger.error("control_query, error", err)
            if write_byte['set']['id'] != []:
                response = getattr(LS_XGT_TCP_CLIENT[str(kwargs['channel_id'])][client_index], "single_write_datas")("byte", str(len(write_byte['set']['arrays'])), write_byte['set']['arrays'])
                try:
                    if hasattr(response, 'detailedStatus'):
                        for id in write_byte['set']['id']:
                            bulk_update_list.append({
                                "id": id,
                                "status": "executed",
                                "response": json.dumps(response.detailedStatus, ensure_ascii=False),
                            })
                    else:
                        for id in write_byte['set']['id']:
                            bulk_update_list.append({
                                "id": id,
                                "status": "failed",
                                "response": json.dumps(response.message, ensure_ascii=False),
                            })
                except Exception as err:
                    client_logger.error("control_query, error", err)
            if write_bit['set']['id'] != []:
                response = getattr(LS_XGT_TCP_CLIENT[str(kwargs['channel_id'])][client_index], "single_write_datas")("bit", str(len(write_bit['set']['arrays'])), write_bit['set']['arrays'])
                try:
                    if hasattr(response, 'detailedStatus'):
                        for id in write_bit['set']['id']:
                            bulk_update_list.append({
                                "id": id,
                                "status": "executed",
                                "response": json.dumps(response.detailedStatus, ensure_ascii=False),
                            })
                    else:
                        for id in write_bit['set']['id']:
                            bulk_update_list.append({
                                "id": id,
                                "status": "failed",
                                "response": json.dumps(response.message, ensure_ascii=False),
                            })
                except Exception as err:
                    client_logger.error("control_query, error", err)
            if write_bit['off_delay_timer']['id'] != []:
                response = getattr(LS_XGT_TCP_CLIENT[str(kwargs['channel_id'])][client_index], "single_write_datas")("bit", str(len(write_bit['off_delay_timer']['arrays'])),write_bit['off_delay_timer']['arrays'])
                time.sleep(3)
                response = getattr(LS_XGT_TCP_CLIENT[str(kwargs['channel_id'])][client_index], "single_write_datas")("bit", str(len(write_bit['reset']['arrays'])),write_bit['reset']['arrays'])
                try:
                    if hasattr(response, 'detailedStatus'):
                        for id in write_bit['off_delay_timer']['id']:
                            bulk_update_list.append({
                                "id": id,
                                "status": "executed",
                                "response": json.dumps(response.detailedStatus, ensure_ascii=False),
                            })
                    else:
                        for id in write_bit['off_delay_timer']['id']:
                            bulk_update_list.append({
                                "id": id,
                                "status": "failed",
                                "response": json.dumps(response.message, ensure_ascii=False),
                            })
                except Exception as err:
                    client_logger.error("control_query, error", err)
    if len(bulk_update_list)> 0:
        query = SQLBuilder(table_name="module_Control", instance=db_instance).bulk_update(bulk_update_list, "id")
        query.execute_many()
        

    end_time = datetime.now()  # 실행 완료 시간 기록
    duration = (end_time - start_time).total_seconds()
    if duration > 5:
        client_logger.info(f"[{end_time}] FUNC=LS_XGT_TCP_TO_REDIS 작업 완료 (실행 시간: {duration}초)")

def HTTP_REDIS(result, *args, **kwargs):
    global VAR_ITEMS
    now = datetime.now()
    start_time = datetime.now()
    alert_data = {}

    # 이벤트 반환값에서 파라미터 추출
    params = kwargs

    # 반환값이 문자열인 경우 처리 생략
    if isinstance(result, str):
        return
    key_value = {}
    pipeline = redis_instance.client.pipeline()

    # 데이터 처리 및 키-값 매핑
    for data in result:
        for row in data:
            identifier = row[params['identifier']]
            nested_data = reduce(lambda d, key: d.get(key, {}), params['data_Access'], row)
            nested_data['measured_at'] = row[params['measured_at']]
            key_value[identifier] = nested_data
    # 🔥 밀리초(ms) 단위 타임스탬프 변환
    for category, tags in VAR_ITEMS[str(kwargs['channel_id'])].items():
        for key, value in tags.items():
            identifier, address, scale, _min, _max, status_able, log_able, write_able, alert_able, cat_name, name = value
            # 채널의 식별자와 매핑된 식별자 비교
            if identifier == 'serial':
                log_value = key_value[address][name]
                channel_datetime =  key_value[address]['measured_at'].replace('T', ' ')
                measured_at = datetime.strptime(key_value[address]['measured_at'], "%Y-%m-%dT%H:%M:%S.%f")
                timestamp_ms = int(measured_at.timestamp() * 1000)
                #REDIS TIMESERIES에서는 부울값을 저장 못함
                if type(log_value).__name__ == 'float':
                    log_value= float("{:.3f}".format(round(log_value, 3)))
                if key.split(':')[0] == 'alert' or key.split(':')[0] == 'write' or key.split(':')[0] == 'status':
                    #과거 값 조회시 변경된 것을 확인하면 DB 업로드
                    if redis_instance.timeseries_exists(key):
                        if redis_instance.get_latest_timeseries(key) != []:
                            get_timestamp, get_data = redis_instance.get_latest_timeseries(key)
                            if key.split(':')[3] == 'number':
                                if float(log_value) != float(get_data):
                                    pipeline.execute_command("TS.ADD", key, timestamp_ms, 1 if log_value == True else 0 if log_value == False else log_value)
                            if key.split(':')[3] == 'bool':
                                if int(log_value) != int(get_data):
                                    pipeline.execute_command("TS.ADD", key, timestamp_ms, 1 if log_value == True else 0 if log_value == False else log_value)
                    else: 
                        pipeline.execute_command("TS.ADD", key, timestamp_ms, 1 if log_value == True else 0 if log_value == False else log_value)
                else:
                    pipeline.execute_command("TS.ADD", key, timestamp_ms, 1 if log_value == True else 0 if log_value == False else log_value)
                    
    pipeline.execute()
    try:
        redis_instance.bulk_set(alert_data)
    except TypeError as err:
        client_logger.error(alert_data, err)
    end_time = datetime.now()  # 실행 완료 시간 기록
    duration = (end_time - start_time).total_seconds()
    if duration > 5:
        client_logger.info(f"[{end_time}] FUNC=HTTP_REDIS 작업 완료 (실행 시간: {duration}초)")


@log_exceptions(client_logger)
def LS_XGT_TCP_TO_REDIS_CHANNEL(result, *args, **kwargs):
    # 채널 파라미터와 JSON 데이터 로드
    ch_params = kwargs
    channel_id = ch_params['channel_id']
    channel_json_data_key = f"Channel:{channel_id}"
    try:
        # channel_json_data_key가 Redis에 존재하는지 확인
        if not redis_instance.hexists(channel_json_data_key, "jsonData"):
            channel_json_data = RegistersSlaveContext(createMemory='LS_XGT_TCP').store
        else:
            channel_json_data = json.loads(redis_instance.hget(channel_json_data_key, "jsonData"))

        # 응답 데이터를 사용해 채널 JSON 데이터 업데이트
        responses = result
        response_params_list = args

        for response, res_params in zip(responses, response_params_list):
            identifier = res_params[ch_params['identifier']]
            address = int(res_params['address'])
            count = int(res_params['count'])
            data_access_key = ch_params['data_Access'][0]
            channel_json_data[identifier][address:address + count] = getattr(response, data_access_key)
            
        # 업데이트된 JSON 데이터를 Redis에 저장
        redis_instance.hmset(channel_json_data_key, 
            {
                "jsonData": json.dumps(channel_json_data),
                "timestamp": int(datetime.now().timestamp() * 1000),
                "datetime": datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f'),
            }
        )
    except AttributeError as err:
        client_logger.error(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [ERROR] FUNC=LS_XGT_TCP_TO_REDIS_CHANNEL Channel:{channel_id} 에러발생 ({err})")

@log_exceptions(client_logger)
def DATABASE_CHANNEL(result, *args, **kwargs):
    # 이벤트 반환값에서 파라미터 추출
    params = kwargs

    # 반환값이 문자열인 경우 처리 생략
    if isinstance(result, str):
        return

    key_value = {}

    # 데이터 처리 및 키-값 매핑
    for data in result:
        for row in data:
            identifier = row[params['identifier']]
            nested_data = reduce(lambda d, key: d.get(key, {}), params['data_Access'], row)
            nested_data['measured_at'] = row[params['measured_at']]
            key_value[identifier] = nested_data

    # 데이터베이스 업데이트
    channel_query = SQLBuilder(table_name="jais_Channel", instance=db_instance)
    channel_query.UPDATE(data={"jsonData": key_value}, where={"id": params['channel_id']}).execute()

@log_exceptions(client_logger)
def REDIS_CHANNEL(result, *args, **kwargs):
    # 이벤트 반환값에서 파라미터 추출
    params = kwargs

    # 반환값이 문자열인 경우 처리 생략
    if isinstance(result, str):
        return

    key_value = {}

    # 데이터 처리 및 키-값 매핑
    for data in result:
        for row in data:
            identifier = row[params['identifier']]
            nested_data = reduce(lambda d, key: d.get(key, {}), params['data_Access'], row)
            nested_data['measured_at'] = row[params['measured_at']]
            key_value[identifier] = nested_data

    # Redis에 업데이트
    redis_key = f"Channel:{params['channel_id']}"

    # channel_json_data_key가 Redis에 존재하는지 확인

    redis_instance.hset(redis_key, "jsonData", json.dumps(key_value))
    redis_instance.hset(redis_key, "timestamp", int(datetime.strptime(row[params['measured_at']], "%Y-%m-%dT%H:%M:%S.%f").timestamp() * 1000))
    redis_instance.hset(redis_key, "datetime", row[params['measured_at']].replace('T', ' '))