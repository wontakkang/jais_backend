from utils import utilities, setup_logger, log_exceptions
from .utilities import dfs_xy_conv
from ..protocol.HTTP import phttp
from utils.config import settings
from datetime import datetime
import inspect


externalAPI_logger = setup_logger(name="externalAPI_logger", log_file=f"{settings.LOG_DIR}/externalAPI_logger.log")

class Defaults:
    serviceKey = settings.DATA_GO_KR_TOKEN
    service = {}
    nx = 0
    ny = 0
    lat = 0
    lng = 0
    def addService(self, servicename, url=None, params={}):
        self.service[servicename] = {
            'url': url,
            'params': params,
        }

data_go_kr_setting = Defaults()
data_go_kr_setting.lat, data_go_kr_setting.lng = (settings.LAT, settings.LNG)
data_go_kr_setting.nx, data_go_kr_setting.ny = dfs_xy_conv(settings.LAT, settings.LNG)

data_go_kr_setting.addService('GetLocation', url='https://dapi.kakao.com/v2/local/search/address.json',
                    params=
                    {
                        'query': ''
                    }
                )
data_go_kr_setting.addService('StanReginCd_Service', url='https://apis.data.go.kr/1741000/StanReginCd/getStanReginCdList',
                    params=
                    {
                        'serviceKey': data_go_kr_setting.serviceKey,
                        'pageNo': '1',
                        'numOfRows': '3',
                        'type': 'json',
                        'locatadd_nm': '제주특별자치도 제주시 도남동',
                    }
                )
data_go_kr_setting.addService('SunriseSunset', url='http://apis.data.go.kr/B090041/openapi/service/RiseSetInfoService/getAreaRiseSetInfo',
                    params=
                    {
                        'serviceKey': data_go_kr_setting.serviceKey,

                    }
                )
data_go_kr_setting.addService('MidFcstInfoService', url='https://apis.data.go.kr/1360000/MidFcstInfoService/getMidLandFcst',
                    params=
                    {
                        'serviceKey': data_go_kr_setting.serviceKey,
                        'pageNo': '1',
                        'numOfRows': '10',
                        'dataType': 'JSON',
                    }
                )
data_go_kr_setting.addService('getMidTaService', url='http://apis.data.go.kr/1360000/MidFcstInfoService/getMidTa',
                    params=
                    {
                        'serviceKey': data_go_kr_setting.serviceKey,
                        'pageNo': '1',
                        'numOfRows': '10',
                        'dataType': 'JSON',
                    }
                )
data_go_kr_setting.addService('VilageFcstInfoService', url='https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst',
                    params=
                    {
                        'serviceKey': data_go_kr_setting.serviceKey,
                        'pageNo': '1',
                        'numOfRows': '1000',
                        'dataType': 'JSON',
                    }
                )

@log_exceptions(externalAPI_logger)
def VilageFcstInfoService(baseDateTime=datetime.now(), *args, **kwargs):
    function_name = inspect.currentframe().f_code.co_name
    baseDate = baseDateTime.strftime('%Y%m%d')
    baseTime = baseDateTime.strftime('0500')
    params = data_go_kr_setting.service[function_name]
    params['params'].update(base_date=baseDate, base_time=baseTime, nx=kwargs.get('nx'), ny=kwargs.get('ny'))
    response = phttp.GET(**params)
    try:
        return response["response"]["body"]["items"]["item"]
    except KeyError as err:
        externalAPI_logger.error('VilageFcstInfoService :: KeyError', err, ' params : ', params, response)

def SunriseSunset(location, baseDate=None, *args, **kwargs):
    function_name = inspect.currentframe().f_code.co_name
    if not baseDate:
        locdate = datetime.now().strftime('%Y%m%d')
    else:
        locdate = baseDate
    params = data_go_kr_setting.service[function_name]
    params['params'].update(locdate=locdate, location=location)
    response = phttp.GET(**params)
    try:
        return response["response"]["body"]["items"]["item"]
    except KeyError as err:
        externalAPI_logger.error('SunriseSunset :: KeyError', err, ' params : ', params, response)

def getMidTaService(regId, *args, **kwargs):
    function_name = inspect.currentframe().f_code.co_name
    baseDateTime = datetime.now().strftime('%Y%m%d0600')
    params = data_go_kr_setting.service[function_name]
    params['params'].update(tmFc=baseDateTime, regId=regId)
    response = phttp.GET(**params)
    return response["response"]["body"]["items"]["item"]

def MidFcstInfoService(regId, *args, **kwargs):
    function_name = inspect.currentframe().f_code.co_name
    baseDateTime = datetime.now().strftime('%Y%m%d0600')
    params = data_go_kr_setting.service[function_name]
    params['params'].update(tmFc=baseDateTime, regId=regId)
    response = phttp.GET(**params)
    return response["response"]["body"]["items"]["item"]
