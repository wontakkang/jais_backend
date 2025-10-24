import logging
from django.apps import AppConfig

from pathlib import Path
logger = logging.getLogger(__name__)

class AgriseedConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'agriseed'
    verbose_name = 'agriseed'

    def ready(self):
        try:
            # 컨텍스트 스토어 기능을 비활성화했습니다.
            # 이전에 이 앱은 utils.protocol.context 패키지를 사용해 상태를 복원했으나,
            # 해당 기능은 현재 제거되어 더 이상 복원 작업을 수행하지 않습니다.
            logger.info(f"[{self.name}] context_store 기능이 비활성화되어 App.ready()에서 복원 작업을 건너뜁니다")
        except Exception:
            logger.exception(f"[{self.name}] App.ready() 실행 중 예외 발생")
