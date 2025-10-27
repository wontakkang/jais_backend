# -*- coding: utf-8 -*-
from datetime import datetime
import time
from utils.calculation import all_dict as calculation_methods
from utils.logger import log_exceptions, log_execution_time
from django.utils import timezone
from pathlib import Path
# Redis instance from shared connection module
from . import logger, redis_instance
import re
import json

sockets = []


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
            if isinstance(parsed, (int, float)):
                return float(parsed)
        except Exception:
            pass
        # try raw numeric parse
        try:
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
        return 'str'
    return type(value).__name__


@log_exceptions(logger)
@log_execution_time(logger)
def redis_to_db(resolution_minutes: int = 2):
    """Scan Redis keys named 'client_id:var_id' in DB0, aggregate current values into
    a time-bucket of `resolution_minutes` (default 2) and upsert into TwoMinuteData.

    This function performs a single pass. For periodic execution, call it from a scheduler.
    """
    from . import models
    now = timezone.now()

    # floor timestamp to the nearest resolution_minutes
    minute_bucket = (now.minute // resolution_minutes) * resolution_minutes
    bucket_ts = now.replace(minute=minute_bucket, second=0, microsecond=0)

    # use UTC-aware timestamp for DB
    timestamp = bucket_ts

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

        numeric = _coerce_numeric(value)

        # maintain aggregates per (var_id) as uniqueness defined by timestamp+var_id
        agg_key = (var_id,)
        if agg_key not in aggregates:
            aggregates[agg_key] = {
                'client_ids': set(),
                'sum': 0.0,
                'min': None,
                'max': None,
                'count': 0,
                'last': None,
            }

        entry = aggregates[agg_key]
        entry['client_ids'].add(client_id)
        if numeric is not None:
            entry['sum'] += numeric
            entry['count'] += 1
            entry['last'] = numeric
            if entry['min'] is None or numeric < entry['min']:
                entry['min'] = numeric
            if entry['max'] is None or numeric > entry['max']:
                entry['max'] = numeric
        else:
            # non-numeric values considered as last value but not part of numeric aggregation
            entry['last'] = value

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
        # choose stored value: last numeric if exists else None
        value_field = agg['last'] if isinstance(agg['last'], (int, float)) else None
        # determine value type from last value
        value_type_field = _value_type(agg.get('last'))

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
                timestamp=timestamp,
                var_id=var_id,
                defaults=defaults
            )
            if created_flag:
                created += 1
            else:
                updated += 1
        except Exception as e:
            logger.error(f'Failed to upsert TwoMinuteData for var_id={var_id}: {e}')

    logger.info(f'redis_to_db completed: buckets={len(aggregates)}, created={created}, updated={updated}')

    return {'buckets': len(aggregates), 'created': created, 'updated': updated}