import asyncio
from dotenv import load_dotenv
import sys, os, time, datetime

from utils.protocol.LSIS.client.tcp import LSIS_TcpClient
# .env 파일에서 환경변수 로드
load_dotenv()
pythonpath = os.getenv("PYTHONPATH")
if pythonpath and pythonpath not in sys.path:
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


sched_logger = setup_logger(name="sched_logger", log_file="./log/sched_queries.log")
scheduler = None
@log_exceptions(sched_logger)
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Starting FastAPI lifespan...")
    global scheduler
    sched_logger.info("Scheduler started.")
    scheduler = BackgroundScheduler(timezone=ZoneInfo(TIME_ZONE))
    scheduler.add_executor(ThreadPoolExecutor(max_workers=os.cpu_count()), "default")
    scheduler.add_executor(ProcessPoolExecutor(max_workers=4), "processpool")
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
    try:
        yield
    finally:
        sched_logger.info("Closing sockets...")
        scheduler.shutdown(wait=False)
        sched_logger.info("Scheduler shut down.")

app = FastAPI(title="FastAPI 스케쥴러", version="1.0", lifespan=lifespan)

