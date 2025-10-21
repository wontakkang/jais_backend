# context_store 관리자 유틸리티
# - 각 app 폴더에 context_store 폴더가 있는지 확인하고 없으면 생성
# - context_store 안에 파일을 생성/업데이트하는 함수 제공
# 사용 예:
#   from utils.protocol.context.manager import ensure_context_store_for_apps, create_or_update_file_for_app
#   ensure_context_store_for_apps()
#   create_or_update_file_for_app(app_dir, "state.json", created_date=datetime.datetime.now(), date_format="%Y-%m-%d")

from pathlib import Path
import json
import datetime
import logging
import shutil
import os
import threading
import time
from typing import List, Dict, Optional, Union
from contextlib import contextmanager
import importlib
from uuid import uuid4
from .store import JSONRegistersDataBlock
from .config import (
    CONTEXT_STORE_DIR_NAME, STATE_FILE_NAME, META_FILE_NAME, BACKUP_DIR_NAME,
    DEFAULT_BACKUP_POLICY, BACKUP_ENV_VARS, JSON_SETTINGS, parse_bytes_string
)
from . import CONTEXT_REGISTRY
from .context import RegistersSlaveContext

logger = logging.getLogger("context_store_manager")
if not logger.handlers:
    h = logging.StreamHandler()
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s: %(message)s"))
    logger.addHandler(h)
    logger.setLevel(logging.INFO)

# per-app locks to avoid race between save helpers and autosave/persist
_APP_LOCKS: Dict[str, threading.Lock] = {}

def _get_app_lock(app_name: str) -> threading.Lock:
    if not app_name:
        return threading.Lock()
    lock = _APP_LOCKS.get(app_name)
    if lock is None:
        lock = threading.Lock()
        _APP_LOCKS[app_name] = lock
    return lock

@contextmanager
def _file_lock(path: Union[str, Path]):
    """Cross-process exclusive lock.

    - On Windows: use a sibling lock file (state.json.lock) and msvcrt locking with non-blocking retries
      to avoid conflicts when other processes have the target file open. Falls back to a final blocking
      lock attempt before giving up.
    - On POSIX: prefer portalocker on the target file with configurable timeout/retries.

    Environment variables:
    - CONTEXT_LOCK_TIMEOUT (float seconds, default 10)
    - CONTEXT_LOCK_RETRIES (int, default 5)
    """
    file_path = Path(path)
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

    try:
        lock_timeout = float(os.getenv('CONTEXT_LOCK_TIMEOUT', '10'))
    except Exception:
        lock_timeout = 10.0
    try:
        max_attempts = int(os.getenv('CONTEXT_LOCK_RETRIES', '5'))
    except Exception:
        max_attempts = 5

    if os.name == 'nt':
        # Use directory-based lock on Windows: os.mkdir is atomic on NTFS and avoids file handle conflicts.
        lock_dir = file_path.with_suffix('.lockdir')
        start = time.time()
        acquired = False
        try:
            for attempt in range(1, max_attempts + 1):
                try:
                    os.mkdir(str(lock_dir))
                    acquired = True
                    break
                except FileExistsError:
                    # Check timeout
                    if (time.time() - start) >= lock_timeout:
                        break
                    # exponential backoff
                    time.sleep(0.05 * (2 ** (attempt - 1)))
            if not acquired:
                raise PermissionError(f"Failed to acquire dir-lock for {file_path} within timeout={lock_timeout}s")
            try:
                yield
            finally:
                try:
                    os.rmdir(str(lock_dir))
                except Exception:
                    # best-effort cleanup; leave stale lock for manual inspection
                    pass
        finally:
            return

    # POSIX or other: try portalocker on the target file
    try:
        portalocker = importlib.import_module('portalocker')
        # ensure file exists
        try:
            file_path.touch(exist_ok=True)
        except Exception:
            pass
        for attempt in range(1, max_attempts + 1):
            try:
                lock_ctx = portalocker.Lock(str(file_path), 'r+', timeout=lock_timeout)
                with lock_ctx:
                    yield
                return
            except Exception as e:
                if attempt == max_attempts:
                    raise
                wait = 0.05 * (2 ** (attempt - 1))
                logger.warning(f"portalocker lock attempt {attempt}/{max_attempts} failed for {file_path}, retrying after {wait:.3f}s: {e}")
                time.sleep(wait)
        return
    except Exception:
        # Fallback: use sibling lock file with fcntl if portalocker not available
        lock_path = Path(str(file_path) + '.lock')
        try:
            lock_path.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        f = open(lock_path, 'a')
        try:
            try:
                import fcntl
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            except Exception:
                pass
            yield
        finally:
            try:
                try:
                    import fcntl
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                except Exception:
                    pass
            finally:
                try:
                    f.close()
                except Exception:
                    pass

def _set_memory_on_slave_context(slave_context, mem_name: str, block) -> bool:
    """Safely set a memory block on a provided slave_context.

    Supports these shapes:
      - object with .store attribute that is a dict
      - dict-like registry entry with key 'store' mapping to dict
      - object exposing set_state(key, value) API
      - object exposing set_memory(key, value) API
      - fallback attempts to set attribute or index where reasonable

    Returns True if the memory was set, False otherwise.
    """
    try:
        # 1) object with .store attribute
        try:
            store_attr = getattr(slave_context, 'store', None)
        except Exception:
            store_attr = None

        if isinstance(store_attr, dict):
            store_attr[mem_name] = block
            return True
        # If .store exists but is not a dict, try to replace it with a dict
        if store_attr is not None and not isinstance(store_attr, dict):
            try:
                setattr(slave_context, 'store', {mem_name: block})
                return True
            except Exception:
                # continue to other strategies
                pass

        # 2) dict-like registry entry
        if isinstance(slave_context, dict):
            store = slave_context.setdefault('store', {})
            if isinstance(store, dict):
                store[mem_name] = block
                return True
            # try best-effort assignment
            try:
                store[mem_name] = block
                return True
            except Exception:
                pass

        # 3) set_state API
        if hasattr(slave_context, 'set_state') and callable(getattr(slave_context, 'set_state')):
            try:
                slave_context.set_state(mem_name, block)
                return True
            except Exception:
                pass

        # 4) set_memory API (some implementations may provide this)
        if hasattr(slave_context, 'set_memory') and callable(getattr(slave_context, 'set_memory')):
            try:
                slave_context.set_memory(mem_name, block)
                return True
            except Exception:
                pass

        # 5) try to set attribute directly on the object as a last resort
        try:
            setattr(slave_context, mem_name, block)
            return True
        except Exception:
            pass

    except Exception:
        logger.exception(f"_set_memory_on_slave_context unexpected error for {mem_name}")
    return False

class ContextManager:
    """Lightweight facade for module-level context store utilities.

    This minimal adapter delegates to the module-level functions so external
    callers can import and use a ContextManager object while reusing the
    existing procedural implementations.
    """
    def __init__(self, project_root: Optional[Union[str, Path]] = None):
        self.project_root = project_root

    def discover_apps(self):
        return discover_apps(self.project_root)

    def ensure_context_store_for_apps(self):
        return ensure_context_store_for_apps(self.project_root)

    def create_or_update_file_for_app(self, *args, **kwargs):
        return create_or_update_file_for_app(*args, **kwargs)

    def ensure_json_file_for_app(self, *args, **kwargs):
        return ensure_json_file_for_app(*args, **kwargs)

    def list_context_store_files(self, *args, **kwargs):
        return list_context_store_files(*args, **kwargs)

    def save_json_block_for_app(self, *args, **kwargs):
        return save_json_block_for_app(*args, **kwargs)

    def load_all_json_blocks_for_app(self, *args, **kwargs):
        return load_all_json_blocks_for_app(*args, **kwargs)

    def load_most_recent_json_block_for_app(self, *args, **kwargs):
        return load_most_recent_json_block_for_app(*args, **kwargs)

    def restore_json_blocks_to_slave_context(self, *args, **kwargs):
        return restore_json_blocks_to_slave_context(*args, **kwargs)

    def upsert_processed_data_into_state(self, *args, **kwargs):
        return upsert_processed_data_into_state(*args, **kwargs)

    def upsert_processed_block_into_state(self, *args, **kwargs):
        return upsert_processed_block_into_state(*args, **kwargs)

    def save_status_with_meta(self, *args, **kwargs):
        return save_status_with_meta(*args, **kwargs)

    def save_status_nested(self, *args, **kwargs):
        return save_status_nested(*args, **kwargs)

    def save_status_path(self, *args, **kwargs):
        return save_status_path(*args, **kwargs)

    def save_block_top_level(self, *args, **kwargs):
        return save_block_top_level(*args, **kwargs)

    def save_setup(self, *args, **kwargs):
        return save_setup(*args, **kwargs)

    def get_or_create_registry_entry(self, app_name: str, create_slave: bool = True):
        return get_or_create_registry_entry(app_name, create_slave=create_slave)

    def autosave_all_contexts(self):
        return autosave_all_contexts(self.project_root)

    def persist_registry_state(self, *args, **kwargs):
        return persist_registry_state(*args, **kwargs)

    def backup_state_for_app(self, *args, **kwargs):
        return backup_state_for_app(*args, **kwargs)

    def backup_all_states(self, *args, **kwargs):
        return backup_all_states(*args, **kwargs)

    def generate_meta_from_state_for_apps(self, *args, **kwargs):
        return generate_meta_from_state_for_apps(*args, **kwargs)

def _infer_project_root() -> Path:
    # 이 파일 위치로부터 프로젝트 루트 추론: utils/protocol/context -> 상위 3단계가 프로젝트 루트
    return Path(__file__).resolve().parents[3]


def discover_apps(project_root: Optional[Union[str, Path]] = None) -> List[Path]:
    """프로젝트 루트에서 Django 앱으로 보이는 폴더들을 반환한다.

    판별 기준: 폴더 안에 apps.py 또는 models.py 또는 views.py 또는 admin.py 중 하나 이상이 존재하면 앱으로 간주.
    """
    root = Path(project_root) if project_root is not None else _infer_project_root()
    apps = []
    for child in root.iterdir():
        if not child.is_dir():
            continue
        # 숨김 폴더 및 가상환경 등 제외
        if child.name.startswith(".") or child.name in {"venv", "env", "__pycache__", "log", "LSIS_socket"}:
            continue
        # 앱 여부 확인
        has_app_file = any((child / fname).exists() for fname in ("apps.py", "models.py", "views.py", "admin.py"))
        if has_app_file:
            apps.append(child)
    return apps


def ensure_context_store_for_apps(project_root: Optional[Union[str, Path]] = None) -> Dict[str, Path]:
    """모든 앱 폴더에 context_store 디렉터리가 존재하는지 확인하고 없으면 생성한다.

    반환값: {app_name: Path_to_context_store}
    """
    root = Path(project_root) if project_root is not None else _infer_project_root()
    apps = discover_apps(root)
    result = {}
    for app in apps:
        cs_path = app / CONTEXT_STORE_DIR_NAME
        if not cs_path.exists():
            cs_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created context_store: {cs_path}")
        else:
            logger.debug(f"context_store exists: {cs_path}")
        result[app.name] = cs_path
    return result


