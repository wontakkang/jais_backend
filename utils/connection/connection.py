
try:
    from utils.DB.redisDB.main import AsyncRedisManager, RedisManager
    from utils.config import settings  # 설정 정보 가져오기
    from utils.DB.mariaDB import Database
    # DB 인스턴스 생성
    db_instance = Database(
            host=settings.DATABASE_HOST,
            user=settings.DATABASE_USER,
            password=settings.DATABASE_PASSWORD,
            database=settings.DATABASE_NAME,
            port=int(settings.DATABASE_PORT)
        )

    # DB1 인스턴스 생성
    db1_instance = Database(
            host=settings.DATABASE1_HOST,
            user=settings.DATABASE1_USER,
            password=settings.DATABASE1_PASSWORD,
            database=settings.DATABASE1_NAME,
            port=settings.DATABASE1_PORT
        )

    # REDIS 연결 인스턴스
    redis_instance = RedisManager(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=settings.REDIS_DID, password=settings.REDIS_PASSWORD)
    # REDIS 연결 인스턴스
    async_redis_instance = AsyncRedisManager(port=settings.REDIS_PORT, db=settings.REDIS_DID, password=settings.REDIS_PASSWORD)
except ImportError:
    pass