import requests, json, xmltodict
from datetime import timedelta
from utils import setup_logger
import ssl
from utils.config import settings
context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)  # Force TLS 1.2
context.set_ciphers('ECDHE-RSA-AES128-GCM-SHA256')  # Example cipher

# from requests.adapters import HTTPAdapter
#  추천 해결 방법: WSL에서 SECLEVEL 낮춰서 requests가 API 서버와 통신 성공하도록 수정
# # OpenSSL 설정 (SECLEVEL 낮추기)
# context = ssl.create_default_context()
# context.set_ciphers("DEFAULT:@SECLEVEL=1")  # 핵심!
# context.minimum_version = ssl.TLSVersion.TLSv1_2

# class SSLAdapter(HTTPAdapter):
#     def init_poolmanager(self, *args, **kwargs):
#         kwargs["ssl_context"] = context
#         return super().init_poolmanager(*args, **kwargs)

# # requests 세션 구성
# session = requests.Session()
# session.mount("https://", SSLAdapter()) 

# SQL 로거 초기화
http_logger = setup_logger(name="http_logger", log_file=f"{settings.LOG_DIR}/http_logger.log")

# GET
class HTTP:
    protocol_code = 4

    def __init__(self, **kwargs):
        if None is not kwargs.get("interval"):
            self.interval = timedelta(seconds=kwargs.get("interval"))
        self.prefix = kwargs.get("prefix", kwargs.get("memoryType"))
        self.header = {"Content-Type": "application/json; chearset=cp949"}

    def GET(self, url=None, headers=None, params=None, **kwargs):
        try:
            res = requests.get(url, headers=headers, params=params, **kwargs)
            if 'application/json' in res.headers['Content-Type']:
                return json.loads(res.text)
            elif 'application/xml' in res.headers['Content-Type'] or 'text/xml' in res.headers['Content-Type']:
                return json.loads(json.dumps(xmltodict.parse(res.text), indent=4))
            else:
                return json.loads(res.text)
        except Exception as err:
            http_logger.error(f"Exception HTTP ::--GET-- : {err.__dict__, type(err)}")
            return err

    def PUT(self, url=None, headers=None, data=None, **kwargs):
        try:
            res = requests.put(
                url, headers=self.header, data=json.dumps(data), **kwargs
            )
            http_logger.info(f"HTTP --PUT--{data}")
            return json.loads(res.text)
        except Exception as err:
            http_logger.error(f"HTTP --PUT--{err.__dict__, type(err)}")
            return err

    # # POST (JSON)
    def POST(self, url=None, headers=None, data=None, **kwargs):
        try:
            res = requests.post(
                url, headers=self.header, data=json.dumps(data), **kwargs
            )
            http_logger.info(f"HTTP --POST--{data}")
            return json.loads(res.text)
        except Exception as err:
            http_logger.error(f"HTTP --POST--{err.__dict__, type(err)}")
            return err

phttp= HTTP()