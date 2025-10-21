import asyncio
from dotenv import load_dotenv
import sys, os, time, datetime

from utils.protocol.LSIS.client.tcp import LSIS_TcpClient
from utils.protocol.context.manager import backup_all_states
from utils.protocol.context.scheduler import autosave_job, cleanup_contexts, get_context_stats, restore_contexts
from utils.ws_log import static_file_app, websocket_app
# .env 파일에서 환경변수 로드
load_dotenv()
pythonpath = os.getenv("PYTHONPATH")
if (pythonpath and pythonpath not in sys.path):
    sys.path.insert(0, pythonpath)

import django
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
# ⬇️ Django 설정 초기화
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "py_backend.settings")
django.setup()
from LSISsocket.models import SocketClientConfig, SocketClientLog
from py_backend.settings import TIME_ZONE
import time
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.executors.pool import ThreadPoolExecutor, ProcessPoolExecutor
from utils import setup_logger, log_exceptions
from pathlib import Path
from LSISsocket.service import tcp_client_servive
from contextlib import asynccontextmanager
from zoneinfo import ZoneInfo
from asgiref.sync import sync_to_async


logger = setup_logger(
    name="py_backend.scheduler",
    log_file=os.path.join(os.getcwd(), "log", "scheduler.log"),
    level="DEBUG",
    backup_days=7,
)
# 환경변수로 동작 제어 (중복 실행 방지, autosave 주기, 로그 레벨, job id)
SCHEDULER_LOG_LEVEL = os.getenv("SCHEDULER_LOG_LEVEL", "INFO").upper()
AUTOSAVE_INTERVAL_SECONDS = int(os.getenv("AUTOSAVE_INTERVAL_SECONDS", "60"))
CONTEXT_AUTOSAVE_JOB_ID = os.getenv("CONTEXT_AUTOSAVE_JOB_ID", "context_autosave")
START_MAIN_PROCESS = os.getenv("START_MAIN_PROCESS", "1")

# NOTE: CONTEXT_REGISTRY는 utils.protocol.context 모듈의 전역 레지스트리를 사용합니다.
# (정의는 utils/protocol/context/__init__.py 에서 이루어집니다)
AUTOSAVE_FAILURES = {}

