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
# .env 파일에서 환경 변수 로드
load_dotenv()
pythonpath = os.getenv("PYTHONPATH")
if (pythonpath and pythonpath not in sys.path):
    sys.path.insert(0, pythonpath)

import django
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
# Django 설정 초기화
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

# 전역 이벤트: 스레드/작업에게 종료 신호를 보냄
STOP_EVENT = threading.Event()

# 환경 변수로 동작 제어 (중복 실행 방지, 자동저장 간격, 로그 레벨, 작업 ID)
SCHEDULER_LOG_LEVEL = os.getenv("SCHEDULER_LOG_LEVEL", "INFO").upper()
AUTOSAVE_INTERVAL_SECONDS = int(os.getenv("AUTOSAVE_INTERVAL_SECONDS", "60"))
CONTEXT_AUTOSAVE_JOB_ID = os.getenv("CONTEXT_AUTOSAVE_JOB_ID", "context_autosave")
START_MAIN_PROCESS = os.getenv("START_MAIN_PROCESS", "1")

# 참고: CONTEXT_REGISTRY는 utils.protocol.context 모듈의 전역 레지스트리를 사용합니다.
# (utils/protocol/context/__init__.py에 정의됨)
AUTOSAVE_FAILURES = {}
APP_LIST = ['corecode', 'MCUnode', 'LSISsocket']
scheduler = None

# 전역 시그널 핸들러: SIGINT/SIGTERM 수신 시 스케줄러를 안전하게 종료하고 컨텍스트를 정리
def _graceful_shutdown(signum, frame=None):
    try:
        logger.info(f"시그널 수신됨 ({signum}), 안전한 종료 수행 중")
    except Exception:
        pass
    try:
        global scheduler
        # 먼저 워커 스레드에게 종료 이벤트를 알립니다.
        try:
            STOP_EVENT.set()
            logger.info('시그널 핸들러: 워커 스레드에게 알리기 위해 STOP_EVENT 설정됨')
        except Exception:
            logger.exception('시그널 핸들러: STOP_EVENT 설정 실패')

        if scheduler is not None:
            try:
                logger.info('시그널 핸들러: APScheduler 종료 중 (wait=True)')
                # 시그널 처리 시, 긴 대기를 피하기 위해 wait=False로 즉시 반환 요청
                scheduler.shutdown(wait=True)
                logger.info('시그널 핸들러: APScheduler 종료 요청됨 (wait=True)')
            except Exception:
                logger.exception('시그널 핸들러: APScheduler 종료 실패, 강제 종료 시도')
                try:
                    scheduler.shutdown(wait=False)
                    logger.info('시그널 핸들러: APScheduler 강제 종료 시도됨')
                except Exception:
                    logger.exception('시그널 핸들러: APScheduler 강제 종료도 실패')
        else:
            logger.info('시그널 핸들러: 종료할 스케줄러 없음')

        # 짧게 대기한 뒤(작업들이 정리될 시간을 주기 위해) 아직 종료가 느리면 스레드 스택을 덤프하여 원인 진단
        try:
            time.sleep(2)
            try:
                logger.warning('시그널 핸들러: 진단을 위해 스레드 스택 덤프 중 (있는 경우)')
                frames = sys._current_frames()
                for tid, frame_obj in frames.items():
                    stack = ''.join(traceback.format_stack(frame_obj))
                    logger.warning(f'스레드 id: {tid}\n{stack}')
            except Exception:
                logger.exception('시그널 핸들러: 스레드 스택 덤프 실패')
        except Exception:
            pass
    except Exception:
        logger.exception('시그널 핸들러에서 스케줄러 종료 중 예외 발생')

    try:
        # cleanup_contexts는 안전한 최종 정리(자동저장/지속화 등)를 수행
        try:
            cleanup_contexts()
            logger.info('시그널 핸들러: cleanup_contexts 완료됨')
        except Exception:
            logger.exception('시그널 핸들러: cleanup_contexts 실패')
    except Exception:
        logger.exception('시그널 핸들러 정리 중 예상치 못한 예외')

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
    logger.exception('SIGINT 핸들러 등록 실패')