def _format_date(dt: Optional[Union[str, datetime.datetime]], fmt: str) -> str:
    if dt is None:
        return datetime.datetime.now().strftime(fmt)
    if isinstance(dt, datetime.datetime):
        return dt.strftime(fmt)
    # 문자열인 경우, 가능한 한 파싱 시도
    try:
        # 우선 ISO 포맷 시도
        parsed = datetime.datetime.fromisoformat(str(dt))
        return parsed.strftime(fmt)
    except Exception:
        # 파싱 실패하면 원 문자열을 그대로 사용
        return str(dt)


def create_or_update_file_for_app(
    app_path: Union[str, Path],
    filename: str,
    created_date: Optional[Union[str, datetime.datetime]] = None,
    date_format: str = "%Y-%m-%d %H:%M:%S",
    content: str = "",
    metadata: Optional[dict] = None,
) -> Path:
    """지정된 앱의 context_store에 파일을 생성하거나 업데이트한다.

    - app_path: 앱 폴더 경로 또는 이름(절대경로 권장)
    - filename: context_store 내 생성할 파일명 (예: state.json)
    - created_date: 생성일자(문자열 또는 datetime). None 이면 현재시간 사용
    - date_format: 생성일자를 포맷할 형식
    - content: 파일의 실제 내용(문자열)
    - metadata: 추가 메타데이터(dict). 저장 시 .meta.json을 함께 생성/업데이트

    반환값: 생성/업데이트된 파일의 Path
    """
    app_p = Path(app_path)
    if not app_p.exists() or not app_p.is_dir():
        raise FileNotFoundError(f"앱 경로를 찾을 수 없습니다: {app_path}")

    cs_dir = app_p / CONTEXT_STORE_DIR_NAME
    cs_dir.mkdir(parents=True, exist_ok=True)

    file_path = cs_dir / filename
    # 메타 파일은 각 파일별로 만들지 않고 context_store/meta.json 으로 통합
    meta_path = cs_dir / META_FILE_NAME

    # 파일 생성/업데이트
    formatted_date = _format_date(created_date, date_format)
    header = f"# created: {formatted_date}\n# filename: {filename}\n# app: {app_p.name}\n\n"

    # 기존 내용이 있을 경우 덮어쓰기(업데이트)
    with file_path.open("w", encoding="utf-8") as f:
        f.write(header)
        f.write(content)

    meta = {
        "filename": filename,
        "app": app_p.name,
        "created": formatted_date,
        "created_raw": created_date.isoformat() if isinstance(created_date, datetime.datetime) else created_date,
        "updated": datetime.datetime.now().isoformat(),
    }
    if metadata:
        meta.update(metadata)

    with meta_path.open("w", encoding="utf-8") as mf:
        json.dump(meta, mf, ensure_ascii=False, indent=2)

    logger.info(f"Created/Updated file: {file_path} (meta: {meta_path})")
    return file_path


def ensure_json_file_for_app(
    app_path: Union[str, Path],
    filename: str = "state.json",
    payload: Optional[object] = None,
    created_date: Optional[Union[str, datetime.datetime]] = None,
    date_format: str = "%Y-%m-%d %H:%M:%S",
    metadata: Optional[dict] = None,
) -> Path:
    """앱의 context_store 안에 filename이 없으면 기본 JSON 파일과 메타를 생성한다.

    payload가 None이면 빈 객체({})를 저장한다.
    반환값: 생성된 파일의 Path
    """
    app_p = Path(app_path)
    if not app_p.exists() or not app_p.is_dir():
        raise FileNotFoundError(f"앱 경로를 찾을 수 없습니다: {app_path}")

    cs_dir = app_p / CONTEXT_STORE_DIR_NAME
    cs_dir.mkdir(parents=True, exist_ok=True)

    file_path = cs_dir / filename
    # 통합 meta.json 사용
    meta_path = cs_dir / META_FILE_NAME

    if file_path.exists():
        return file_path

    formatted_date = _format_date(created_date, date_format)

    if payload is None:
        payload = {}

    try:
        with file_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

        meta = {
            "filename": filename,
            "app": app_p.name,
            "created": formatted_date,
            "created_raw": created_date.isoformat() if isinstance(created_date, datetime.datetime) else created_date,
            "updated": datetime.datetime.now().isoformat(),
        }
        if metadata:
            meta.update(metadata)

        with meta_path.open("w", encoding="utf-8") as mf:
            json.dump(meta, mf, ensure_ascii=False, indent=2)

        logger.info(f"Ensured JSON file created: {file_path} (meta: {meta_path})")
    except Exception:
        logger.exception(f"Failed to create ensured json file: {file_path}")
        raise

    return file_path


def list_context_store_files(app_path: Union[str, Path]) -> List[Path]:
    """지정된 앱의 context_store 내부 파일 목록을 반환"""
    app_p = Path(app_path)
    cs_dir = app_p / CONTEXT_STORE_DIR_NAME
    if not cs_dir.exists():
        return []
    return [p for p in cs_dir.iterdir() if p.is_file()]


def save_json_block_for_app(
    app_path: Union[str, Path],
    filename: str,
    block,
    created_date: Optional[Union[str, datetime.datetime]] = None,
    date_format: str = "%Y-%m-%d %H:%M:%S",
    metadata: Optional[dict] = None,
) -> Path:
    """JSONRegistersDataBlock 인스턴스를 context_store에 저장한다.

    - filename은 예: "%MB.json" 또는 "state.json" 등
    - block은 to_json() 메서드를 제공하는 객체여야 함
    """
    app_p = Path(app_path)
    if not app_p.exists() or not app_p.is_dir():
        raise FileNotFoundError(f"앱 경로를 찾을 수 없습니다: {app_path}")

    cs_dir = app_p / CONTEXT_STORE_DIR_NAME
    cs_dir.mkdir(parents=True, exist_ok=True)

    file_path = cs_dir / filename
    # 통합 meta.json 사용
    meta_path = cs_dir / META_FILE_NAME

    formatted_date = _format_date(created_date, date_format)

    # JSON 저장
    try:
        payload = block.to_json() if hasattr(block, "to_json") else block
    except Exception:
        payload = block

    # Acquire cross-process lock while writing this file
    with _file_lock(file_path):
        with file_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    meta = {
        "filename": filename,
        "app": app_p.name,
        "created": formatted_date,
        "created_raw": created_date.isoformat() if isinstance(created_date, datetime.datetime) else created_date,
        "updated": datetime.datetime.now().isoformat(),
    }
    if metadata:
        meta.update(metadata)

    with meta_path.open("w", encoding="utf-8") as mf:
        json.dump(meta, mf, ensure_ascii=False, indent=2)

    logger.info(f"Saved JSON block: {file_path} (meta: {meta_path})")
    return file_path


def load_all_json_blocks_for_app(app_path: Union[str, Path]) -> Dict[str, object]:
    """앱의 context_store에서 모든 .json 파일을 로드하여 딕셔너리로 반환한다.

    반환: {stem_without_ext: JSON object 또는 block instance}
    - .meta.json 파일은 무시한다
    - 파일 내용에 'values' 키가 있을 경우 그대로 반환(나중에 JSONRegistersDataBlock.from_json 사용 가능)
    """
    app_p = Path(app_path)
    cs_dir = app_p / CONTEXT_STORE_DIR_NAME
    result = {}
    if not cs_dir.exists():
        return result

    for p in cs_dir.glob("*.json"):
        # 통합 meta 파일(meta.json)은 무시
        if p.name == META_FILE_NAME:
            continue
        try:
            # Acquire cross-process lock while reading this file
            with _file_lock(p):
                with p.open("r", encoding="utf-8") as f:
                    obj = json.load(f)
            key = p.stem  # 파일명에서 확장자 제거
            result[key] = obj
        except Exception:
            logger.exception(f"Failed to load json block: {p}")
    return result


def load_most_recent_json_block_for_app(app_path: Union[str, Path]):
    """context_store에서 가장 최근에 수정된 .json 파일을 로드하여 반환한다.

    반환: (filename_stem, obj) 또는 (None, None) if not found
    """
    app_p = Path(app_path)
    cs_dir = app_p / CONTEXT_STORE_DIR_NAME
    if not cs_dir.exists():
        return None, None

    # meta.json은 데이터 파일이 아니므로 제외
    candidates = [p for p in cs_dir.glob("*.json") if p.name != META_FILE_NAME]
    if not candidates:
        # .json 파일이 하나도 없을 경우 기본 state.json을 생성하고 이를 반환
        try:
            created = ensure_json_file_for_app(app_p, filename=STATE_FILE_NAME, payload={})
            with _file_lock(created):
                with created.open("r", encoding="utf-8") as f:
                    obj = json.load(f)
            return created.stem, obj
        except Exception:
            logger.exception(f"Failed to create or load default json in {cs_dir}")
            return None, None

    # 최신 수정시간 기준으로 가장 최근 파일 선택
    latest = max(candidates, key=lambda p: p.stat().st_mtime)
    try:
        with _file_lock(latest):
            with latest.open("r", encoding="utf-8") as f:
                obj = json.load(f)
        return latest.stem, obj
    except Exception:
        logger.exception(f"Failed to load most recent json block: {latest}")
        return None, None


def _normalize_json_block_for_restore(obj):
    """Normalize a JSON block loaded from state/context_store for restoration.

    - If obj is a list, wrap into {'values': {"0": v0, ...}}
    - If obj['values'] is a list, convert to dict with string indices: {'0': v0, '1': v1, ...}
    - Preserve other keys (address, default_value, type).
    Returns the normalized object (may be same instance or a shallow copy).
    """
    try:
        # If top-level is a list (some state entries store values directly), wrap it
        if isinstance(obj, list):
            try:
                new_vals = {str(i): v for i, v in enumerate(obj)}
                return {'values': new_vals}
            except Exception:
                return {'values': {str(i): v for i, v in enumerate(obj)}}

        if not isinstance(obj, dict):
            return obj
        vals = obj.get('values')
        if isinstance(vals, list):
            # convert list to dict with string indices
            try:
                new_vals = {str(i): v for i, v in enumerate(vals)}
                # create shallow copy to avoid mutating original source
                new_obj = dict(obj)
                new_obj['values'] = new_vals
                return new_obj
            except Exception:
                return obj
        return obj
    except Exception:
        return obj


