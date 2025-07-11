from collections import namedtuple
import pymysql
import subprocess
import os
from dbutils.pooled_db import PooledDB

class Database:
    def __init__(self, host: str, user: str, password: str, database: str, port: int, pool_size: int = 5):
        """
        데이터베이스 커넥션 풀을 초기화합니다.
        """
        self.connection = None
        self.DATABASE_HOST = host
        self.DATABASE_USER = user
        self.DATABASE_PASSWORD = password
        self.DATABASE_NAME = database
        self.DATABASE_PORT = port

        # PooledDB 생성
        self.pool = PooledDB(
            creator=pymysql,
            maxconnections=pool_size,  # 최대 커넥션 개수
            mincached=2,  # 최소한으로 유지할 유휴 커넥션 개수
            maxcached=pool_size,  # 최대 유휴 커넥션 개수
            blocking=True,  # 커넥션이 없을 경우 대기 여부
            host=self.DATABASE_HOST,
            user=self.DATABASE_USER,
            password=self.DATABASE_PASSWORD,
            database=self.DATABASE_NAME,
            port=self.DATABASE_PORT,
            cursorclass=pymysql.cursors.DictCursor,
        )

    def get_connection(self):
        """커넥션 풀에서 새로운 커넥션을 가져옴"""
        return self.pool.connection()
        
    def execute_query(self, query: str, params: tuple = ()): 
        """
        SELECT 쿼리 실행.
        사용 예제:
        db.execute_query("SELECT * FROM users WHERE id = %s", (1,))
        """
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, params)
                # SELECT 문이면 결과 반환
                if query.strip().upper().startswith("SELECT"):
                    return cursor.fetchall()
                
            # SELECT가 아니면 변경 사항을 커밋
            conn.commit()

    def execute_many(self, query: str, params: list = []): 
        """
        여러 개의 INSERT/UPDATE/DELETE 쿼리를 한 번에 실행합니다.
        사용 예제:
        db.execute_many("INSERT INTO users (name, age) VALUES (%s, %s)", [("John", 30), ("Jane", 25)])
        """

        if not params:
            raise ValueError("params 리스트가 비어 있습니다.")

        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.executemany(query, params)
                conn.commit()
        except pymysql.MySQLError as e:
            print(f"오류 발생: {e}")
            if conn.open:  # ✅ 연결이 열려 있는 경우에만 롤백 실행
                conn.rollback()
                
    def execute_update(self, query: str, params: tuple = ()): 
        """
        INSERT/UPDATE/DELETE 쿼리 실행.
        사용 예제:
        db.execute_update("INSERT INTO users (name, age) VALUES (%s, %s)", ("John", 30))
        """
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, params)
        conn.commit()


    def fetch_one(self, query: str, params: tuple = ()): 
        """
        단일 레코드를 반환하는 SELECT 쿼리 실행.
        사용 예제:
        db.fetch_one("SELECT * FROM users WHERE id = %s", (1,))
        """
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, params)
                return cursor.fetchone()
        
    def is_connected(self):
        """연결 상태 확인"""
        return self.connection is not None and self.connection.open

    def begin_transaction(self):
        """트랜잭션 시작"""
        conn = self.get_connection()
        conn.begin()
        return conn

    def commit_transaction(self, conn):
        """트랜잭션 커밋"""
        conn.commit()
        conn.close()

    def rollback_transaction(self, conn):
        """트랜잭션 롤백"""
        conn.rollback()
        conn.close()

    def backup_database(self, backup_file: str):
        """
        데이터베이스 백업을 수행합니다.
        사용 예제:
        db.backup_database("backup.sql")
        """
        try:
            command = f"mysqldump -h {self.DATABASE_HOST} -P {self.DATABASE_PORT} -u {self.DATABASE_USER} -p{self.DATABASE_PASSWORD} {self.DATABASE_NAME} > {backup_file}"
            subprocess.run(command, shell=True, check=True)
            print(f"백업 완료: {backup_file}")
        except subprocess.CalledProcessError as e:
            print(f"백업 실패: {e}")
    
    def restore_database(self, backup_file: str):
        """
        데이터베이스를 백업 파일을 이용해 복원합니다.
        사용 예제:
        db.restore_database("backup.sql")
        """
        if not self.is_valid_backup_file(backup_file):
            print(f"유효하지 않은 백업 파일: {backup_file}")
            return
        
        if not self.can_restore_database():
            print("데이터베이스 복원이 불가능한 상태입니다.")
            return
        
        try:
            command = f"mysql -h {self.DATABASE_HOST} -P {self.DATABASE_PORT} -u {self.DATABASE_USER} -p{self.DATABASE_PASSWORD} {self.DATABASE_NAME} < {backup_file}"
            subprocess.run(command, shell=True, check=True)
            print(f"복원 완료: {backup_file}")
        except subprocess.CalledProcessError as e:
            print(f"복원 실패: {e}")
    
    def is_valid_backup_file(self, backup_file: str):
        """
        백업 파일이 유효한지 확인합니다.
        사용 예제:
        if db.is_valid_backup_file("backup.sql"):
            print("유효한 백업 파일입니다.")
        """
        if not os.path.exists(backup_file) or not os.path.isfile(backup_file):
            return False
        
        try:
            with open(backup_file, 'r', encoding='utf-8') as file:
                first_line = file.readline().strip()
                return first_line.startswith("-- MySQL dump") or first_line.startswith("-- MariaDB dump")
        except Exception:
            return False
    
    def can_restore_database(self):
        """
        데이터베이스가 복원 가능한 상태인지 확인합니다.
        사용 예제:
        if db.can_restore_database():
            print("데이터베이스 복원이 가능합니다.")
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    return True
        except pymysql.MySQLError as e:
            print(f"데이터베이스 상태 확인 실패: {e}")
            return False
