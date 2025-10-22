import asyncio
from dotenv import load_dotenv
import sys, os, time, datetime
import signal
import threading
import faulthandler
import traceback

from utils.protocol.LSIS.client.tcp import LSIS_TcpClient
from utils.protocol.context.scheduler import autosave_job, cleanup_contexts, get_context_stats, restore_contexts
from utils.ws_log import static_file_app, websocket_app
from utils.protocol.context import manager as context_manager
from utils.protocol.context.sqlite_store import migrate_from_state_json
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

# 전역 이벤트: 스레드/잡에 종료 신호를 전달
STOP_EVENT = threading.Event()

# 환경변수로 동작 제어 (중복 실행 방지, autosave 주기, 로그 레벨, job id)
SCHEDULER_LOG_LEVEL = os.getenv("SCHEDULER_LOG_LEVEL", "INFO").upper()
AUTOSAVE_INTERVAL_SECONDS = int(os.getenv("AUTOSAVE_INTERVAL_SECONDS", "60"))
CONTEXT_AUTOSAVE_JOB_ID = os.getenv("CONTEXT_AUTOSAVE_JOB_ID", "context_autosave")
START_MAIN_PROCESS = os.getenv("START_MAIN_PROCESS", "1")

# NOTE: CONTEXT_REGISTRY는 utils.protocol.context 모듈의 전역 레지스트리를 사용합니다.
# (정의는 utils/protocol/context/__init__.py 에서 이루어집니다)
AUTOSAVE_FAILURES = {}
APP_LIST = ['corecode', 'MCUnode', 'LSISsocket']
scheduler = None

# 전역 시그널 핸들러: SIGINT/SIGTERM 수신 시 안전하게 스케줄러 종료 및 컨텍스트 정리 수행
def _graceful_shutdown(signum, frame=None):
    try:
        logger.info(f"Signal received ({signum}), performing graceful shutdown")
    except Exception:
        pass
    try:
        global scheduler
        # 먼저 워커들에게 종료 이벤트를 알립니다.
        try:
            STOP_EVENT.set()
            logger.info('Signal handler: STOP_EVENT set to notify worker threads')
        except Exception:
            logger.exception('Signal handler: failed to set STOP_EVENT')

        if scheduler is not None:
            try:
                logger.info('Signal handler: shutting down APScheduler (wait=False)')
                # 시그널 처리 시에는 긴 대기를 피하기 위해 wait=False로 즉시 반환 요청
                scheduler.shutdown(wait=False)
                logger.info('Signal handler: APScheduler shutdown requested (wait=False)')
            except Exception:
                logger.exception('Signal handler: APScheduler shutdown failed, attempting force shutdown')
                try:
                    scheduler.shutdown(wait=False)
                    logger.info('Signal handler: APScheduler forced shutdown attempted')
                except Exception:
                    logger.exception('Signal handler: APScheduler forced shutdown also failed')
        else:
            logger.info('Signal handler: no scheduler to shutdown')

        # 짧게 대기한 뒤(잡들이 정리될 시간을 주기 위해) 아직 종료가 느리면 스레드 스택을 덤프하여 원인 진단
        try:
            time.sleep(2)
            try:
                logger.warning('Signal handler: dumping thread stacks for diagnosis (if any)')
                frames = sys._current_frames()
                for tid, frame_obj in frames.items():
                    stack = ''.join(traceback.format_stack(frame_obj))
                    logger.warning(f'Thread id: {tid}\n{stack}')
            except Exception:
                logger.exception('Signal handler: failed to dump thread stacks')
        except Exception:
            pass
    except Exception:
        logger.exception('Exception during scheduler shutdown in signal handler')

    try:
        # cleanup_contexts는 안전한 최종 정리(autosave/persist 등)를 수행
        try:
            cleanup_contexts()
            logger.info('Signal handler: cleanup_contexts completed')
        except Exception:
            logger.exception('Signal handler: cleanup_contexts failed')
    except Exception:
        logger.exception('Unexpected exception in signal handler cleanup')

    # 이벤트 루프가 실행 중이면 중지 시도
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            try:
                loop.call_soon_threadsafe(loop.stop)
            except Exception:
                pass
    except Exception:
        pass

    # 안전하게 프로세스 종료
    try:
        sys.exit(0)
    except SystemExit:
        try:
            os._exit(0)
        except Exception:
            pass

