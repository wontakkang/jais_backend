from django.apps import AppConfig
from pathlib import Path
import logging

from utils.protocol.context import RegistersSlaveContext, CONTEXT_REGISTRY
from utils.protocol.context.manager import restore_json_blocks_to_slave_context

logger = logging.getLogger(__name__)

class CorecodeConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'corecode'
    verbose_name = 'corecode'

    def ready(self):
        try:
            app_path = Path(self.path)
            cs_path = app_path / 'context_store'
            cs_path.mkdir(parents=True, exist_ok=True)

            # Create or ensure a RegistersSlaveContext
            slave_ctx = RegistersSlaveContext(createMemory=None)

            # Try to load blocks from sqlite first (DB-backed store)
            restored = {}
            try:
                from utils.protocol.context.sqlite_store import list_app_states
                from utils.protocol.context import JSONRegistersDataBlock

                db_objs = list_app_states(self.name) or {}
                if isinstance(db_objs, dict) and db_objs:
                    for mem_name, mem_obj in db_objs.items():
                        try:
                            if isinstance(mem_obj, dict) and 'values' in mem_obj:
                                try:
                                    block = JSONRegistersDataBlock.from_json(mem_obj)
                                except Exception:
                                    block = mem_obj
                            else:
                                block = mem_obj

                            # assign into slave_ctx using supported APIs
                            try:
                                if hasattr(slave_ctx, 'set_state') and callable(getattr(slave_ctx, 'set_state')):
                                    slave_ctx.set_state(mem_name, block)
                                else:
                                    store_attr = getattr(slave_ctx, 'store', None)
                                    if isinstance(store_attr, dict):
                                        store_attr[mem_name] = block
                                    else:
                                        setattr(slave_ctx, mem_name, block)
                                restored[mem_name] = block
                            except Exception:
                                continue
                        except Exception:
                            continue
            except Exception:
                restored = {}

            # If DB returned nothing, fallback to existing file/DB-aware restore helper
            try:
                if not restored:
                    restored = restore_json_blocks_to_slave_context(app_path, slave_ctx, load_most_recent=False)
            except Exception:
                logger.exception(f"[{self.name}] Fallback restore_json_blocks_to_slave_context failed")

            # Register into global registry
            CONTEXT_REGISTRY[self.name] = slave_ctx
            logger.info(f"[{self.name}] Restored {{len(restored)}} blocks in App.ready() (sqlite first)")
        except Exception:
            logger.exception(f"[{self.name}] Failed to restore context in App.ready()")


    # SQLITE_FIRST_RESTORE_APPLIED
