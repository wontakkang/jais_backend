"""
스케줄러 모듈

컨텍스트 저장소 관련 스케줄링 및 백그라운드 작업을 관리합니다.
네임 패턴을 표준화하고 객체지향적 접근 방식을 도입하여 유지보수성을 높였습니다.
"""

import logging
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Union, Dict, List, Callable, Any
from dataclasses import dataclass, field
from enum import Enum

from . import CONTEXT_REGISTRY
from .context import SlaveContext, ContextException
from .manager import (
    ensure_context_store_for_apps,
    restore_json_blocks_to_slave_context,
    autosave_all_contexts,
    persist_registry_state,
)
from .config import (
    get_log_file_path, ContextConfig
)

# =============================================================================
# 로거 설정
# =============================================================================
logger = logging.getLogger(__name__)
if not logger.handlers:
    log_path = get_log_file_path("context")
    handler = logging.FileHandler(log_path)
    formatter = logging.Formatter("%(asctime)s %(levelname)s [%(name)s]: %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

# =============================================================================
# 열거형 및 데이터 클래스
# =============================================================================

class SchedulerState(Enum):
    """스케줄러 상태"""
    STOPPED = "stopped"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"

class TaskStatus(Enum):
    """작업 상태"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class SchedulerStats:
    """스케줄러 통계 정보"""
    total_apps: int = 0
    active_apps: List[str] = field(default_factory=list)
    last_autosave: Optional[datetime] = None
    last_restore: Optional[datetime] = None
    autosave_count: int = 0
    restore_count: int = 0
    error_count: int = 0
    uptime_seconds: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            "total_apps": self.total_apps,
            "active_apps": self.active_apps.copy(),
            "last_autosave": self.last_autosave.isoformat() if self.last_autosave else None,
            "last_restore": self.last_restore.isoformat() if self.last_restore else None,
            "autosave_count": self.autosave_count,
            "restore_count": self.restore_count,
            "error_count": self.error_count,
            "uptime_seconds": self.uptime_seconds
        }

@dataclass
class TaskResult:
    """작업 결과"""
    task_name: str
    status: TaskStatus
    start_time: datetime
    end_time: Optional[datetime] = None
    result_data: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None
    
    @property
    def duration(self) -> Optional[timedelta]:
        """작업 실행 시간"""
        if self.end_time:
            return self.end_time - self.start_time
        return None
    
    @property
    def success(self) -> bool:
        """성공 여부"""
        return self.status == TaskStatus.COMPLETED

# =============================================================================
# 컨텍스트 스케줄러 클래스
# =============================================================================

class ContextScheduler:
    """컨텍스트 관리를 위한 스케줄러 클래스
    
    백그라운드에서 자동 저장, 복원, 정리 등의 작업을 스케줄링하고 관리합니다.
    """
    
    def __init__(self, autosave_interval: float = 300.0, project_root: Optional[Path] = None):
        """스케줄러 초기화
        
        Args:
            autosave_interval: 자동 저장 간격 (초)
            project_root: 프로젝트 루트 경로
        """
        self._state = SchedulerState.STOPPED
        self._autosave_interval = autosave_interval
        self._project_root = project_root
        
        self._stats = SchedulerStats()
        self._start_time: Optional[datetime] = None
        self._worker_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.RLock()
        
        # 작업 결과 히스토리
        self._task_history: List[TaskResult] = []
        self._max_history_size = 100
        
        logger.info(f"ContextScheduler 초기화 완료 (autosave_interval={autosave_interval}s)")
    
    @property
    def state(self) -> SchedulerState:
        """현재 스케줄러 상태"""
        return self._state
    
    @property
    def is_running(self) -> bool:
        """실행 중인지 확인"""
        return self._state == SchedulerState.RUNNING
    
    @property
    def stats(self) -> SchedulerStats:
        """통계 정보 (복사본)"""
        with self._lock:
            # 실시간 정보 업데이트
            if self._start_time:
                self._stats.uptime_seconds = (datetime.now() - self._start_time).total_seconds()
            self._stats.total_apps = len(CONTEXT_REGISTRY)
            self._stats.active_apps = list(CONTEXT_REGISTRY.keys())
            
            # 깊은 복사 대신 새 인스턴스 생성
            return SchedulerStats(
                total_apps=self._stats.total_apps,
                active_apps=self._stats.active_apps.copy(),
                last_autosave=self._stats.last_autosave,
                last_restore=self._stats.last_restore, 
                autosave_count=self._stats.autosave_count,
                restore_count=self._stats.restore_count,
                error_count=self._stats.error_count,
                uptime_seconds=self._stats.uptime_seconds
            )
    
    def start(self) -> bool:
        """스케줄러 시작"""
        with self._lock:
            if self._state != SchedulerState.STOPPED:
                logger.warning(f"스케줄러가 이미 {self._state.value} 상태입니다")
                return False
            
            try:
                self._state = SchedulerState.RUNNING
                self._start_time = datetime.now()
                self._stop_event.clear()
                
                self._worker_thread = threading.Thread(
                    target=self._worker_loop,
                    name="ContextScheduler",
                    daemon=True
                )
                self._worker_thread.start()
                
                logger.info("ContextScheduler 시작됨")
                return True
                
            except Exception as e:
                self._state = SchedulerState.STOPPED
                logger.error(f"스케줄러 시작 실패: {e}")
                return False
    
    def stop(self, timeout: float = 30.0) -> bool:
        """스케줄러 정지
        
        Args:
            timeout: 정지 대기 시간 (초)
            
        Returns:
            정지 성공 여부
        """
        with self._lock:
            if self._state == SchedulerState.STOPPED:
                return True
            
            logger.info("ContextScheduler 정지 중...")
            self._state = SchedulerState.STOPPING
            self._stop_event.set()
        
        # 워커 스레드 종료 대기
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout)
            
            if self._worker_thread.is_alive():
                logger.warning(f"워커 스레드가 {timeout}초 내에 종료되지 않음")
                return False
        
        with self._lock:
            self._state = SchedulerState.STOPPED
            self._worker_thread = None
            
        logger.info("ContextScheduler 정지됨")
        return True
    
    def pause(self) -> bool:
        """스케줄러 일시 정지"""
        with self._lock:
            if self._state != SchedulerState.RUNNING:
                return False
            
            self._state = SchedulerState.PAUSED
            logger.info("ContextScheduler 일시 정지됨")
            return True
    
    def resume(self) -> bool:
        """스케줄러 재개"""
        with self._lock:
            if self._state != SchedulerState.PAUSED:
                return False
            
            self._state = SchedulerState.RUNNING
            logger.info("ContextScheduler 재개됨")
            return True
    
    def _worker_loop(self) -> None:
        """워커 스레드 메인 루프"""
        logger.info("스케줄러 워커 스레드 시작")
        
        last_autosave = datetime.now()
        
        try:
            while not self._stop_event.is_set():
                # 일시 정지 상태 처리
                if self._state == SchedulerState.PAUSED:
                    time.sleep(1.0)
                    continue
                
                current_time = datetime.now()
                
                # 자동 저장 실행
                if (current_time - last_autosave).total_seconds() >= self._autosave_interval:
                    self._execute_autosave_task()
                    last_autosave = current_time
                
                # 짧은 대기 (중단 신호 빠른 감지)
                self._stop_event.wait(1.0)
                
        except Exception as e:
            logger.error(f"스케줄러 워커 루프 오류: {e}")
        finally:
            # 종료 시 정리 작업
            self._execute_cleanup_task()
            logger.info("스케줄러 워커 스레드 종료")
    
    def _execute_autosave_task(self) -> TaskResult:
        """자동 저장 작업 실행"""
        return self._execute_task("autosave", self._autosave_job)
    
    def _execute_cleanup_task(self) -> TaskResult:
        """정리 작업 실행"""
        return self._execute_task("cleanup", self._cleanup_contexts)
    
    def _execute_task(self, task_name: str, task_func: Callable) -> TaskResult:
        """작업 실행 및 결과 기록"""
        start_time = datetime.now()
        
        result = TaskResult(
            task_name=task_name,
            status=TaskStatus.RUNNING,
            start_time=start_time
        )
        
        try:
            logger.debug(f"작업 '{task_name}' 시작")
            task_result = task_func()
            
            result.status = TaskStatus.COMPLETED
            result.result_data = task_result if isinstance(task_result, dict) else {"success": True}
            
            logger.debug(f"작업 '{task_name}' 완료")
            
        except Exception as e:
            result.status = TaskStatus.FAILED
            result.error_message = str(e)
            
            with self._lock:
                self._stats.error_count += 1
            
            logger.error(f"작업 '{task_name}' 실패: {e}")
        
        finally:
            result.end_time = datetime.now()
            
            # 히스토리에 추가
            with self._lock:
                self._task_history.append(result)
                if len(self._task_history) > self._max_history_size:
                    self._task_history.pop(0)
        
        return result
    
    def _autosave_job(self) -> Dict[str, Any]:
        """자동 저장 작업"""
        try:
            autosave_all_contexts()
            
            with self._lock:
                self._stats.autosave_count += 1
                self._stats.last_autosave = datetime.now()
            
            return {
                "success": True,
                "apps_saved": len(CONTEXT_REGISTRY),
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            raise ContextException(f"자동 저장 실패: {e}")
    
    def _cleanup_contexts(self) -> Dict[str, Any]:
        """컨텍스트 정리 작업"""
        try:
            # 즉시 자동저장
            autosave_result = self._autosave_job()
            
            # 앱별 상태 영속화
            persist_results = self.persist_all_registry_states()
            success_count = sum(1 for success in persist_results.values() if success)
            total_count = len(persist_results)
            
            return {
                "success": True,
                "autosave_result": autosave_result,
                "persist_results": persist_results,
                "persist_success_rate": f"{success_count}/{total_count}",
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            raise ContextException(f"컨텍스트 정리 실패: {e}")
    
    def restore_contexts(self, project_root: Optional[Union[str, Path]] = None) -> Dict[str, int]:
        """모든 앱의 컨텍스트를 복원합니다"""
        result = {}
        
        try:
            root_path = Path(project_root) if project_root else self._project_root
            app_stores = ensure_context_store_for_apps(root_path)
            
            for app_name, cs_path in app_stores.items():
                try:
                    slave_ctx = SlaveContext(create_memory=None)
                    restored = restore_json_blocks_to_slave_context(
                        cs_path.parent, slave_ctx, load_most_recent=True
                    )
                    
                    CONTEXT_REGISTRY[app_name] = slave_ctx
                    restored_count = len(restored) if isinstance(restored, dict) else 0
                    result[app_name] = restored_count
                    
                    logger.info(f"앱 '{app_name}'에 대해 {restored_count}개 블록 복원됨")
                    
                except Exception as e:
                    logger.error(f"앱 '{app_name}' 컨텍스트 복원 실패: {e}")
                    result[app_name] = 0
            
            with self._lock:
                self._stats.restore_count += 1
                self._stats.last_restore = datetime.now()
            
        except Exception as e:
            logger.error(f"컨텍스트 복원 실패: {e}")
            raise ContextException(f"컨텍스트 복원 실패: {e}")
        
        return result
    
    def persist_all_registry_states(self, project_root: Optional[Union[str, Path]] = None) -> Dict[str, bool]:
        """모든 앱의 레지스트리 상태를 영속화합니다"""
        result = {}
        root_path = Path(project_root) if project_root else self._project_root
        
        try:
            for app_name in list(CONTEXT_REGISTRY.keys()):
                try:
                    written_path = persist_registry_state(app_name, root_path)
                    result[app_name] = written_path is not None
                    
                    if written_path:
                        logger.debug(f"앱 '{app_name}' 레지스트리 상태 영속화 성공")
                    else:
                        logger.warning(f"앱 '{app_name}' 레지스트리 상태 영속화 실패")
                        
                except Exception as e:
                    logger.error(f"앱 '{app_name}' 레지스트리 상태 영속화 중 오류: {e}")
                    result[app_name] = False
                    
        except Exception as e:
            logger.error(f"레지스트리 상태 영속화 실패: {e}")
            raise ContextException(f"레지스트리 상태 영속화 실패: {e}")
        
        return result
    
    def get_task_history(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """작업 히스토리를 반환합니다"""
        with self._lock:
            history = self._task_history.copy()
            
        if limit:
            history = history[-limit:]
        
        return [
            {
                "task_name": task.task_name,
                "status": task.status.value,
                "start_time": task.start_time.isoformat(),
                "end_time": task.end_time.isoformat() if task.end_time else None,
                "duration_seconds": task.duration.total_seconds() if task.duration else None,
                "success": task.success,
                "result_data": task.result_data,
                "error_message": task.error_message
            }
            for task in history
        ]
    
    def force_autosave(self) -> TaskResult:
        """강제 자동 저장 실행"""
        return self._execute_autosave_task()
    
    def get_detailed_stats(self) -> Dict[str, Any]:
        """상세 통계 정보 반환"""
        stats = self.stats.to_dict()
        
        # 컨텍스트별 상세 정보 추가
        context_details = {}
        for app_name, context in CONTEXT_REGISTRY.items():
            try:
                if hasattr(context, 'get_memory_info'):
                    memory_info = context.get_memory_info()
                else:
                    memory_info = {"type": type(context).__name__}
                
                context_details[app_name] = {
                    "context_type": type(context).__name__,
                    "memory_info": memory_info
                }
            except Exception as e:
                context_details[app_name] = {
                    "error": str(e)
                }
        
        stats["context_details"] = context_details
        stats["task_history_count"] = len(self._task_history)
        
        return stats

# =============================================================================
# 편의 함수들 (하위 호환성 유지)
# =============================================================================

def autosave_job():
    """모든 컨텍스트를 자동 저장하는 작업 함수 (하위 호환성)"""
    try:
        autosave_all_contexts()
        logger.info("autosave_job 완료")
    except Exception:
        logger.exception('autosave_job 실패')

def restore_contexts(project_root: Optional[Union[str, Path]] = None) -> Dict[str, int]:
    """모든 앱의 컨텍스트를 복원합니다 (하위 호환성)"""
    scheduler = ContextScheduler(project_root=project_root)
    return scheduler.restore_contexts(project_root)

def persist_all_registry_states(project_root: Optional[Union[str, Path]] = None) -> Dict[str, bool]:
    """모든 앱의 레지스트리 상태를 영속화합니다 (하위 호환성)"""
    scheduler = ContextScheduler(project_root=project_root)
    return scheduler.persist_all_registry_states(project_root)

def cleanup_contexts():
    """컨텍스트 정리 작업을 수행합니다 (하위 호환성)"""
    try:
        logger.info('컨텍스트 정리 시작')
        
        # 즉시 자동저장
        try:
            autosave_all_contexts()
            logger.info('정리 중 즉시 자동저장 완료')
        except Exception:
            logger.exception('정리 중 즉시 자동저장 실패')

        # 상태 영속화
        persist_results = persist_all_registry_states()
        success_count = sum(1 for success in persist_results.values() if success)
        total_count = len(persist_results)
        logger.info(f'레지스트리 상태 영속화: {success_count}/{total_count}개 앱 성공')
        
        logger.info('컨텍스트 정리 완료')
        
    except Exception:
        logger.exception('cleanup_contexts 실패')

def get_context_stats() -> Dict:
    """현재 컨텍스트 레지스트리의 통계 정보를 반환합니다 (하위 호환성)"""
    try:
        stats = {
            'total_apps': len(CONTEXT_REGISTRY),
            'app_names': list(CONTEXT_REGISTRY.keys()),
            'app_details': {}
        }
        
        for app_name, context in CONTEXT_REGISTRY.items():
            try:
                if hasattr(context, 'get_memory_info'):
                    memory_info = context.get_memory_info()
                    stats['app_details'][app_name] = {
                        'context_type': type(context).__name__,
                        'memory_info': memory_info
                    }
                else:
                    # 기존 방식으로 폴백
                    if hasattr(context, 'store') and hasattr(context.store, '__len__'):
                        store_size = len(context.store)
                    elif isinstance(context, dict) and 'store' in context:
                        store_size = len(context['store']) if isinstance(context['store'], dict) else 0
                    else:
                        store_size = 0
                        
                    stats['app_details'][app_name] = {
                        'store_size': store_size,
                        'context_type': type(context).__name__
                    }
            except Exception as e:
                stats['app_details'][app_name] = {
                    'context_type': 'unknown',
                    'error': str(e)
                }
        
        return stats
    except Exception:
        logger.exception('get_context_stats 실패')
        return {'error': 'Failed to collect stats'}