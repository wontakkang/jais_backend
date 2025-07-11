from utils.system.main import BatchFileExecutor
from utils.system.nmap import NmapScanner

__all__ = ["BatchFileExecutor", "NmapScanner"]



# 사용예시
# from app.config import settings
# from app.utils.system import BatchFileExecutor
#
# # BatchFileExecutor 인스턴스 생성
# dump_executor = BatchFileExecutor(
#     batch_file_path="d:/project/pythonProject/app/utils/system/bat/backup.bat",
#     file_extension=".sql",
#     args=[settings.DATABASE_DATADUMP_PATH, settings.DATABASE_BACKUP_PATH],
# )
#
# def dump_backup(days):
#     dump_executor.execute(cleanup_days=days)