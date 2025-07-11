from datetime import datetime
import json
from app.utils import utilities
from app.utils.DB.mariaDB import SQLBuilder
from app.utils.logger import setup_logger
from app.utils.protocol.HTTP import phttp
from app.db import *
from app.utils import ExternalAPI
from app.utils import log_exceptions

restful_logger = setup_logger(name="restful_logger", log_file="./log/restful_logs.log")

@log_exceptions(restful_logger)
def VilageFcstInfoService(*args, **kwargs):
    start_time = datetime.now()
    baseDate = datetime.now().strftime('%Y%m%d')
    baseTime = datetime.now().strftime('0500')
    facility_query = SQLBuilder(table_name="jais_Basic_Facility", instance=db_instance).all().execute()
    for row in facility_query:
        row = utilities.dict_to_object(row)
        nx, ny = ExternalAPI.dfs_xy_conv(row.lat, row.lng)
        res_data = ExternalAPI.VilageFcstInfoService(nx=nx, ny=ny)
        facilityWeatherFcst = SQLBuilder(table_name="jais_STAT_FacilityWeatherFcst", instance=db_instance)
        
        if facilityWeatherFcst.EXISTS({'Basic_Facility_id': row.id}).execute():
            facilityWeatherFcst.params = []
            facilityWeatherFcst.UPDATE(data={'VilageFcst': json.dumps(res_data)}, where={'Basic_Facility_id': row.id}).execute()
        else:
            facilityWeatherFcst.params = []
            facilityWeatherFcst.INSERT(data={'Basic_Facility_id': row.id, 'VilageFcst': json.dumps(res_data)}).execute()
    end_time = datetime.now()  # 실행 완료 시간 기록
    duration = (end_time - start_time).total_seconds()
    restful_logger.info(f"[{start_time}] FUNC=VilageFcstInfoService 작업 완료 (실행 시간: {duration}초)")

@log_exceptions(restful_logger)
def SunriseSunset(*args, **kwargs):
    start_time = datetime.now()
    locdate = datetime.now().strftime('%Y%m%d')
    facility_query = SQLBuilder(table_name="jais_Basic_Facility", instance=db_instance).values('id', 'location').execute()
    for row in facility_query:
        row = utilities.dict_to_object(row)
        res_data = ExternalAPI.SunriseSunset(row.location)
        sunriseSunset = SQLBuilder(table_name="jais_STAT_SunriseSunset", instance=db_instance)
        
        if sunriseSunset.EXISTS({'location': row.location, 'locdate': locdate}).execute():
            sunriseSunset.params = []
            sunriseSunset.UPDATE(data={
                'locdate': locdate, 
                'sunrise': res_data['sunrise'], 
                'suntransit': res_data['suntransit'],
                'sunset': res_data['sunset'],
            }, where={'location': row.location}).execute()
        else:
            sunriseSunset.params = []
            sunriseSunset.INSERT(data={
                'location': row.location,
                'locdate': locdate,
                'sunrise': res_data['sunrise'],
                'suntransit': res_data['suntransit'],
                'res_data': res_data['sunset'],
            }).execute()
    end_time = datetime.now()  # 실행 완료 시간 기록
    duration = (end_time - start_time).total_seconds()
    restful_logger.info(f"[{start_time}] FUNC=SunriseSunset 작업 완료 (실행 시간: {duration}초)")

@log_exceptions(restful_logger)
def getMidTaService(*args, **kwargs):
    start_time = datetime.now()
    facility_query = SQLBuilder(table_name="jais_Basic_Facility", instance=db_instance).all().execute()
    for row in facility_query:
        row = utilities.dict_to_object(row)
        basic_Location = SQLBuilder(table_name="jais_Basic_Location", instance=db_instance)
        weather = SQLBuilder(table_name="jais_Weather", instance=db_instance)
        res_data = ExternalAPI.getMidTaService(basic_Location.get({'name': row.location}).code)
        if weather.EXISTS({'Basic_Facility_id': row.id}).execute():
            weather.params = []
            weather.UPDATE(data={
                'getMidTa': json.dumps(res_data), 
            }, where={'Basic_Facility_id': row.id}).execute()
        else:
            weather.params = []
            weather.INSERT(data={
                'Basic_Facility_id': row.id,
                'Basic_Location': basic_Location.get({'name': row.location}).id,
                'getMidTa': json.dumps(res_data),
            }).execute()

    end_time = datetime.now()  # 실행 완료 시간 기록
    duration = (end_time - start_time).total_seconds()
    restful_logger.info(f"[{start_time}] FUNC=getMidTaService 작업 완료 (실행 시간: {duration}초)")

@log_exceptions(restful_logger)
def MidFcstInfoService(*args, **kwargs):
    start_time = datetime.now()
    start_time = datetime.now()
    facility_query = SQLBuilder(table_name="jais_Basic_Facility", instance=db_instance).all().execute()
    for row in facility_query:
        row = utilities.dict_to_object(row)
        basic_Location = SQLBuilder(table_name="jais_Basic_Location", instance=db_instance)
        weather = SQLBuilder(table_name="jais_Weather", instance=db_instance)
        res_data = ExternalAPI.getMidTaService(basic_Location.get({'name': row.location}).code2)
        if weather.EXISTS({'Basic_Facility_id': row.id}).execute():
            weather.params = []
            weather.UPDATE(data={
                'MidLandFcst': json.dumps(res_data), 
            }, where={'Basic_Facility_id': row.id}).execute()
        else:
            weather.params = []
            weather.INSERT(data={
                'Basic_Facility_id': row.id,
                'Basic_Location': basic_Location.get({'name': row.location}).id,
                'MidLandFcst': json.dumps(res_data),
            }).execute()

    end_time = datetime.now()  # 실행 완료 시간 기록
    duration = (end_time - start_time).total_seconds()
    restful_logger.info(f"[{start_time}] FUNC=MidFcstInfoService 작업 완료 (실행 시간: {duration}초)")