def restore_json_blocks_to_slave_context(
    app_path: Union[str, Path],
    slave_context,
    load_most_recent: bool = False,
    use_key_as_memory_name: bool = True,
):
    """앱의 context_store에서 JSON 블록을 읽어주어 slave_context.store에 복원한다.

    - load_most_recent: True이면 가장 최근 파일 하나만 로드
    - use_key_as_memory_name: 파일 stem을 memory key로 사용 (예: "%MB"), False면 파일명을 그대로 사용
    """
    app_p = Path(app_path)
    if not app_p.exists() or not app_p.is_dir():
        raise FileNotFoundError(f"앱 경로를 찾을 수 없습니다: {app_path}")

    # container for restored blocks (used by both single and all-file paths)
    restored = {}

    if load_most_recent:
        stem, obj = load_most_recent_json_block_for_app(app_p)
        if not stem:
            return {}
        # If the most recent file is the aggregated state.json containing MEMORY maps, handle it specially
        if stem == STATE_FILE_NAME.replace('.json', '') and isinstance(obj, dict):
            try:
                # iterate keys in state.json (e.g. '192.168.0.198:2004') and their MEMORY maps
                for serial_key, entry in obj.items():
                    if not isinstance(entry, dict):
                        continue
                    mem_map = entry.get('MEMORY') if isinstance(entry.get('MEMORY'), dict) else None
                    if not mem_map:
                        continue
                    for mem_name, mem_obj in mem_map.items():
                        try:
                            norm = _normalize_json_block_for_restore(mem_obj)
                            block = JSONRegistersDataBlock.from_json(norm) if isinstance(norm, dict) and 'values' in norm else norm
                            _set_memory_on_slave_context(slave_context, mem_name, block)
                            restored[mem_name] = block
                        except Exception:
                            logger.exception(f"Failed to restore memory {mem_name} from state.json entry {serial_key}")
                logger.info(f"Restored {len(restored)} MEMORY blocks from state.json into slave_context for app {app_p.name}")
                return restored
            except Exception:
                logger.exception('Failed to process aggregated state.json for restore')
                # fallback to normal single-file handling below
        # 기존 처리
        # 메모리 이름 결정
        mem_name = stem if use_key_as_memory_name else (stem + ".json")
        try:
            # Normalize list values -> dict for backward compatibility
            obj = _normalize_json_block_for_restore(obj)
            # JSONRegistersDataBlock 형태라면 from_json 사용
            if isinstance(obj, dict) and "values" in obj:
                block = JSONRegistersDataBlock.from_json(obj)
            else:
                block = obj
            if not _set_memory_on_slave_context(slave_context, mem_name, block):
                raise AttributeError("slave_context does not support .store or set_state to assign memory blocks")
            restored[mem_name] = block
            logger.info(f"Restored '{mem_name}' into slave_context from {stem}.json")
            return {mem_name: block}
        except Exception:
            logger.exception(f"Failed to restore most recent json block: {stem}")
            return {}

    # load all
    objs = load_all_json_blocks_for_app(app_p)
    restored = {}
    for stem, obj in objs.items():
        # If this file is the aggregated state.json, extract MEMORY entries and restore them
        if stem == STATE_FILE_NAME.replace('.json', '') and isinstance(obj, dict):
            try:
                for serial_key, entry in obj.items():
                    if not isinstance(entry, dict):
                        continue
                    mem_map = entry.get('MEMORY') if isinstance(entry.get('MEMORY'), dict) else None
                    if not mem_map:
                        continue
                    for mem_name, mem_obj in mem_map.items():
                        try:
                            norm = _normalize_json_block_for_restore(mem_obj)
                            block = JSONRegistersDataBlock.from_json(norm) if isinstance(norm, dict) and 'values' in norm else norm
                            if _set_memory_on_slave_context(slave_context, mem_name, block):
                                restored[mem_name] = block
                        except Exception:
                            logger.exception(f"Failed to restore memory {mem_name} from state.json entry {serial_key}")
            except Exception:
                logger.exception('Failed to process aggregated state.json during load_all')
            continue
        mem_name = stem if use_key_as_memory_name else (stem + ".json")
        try:
            # Normalize list values -> dict for backward compatibility
            obj = _normalize_json_block_for_restore(obj)
            if isinstance(obj, dict) and "values" in obj:
                block = JSONRegistersDataBlock.from_json(obj)
            else:
                block = obj
            if not _set_memory_on_slave_context(slave_context, mem_name, block):
                logger.error(f"Unable to restore memory '{mem_name}' into provided slave_context (unsupported type)")
            else:
                restored[mem_name] = block
        except Exception:
            logger.exception(f"Failed to restore json block: {stem}")
    logger.info(f"Restored {len(restored)} blocks into slave_context for app {app_p.name}")
    return restored


def _merge_lists(a, b, dedup: bool = False, sort: bool = False):
    """리스트 병합: 기본은 a + b.
    - dedup: True이면 순서를 유지하면서 중복을 제거(해시 불가능 항목은 안전하게 처리)
    - sort: True이면 결과를 정렬(가능한 경우). sort는 dedup 이후에 적용.
    """
    if not isinstance(a, list) or not isinstance(b, list):
        return b
    combined = list(a) + list(b)
    if not dedup and not sort:
        return combined

    # 중복 제거 (순서 유지)
    if dedup:
        seen = set()
        result = []
        for item in combined:
            try:
                key = item if isinstance(item, (str, int, float, bool, tuple)) else json.dumps(item, sort_keys=True)
            except Exception:
                # JSON 직렬화 실패하면 repr로 fallback
                key = repr(item)
            if key in seen:
                continue
            seen.add(key)
            result.append(item)
    else:
        result = combined

    if sort:
        try:
            result = sorted(result)
        except Exception:
            # 정렬 불가능한 항목이 섞여 있으면 무시
            pass
    return result


def _deep_merge_with_list_option(dest, src, list_merge: Union[bool, dict] = False):
    """딕셔너리 재귀 병합. list_merge는 다음을 허용:
    - False: 리스트는 src로 교체
    - True: 리스트는 append (a + b)
    - dict: 옵션을 지정할 수 있음 {'dedup': bool, 'sort': bool}
    """
    if not isinstance(dest, dict) or not isinstance(src, dict):
        return src
    result = dict(dest)

    # 해석
    lm_dedup = False
    lm_sort = False
    lm_append = False
    if isinstance(list_merge, dict):
        lm_dedup = bool(list_merge.get('dedup'))
        lm_sort = bool(list_merge.get('sort'))
        lm_append = True if (list_merge.get('mode') == 'append' or not list_merge.get('mode')) else False
    else:
        lm_append = bool(list_merge)

    for k, v in src.items():
        if k in result:
            a = result[k]
            b = v
            if isinstance(a, dict) and isinstance(b, dict):
                result[k] = _deep_merge_with_list_option(a, b, list_merge)
            elif isinstance(a, list) and isinstance(b, list):
                if isinstance(list_merge, dict):
                    # dict 옵션 사용: dedup/sort 가능
                    result[k] = _merge_lists(a, b, dedup=lm_dedup, sort=lm_sort)
                else:
                    # boolean: True -> append, False -> replace
                    result[k] = (a + b) if lm_append else b
            else:
                result[k] = b
        else:
            result[k] = v
    return result


def _find_matching_key(d: dict, desired_key: str):
    """Find an existing key in dict d that matches desired_key under normalization.
    Returns the existing key if found, otherwise None.
    Normalization is performed inline here (lowercase, remove spaces/underscores, and a few common typo corrections).
    """
    if not isinstance(d, dict):
        return None
    try:
        def _norm(s: str) -> str:
            t = str(s).strip().lower()
            t = t.replace(' ', '').replace('_', '')
            # minor common typo corrections kept inline
            t = t.replace('ditital', 'digital')
            t = t.replace('threshod', 'threshold')
            t = t.replace('thresold', 'threshold')
            t = t.replace('theshold', 'threshold')
            return t

        norm_desired = _norm(desired_key)
        for existing in d.keys():
            try:
                if _norm(existing) == norm_desired:
                    return existing
            except Exception:
                continue
    except Exception:
        return None
    return None


def upsert_processed_block_into_state(app_path_or_name: Union[str, Path], serial: str, block: dict, list_merge: Union[bool, dict] = False, commands: Optional[list] = None, project_root: Optional[Union[str, Path]] = None):
    """블록(block) 내부의 모든(또는 지정된) 커맨드의 processed_data를 한 번의 원자적 쓰기로 state.json에 병합 저장합니다.

    - block: 예시 구조:
      {"ANALOG_READ_ALL": {"request":..., "response":..., "processed_data": {...}}, "OTHER_CMD": {...}}
    - commands: 리스트로 특정 커맨드만 처리하고 싶을 때 사용 (None이면 block에 있는 모든 커맨드 처리)
    - list_merge: 리스트 병합 동작. _deep_merge_with_list_option과 동일한 형식 허용
    - 반환: 저장된 state.json Path 또는 None
    """
    try:
        # 앱 경로/이름 해석
        app_p = None
        if isinstance(app_path_or_name, (str,)):
            candidate = Path(app_path_or_name)
            if candidate.exists() and candidate.is_dir():
                app_p = candidate
            else:
                app_stores = ensure_context_store_for_apps(project_root)
                cs_path = app_stores.get(app_path_or_name)
                if cs_path:
                    app_p = Path(cs_path).parent
                else:
                    root = Path(project_root) if project_root else _infer_project_root()
                    candidate2 = root / app_path_or_name
                    if candidate2.exists() and candidate2.is_dir():
                        app_p = candidate2
        elif isinstance(app_path_or_name, Path):
            app_p = app_path_or_name
        else:
            app_p = Path(app_path_or_name)

        if app_p is None or not app_p.exists():
            logger.error(f"upsert_processed_block_into_state: app not found: {app_path_or_name}")
            return None

        cs_dir = app_p / CONTEXT_STORE_DIR_NAME
        cs_dir.mkdir(parents=True, exist_ok=True)
        state_path = cs_dir / STATE_FILE_NAME

        # Load existing state once
        existing_state = {}
        if state_path.exists():
            try:
                with state_path.open('r', encoding='utf-8') as f:
                    existing_state = json.load(f)
            except Exception:
                logger.exception(f"Failed to load existing state.json for upsert_block: {state_path}")
                existing_state = {}

        if not isinstance(existing_state, dict):
            existing_state = {}

        entry = existing_state.get(serial)
        if not isinstance(entry, dict):
            entry = {}

        # Iterate commands in block
        for cmd_name, cmd_val in (block.items() if commands is None else ((k, block.get(k)) for k in commands)):
            if not isinstance(cmd_val, dict):
                continue
            if 'processed_data' not in cmd_val:
                continue
            new_proc = cmd_val.get('processed_data', {})
            if not isinstance(new_proc, dict):
                # 비정상 처리 데이터면 교체
                merged_proc = new_proc
            else:
                existing_cmd = entry.get(cmd_name, {})
                existing_proc = existing_cmd.get('processed_data', {}) if isinstance(existing_cmd.get('processed_data', {}), dict) else {}
                try:
                    merged_proc = _deep_merge_with_list_option(existing_proc, new_proc, list_merge=list_merge)
                except Exception:
                    merged_proc = new_proc
            cmd_obj = entry.get(cmd_name, {}) if isinstance(entry.get(cmd_name, {}), dict) else {}
            cmd_obj['processed_data'] = merged_proc
            entry[cmd_name] = cmd_obj

        existing_state[serial] = entry

        # Atomic write once
        try:
            written = _atomic_write_json(state_path, existing_state)
            logger.info(f"Upserted processed block for serial {serial} into {written} (commands={commands}, list_merge={list_merge})")
            return written
        except Exception:
            logger.exception(f"Failed to write state.json during upsert_block for {serial}")
            return None
    except Exception:
        logger.exception("upsert_processed_block_into_state failed")
        return None


