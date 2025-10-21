import logging
import asyncio
import atexit

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
        try:
            sch.start()
            _started = True
            logger.info('APScheduler started')
        except Exception:
            logger.exception('Failed to start APScheduler')
    except Exception:
        logger.exception('Unexpected error in scheduler.start')


def shutdown(wait: bool = False):
    """Shutdown the scheduler if running."""
    global scheduler, _started
    try:
        if scheduler is not None:
            try:
                scheduler.shutdown(wait=wait)
            except Exception:
                logger.exception('Error while shutting down scheduler')
        _started = False
    except Exception:
        logger.exception('Unexpected error in scheduler.shutdown')


# Ensure scheduler is shut down at process exit
atexit.register(lambda: shutdown(wait=False))
