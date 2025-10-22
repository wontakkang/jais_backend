import subprocess
import os
import time
from typing import List
import logging
from utils import setup_logger
from utils.config import settings

# bat 로거 초기화
bat_logger = setup_logger(name="bat_logger", log_file=f"{settings.LOG_DIR}/bat_Execute.log", level=logging.DEBUG)

class BatchFileExecutor:
    def __init__(self, batch_file_path: str, file_extension: str = "*", args: List[str] = None):
        """
        배치 파일 실행기를 초기화합니다.

        :param batch_file_path: 실행할 배치 파일의 경로
        :param file_extension: 처리할 파일의 확장자 (기본값: "*", 모든 파일)
        :param args: 배치 파일 실행에 필요한 매개변수 리스트 (기본값: None)
        """
        if not batch_file_path:
            raise ValueError("Batch file path cannot be empty.")

        self.batch_file_path = batch_file_path
        self.file_extension = file_extension
        self.args = args or []

    def ensure_directory_exists(self, directory: str):
        """
        지정된 경로에 폴더가 없으면 생성합니다.

        :param directory: 확인 및 생성할 폴더 경로
        """
        try:
            if not os.path.exists(directory):
                os.makedirs(directory)
                bat_logger.info(f"Directory created: {directory}")
            else:
                bat_logger.info(f"Directory already exists: {directory}")
        except Exception as e:
            bat_logger.error(f"Failed to ensure directory exists: {e}")
            raise

    def delete_old_files(self, directory: str, days: int):
        """
        지정된 경로에서 입력한 일 수(days)만큼 지난 파일을 삭제합니다.

        :param directory: 파일을 삭제할 폴더 경로
        :param days: 삭제 기준이 되는 일 수
        """
        now = time.time()
        cutoff_time = now - (days * 86400)  # 일 수를 초로 변환

        if os.path.exists(directory):
            try:
                for filename in os.listdir(directory):
                    if not filename.endswith(self.file_extension) and self.file_extension != "*":
                        continue

                    file_path = os.path.join(directory, filename)
                    if os.path.isfile(file_path):
                        file_creation_time = os.path.getctime(file_path)
                        if file_creation_time < cutoff_time:
                            os.remove(file_path)
                            bat_logger.info(f"Deleted: {file_path}")
            except Exception as e:
                bat_logger.error(f"Failed to delete old files: {e}")
                raise
        else:
            bat_logger.warning(f"Directory does not exist: {directory}")

    def execute(self, cleanup_days: int = None) -> dict:
        """
        배치 파일을 실행합니다.

        :param cleanup_days: 지정된 일 수 이전의 파일을 삭제할 기준 (기본값: None)
        :return: 실행 결과를 담은 딕셔너리 {'success': bool, 'output': str, 'error': str}
        """
        if len(self.args) > 1:
            try:
                self.ensure_directory_exists(self.args[1])

                if cleanup_days is not None:
                    self.delete_old_files(self.args[1], cleanup_days)
            except Exception as e:
                bat_logger.error(f"Pre-execution setup failed: {e}")
                return {"success": False, "output": "", "error": str(e)}

        try:
            result = subprocess.run(
                [self.batch_file_path, *self.args],
                shell=False,  # shell=True 사용 시 보안 위험 방지
                check=True,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            bat_logger.info("Batch file executed successfully.")
            return {"success": True, "output": result.stdout.strip(), "error": ""}
        except subprocess.CalledProcessError as e:
            bat_logger.error(f"Batch file execution failed: {e.stderr}")
            return {"success": False, "output": "", "error": e.stderr.strip()}
        except Exception as e:
            bat_logger.error(f"Unexpected error during execution: {e}")
            return {"success": False, "output": "", "error": str(e)}

    def set_batch_file_path(self, batch_file_path: str):
        """
        배치 파일 경로를 업데이트합니다.

        :param batch_file_path: 새로운 배치 파일 경로
        """
        if not batch_file_path:
            raise ValueError("Batch file path cannot be empty.")
        self.batch_file_path = batch_file_path

    def set_file_extension(self, file_extension: str):
        """
        처리할 파일 확장자를 설정합니다.

        :param file_extension: 파일 확장자 (예: ".sql", ".txt", "*")
        """
        self.file_extension = file_extension

    def set_args(self, args: List[str]):
        """
        배치 파일 실행 매개변수를 설정합니다.

        :param args: 배치 파일 실행에 필요한 매개변수 리스트
        """
        self.args = args

