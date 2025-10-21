from django.apps import AppConfig
from pathlib import Path
import logging

from utils.protocol.context import RegistersSlaveContext, CONTEXT_REGISTRY
from utils.protocol.context.manager import restore_json_blocks_to_slave_context

logger = logging.getLogger(__name__)

class LSISsocketConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'LSISsocket'
    verbose_name = 'LSISsocket'

    def ready(self):
        try:
            app_path = Path(self.path)
            cs_path = app_path / 'context_store'
            cs_path.mkdir(parents=True, exist_ok=True)

            slave_ctx = RegistersSlaveContext(createMemory=None)
            restored = restore_json_blocks_to_slave_context(app_path, slave_ctx, load_most_recent=True)
            CONTEXT_REGISTRY[self.name] = slave_ctx
            logger.info(f"[{self.name}] Restored {len(restored)} blocks in App.ready()")
        except Exception:
            logger.exception(f"[{self.name}] Failed to restore context in App.ready()")