# 시그널 핸들러 등록 (Windows 포함)
try:
    signal.signal(signal.SIGINT, _graceful_shutdown)
except Exception:
    logger.exception('Failed to register SIGINT handler')
try:
    signal.signal(signal.SIGTERM, _graceful_shutdown)
except Exception:
    # 일부 Windows 환경에서는 SIGTERM이 제한될 수 있지만 등록 시도는 함
    logger.exception('Failed to register SIGTERM handler')

@log_exceptions(logger)
@asynccontextmanager
async def lifespan(app: FastAPI):
    global scheduler
    logger.info("FastAPI 수명주기 및 스케줄러 시작")
    try:
        scheduler = BackgroundScheduler(timezone=ZoneInfo(TIME_ZONE))
        scheduler.add_executor(ThreadPoolExecutor(max_workers=os.cpu_count()), "default")
        scheduler.add_executor(ProcessPoolExecutor(max_workers=os.cpu_count()), "processpool")
        # Initialize SQLite persistent store and migrate existing state.json into DB (if present)
        try:
            # configure centralized sqlite DB (defaults to project/root/context_store.sqlite3 or env CONTEXT_STORE_DB_PATH)
            context_manager.configure_context_store()
            # migrate each app's aggregated state.json into the DB (non-destructive)
            try:
                app_stores = context_manager.ensure_context_store_for_apps()
                for app_name, cs_path in app_stores.items():
                    try:
                        migrate_from_state_json(Path(cs_path).parent, app_name)
                    except Exception:
                        logger.exception(f"Migration failed for {app_name}")
            except Exception:
                logger.exception('Failed to enumerate apps for migration')
        except Exception:
            logger.exception('Failed to configure centralized context_store')
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
                # 기존 자동 백업 등록은 scheduler 모듈의 전역 백업(job)으로 단일화했습니다.
                # 중복 실행 방지를 위해 여기서는 backup_all_states 등록을 생략합니다.
                logger.info('Skipped main-level backup_all_states registration to avoid duplicate backups; scheduler module handles backups')
            except Exception:
                logger.exception('컨텍스트 백업 작업 등록(생략) 중 예외 발생')
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
        # 종료 시점: scheduler가 존재하면 한 번만 완전 종료(wait=True) 시도하고, 그 다음에 컨텍스트 정리 수행
        try:
            if scheduler is not None:
                try:
                    logger.info('Shutting down APScheduler (waiting for jobs to finish)')
                    scheduler.shutdown(wait=False)
                    logger.info('APScheduler fully shutdown (wait=True)')
                except Exception:
                    # 강제/빠른 종료가 필요한 경우 로그를 남기고 계속 진행
                    logger.exception('APScheduler shutdown with wait=True failed, attempting force shutdown')
                    try:
                        scheduler.shutdown(wait=False)
                        logger.info('APScheduler shutdown attempted with wait=False')
                    except Exception:
                        logger.exception('APScheduler forced shutdown failed')
            else:
                logger.info('No scheduler instance to shutdown')
        except Exception:
            logger.exception('Exception while shutting down scheduler')

        # START_MAIN_PROCESS == '1' 일 때만 컨텍스트 정리 수행
        try:
            if START_MAIN_PROCESS == '1':
                try:
                    cleanup_contexts()
                    logger.info('cleanup_contexts completed')
                except Exception:
                    logger.exception('cleanup_contexts failed')
            else:
                logger.info('START_MAIN_PROCESS != 1 이므로 종료 시 autosave/persist를 건너뜁니다')
        except Exception:
            logger.exception('Exception during final cleanup')

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

