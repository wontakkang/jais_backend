# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
import time
from utils.calculation import all_dict as calculation_methods
from utils.logger import log_exceptions, log_execution_time
from django.utils import timezone
from pathlib import Path
# Redis instance from shared connection module
from . import logger, redis_instance
import re
import json
import os
try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None

# Redis에 저장된 datetime은 로컬 시간으로 저장되어 있다고 가정 (기본 +09:00, Asia/Seoul)
REDIS_LOCAL_TZ = None
try:
    redis_tz_name = os.getenv('REDIS_TIME_ZONE', 'Asia/Seoul')
    REDIS_LOCAL_TZ = ZoneInfo(redis_tz_name) if ZoneInfo else timezone.get_default_timezone()
except Exception:
    REDIS_LOCAL_TZ = timezone.get_default_timezone()

sockets = []

# DB 저장 시 오프셋 시간(+9h) 적용: 환경변수 DB_SAVE_OFFSET_HOURS로 조정 가능
DB_SAVE_OFFSET_HOURS = int(os.getenv('DB_SAVE_OFFSET_HOURS', '9'))

def _to_db_time(dt):
    try:
        return dt
    except Exception:
        return dt


def _coerce_numeric(value):
    """Try to convert value to numeric (int/float). Return float or None if not numeric."""
    if value is None:
        return None
    # booleans are numeric-ish but keep as ints
    if isinstance(value, bool):
        return float(int(value))
    if isinstance(value, (int, float)):
        return float(value)
    # if it's a JSON encoded string, try to decode
    if isinstance(value, str):
        # try JSON
        try:
            parsed = json.loads(value)
            if isinstance(parsed, (int, float, bool)):
                # keep bool as 0/1
                return float(int(parsed)) if isinstance(parsed, bool) else float(parsed)
        except Exception:
            pass
        # try raw numeric parse
        try:
            if value.lower() in ("true", "false"):
                return 1.0 if value.lower() == "true" else 0.0
            if '.' in value:
                return float(value)
            return float(int(value))
        except Exception:
            return None
    return None


def _value_type(value):
    if value is None:
        return 'null'
    if isinstance(value, bool):
        return 'bool'
    if isinstance(value, int) and not isinstance(value, bool):
        return 'int'
    if isinstance(value, float):
        return 'float'
    if isinstance(value, str):
        # recognize boolean-like strings
        if value.strip().lower() in ('true', 'false'):
            return 'bool'
        # distinguish int-like vs float-like quickly
        try:
            int(value)
            if '.' not in value:
                return 'int'
        except Exception:
            pass
        try:
            float(value)
            return 'float'
        except Exception:
            return 'str'
    return type(value).__name__


def _classify_value(value):
    """
    Return (value_type_label, numeric_value) where numeric_value is float or None.
    Rules:
    - bool/"true"/"false" -> ('bool', 1.0 or 0.0)
    - int -> ('int', float(int))
    - float -> ('float', float)
    - numeric strings -> classified accordingly
    - others -> ('str' or type name, None)
    """
    # bytes -> decode to str
    if isinstance(value, (bytes, bytearray)):
        try:
            value = value.decode('utf-8', errors='ignore')
        except Exception:
            value = str(value)

    if value is None:
        return ('null', None)

    if isinstance(value, bool):
        return ('bool', 1.0 if value else 0.0)

    if isinstance(value, int) and not isinstance(value, bool):
        return ('int', float(value))

    if isinstance(value, float):
        return ('float', float(value))

    if isinstance(value, str):
        s = value.strip()
        low = s.lower()
        if low in ('true', 'false'):
            return ('bool', 1.0 if low == 'true' else 0.0)
        # try int first (no dot, no exponent)
        try:
            if '.' not in s and 'e' not in low and 'E' not in s:
                iv = int(s)
                return ('int', float(iv))
        except Exception:
            pass
        # then float
        try:
            fv = float(s)
            return ('float', fv)
        except Exception:
            return ('str', None)

    # try JSON parse as last resort
    try:
        parsed = json.loads(value)
        return _classify_value(parsed)
    except Exception:
        return (type(value).__name__, None)