def generate_meta_from_state_for_apps(project_root: Optional[Union[str, Path]] = None, app_names: Optional[List[str]] = None, backup: bool = True) -> Dict[str, Dict]:
    """state.json은 존재하지만 meta.json이 없는 앱들에 대해 기본 meta.json을 생성한다.

    - project_root: 앱 탐색에 사용할 루트(없으면 자동 추론)
    - app_names: 처리할 앱 이름 리스트(없으면 모든 앱)
    - backup: 기존 meta.json이 없지만 백업 디렉터리를 만들고 싶다면 True

    반환: {app_name: {'created': bool, 'path': str or None, 'error': str or None}}
    """
    results: Dict[str, Dict] = {}
    app_stores = ensure_context_store_for_apps(project_root)

    for app_name, cs_path in app_stores.items():
        if app_names and app_name not in app_names:
            continue
        res = {'created': False, 'path': None, 'error': None}
        try:
            cs_dir = Path(cs_path)
            state_path = cs_dir / STATE_FILE_NAME
            meta_path = cs_dir / META_FILE_NAME

            if not state_path.exists():
                res['error'] = 'no state.json'
                results[app_name] = res
                continue
            if meta_path.exists():
                res['error'] = 'meta.json already exists'
                results[app_name] = res
                continue

            # state 파일의 메타 정보를 기반으로 기본 meta 생성
            try:
                created_mtime = datetime.datetime.fromtimestamp(state_path.stat().st_mtime)
                created_str = _format_date(created_mtime, "%Y-%m-%d %H:%M:%S")
            except Exception:
                created_mtime = None
                created_str = _format_date(None, "%Y-%m-%d %H:%M:%S")

            meta = {
                'filename': 'state.json',
                'app': app_name,
                'created': created_str,
                'created_raw': created_mtime.isoformat() if isinstance(created_mtime, datetime.datetime) else None,
                'updated': datetime.datetime.now().isoformat(),
            }

            # write meta.json atomically
            try:
                with meta_path.open('w', encoding='utf-8') as mf:
                    json.dump(meta, mf, ensure_ascii=False, indent=2)
                res['created'] = True
                res['path'] = str(meta_path)
            except Exception as e:
                res['error'] = f'write_failed:{e}'
                results[app_name] = res
                continue

            # optional backup folder creation (for symmetry with migrate tool)
            if backup:
                try:
                    backup_dir = cs_dir / BACKUP_DIR_NAME
                    backup_dir.mkdir(parents=True, exist_ok=True)
                except Exception:
                    # 비치명 : 백업 실패는 치명적이지 않음
                    pass

        except Exception as e:
            res['error'] = str(e)
        results[app_name] = res
    return results


def get_or_create_registry_entry(app_name: str, create_slave: bool = True):
    """CONTEXT_REGISTRY에서 앱 엔트리를 가져오거나 생성합니다.

    반환값은 RegistersSlaveContext 인스턴스 또는 dict 구조({'store': {'state': {...}}})입니다.
    """
    try:
        entry = CONTEXT_REGISTRY.get(app_name)
        if entry:
            return entry
        if not create_slave:
            return None
        try:
            ctx = RegistersSlaveContext(createMemory=None)
            CONTEXT_REGISTRY[app_name] = ctx
            logger.info(f"Created RegistersSlaveContext for registry app: {app_name}")
            return ctx
        except Exception:
            logger.exception(f"Failed to create RegistersSlaveContext for {app_name}, falling back to dict store")
            fallback = {"store": {"state": {}}}
            CONTEXT_REGISTRY[app_name] = fallback
            return fallback
    except Exception:
        logger.exception('get_or_create_registry_entry 예외 발생')
        return None


def _atomic_write_json(file_path: Path, payload) -> Path:
    """Write JSON payload atomically to file_path by writing to a temp file and replacing.
    Uses a unique temp filename per-process to avoid collisions across processes.
    """
    file_path = Path(file_path)
    # unique temp filename to avoid cross-process collisions
    temp_path = file_path.with_suffix(f'.{os.getpid()}.{uuid4().hex}.tmp')
    # Ensure parent exists
    file_path.parent.mkdir(parents=True, exist_ok=True)
    # Acquire cross-process lock on the target file while performing atomic write
    with _file_lock(file_path):
        try:
            with temp_path.open('w', encoding='utf-8') as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
                f.flush()
                try:
                    os.fsync(f.fileno())
                except Exception:
                    # fsync may not be available in some environments; ignore if fails
                    pass
            # Use os.replace for atomic rename (works on Windows and POSIX).
            # On Windows another process may hold the target for a short time -> retry with backoff.
            max_attempts = 6
            for attempt in range(1, max_attempts + 1):
                try:
                    os.replace(str(temp_path), str(file_path))
                    break
                except PermissionError as e:
                    # Log and retry with backoff
                    wait = 0.02 * (2 ** (attempt - 1))
                    logger.warning(f"os.replace PermissionError on attempt {attempt}/{max_attempts} for {file_path}, retrying after {wait:.3f}s: {e}")
                    if attempt == max_attempts:
                        # re-raise to be handled by outer logic
                        raise
                    time.sleep(wait)
                except Exception:
                    # Non-PermissionError -> re-raise immediately
                    raise
        finally:
            try:
                # clean up any leftover temp files matching the pattern for this PID if present
                if temp_path.exists():
                    try:
                        temp_path.unlink()
                    except Exception:
                        pass
                # also try to remove any other stale temp files created by this process
                prefix = f"{file_path.stem}.{os.getpid()}."
                for p in file_path.parent.glob(f"{file_path.stem}.{os.getpid()}.*.tmp"):
                    try:
                        p.unlink()
                    except Exception:
                        pass
            except Exception:
                pass
    return file_path


def _deep_merge_overwrite(dest, src):
    """재귀적으로 dict를 병합합니다. src의 값이 있으면 dest을 덮어씁니다.
    리스트나 dict 이외의 타입은 src로 완전히 대체됩니다.
    """
    if not isinstance(dest, dict) or not isinstance(src, dict):
        return src
    result = dict(dest)
    for k, v in src.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge_overwrite(result[k], v)
        else:
            result[k] = v
    return result


def upsert_processed_data_into_state(app_path_or_name: Union[str, Path], serial: str, processed_data: dict, project_root: Optional[Union[str, Path]] = None):
    """state.json 안에서 serial 키에 대해 processed_data를 생성하거나 덮어씁니다.

    동작:
    - app_path_or_name이 앱 폴더명(예: 'MCUnode')이면 프로젝트에서 context_store 경로를 찾습니다.
    - app_path_or_name이 경로이면 해당 앱의 context_store를 사용합니다.
    - 기존 state.json을 로드한 후 serial 키에 대해 딥 머지(기존 값 보존, 새 값으로 덮어쓰기)를 수행합니다.
    - 원자적 파일 쓰기를 사용하여 저장합니다.

    반환값: 저장된 state.json의 Path 또는 None(실패시)
    """
    try:
        # app_path_or_name이 앱 폴더명인지 경로인지 판단
        app_p = None
        if isinstance(app_path_or_name, (str,)):
            # 문자열이 경로일 수도 있고 앱 이름일 수도 있으므로 우선 경로로 해석
            candidate = Path(app_path_or_name)
            if candidate.exists() and candidate.is_dir():
                app_p = candidate
            else:
                # 앱 이름으로 검색
                app_stores = ensure_context_store_for_apps(project_root)
                cs_path = app_stores.get(app_path_or_name)
                if cs_path:
                    app_p = Path(cs_path).parent
                else:
                    # 마지막 시도로 프로젝트 루트 아래 app 폴더를 추정
                    root = Path(project_root) if project_root else _infer_project_root()
                    candidate2 = root / app_path_or_name
                    if candidate2.exists() and candidate2.is_dir():
                        app_p = candidate2
        elif isinstance(app_path_or_name, Path):
            app_p = app_path_or_name
        else:
            app_p = Path(app_path_or_name)

        if app_p is None or not app_p.exists():
            logger.error(f"upsert_processed_data_into_state: app not found: {app_path_or_name}")
            return None

        cs_dir = app_p / CONTEXT_STORE_DIR_NAME
        cs_dir.mkdir(parents=True, exist_ok=True)
        state_path = cs_dir / STATE_FILE_NAME

        # 기존 상태 로드
        existing_state = {}
        if state_path.exists():
            try:
                with state_path.open('r', encoding='utf-8') as f:
                    existing_state = json.load(f)
            except Exception:
                logger.exception(f"Failed to load existing state.json for upsert: {state_path}")
                existing_state = {}

        if not isinstance(existing_state, dict):
            existing_state = {}

        # 기존 항목과 병합
        current_entry = existing_state.get(serial, {}) if isinstance(existing_state.get(serial, {}), dict) else existing_state.get(serial, {})
        try:
            merged = _deep_merge_overwrite(current_entry, processed_data)
        except Exception:
            # 실패 시 단순 교체
            merged = processed_data

        existing_state[serial] = merged

        # 원자적 쓰기
        try:
            written = _atomic_write_json(state_path, existing_state)
            logger.info(f"Upserted processed_data for serial {serial} into {written}")
            return written
        except Exception:
            logger.exception(f"Failed to write state.json during upsert for {serial}")
            return None

    except Exception:
        logger.exception("upsert_processed_data_into_state failed")
        return None


from copy import deepcopy

def autosave_all_contexts(project_root: Optional[Union[str, Path]] = None):
    """현재 CONTEXT_REGISTRY에 존재하는 모든 앱의 상태를 저장합니다.
    - project_root: 앱 탐색에 사용할 루트(없으면 자동 추론)
    """
    for app_name in list(CONTEXT_REGISTRY.keys()):
        try:
            entry = CONTEXT_REGISTRY.get(app_name)
            # 상태 추출 (get_all_state 우선, 그 외 dict 형태에서 추출)
            if hasattr(entry, 'get_all_state') and callable(getattr(entry, 'get_all_state')):
                state = entry.get_all_state()
            elif isinstance(entry, dict):
                state = entry.get('store', {}).get('state', {})
            else:
                store_attr = getattr(entry, 'store', None)
                state = store_attr.get('state', {}) if isinstance(store_attr, dict) else {}

            if not isinstance(state, dict):
                try:
                    state = dict(state)
                except Exception:
                    state = {}

            # 앱의 context_store 경로 결정
            app_stores = ensure_context_store_for_apps(project_root)
            cs_path = app_stores.get(app_name)
            if cs_path is None:
                root = Path(project_root) if project_root else _infer_project_root()
                app_path = root / app_name
            else:
                app_path = Path(cs_path).parent

            cs_dir = Path(app_path) / CONTEXT_STORE_DIR_NAME
            cs_dir.mkdir(parents=True, exist_ok=True)
            state_path = cs_dir / STATE_FILE_NAME

            # 기존 state 로드 및 병합(기존 보존, 새 값으로 덮어쓰기)
            existing_state = {}
            if state_path.exists():
                try:
                    with state_path.open('r', encoding='utf-8') as f:
                        existing_state = json.load(f)
                except Exception:
                    logger.exception(f'Failed to load existing state.json for {app_name} during autosave')
                    existing_state = {}

            payload = state
            try:
                if isinstance(existing_state, dict) and isinstance(state, dict) and existing_state:
                    merged = dict(existing_state)
                    merged.update(state)
                    payload = merged
            except Exception:
                payload = state

            # Acquire per-app lock before writing to avoid race with save helpers
            lock = _get_app_lock(app_name)
            with lock:
                _atomic_write_json(state_path, payload)
            logger.info(f"autosave saved state for {app_name} -> {state_path}")
        except Exception:
            logger.exception(f"autosave failed for {app_name}")


