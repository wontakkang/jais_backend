import os
import sys
import time
from zoneinfo import ZoneInfo
import django
from asgiref.sync import sync_to_async
import asyncio

from jais_backend.LSISsocket.service import tcp_client_servive

sys.path.append(os.path.dirname(os.path.abspath(__file__)))  # jais_backend 폴더 경로 추가
# Django 환경 설정
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "jais_backend.py_backend.settings")
django.setup()
from LSISsocket.models import SocketClientConfig, SocketClientLog
from py_backend.settings import TIME_ZONE
from fastapi import FastAPI
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.executors.pool import ThreadPoolExecutor, ProcessPoolExecutor
from .utils.protocol.LSIS import LSIS_TcpClient
from .utils import setup_logger, log_exceptions
app = FastAPI()

sched_logger = setup_logger(name="sched_logger", log_file="./log/sched_queries.log")
scheduler = None

def run_tcp_client_service(client):
    asyncio.run(tcp_client_servive(client))

# FastAPI 시작 이벤트에서 스케줄러 실행
@log_exceptions(sched_logger)
@app.on_event("startup")
async def start_scheduler():
    global scheduler
    scheduler = BackgroundScheduler(timezone=ZoneInfo(TIME_ZONE))
    scheduler.add_executor(ThreadPoolExecutor(max_workers=os.cpu_count()), "default")
    scheduler.add_executor(ProcessPoolExecutor(max_workers=4), "processpool")
    sched_logger.info("Scheduler started.")
    
    clients = await sync_to_async(list)(SocketClientConfig.objects.filter(is_used=True).all())
    for client in clients:
        scheduler.add_job(
            run_tcp_client_service,
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
# FastAPI 종료 이벤트에서 스케줄러 종료
@app.on_event("shutdown")
async def shutdown_event():
    global scheduler
    scheduler.shutdown(wait=False)
    sched_logger.info("Scheduler shut down.")

@app.get("/")
def read_root():
    return {"message": "FastAPI + Django ORM 연동 성공"}

# 이제 Django ORM 모델을 자유롭게 import해서 사용할 수 있습니다.
# 예시: from agriseed.models import YourModel
