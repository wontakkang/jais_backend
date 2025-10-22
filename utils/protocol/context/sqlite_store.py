import sqlite3
import json
import os
import threading
import datetime
from pathlib import Path
from typing import Optional, Dict
import shutil
import hashlib

_db_path: Optional[Path] = None
_writer_lock = threading.Lock()


def _get_django_project_root():
    """Django 프로젝트 루트 경로를 동적으로 탐지합니다.
    
    현재 파일의 위치를 기준으로 Django 프로젝트 루트를 찾습니다.
    manage.py, settings.py 등의 Django 관련 파일이 있는 디렉터리를 찾습니다.
    """
    try:
        # 현재 파일의 경로에서 시작
        current_path = Path(__file__).resolve()
        
        # Django 프로젝트의 특징적인 파일들
        django_markers = ['manage.py', 'settings.py', 'wsgi.py', 'asgi.py']
        
        # 상위 디렉터리로 올라가면서 Django 프로젝트 루트 찾기
        for parent in current_path.parents:
            # manage.py가 있는 디렉터리를 Django 프로젝트 루트로 판단
            if (parent / 'manage.py').exists():
                return parent
            
            # 또는 Django 설정 파일들이 있는 패키지 구조 확인
            for child in parent.iterdir():
                if child.is_dir() and any((child / marker).exists() for marker in django_markers[1:]):
                    return parent
        
        # 찾지 못한 경우 현재 파일 기준으로 추정 (utils/protocol/context -> 상위 3단계)
        fallback_root = current_path.parents[3]
        return fallback_root
        
    except Exception:
        # 예외 발생 시 현재 파일 기준으로 추정
        return Path(__file__).resolve().parents[3]


def init_db(db_path: Optional[Path] = None):
    global _db_path
    try:
        # Django 프로젝트 루트를 동적으로 탐지
        django_root = _get_django_project_root()
        default_db_path = django_root / 'context_store.sqlite3'
        
        # 환경변수에서 데이터베이스 경로 확인 (선택사항)
        env_path = os.getenv('CONTEXT_STORE_DB_PATH')
        
        # 경로 우선순위: 함수 인자 > 환경변수 > Django 프로젝트 루트의 기본 경로
        if db_path is not None:
            try:
                candidate = Path(db_path).expanduser()
                if candidate.is_absolute():
                    db_path = candidate
                else:
                    # 상대 경로인 경우 Django 프로젝트 루트 기준으로 해석
                    db_path = django_root / candidate
            except Exception:
                db_path = default_db_path
        elif env_path:
            try:
                candidate = Path(env_path).expanduser()
                if candidate.is_absolute():
                    db_path = candidate
                else:
                    # 환경변수가 상대 경로인 경우 Django 프로젝트 루트 기준
                    db_path = django_root / candidate
            except Exception:
                db_path = default_db_path
        else:
            # 기본값: Django 프로젝트 루트의 context_store.sqlite3
            db_path = default_db_path
            
        # Log the chosen DB path for diagnostics
        try:
            print(f"Django project root detected: {django_root}")
            print(f"Initializing context sqlite DB at: {db_path}")
        except Exception:
            pass
            
        _db_path = Path(db_path)
        _db_path.parent.mkdir(parents=True, exist_ok=True)
        # Create DB and table if not exists
        conn = sqlite3.connect(str(_db_path), timeout=30, check_same_thread=False)
        try:
            conn.execute("PRAGMA journal_mode = WAL;")
            conn.execute("PRAGMA synchronous = NORMAL;")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS states (
                    app TEXT NOT NULL,
                    serial TEXT NOT NULL,
                    payload TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY(app, serial)
                ) WITHOUT ROWID;
            """)
            # store_meta: key/value JSON store for per-app metadata (e.g. meta.json contents)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS store_meta (
                    app TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT,
                    PRIMARY KEY(app, key)
                );
            """)
            # context history for audit/rollback
            conn.execute("""
                CREATE TABLE IF NOT EXISTS context_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    app TEXT NOT NULL,
                    serial TEXT,
                    payload TEXT,
                    change_type TEXT,
                    actor TEXT,
                    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            # lightweight meta for states (optional, denormalized)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS states_meta (
                    app TEXT NOT NULL,
                    serial TEXT NOT NULL,
                    version INTEGER DEFAULT 1,
                    checksum TEXT,
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP,
                    PRIMARY KEY(app, serial)
                );
            """)
            # indices
            conn.execute("CREATE INDEX IF NOT EXISTS idx_states_app ON states(app);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_states_updated_at ON states(updated_at);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_states_meta_updated ON states_meta(updated_at);")
            conn.commit()
        finally:
            conn.close()
    except Exception:
        # raise to caller
        raise


