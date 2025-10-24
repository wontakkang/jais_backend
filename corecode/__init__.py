
import os
from py_backend.settings import REDIS_HOST, REDIS_PASSWORD, REDIS_PORT
from utils.DB.redisDB.main import RedisManager
from utils.logger import setup_logger

REDIS_DID = 0
NAME = 'corecode'

logger = setup_logger(
    name=NAME,
    log_file=os.path.join(os.getcwd(), "log", f"{NAME}.log"),
    level="DEBUG",
    backup_days=7,
)
try:
    # REDIS 연결 인스턴스
    redis_instance = RedisManager(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DID, password=REDIS_PASSWORD)
    redis_instance.connect()
    logger.info(f"Redis 연결 성공: {REDIS_HOST}:{REDIS_PORT}, DB: {REDIS_DID}")
except Exception as e:
    logger.error(f"Redis 연결 실패: {e}")
    redis_instance = None
    async_redis_instance = None