try:
    signal.signal(signal.SIGTERM, _graceful_shutdown)
except Exception:
    # 일부 Windows 환경에서는 SIGTERM이 제한될 수 있지만 등록 시도는 함
    logger.exception('SIGTERM 핸들러 등록 실패')

@log_exceptions(logger)
@asynccontextmanager
async def lifespan(app: FastAPI):
    global scheduler
    logger.info("FastAPI 수명주기 및 스케줄러 시작")
    try:
        scheduler = BackgroundScheduler(timezone=ZoneInfo(TIME_ZONE))
        scheduler.add_executor(ThreadPoolExecutor(max_workers=os.cpu_count()), "default")
        scheduler.add_executor(ProcessPoolExecutor(max_workers=os.cpu_count()), "processpool")
        # SQLite 지속 저장소 초기화 및 기존 state.json을 DB로 마이그레이션 (있는 경우)
        try:
            # 중앙집중식 sqlite DB 구성 (기본값: project/root/context_store.sqlite3 또는 env CONTEXT_STORE_DB_PATH)
            context_manager.configure_context_store()
            # 각 앱의 통합된 state.json을 DB로 마이그레이션 (비파괴적)
            try:
                app_stores = context_manager.ensure_context_store_for_apps()
                for app_name, cs_path in app_stores.items():
                    try:
                        migrate_from_state_json(Path(cs_path).parent, app_name)
                    except Exception:
                        logger.exception(f"{app_name} 마이그레이션 실패")
            except Exception:
                logger.exception('마이그레이션을 위한 앱 열거 실패')
        except Exception:
            logger.exception('중앙집중식 context_store 구성 실패')
        # 모듈화된 restore_contexts 함수 사용
        try:
            restore_results = restore_contexts()
            total_restored = sum(restore_results.values())
            logger.info(f"{len(restore_results)}개 앱의 컨텍스트 복원됨, 총 블록 수: {total_restored}")

            # 시작 시: MCUnode 레지스트리 항목이 비어있으면 디스크에서 채우기
            try:
                from utils.protocol.context.manager import get_or_create_registry_entry, restore_json_blocks_to_slave_context, ensure_context_store_for_apps
                entry = get_or_create_registry_entry('MCUnode', create_slave=True)
                try:
                    # 기존 메모리 내 상태 확인
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
                        # 앱 경로 찾고 가장 최근 JSON 블록을 슬레이브 컨텍스트로 복원 시도
                        app_stores = ensure_context_store_for_apps()
                        cs = app_stores.get('MCUnode')
                        app_path = Path(cs).parent if cs else Path(__file__).resolve().parents[1]

                        # 1) 기존 블록 기반 복원 시도 (MEMORY 스타일 블록 보존)
                        try:
                            restore_json_blocks_to_slave_context(app_path, entry, load_most_recent=True, use_key_as_memory_name=True)
                        except Exception:
                            logger.exception('restore_json_blocks_to_slave_context 중 MCUnode 시작 복원 실패')

                        # 2) 여전히 비어있으면 통합된 state.json 복원 시도 (최상위 시리얼 -> STATUS/Meta)
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
                                # 발견된 context_store 경로(cs)를 우선시 (context_store 디렉토리를 가리킴)
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
                                            # 대안: CONTEXT_REGISTRY가 이 통합된 상태를 가리키는 dict 형태를 포함하도록 보장
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
                                            logger.info('시작 시 통합된 state.json에서 MCUnode 레지스트리 복원됨')
                                        except Exception:
                                            logger.exception('MCUnode 시작 통합상태 적용 실패')
                        except Exception:
                            logger.exception('MCUnode 시작 통합상태 복원 실패')
                except Exception:
                    logger.exception('MCUnode 시작 복원 확인 실패')
            except Exception:
                logger.exception('MCUnode 시작 복원 임포트 실패')

            # 시작 시 컨텍스트 통계 로깅
            try:
                stats = get_context_stats()
                logger.info(f"컨텍스트 레지스트리 통계: {stats['total_apps']}개 앱 로드됨: {stats['app_names']}")
            except Exception:
                logger.exception("컨텍스트 통계 로깅 실패")

        except Exception:
            logger.exception("컨텍스트 복원 실패")

        # 주기적 자동 저장 작업 등록: scheduler.autosave_job을 직접 사용
        # --reload 등의 리로더로 인한 중복 실행을 방지하기 위해 START_MAIN_PROCESS 환경변수를 확인합니다.
        if START_MAIN_PROCESS == '1':
            # 등록: 이미 같은 id의 작업이 존재하면 제거 후 등록
            try:
                if scheduler.get_job(CONTEXT_AUTOSAVE_JOB_ID):
                    scheduler.remove_job(CONTEXT_AUTOSAVE_JOB_ID)
            except Exception:
                pass
            try:
                # 초 단위로 유연하게 설정
                scheduler.add_job(autosave_job, 'interval', seconds=AUTOSAVE_INTERVAL_SECONDS, id=CONTEXT_AUTOSAVE_JOB_ID)
                logger.info(f'자동저장 작업 등록됨 (간격={AUTOSAVE_INTERVAL_SECONDS}초, job_id={CONTEXT_AUTOSAVE_JOB_ID})')
            except Exception:
                logger.exception('자동저장 작업 등록 실패')

            try:
                # 기존 자동 백업 등록은 scheduler 모듈의 전역 백업(작업)으로 단일화했습니다.
                # 중복 실행 방지를 위해 여기서는 backup_all_states 등록을 생략합니다.
                logger.info('중복 백업 방지를 위해 메인 레벨 backup_all_states 등록 생략; scheduler 모듈이 백업 처리')
            except Exception:
                logger.exception('컨텍스트 백업 작업 등록(생략) 중 예외 발생')
        else:
            logger.info('START_MAIN_PROCESS != 1 이므로 자동저장 및 복원 작업을 건너뜀 (중복 실행 방지)')

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
        print("스케줄러 시작됨.")
        logger.info("스케줄러 시작됨.")
        yield
    finally:
        # 종료 시점: scheduler가 존재하면 한 번만 완전 종료(wait=True) 시도하고, 그 다음에 컨텍스트 정리 수행
        try:
            if scheduler is not None:
                try:
                    logger.info('APScheduler 종료 중 (작업 완료 대기)')
                    scheduler.shutdown(wait=False)
                    logger.info('APScheduler 완전 종료됨 (wait=True)')
                except Exception:
                    # 강제/빠른 종료가 필요한 경우 로그를 남기고 계속 진행
                    logger.exception('wait=True로 APScheduler 종료 실패, 강제 종료 시도')
                    try:
                        scheduler.shutdown(wait=False)
                        logger.info('wait=False로 APScheduler 종료 시도됨')
                    except Exception:
                        logger.exception('APScheduler 강제 종료 실패')
            else:
                logger.info('종료할 스케줄러 인스턴스 없음')
        except Exception:
            logger.exception('스케줄러 종료 중 예외 발생')

        # START_MAIN_PROCESS == '1' 일 때만 컨텍스트 정리 수행
        try:
            if START_MAIN_PROCESS == '1':
                try:
                    cleanup_contexts()
                    logger.info('cleanup_contexts 완료됨')
                except Exception:
                    logger.exception('cleanup_contexts 실패')
            else:
                logger.info('START_MAIN_PROCESS != 1 이므로 종료 시 자동저장/지속화를 건너뜀')
        except Exception:
            logger.exception('최종 정리 중 예외 발생')

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