# 로컬 naive datetime 강제 보조 함수
def _ensure_naive_local(dt: datetime) -> datetime:
    try:
        tz = timezone.get_default_timezone()
        if timezone.is_aware(dt):
            try:
                return timezone.make_naive(dt, tz)
            except Exception:
                return dt.replace(tzinfo=None)
        return dt
    except Exception:
        return dt.replace(tzinfo=None) if hasattr(dt, 'tzinfo') and dt.tzinfo else dt


def _parse_scheduled_time(at):
    """
    datetime 또는 ISO 문자열을 받아 최종적으로 '로컬 naive(datetime.tzinfo=None)'로 반환합니다.
    규칙:
    - 문자열 끝 Z는 UTC로 간주해 변환
    - naive 입력은 REDIS_LOCAL_TZ(기본 Asia/Seoul, +09:00)로 인지 후 기본 타임존으로 변환
    - 결과는 항상 기본 타임존의 naive 로컬 시간
    """
    if at is None:
        return None
    if isinstance(at, datetime):
        dt = at
    elif isinstance(at, str):
        s = at.strip()
        if s.endswith('Z'):
            s = s[:-1] + '+00:00'
        try:
            dt = datetime.fromisoformat(s)
        except Exception:
            logger.warning(f"Failed to parse 'at' as ISO datetime: {at}")
            return None
    else:
        logger.warning(f"Unsupported type for 'at': {type(at)}")
        return None

    default_tz = timezone.get_default_timezone()

    # naive면 REDIS_LOCAL_TZ로 인지
    if timezone.is_naive(dt):
        try:
            dt = timezone.make_aware(dt, REDIS_LOCAL_TZ)
        except Exception:
            dt = timezone.make_aware(dt)

    # 기본 타임존으로 변환 후 naive로 변환
    try:
        dt = dt.astimezone(default_tz)
    except Exception:
        pass
    try:
        dt = timezone.make_naive(dt, default_tz)
    except Exception:
        dt = dt.replace(tzinfo=None)
    return dt


