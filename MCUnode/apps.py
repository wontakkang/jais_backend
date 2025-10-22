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
        try:
            app_path = Path(self.path)
            cs_path = app_path / 'context_store'
            cs_path.mkdir(parents=True, exist_ok=True)

            # RegistersSlaveContext 생성 또는 확인
            slave_ctx = RegistersSlaveContext(createMemory=None)

            # 먼저 sqlite에서 블록 로드 시도 (DB 기반 저장소)
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

                            # 지원되는 API를 사용하여 slave_ctx에 할당
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

            # DB에서 아무것도 반환하지 않으면 기존 파일/DB 인식 복원 도우미로 대체
            try:
                if not restored:
                    restored = restore_json_blocks_to_slave_context(app_path, slave_ctx, load_most_recent=False)
            except Exception:
                logger.exception(f"[{self.name}] 대체 restore_json_blocks_to_slave_context 실패")

            # 전역 레지스트리에 등록
            CONTEXT_REGISTRY[self.name] = slave_ctx
            logger.info(f"[{self.name}] App.ready()에서 {len(restored)}개 블록 복원됨 (sqlite 우선)")
        except Exception:
            logger.exception(f"[{self.name}] App.ready()에서 컨텍스트 복원 실패")


    # SQLITE_FIRST_RESTORE_APPLIED
