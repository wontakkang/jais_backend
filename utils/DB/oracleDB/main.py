import cx_Oracle
import subprocess
import os

class OracleDatabase:
    def __init__(self, host: str, user: str, password: str, service_name: str, port: int):
        """
        오라클 데이터베이스 연결 초기화.
        """
        self.connection = None
        self.DATABASE_HOST = host
        self.DATABASE_USER = user
        self.DATABASE_PASSWORD = password
        self.DATABASE_SERVICE_NAME = service_name
        self.DATABASE_PORT = port

    def connect(self):
        """
        데이터베이스 연결을 생성합니다.
        """
        if not self.connection or self.connection.closed:
            dsn = cx_Oracle.makedsn(self.DATABASE_HOST, self.DATABASE_PORT, service_name=self.DATABASE_SERVICE_NAME)
            self.connection = cx_Oracle.connect(user=self.DATABASE_USER, password=self.DATABASE_PASSWORD, dsn=dsn)

    def execute_query(self, query: str, params: tuple = ()): 
        """
        SELECT 쿼리 실행.
        사용 예제:
        db.execute_query("SELECT * FROM users WHERE id = :1", (1,))
        """
        self.connect()
        with self.connection.cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchall()

    def execute_update(self, query: str, params: tuple = ()): 
        """
        INSERT/UPDATE/DELETE 쿼리 실행.
        사용 예제:
        db.execute_update("INSERT INTO users (name, age) VALUES (:1, :2)", ("John", 30))
        """
        self.connect()
        with self.connection.cursor() as cursor:
            cursor.execute(query, params)
            self.connection.commit()

    def begin_transaction(self):
        """트랜잭션 시작"""
        self.connect()

    def commit_transaction(self):
        """트랜잭션 커밋"""
        if self.connection:
            self.connection.commit()
    
    def rollback_transaction(self):
        """트랜잭션 롤백"""
        if self.connection:
            self.connection.rollback()

    def close(self):
        """
        데이터베이스 연결을 닫습니다.
        사용 예제:
        db.close()
        """
        if self.connection and self.connection:
            self.connection.close()

    def backup_database(self, backup_file: str):
        """
        오라클 데이터베이스 백업 수행.
        사용 예제:
        db.backup_database("backup.dmp")
        """
        try:
            command = f"expdp {self.DATABASE_USER}/{self.DATABASE_PASSWORD}@{self.DATABASE_HOST}:{self.DATABASE_PORT}/{self.DATABASE_SERVICE_NAME} DUMPFILE={backup_file} FULL=Y"
            subprocess.run(command, shell=True, check=True)
            print(f"백업 완료: {backup_file}")
        except subprocess.CalledProcessError as e:
            print(f"백업 실패: {e}")
    
    def restore_database(self, backup_file: str):
        """
        오라클 데이터베이스 백업 파일을 이용해 복원합니다.
        사용 예제:
        db.restore_database("backup.dmp")
        """
        if not os.path.exists(backup_file) or not os.path.isfile(backup_file):
            print(f"유효하지 않은 백업 파일: {backup_file}")
            return
        
        try:
            command = f"impdp {self.DATABASE_USER}/{self.DATABASE_PASSWORD}@{self.DATABASE_HOST}:{self.DATABASE_PORT}/{self.DATABASE_SERVICE_NAME} DUMPFILE={backup_file} FULL=Y"
            subprocess.run(command, shell=True, check=True)
            print(f"복원 완료: {backup_file}")
        except subprocess.CalledProcessError as e:
            print(f"복원 실패: {e}")
    
    def can_restore_database(self):
        """
        데이터베이스가 복원 가능한 상태인지 확인합니다.
        사용 예제:
        if db.can_restore_database():
            print("데이터베이스 복원이 가능합니다.")
        """
        try:
            self.connect()
            with self.connection.cursor() as cursor:
                cursor.execute("SELECT 1 FROM dual")
                return True
        except cx_Oracle.DatabaseError as e:
            print(f"데이터베이스 상태 확인 실패: {e}")
            return False