def _connect():
    if _db_path is None:
        init_db()
    return sqlite3.connect(str(_db_path), timeout=30, check_same_thread=False)


def compute_checksum(obj: object) -> str:
    """Compute SHA256 checksum of JSON-serialized object (stable key order)."""
    try:
        text = json.dumps(obj, ensure_ascii=False, separators=(',', ':'), sort_keys=True)
        return hashlib.sha256(text.encode('utf-8')).hexdigest()
    except Exception:
        try:
            text = str(obj)
            return hashlib.sha256(text.encode('utf-8')).hexdigest()
        except Exception:
            return ''


def _upsert_states_meta(conn, app: str, serial: str, checksum: Optional[str], created_at: Optional[str], updated_at: Optional[str]):
    cur = conn.cursor()
    cur.execute("SELECT version FROM states_meta WHERE app = ? AND serial = ?", (app, serial))
    row = cur.fetchone()
    if row:
        ver = int(row[0]) + 1
        cur.execute(
            "UPDATE states_meta SET version = ?, checksum = ?, updated_at = ? WHERE app = ? AND serial = ?",
            (ver, checksum, updated_at, app, serial),
        )
    else:
        cur.execute(
            "INSERT INTO states_meta(app, serial, version, checksum, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (app, serial, 1, checksum, created_at, updated_at),
        )


def upsert_state(app: str, serial: str, payload: object) -> None:
    """Insert or replace a single serial payload for an app. Also maintains states_meta and context_history."""
    payload_text = json.dumps(payload, ensure_ascii=False, separators=(',', ':')) if payload is not None else 'null'
    checksum = compute_checksum(payload)
    now = datetime.datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'
    with _writer_lock:
        conn = _connect()
        try:
            cur = conn.cursor()
            cur.execute("PRAGMA journal_mode = WAL;")
            cur.execute("PRAGMA synchronous = NORMAL;")
            cur.execute(
                "INSERT OR REPLACE INTO states(app, serial, payload, updated_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
                (app, serial, payload_text),
            )
            # update meta table
            try:
                _upsert_states_meta(conn, app, serial, checksum, None, now)
            except Exception:
                pass
            # append simple history row
            try:
                cur.execute(
                    "INSERT INTO context_history(app, serial, payload, change_type, actor) VALUES (?, ?, ?, ?, ?)",
                    (app, serial, payload_text, 'upsert', 'system'),
                )
            except Exception:
                pass
            conn.commit()
        finally:
            conn.close()


def upsert_store_meta(app: str, key: str, value: object) -> None:
    """Insert or replace a key/value JSON metadata entry for an app."""
    value_text = json.dumps(value, ensure_ascii=False, separators=(',', ':')) if value is not None else 'null'
    with _writer_lock:
        conn = _connect()
        try:
            cur = conn.cursor()
            cur.execute("PRAGMA journal_mode = WAL;")
            cur.execute("PRAGMA synchronous = NORMAL;")
            cur.execute(
                "INSERT OR REPLACE INTO store_meta(app, key, value) VALUES (?, ?, ?)",
                (app, key, value_text),
            )
            conn.commit()
        finally:
            conn.close()


def load_state(app: str, serial: str) -> Optional[object]:
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute("SELECT payload FROM states WHERE app = ? AND serial = ?", (app, serial))
        row = cur.fetchone()
        if not row:
            return None
        text = row[0]
        if text is None:
            return None
        try:
            return json.loads(text)
        except Exception:
            return text
    finally:
        conn.close()


def list_app_states(app: str) -> Dict[str, object]:
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute("SELECT serial, payload FROM states WHERE app = ?", (app,))
        out = {}
        for serial, payload_text in cur.fetchall():
            try:
                out[serial] = json.loads(payload_text) if payload_text is not None else None
            except Exception:
                out[serial] = payload_text
        return out
    finally:
        conn.close()


def delete_state(app: str, serial: str) -> None:
    with _writer_lock:
        conn = _connect()
        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM states WHERE app = ? AND serial = ?", (app, serial))
            conn.commit()
        finally:
            conn.close()


