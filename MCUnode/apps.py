from django.apps import AppConfig
from pathlib import Path
import logging

from utils.protocol.context import RegistersSlaveContext, CONTEXT_REGISTRY
from utils.protocol.context.manager import (
    restore_json_blocks_to_slave_context,
    ensure_context_store_for_apps,
    get_or_create_registry_entry,
)

logger = logging.getLogger(__name__)

class McunodeConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'MCUnode'
    verbose_name = 'MCUnode'

    def ready(self):
        app_path = Path(self.path)
        cs_dir = app_path / 'context_store'
        cs_dir.mkdir(parents=True, exist_ok=True)

        # Ensure registry entry exists (prefer RegistersSlaveContext)
        try:
            entry = get_or_create_registry_entry(self.name, create_slave=True)
        except Exception:
            entry = None

        # 1) Try block-based restore (MEMORY blocks)
        try:
            if entry is not None:
                restored = restore_json_blocks_to_slave_context(app_path, entry, load_most_recent=True, use_key_as_memory_name=True)
                logger.info(f"[{self.name}] Restored {len(restored)} memory blocks in App.ready() (block-based)")
        except Exception:
            logger.exception(f"[{self.name}] block-based restore failed in App.ready()")

        # 2) If still empty, try aggregated state.json (top-level serial -> STATUS/Meta/...)
        try:
            still_empty = True
            if entry is not None and hasattr(entry, 'get_all_state') and callable(getattr(entry, 'get_all_state')):
                try:
                    cur = entry.get_all_state()
                    if isinstance(cur, dict) and cur:
                        still_empty = False
                except Exception:
                    still_empty = True

            if still_empty:
                app_stores = ensure_context_store_for_apps()
                cs = app_stores.get(self.name)
                cs_dir_path = Path(cs) if cs else cs_dir
                state_path = cs_dir_path / 'state.json'
                if state_path.exists():
                    try:
                        import json as _json
                        with state_path.open('r', encoding='utf-8') as sf:
                            disk_state = _json.load(sf)
                    except Exception:
                        disk_state = None

                    if isinstance(disk_state, dict) and disk_state:
                        # Apply into entry using API if available
                        try:
                            if entry is not None and hasattr(entry, 'set_state') and callable(getattr(entry, 'set_state')):
                                for serial_k, v in disk_state.items():
                                    try:
                                        entry.set_state(serial_k, v)
                                    except Exception:
                                        pass
                            else:
                                # ensure a simple dict-backed registry entry so StateViewSet can read it
                                try:
                                    CONTEXT_REGISTRY[self.name] = {'store': {'state': dict(disk_state)}}
                                except Exception:
                                    pass

                            # attempt to sync per-serial (best-effort)
                            try:
                                from utils.protocol.context.manager import _sync_registry_state
                                for serial_k, v in disk_state.items():
                                    try:
                                        _sync_registry_state(self.name, serial_k, v)
                                    except Exception:
                                        pass
                            except Exception:
                                pass

                            logger.info(f"[{self.name}] Restored aggregated state.json into registry in App.ready()")
                        except Exception:
                            logger.exception(f"[{self.name}] Failed to apply aggregated state.json into registry in App.ready()")
        except Exception:
            logger.exception(f"[{self.name}] Aggregated-state restore check failed in App.ready()")