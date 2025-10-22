import logging
import asyncio
import atexit
import os
from pathlib import Path
import datetime
from concurrent.futures import ThreadPoolExecutor

try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.interval import IntervalTrigger
except Exception:
    AsyncIOScheduler = None
    IntervalTrigger = None

logger = logging.getLogger('py_backend.scheduler')

scheduler = None
_started = False

# 샘플 비동기 작업
async def _heartbeat():
    try:
        logger.debug('scheduler heartbeat')
    except Exception:
        pass

# 백업 설정: 환경변수로 제어 가능 (기본: 활성화)
_BACKUP_ENABLED = os.getenv('CONTEXT_STORE_BACKUP_ENABLED', '1') != '0'
_BACKUP_INTERVAL = int(os.getenv('CONTEXT_STORE_BACKUP_INTERVAL_SECONDS', '300'))
_DEFAULT_BACKUP_DIR = Path(os.getenv('CONTEXT_STORE_BACKUP_DIR', ''))
if not _DEFAULT_BACKUP_DIR:
    # 프로젝트 루트(py_backend 폴더 기준) 아래에 context_store_backups 디렉터리 생성
    _DEFAULT_BACKUP_DIR = Path(__file__).resolve().parents[2] / 'context_store_backups'

_backup_executor = ThreadPoolExecutor(max_workers=1)

# 지연 임포트 대신 직접 가져오기: sqlite_store.backup_db 사용
from utils.protocol.context.sqlite_store import backup_db


def _backup_once():
    """동기식으로 일회 백업을 생성한다. 실패 시 로깅만 함."""
    try:
        if not _BACKUP_ENABLED:
            logger.debug('context store backup disabled by config')
            return
        _DEFAULT_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H%M%SZ')
        dest = _DEFAULT_BACKUP_DIR / f'context_store_backup_{ts}.sqlite3'
        p = backup_db(dest)
        logger.info('Created context store backup: %s', str(p))
        # --- 보관 정책 적용: 환경변수로 keep_days와 max_files를 제어 ---
        try:
            keep_days_env = os.getenv('CONTEXT_STORE_BACKUP_KEEP_DAYS')
            default_keep = int(os.getenv('CONTEXT_STORE_BACKUP_KEEP_DAYS_DEFAULT', '30'))
            if keep_days_env and keep_days_env.strip().lstrip('-').isdigit():
                keep_days = int(keep_days_env)
            else:
                keep_days = default_keep
        except Exception:
            keep_days = int(os.getenv('CONTEXT_STORE_BACKUP_KEEP_DAYS_DEFAULT', '30'))
        try:
            max_files_env = os.getenv('CONTEXT_STORE_BACKUP_MAX_FILES')
            default_max = int(os.getenv('CONTEXT_STORE_BACKUP_MAX_FILES_DEFAULT', '10'))
            if max_files_env and max_files_env.strip().lstrip('-').isdigit():
                max_files = int(max_files_env)
            else:
                max_files = default_max
        except Exception:
            max_files = int(os.getenv('CONTEXT_STORE_BACKUP_MAX_FILES_DEFAULT', '10'))

        try:
            # collect all backup files sorted by mtime (oldest first)
            files = sorted([f for f in _DEFAULT_BACKUP_DIR.glob('context_store_backup_*.sqlite3') if f.is_file()], key=lambda p: p.stat().st_mtime)
            # age-based pruning
            if isinstance(keep_days, int) and keep_days > 0:
                cutoff_ts = (datetime.datetime.utcnow() - datetime.timedelta(days=keep_days)).timestamp()
                for fpath in list(files):
                    try:
                        if fpath.stat().st_mtime < cutoff_ts:
                            fpath.unlink()
                            logger.info('Pruned old global backup by age: %s', str(fpath))
                    except Exception:
                        logger.exception('Failed to prune backup by age: %s', str(fpath))
                # refresh list
                files = sorted([f for f in _DEFAULT_BACKUP_DIR.glob('context_store_backup_*.sqlite3') if f.is_file()], key=lambda p: p.stat().st_mtime)
            # count-based pruning (keep newest max_files)
            if isinstance(max_files, int) and max_files > 0:
                if len(files) > max_files:
                    to_remove = files[0:len(files)-max_files]
                    for fpath in to_remove:
                        try:
                            fpath.unlink()
                            logger.info('Pruned old global backup by count: %s', str(fpath))
                        except Exception:
                            logger.exception('Failed to prune backup by count: %s', str(fpath))
        except Exception:
            logger.exception('Failed to apply retention policy to global backups')
    except Exception:
        logger.exception('Failed to create context store backup')


async def _backup_job():
    """비동기 스케줄러에서 호출되는 백업 작업(블로킹 코드를 스레드에서 실행)."""
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(_backup_executor, _backup_once)


def _ensure_scheduler():
    global scheduler
    if scheduler is None:
        if AsyncIOScheduler is None:
            logger.warning('APScheduler not available (missing dependency)')
            return None
        # create AsyncIOScheduler using current event loop
        try:
            scheduler = AsyncIOScheduler()
        except Exception:
            logger.exception('Failed to create AsyncIOScheduler')
            scheduler = None
    return scheduler


def start():
    """Start the scheduler (safe to call multiple times)."""
    global _started
    try:
        if _started:
            return
        sch = _ensure_scheduler()
        if sch is None:
            return
        # add example heartbeat job (idempotent)
        try:
            if IntervalTrigger is not None:
                sch.add_job(_heartbeat, IntervalTrigger(seconds=60), id='heartbeat', replace_existing=True)
        except Exception:
            logger.exception('Failed to add heartbeat job')

        # add context_store backup job
        try:
            if _BACKUP_ENABLED and IntervalTrigger is not None:
                sch.add_job(_backup_job, IntervalTrigger(seconds=_BACKUP_INTERVAL), id='context_store_backup', replace_existing=True)
                logger.info('Scheduled context_store backup every %s seconds to %s', _BACKUP_INTERVAL, str(_DEFAULT_BACKUP_DIR))
        except Exception:
            logger.exception('Failed to add context_store backup job')

        try:
            sch.start()
            _started = True
            logger.info('APScheduler started')
        except Exception:
            logger.exception('Failed to start APScheduler')
    except Exception:
        logger.exception('Unexpected error in scheduler.start')


def shutdown(wait: bool = False):
    """Shutdown the scheduler if running. 종료 시 한 번 더 백업을 시도함."""
    global scheduler, _started
    try:
        # 최종 백업(동기)
        try:
            if _BACKUP_ENABLED:
                logger.info('Performing final context_store backup before shutdown')
                # 블로킹이지만 프로세스 종료 전에 완료시키기 위해 동기 호출
                _backup_once()
        except Exception:
            logger.exception('Final backup failed during shutdown')

        if scheduler is not None:
            try:
                scheduler.shutdown(wait=wait)
            except Exception:
                logger.exception('Error while shutting down scheduler')
        _started = False
    except Exception:
        logger.exception('Unexpected error in scheduler.shutdown')


# Ensure scheduler is shut down at process exit; 백업 후 종료
def _exit_handler():
    try:
        if _BACKUP_ENABLED:
            try:
                _backup_once()
            except Exception:
                logger.exception('Exit-time backup failed')
    finally:
        try:
            shutdown(wait=False)
        except Exception:
            logger.exception('Error in exit handler during shutdown')

atexit.register(_exit_handler)
