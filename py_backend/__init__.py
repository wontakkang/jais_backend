# PyMySQL을 MySQLdb로 대체 등록 (mysqlclient 미설치 환경 대비)
try:
    import pymysql  # type: ignore
    pymysql.install_as_MySQLdb()
except Exception:
    pass

# ...existing code...