def persist_registry_state(app_name: str, project_root: Optional[Union[str, Path]] = None):
    """CONTEXT_REGISTRY의 특정 앱 상태를 해당 앱의 context_store/state.json으로 저장합니다.

    - app_name: 앱 폴더명
    - project_root: 프로젝트 루트 경로(없으면 자동 추론)
    반환: 저장된 Path 또는 None
    """
    try:
        app_stores = ensure_context_store_for_apps(project_root)
        cs_path = app_stores.get(app_name)
        if cs_path is None:
            # 앱 폴더가 프로젝트 루트에 없을 수 있으므로 추정
            root = Path(project_root) if project_root else _infer_project_root()
            app_path = root / app_name
        else:
            app_path = Path(cs_path).parent

        entry = CONTEXT_REGISTRY.get(app_name) or get_or_create_registry_entry(app_name, create_slave=False)
        if entry is None:
            logger.warning(f"No registry entry to persist for {app_name}")
            return None

        # 상태 추출
        if hasattr(entry, 'get_all_state') and callable(getattr(entry, 'get_all_state')):
            state = entry.get_all_state()
        elif isinstance(entry, dict):
            state = entry.get('store', {}).get('state', {})
        else:
            store_attr = getattr(entry, 'store', None)
            state = store_attr.get('state', {}) if isinstance(store_attr, dict) else {}

        # 안전성: state가 아닌 경우 빈 dict로
        if not isinstance(state, dict):
            try:
                state = dict(state)
            except Exception:
                state = {}

        # Determine context_store path
        cs_dir = Path(app_path) / CONTEXT_STORE_DIR_NAME
        cs_dir.mkdir(parents=True, exist_ok=True)
        state_path = cs_dir / STATE_FILE_NAME

        # Acquire cross-process lock while reading/writing state.json
        with _file_lock(state_path):
            # Load existing state if present (for merge)
            existing_state = {}
            if state_path.exists():
                try:
                    with state_path.open('r', encoding='utf-8') as sf:
                        existing_state = json.load(sf)
                except Exception:
                    logger.exception(f'Failed to load existing state.json for {app_name} during persist')

            # If extracted state is empty dict and existing exists, skip overwrite
            if isinstance(state, dict) and not state:
                if existing_state:
                    logger.info(f"Persist skipped for {app_name}: new state empty, keeping existing state.json (keys={list(existing_state.keys())[:10]})")
                    return state_path
                # try restore from backups if any
                # (optional) omitted here

            payload = state
            try:
                if isinstance(existing_state, dict) and isinstance(state, dict) and existing_state:
                    merged = dict(existing_state)
                    merged.update(state)
                    payload = merged
                    logger.info(f"Merged state for {app_name}: existing_keys={len(existing_state)} new_keys={len(state)} -> merged_keys={len(payload)}")

                written = _atomic_write_json(state_path, payload)
                logger.info(f"Persisted registry state for {app_name} -> {written}")
                return written
            except Exception:
                logger.exception(f"Failed to persist registry state for {app_name}")
                return None
    except Exception:
        logger.exception(f"Failed to persist registry state for {app_name}")
        return None


def _parse_bytes(s: Optional[Union[str, int]]) -> int:
    """사람 친화적 문자열을 바이트로 파싱합니다. 예: '100', '10K', '5M', '1G'. 실패 시 0 반환."""
    if s is None:
        return 0
    if isinstance(s, int):
        return int(s)
    try:
        t = str(s).strip().upper()
        if not t:
            return 0
        if t.endswith('GB') or t.endswith('G'):
            return int(float(t.rstrip('GB').rstrip('G')) * 1024 ** 3)
        if t.endswith('MB') or t.endswith('M'):
            return int(float(t.rstrip('MB').rstrip('M')) * 1024 ** 2)
        if t.endswith('KB') or t.endswith('K'):
            return int(float(t) * 1024)
        return int(float(t))
    except Exception:
        return 0


def backup_state_for_app(app_name: str, project_root: Optional[Union[str, Path]] = None, keep_days: Optional[int] = None, max_backups: Optional[int] = None, max_total_bytes: Optional[Union[int, str]] = None) -> Optional[Path]:
    """
    앱의 state.json을 meta_backups에 백업하고 보관 정책을 적용합니다.

    - max_total_bytes: 최대 보관 총 용량(바이트) 또는 '100M' 같은 문자열. None이면 환경변수 CONTEXT_BACKUP_MAX_BYTES 사용.
    - keep_days, max_backups는 선택적으로 오래된 파일 삭제에 사용됩니다.

    반환: 생성된 백업 파일 Path 또는 None
    """
    try:
        # env 값 읽기(인자 None일 때만 적용)
        try:
            if max_total_bytes is None:
                env_bytes = os.getenv(BACKUP_ENV_VARS['max_bytes'])
                max_total_bytes = parse_bytes_string(env_bytes) if env_bytes else 0
            else:
                max_total_bytes = parse_bytes_string(max_total_bytes)
        except Exception:
            max_total_bytes = 0

        try:
            if keep_days is None:
                env_keep = os.getenv(BACKUP_ENV_VARS['keep_days'])
                keep_days = int(env_keep) if env_keep and env_keep.isdigit() else None
        except Exception:
            keep_days = None
        try:
            if max_backups is None:
                env_max = os.getenv(BACKUP_ENV_VARS['max_files'])
                max_backups = int(env_max) if env_max and env_max.strip().lstrip('-').isdigit() else None
        except Exception:
            max_backups = None

        app_stores = ensure_context_store_for_apps(project_root)
        cs_path = app_stores.get(app_name)
        if cs_path is None:
            root = Path(project_root) if project_root else _infer_project_root()
            cs_dir = root / app_name / CONTEXT_STORE_DIR_NAME
        else:
            cs_dir = Path(cs_path)

        state_path = cs_dir / STATE_FILE_NAME
        if not state_path.exists():
            logger.info(f'No state.json to backup for app {app_name}: {state_path}')
            return None

        backup_dir = cs_dir / BACKUP_DIR_NAME
        backup_dir.mkdir(parents=True, exist_ok=True)

        try:
            with state_path.open('r', encoding='utf-8') as sf:
                payload = json.load(sf)
        except Exception:
            logger.exception(f'Failed to read state.json for backup: {state_path}')
            return None

        timestamp = datetime.datetime.now().strftime('%Y%m%dT%H%M%S')
        dest = backup_dir / f'state-{timestamp}.json'
        try:
            _atomic_write_json(dest, payload)
            logger.info(f'Created state backup for {app_name}: {dest}')
        except Exception:
            logger.exception(f'Failed to write state backup for {app_name} to {dest}')
            return None

        # 보관 정책 적용
        try:
            # 1) age-based pruning
            if isinstance(keep_days, int) and keep_days > 0:
                cutoff = datetime.datetime.now() - datetime.timedelta(days=keep_days)
                for p in backup_dir.glob('state-*.json'):
                    try:
                        mtime = datetime.datetime.fromtimestamp(p.stat().st_mtime)
                        if mtime < cutoff:
                            p.unlink()
                            logger.info(f'Removed old backup for {app_name} by age: {p}')
                    except Exception:
                        logger.exception(f'Failed to inspect/remove backup file: {p}')

            # 2) size-based pruning
            if isinstance(max_total_bytes, int) and max_total_bytes > 0:
                candidates = sorted([p for p in backup_dir.glob('state-*.json') if p.is_file()], key=lambda p: p.stat().st_mtime)
                total = sum((p.stat().st_size for p in candidates))
                logger.debug(f'Backup dir total size for {app_name}: {total} bytes (limit={max_total_bytes})')
                if total > max_total_bytes:
                    for p in candidates:
                        try:
                            size = p.stat().st_size
                            p.unlink()
                            total -= size
                            logger.info(f'Removed old backup for {app_name} by size policy: {p} (freed={size} bytes)')
                            if total <= max_total_bytes:
                                break
                        except Exception:
                            logger.exception(f'Failed to remove backup file by size policy: {p}')

            # 3) count-based pruning
            if isinstance(max_backups, int) and max_backups > 0:
                candidates = sorted([p for p in backup_dir.glob('state-*.json') if p.is_file()], key=lambda p: p.stat().st_mtime, reverse=True)
                if len(candidates) > max_backups:
                    to_remove = candidates[max_backups:]
                    for p in to_remove:
                        try:
                            p.unlink()
                            logger.info(f'Removed old backup for {app_name} by count policy: {p}')
                        except Exception:
                            logger.exception(f'Failed to remove backup file by count policy: {p}')
        except Exception:
            logger.exception(f'Failed to prune backups in {backup_dir} for {app_name}')

        return dest
    except Exception:
        logger.exception(f'backup_state_for_app failed for {app_name}')
        return None


def backup_all_states(project_root: Optional[Union[str, Path]] = None, keep_days: Optional[int] = None, max_backups: Optional[int] = None, max_total_bytes: Optional[Union[int, str]] = None) -> Dict[str, Optional[str]]:
    """프로젝트에 있는 모든 앱에 대해 state.json을 meta_backups에 백업하고 보관 정책을 적용합니다.

    - max_total_bytes는 함수 인자 또는 환경변수(CONTEXT_BACKUP_MAX_BYTES)를 통해 제어.
    반환: {app_name: str(path) or None}
    """
    results: Dict[str, Optional[str]] = {}
    try:
        app_stores = ensure_context_store_for_apps(project_root)
        for app_name in app_stores.keys():
            try:
                created = backup_state_for_app(app_name, project_root, keep_days=keep_days, max_backups=max_backups, max_total_bytes=max_total_bytes)
                results[app_name] = str(created) if created else None
            except Exception:
                logger.exception(f'backup_all_states: failed for {app_name}')
                results[app_name] = None
    except Exception:
        logger.exception('backup_all_states: discovery failed')
    return results