@log_exceptions(logger)
@log_execution_time(logger)
def redis_to_db(resolution_minutes: int = 2, at=None):
    """
    Redis의 'client_id:var_id' 키를 스캔하여 현재 값을 집계하고,
    지정된 시간 버킷(timestamp)에 TwoMinuteData로 업서트합니다.

    - APScheduler에서 실행 시, 예약된 실행 시각을 `at` 인자로 전달하세요.
      예) scheduler.add_job(redis_to_db, 'cron', minute='*/2', kwargs={'at': '2025-10-28T12:34:00Z'})
    - `at`가 없으면 현재 시간(timezone.now()) 기준으로 버킷을 계산합니다.
    - 모든 시각은 프로젝트 기본 타임존(TIME_ZONE, 로컬타임)으로 변환 후 버킷을 산출/저장합니다.
    - 버킷은 resolution_minutes 단위로 내림(floor)됩니다.
    - 논리값 false/true는 boolean으로 분류되고 값은 0/1로 저장됩니다.
    - 정수 1, 10, -5는 integer로 분류되고 값은 float로 저장됩니다.
    - 실수 1.5, -3.14는 float로 분류됩니다.
    - 사용예시: redis_to_db(resolution_minutes=2, at='2025-10-28T12:34:00Z')
    """
    from . import models

    # 기준 시각: 로컬 naive로 확보
    base_time = _parse_scheduled_time(at) or timezone.now()
    base_time = _ensure_naive_local(base_time)

    # 버킷 계산
    minute_bucket = (base_time.minute // resolution_minutes) * resolution_minutes
    bucket_ts = base_time.replace(minute=minute_bucket, second=0, microsecond=0)

    # DB 저장용 타임스탬프 (naive local)
    db_timestamp = _to_db_time(bucket_ts)

    # Log which time was used
    try:
        logger.info(
            f"redis_to_db start: local_bucket={bucket_ts.isoformat()}, db_bucket={db_timestamp.isoformat()}, resolution={resolution_minutes}m"
        )
    except Exception:
        pass

    # scan keys with pattern like 'number:number'
    pattern = '*:*'
    try:
        keys = redis_instance.query_scan(pattern)
    except Exception:
        try:
            keys = redis_instance.client.keys(pattern) if hasattr(redis_instance, 'client') and redis_instance.client else []
        except Exception:
            keys = []

    # aggregate per var_id (TwoMinuteData.unique_together = (timestamp, var_id))
    aggregates = {}

    for key in keys:
        # parse only keys that look like 'int:int'
        if not isinstance(key, str) or ':' not in key:
            continue
        parts = key.split(':')
        if len(parts) != 2:
            continue
        try:
            client_id = int(parts[0])
            var_id = int(parts[1])
        except Exception:
            continue

        # read value (try JSON-decoded get_value first)
        try:
            value = redis_instance.get_value(key)
        except Exception:
            try:
                value = redis_instance.client.get(key)
            except Exception:
                value = None

        # classify and coerce to numeric if applicable
        vtype, vnum = _classify_value(value)

        # maintain aggregates per (var_id) as uniqueness defined by timestamp+var_id
        agg_key = (var_id,)
        if agg_key not in aggregates:
            aggregates[agg_key] = {
                'client_ids': set(),
                'sum': 0.0,
                'min': None,
                'max': None,
                'count': 0,
                'last_numeric': None,
                'last_label': 'null',
            }

        entry = aggregates[agg_key]
        entry['client_ids'].add(client_id)
        if vnum is not None:
            entry['sum'] += float(vnum)
            entry['count'] += 1
            entry['last_numeric'] = float(vnum)
            entry['last_label'] = vtype
            if entry['min'] is None or vnum < entry['min']:
                entry['min'] = float(vnum)
            if entry['max'] is None or vnum > entry['max']:
                entry['max'] = float(vnum)
        else:
            # non-numeric values: only track type label
            entry['last_label'] = vtype

    # upsert aggregated rows into TwoMinuteData
    created = 0
    updated = 0
    for (var_id,), agg in aggregates.items():
        # prepare fields
        count = agg['count']
        sum_value = agg['sum'] if count > 0 else None
        min_value = agg['min']
        max_value = agg['max']
        avg_value = (sum_value / count) if count > 0 else None

        value_field = agg['last_numeric'] if agg['last_numeric'] is not None else None
        value_type_field = agg['last_label']

        # group_id is unknown in Redis key; set to 0 by default
        defaults = {
            'client_id': next(iter(agg['client_ids'])) if agg['client_ids'] else 0,
            'group_id': 0,
            'value': value_field,
            'value_type': value_type_field,
            'min_value': min_value,
            'max_value': max_value,
            'avg_value': avg_value,
            'sum_value': sum_value,
            'count': count if count > 0 else None,
        }

        # use update_or_create based on unique keys timestamp + var_id
        try:
            obj, created_flag = models.TwoMinuteData.objects.update_or_create(
                timestamp=db_timestamp,
                var_id=var_id,
                defaults=defaults
            )
            if created_flag:
                created += 1
            else:
                updated += 1
        except Exception as e:
            logger.error(f'Failed to upsert TwoMinuteData for var_id={var_id}: {e}')

    logger.info(f'redis_to_db completed: buckets={len(aggregates)}, created={created}, updated={updated}, db_bucket={db_timestamp.isoformat()}')

    return {'buckets': len(aggregates), 'created': created, 'updated': updated, 'bucket_ts': db_timestamp.isoformat()}


@log_exceptions(logger)
@log_execution_time(logger)
def aggregate_2min_to_10min(at=None):
    """
    data_2min(TwoMinuteData)를 */10 분 단위로 집계해 data_10min(TenMinuteData)을 구성합니다.
    - 집계 구간: [버킷 시작, 버킷 시작 + 10분)
    - 각 var_id별로 약 5개의 2분 데이터에서 min/max/avg/sum/count를 산출
    - TenMinuteData.value에는 avg를 저장, value_type은 'float' (집계 불가 시 'null')

    매개변수:
    - at: 예약 실행 시각(문자열 ISO 또는 datetime). 없으면 현재 로컬 시간 기준.

    사용 예시:
    - aggregate_2min_to_10min()
    - aggregate_2min_to_10min(at='2025-10-28T12:30:00Z')
    - scheduler.add_job(aggregate_2min_to_10min, 'cron', minute='*/10', kwargs={'at': '2025-10-28T12:30:00Z'})
    """
    from . import models

    # 기준 시각: 로컬 naive로 확보
    base_time = _parse_scheduled_time(at) or timezone.now()
    base_time = _ensure_naive_local(base_time)

    # 10분 버킷으로 내림
    minute_bucket = (base_time.minute // 10) * 10
    bucket_start = base_time.replace(minute=minute_bucket, second=0, microsecond=0)
    bucket_end = bucket_start + timedelta(minutes=10)

    # DB 조회/저장용 타임스탬프 범위 (naive local)
    db_start = _to_db_time(bucket_start)
    db_end = _to_db_time(bucket_end)

    try:
        logger.info(f"aggregate_2min_to_10min start: local={bucket_start.isoformat()}~{bucket_end.isoformat()}, db={db_start.isoformat()}~{db_end.isoformat()}")
    except Exception:
        pass

    # 집계 대상 로우 로드 (DB에는 오프셋 적용된 시간으로 저장됨)
    rows = models.TwoMinuteData.objects.filter(timestamp__gte=db_start, timestamp__lt=db_end)

    # var_id별 집계
    agg = {}
    for r in rows:
        vid = r.var_id
        if vid not in agg:
            agg[vid] = {
                'client_ids': set(),
                'group_ids': set(),
                'sum': 0.0,
                'count': 0,
                'min': None,
                'max': None,
            }
        g = agg[vid]
        if r.client_id is not None:
            g['client_ids'].add(r.client_id)
        if r.group_id is not None:
            g['group_ids'].add(r.group_id)

        # row-level 집계값 계산
        row_count = r.count if r.count is not None else (1 if r.value is not None else 0)
        row_sum = r.sum_value if r.sum_value is not None else (float(r.value) if r.value is not None else 0.0)

        # min/max 후보값: min_value/max_value 우선, 없으면 value 사용
        min_candidate = r.min_value if r.min_value is not None else r.value
        max_candidate = r.max_value if r.max_value is not None else r.value

        # 합산/카운트 누적
        if row_count and row_sum is not None:
            try:
                g['sum'] += float(row_sum)
                g['count'] += int(row_count)
            except Exception:
                pass

        # 최소/최대 갱신
        if min_candidate is not None:
            try:
                mv = float(min_candidate)
                if g['min'] is None or mv < g['min']:
                    g['min'] = mv
            except Exception:
                pass
        if max_candidate is not None:
            try:
                xv = float(max_candidate)
                if g['max'] is None or xv > g['max']:
                    g['max'] = xv
            except Exception:
                pass

    created = 0
    updated = 0
    for vid, g in agg.items():
        if g['count'] <= 0:
            # 데이터 없음: 업서트 생략
            continue
        sum_value = g['sum']
        count = g['count']
        avg_value = (sum_value / count) if count > 0 else None
        min_value = g['min']
        max_value = g['max']

        defaults = {
            'client_id': next(iter(g['client_ids'])) if g['client_ids'] else 0,
            'group_id': next(iter(g['group_ids'])) if g['group_ids'] else 0,
            'value': avg_value,
            'value_type': 'float' if avg_value is not None else 'null',
            'min_value': min_value,
            'max_value': max_value,
            'avg_value': avg_value,
            'sum_value': sum_value,
            'count': count,
        }
        try:
            obj, created_flag = models.TenMinuteData.objects.update_or_create(
                timestamp=db_start,
                var_id=vid,
                defaults=defaults,
            )
            if created_flag:
                created += 1
            else:
                updated += 1
        except Exception as e:
            logger.error(f"TenMinuteData upsert 실패: var_id={vid}, err={e}")

    logger.info(f"aggregate_2min_to_10min completed: db_bucket_start={db_start.isoformat()}, created={created}, updated={updated}, sources={len(rows)}")
    return {
        'bucket_start': db_start.isoformat(),
        'created': created,
        'updated': updated,
        'sources': len(rows),
        'var_count': len(agg),
    }


@log_exceptions(logger)
@log_execution_time(logger)
def aggregate_to_1hour(at=None):
    """
    1시간 데이터를 구성합니다.
    - 기준: 로컬 타임존 기준으로 at(없으면 now)를 받아 해당 시각을 시간 단위로 내림한 버킷을 사용
    - 규칙: var_id별로 10분데이터가 3개 이상이면 TenMinuteData로 집계,
            3개 미만이면 TwoMinuteData로 집계
    - 산출: min, max, avg, sum, count 계산 후 HourlyData에 업서트

    사용 예시:
    - aggregate_to_1hour()
    - aggregate_to_1hour(at='2025-10-28T13:00:00Z')
    - scheduler.add_job(aggregate_to_1hour, 'cron', minute=0, kwargs={'at': '2025-10-28T13:00:00Z'})
    """
    from . import models
    from datetime import timedelta

    # 기준 시각: 로컬 naive로 확보
    base_time = _parse_scheduled_time(at) or timezone.now()
    base_time = _ensure_naive_local(base_time)

    # 1시간 버킷 시작/끝 (naive local)
    bucket_start = base_time.replace(minute=0, second=0, microsecond=0)
    bucket_end = bucket_start + timedelta(hours=1)

    db_start = _to_db_time(bucket_start)
    db_end = _to_db_time(bucket_end)

    try:
        logger.info(
            f"aggregate_to_1hour start: local={bucket_start.isoformat()}~{bucket_end.isoformat()}, db={db_start.isoformat()}~{db_end.isoformat()}"
        )
    except Exception:
        pass

    # 데이터 조회 (DB 상의 오프로 저장된 타임스탬프 기준)
    ten_rows = models.TenMinuteData.objects.filter(timestamp__gte=db_start, timestamp__lt=db_end)
    two_rows = models.TwoMinuteData.objects.filter(timestamp__gte=db_start, timestamp__lt=db_end)

    # 10분 집계 사전
    ten_agg = {}
    for r in ten_rows:
        vid = r.var_id
        if vid not in ten_agg:
            ten_agg[vid] = {
                'client_ids': set(),
                'group_ids': set(),
                'sum': 0.0,
                'count': 0,
                'min': None,
                'max': None,
                'slots': 0,  # 10분 슬롯 수
            }
        g = ten_agg[vid]
        if r.client_id is not None:
            g['client_ids'].add(r.client_id)
        if r.group_id is not None:
            g['group_ids'].add(r.group_id)

        # row-level 수치 추출 (sum/count 우선, 없으면 avg*count, 최후엔 value)
        rc = r.count if r.count is not None else (1 if r.value is not None else 0)
        if r.sum_value is not None:
            rs = float(r.sum_value)
        elif r.avg_value is not None and rc:
            rs = float(r.avg_value) * int(rc)
        else:
            rs = float(r.value) if r.value is not None else 0.0

        if rc and rs is not None:
            try:
                g['sum'] += float(rs)
                g['count'] += int(rc)
            except Exception:
                pass

        # min/max 후보
        min_c = r.min_value if r.min_value is not None else r.value
        max_c = r.max_value if r.max_value is not None else r.value
        if min_c is not None:
            try:
                mv = float(min_c)
                if g['min'] is None or mv < g['min']:
                    g['min'] = mv
            except Exception:
                pass
        if max_c is not None:
            try:
                xv = float(max_c)
                if g['max'] is None or xv > g['max']:
                    g['max'] = xv
            except Exception:
                pass

        g['slots'] += 1

    # 2분 집계 사전 (fallback)
    two_agg = {}
    for r in two_rows:
        vid = r.var_id
        if vid not in two_agg:
            two_agg[vid] = {
                'client_ids': set(),
                'group_ids': set(),
                'sum': 0.0,
                'count': 0,
                'min': None,
                'max': None,
            }
        g = two_agg[vid]
        if r.client_id is not None:
            g['client_ids'].add(r.client_id)
        if r.group_id is not None:
            g['group_ids'].add(r.group_id)

        rc = r.count if r.count is not None else (1 if r.value is not None else 0)
        rs = r.sum_value if r.sum_value is not None else (float(r.value) if r.value is not None else 0.0)
        if rc and rs is not None:
            try:
                g['sum'] += float(rs)
                g['count'] += int(rc)
            except Exception:
                pass

        min_c = r.min_value if r.min_value is not None else r.value
        max_c = r.max_value if r.max_value is not None else r.value
        if min_c is not None:
            try:
                mv = float(min_c)
                if g['min'] is None or mv < g['min']:
                    g['min'] = mv
            except Exception:
                pass
        if max_c is not None:
            try:
                xv = float(max_c)
                if g['max'] is None or xv > g['max']:
                    g['max'] = xv
            except Exception:
                pass

    # 처리 대상 var_id 집합
    all_vids = set(ten_agg.keys()) | set(two_agg.keys())

    created = 0
    updated = 0
    for vid in all_vids:
        use_ten = (vid in ten_agg and ten_agg[vid].get('slots', 0) >= 3)
        src = ten_agg[vid] if use_ten else two_agg.get(vid)
        if not src or src.get('count', 0) <= 0:
            continue

        sum_value = src['sum']
        count = src['count']
        avg_value = (sum_value / count) if count > 0 else None
        min_value = src['min']
        max_value = src['max']

        defaults = {
            'client_id': next(iter(src['client_ids'])) if src['client_ids'] else 0,
            'group_id': next(iter(src['group_ids'])) if src['group_ids'] else 0,
            'value': avg_value,
            'value_type': 'float' if avg_value is not None else 'null',
            'min_value': min_value,
            'max_value': max_value,
            'avg_value': avg_value,
            'sum_value': sum_value,
            'count': count,
        }
        try:
            obj, created_flag = models.HourlyData.objects.update_or_create(
                timestamp=db_start,
                var_id=vid,
                defaults=defaults,
            )
            if created_flag:
                created += 1
            else:
                updated += 1
        except Exception as e:
            logger.error(f"HourlyData upsert 실패: var_id={vid}, err={e}")

    logger.info(
        f"aggregate_to_1hour completed: db_bucket_start={db_start.isoformat()}, created={created}, updated={updated}, ten_sources={len(ten_rows)}, two_sources={len(two_rows)}"
    )

    return {
        'bucket_start': db_start.isoformat(),
        'created': created,
        'updated': updated,
        'ten_sources': len(ten_rows),
        'two_sources': len(two_rows),
        'var_count': len(all_vids),
    }


@log_exceptions(logger)
@log_execution_time(logger)
def aggregate_to_daily(at=None):
    """
    1일(일간) 데이터를 구성합니다.
    - 기준: 로컬 타임존 기준으로 at(없으면 now)를 받아 해당 날짜의 00:00:00로 내림한 버킷 사용
    - 규칙: var_id별로 10분데이터가 3개 이상이면 TenMinuteData로 집계,
            3개 미만이면 TwoMinuteData로 집계
    - 산출: min, max, avg, sum, count 계산 후 DailyData에 업서트

    사용 예시:
    - aggregate_to_daily()
    - aggregate_to_daily(at='2025-10-28T00:00:00Z')
    - scheduler.add_job(aggregate_to_daily, 'cron', hour=0, minute=5, kwargs={'at': '2025-10-28T00:00:00Z'})
    """
    from . import models

    # 기준 시각: 로컬 naive로 확보
    base_time = _parse_scheduled_time(at) or timezone.now()
    base_time = _ensure_naive_local(base_time)

    # 일간 버킷 시작/끝 (naive local)
    bucket_start = base_time.replace(hour=0, minute=0, second=0, microsecond=0)
    bucket_end = bucket_start + timedelta(days=1)

    db_start = _to_db_time(bucket_start)
    db_end = _to_db_time(bucket_end)

    try:
        logger.info(
            f"aggregate_to_daily start: local={bucket_start.isoformat()}~{bucket_end.isoformat()}, db={db_start.isoformat()}~{db_end.isoformat()}"
        )
    except Exception:
        pass

    # 데이터 조회 (DB 상의 오프로 저장된 타임스탬프 기준)
    ten_rows = models.TenMinuteData.objects.filter(timestamp__gte=db_start, timestamp__lt=db_end)
    two_rows = models.TwoMinuteData.objects.filter(timestamp__gte=db_start, timestamp__lt=db_end)

    # 10분 집계 사전
    ten_agg = {}
    for r in ten_rows:
        vid = r.var_id
        if vid not in ten_agg:
            ten_agg[vid] = {
                'client_ids': set(),
                'group_ids': set(),
                'sum': 0.0,
                'count': 0,
                'min': None,
                'max': None,
                'slots': 0,  # 10분 슬롯 수
            }
        g = ten_agg[vid]
        if r.client_id is not None:
            g['client_ids'].add(r.client_id)
        if r.group_id is not None:
            g['group_ids'].add(r.group_id)

        rc = r.count if r.count is not None else (1 if r.value is not None else 0)
        if r.sum_value is not None:
            rs = float(r.sum_value)
        elif r.avg_value is not None and rc:
            rs = float(r.avg_value) * int(rc)
        else:
            rs = float(r.value) if r.value is not None else 0.0

        if rc and rs is not None:
            try:
                g['sum'] += float(rs)
                g['count'] += int(rc)
            except Exception:
                pass

        min_c = r.min_value if r.min_value is not None else r.value
        max_c = r.max_value if r.max_value is not None else r.value
        if min_c is not None:
            try:
                mv = float(min_c)
                if g['min'] is None or mv < g['min']:
                    g['min'] = mv
            except Exception:
                pass
        if max_c is not None:
            try:
                xv = float(max_c)
                if g['max'] is None or xv > g['max']:
                    g['max'] = xv
            except Exception:
                pass

        g['slots'] += 1

    # 2분 집계 사전 (fallback)
    two_agg = {}
    for r in two_rows:
        vid = r.var_id
        if vid not in two_agg:
            two_agg[vid] = {
                'client_ids': set(),
                'group_ids': set(),
                'sum': 0.0,
                'count': 0,
                'min': None,
                'max': None,
            }
        g = two_agg[vid]
        if r.client_id is not None:
            g['client_ids'].add(r.client_id)
        if r.group_id is not None:
            g['group_ids'].add(r.group_id)

        rc = r.count if r.count is not None else (1 if r.value is not None else 0)
        rs = r.sum_value if r.sum_value is not None else (float(r.value) if r.value is not None else 0.0)
        if rc and rs is not None:
            try:
                g['sum'] += float(rs)
                g['count'] += int(rc)
            except Exception:
                pass

        min_c = r.min_value if r.min_value is not None else r.value
        max_c = r.max_value if r.max_value is not None else r.value
        if min_c is not None:
            try:
                mv = float(min_c)
                if g['min'] is None or mv < g['min']:
                    g['min'] = mv
            except Exception:
                pass
        if max_c is not None:
            try:
                xv = float(max_c)
                if g['max'] is None or xv > g['max']:
                    g['max'] = xv
            except Exception:
                pass

    # 처리 대상 var_id 집합
    all_vids = set(ten_agg.keys()) | set(two_agg.keys())

    created = 0
    updated = 0
    for vid in all_vids:
        use_ten = (vid in ten_agg and ten_agg[vid].get('slots', 0) >= 3)
        src = ten_agg[vid] if use_ten else two_agg.get(vid)
        if not src or src.get('count', 0) <= 0:
            continue

        sum_value = src['sum']
        count = src['count']
        avg_value = (sum_value / count) if count > 0 else None
        min_value = src['min']
        max_value = src['max']

        defaults = {
            'client_id': next(iter(src['client_ids'])) if src['client_ids'] else 0,
            'group_id': next(iter(src['group_ids'])) if src['group_ids'] else 0,
            'value': avg_value,
            'value_type': 'float' if avg_value is not None else 'null',
            'min_value': min_value,
            'max_value': max_value,
            'avg_value': avg_value,
            'sum_value': sum_value,
            'count': count,
        }
        try:
            obj, created_flag = models.DailyData.objects.update_or_create(
                timestamp=db_start,
                var_id=vid,
                defaults=defaults,
            )
            if created_flag:
                created += 1
            else:
                updated += 1
        except Exception as e:
            logger.error(f"DailyData upsert 실패: var_id={vid}, err={e}")

    logger.info(
        f"aggregate_to_daily completed: db_bucket_start={db_start.isoformat()}, created={created}, updated={updated}, ten_sources={len(ten_rows)}, two_sources={len(two_rows)}"
    )

    return {
        'bucket_start': db_start.isoformat(),
        'created': created,
        'updated': updated,
        'ten_sources': len(ten_rows),
        'two_sources': len(two_rows),
        'var_count': len(all_vids),
    }