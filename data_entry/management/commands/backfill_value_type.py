from django.core.management.base import BaseCommand
from django.db import transaction
from data_entry import models
import math
import json


class Command(BaseCommand):
    help = "Backfill value_type field for time-series models (TwoMinuteData, TenMinuteData, HourlyData, DailyData)."

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', dest='dry_run', help='Do not persist changes; just report')
        parser.add_argument('--batch-size', type=int, dest='batch_size', default=500, help='Number of rows to process per batch')
        parser.add_argument('--models', nargs='*', dest='models', default=['TwoMinuteData', 'TenMinuteData', 'HourlyData', 'DailyData'], help='Model class names to process')

    def _infer_type(self, value):
        """Infer a simple type string for a given value.

        Rules:
        - None -> None
        - Python bool -> 'bool'
        - Python int/float -> 'int' or 'float'
        - Strings: handle 'true'/'false' (case-insensitive) -> 'bool'
          try JSON decoding -> infer from decoded value (support dict/list: try common keys)
          try numeric parse -> 'int'/'float'
          else -> 'str'
        """
        if value is None:
            return None

        # direct python types
        if isinstance(value, bool):
            return 'bool'
        if isinstance(value, int):
            return 'int'
        if isinstance(value, float):
            # float that is integer-like treat as int
            if math.isfinite(value) and float(value).is_integer():
                return 'int'
            return 'float'

        # strings: try to be smart
        if isinstance(value, str):
            s = value.strip()
            if not s:
                return None

            # boolean-like strings
            if s.lower() in ('true', 'false', 't', 'f', 'yes', 'no'):
                return 'bool'

            # try JSON decode
            try:
                decoded = json.loads(s)
                # recursively infer
                if isinstance(decoded, bool):
                    return 'bool'
                if isinstance(decoded, int):
                    return 'int'
                if isinstance(decoded, float):
                    if math.isfinite(decoded) and float(decoded).is_integer():
                        return 'int'
                    return 'float'
                if isinstance(decoded, str):
                    # if JSON decoded to string, fallthrough to numeric attempt below
                    s = decoded.strip()
                if isinstance(decoded, dict):
                    # look for common value keys
                    for k in ('value', 'val', 'v', 'data', 'measurement'):
                        if k in decoded:
                            return self._infer_type(decoded[k])
                    # try to infer from any single-field dict value
                    if len(decoded) == 1:
                        only_val = next(iter(decoded.values()))
                        return self._infer_type(only_val)
                    return None
                if isinstance(decoded, list) and decoded:
                    # infer from first element
                    return self._infer_type(decoded[0])
            except Exception:
                pass

            # numeric strings
            try:
                f = float(s)
                if math.isfinite(f) and float(f).is_integer():
                    return 'int'
                return 'float'
            except Exception:
                pass

            # fallback: treat as plain string
            return 'str'

        # unknown types
        return None

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        batch_size = options.get('batch_size') or 500
        model_names = options.get('models') or ['TwoMinuteData', 'TenMinuteData', 'HourlyData', 'DailyData']

        self.stdout.write(self.style.MIGRATE_HEADING('Start backfill value_type'))
        self.stdout.write(f'Dry run: {dry_run}, batch_size: {batch_size}, models: {model_names}')

        for model_name in model_names:
            Model = getattr(models, model_name, None)
            if Model is None:
                self.stdout.write(self.style.WARNING(f'Model {model_name} not found in data_entry.models; skipping'))
                continue

            qs = Model.objects.filter(value_type__isnull=True)
            total = qs.count()
            if total == 0:
                self.stdout.write(self.style.SUCCESS(f'[{model_name}] No rows need backfill'))
                continue

            self.stdout.write(self.style.NOTICE(f'[{model_name}] {total} rows to inspect'))
            offset = 0
            updated_total = 0

            while True:
                batch = list(qs.order_by('id')[offset:offset + batch_size])
                if not batch:
                    break

                to_update = []
                for obj in batch:
                    inferred = None
                    # 1) prefer value field
                    if obj.value is not None:
                        inferred = self._infer_type(obj.value)
                    # 2) fallback to aggregate fields
                    if inferred is None:
                        for fld in ('min_value', 'avg_value', 'max_value', 'sum_value'):
                            val = getattr(obj, fld, None)
                            if val is not None:
                                inferred = self._infer_type(val)
                                if inferred:
                                    break
                    # 3) boolean guess: if fields absent but count present and maybe min/max 0/1
                    if inferred is None and obj.count is not None:
                        # try to detect boolean-like with min/max
                        if obj.min_value in (0, 1) and obj.max_value in (0, 1):
                            inferred = 'bool'

                    if inferred:
                        obj.value_type = inferred
                        to_update.append(obj)

                if not dry_run and to_update:
                    try:
                        with transaction.atomic():
                            Model.objects.bulk_update(to_update, ['value_type'])
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f'Error bulk updating {model_name}: {e}'))
                updated_total += len(to_update)

                self.stdout.write(f'[{model_name}] processed {min(offset + batch_size, total)}/{total} - updates in batch: {len(to_update)}')
                offset += batch_size

            self.stdout.write(self.style.SUCCESS(f'[{model_name}] Completed. total_updated={updated_total}'))

        self.stdout.write(self.style.MIGRATE_LABEL('Backfill finished'))
