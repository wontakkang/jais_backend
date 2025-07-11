from app.config import settings  # 설정 정보 가져오기
from app.utils.DB.mariaDB import Database
from app.utils.DB.inFluxDB import Influx_Database
from app.utils.DB.redisDB import RedisManager, AsyncRedisManager

# DB 인스턴스 생성
db_instance = Database(
        host=settings.DATABASE_HOST,
        user=settings.DATABASE_USER,
        password=settings.DATABASE_PASSWORD,
        database=settings.DATABASE_NAME,
        port=settings.DATABASE_PORT
    )

# DB1 인스턴스 생성
db1_instance = Database(
        host=settings.DATABASE1_HOST,
        user=settings.DATABASE1_USER,
        password=settings.DATABASE1_PASSWORD,
        database=settings.DATABASE1_NAME,
        port=settings.DATABASE1_PORT
    )
db2_instance = None
inFlux_instance = None


redis_instance = None
async_redis_instance = None
# # REDIS 연결 인스턴스
# redis_instance = RedisManager(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=settings.REDIS_DID, password=settings.REDIS_PASSWORD)
# # REDIS 연결 인스턴스
# async_redis_instance = AsyncRedisManager(port=settings.REDIS_PORT, db=settings.REDIS_DID, password=settings.REDIS_PASSWORD)

# # DB2 인스턴스 생성
# db2_instance = Database(
#         host=settings.DATABASE2_HOST,
#         user=settings.DATABASE2_USER,
#         password=settings.DATABASE2_PASSWORD,
#         database=settings.DATABASE2_NAME,
#         port=settings.DATABASE2_PORT
#     )

# # InfluxDB 인스턴스 생성
# inFlux_instance = Influx_Database()