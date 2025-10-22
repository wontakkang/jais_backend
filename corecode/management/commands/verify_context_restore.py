from pathlib import Path
from django.core.management.base import BaseCommand
from django.apps import apps as django_apps
import logging

from utils.protocol.context import CONTEXT_REGISTRY, RegistersSlaveContext

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Verify sqlite-first context restore for installed Django apps. Optionally perform restore to populate CONTEXT_REGISTRY.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Do not perform restore; only report DB vs registry state')
        parser.add_argument('--apps', nargs='*', help='List of app labels to check (default: all)')

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        apps_filter = options.get('apps')

        # lazy import sqlite helper
        try:
            from utils.protocol.context.sqlite_store import list_app_states
        except Exception:
            list_app_states = None

        try:
            from utils.protocol.context.manager import restore_json_blocks_to_slave_context, get_or_create_registry_entry
        except Exception:
            restore_json_blocks_to_slave_context = None
            get_or_create_registry_entry = None

        total = 0
        issues = []

        for ac in django_apps.get_app_configs():
            label = ac.name.split('.')[-1]
            if apps_filter and label not in apps_filter:
                continue
            total += 1
            app_path = Path(ac.path)

            # DB count
            db_count = None
            if list_app_states:
                try:
                    db_objs = list_app_states(label) or {}
                    db_count = len(db_objs) if isinstance(db_objs, dict) else 0
                except Exception as e:
                    db_count = None
                    logger.exception(f'list_app_states failed for {label}: {e}')

            # registry state
            reg_entry = CONTEXT_REGISTRY.get(label)
            reg_count = None
            try:
                if reg_entry is None:
                    reg_count = 0
                else:
                    if hasattr(reg_entry, 'get_all_state') and callable(getattr(reg_entry, 'get_all_state')):
                        st = reg_entry.get_all_state() or {}
                        reg_count = len(st) if isinstance(st, dict) else 0
                    elif isinstance(reg_entry, dict):
                        reg_count = len(reg_entry.get('store', {}).get('state', {}) or {})
                    else:
                        store = getattr(reg_entry, 'store', None)
                        if isinstance(store, dict):
                            reg_count = len(store.get('state', {}) or {})
                        else:
                            reg_count = 0
            except Exception:
                reg_count = None

            self.stdout.write(f'App: {label} | DB blocks: {db_count} | Registry blocks: {reg_count}')

            # If dry-run, skip restore
            if dry_run:
                if db_count and reg_count is not None and db_count != reg_count:
                    issues.append((label, db_count, reg_count))
                continue

            # perform restore if registry is empty but DB has entries, or to re-sync
            if restore_json_blocks_to_slave_context and (reg_count == 0 or (db_count and db_count != reg_count)):
                try:
                    # ensure entry exists
                    entry = reg_entry or (get_or_create_registry_entry(label, create_slave=True) if get_or_create_registry_entry else RegistersSlaveContext(createMemory=None))
                    restored = restore_json_blocks_to_slave_context(app_path, entry, load_most_recent=False)
                    restored_count = len(restored) if isinstance(restored, dict) else 0
                    self.stdout.write(f'  -> Performed restore for {label}, restored blocks: {restored_count}')
                    # update registry counts
                    try:
                        if hasattr(entry, 'get_all_state') and callable(getattr(entry, 'get_all_state')):
                            st2 = entry.get_all_state() or {}
                            reg_count = len(st2) if isinstance(st2, dict) else reg_count
                        elif isinstance(entry, dict):
                            reg_count = len(entry.get('store', {}).get('state', {}) or {})
                    except Exception:
                        pass
                    if db_count and reg_count is not None and db_count != reg_count:
                        issues.append((label, db_count, reg_count))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'  -> Restore failed for {label}: {e}'))
                    logger.exception(f'Restore failed for {label}')
                    issues.append((label, 'restore_failed', str(e)))

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f'Checked {total} apps'))
        if issues:
            self.stdout.write(self.style.WARNING('Discrepancies or failures:'))
            for it in issues:
                self.stdout.write(self.style.WARNING(f' - {it}'))
        else:
            self.stdout.write(self.style.SUCCESS('No issues detected (DB vs registry counts match or restored)'))