def migrate_from_state_json(app_path: Path, app_name: Optional[str] = None) -> int:
    """Load existing state.json (aggregated) under app_path/context_store/state.json and insert into DB.
    Returns number of entries migrated.
    This function is non-destructive: it will create backups of the DB and the state.json/meta.json files before importing.
    Additionally, it will update states_meta entries with checksums.
    """
    cs = Path(app_path) / 'context_store'
    state_file = cs / 'state.json'
    meta_file = cs / 'meta.json'
    if not state_file.exists():
        return 0

    # ensure DB initialized
    if _db_path is None:
        init_db()

    # create backups directory under the app context_store
    backups_dir = cs / 'meta_backups'
    backups_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
    # backup DB snapshot
    try:
        backup_dest = backups_dir / f'context_store_backup_{timestamp}.sqlite3'
        backup_db(str(backup_dest))
    except Exception:
        # continue even if DB backup fails
        pass

    # copy state.json to backups
    try:
        shutil.copy2(str(state_file), str(backups_dir / f'state-{timestamp}.json'))
    except Exception:
        pass
    # copy meta.json if exists
    try:
        if meta_file.exists():
            shutil.copy2(str(meta_file), str(backups_dir / f'meta-{timestamp}.json'))
    except Exception:
        pass

    try:
        with state_file.open('r', encoding='utf-8') as f:
            obj = json.load(f)
    except Exception:
        return 0
    if not isinstance(obj, dict):
        return 0
    count = 0
    app_key = app_name or Path(app_path).name
    conn = _connect()
    try:
        cur = conn.cursor()
        for serial, entry in obj.items():
            try:
                payload_text = json.dumps(entry, ensure_ascii=False, separators=(',', ':')) if entry is not None else 'null'
                cur.execute(
                    "INSERT OR REPLACE INTO states(app, serial, payload, updated_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
                    (app_key, str(serial), payload_text),
                )
                checksum = compute_checksum(entry)
                now = datetime.datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'
                try:
                    _upsert_states_meta(conn, app_key, str(serial), checksum, None, now)
                except Exception:
                    pass
                try:
                    cur.execute(
                        "INSERT INTO context_history(app, serial, payload, change_type, actor) VALUES (?, ?, ?, ?, ?)",
                        (app_key, str(serial), payload_text, 'migrate', 'migration_script'),
                    )
                except Exception:
                    pass
                count += 1
            except Exception:
                continue
        conn.commit()
    finally:
        conn.close()

    # import meta.json as a single metadata blob for the app
    try:
        if meta_file.exists():
            with meta_file.open('r', encoding='utf-8') as mf:
                meta_obj = json.load(mf)
            upsert_store_meta(app_key, 'meta.json', meta_obj)
    except Exception:
        pass

    return count


def backup_db(dest_path) -> Path:
    """Create a consistent copy of the underlying sqlite DB to dest_path using sqlite's backup API.
    Returns the Path to the created backup file. Ensures '.sqlite3' extension for consistency.
    """
    if _db_path is None:
        init_db()
    dest = Path(dest_path)
    # ensure extension
    if dest.suffix not in {'.sqlite', '.sqlite3'}:
        dest = dest.with_suffix('.sqlite3')
    dest.parent.mkdir(parents=True, exist_ok=True)
    # Use two separate connections for backup; open source in read-only mode to be safe
    src = sqlite3.connect(str(_db_path), timeout=30, check_same_thread=False)
    dest_conn = sqlite3.connect(str(dest), timeout=30)
    try:
        # Use backup API (writes a consistent snapshot)
        src.backup(dest_conn)
        dest_conn.commit()
    finally:
        try:
            dest_conn.close()
        except Exception:
            pass
        try:
            src.close()
        except Exception:
            pass
    return dest


def get_store_stats(app: Optional[str] = None) -> Dict[str, int]:
    """Return simple stats: total states, per-app counts"""
    if _db_path is None:
        init_db()
    conn = _connect()
    try:
        cur = conn.cursor()
        stats = {}
        if app:
            cur.execute("SELECT COUNT(*) FROM states WHERE app = ?", (app,))
            stats['count'] = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM context_history WHERE app = ?", (app,))
            stats['history_count'] = cur.fetchone()[0]
            return stats
        cur.execute("SELECT app, COUNT(*) FROM states GROUP BY app")
        for a, c in cur.fetchall():
            stats[a] = c
        return stats
    finally:
        conn.close()


def health_check_db() -> Dict[str, object]:
    """Quick health check of DB: accessibility, tables existence, wal mode"""
    result = {'ok': False, 'errors': [], 'details': {}}
    try:
        if _db_path is None:
            init_db()
        conn = _connect()
        try:
            cur = conn.cursor()
            cur.execute("PRAGMA journal_mode;")
            result['details']['journal_mode'] = cur.fetchone()[0]
            cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [r[0] for r in cur.fetchall()]
            result['details']['tables'] = tables
            result['ok'] = True
        finally:
            conn.close()
    except Exception as e:
        result['errors'].append(str(e))
    return result
