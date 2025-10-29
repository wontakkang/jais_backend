import asyncio
from dotenv import load_dotenv
import sys, os, time, datetime
import signal
import threading
import faulthandler
import traceback
import logging

from data_entry.service import aggregate_2min_to_10min, aggregate_to_1hour, redis_to_db, aggregate_to_daily
from utils.protocol.LSIS.client.tcp import LSIS_TcpClient
from utils.ws_log import static_file_app, websocket_app
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
from LSISsocket.models import SetupGroup, SocketClientConfig, SocketClientLog
from py_backend.settings import TIME_ZONE
import time
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.executors.pool import ThreadPoolExecutor, ProcessPoolExecutor
from apscheduler.schedulers.base import SchedulerNotRunningError
from utils import setup_logger, log_exceptions
from utils.logger import log_job_runtime
from pathlib import Path
from LSISsocket.service import setup_variables_to_redis, tcp_client_to_redis, reids_to_memory_mapping
from contextlib import asynccontextmanager
from zoneinfo import ZoneInfo
from asgiref.sync import sync_to_async


logger = setup_logger(
    name="py_backend.scheduler",
    log_file=os.path.join(os.getcwd(), "log", "scheduler.log"),
    level="DEBUG",
    backup_days=7,
)

# 전역 스케줄러 레퍼런스 (없을 수 있으므로 미리 None으로 초기화)
scheduler = None

# 전역 이벤트: 스레드/작업에게 종료 신호를 보냄
STOP_EVENT = threading.Event()

# 환경 변수로 동작 제어 (스케줄러 로그 레벨 등)
SCHEDULER_LOG_LEVEL = os.getenv("SCHEDULER_LOG_LEVEL", "INFO").upper()

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
        # AsyncIO 기반 스케줄러로 교체하여 FastAPI 이벤트 루프와 자연스럽게 동작
        scheduler = AsyncIOScheduler(timezone=ZoneInfo(TIME_ZONE))
        # 동일한 executors를 등록 (IO 바운드 작업은 쓰레드풀, 필요시 프로세스풀 사용)
        scheduler.add_executor(ThreadPoolExecutor(max_workers=os.cpu_count()), "default")
        scheduler.add_executor(ProcessPoolExecutor(max_workers=os.cpu_count()), "processpool")

        clients = await sync_to_async(list)(SocketClientConfig.objects.filter(is_used=True).all())
        setup_groups = await sync_to_async(list)(SetupGroup.objects.filter(is_active=True).all())
        for client in clients:
            try:
                # AsyncIOScheduler의 add_job은 이벤트 루프에서 안전하게 호출 가능하므로 직접 호출
                # tcp_client_servive에 잡 런타임 로깅 데코레이터를 적용하여 START/END/ERROR 로그를 남김
                try:
                    wrapped_job = log_job_runtime(logger, level=logging.WARNING, msg_prefix='JOB')(tcp_client_to_redis)
                except Exception:
                    wrapped_job = tcp_client_to_redis
                scheduler.add_job(
                    wrapped_job,
                    list(client.cron.keys())[0],
                    **list(client.cron.values())[0],
                    replace_existing=True,
                    max_instances=1,
                    misfire_grace_time=15,
                    coalesce=False,
                    executor='default',
                    args=(client,),
                )
            except Exception:
                logger.exception(f'클라이언트 작업 등록 실패: {getattr(client, "id", None)}')
            # 이벤트 루프를 블로킹하지 않도록 소량 대기
            await asyncio.sleep(0.111)
            
        for group in setup_groups:
            try:
                # AsyncIOScheduler의 add_job은 이벤트 루프에서 안전하게 호출 가능하므로 직접 호출
                # tcp_client_servive에 잡 런타임 로깅 데코레이터를 적용하여 START/END/ERROR 로그를 남김
                try:
                    wrapped_job = log_job_runtime(logger, level=logging.WARNING, msg_prefix='JOB')(setup_variables_to_redis)
                except Exception:
                    wrapped_job = setup_variables_to_redis
                scheduler.add_job(
                    wrapped_job,
                    list(group.cron.keys())[0],
                    **list(group.cron.values())[0],
                    replace_existing=True,
                    max_instances=1,
                    misfire_grace_time=15,
                    coalesce=False,
                    executor='default',
                    args=(group,),
                )
            except Exception:
                logger.exception(f'설정 그룹 작업 등록 실패: {getattr(group, "id", None)}')
            # 이벤트 루프를 블로킹하지 않도록 소량 대기
            await asyncio.sleep(0.111)

        # 전역 집계 작업은 한 번만 등록 (클라이언트 루프 밖)
        scheduler.add_job(
            redis_to_db,
            'cron',
            minute='*/2',
            replace_existing=True,
            max_instances=1,
            misfire_grace_time=15,
            coalesce=False,
            executor='default',
            args=(2,),
        )
        scheduler.add_job(
            aggregate_2min_to_10min,
            'cron',
            minute='*/10',
            second=5, # 10분 단위 집계 작업이 DB 적재 작업과 겹치지 않도록 5초 지연
            replace_existing=True,
            max_instances=1,
            misfire_grace_time=30,
            coalesce=False,
            executor='default',
        )
        scheduler.add_job(
            aggregate_to_1hour,
            'cron',
            minute=0,  # 매 정시
            second=10, # 10분 단위 집계 작업이 DB 적재 작업과 겹치지 않도록 10초 지연
            replace_existing=True,
            max_instances=1,
            misfire_grace_time=60,
            coalesce=False,
            executor='default',
        )
        scheduler.add_job(
            aggregate_to_daily,
            'cron',
            hour=0,
            minute=5,  # 자정+5분에 실행 (이전 집계 완료 여유)
            replace_existing=True,
            max_instances=1,
            misfire_grace_time=300,
            coalesce=False,
            executor='default',
        )
        # AsyncIOScheduler.start()는 동기 메서드(코루틴이 아님)이므로 await하지 않고 호출
        scheduler.start()
        logger.info("스케줄러 시작됨.")
        yield
    finally:
        # 종료 시점: scheduler가 존재하면 한 번만 완전 종료 시도
        try:
            if scheduler is not None:
                try:
                    logger.info('APScheduler 종료 중 (작업 완료 대기)')
                    # shutdown 호출 시 스케줄러가 실행중이지 않으면 SchedulerNotRunningError가 발생할 수 있으므로 처리
                    try:
                        scheduler.shutdown(wait=True)
                    except SchedulerNotRunningError:
                        logger.warning('APScheduler가 실행중이 아님 (shutdown 스킵)')
                    logger.info('APScheduler 완전 종료됨 (wait=True)')
                except Exception:
                    logger.exception('wait=True로 APScheduler 종료 실패, 강제 종료 시도')
                    try:
                        try:
                            scheduler.shutdown(wait=False)
                        except SchedulerNotRunningError:
                            logger.warning('APScheduler가 실행중이 아님 (강제 shutdown 스킵)')
                        logger.info('wait=False로 APScheduler 종료 시도됨')
                    except Exception:
                        logger.exception('APScheduler 강제 종료 실패')
            else:
                logger.info('종료할 스케줄러 인스턴스 없음')
        except Exception:
            logger.exception('스케줄러 종료 중 예외 발생')

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