def create_or_update_slave_context(app_name: str, host: str, port: int, memory_creator: str = 'LS_XGT_TCP', memory_kwargs: Optional[dict] = None, persist: bool = True) -> bool:
    """Create or update a slave context entry under CONTEXT_REGISTRY and persist to state.json.

    - app_name: 앱 폴더명
    - host, port: slave 식별자 (대분류 key: "host:port")
    - memory_creator: BaseSlaveContext의 생성 메서드 이름이나 별칭 (예: 'LS_XGT_TCP')
    - memory_kwargs: create_memory에 전달할 추가 kwargs
    - persist: True면 persist_registry_state를 호출해 state.json에 영구 저장

    동작:
    - SlaveContext(create_memory=memory_creator, **memory_kwargs)를 생성
    - 생성된 sc.store 내부 블록들을 JSON-직렬화 가능한 형태로 변환하여 state["host:port"]["MEMORY"]=... 으로 저장
    - per-app 락(_get_app_lock)으로 동기화
    - CONTEXT_REGISTRY에 반영(_sync_registry_state)하고 필요시 persist

    반환: 성공 여부
    """
    try:
        try:
            from .context import SlaveContext
        except Exception:
            # Fallback alias if available
            try:
                from .context import RegistersSlaveContext as SlaveContext
            except Exception:
                SlaveContext = None
        if SlaveContext is None:
            logger.error('SlaveContext class not available')
            return False

        slave_key = f"{host}:{port}"
        memory_kwargs = memory_kwargs or {}
        # create a fresh SlaveContext with requested memory
        try:
            sc = SlaveContext(create_memory=memory_creator, **memory_kwargs)
        except TypeError:
            # some older factories may expect different kwarg name
            try:
                sc = SlaveContext(createMemory=memory_creator)
            except Exception:
                sc = SlaveContext()
        except Exception:
            sc = SlaveContext()

        # serialize sc.store contents
        memory_dump = {}
        try:
            mem_info = sc.get_memory_info() if hasattr(sc, 'get_memory_info') else {}
        except Exception:
            mem_info = {}
        for mem_name, block in getattr(sc, 'store', {}).items():
            try:
                if hasattr(block, 'to_json') and callable(getattr(block, 'to_json')):
                    mem_obj = block.to_json()
                elif isinstance(block, dict):
                    mem_obj = block
                elif hasattr(block, 'values'):
                    try:
                        mem_obj = getattr(block, 'values')
                    except Exception:
                        mem_obj = mem_info.get(mem_name)
                else:
                    # fallback to get_memory_info metadata or type name
                    mem_obj = mem_info.get(mem_name) if mem_info.get(mem_name) is not None else {'type': type(block).__name__}

                # For memory types %MB/%RB/%WB, prefer list serialization for 'values'
                if isinstance(mem_obj, dict) and 'values' in mem_obj:
                    vals = mem_obj.get('values')
                    if isinstance(vals, dict) and mem_name in {"%MB", "%RB", "%WB"}:
                        # convert dict->list
                        try:
                            mem_obj = dict(mem_obj)
                            mem_obj['values'] = _values_dict_to_list(vals)
                        except Exception:
                            pass
                memory_dump[mem_name] = mem_obj
            except Exception:
                memory_dump[mem_name] = {'error': 'serialize_failed', 'type': str(type(block))}

        payload = {'MEMORY': memory_dump, 'Meta': {'created': datetime.datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'}}

        # synchronize into in-memory registry + persist under lock
        lock = _get_app_lock(app_name)
        with lock:
            try:
                # ensure registry entry exists
                get_or_create_registry_entry(app_name, create_slave=True)
            except Exception:
                logger.exception(f'Failed to ensure registry entry for {app_name}')
            try:
                # sync specific slave_key entry
                _sync_registry_state(app_name, slave_key, payload)
            except Exception:
                logger.exception(f'Failed to sync registry state for {app_name}/{slave_key}')
            if persist:
                try:
                    persist_registry_state(app_name)
                except Exception:
                    logger.exception(f'Failed to persist registry state for {app_name}')
        logger.info(f'Created/Updated slave context in registry for {app_name} -> {slave_key}')
        return True
    except Exception:
        logger.exception('create_or_update_slave_context failed')
        return False


def save_status_with_meta(app_path_or_name: Union[str, Path], serial_input, command_name: str, processed_data: dict, project_root: Optional[Union[str, Path]] = None):
    """특정 앱의 state.json에서 serial 키에 대해 STATUS 블록을 교체하고 Meta를 업데이트합니다.

    반환: dict { 'changed': bool, 'written': str or None, 'error': str or None, 'entry': dict }
    """
    try:
        # normalise serial
        try:
            if isinstance(serial_input, (bytes, bytearray)):
                serial = serial_input.hex().upper()
            else:
                serial = str(serial_input).upper() if serial_input is not None else 'UNKNOWN_SERIAL'
        except Exception:
            serial = 'UNKNOWN_SERIAL'

        # determine app path
        app_p = None
        if isinstance(app_path_or_name, (str,)):
            candidate = Path(app_path_or_name)
            if candidate.exists() and candidate.is_dir():
                app_p = candidate
            else:
                app_stores = ensure_context_store_for_apps(project_root)
                cs_path = app_stores.get(app_path_or_name)
                if cs_path:
                    app_p = Path(cs_path).parent
                else:
                    root = Path(project_root) if project_root else _infer_project_root()
                    candidate2 = root / app_path_or_name
                    if candidate2.exists() and candidate2.is_dir():
                        app_p = candidate2
        elif isinstance(app_path_or_name, Path):
            app_p = app_path_or_name
        else:
            app_p = Path(app_path_or_name)

        if app_p is None or not app_p.exists():
            logger.error(f"save_status_with_meta: app not found: {app_path_or_name}")
            return {'changed': False, 'written': None, 'error': 'app_not_found', 'entry': None}

        cs_dir = app_p / CONTEXT_STORE_DIR_NAME
        cs_dir.mkdir(parents=True, exist_ok=True)
        state_path = cs_dir / STATE_FILE_NAME

        # load existing state
        existing_state = {}
        if state_path.exists():
            try:
                with state_path.open('r', encoding='utf-8') as f:
                    existing_state = json.load(f)
            except Exception:
                logger.exception(f"Failed to load existing state.json for save_status_with_meta: {state_path}")
                existing_state = {}

        if not isinstance(existing_state, dict):
            existing_state = {}

        old_entry = deepcopy(existing_state.get(serial)) if serial in existing_state else None
        entry = deepcopy(old_entry) if isinstance(old_entry, dict) else {}

        # Extract STATUS block
        status_block = None
        if isinstance(processed_data, dict) and 'STATUS' in processed_data:
            status_block = processed_data.get('STATUS')
        elif isinstance(processed_data, dict) and ('Voltage' in processed_data or 'Current' in processed_data):
            # processed_data already looks like STATUS contents
            status_block = processed_data
        else:
            # fallback: try to find nested 'STATUS'
            try:
                # naive search
                if isinstance(processed_data, dict):
                    for v in processed_data.values():
                        if isinstance(v, dict) and 'STATUS' in v:
                            status_block = v.get('STATUS')
                            break
            except Exception:
                status_block = None

        # set STATUS (replace)
        if status_block is not None:
            # Defensive merge: do not replace whole STATUS. Merge per mid-category and subkeys.
            status_existing = entry.get('STATUS') if isinstance(entry.get('STATUS'), dict) else {}
            if not isinstance(status_existing, dict):
                # existing STATUS is leaf -> wrap it into dict under a special key? Prefer to preserve by moving to '_legacy'
                try:
                    status_existing = {'_legacy': status_existing}
                except Exception:
                    status_existing = {}

            status = dict(status_existing)
            # iterate incoming mid-categories
            try:
                for mid_k, mid_v in (status_block.items() if isinstance(status_block, dict) else []):
                    # find matching existing mid key (normalize)
                    match = _find_matching_key(status, mid_k)
                    use_key = match if match else mid_k
                    existing_mid = status.get(use_key)
                    # if both are dicts, merge subkeys selectively
                    if isinstance(existing_mid, dict) and isinstance(mid_v, dict):
                        for subk, subv in mid_v.items():
                            # update only when different
                            try:
                                if subk in existing_mid:
                                    if existing_mid.get(subk) != subv:
                                        existing_mid[subk] = subv
                                else:
                                    existing_mid[subk] = subv
                            except Exception:
                                existing_mid[subk] = subv
                                
                        status[use_key] = existing_mid
                    else:
                        # otherwise replace the mid entry (less destructive than replacing whole STATUS)
                        status[use_key] = mid_v
            except Exception:
                # fallback: if merging fails, try to minimally set STATUS to incoming block without clobbering if possible
                try:
                    if isinstance(status_block, dict):
                        for k, v in status_block.items():
                            status[k] = v
                except Exception:
                    status = status_block

            entry['STATUS'] = status

        # Ensure we do not persist wrapper 'processed_data' into state.json
        try:
            if 'processed_data' in entry:
                entry.pop('processed_data', None)
        except Exception:
            pass

        # update Meta
        meta = entry.get('Meta', {}) if isinstance(entry.get('Meta', {}), dict) else {}
        # last_updated in UTC (Z)
        try:
            meta['last_updated'] = datetime.datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'
        except Exception:
            meta['last_updated'] = datetime.datetime.utcnow().isoformat() + 'Z'
        # command timestamp in local timezone
        try:
            meta[command_name] = datetime.datetime.now().astimezone().isoformat()
        except Exception:
            meta[command_name] = datetime.datetime.now().isoformat()
        entry['Meta'] = meta

        # Ensure we do not persist wrapper 'processed_data' into state.json (again for safety)
        try:
            if 'processed_data' in entry:
                entry.pop('processed_data', None)
        except Exception:
            pass

        # decide changed
        try:
            changed = json.dumps(old_entry, sort_keys=True, ensure_ascii=False) != json.dumps(entry, sort_keys=True, ensure_ascii=False)
        except Exception:
            changed = True

        existing_state[serial] = entry
        lock = _get_app_lock(app_p.name)
        with lock:
            try:
                _sync_registry_state(app_p.name, serial, entry)
            except Exception:
                logger.exception(f"Failed to sync registry before write for {app_p.name}/{serial}")
            try:
                written = _atomic_write_json(state_path, existing_state)
                logger.info(f"Saved STATUS+Meta for serial {serial} command {command_name} -> {written} changed={changed}")
                return {'changed': changed, 'written': str(written), 'error': None, 'entry': entry}
            except Exception as e:
                logger.exception(f"Failed to write state.json in save_status_with_meta for {serial}")
                return {'changed': False, 'written': None, 'error': str(e), 'entry': entry}
    except Exception as e:
        logger.exception('save_status_with_meta failed')
        return {'changed': False, 'written': None, 'error': str(e), 'entry': None}


def save_status_nested(app_path_or_name: Union[str, Path], serial_input, mid_category: str, sub_category: str, kv: dict, overwrite_sub_if_exists: bool = True, command_name: Optional[str] = None, project_root: Optional[Union[str, Path]] = None):
    """STATUS 대분류->중분류->소분류 경로에 kv(dict)를 저장합니다.

    동작:
    - serial_input을 대문자(normalize)로 변환
    - STATUS, mid_category, sub_category 계층을 없으면 생성
    - sub_category가 이미 존재할 경우 overwrite_sub_if_exists=True 이면 덮어쓰고, False이면 기존 값을 유지함
    - 항상 Meta['last_updated']는 갱신

    반환: 업데이트된 entry(dict) 또는 None
    """
    try:
        # normalize serial
        try:
            if isinstance(serial_input, (bytes, bytearray)):
                serial = serial_input.hex().upper()
            else:
                serial = str(serial_input).upper() if serial_input is not None else 'UNKNOWN_SERIAL'
        except Exception:
            serial = 'UNKNOWN_SERIAL'

        # determine app path (reuse logic)
        app_p = None
        if isinstance(app_path_or_name, (str,)):
            candidate = Path(app_path_or_name)
            if candidate.exists() and candidate.is_dir():
                app_p = candidate
            else:
                app_stores = ensure_context_store_for_apps(project_root)
                cs_path = app_stores.get(app_path_or_name)
                if cs_path:
                    app_p = Path(cs_path).parent
                else:
                    root = Path(project_root) if project_root else _infer_project_root()
                    candidate2 = root / app_path_or_name
                    if candidate2.exists() and candidate2.is_dir():
                        app_p = candidate2
        elif isinstance(app_path_or_name, Path):
            app_p = app_path_or_name
        else:
            app_p = Path(app_path_or_name)

        if app_p is None or not app_p.exists():
            logger.error(f"save_status_nested: app not found: {app_path_or_name}")
            return None

        cs_dir = app_p / CONTEXT_STORE_DIR_NAME
        cs_dir.mkdir(parents=True, exist_ok=True)
        state_path = cs_dir / STATE_FILE_NAME

        # load existing state
        existing_state = {}
        if state_path.exists():
            try:
                with state_path.open('r', encoding='utf-8') as f:
                    existing_state = json.load(f)
            except Exception:
                logger.exception(f"Failed to load existing state.json for save_status_nested: {state_path}")
                existing_state = {}

        if not isinstance(existing_state, dict):
            existing_state = {}

        entry = existing_state.get(serial) if isinstance(existing_state.get(serial), dict) else existing_state.get(serial, {})
        if not isinstance(entry, dict):
            entry = {}

        # STATUS 처리: 중간 노드가 dict인지 여부에 따라 분류 동작을 다르게 함
        status_raw = entry.get('STATUS')
        # 1) STATUS가 dict이 아니면 분류 구조가 끝난 것으로 간주(leaf) => leaf 값과 비교하여 다를 때만 덮어쓰기
        if not isinstance(status_raw, dict):
            try:
                if status_raw != {mid_category: {sub_category: kv}}:
                    # 기존이 leaf이므로 새로운 중첩 구조 대신 전달된 kv로 대체
                    entry['STATUS'] = {mid_category: {sub_category: kv}}
                # else 동일 구조로 간주하여 변경 없음
            except Exception:
                entry['STATUS'] = {mid_category: {sub_category: kv}}
        else:
            status = status_raw
            # try to match existing mid_category key (handle typos like 'Ditital' vs 'Digital')
            matching_mid = _find_matching_key(status, mid_category)
            if matching_mid:
                mid_raw = status.get(matching_mid)
                mid_key_to_use = matching_mid
            else:
                mid_raw = status.get(mid_category)
                mid_key_to_use = mid_category
            # 2) mid_category가 dict이 아니면 그 시점에서 분류 구조가 끝남 -> leaf로 간주하여 다를 때만 덮어쓰기
            if not isinstance(mid_raw, dict):
                try:
                    if mid_raw != kv:
                        # mid 레벨을 leaf로 덮어쓰기 (사용자가 의도한 소분류를 mid에 기록)
                        status[mid_key_to_use] = kv
                    # else 동일하면 아무 처리 안함
                except Exception:
                    status[mid_key_to_use] = kv
            else:
                # mid가 dict일 때만 소분류 검사/생성/업데이트 수행
                mid = mid_raw
                matching_key = _find_matching_key(mid, sub_category)
                if matching_key:
                    existing_val = mid.get(matching_key)
                    try:
                        if existing_val != kv:
                            mid[matching_key] = kv  # 변경 감지 시에만 덮어쓰기
                        else:
                            # 값 동일하면 아무 변경 없음
                            pass
                    except Exception:
                        mid[matching_key] = kv
                else:
                    # 소분류가 없으면 생성
                    mid[sub_category] = kv

                status[mid_key_to_use] = mid
            entry['STATUS'] = status

        # Ensure we do not persist wrapper 'processed_data' into state.json
        try:
            if 'processed_data' in entry:
                entry.pop('processed_data', None)
        except Exception:
            pass

        # update Meta
        meta = entry.get('Meta', {}) if isinstance(entry.get('Meta', {}), dict) else {}
        try:
            meta['last_updated'] = datetime.datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'
        except Exception:
            meta['last_updated'] = datetime.datetime.utcnow().isoformat() + 'Z'
        if command_name:
            try:
                meta[command_name] = datetime.datetime.now().astimezone().isoformat()
            except Exception:
                meta[command_name] = datetime.datetime.now().isoformat()
        entry['Meta'] = meta

        # Remove wrapper processed_data if present
        try:
            if 'processed_data' in entry:
                entry.pop('processed_data', None)
        except Exception:
            pass

        old_entry = deepcopy(existing_state.get(serial)) if serial in existing_state else None
        try:
            changed = json.dumps(old_entry, sort_keys=True, ensure_ascii=False) != json.dumps(entry, sort_keys=True, ensure_ascii=False)
        except Exception:
            changed = True
        existing_state[serial] = entry
        lock = _get_app_lock(app_p.name)
        with lock:
            try:
                try:
                    _sync_registry_state(app_p.name, serial, entry)
                except Exception:
                    logger.exception(f"Failed to sync registry before write for {app_p.name}/{serial}")
                written = _atomic_write_json(state_path, existing_state)
                logger.info(f"Saved nested STATUS for serial {serial} {mid_category}/{sub_category} -> {written} (changed={changed})")
                return {'changed': changed, 'written': str(written), 'error': None, 'entry': entry}
            except Exception as e:
                logger.exception(f"Failed to write state.json in save_status_nested for {serial}")
                return {'changed': False, 'written': None, 'error': str(e), 'entry': entry}
    except Exception:
        logger.exception('save_status_nested failed')
        return None


def save_status_path(app_path_or_name: Union[str, Path], serial_input, path: list, kv, command_name: Optional[str] = None, project_root: Optional[Union[str, Path]] = None):
    """Generalized saver: STATUS path (list of keys) 를 따라 kv를 저장.

    - path: ['Voltage','AV1'] 등. 빈 path는 전체 STATUS 교체(kv로).
    - kv: dict or scalar. 덮어쓰기는 기존값과 다를 때만 수행.
    - non-dict encountered: 그 지점부터 분류 구조가 끝난 것으로 간주하고 비교/교체.
    """
    try:
        # normalize serial
        try:
            if isinstance(serial_input, (bytes, bytearray)):
                serial = serial_input.hex().upper()
            else:
                serial = str(serial_input).upper() if serial_input is not None else 'UNKNOWN_SERIAL'
        except Exception:
            serial = 'UNKNOWN_SERIAL'

        # resolve app path
        app_p = None
        if isinstance(app_path_or_name, (str,)):
            candidate = Path(app_path_or_name)
            if candidate.exists() and candidate.is_dir():
                app_p = candidate
            else:
                app_stores = ensure_context_store_for_apps(project_root)
                cs_path = app_stores.get(app_path_or_name)
                if cs_path:
                    app_p = Path(cs_path).parent
                else:
                    root = Path(project_root) if project_root else _infer_project_root()
                    candidate2 = root / app_path_or_name
                    if candidate2.exists() and candidate2.is_dir():
                        app_p = candidate2
        elif isinstance(app_path_or_name, Path):
            app_p = app_path_or_name
        else:
            app_p = Path(app_path_or_name)

        if app_p is None or not app_p.exists():
            logger.error(f"save_status_path: app not found: {app_path_or_name}")
            return None

        cs_dir = app_p / CONTEXT_STORE_DIR_NAME
        cs_dir.mkdir(parents=True, exist_ok=True)
        state_path = cs_dir / STATE_FILE_NAME

        # load existing
        existing_state = {}
        if state_path.exists():
            try:
                with state_path.open('r', encoding='utf-8') as f:
                    existing_state = json.load(f)
            except Exception:
                logger.exception(f"Failed to load existing state.json for save_status_path: {state_path}")
                existing_state = {}
        if not isinstance(existing_state, dict):
            existing_state = {}

        entry = existing_state.get(serial) if isinstance(existing_state.get(serial), dict) else existing_state.get(serial, {})
        if not isinstance(entry, dict):
            entry = {}

        # helper to build nested dict from path and kv
        def build_nested(pth, value):
            if not pth:
                return value
            d = {}
            cur = d
            for i, k in enumerate(pth):
                if i == len(pth) - 1:
                    cur[k] = value
                else:
                    cur[k] = {}
                    cur = cur[k]
            return d

        nested_struct = build_nested(path, kv)

        status_raw = entry.get('STATUS')
        # if STATUS is not dict => treat as leaf, compare with nested_struct
        if not isinstance(status_raw, dict):
            try:
                if status_raw != nested_struct:
                    entry['STATUS'] = nested_struct
            except Exception:
                entry['STATUS'] = nested_struct
        else:
            # traverse
            cur = status_raw
            parent_stack = []  # stack of (parent_dict, key)
            stopped_as_leaf = False
            for i, key in enumerate(path):
                last = (i == len(path) - 1)
                matching_key = _find_matching_key(cur, key)
                if matching_key:
                    key = matching_key
                val = cur.get(key)
                # if last key: compare/assign
                if last:
                    if key in cur:
                        existing_val = cur.get(key)
                        try:
                            # If both existing and incoming are dicts, merge at subkey level
                            if isinstance(existing_val, dict) and isinstance(kv, dict):
                                for subk, subv in kv.items():
                                        if subk in existing_val:
                                            # only update if different
                                            if existing_val.get(subk) != subv:
                                                existing_val[subk] = subv
                                        else:
                                            existing_val[subk] = subv
                                cur[key] = existing_val
                            else:
                                if existing_val != kv:
                                    cur[key] = kv
                        except Exception:
                            cur[key] = kv
                    else:
                        cur[key] = kv
                    break
                # not last
                if not isinstance(val, dict):
                    # existing is leaf -> replace this key with nested remainder if different
                    remainder = build_nested(path[i+1:], kv)
                    try:
                        if val != remainder:
                            cur[key] = remainder
                        # else identical => no-op
                    except Exception:
                        cur[key] = remainder
                    stopped_as_leaf = True
                    break
                # val is dict -> descend
                parent_stack.append((cur, key))
                cur = val
            # assign back
            entry['STATUS'] = status_raw

        # update Meta
        meta = entry.get('Meta', {}) if isinstance(entry.get('Meta', {}), dict) else {}
        try:
            meta['last_updated'] = datetime.datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'
        except Exception:
            meta['last_updated'] = datetime.datetime.utcnow().isoformat() + 'Z'
        if command_name:
            try:
                meta[command_name] = datetime.datetime.now().astimezone().isoformat()
            except Exception:
                meta[command_name] = datetime.datetime.now().isoformat()
        entry['Meta'] = meta

        # Remove wrapper processed_data if present
        try:
            if 'processed_data' in entry:
                entry.pop('processed_data', None)
        except Exception:
            pass

        old_entry = deepcopy(existing_state.get(serial)) if serial in existing_state else None
        try:
            changed = json.dumps(old_entry, sort_keys=True, ensure_ascii=False) != json.dumps(entry, sort_keys=True, ensure_ascii=False)
        except Exception:
            changed = True
        existing_state[serial] = entry
        lock = _get_app_lock(app_p.name)
        with lock:
            try:
                try:
                    _sync_registry_state(app_p.name, serial, entry)
                except Exception:
                    logger.exception(f"Failed to sync registry before write for {app_p.name}/{serial}")
                written = _atomic_write_json(state_path, existing_state)
                logger.info(f"Saved STATUS path for serial {serial} path={path} -> {written} (changed={changed})")
                return {'changed': changed, 'written': str(written), 'error': None, 'entry': entry}
            except Exception as e:
                logger.exception(f"Failed to write state.json in save_status_path for {serial}")
                return {'changed': False, 'written': None, 'error': str(e), 'entry': entry}
    except Exception:
        logger.exception('save_status_path failed')
        return None


def _sync_registry_state(app_name: str, serial: str, entry_obj: dict):
    """Ensure CONTEXT_REGISTRY[app_name] in-memory state reflects on-disk entry for serial.

    - If registry entry exposes set_state/get_state, use those.
    - If registry entry is a dict, update ['store']['state'][serial] = entry_obj
    - If registry entry has 'store' dict attribute, update similarly.
    This is best-effort and must not raise.
    """
    try:
        if not app_name:
            return
        reg = CONTEXT_REGISTRY.get(app_name)
        if reg is None:
            return
        # RegistersSlaveContext-like object with set_state/get_state
        try:
            if hasattr(reg, 'set_state') and callable(getattr(reg, 'set_state')):
                try:
                    reg.set_state(serial, entry_obj)
                    return
                except Exception:
                    pass
        except Exception:
            pass
        # dict-like fallback
        try:
            if isinstance(reg, dict):
                store = reg.setdefault('store', {})
                state = store.setdefault('state', {})
                state[serial] = entry_obj
                return
        except Exception:
            pass
        # object with .store attribute as dict
        try:
            store_attr = getattr(reg, 'store', None)
            if isinstance(store_attr, dict):
                state = store_attr.setdefault('state', {})
                state[serial] = entry_obj
                return
        except Exception:
            pass
    except Exception:
        logger.exception(f"_sync_registry_state failed for {app_name}/{serial}")


def save_block_top_level(app_path_or_name: Union[str, Path], serial_input, block_name: str, block_value, command_name: Optional[str] = None, project_root: Optional[Union[str, Path]] = None):
    """Save a top-level block under entry[block_name] (not under STATUS).

    - block_name: e.g. 'SETUP'
    - block_value: dict or scalar. If both existing and incoming are dicts, merge subkeys (update only when different).
    - updates Meta as in other save helpers.
    Returns dict {'changed','written','error','entry'}.
    """
    try:
        # normalize serial
        try:
            if isinstance(serial_input, (bytes, bytearray)):
                serial = serial_input.hex().upper()
            else:
                serial = str(serial_input).upper() if serial_input is not None else 'UNKNOWN_SERIAL'
        except Exception:
            serial = 'UNKNOWN_SERIAL'

        # determine app path
        app_p = None
        if isinstance(app_path_or_name, (str,)):
            candidate = Path(app_path_or_name)
            if candidate.exists() and candidate.is_dir():
                app_p = candidate
            else:
                app_stores = ensure_context_store_for_apps(project_root)
                cs_path = app_stores.get(app_path_or_name)
                if cs_path:
                    app_p = Path(cs_path).parent
                else:
                    root = Path(project_root) if project_root else _infer_project_root()
                    candidate2 = root / app_path_or_name
                    if candidate2.exists() and candidate2.is_dir():
                        app_p = candidate2
        elif isinstance(app_path_or_name, Path):
            app_p = app_path_or_name
        else:
            app_p = Path(app_path_or_name)

        if app_p is None or not app_p.exists():
            logger.error(f"save_block_top_level: app not found: {app_path_or_name}")
            return {'changed': False, 'written': None, 'error': 'app_not_found', 'entry': None}

        cs_dir = app_p / CONTEXT_STORE_DIR_NAME
        cs_dir.mkdir(parents=True, exist_ok=True)
        state_path = cs_dir / STATE_FILE_NAME

        # load existing state
        existing_state = {}
        if state_path.exists():
            try:
                with state_path.open('r', encoding='utf-8') as f:
                    existing_state = json.load(f)
            except Exception:
                logger.exception(f"Failed to load existing state.json for save_block_top_level: {state_path}")
                existing_state = {}

        if not isinstance(existing_state, dict):
            existing_state = {}

        old_entry = deepcopy(existing_state.get(serial)) if serial in existing_state else None
        entry = deepcopy(old_entry) if isinstance(old_entry, dict) else {}

        existing_block = entry.get(block_name)
        # merge policy: if both dicts, merge subkeys and update only when different
        if isinstance(existing_block, dict) and isinstance(block_value, dict):
            # Try to smart-merge using normalized key matching to handle common typos
            merged_block = dict(existing_block)
            try:
                for k, v in block_value.items():
                    # find matching existing key by normalization (handles e.g. 'Digital_Input_Threshod' vs 'Digital_Input_Threshold')
                    match = _find_matching_key(merged_block, k)
                    use_key = match if match else k
                    existing_mid = merged_block.get(use_key)
                    # If both are dicts, merge their subkeys with normalization too
                    if isinstance(existing_mid, dict) and isinstance(v, dict):
                        for subk, subv in v.items():
                            submatch = _find_matching_key(existing_mid, subk)
                            use_sub = submatch if submatch else subk
                            try:
                                if use_sub in existing_mid:
                                    if existing_mid.get(use_sub) != subv:
                                        existing_mid[use_sub] = subv
                                else:
                                    existing_mid[use_sub] = subv
                            except Exception:
                                existing_mid[use_sub] = subv
                        merged_block[use_key] = existing_mid
                    else:
                        # No existing dict to merge into -> replace or insert at normalized key
                        merged_block[use_key] = v
            except Exception:
                # If smart merge fails, fall back to replacing the whole block
                merged_block = dict(block_value)
            entry[block_name] = merged_block
        else:
            # replace
            entry[block_name] = block_value

        # update Meta
        meta = entry.get('Meta', {}) if isinstance(entry.get('Meta', {}), dict) else {}
        try:
            meta['last_updated'] = datetime.datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'
        except Exception:
            meta['last_updated'] = datetime.datetime.utcnow().isoformat() + 'Z'
        if command_name:
            try:
                meta[command_name] = datetime.datetime.now().astimezone().isoformat()
            except Exception:
                meta[command_name] = datetime.datetime.now().isoformat()
        entry['Meta'] = meta

        # Remove wrapper processed_data if present
        try:
            if 'processed_data' in entry:
                entry.pop('processed_data', None)
        except Exception:
            pass

        try:
            changed = json.dumps(old_entry, sort_keys=True, ensure_ascii=False) != json.dumps(entry, sort_keys=True, ensure_ascii=False)
        except Exception:
            changed = True

        existing_state[serial] = entry
        lock = _get_app_lock(app_p.name)
        with lock:
            try:
                try:
                    _sync_registry_state(app_p.name, serial, entry)
                except Exception:
                    logger.exception(f"Failed to sync registry before write for {app_p.name}/{serial}")
                written = _atomic_write_json(state_path, existing_state)
                # Verify on-disk content contains expected block; if not, rewrite to ensure persistence
                on_disk_verified = False
                try:
                    with state_path.open('r', encoding='utf-8') as f:
                        disk_obj = json.load(f)
                    disk_entry = disk_obj.get(serial, {}) if isinstance(disk_obj, dict) else {}
                    # block must exist at top-level (not inside processed_data)
                    if isinstance(disk_entry, dict) and block_name in disk_entry:
                        # if block_value is dict, do deep compare for the block key
                        try:
                            if isinstance(block_value, dict):
                                on_disk_verified = disk_entry.get(block_name) == entry.get(block_name)
                            else:
                                on_disk_verified = disk_entry.get(block_name) == entry.get(block_name)
                        except Exception:
                            on_disk_verified = False
                except Exception:
                    on_disk_verified = False

                if not on_disk_verified:
                    try:
                        logger.warning(f"On-disk verification failed for {serial}/{block_name}, rewriting state.json to enforce change")
                        written = _atomic_write_json(state_path, existing_state)
                        # attempt one more verification
                        try:
                            with state_path.open('r', encoding='utf-8') as f:
                                disk_obj2 = json.load(f)
                            disk_entry2 = disk_obj2.get(serial, {}) if isinstance(disk_obj2, dict) else {}
                            on_disk_verified = isinstance(disk_entry2, dict) and block_name in disk_entry2 and disk_entry2.get(block_name) == entry.get(block_name)
                        except Exception:
                            on_disk_verified = False
                    except Exception:
                        logger.exception(f"Failed to rewrite state.json for enforcing {serial}/{block_name}")

                persisted_flag = False
                if on_disk_verified:
                    try:
                        # persist registry so that autosave won't overwrite the just-written file
                        try:
                            persist_registry_state(app_p.name)
                            persisted_flag = True
                        except Exception:
                            logger.exception(f"Failed to persist registry state for {app_p.name} after save_block_top_level")
                        # ensure registry contains final entry; sync again
                        try:
                            _sync_registry_state(app_p.name, serial, entry)
                        except Exception:
                            logger.exception(f"Post-persist registry sync failed for {app_p.name}/{serial}")
                        # re-verify disk after persist
                        try:
                            with state_path.open('r', encoding='utf-8') as f:
                                disk_obj3 = json.load(f)
                            disk_entry3 = disk_obj3.get(serial, {}) if isinstance(disk_obj3, dict) else {}
                            on_disk_verified = isinstance(disk_entry3, dict) and block_name in disk_entry3 and disk_entry3.get(block_name) == entry.get(block_name)
                        except Exception:
                            on_disk_verified = False
                    except Exception:
                        logger.exception('persist attempt after save_block_top_level failed')

                logger.info(f"Saved top-level block for serial {serial} block={block_name} -> {written} (changed={changed}) verified={on_disk_verified} persisted={persisted_flag}")
                return {'changed': changed, 'written': str(written), 'error': None, 'entry': entry, 'on_disk_verified': on_disk_verified, 'persisted': persisted_flag}
                 
            except Exception as e:
                logger.exception(f"Failed to write state.json in save_block_top_level for {serial}")
                return {'changed': False, 'written': None, 'error': str(e), 'entry': entry}
    except Exception as e:
        logger.exception('save_block_top_level failed')
        return {'changed': False, 'written': None, 'error': str(e), 'entry': None}


def save_setup(app_path_or_name: Union[str, Path], serial_input, setup_data, command_name: Optional[str] = None, project_root: Optional[Union[str, Path]] = None):
    """Convenience helper to save a SETUP top-level block for a device serial.

    Delegates to save_block_top_level to perform the actual atomic write and verification.

    :param app_path_or_name: 앱 폴더명 또는 경로
    :param serial_input: serial bytes or string
    :param setup_data: dict or scalar to store under entry['SETUP']
    :param command_name: optional command name to record in Meta
    :param project_root: optional project root for app discovery
    :return: dict like save_block_top_level's return value
    """
    try:
        return save_block_top_level(app_path_or_name, serial_input, 'SETUP', setup_data, command_name=command_name, project_root=project_root)
    except Exception as e:
        logger.exception('save_setup failed')
        return {'changed': False, 'written': None, 'error': str(e), 'entry': None}


def _values_dict_to_list(values_dict):
    """Convert a values dict with string/integer keys to a list ordered by integer index.
    Fills missing indices with 0 if gaps detected."""
    try:
        if not isinstance(values_dict, dict):
            return values_dict
        # collect integer keys
        items = []
        for k, v in values_dict.items():
            try:
                idx = int(k)
            except Exception:
                # skip non-integer keys
                continue
            items.append((idx, v))
        if not items:
            return []
        items.sort(key=lambda x: x[0])
        max_idx = items[-1][0]
        lst = [0] * (max_idx + 1)
        for idx, v in items:
            try:
                lst[idx] = v
            except Exception:
                lst[idx] = v
        return lst
    except Exception:
        return values_dict