scheduler = None
@log_exceptions(logger)
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("FastAPI 수명주기 및 스케줄러 시작")
    try:
        global scheduler
        scheduler = BackgroundScheduler(timezone=ZoneInfo(TIME_ZONE))
        scheduler.add_executor(ThreadPoolExecutor(max_workers=os.cpu_count()), "default")
        scheduler.add_executor(ProcessPoolExecutor(max_workers=4), "processpool")
        # 모듈화된 restore_contexts 함수 사용
        try:
            restore_results = restore_contexts()
            total_restored = sum(restore_results.values())
            logger.info(f"Restored contexts for {len(restore_results)} apps, total blocks: {total_restored}")

            # Start-up: ensure MCUnode registry entry is populated from disk if empty
            try:
                from utils.protocol.context.manager import get_or_create_registry_entry, restore_json_blocks_to_slave_context, ensure_context_store_for_apps
                entry = get_or_create_registry_entry('MCUnode', create_slave=True)
                try:
                    # Check existing in-memory state
                    state_ok = False
                    if entry is not None:
                        try:
                            if hasattr(entry, 'get_all_state') and callable(getattr(entry, 'get_all_state')):
                                cur = entry.get_all_state()
                                if isinstance(cur, dict) and cur:
                                    state_ok = True
                        except Exception:
                            state_ok = False
                    if not state_ok:
                        # locate app path and attempt restore of most recent JSON blocks into the slave context
                        app_stores = ensure_context_store_for_apps()
                        cs = app_stores.get('MCUnode')
                        app_path = Path(cs).parent if cs else Path(__file__).resolve().parents[1]

                        # 1) Try existing block-based restore (preserves MEMORY-style blocks)
                        try:
                            restore_json_blocks_to_slave_context(app_path, entry, load_most_recent=True, use_key_as_memory_name=True)
                        except Exception:
                            logger.exception('MCUnode startup restore failed during restore_json_blocks_to_slave_context')

                        # 2) If still empty, attempt aggregated state.json restore (top-level serial -> STATUS/Meta)
                        try:
                            still_empty = True
                            try:
                                if hasattr(entry, 'get_all_state') and callable(getattr(entry, 'get_all_state')):
                                    cur2 = entry.get_all_state()
                                    if isinstance(cur2, dict) and cur2:
                                        still_empty = False
                            except Exception:
                                still_empty = True

                            if still_empty:
                                # prefer the discovered context_store path (cs) which points at the context_store directory
                                if cs:
                                    cs_dir = Path(cs)
                                else:
                                    cs_dir = Path(app_path) / 'context_store'
                                state_path = cs_dir / 'state.json'
                                if state_path.exists():
                                    import json as _json
                                    try:
                                        with state_path.open('r', encoding='utf-8') as sf:
                                            disk_state = _json.load(sf)
                                    except Exception:
                                        disk_state = None
                                    if isinstance(disk_state, dict) and disk_state:
                                        try:
                                            if hasattr(entry, 'set_state') and callable(getattr(entry, 'set_state')):
                                                for serial_k, v in disk_state.items():
                                                    try:
                                                        entry.set_state(serial_k, v)
                                                    except Exception:
                                                        pass
                                            elif isinstance(entry, dict):
                                                store = entry.setdefault('store', {})
                                                store['state'] = disk_state
                                            else:
                                                store_attr = getattr(entry, 'store', None)
                                                if isinstance(store_attr, dict):
                                                    store_attr['state'] = disk_state
                                                else:
                                                    try:
                                                        setattr(entry, 'store', {'state': disk_state})
                                                    except Exception:
                                                        pass
                                            # Fallback: ensure CONTEXT_REGISTRY contains a dict form pointing at this aggregated state
                                            try:
                                                from utils.protocol.context import CONTEXT_REGISTRY
                                                if not isinstance(CONTEXT_REGISTRY.get('MCUnode'), dict):
                                                    CONTEXT_REGISTRY['MCUnode'] = {'store': {'state': dict(disk_state)}}
                                                else:
                                                    try:
                                                        CONTEXT_REGISTRY['MCUnode'].setdefault('store', {})['state'] = dict(disk_state)
                                                    except Exception:
                                                        CONTEXT_REGISTRY['MCUnode'] = {'store': {'state': dict(disk_state)}}
                                            except Exception:
                                                pass
                                            logger.info('MCUnode registry restored from aggregated state.json at startup')
                                        except Exception:
                                            logger.exception('MCUnode startup aggregated-state apply failed')
                        except Exception:
                            logger.exception('MCUnode startup aggregated-state restore failed')
                except Exception:
                    logger.exception('MCUnode startup restore check failed')
            except Exception:
                logger.exception('MCUnode startup restore import failed')

            # 시작 시 컨텍스트 통계 로깅
            try:
                stats = get_context_stats()
                logger.info(f"Context registry stats: {stats['total_apps']} apps loaded: {stats['app_names']}")
            except Exception:
                logger.exception("Failed to log context stats")

        except Exception:
            logger.exception("컨텍스트 복원 실패")

        # 주기적 자동 저장 작업 등록: scheduler.autosave_job을 직접 사용
        # --reload 등의 리로더로 인한 중복 실행을 방지하기 위해 START_MAIN_PROCESS 환경변수를 확인합니다.
        if START_MAIN_PROCESS == '1':
            # 등록: 이미 같은 id의 job이 존재하면 제거 후 등록
            try:
                if scheduler.get_job(CONTEXT_AUTOSAVE_JOB_ID):
                    scheduler.remove_job(CONTEXT_AUTOSAVE_JOB_ID)
            except Exception:
                pass
            try:
                # seconds 기반으로 유연하게 설정
                scheduler.add_job(autosave_job, 'interval', seconds=AUTOSAVE_INTERVAL_SECONDS, id=CONTEXT_AUTOSAVE_JOB_ID)
                logger.info(f'자동저장 작업 등록됨 (interval={AUTOSAVE_INTERVAL_SECONDS}s, job_id={CONTEXT_AUTOSAVE_JOB_ID})')
            except Exception:
                logger.exception('자동저장 작업 등록 실패')

            try:
                # 정기 백업 작업 등록: context_store 백업을 주기적으로 실행
                try:
                    CONTEXT_BACKUP_INTERVAL_SECONDS = int(os.getenv('CONTEXT_BACKUP_INTERVAL_SECONDS', '3600'))
                except Exception:
                    CONTEXT_BACKUP_INTERVAL_SECONDS = 3600
                CONTEXT_BACKUP_JOB_ID = os.getenv('CONTEXT_BACKUP_JOB_ID', 'context_backup')

                # 기존에 동일한 ID의 잡이 있으면 제거
                try:
                    if scheduler.get_job(CONTEXT_BACKUP_JOB_ID):
                        scheduler.remove_job(CONTEXT_BACKUP_JOB_ID)
                except Exception:
                    pass

                def backup_contexts_wrapper():
                    try:
                        # env에서 보관 정책값 읽기(없으면 manager의 기본값 사용)
                        keep_days_env = os.getenv('CONTEXT_BACKUP_KEEP_DAYS')
                        max_files_env = os.getenv('CONTEXT_BACKUP_MAX_FILES')
                        try:
                            keep_days_val = int(keep_days_env) if keep_days_env and keep_days_env.strip().lstrip('-').isdigit() else None
                        except Exception:
                            keep_days_val = None
                        try:
                            max_files_val = int(max_files_env) if max_files_env and max_files_env.strip().lstrip('-').isdigit() else None
                        except Exception:
                            max_files_val = None

                        backup_all_states(keep_days=keep_days_val, max_backups=max_files_val)
                    except Exception:
                        logger.exception('backup_all_states 실행 실패')

                scheduler.add_job(backup_contexts_wrapper, 'interval', seconds=CONTEXT_BACKUP_INTERVAL_SECONDS, id=CONTEXT_BACKUP_JOB_ID)
                logger.info(f'컨텍스트 백업 작업 등록됨 (interval={CONTEXT_BACKUP_INTERVAL_SECONDS}s, job_id={CONTEXT_BACKUP_JOB_ID})')
            except Exception:
                logger.exception('컨텍스트 백업 작업 등록 실패')
        else:
            logger.info('START_MAIN_PROCESS != 1 이므로 autosave 및 복원 작업을 건너뜁니다 (중복 실행 방지)')

        clients = await sync_to_async(list)(SocketClientConfig.objects.filter(is_used=True).all())
        for client in clients:
            scheduler.add_job(
                tcp_client_servive,
                list(client.cron.keys())[0],
                **list(client.cron.values())[0],
                replace_existing=True,
                max_instances=5,
                misfire_grace_time=15,
                coalesce=False,
                executor='default',
                args=(client,),
            )
            time.sleep(0.111)
        scheduler.start()
        print("Scheduler started.")
        logger.info("Scheduler started.")
        yield
    finally:
        try:
            scheduler.shutdown(wait=False)
            logger.info('APScheduler 종료 중')
            logger.info("Closing sockets...")
        except Exception:
            pass
        # 앱 종료 시: START_MAIN_PROCESS가 1일 때 스케줄러를 완전 종료(wait=True)한 뒤
        # 모듈화된 cleanup_contexts 함수를 사용합니다.
        try:
            if START_MAIN_PROCESS == '1':
                try:
                    # scheduler를 먼저 완전 종료하여 주기 작업이 더 이상 실행되지 않게 함
                    try:
                        scheduler.shutdown(wait=True)
                        logger.info('APScheduler 완전 종료됨 (wait=True)')
                    except Exception:
                        logger.exception('APScheduler 완전 종료 중 오류 발생')

                    # 모듈화된 cleanup_contexts 함수 사용
                    cleanup_contexts()

                except Exception:
                    logger.exception('종료 시 cleanup 실패')
            else:
                logger.info('START_MAIN_PROCESS != 1 이므로 종료 시 autosave/persist를 건너뜁니다')
                try:
                    scheduler.shutdown(wait=True)
                    logger.info('APScheduler 완전 종료됨 (wait=True)')
                except Exception:
                    logger.exception('APScheduler 완전 종료 중 오류 발생')
        except Exception:
            logger.exception('종료 루틴에서 예외 발생')

app = FastAPI(title="FastAPI 스케쥴러", version="1.0", lifespan=lifespan)

# 웹소켓 ASGI 앱과 정적 UI 마운트
# websocket_app은 utils.ws_log에서 제공하는 ASGI 애플리케이션 스타일의 호출 가능한 객체입니다
app.mount('/ws/logging-tail', websocket_app)
# Starlette의 StaticFiles가 사용 가능하면 /static/ws_ui 경로로 내장 UI 정적 파일을 제공하고,
# 그렇지 않으면 utils.ws_log에서 제공하는 static_file_app으로 대체합니다
try:
    app.mount('/static/ws_ui', StaticFiles(directory=os.path.join(os.getcwd(), 'utils', 'static', 'ws_ui')), name='ws_ui')
except Exception:
    # 대체: 커스텀 ASGI 정적 파일 핸들러 사용
    app.mount('/static/ws_ui', static_file_app)

